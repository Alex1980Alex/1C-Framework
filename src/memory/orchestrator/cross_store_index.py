"""Cross-store ``content_hash`` index — pure core (§26 P3, D3.1).

Detects the same fact (identical ``content_hash``) living in **two or more**
memory stores — the divergence signal that drives P3 dedup/sync (D3.2 conflict
resolution, D3.3 ``MIRRORS``/``PROMOTED_TO`` links) and the
``cross_store_dup_rate`` metric (§26 §7).

The canonical join key is ``content_hash`` (= ``content_hash.hash_content`` —
the shared ``sha256(content)[:16]`` from §26 P0). This module is **store-agnostic
and I/O-free**: scanners (in ``scripts/cross_store_index.py``) feed it
``StoreRecord`` rows; the core builds the reverse index, classifies duplicates,
and renders a report. Read-only by design — nothing here writes or deletes.

Roadmap: ``docs/roadmap/260602_ROADMAP_MEMORY_INGESTION_SYNC.md`` (§26 P3, D3.1).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

# Stores managed as projections of a single ``MemoryCube`` fact. The ~12k
# ``docs/wiki/entities`` LightRAG pages are a *different* knowledge layer (not
# MemoryCube facts) and are intentionally out of scope for this dedup index.
KNOWN_STORES = ("learned_patterns", "memory_ai", "skill_learning", "wiki")


@dataclass(frozen=True)
class StoreRecord:
    """One item from one store, reduced to what cross-store dedup needs.

    ``preview`` is a short, human-facing excerpt for the report only — it never
    participates in matching (that is solely ``content_hash``).
    """

    store: str
    item_id: str
    content_hash: str
    preview: str = ""


def build_index(records: Iterable[StoreRecord]) -> dict[str, list[StoreRecord]]:
    """Reverse index ``content_hash -> [records]`` (skips empty hashes).

    Empty-content rows (no derivable hash) cannot be deduped and would collide
    on the empty-string hash, so they are dropped here rather than poison the
    index.
    """
    index: dict[str, list[StoreRecord]] = defaultdict(list)
    for rec in records:
        if rec.content_hash:
            index[rec.content_hash].append(rec)
    return dict(index)


def find_cross_store_dups(
    index: dict[str, list[StoreRecord]],
) -> list[tuple[str, list[StoreRecord]]]:
    """``content_hash`` groups spanning **>=2 distinct stores**.

    Sorted most-interesting-first: more stores, then more records, then hash
    (stable tie-break for deterministic reports/tests).
    """
    out: list[tuple[str, list[StoreRecord]]] = []
    for content_hash, recs in index.items():
        if len({r.store for r in recs}) >= 2:
            out.append((content_hash, recs))
    out.sort(key=lambda t: (-len({r.store for r in t[1]}), -len(t[1]), t[0]))
    return out


def summarize(
    records: list[StoreRecord],
    index: dict[str, list[StoreRecord]],
    dups: list[tuple[str, list[StoreRecord]]],
) -> dict[str, object]:
    """Aggregate metrics over the scan (feeds §26 §7 / the report)."""
    by_store: dict[str, int] = defaultdict(int)
    for rec in records:
        by_store[rec.store] += 1

    # intra-store dups: same hash repeated within one store (count-1 per store).
    intra = 0
    for recs in index.values():
        per_store: dict[str, int] = defaultdict(int)
        for rec in recs:
            per_store[rec.store] += 1
        intra += sum(c - 1 for c in per_store.values() if c > 1)

    unique_hashes = len(index)
    cross = len(dups)
    affected = sum(len(recs) for _, recs in dups)
    rate = (cross / unique_hashes) if unique_hashes else 0.0
    return {
        "total_records": len(records),
        "by_store": dict(by_store),
        "unique_hashes": unique_hashes,
        "intra_store_dups": intra,
        "cross_store_dup_count": cross,
        "cross_store_affected_records": affected,
        "cross_store_dup_rate": round(rate, 4),
    }


def render_report(
    summary: dict[str, object],
    dups: list[tuple[str, list[StoreRecord]]],
    stamp: str,
    store_errors: dict[str, str] | None = None,
    max_groups: int = 50,
) -> str:
    """Markdown report (matches the §25 ``data/reports/memory`` house style)."""
    store_errors = store_errors or {}
    lines: list[str] = []
    lines.append("# Cross-store content_hash index (§26 P3 / D3.1)")
    lines.append("")
    lines.append(f"> Generated: {stamp} · read-only (dry-run, no writes)")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- total records scanned: **{summary['total_records']}**")
    by_store = summary.get("by_store", {})
    if isinstance(by_store, dict):
        for store in KNOWN_STORES:
            if store in by_store:
                lines.append(f"  - {store}: {by_store[store]}")
    lines.append(f"- unique content hashes: **{summary['unique_hashes']}**")
    lines.append(f"- intra-store duplicates: {summary['intra_store_dups']}")
    lines.append(
        f"- **cross-store duplicate facts: {summary['cross_store_dup_count']}** "
        f"(affecting {summary['cross_store_affected_records']} records)"
    )
    lines.append(f"- cross_store_dup_rate: **{summary['cross_store_dup_rate']}**")
    if store_errors:
        lines.append("")
        lines.append("## Skipped stores (fail-soft)")
        lines.append("")
        for store, err in store_errors.items():
            lines.append(f"- {store}: {err}")

    lines.append("")
    lines.append("## Cross-store duplicates")
    lines.append("")
    if not dups:
        lines.append("_None — no fact found in two or more stores._")
    else:
        shown = dups[:max_groups]
        for content_hash, recs in shown:
            stores = sorted({r.store for r in recs})
            preview = next((r.preview for r in recs if r.preview), "")
            preview = preview.replace("\n", " ").strip()[:100]
            lines.append(f"### `{content_hash}` — {', '.join(stores)}")
            if preview:
                lines.append(f"> {preview}")
            for rec in recs:
                lines.append(f"- {rec.store}: `{rec.item_id}`")
            lines.append("")
        if len(dups) > max_groups:
            lines.append(f"_… and {len(dups) - max_groups} more groups (truncated)._")
    return "\n".join(lines) + "\n"


__all__ = [
    "KNOWN_STORES",
    "StoreRecord",
    "build_index",
    "find_cross_store_dups",
    "render_report",
    "summarize",
]
