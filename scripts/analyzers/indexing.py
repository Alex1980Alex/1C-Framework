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

        coll_info = self._fetch_collection_info(collection, anomalies)
        spec.sections.append(("Collection state", self._section_collection(coll_info, anomalies)))

        probes: dict[str, Any] = {}
        if _QDRANT_AVAILABLE and coll_info.get("ok"):
            probes = self._run_quality_probes(collection, coll_info, anomalies)
            spec.sections.append(("Quality probes", self._section_probes(probes)))
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

        spec.anomalies = anomalies
        spec.summary = self._build_summary(run_end, coll_info, duration, anomalies)
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
                "anomalies": anomalies,
            }
        )
        return spec

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
        ends_sorted = sorted(ends, key=lambda x: x[1], reverse=True)
        lines = ["| Stage | Duration | OK | Err |", "|-------|---------:|:--:|-----|"]
        for name, dur, ok, err in ends_sorted:
            lines.append(f"| `{name}` | {dur:.2f}s | {'+' if ok else 'x'} | {err or ''} |")
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
        lines = []
        sample = probes.get("sample_size", 0)
        lines.append(f"- **sample_size:** `{sample}`")
        norm = probes.get("norm")
        if norm:
            lines.append(
                f"- **L2 norm:** mean=`{norm['mean']:.4f}`, std=`{norm['std']:.4f}`, "
                f"min=`{norm['min']:.4f}`, max=`{norm['max']:.4f}`"
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
            out["norm"] = {
                "mean": statistics.fmean(norms),
                "std": statistics.pstdev(norms) if len(norms) > 1 else 0.0,
                "min": min(norms),
                "max": max(norms),
            }
            out["zero_vectors"] = sum(1 for n in norms if n < 1e-9)

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
