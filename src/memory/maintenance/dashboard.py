"""Memory maintenance dashboard — pure aggregator (§26 P4, D4.3).

Combines per-job results + store sizes + ingestion metrics into a §25-style
report (``data/reports/memory``). I/O-free: the CLI reads the sources and feeds
dicts in. Surfaces the §26 §7 metrics: ingest/dup rates, cross_store_dup_rate,
store_sizes (bounded-growth), and the ForgetGate summary.

Roadmap: ``docs/roadmap/260602_ROADMAP_MEMORY_INGESTION_SYNC.md`` (§26 P4, D4.3).
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any


def aggregate_ingest_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate ``.claude/cache/memory-ingestion.log`` events.

    Counts ingest actions (saved/dup/skipped/error) → attempted + dup_rate and
    surfaces the most-recent logged ``store_size`` per store.
    """
    actions: Counter[str] = Counter()
    logged_sizes: dict[str, Any] = {}
    for e in events:
        ev = e.get("event")
        if ev == "ingest":
            actions[str(e.get("action", "?"))] += 1
        elif ev == "store_size":
            store = e.get("store")
            if store is not None:
                logged_sizes[str(store)] = e.get("size")
    attempted = sum(actions.values())
    dup = actions.get("dup", 0)
    return {
        "actions": dict(actions),
        "attempted": attempted,
        "saved": actions.get("saved", 0),
        "dup_rate": round(dup / attempted, 4) if attempted else 0.0,
        "logged_store_sizes": logged_sizes,
    }


def compute_docs_freshness(
    last_run_end: dict[str, str | None],
    points: dict[str, Any],
    *,
    now: datetime,
    max_age_days: int = 30,
) -> dict[str, Any]:
    """Staleness-метрика docs-индексов (roadmap 260612 P3.2, pure).

    Args:
        last_run_end: collection -> ISO-timestamp последнего ``run_end`` из
            ``data/indexing-progress.jsonl`` (None = run_end отсутствует вовсе).
        points: collection -> points_count (None = Qdrant недоступен).
        now: момент оценки (aware, если timestamps с offset'ом).
        max_age_days: порог алерта (default 30).

    Returns:
        collection -> {points, last_run_end, age_days, stale}. Отсутствие
        run_end = stale (дрейф невидим, что и есть алерт-условие D5).
    """
    out: dict[str, Any] = {}
    for coll, ts in last_run_end.items():
        age_days: float | None = None
        stale = True
        if ts:
            try:
                dt = datetime.fromisoformat(ts)
                ref = now if dt.tzinfo is None else now.astimezone()
                if dt.tzinfo is None and ref.tzinfo is not None:
                    ref = ref.replace(tzinfo=None)
                age_days = round((ref - dt).total_seconds() / 86400.0, 1)
                stale = age_days > max_age_days
            except (ValueError, TypeError):
                pass
        out[coll] = {
            "points": points.get(coll),
            "last_run_end": ts,
            "age_days": age_days,
            "stale": stale,
        }
    return out


def build_dashboard(
    *,
    store_sizes: dict[str, Any],
    cross_store: dict[str, Any] | None = None,
    link_stats: dict[str, Any] | None = None,
    ingest: dict[str, Any] | None = None,
    forget: dict[str, Any] | None = None,
    jobs: dict[str, Any] | None = None,
    docs_freshness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the maintenance dashboard payload (pure)."""
    total = sum(v for v in store_sizes.values() if isinstance(v, (int, float)))
    return {
        "store_sizes": store_sizes,
        "total_facts": total,
        "cross_store": cross_store or {},
        "link_stats": link_stats or {},
        "ingest": ingest or {},
        "forget": forget or {},
        "jobs": jobs or {},
        "docs_freshness": docs_freshness or {},
    }


def render_dashboard(dash: dict[str, Any], stamp: str) -> str:
    """Markdown dashboard (matches the ``data/reports/memory`` house style)."""
    lines: list[str] = []
    lines.append("# Memory maintenance dashboard (§26 P4 / D4.3)")
    lines.append("")
    lines.append(f"> Generated: {stamp}")
    lines.append("")
    lines.append("## Store sizes (bounded-growth)")
    lines.append("")
    for store, size in dash.get("store_sizes", {}).items():
        lines.append(f"- {store}: {size}")
    lines.append(f"- **total facts: {dash.get('total_facts', 0)}**")

    df = dash.get("docs_freshness") or {}
    if df:
        lines.append("")
        lines.append("## Docs freshness (260612 P3.2)")
        lines.append("")
        for coll, st in df.items():
            age = st.get("age_days")
            age_s = f"{age}d" if age is not None else "no run_end in progress-log"
            mark = " ⚠ STALE" if st.get("stale") else ""
            lines.append(f"- {coll}: {st.get('points')} pts · last index {age_s}{mark}")

    cs = dash.get("cross_store") or {}
    if cs:
        lines.append("")
        lines.append("## Cross-store")
        lines.append(f"- cross_store_dup_rate: {cs.get('cross_store_dup_rate', 'n/a')}")
        lines.append(f"- cross-store dup groups: {cs.get('cross_store_dup_count', 'n/a')}")

    ing = dash.get("ingest") or {}
    if ing:
        lines.append("")
        lines.append("## Ingestion")
        lines.append(
            f"- attempted: {ing.get('attempted', 0)} · saved: {ing.get('saved', 0)} · "
            f"dup_rate: {ing.get('dup_rate', 0.0)}"
        )
        if ing.get("actions"):
            lines.append(f"- actions: {ing['actions']}")

    fg = dash.get("forget") or {}
    if fg:
        lines.append("")
        lines.append("## ForgetGate (bound)")
        lines.append(
            f"- archive: {fg.get('archive', 0)} · keep: {fg.get('keep', 0)} · "
            f"already_archived: {fg.get('already_archived', 0)} · "
            f"invariant_protected: {fg.get('invariant_protected', 0)}"
        )

    ls = dash.get("link_stats") or {}
    if ls:
        lines.append("")
        lines.append("## Links")
        lines.append(
            f"- total_links: {ls.get('total_links', 0)} · by_type: {ls.get('by_type', {})}"
        )

    jobs = dash.get("jobs") or {}
    if jobs:
        lines.append("")
        lines.append("## Jobs (this run)")
        for name, res in jobs.items():
            lines.append(f"- {name}: {res}")

    return "\n".join(lines) + "\n"


__all__ = ["aggregate_ingest_events", "build_dashboard", "render_dashboard"]
