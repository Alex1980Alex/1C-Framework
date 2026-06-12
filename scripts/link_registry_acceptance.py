"""LinkRegistry acceptance-окно (roadmap 260612 LinkRegistry §P4, 14 дней с 2026-06-12).

Четвёртый потребитель ``acceptance_common`` (после skill_learning / memory-ai /
pdf-docs). Критерии:
- no_raw_ids — 0 рёбер с не-unified концами (P0.1)
- stats_sync — link_stats == пересчёт из entity_links (P0.2)
- history_complete — в link_history есть и create, и delete/update действия,
  неизвестных действий нет (P0.3: удаления журналируются)
- typology_clean — LinkType == 8 типов ADR-L1, рёбер с типами вне enum нет
- links_sink_registered — memory-links.log в known_sinks (P3.1)
- live_chains_green — BFS по мигрированному ребру отдаёт соседей (B1-инвариант)

Usage:
    python scripts/link_registry_acceptance.py [--json] [--final] [--no-report]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from acceptance_common import emit, render_acceptance, window_day

WINDOW_START = datetime(2026, 6, 12)
WINDOW_DAYS = 14
LINK_DB = PROJECT_ROOT / "data" / "link_registry.db"


def collect_metrics() -> dict[str, Any]:
    m: dict[str, Any] = {}
    conn = sqlite3.connect(LINK_DB)
    conn.row_factory = sqlite3.Row
    try:
        m["edges"] = conn.execute("SELECT COUNT(*) c FROM entity_links").fetchone()["c"]
        m["raw_id_edges"] = conn.execute(
            "SELECT COUNT(*) c FROM entity_links "
            "WHERE source_id NOT LIKE '%:%:%' OR target_id NOT LIKE '%:%:%'"
        ).fetchone()["c"]
        m["by_type"] = dict(
            conn.execute("SELECT link_type, COUNT(*) FROM entity_links GROUP BY link_type")
        )
        m["history_actions"] = dict(
            conn.execute("SELECT action, COUNT(*) FROM link_history GROUP BY action")
        )
        # stats_sync: фактические строки vs пересчёт
        mismatch = conn.execute(
            """
            SELECT COUNT(*) c FROM link_stats s
            WHERE s.outgoing_count != (SELECT COUNT(*) FROM entity_links WHERE source_id = s.entity_id)
               OR s.incoming_count != (SELECT COUNT(*) FROM entity_links WHERE target_id = s.entity_id)
            """
        ).fetchone()["c"]
        orphan = conn.execute(
            """
            SELECT COUNT(*) c FROM link_stats s
            WHERE NOT EXISTS (SELECT 1 FROM entity_links WHERE source_id = s.entity_id OR target_id = s.entity_id)
            """
        ).fetchone()["c"]
        m["stats_mismatch"] = mismatch
        m["stats_orphans"] = orphan
    finally:
        conn.close()

    from src.memory.infrastructure.event_envelope import CACHE_LOGS
    from src.memory.orchestrator.link_registry import LinkRegistry, LinkType

    m["link_types_count"] = len(LinkType)
    enum_values = {lt.value for lt in LinkType}
    m["edges_outside_enum"] = sum(
        c for t, c in m["by_type"].items() if t not in enum_values
    )
    m["links_sink_registered"] = "memory-links.log" in CACHE_LOGS

    # B1-инвариант: BFS по живому ребру (мигрированный semantic-конец)
    try:
        rel = LinkRegistry(db_path=str(LINK_DB)).get_related_entities(
            "semantic:vector-memory:0e74b837-6719-470b-9ef2-d6336d74e9a1", max_depth=1
        )
        m["bfs_neighbours"] = len(rel)
    except Exception:
        m["bfs_neighbours"] = -1
    return m


def evaluate(m: dict[str, Any]) -> dict[str, bool]:
    actions = set(m.get("history_actions", {}))
    return {
        "no_raw_ids": m.get("raw_id_edges", 1) == 0,
        "stats_sync": m.get("stats_mismatch", 1) == 0 and m.get("stats_orphans", 1) == 0,
        "history_complete": "create" in actions
        and ("delete" in actions or "update" in actions)
        and not (actions - {"create", "delete", "update"}),
        "typology_clean": m.get("link_types_count") == 8
        and m.get("edges_outside_enum", 1) == 0,
        "links_sink_registered": bool(m.get("links_sink_registered")),
        "live_chains_green": m.get("bfs_neighbours", 0) > 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="LinkRegistry acceptance (roadmap 260612 §P4)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--no-report", action="store_true")
    args = ap.parse_args()

    now = datetime.now()
    m = collect_metrics()
    crit = evaluate(m)
    day = window_day(now, WINDOW_START, WINDOW_DAYS)

    detail = [
        f"- edges: {m['edges']} · by_type: {m['by_type']}",
        f"- raw_id_edges: {m['raw_id_edges']} · stats_mismatch: {m['stats_mismatch']}"
        f" · stats_orphans: {m['stats_orphans']}",
        f"- history_actions: {m['history_actions']}",
        f"- LinkType: {m['link_types_count']} · вне enum: {m['edges_outside_enum']}",
        f"- bfs_neighbours(B1): {m['bfs_neighbours']}",
        f"- день окна: {day}/{WINDOW_DAYS}",
    ]
    report = render_acceptance(
        f"# LinkRegistry acceptance (roadmap 260612) — день {day}/{WINDOW_DAYS}",
        m,
        crit,
        final=args.final,
        detail_lines=detail,
        roadmap_rel="docs/roadmap/260612_ROADMAP_LINK_REGISTRY_FULL_VERIFICATION.md",
    )
    out = json.dumps({"metrics": m, "criteria": crit}, ensure_ascii=False) if args.json else report
    emit(out, report_name=None if args.no_report else "link_registry_acceptance")
    return 0 if all(crit.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
