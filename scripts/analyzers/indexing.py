"""Indexing run analyzer.

Reads all events for a given ``run_id`` from ``data/indexing-progress.jsonl``,
introspects the target Qdrant collection (count, config, sample probes),
diffs against the previous report for the same subject, and emits a
ReportSpec ready for ``report_writer.write_report``.

Compatibility notes:
  * Uses ``client.query_points(query=vec, ...)`` — ``client.search`` is removed
    in qdrant-client ≥ 1.13 (skill: qdrant-operations §"Диагностика").
  * Alias-aware via ``get_aliases()``; some collections are named-vector
    layouts (Phase 8.12 BSL collections are single-vector and don't need
    ``using``).
  * Self-recall@1 sanity probe — picks ≤5 random points, queries by their
    own vector, expects top-1 == self. Catches HNSW corruption or wrong
    ``using=`` parameter on named-vector collections.
"""

from __future__ import annotations

import json
import math
import os
import random
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

from .base import AnalyzerBase, ReportSpec

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models as qmodels

    _QDRANT_AVAILABLE = True
except ImportError:
    _QDRANT_AVAILABLE = False
    qmodels = None  # type: ignore[assignment]


HEARTBEAT_GAP_WARN_S = 60.0
NORM_DRIFT_WARN_PCT = 0.25
SELF_RECALL_TARGET = 0.95
TAIL_BYTES = 4 * 1024 * 1024


def _load_run_events(jsonl_path: Path, run_id: str) -> list[dict[str, Any]]:
    if not jsonl_path.exists():
        return []
    size = jsonl_path.stat().st_size
    with jsonl_path.open("rb") as fh:
        if size > TAIL_BYTES:
            fh.seek(size - TAIL_BYTES)
            fh.readline()
        raw = fh.read().decode("utf-8", errors="replace")
    events: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("run_id") == run_id:
            events.append(rec)
    return events


def _find_previous_report(
    reports_dir: Path, subject: str, current_run_id: str
) -> dict[str, Any] | None:
    indexing_dir = reports_dir / "indexing"
    if not indexing_dir.exists():
        return None
    candidates = sorted(indexing_dir.glob("*.json"), reverse=True)
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("collection") == subject and data.get("run_id") != current_run_id:
            return data
    return None


