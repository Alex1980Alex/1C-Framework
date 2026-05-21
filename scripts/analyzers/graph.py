"""Graph-build run analyzer.

Three independent sub-sources (selected via ``--source`` CLI flag):

  * ``sqlite``       — ``cache/bsl_call_graph.db`` (output of
                       ``scripts/build_call_graph.py``). Tables: ``symbols``,
                       ``calls``, ``module_metadata``. Source-of-truth for
                       BSL call graph; lightweight (no extra deps beyond
                       stdlib).
  * ``neo4j``        — bolt://localhost:7687, labels: Module / Symbol /
                       Object (loaded by ``scripts/load_graph_to_neo4j.py``).
                       Requires ``neo4j`` package; degraded section if
                       unavailable.
  * ``qdrant_graph`` — Qdrant ``graph_embeddings`` collection (vector view).
                       Payload-aware: distinguishes entity vs relation
                       points, per-type counts.

All three emit a ReportSpec with the same shape (TL;DR + sections +
anomalies + diff vs previous). Different sub-sources are mutually
exclusive within one run.
"""
from __future__ import annotations

import json
import math
import os
import sqlite3
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from .base import AnalyzerBase, ReportSpec

try:
    from qdrant_client import QdrantClient
    _QDRANT_AVAILABLE = True
except ImportError:
    _QDRANT_AVAILABLE = False

try:
    from neo4j import GraphDatabase
    _NEO4J_AVAILABLE = True
except ImportError:
    _NEO4J_AVAILABLE = False


TAIL_BYTES = 4 * 1024 * 1024
DEFAULT_NEO4J_URI = "bolt://localhost:7687"
DEFAULT_NEO4J_AUTH = ("neo4j", "bsl-graph-2026")


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


def _find_previous_report(reports_dir: Path, subject: str, current_run_id: str) -> dict[str, Any] | None:
    graph_dir = reports_dir / "graph"
    if not graph_dir.exists():
        return None
    candidates = sorted(graph_dir.glob("*.json"), reverse=True)
    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("subject") == subject and data.get("run_id") != current_run_id:
            return data
    return None


