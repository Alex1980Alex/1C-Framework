"""Cross-store sync — MIRRORS links + conflict resolution (§26 P3, D3.2+D3.3).

Consumes the D3.1 cross-store index (``content_hash`` groups spanning >=2 stores)
and, for each duplicated fact:

  - **D3.2** — picks a *canonical* store via
    :class:`ConflictResolver` with ``SOURCE_PRIORITY`` and records the resolution
    (audit). The same fact living in N stores is reconciled to one authoritative
    copy instead of N independent ones.
  - **D3.3** — emits ``MIRRORS`` edges (``mirror --MIRRORS--> canonical``) so the
    duplicate relationship is *persisted* in the link_registry (provenance),
    not re-derived per query. (``unified_search`` already collapses identical
    content at query time via ``Deduplicator``; ``MIRRORS`` adds the durable
    cross-store edge that survives between searches.)

This module is **pure and I/O-free**: it turns dup groups into a plan
(``MirrorLink`` rows + a conflict audit). The CLI
(``scripts/cross_store_sync.py``) feeds it D3.1 dups, applies the plan to the
link_registry (idempotent), and writes the audit report. Read-only by default
(dry-run); the links it creates are additive and reversible.

Roadmap: ``docs/roadmap/260602_ROADMAP_MEMORY_INGESTION_SYNC.md`` (§26 P3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from src.memory.infrastructure.conflict_resolver import ConflictResolver, ConflictStrategy
from src.memory.orchestrator.unified_id import SourceServer, UnifiedID

if TYPE_CHECKING:  # avoid a second runtime copy of the D3.1 module (records are duck-typed)
    from src.memory.orchestrator.cross_store_index import StoreRecord

# D3.1 store name -> unified-id SourceServer (the projection identity).
STORE_TO_SOURCE: dict[str, SourceServer] = {
    "learned_patterns": SourceServer.VECTOR_MEMORY,
    "memory_ai": SourceServer.MEMORY_AI,
    "skill_learning": SourceServer.SKILL_LEARNING,
    "wiki": SourceServer.OBSIDIAN_VAULT,
}

# Canonical priority, most-curated first. ConflictResolver SOURCE_PRIORITY uses
# this order to pick the authoritative copy of a duplicated fact; the rest mirror
# it. Rationale: wiki (L5, human-reviewed) > learned_patterns (semantic, gated) >
# skill_learning (captured) > memory_ai (raw episodic).
STORE_PRIORITY: list[str] = ["wiki", "learned_patterns", "skill_learning", "memory_ai"]


@dataclass(frozen=True)
class MirrorLink:
    """A ``MIRRORS`` edge: ``mirror`` mirrors the canonical copy.

    Direction matches ``LinkType.MIRRORS`` semantics ("source mirrors target"):
    ``mirror_uid --MIRRORS--> canonical_uid``.
    """

    mirror_uid: str
    canonical_uid: str
    content_hash: str


def unified_id_for(rec: StoreRecord) -> str | None:
    """Unified-id string for a store record, or ``None`` if unmappable.

    Returns ``None`` for an unknown store or an identifier with characters the
    unified-id grammar rejects (so the CLI can skip it rather than crash).
    """
    source = STORE_TO_SOURCE.get(rec.store)
    if source is None:
        return None
    try:
        return UnifiedID.from_original(source, str(rec.item_id)).unified
    except ValueError:
        return None


def make_resolver() -> ConflictResolver:
    """ConflictResolver wired for cross-store canonical selection (SOURCE_PRIORITY)."""
    return ConflictResolver(
        default_strategy=ConflictStrategy.SOURCE_PRIORITY,
        source_priorities=STORE_PRIORITY,
    )


def choose_canonical(
    records: list[StoreRecord],
    resolver: ConflictResolver | None = None,
) -> tuple[StoreRecord, str]:
    """Pick the canonical record of a dup group via ConflictResolver (D3.2).

    Pairwise-reduces the group so the resolver is the single arbiter; ties favour
    the incumbent (stable / deterministic). Returns ``(record, store)``.
    """
    resolver = resolver or make_resolver()
    canon = records[0]
    for rec in records[1:]:
        res = resolver.resolve(
            {"_source": canon.store, "store": canon.store},
            {"_source": rec.store, "store": rec.store},
            ConflictStrategy.SOURCE_PRIORITY,
        )
        winner_store = res.resolved_value.get("store") if res.resolved_value else canon.store
        if winner_store != canon.store:
            canon = rec
    return canon, canon.store


def build_sync_plan(
    dups: list[tuple[str, list[StoreRecord]]],
    resolver: ConflictResolver | None = None,
) -> dict[str, Any]:
    """Turn D3.1 cross-store dup groups into a MIRRORS plan + conflict audit.

    ``dups`` is the output of ``cross_store_index.find_cross_store_dups`` — groups
    of records sharing one ``content_hash`` across >=2 stores. For each group:
    choose a canonical (D3.2) and emit a ``MirrorLink`` from every other record to
    it (D3.3). Groups whose records can't yield >=2 distinct unified-ids are
    skipped (nothing to link).
    """
    resolver = resolver or make_resolver()
    links: list[MirrorLink] = []
    conflicts: list[dict[str, Any]] = []
    skipped: list[str] = []

    for content_hash, recs in dups:
        mapped = [(r, unified_id_for(r)) for r in recs]
        mapped = [(r, u) for r, u in mapped if u]
        if len({u for _, u in mapped}) < 2:
            skipped.append(content_hash)
            continue
        canon, canon_store = choose_canonical([r for r, _ in mapped], resolver)
        canon_uid = unified_id_for(canon)
        if canon_uid is None:
            # canon came from a uid-filtered set, so this is defensive; skip group.
            skipped.append(content_hash)
            continue
        for _rec, uid in mapped:
            if uid is None or uid == canon_uid:
                continue
            links.append(
                MirrorLink(mirror_uid=uid, canonical_uid=canon_uid, content_hash=content_hash)
            )
        conflicts.append(
            {
                "content_hash": content_hash,
                "stores": sorted({r.store for r, _ in mapped}),
                "canonical_store": canon_store,
                "canonical_uid": canon_uid,
                "strategy": ConflictStrategy.SOURCE_PRIORITY.value,
                "mirror_count": sum(1 for _, u in mapped if u != canon_uid),
            }
        )
    return {"links": links, "conflicts": conflicts, "skipped": skipped}


def _count_canonical(conflicts: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in conflicts:
        store = c["canonical_store"]
        out[store] = out.get(store, 0) + 1
    return out


def summarize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Aggregate counts for the report / metrics."""
    return {
        "mirror_links": len(plan["links"]),
        "conflict_groups": len(plan["conflicts"]),
        "skipped_groups": len(plan["skipped"]),
        "canonical_by_store": _count_canonical(plan["conflicts"]),
    }