class IndexingAnalyzer(AnalyzerBase):
    def __init__(
        self,
        run_id: str,
        progress_jsonl: Path,
        reports_dir: Path,
        collection: str | None = None,
        qdrant_url: str | None = None,
        verbosity: str = "medium",
        sample_size: int = 200,
    ) -> None:
        self.run_id = run_id
        self.progress_jsonl = progress_jsonl
        self.reports_dir = reports_dir
        self.collection_override = collection
        self.qdrant_url = qdrant_url or os.environ.get("QDRANT_URL", "http://localhost:6333")
        self.verbosity = verbosity
        self.sample_size = sample_size

    def analyze(self) -> ReportSpec:
        events = _load_run_events(self.progress_jsonl, self.run_id)
        if not events:
            raise RuntimeError(
                f"No events found for run_id={self.run_id!r} in {self.progress_jsonl}"
            )

        run_start = next((e for e in events if e.get("category") == "run_start"), None)
        run_end = next((e for e in reversed(events) if e.get("category") == "run_end"), None)
        script = (events[0] if events else {}).get("script", "unknown")
        duration = (run_end or {}).get("elapsed_s") or (events[-1] if events else {}).get(
            "elapsed_s"
        )

        collection = self._detect_collection(events, run_end)
        anomalies: list[str] = []

        spec = ReportSpec(
            mode="indexing",
            subject=collection,
            run_id=self.run_id,
            generated_at=datetime.now().isoformat(timespec="seconds"),
            indexer_script=script,
            duration_sec=float(duration) if duration is not None else None,
        )

        startup = self._find_startup(events)
        spec.sections.append(("Run identity & CLI", self._section_identity(startup, run_start)))
        spec.sections.append(("Run end summary", self._section_run_end(run_end, anomalies)))
        spec.sections.append(("Stages & timing", self._section_stages(events, anomalies)))
        spec.sections.append(("Discrete events", self._section_events(events)))
        spec.sections.append(("Heartbeat gaps", self._section_heartbeat(events, anomalies)))
        spec.sections.append(("Resource telemetry", self._section_telemetry(events, anomalies)))

        coll_info = self._fetch_collection_info(collection, anomalies)
        spec.sections.append(("Collection state", self._section_collection(coll_info, anomalies)))

        probes: dict[str, Any] = {}
        chunk_stats: dict[str, Any] = {}
        if _QDRANT_AVAILABLE and coll_info.get("ok"):
            probes = self._run_quality_probes(collection, coll_info, anomalies)
            spec.sections.append(("Quality probes", self._section_probes(probes)))
            chunk_stats = self._run_chunk_metrics(collection, coll_info, anomalies)
            if chunk_stats:
                from .charts import histogram
                from .chunk_metrics import render_chunk_section

                spec.sections.append(("Chunk-level metrics", render_chunk_section(chunk_stats)))
                char_lens = chunk_stats.get("char_length_distribution") or []
                if char_lens and len(char_lens) >= 10:
                    spec.sections.append(
                        (
                            "Chunk char-length histogram",
                            histogram(char_lens, bins=10, label="Char length distribution"),
                        )
                    )
        else:
            spec.sections.append(
                (
                    "Quality probes",
                    "_Skipped — qdrant_client недоступен или коллекция не отвечает._",
                )
            )

        prev = _find_previous_report(self.reports_dir, collection, self.run_id)
        if prev:
            spec.sections.append(
                ("Diff vs previous run", self._section_diff(prev, coll_info, duration, anomalies))
            )
        else:
            spec.sections.append(
                (
                    "Diff vs previous run",
                    f"_Нет предыдущего отчёта для `{collection}` — это первый ран._",
                )
            )

        # Persist anomalies to registry (closed-loop foundation)
        from .anomaly_tracker import AnomalyTracker

        tracker = AnomalyTracker(self.reports_dir)
        anomaly_stats = tracker.record(collection, anomalies, self.run_id)
        spec.sections.append(("Anomaly history", tracker.summary_section(collection)))

        spec.anomalies = anomalies
        spec.summary = self._build_summary(run_end, coll_info, duration, anomalies)

        # Verdict gauge + auto action items (rendered as a pre-TL;DR section)
        from .verdict import compute_verdict, extract_wins, render_verdict_section

        verdict = compute_verdict(anomalies)
        verdict.wins = extract_wins(spec.summary, probes)
        spec.sections.insert(
            0, ("Verdict & action items", render_verdict_section(verdict, anomaly_stats))
        )

        spec.raw.update(
            {
                "run_id": self.run_id,
                "collection": collection,
                "script": script,
                "duration_sec": duration,
                "events_total": len(events),
                "run_end": run_end,
                "startup": startup,
                "collection_info": coll_info,
                "probes": probes,
                "chunk_metrics": {
                    k: v for k, v in chunk_stats.items() if k != "char_length_distribution"
                },
                "anomalies": anomalies,
                "anomaly_stats": {k: v for k, v in anomaly_stats.items() if k != "chronic"},
                "verdict": {
                    "gauge": verdict.gauge,
                    "fails": verdict.fails,
                    "warns": verdict.warns,
                    "infos": verdict.infos,
                    "wins": verdict.wins,
                    "action_items": verdict.action_items,
                },
            }
        )
        return spec

    def _run_chunk_metrics(
        self, collection: str, info: dict, anomalies: list[str]
    ) -> dict[str, Any]:
        """Scroll with_payload=True, compute chunk metrics from text fields."""
        if not _QDRANT_AVAILABLE:
            return {}
        try:
            from .chunk_metrics import analyze_chunks

            client = QdrantClient(url=self.qdrant_url, timeout=30)
            physical = info["physical_name"]
            points_total = int(info.get("points_count") or 0)
            sample_n = min(self.sample_size, points_total) if points_total else self.sample_size
            if sample_n <= 0:
                return {}
            scroll = client.scroll(
                collection_name=physical,
                limit=sample_n,
                with_payload=True,
                with_vectors=False,
            )
            points = scroll[0] if isinstance(scroll, tuple) else getattr(scroll, "points", [])
            payloads = [getattr(p, "payload", None) for p in points]
            metrics = analyze_chunks(payloads)
            empty = metrics.get("empty_chunks") or 0
            if empty > metrics.get("total_sampled", 1) * 0.1:
                anomalies.append(
                    f"Empty chunks rate {empty}/{metrics['total_sampled']} > 10% — chunker/parser bug suspected."
                )
            nd = metrics.get("near_duplicates") or {}
            if nd.get("rate_pct", 0) > 5.0:
                anomalies.append(
                    f"Near-duplicate chunks rate {nd['rate_pct']}% — chunker dedup gap."
                )
            return metrics
        except Exception:
            return {}

    # ---- detection ----------------------------------------------------

    def _detect_collection(self, events: list[dict], run_end: dict | None) -> str:
        if self.collection_override:
            return self.collection_override
        if run_end and isinstance(run_end.get("collection"), str):
            return run_end["collection"]
        for e in events:
            v = e.get("collection")
            if isinstance(v, str):
                return v
        return "unknown_collection"

    def _find_startup(self, events: list[dict]) -> dict[str, Any]:
        for e in events:
            if e.get("category") == "event" and e.get("name") == "startup":
                return e
        return {}

    # ---- section renderers --------------------------------------------

    def _section_identity(self, startup: dict, run_start: dict | None) -> str:
        lines = []
        pid = (run_start or {}).get("pid", "?")
        lines.append(f"- **PID:** `{pid}`")
        for key in (
            "embedder",
            "project",
            "qdrant_url",
            "tei_url",
            "batch_size",
            "pooling_mode",
            "region_aware",
            "recreate",
            "paths_mode",
            "dry_run",
            "limit",
            "only_paths",
            "db",
        ):
            if key in startup:
                lines.append(f"- **{key}:** `{startup[key]}`")
        if not lines:
            return "_Нет startup-события — запускали без CLI parser._"
        return "\n".join(lines)

    def _section_run_end(self, run_end: dict | None, anomalies: list[str]) -> str:
        if not run_end:
            anomalies.append("Нет `run_end` события — индексер мог упасть до atexit.")
            return "_run_end отсутствует (ABORT?)._"
        lines = []
        for k, v in run_end.items():
            if k in ("ts", "run_id", "script", "category", "elapsed_s"):
                continue
            lines.append(f"- **{k}:** `{v}`")
        errors = run_end.get("errors")
        if isinstance(errors, int | float) and errors > 0:
            anomalies.append(f"`run_end.errors={errors}` — были ошибки в pipeline.")
        return "\n".join(lines) or "_(пусто)_"

    def _section_stages(self, events: list[dict], anomalies: list[str]) -> str:
        ends: list[tuple[str, float, bool, str | None]] = []
        for e in events:
            if e.get("category") == "stage_end":
                name = e.get("name", "")
                dur = float(e.get("elapsed_s", 0.0))
                ok = bool(e.get("ok", True))
                err = e.get("err")
                ends.append((name, dur, ok, err))
                if not ok:
                    anomalies.append(f"Stage `{name}` завершился с ошибкой: {err}")
        if not ends:
            return "_Нет stage-событий._"
        from .charts import waterfall

        ends_sorted = sorted(ends, key=lambda x: x[1], reverse=True)
        lines = ["| Stage | Duration | OK | Err |", "|-------|---------:|:--:|-----|"]
        for name, dur, ok, err in ends_sorted:
            lines.append(f"| `{name}` | {dur:.2f}s | {'+' if ok else 'x'} | {err or ''} |")
        # Chronological waterfall (preserves original event order, not sorted)
        chrono = [(name, dur) for name, dur, ok, _ in ends if ok]
        if chrono:
            lines.append("")
            lines.append(waterfall(chrono))
        return "\n".join(lines)

    def _section_events(self, events: list[dict]) -> str:
        discrete = [e for e in events if e.get("category") == "event"]
        if not discrete:
            return "_Нет discrete events._"
        lines = ["| ts | name | payload |", "|----|------|---------|"]
        for e in discrete:
            payload = {
                k: v
                for k, v in e.items()
                if k not in ("ts", "run_id", "script", "category", "elapsed_s", "name")
            }
            payload_str = ", ".join(f"`{k}`=`{v}`" for k, v in payload.items())
            lines.append(f"| {e.get('ts', '')} | `{e.get('name', '')}` | {payload_str} |")
        return "\n".join(lines)

    def _section_telemetry(self, events: list[dict], anomalies: list[str]) -> str:
        tels = [e for e in events if e.get("category") == "telemetry"]
        if not tels:
            return "_Нет telemetry events (psutil не установлен или INDEXING_NO_TELEMETRY=1)._"
        rss = [float(e.get("rss_mb") or 0) for e in tels if e.get("rss_mb") is not None]
        gpu = [float(e.get("gpu_vram_mb") or 0) for e in tels if e.get("gpu_vram_mb") is not None]
        cpu = [float(e.get("cpu_pct") or 0) for e in tels if e.get("cpu_pct") is not None]
        lines = [f"- **samples:** {len(tels)}"]
        if rss:
            peak = max(rss)
            lines.append(f"- **RSS (MB):** peak=`{peak:.0f}`, mean=`{statistics.fmean(rss):.0f}`")
            if peak > 8000:
                anomalies.append(
                    f"Peak RSS = {peak:.0f} MB > 8 GB — high memory pressure, consider streaming."
                )
        if gpu:
            lines.append(
                f"- **GPU VRAM (MB):** peak=`{max(gpu):.0f}`, mean=`{statistics.fmean(gpu):.0f}`"
            )
        if cpu:
            lines.append(f"- **CPU %:** peak=`{max(cpu):.1f}`, mean=`{statistics.fmean(cpu):.1f}`")
        return "\n".join(lines)

    def _section_heartbeat(self, events: list[dict], anomalies: list[str]) -> str:
        hbs = [e for e in events if e.get("category") == "heartbeat"]
        if not hbs:
            return "_Нет heartbeat — короткий run либо отключён._"
        max_idle = max((float(e.get("idle_s", 0.0)) for e in hbs), default=0.0)
        if max_idle > HEARTBEAT_GAP_WARN_S:
            anomalies.append(
                f"Heartbeat зафиксировал idle_s={max_idle:.0f}s — возможное зависание стадии."
            )
        lines = [
            f"- **heartbeats:** {len(hbs)}",
            f"- **max idle_s:** {max_idle:.1f}s",
        ]
        last = hbs[-1]
        lines.append(
            "- **последний снимок:** "
            + ", ".join(
                f"`{k}={v}`"
                for k, v in last.items()
                if k not in ("ts", "run_id", "script", "category")
            )
        )
        return "\n".join(lines)

    def _section_collection(self, info: dict, anomalies: list[str]) -> str:
        if not info.get("ok"):
            anomalies.append(f"Qdrant introspection failed: {info.get('error', 'unknown')}")
            return f"_Не удалось получить состояние коллекции: {info.get('error', '?')}_"
        lines = [
            f"- **physical name:** `{info.get('physical_name', info.get('name'))}`",
            f"- **points_count:** `{info.get('points_count')}`",
            f"- **vectors_count:** `{info.get('vectors_count')}`",
            f"- **status:** `{info.get('status')}`",
            f"- **distance:** `{info.get('distance')}`",
            f"- **dimension:** `{info.get('dimension')}`",
            f"- **on_disk:** `{info.get('on_disk')}`",
        ]
        if info.get("quantization"):
            lines.append(f"- **quantization:** `{info['quantization']}`")
        named = info.get("named_vectors") or {}
        if named:
            lines.append("- **named vectors:**")
            for vname, vmeta in named.items():
                lines.append(
                    f"  - `{vname}` → size={vmeta.get('size')}, distance={vmeta.get('distance')}"
                )
        return "\n".join(lines)

    def _section_probes(self, probes: dict) -> str:
        lines: list[str] = []
        sample = probes.get("sample_size", 0)
        lines.append(f"- **sample_size:** `{sample}`")
        norm = probes.get("norm")
        if norm:
            extras = []
            if "outliers_3sigma" in norm:
                extras.append(f"outliers_3σ=`{norm['outliers_3sigma']}`")
            extra_str = (", " + ", ".join(extras)) if extras else ""
            lines.append(
                f"- **L2 norm:** mean=`{norm['mean']:.4f}`, std=`{norm['std']:.4f}`, "
                f"min=`{norm['min']:.4f}`, max=`{norm['max']:.4f}`{extra_str}"
            )
        zero = probes.get("zero_vectors")
        if zero is not None:
            lines.append(f"- **zero-vector points:** `{zero}`")
        recall = probes.get("self_recall_at_1")
        if recall is not None:
            ok_tag = "OK" if recall >= SELF_RECALL_TARGET else "FAIL"
            lines.append(
                f"- **self recall@1:** `{recall:.3f}` ({ok_tag}, target ≥ {SELF_RECALL_TARGET})"
            )
        dim_check = probes.get("dimension_check")
        if dim_check is not None:
            lines.append(f"- **dimension check:** {'match' if dim_check else 'MISMATCH'}")
        eff_rank = probes.get("effective_rank")
        if eff_rank is not None:
            ratio = probes.get("effective_rank_ratio", 0)
            cap = probes.get("effective_rank_max")
            lines.append(
                f"- **effective rank:** `{eff_rank}/{cap}` (ratio={ratio:.2%}, "
                f"<30% = collapse risk)"
            )
        aniso = probes.get("anisotropy_mean")
        if aniso is not None:
            tag = " !" if aniso > 0.5 else ""
            lines.append(
                f"- **anisotropy mean cos:** `{aniso:.4f}` "
                f"(>0.5 = collapsed cone, ideal ≈ 0){tag}"
            )
        if probes.get("error"):
            lines.append(f"- **probe error:** `{probes['error']}`")
        return "\n".join(lines) if lines else "_(пусто)_"

    def _section_diff(
        self,
        prev: dict,
        coll: dict,
        duration: float | None,
        anomalies: list[str],
    ) -> str:
        lines = []
        prev_points = (prev.get("collection_info") or {}).get("points_count")
        cur_points = coll.get("points_count")
        if isinstance(prev_points, int) and isinstance(cur_points, int):
            delta = cur_points - prev_points
            pct = (delta / prev_points * 100) if prev_points else float("inf")
            lines.append(
                f"- **points:** `{prev_points}` -> `{cur_points}` (Δ {delta:+d}, {pct:+.1f}%)"
            )
        prev_dur = prev.get("duration_sec")
        if isinstance(prev_dur, int | float) and isinstance(duration, int | float):
            d = duration - prev_dur
            lines.append(f"- **duration:** `{prev_dur:.1f}s` -> `{duration:.1f}s` (Δ {d:+.1f}s)")
        prev_norm = ((prev.get("probes") or {}).get("norm") or {}).get("mean")
        cur_norm = ((coll.get("probes") or {}).get("norm") or {}).get("mean")
        if prev_norm and cur_norm:
            drift = abs(cur_norm - prev_norm) / prev_norm
            lines.append(f"- **L2 norm mean drift:** `{drift:.2%}`")
            if drift > NORM_DRIFT_WARN_PCT:
                anomalies.append(
                    f"L2 norm mean изменился на {drift:.0%} vs прошлого ран — возможный model swap."
                )
        prev_dim = (prev.get("collection_info") or {}).get("dimension")
        cur_dim = coll.get("dimension")
        if prev_dim and cur_dim and prev_dim != cur_dim:
            anomalies.append(f"Dimension изменился: {prev_dim} -> {cur_dim} (model swap?).")
            lines.append(f"- **dimension:** `{prev_dim}` -> `{cur_dim}` !")
        return "\n".join(lines) or "_Нет сопоставимых метрик._"

    # ---- Qdrant integration -------------------------------------------

    def _fetch_collection_info(self, collection: str, anomalies: list[str]) -> dict[str, Any]:
        if not _QDRANT_AVAILABLE:
            return {"ok": False, "error": "qdrant_client not installed"}
        try:
            client = QdrantClient(url=self.qdrant_url, timeout=10)
            physical = self._resolve_alias(client, collection)
            info = client.get_collection(physical)
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        params = info.config.params if info.config else None
        vectors_cfg = params.vectors if params else None
        named: dict[str, dict[str, Any]] = {}
        dim = None
        distance = None
        if hasattr(vectors_cfg, "size"):
            dim = vectors_cfg.size
            distance = str(vectors_cfg.distance)
        elif isinstance(vectors_cfg, dict):
            for vname, vmeta in vectors_cfg.items():
                named[vname] = {
                    "size": getattr(vmeta, "size", None),
                    "distance": str(getattr(vmeta, "distance", None)),
                }
                if dim is None:
                    dim = getattr(vmeta, "size", None)
                    distance = str(getattr(vmeta, "distance", None))
        quant = None
        try:
            q = info.config.quantization_config
            if q is not None:
                quant = type(q).__name__
        except AttributeError:
            pass
        try:
            on_disk = bool(getattr(vectors_cfg, "on_disk", False))
        except Exception:
            on_disk = None
        return {
            "ok": True,
            "name": collection,
            "physical_name": physical,
            "points_count": info.points_count,
            "vectors_count": getattr(info, "vectors_count", None),
            "status": str(info.status),
            "distance": distance,
            "dimension": dim,
            "on_disk": on_disk,
            "quantization": quant,
            "named_vectors": named,
        }

    def _resolve_alias(self, client: QdrantClient, collection: str) -> str:
        try:
            for alias in client.get_aliases().aliases:
                if alias.alias_name == collection:
                    return alias.collection_name
        except Exception:
            pass
        return collection

    def _embedding_quality_metrics(
        self, vectors: list[list[float]], anomalies: list[str]
    ) -> dict[str, Any]:
        """Effective rank + anisotropy on a vector sample.

        - **Effective rank** (Roy & Vetterli 2007): exp(entropy(σ)) of normalized
          singular values. High = dimensions used uniformly; low = collapse.
          Fully sane sample → close to min(N, D).
        - **Anisotropy**: average pairwise cosine of N random pairs. High (>0.5)
          = embeddings collapsed into narrow cone (typical failure mode of
          contrastive models without negatives). 0 = perfectly isotropic.
        """
        out: dict[str, Any] = {}
        try:
            import numpy as np  # type: ignore[import-not-found]
        except ImportError:
            return out
        if len(vectors) < 3:
            return out
        # Cap heavy compute — SVD on huge matrices is expensive.
        cap = min(len(vectors), 500)
        m = np.asarray(vectors[:cap], dtype=np.float32)
        try:
            # Singular values directly (no covariance step — same eigenvalue spectrum
            # for L2-normalized inputs).
            sv = np.linalg.svd(m, compute_uv=False)
            sv2 = sv**2
            total = float(sv2.sum())
            if total > 0:
                p = sv2 / total
                # Shannon entropy of singular value distribution → exp gives
                # effective participation count (≈ "effective rank").
                p_safe = np.where(p > 0, p, 1.0)
                entropy = float(-(p * np.log(p_safe)).sum())
                eff_rank = int(round(float(np.exp(entropy))))
                out["effective_rank"] = eff_rank
                out["effective_rank_max"] = int(min(m.shape))
                ratio = eff_rank / min(m.shape) if min(m.shape) else 0.0
                out["effective_rank_ratio"] = round(ratio, 3)
                if ratio < 0.3 and min(m.shape) > 50:
                    anomalies.append(
                        f"Effective rank ratio {ratio:.2%} (rank={eff_rank}/{min(m.shape)}) — "
                        f"возможный embedding collapse."
                    )
        except Exception as exc:
            out["svd_error"] = f"{type(exc).__name__}: {exc}"

        try:
            import numpy as np

            # Anisotropy: average pairwise cosine of random distinct pairs.
            rng = np.random.default_rng(42)
            n_pairs = min(1000, cap * (cap - 1) // 2)
            if n_pairs >= 10:
                idx1 = rng.integers(0, cap, size=n_pairs)
                idx2 = rng.integers(0, cap, size=n_pairs)
                # Filter self-pairs
                mask = idx1 != idx2
                idx1, idx2 = idx1[mask], idx2[mask]
                if len(idx1) >= 10:
                    a = m[idx1]
                    b = m[idx2]
                    norms_a = np.linalg.norm(a, axis=1)
                    norms_b = np.linalg.norm(b, axis=1)
                    denom = norms_a * norms_b
                    denom = np.where(denom > 0, denom, 1.0)
                    cos = (a * b).sum(axis=1) / denom
                    aniso_mean = float(np.mean(cos))
                    aniso_p95 = float(np.percentile(cos, 95))
                    out["anisotropy_mean"] = round(aniso_mean, 4)
                    out["anisotropy_p95"] = round(aniso_p95, 4)
                    if aniso_mean > 0.5:
                        anomalies.append(
                            f"Anisotropy mean cos = {aniso_mean:.3f} > 0.5 — vectors collapsed into narrow cone."
                        )
        except Exception as exc:
            out["anisotropy_error"] = f"{type(exc).__name__}: {exc}"
        return out

    def _run_quality_probes(
        self, collection: str, info: dict, anomalies: list[str]
    ) -> dict[str, Any]:
        out: dict[str, Any] = {"sample_size": 0}
        try:
            client = QdrantClient(url=self.qdrant_url, timeout=30)
            physical = info["physical_name"]
            points_total = int(info.get("points_count") or 0)
            sample_n = min(self.sample_size, points_total) if points_total else self.sample_size
            if sample_n <= 0:
                return out

            scroll = client.scroll(
                collection_name=physical,
                limit=sample_n,
                with_payload=False,
                with_vectors=True,
            )
            points = scroll[0] if isinstance(scroll, tuple) else getattr(scroll, "points", [])

            named_vectors = info.get("named_vectors") or {}
            vector_name = next(iter(named_vectors), None) if named_vectors else None

            vectors: list[list[float]] = []
            ids: list[Any] = []
            for p in points:
                v = getattr(p, "vector", None)
                if isinstance(v, dict):
                    v = v.get(vector_name) if vector_name else next(iter(v.values()), None)
                if isinstance(v, list):
                    vectors.append(v)
                    ids.append(getattr(p, "id", None))

            out["sample_size"] = len(vectors)
            if not vectors:
                return out

            norms = [math.sqrt(sum(x * x for x in v)) for v in vectors]
            norm_mean = statistics.fmean(norms)
            norm_std = statistics.pstdev(norms) if len(norms) > 1 else 0.0
            out["norm"] = {
                "mean": norm_mean,
                "std": norm_std,
                "min": min(norms),
                "max": max(norms),
                "outliers_3sigma": sum(1 for n in norms if abs(n - norm_mean) > 3 * norm_std)
                if norm_std > 0
                else 0,
            }
            out["zero_vectors"] = sum(1 for n in norms if n < 1e-9)
            out.update(self._embedding_quality_metrics(vectors, anomalies))

            cur_dim = info.get("dimension")
            if cur_dim and len(vectors[0]) != cur_dim:
                anomalies.append(
                    f"Dimension mismatch: collection={cur_dim}, sample vector len={len(vectors[0])}"
                )
                out["dimension_check"] = False
            else:
                out["dimension_check"] = cur_dim is None or len(vectors[0]) == cur_dim

            probe_n = min(10, len(vectors))
            if probe_n > 0:
                hits_ok = 0
                tested = 0
                indices = (
                    random.sample(range(len(vectors)), probe_n)
                    if len(vectors) > probe_n
                    else list(range(probe_n))
                )
                # SQ-quantized collections (e.g. framework_code_v1_mrl_1024) need
                # explicit rescore=True — otherwise self-query may search in int8
                # space while scroll returns the exact stored fp32 vector,
                # producing false-negative top-1 misses. Skill `qdrant-operations`
                # §"Диагностика" notes the rescore policy.
                search_params = None
                if info.get("quantization") and qmodels is not None:
                    search_params = qmodels.SearchParams(
                        quantization=qmodels.QuantizationSearchParams(rescore=True, ignore=False)
                    )
                for idx in indices:
                    pt_id = ids[idx]
                    query_vec = vectors[idx]
                    try:
                        kwargs: dict[str, Any] = {
                            "collection_name": physical,
                            "query": query_vec,
                            "limit": 1,
                            "with_payload": False,
                        }
                        if vector_name:
                            kwargs["using"] = vector_name
                        if search_params is not None:
                            kwargs["search_params"] = search_params
                        response = client.query_points(**kwargs)
                        result = getattr(response, "points", response)
                    except Exception:
                        continue
                    if result and getattr(result[0], "id", None) == pt_id:
                        hits_ok += 1
                    tested += 1
                if tested:
                    recall = hits_ok / tested
                    out["self_recall_at_1"] = recall
                    if recall < SELF_RECALL_TARGET:
                        anomalies.append(
                            f"Self recall@1 = {recall:.2f} < {SELF_RECALL_TARGET} — HNSW corruption либо named-vector mismatch."
                        )
        except Exception as exc:
            out["error"] = f"{type(exc).__name__}: {exc}"
        return out

    def _build_summary(
        self, run_end: dict | None, coll: dict, duration: float | None, anomalies: list[str]
    ) -> dict[str, Any]:
        summary: dict[str, Any] = {}
        if duration is not None:
            summary["duration"] = f"{duration:.1f}s"
        if run_end:
            for k in ("files", "files_indexed", "symbols", "chunks", "embeddings_done", "errors"):
                if k in run_end:
                    summary[k] = run_end[k]
        if coll.get("ok"):
            summary["points_after"] = coll.get("points_count")
            summary["dimension"] = coll.get("dimension")
        summary["anomalies"] = len(anomalies)
        return summary