class GraphAnalyzer(AnalyzerBase):
    def __init__(
        self,
        source: str,
        run_id: str | None,
        progress_jsonl: Path,
        reports_dir: Path,
        db_path: Path | None = None,
        neo4j_uri: str = DEFAULT_NEO4J_URI,
        neo4j_user: str = DEFAULT_NEO4J_AUTH[0],
        neo4j_password: str = DEFAULT_NEO4J_AUTH[1],
        qdrant_url: str | None = None,
        qdrant_collection: str = "graph_embeddings",
        verbosity: str = "medium",
        sample_size: int = 200,
    ) -> None:
        if source not in ("sqlite", "neo4j", "qdrant_graph"):
            raise ValueError(f"Unsupported graph source: {source!r}")
        self.source = source
        self.run_id = run_id or f"manual-graph-{source}-{int(datetime.now().timestamp())}"
        self.progress_jsonl = progress_jsonl
        self.reports_dir = reports_dir
        self.db_path = db_path
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.qdrant_url = qdrant_url or os.environ.get("QDRANT_URL", "http://localhost:6333")
        self.qdrant_collection = qdrant_collection
        self.verbosity = verbosity
        self.sample_size = sample_size

    def analyze(self) -> ReportSpec:
        events = _load_run_events(self.progress_jsonl, self.run_id) if self.run_id else []
        run_start = next((e for e in events if e.get("category") == "run_start"), None)
        run_end = next((e for e in reversed(events) if e.get("category") == "run_end"), None)
        script = (events[0].get("script") if events else f"manual:{self.source}")
        duration = (run_end or {}).get("elapsed_s")

        subject = self._subject_for_source()
        anomalies: list[str] = []

        spec = ReportSpec(
            mode="graph",
            subject=subject,
            run_id=self.run_id,
            generated_at=datetime.now().isoformat(timespec="seconds"),
            indexer_script=str(script or self.source),
            duration_sec=float(duration) if duration is not None else None,
        )

        if events:
            spec.sections.append(("Run identity (from progress JSONL)", self._section_run(events, run_start, run_end, anomalies)))

        if self.source == "sqlite":
            self._analyze_sqlite(spec, anomalies)
        elif self.source == "neo4j":
            self._analyze_neo4j(spec, anomalies)
        elif self.source == "qdrant_graph":
            self._analyze_qdrant_graph(spec, anomalies)

        prev = _find_previous_report(self.reports_dir, subject, self.run_id)
        if prev:
            spec.sections.append(("Diff vs previous run", self._section_diff(prev, spec.raw, anomalies)))
        else:
            spec.sections.append(("Diff vs previous run", f"_Нет предыдущего отчёта для `{subject}` — это первый ран._"))

        spec.anomalies = anomalies
        spec.summary = self._build_summary(spec.raw, anomalies)
        spec.raw.setdefault("source", self.source)
        spec.raw.setdefault("subject", subject)
        spec.raw.setdefault("run_id", self.run_id)
        return spec

    # ---- subject naming -----------------------------------------------

    def _subject_for_source(self) -> str:
        if self.source == "sqlite":
            return (self.db_path or Path("bsl_call_graph.db")).stem
        if self.source == "neo4j":
            return "neo4j_call_graph"
        return self.qdrant_collection

    # ---- common run section -------------------------------------------

    def _section_run(self, events: list[dict], run_start: dict | None, run_end: dict | None, anomalies: list[str]) -> str:
        lines = []
        pid = (run_start or {}).get("pid", "?")
        lines.append(f"- **PID:** `{pid}`")
        if run_end:
            for k, v in run_end.items():
                if k in ("ts", "run_id", "script", "category", "elapsed_s"):
                    continue
                lines.append(f"- **run_end.{k}:** `{v}`")
            errors = run_end.get("errors")
            if isinstance(errors, (int, float)) and errors > 0:
                anomalies.append(f"`run_end.errors={errors}` — parse errors в pipeline.")
        else:
            anomalies.append("Нет `run_end` события — build_call_graph мог упасть до atexit.")
        return "\n".join(lines) or "_(пусто)_"

    # ---- SQLite source ------------------------------------------------

    def _analyze_sqlite(self, spec: ReportSpec, anomalies: list[str]) -> None:
        db_path = self.db_path
        if not db_path or not db_path.exists():
            spec.sections.append(
                ("SQLite call graph", f"_DB not found: {db_path}_")
            )
            anomalies.append(f"SQLite DB не найден: {db_path}")
            return
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
        except sqlite3.Error as exc:
            spec.sections.append(("SQLite call graph", f"_Ошибка открытия БД: {exc}_"))
            anomalies.append(f"SQLite open error: {exc}")
            return

        try:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            counts: dict[str, int] = {}
            for t in ("modules", "module_metadata", "symbols", "calls"):
                if t in tables:
                    counts[t] = int(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])

            lines = ["| Table | Rows |", "|-------|-----:|"]
            for t, n in counts.items():
                lines.append(f"| `{t}` | {n:,} |")
            spec.sections.append(("SQLite tables", "\n".join(lines)))

            symbols_by_type = self._sqlite_symbols_by_type(conn, tables)
            spec.sections.append(("Symbols by symbol_type", self._render_distribution(symbols_by_type)))

            top_callers = self._sqlite_top_callees(conn, tables, limit=15)
            spec.sections.append(("Top-15 symbols by incoming call count (callees)", self._render_top(top_callers)))

            module_density = self._sqlite_module_density(conn, tables, limit=15)
            spec.sections.append(("Top-15 modules by symbol count", self._render_top(module_density)))

            orphan_count, dangling = self._sqlite_orphans_and_dangling(conn, tables, anomalies)
            sec = [
                f"- **modules с 0 symbols:** {orphan_count}",
                f"- **calls с broken endpoints:** {dangling}",
            ]
            spec.sections.append(("Schema integrity", "\n".join(sec)))

            spec.raw.update(
                {
                    "tables": counts,
                    "symbols_by_type": symbols_by_type,
                    "top_callees": top_callers,
                    "top_modules": module_density,
                    "orphan_modules": orphan_count,
                    "dangling_calls": dangling,
                }
            )
        except sqlite3.Error as exc:
            spec.sections.append(("SQLite call graph", f"_SQL error: {exc}_"))
            anomalies.append(f"SQLite query error: {exc}")
        finally:
            conn.close()

    def _sqlite_symbols_by_type(self, conn: sqlite3.Connection, tables: set[str]) -> dict[str, int]:
        if "symbols" not in tables:
            return {}
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(symbols)")}
        except sqlite3.Error:
            return {}
        col = "symbol_type" if "symbol_type" in cols else ("kind" if "kind" in cols else None)
        if not col:
            return {}
        rows = conn.execute(
            f"SELECT {col} AS k, COUNT(*) AS n FROM symbols GROUP BY {col} ORDER BY n DESC"
        ).fetchall()
        return {(r["k"] or "<null>"): int(r["n"]) for r in rows}

    def _sqlite_top_callees(self, conn: sqlite3.Connection, tables: set[str], limit: int) -> list[tuple[str, int]]:
        if "calls" not in tables:
            return []
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(calls)")}
        except sqlite3.Error:
            return []
        col = None
        for c in ("callee_name", "callee", "target_name", "target"):
            if c in cols:
                col = c
                break
        if not col:
            return []
        rows = conn.execute(
            f"SELECT {col} AS name, COUNT(*) AS n FROM calls WHERE {col} IS NOT NULL "
            f"GROUP BY {col} ORDER BY n DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [(r["name"], int(r["n"])) for r in rows]

    def _sqlite_module_density(self, conn: sqlite3.Connection, tables: set[str], limit: int) -> list[tuple[str, int]]:
        if "symbols" not in tables:
            return []
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(symbols)")}
        except sqlite3.Error:
            return []
        col = "module_path" if "module_path" in cols else ("module" if "module" in cols else None)
        if not col:
            return []
        rows = conn.execute(
            f"SELECT {col} AS m, COUNT(*) AS n FROM symbols GROUP BY {col} ORDER BY n DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [(r["m"], int(r["n"])) for r in rows]

    def _sqlite_orphans_and_dangling(
        self, conn: sqlite3.Connection, tables: set[str], anomalies: list[str]
    ) -> tuple[int, int]:
        orphan = 0
        dangling = 0
        if "module_metadata" in tables and "symbols" in tables:
            try:
                cols = {r[1] for r in conn.execute("PRAGMA table_info(symbols)")}
                sym_mod_col = "module_path" if "module_path" in cols else "module"
                orphan = int(
                    conn.execute(
                        f"SELECT COUNT(*) FROM module_metadata m "
                        f"WHERE NOT EXISTS (SELECT 1 FROM symbols s WHERE s.{sym_mod_col} = m.path)"
                    ).fetchone()[0]
                )
            except sqlite3.Error:
                pass
        if "calls" in tables and "symbols" in tables:
            try:
                cols_c = {r[1] for r in conn.execute("PRAGMA table_info(calls)")}
                cols_s = {r[1] for r in conn.execute("PRAGMA table_info(symbols)")}
                callee_col = next((c for c in ("callee_name", "callee", "target_name", "target") if c in cols_c), None)
                sym_name = "name" if "name" in cols_s else None
                if callee_col and sym_name:
                    dangling = int(
                        conn.execute(
                            f"SELECT COUNT(*) FROM calls c "
                            f"WHERE c.{callee_col} IS NOT NULL "
                            f"AND NOT EXISTS (SELECT 1 FROM symbols s WHERE s.{sym_name} = c.{callee_col})"
                        ).fetchone()[0]
                    )
            except sqlite3.Error:
                pass
        if dangling > 0:
            anomalies.append(f"{dangling:,} calls без matching symbol — dangling endpoints (внешние API или typo).")
        return orphan, dangling

    # ---- Neo4j source -------------------------------------------------

    def _analyze_neo4j(self, spec: ReportSpec, anomalies: list[str]) -> None:
        if not _NEO4J_AVAILABLE:
            spec.sections.append(("Neo4j graph", "_Skipped — пакет `neo4j` не установлен._"))
            return
        try:
            driver = GraphDatabase.driver(self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password))
            driver.verify_connectivity()
        except Exception as exc:
            spec.sections.append(("Neo4j graph", f"_Connectivity failed: {type(exc).__name__}: {exc}_"))
            anomalies.append(f"Neo4j connect error: {exc}")
            return

        node_counts: dict[str, int] = {}
        rel_counts: dict[str, int] = {}
        top_nodes: list[tuple[str, int]] = []
        orphan_count = 0

        try:
            with driver.session() as session:
                labels = session.run("CALL db.labels() YIELD label RETURN label").value()
                for lab in labels:
                    n = session.run(f"MATCH (n:`{lab}`) RETURN count(n) AS c").single()["c"]
                    node_counts[lab] = int(n)

                rel_types = session.run("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType").value()
                for rt in rel_types:
                    n = session.run(f"MATCH ()-[r:`{rt}`]->() RETURN count(r) AS c").single()["c"]
                    rel_counts[rt] = int(n)

                top_q = (
                    "MATCH (n) WITH n, size([(n)--() | 1]) AS deg "
                    "ORDER BY deg DESC LIMIT 15 "
                    "RETURN coalesce(n.name, n.path, toString(id(n))) AS label, deg"
                )
                top_nodes = [(r["label"], int(r["deg"])) for r in session.run(top_q)]

                orphan = session.run("MATCH (n) WHERE NOT (n)--() RETURN count(n) AS c").single()["c"]
                orphan_count = int(orphan)
        except Exception as exc:
            spec.sections.append(("Neo4j graph", f"_Cypher error: {exc}_"))
            anomalies.append(f"Neo4j query error: {exc}")
            driver.close()
            return
        finally:
            try:
                driver.close()
            except Exception:
                pass

        total_nodes = sum(node_counts.values())
        total_rels = sum(rel_counts.values())
        density = (total_rels / total_nodes) if total_nodes else 0.0

        spec.sections.append(
            (
                "Neo4j overview",
                "\n".join(
                    [
                        f"- **uri:** `{self.neo4j_uri}`",
                        f"- **total nodes:** `{total_nodes:,}`",
                        f"- **total relationships:** `{total_rels:,}`",
                        f"- **edges/node ratio:** `{density:.2f}`",
                        f"- **orphan nodes (degree=0):** `{orphan_count:,}`",
                    ]
                ),
            )
        )
        spec.sections.append(("Nodes by label", self._render_distribution(node_counts)))
        spec.sections.append(("Relationships by type", self._render_distribution(rel_counts)))
        spec.sections.append(("Top-15 nodes by degree", self._render_top(top_nodes)))

        if orphan_count > 0:
            anomalies.append(f"{orphan_count:,} orphan nodes — изолированные модули/символы.")

        spec.raw.update(
            {
                "neo4j_node_counts": node_counts,
                "neo4j_rel_counts": rel_counts,
                "neo4j_top_nodes": top_nodes,
                "neo4j_orphan_count": orphan_count,
                "neo4j_total_nodes": total_nodes,
                "neo4j_total_rels": total_rels,
            }
        )

    # ---- Qdrant graph source ------------------------------------------

    def _analyze_qdrant_graph(self, spec: ReportSpec, anomalies: list[str]) -> None:
        if not _QDRANT_AVAILABLE:
            spec.sections.append(("Qdrant graph_embeddings", "_Skipped — qdrant_client не установлен._"))
            return
        try:
            client = QdrantClient(url=self.qdrant_url, timeout=30)
            physical = self._resolve_alias(client, self.qdrant_collection)
            info = client.get_collection(physical)
        except Exception as exc:
            spec.sections.append(("Qdrant graph_embeddings", f"_Connectivity failed: {type(exc).__name__}: {exc}_"))
            anomalies.append(f"Qdrant connect error: {exc}")
            return

        params = info.config.params if info.config else None
        vectors_cfg = params.vectors if params else None
        dim = getattr(vectors_cfg, "size", None) if vectors_cfg else None

        spec.sections.append(
            (
                "Qdrant collection state",
                "\n".join(
                    [
                        f"- **collection:** `{self.qdrant_collection}` (physical: `{physical}`)",
                        f"- **points_count:** `{info.points_count}`",
                        f"- **dimension:** `{dim}`",
                        f"- **status:** `{info.status}`",
                    ]
                ),
            )
        )

        sample_n = min(self.sample_size, int(info.points_count or 0)) or self.sample_size
        try:
            scroll = client.scroll(
                collection_name=physical,
                limit=sample_n,
                with_payload=True,
                with_vectors=True,
            )
            points = scroll[0] if isinstance(scroll, tuple) else getattr(scroll, "points", [])
        except Exception as exc:
            anomalies.append(f"Qdrant scroll error: {exc}")
            spec.raw.update({"qdrant_points_count": info.points_count, "qdrant_dimension": dim})
            return

        entity_types: Counter[str] = Counter()
        sources: Counter[str] = Counter()
        kinds: Counter[str] = Counter()
        norms: list[float] = []
        for p in points:
            payload = getattr(p, "payload", None) or {}
            etype = payload.get("entity_type") or payload.get("type") or "<unknown>"
            entity_types[etype] += 1
            src = payload.get("source") or payload.get("source_doc") or "<unknown>"
            sources[src] += 1
            kind = payload.get("kind") or ("relation" if payload.get("relation_type") else "entity")
            kinds[kind] += 1
            v = getattr(p, "vector", None)
            if isinstance(v, dict):
                v = next(iter(v.values()), None)
            if isinstance(v, list):
                norms.append(math.sqrt(sum(x * x for x in v)))

        spec.sections.append(("Entity types (sample)", self._render_distribution(dict(entity_types.most_common(20)))))
        spec.sections.append(("Entity vs relation split (sample)", self._render_distribution(dict(kinds))))
        spec.sections.append(("Top sources (sample)", self._render_distribution(dict(sources.most_common(15)))))

        norm_summary: dict[str, float] = {}
        if norms:
            norm_summary = {
                "mean": statistics.fmean(norms),
                "std": statistics.pstdev(norms) if len(norms) > 1 else 0.0,
                "min": min(norms),
                "max": max(norms),
            }
            spec.sections.append(
                (
                    "Vector L2 norms",
                    f"- **sample:** {len(norms)}\n"
                    f"- **mean:** `{norm_summary['mean']:.4f}`, std=`{norm_summary['std']:.4f}`, "
                    f"min=`{norm_summary['min']:.4f}`, max=`{norm_summary['max']:.4f}`",
                )
            )

        spec.raw.update(
            {
                "qdrant_collection": self.qdrant_collection,
                "qdrant_physical": physical,
                "qdrant_points_count": info.points_count,
                "qdrant_dimension": dim,
                "qdrant_entity_types": dict(entity_types),
                "qdrant_kinds": dict(kinds),
                "qdrant_sources": dict(sources.most_common(50)),
                "qdrant_norm": norm_summary,
                "qdrant_sample_size": len(points),
            }
        )

    def _resolve_alias(self, client, collection: str) -> str:
        try:
            for alias in client.get_aliases().aliases:
                if alias.alias_name == collection:
                    return alias.collection_name
        except Exception:
            pass
        return collection

    # ---- diff / summary -----------------------------------------------

    def _section_diff(self, prev: dict, cur: dict, anomalies: list[str]) -> str:
        lines: list[str] = []
        # SQLite diff
        if "tables" in cur and "tables" in prev:
            for key in ("modules", "module_metadata", "symbols", "calls"):
                prev_v = (prev.get("tables") or {}).get(key)
                cur_v = (cur.get("tables") or {}).get(key)
                if isinstance(prev_v, int) and isinstance(cur_v, int):
                    d = cur_v - prev_v
                    pct = (d / prev_v * 100) if prev_v else float("inf")
                    lines.append(f"- **{key}:** `{prev_v:,}` -> `{cur_v:,}` (Δ {d:+,}, {pct:+.1f}%)")
        # Neo4j diff
        if "neo4j_total_nodes" in cur and "neo4j_total_nodes" in prev:
            for key in ("neo4j_total_nodes", "neo4j_total_rels", "neo4j_orphan_count"):
                prev_v = prev.get(key)
                cur_v = cur.get(key)
                if isinstance(prev_v, int) and isinstance(cur_v, int):
                    d = cur_v - prev_v
                    lines.append(f"- **{key}:** `{prev_v:,}` -> `{cur_v:,}` (Δ {d:+,})")
        # Qdrant graph diff
        if "qdrant_points_count" in cur and "qdrant_points_count" in prev:
            for key in ("qdrant_points_count", "qdrant_dimension"):
                prev_v = prev.get(key)
                cur_v = cur.get(key)
                if isinstance(prev_v, int) and isinstance(cur_v, int):
                    d = cur_v - prev_v
                    lines.append(f"- **{key}:** `{prev_v:,}` -> `{cur_v:,}` (Δ {d:+,})")
            prev_norm = (prev.get("qdrant_norm") or {}).get("mean")
            cur_norm = (cur.get("qdrant_norm") or {}).get("mean")
            if prev_norm and cur_norm:
                drift = abs(cur_norm - prev_norm) / prev_norm
                lines.append(f"- **L2 norm drift:** `{drift:.2%}`")
                if drift > 0.25:
                    anomalies.append(f"L2 norm изменился на {drift:.0%} — возможный model swap.")
        return "\n".join(lines) or "_Нет сопоставимых метрик._"

    def _build_summary(self, raw: dict, anomalies: list[str]) -> dict[str, Any]:
        s: dict[str, Any] = {"source": self.source}
        if self.source == "sqlite":
            t = raw.get("tables") or {}
            for k in ("modules", "module_metadata", "symbols", "calls"):
                if k in t:
                    s[k] = t[k]
            if "orphan_modules" in raw:
                s["orphan_modules"] = raw["orphan_modules"]
            if "dangling_calls" in raw:
                s["dangling_calls"] = raw["dangling_calls"]
        elif self.source == "neo4j":
            s["total_nodes"] = raw.get("neo4j_total_nodes")
            s["total_rels"] = raw.get("neo4j_total_rels")
            s["orphan_nodes"] = raw.get("neo4j_orphan_count")
        elif self.source == "qdrant_graph":
            s["points"] = raw.get("qdrant_points_count")
            s["dimension"] = raw.get("qdrant_dimension")
            s["sample_size"] = raw.get("qdrant_sample_size")
        s["anomalies"] = len(anomalies)
        return s

    # ---- shared renderers ---------------------------------------------

    def _render_distribution(self, dist: dict[str, int]) -> str:
        if not dist:
            return "_(пусто)_"
        total = sum(dist.values()) or 1
        lines = ["| Key | Count | % |", "|-----|------:|--:|"]
        for k, v in sorted(dist.items(), key=lambda kv: kv[1], reverse=True):
            pct = v / total * 100
            lines.append(f"| `{k}` | {v:,} | {pct:.1f}% |")
        return "\n".join(lines)

    def _render_top(self, items: list[tuple[str, int]]) -> str:
        if not items:
            return "_(пусто)_"
        lines = ["| Name | Count |", "|------|------:|"]
        for name, n in items:
            lines.append(f"| `{name}` | {n:,} |")
        return "\n".join(lines)