def render_sync_report(
    plan: dict[str, Any],
    summary: dict[str, Any],
    stamp: str,
    applied: bool = False,
    store_errors: dict[str, str] | None = None,
    max_groups: int = 50,
) -> str:
    """Markdown report (matches the ``data/reports/memory`` house style)."""
    store_errors = store_errors or {}
    mode = "APPLIED" if applied else "dry-run (no links written)"
    lines: list[str] = []
    lines.append("# Cross-store sync — MIRRORS + conflict resolution (§26 P3 / D3.2+D3.3)")
    lines.append("")
    lines.append(f"> Generated: {stamp} · {mode}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- MIRRORS links: **{summary['mirror_links']}**")
    lines.append(
        f"- conflict groups (resolved via SOURCE_PRIORITY): **{summary['conflict_groups']}**"
    )
    lines.append(f"- skipped groups (unmappable): {summary['skipped_groups']}")
    canon = summary.get("canonical_by_store", {})
    if isinstance(canon, dict) and canon:
        lines.append("- canonical chosen by store:")
        for store in STORE_PRIORITY:
            if store in canon:
                lines.append(f"  - {store}: {canon[store]}")
    if store_errors:
        lines.append("")
        lines.append("## Skipped stores (fail-soft)")
        lines.append("")
        for store, err in store_errors.items():
            lines.append(f"- {store}: {err}")

    lines.append("")
    lines.append("## Conflict resolution audit")
    lines.append("")
    conflicts = plan["conflicts"]
    if not conflicts:
        lines.append("_None — no fact found in two or more stores._")
    else:
        for c in conflicts[:max_groups]:
            lines.append(
                f"- `{c['content_hash']}` — stores {c['stores']} → "
                f"canonical **{c['canonical_store']}** "
                f"({c['mirror_count']} mirror link(s), {c['strategy']})"
            )
        if len(conflicts) > max_groups:
            lines.append(f"_… and {len(conflicts) - max_groups} more (truncated)._")
    return "\n".join(lines) + "\n"


__all__ = [
    "STORE_PRIORITY",
    "STORE_TO_SOURCE",
    "MirrorLink",
    "build_sync_plan",
    "choose_canonical",
    "make_resolver",
    "render_sync_report",
    "summarize_plan",
    "unified_id_for",
]
