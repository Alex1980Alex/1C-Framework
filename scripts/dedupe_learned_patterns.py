#!/usr/bin/env python3
"""Dedupe + cleanup the `learned_patterns` Qdrant collection.

The collection accumulated exact-content duplicates (e.g. ``calculate_rrf_score``
x4 with distinct point IDs but identical content) plus a couple of test records.
This collapses each group of byte-identical content to a single survivor and
optionally drops known test markers, so the collection is fit for real learning.

SAFETY (this is a destructive, irreversible Qdrant mutation):
  - **dry-run by default** — prints the plan; ``--apply`` is required to mutate.
  - **backup first** — before any delete, every point (id + payload + vector) is
    exported to ``data/memory/backups/learned_patterns_<ts>.json``. Restore with
    ``--restore <file> --apply`` (re-upserts the snapshot). ``--no-backup`` opts out.
  - **conservative** — survivor per content group = the richest schema
    (``pattern_id``) with the earliest ``created_at``, else the earliest overall;
    succ/fail/application_count are SUMMED into the survivor (no learning lost) and
    its ``confidence`` denorm is recomputed from the merged counts (§22 Beta(7,3)).
  - test removal is **opt-in** (``--drop-test``) and matches an explicit exact-content
    allowlist only — never broad heuristics.
  - **link-aware** (roadmap 260716 P1.7) — see below.

LINK AWARENESS (was: "KNOWN UNSAFE, do not --apply", found 2026-07-16, fixed 2026-07-17)
This planner used to be blind to ``data/link_registry.db`` and would have:
  1. DELETED points other entities link to — live check on the 3 duplicate groups: all
     3 delete-candidates carried edges (``derives_from`` to their episodic sources,
     ``mirrors`` from their duplicates) → 10 dangling edges;
  2. CONTRADICTED cross_store_sync's canonical choice — ``mirrors`` points
     mirror→canonical, so ``mirrors: A -> B`` means B is canonical, yet
     ``pick_survivor`` (richest schema, earliest created_at) picked A and would have
     deleted B. Two subsystems, two different survivors (2 of the 3 live groups).
Now: an intra-group ``mirrors`` designation WINS over the heuristic, and the losers'
edges are RE-POINTED onto the survivor (the fact lives on under one id) — never merely
deleted, which would have dropped provenance. Edges whose referent disappears (the
duplicate relation itself) are dropped; duplicates of an edge the survivor already has
collapse. The plan is refused outright if the registry cannot be read, or if any edge
would still be left dangling.

Usage:
  python scripts/dedupe_learned_patterns.py                 # dry-run plan
  python scripts/dedupe_learned_patterns.py --drop-test     # include test records in plan
  python scripts/dedupe_learned_patterns.py --apply --drop-test
  python scripts/dedupe_learned_patterns.py --restore data/memory/backups/learned_patterns_<ts>.json --apply
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COLLECTION = "learned_patterns"
BACKUP_DIR = PROJECT_ROOT / "data" / "memory" / "backups"

# Exact full-content test records to drop with --drop-test (allowlist, not heuristic).
TEST_MARKERS = frozenset(
    {
        "Testing vector-memory save after dimension fix",
        "Entity lookup test content",
    }
)


def _content(payload: dict[str, Any]) -> str:
    return payload.get("content") or payload.get("description") or ""


def content_key(payload: dict[str, Any]) -> str:
    """Cross-store dedup key — delegates to the canonical implementation (§26 P0).

    Falls back to the inline sha256[:16] if ``src`` is not importable, keeping the
    script self-contained. Both paths are byte-identical by construction.
    """
    try:
        src = str(PROJECT_ROOT / "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from memory.orchestrator.content_hash import content_key as _ck

        return _ck(payload)
    except Exception:
        return hashlib.sha256(_content(payload).encode("utf-8", errors="replace")).hexdigest()[:16]


def _num(payload: dict[str, Any], key: str) -> float:
    v = payload.get(key)
    return float(v) if isinstance(v, (int, float)) else 0.0


def derive_confidence(succ: float, fail: float) -> float:
    """§22 Beta(7,3) posterior mean; falls back to the inline formula on import error."""
    try:
        src = str(PROJECT_ROOT / "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from memory.vector_memory.confidence import derive_confidence as _dc

        return float(_dc(succ, fail))
    except Exception:
        return (7.0 + succ) / (10.0 + succ + fail)


# --------------------------------------------------------------------- links
SEMANTIC_PREFIX = "semantic:vector-memory:"
MIRRORS = "mirrors"


def uid(point_id: str) -> str:
    """Unified-ID form that link_registry uses for a learned_patterns point."""
    return f"{SEMANTIC_PREFIX}{point_id}"


def canonical_from_links(group_ids: set[str], links: list[dict[str, Any]]) -> str | None:
    """Point already designated canonical by a MIRRORS edge inside the group, if any.

    ``cross_store_sync`` writes ``mirror --MIRRORS--> canonical`` (§26 P3), so a member
    that is the TARGET of an intra-group mirrors edge and never the SOURCE of one is the
    canonical copy. That designation is durable and shared with the rest of the system —
    it outranks this script's local heuristic, which knows nothing about it. Live check
    2026-07-17: 2 of the 3 duplicate groups had a canonical that `pick_survivor`
    would have DELETED.

    Returns None when there is no designation, or when the edges contradict each other
    (a cycle) — the caller then falls back to the heuristic.
    """
    targets: set[str] = set()
    sources: set[str] = set()
    by_uid = {uid(i): i for i in group_ids}
    for lk in links:
        if lk["link_type"] != MIRRORS:
            continue
        s, t = lk["source_id"], lk["target_id"]
        if s in by_uid and t in by_uid:
            sources.add(by_uid[s])
            targets.add(by_uid[t])
    finals = targets - sources  # end of the mirror chain (A->B->C  =>  C)
    return finals.pop() if len(finals) == 1 else None


def pick_survivor(
    group: list[dict[str, Any]], links: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Choose the record to keep: an existing canonical designation first, else heuristic.

    Heuristic: richest schema (has pattern_id), then earliest created_at, then first.
    """
    if links:
        canon = canonical_from_links({p["id"] for p in group}, links)
        if canon is not None:
            for p in group:
                if p["id"] == canon:
                    return p

    def sort_key(pt: dict[str, Any]) -> tuple:
        pl = pt["payload"]
        is_rich = 0 if pl.get("pattern_id") else 1  # prefer pattern_id schema
        created = str(pl.get("created_at") or "~")  # "~" sorts after ISO dates
        return (is_rich, created)

    return sorted(group, key=sort_key)[0]


def plan_link_moves(
    remap: dict[str, str],
    doomed: set[str],
    links: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Decide what happens to every edge touching a disappearing point.

    Planned GLOBALLY, over one remap of every loser→survivor across all groups, not
    per-group. Per-group planning was wrong: an edge BETWEEN two duplicate groups
    (``uid(x2) --supports--> uid(y2)``, both losers) is visited by both passes and
    re-pointed twice with contradictory ends — `x1→y2` and `x2→y1` — neither of which
    is the answer (`x1→y1`), and both of which dangle. One pass with both ends remapped
    at once cannot produce that.

    Args:
        remap: loser uid → survivor uid, for every duplicate group at once.
        doomed: uids of points that disappear WITHOUT an heir (purged test records).
        links: every edge touching any of the collection's points.

    Returns:
        ``(deletes, repoints)``. Cases per edge:

        * an end is doomed-without-heir → nothing to inherit it → **delete**;
        * both ends collapse onto the same point → the edge described the duplication
          itself (e.g. the ``mirrors`` edge that named the canonical) → **delete**;
        * the re-pointed edge already exists (or is already planned) → **delete** the
          loser's copy rather than create a duplicate;
        * otherwise → **re-point**.

    Deleting the losers' edges outright ("also delete the links") would silently drop
    provenance: in live group 3 the only ``derives_from`` edge to the episodic source
    hung off the loser.
    """
    existing = {(lk["source_id"], lk["link_type"], lk["target_id"]) for lk in links}

    deletes: list[dict[str, Any]] = []
    repoints: list[dict[str, Any]] = []
    planned: set[tuple[str, str, str]] = set()

    for lk in links:
        src, ltype, tgt = lk["source_id"], lk["link_type"], lk["target_id"]
        if src in doomed or tgt in doomed:
            deletes.append({**lk, "reason": "endpoint-purged"})
            continue
        if src not in remap and tgt not in remap:
            continue
        new_src = remap.get(src, src)
        new_tgt = remap.get(tgt, tgt)
        if new_src == new_tgt:
            deletes.append({**lk, "reason": "intra-group"})
            continue
        key = (new_src, ltype, new_tgt)
        if key in existing or key in planned:
            deletes.append({**lk, "reason": "already-on-survivor"})
            continue
        planned.add(key)
        repoints.append({**lk, "new_source_id": new_src, "new_target_id": new_tgt})

    return deletes, repoints


def build_plan(
    points: list[dict[str, Any]],
    drop_test: bool,
    links: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Pure planner: group by content, choose survivors, compute merges/deletes.

    Args:
        points: Qdrant points as ``{"id", "payload"}``.
        drop_test: also plan removal of the exact-content test markers.
        links: edges touching *points* (see :func:`load_links_for`). Empty/omitted means
            "there are no edges" — main() is responsible for refusing to run when the
            registry could not be READ, since "unknown" and "none" are not the same
            thing and only one of them is safe to delete against.
    """
    links = list(links or [])
    groups: dict[str, list[dict[str, Any]]] = {}
    for pt in points:
        groups.setdefault(content_key(pt["payload"]), []).append(pt)

    # Test records are resolved FIRST. They used to be computed after the link plan,
    # which let a point be a survivor (inheriting re-pointed edges) AND a purge target
    # in the same run — the edges then hung off a deleted point while the dangling
    # guard, keyed on "was this link_id planned", reported all clear. Every member of a
    # content group is by construction the same content, so a marker match purges the
    # whole group: no survivor, no heir, no re-point.
    test_ids: list[str] = []
    if drop_test:
        for pt in points:
            if _content(pt["payload"]).strip() in TEST_MARKERS:
                test_ids.append(pt["id"])
    purged = set(test_ids)

    delete_ids: list[str] = []
    survivor_updates: list[dict[str, Any]] = []
    canonical_conflicts: list[dict[str, Any]] = []
    remap: dict[str, str] = {}  # loser uid -> survivor uid, across ALL groups
    dup_groups = 0

    for key, group in groups.items():
        if any(p["id"] in purged for p in group):
            continue  # whole group is purged; nothing survives to inherit anything
        survivor = pick_survivor(group, links)
        losers = [p for p in group if p["id"] != survivor["id"]]
        if not losers:
            continue
        dup_groups += 1
        delete_ids.extend(p["id"] for p in losers)
        for p in losers:
            remap[uid(p["id"])] = uid(survivor["id"])

        group_ids = {p["id"] for p in group}
        # Surface where the durable designation and the local heuristic disagreed —
        # that disagreement is the bug this planner exists to not have.
        canon = canonical_from_links(group_ids, links)
        heuristic = pick_survivor(group, None)["id"]
        if canon is not None and canon != heuristic:
            canonical_conflicts.append(
                {"group": key, "canonical": canon, "heuristic_pick": heuristic}
            )

        # Merge counts across the whole group into the survivor.
        succ = sum(_num(p["payload"], "succ") for p in group)
        fail = sum(_num(p["payload"], "fail") for p in group)
        appc = sum(_num(p["payload"], "application_count") for p in group)
        cur = survivor["payload"]
        if (
            _num(cur, "succ") != succ
            or _num(cur, "fail") != fail
            or _num(cur, "application_count") != appc
        ):
            survivor_updates.append(
                {
                    "id": survivor["id"],
                    "succ": succ,
                    "fail": fail,
                    "application_count": int(appc),
                    "confidence": round(derive_confidence(succ, fail), 6),
                }
            )

    link_deletes, link_repoints = plan_link_moves(remap, {uid(i) for i in test_ids}, links)

    # Invariant, checked against the FINAL edge set rather than against bookkeeping:
    # simulate the graph after the moves and assert nothing points at a deleted point.
    # The earlier version asked "was this link_id planned?", which a planner bug cannot
    # fail — a wrongly re-pointed edge counts as planned and still dangles.
    doomed = {uid(i) for i in delete_ids} | {uid(i) for i in test_ids}
    dropped = {lk["link_id"] for lk in link_deletes}
    moved_from = {lk["link_id"] for lk in link_repoints}
    final_edges = [
        (lk["source_id"], lk["target_id"])
        for lk in links
        if lk["link_id"] not in dropped and lk["link_id"] not in moved_from
    ] + [(lk["new_source_id"], lk["new_target_id"]) for lk in link_repoints]
    dangling = [
        {"source_id": s, "target_id": t} for s, t in final_edges if s in doomed or t in doomed
    ]

    return {
        "total": len(points),
        "unique_groups": len(groups),
        "dup_groups": dup_groups,
        "dup_delete_ids": delete_ids,
        "survivor_updates": survivor_updates,
        "test_delete_ids": test_ids,
        "final_count": len(points) - len(delete_ids) - len(test_ids),
        "link_deletes": link_deletes,
        "link_repoints": link_repoints,
        "canonical_conflicts": canonical_conflicts,
        "dangling_links": dangling,
    }


# --------------------------------------------------------------------------- I/O
def _client():
    from qdrant_client import QdrantClient

    return QdrantClient(host="127.0.0.1", port=6333, timeout=30)


def _registry():
    """LinkRegistry, or raise — a dedupe without the edge graph is not safe to run."""
    src = str(PROJECT_ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from memory.orchestrator.link_registry import LinkRegistry

    return LinkRegistry()


def _link_dict(lk: Any) -> dict[str, Any]:
    return {
        "link_id": lk.link_id,
        "source_id": lk.source_id,
        "target_id": lk.target_id,
        "link_type": lk.link_type.value,
        "strength": lk.strength,
        "metadata": dict(lk.metadata or {}),
        "created_by": lk.created_by,
    }


def load_links_for(registry, point_ids: list[str]) -> list[dict[str, Any]]:
    """Every edge touching any of *point_ids*, de-duplicated by link_id.

    Both the unified form and the bare uuid are queried — all 46 live edges use the
    unified form (create_link has rejected bare ids since P0.1), but a legacy bare-id
    edge this planner failed to see is exactly the dangling edge it exists to prevent.

    A bare-id end is NORMALIZED to the unified form on the way out. Without that the
    lookup was decoration: every downstream set (`remap`, `doomed`, `existing`) is keyed
    on `uid(...)`, so a loaded `<bare-uuid> --mirrors--> …` edge matched nothing, was
    never planned, and dangled anyway — protection in the docstring only. The original
    id is kept so the applier still deletes the right row.
    """
    known = set(point_ids)

    def _norm(entity_id: str) -> str:
        return uid(entity_id) if entity_id in known else entity_id

    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pid in point_ids:
        for eid in (uid(pid), pid):
            try:
                all_links = registry.get_all_links(eid)
            except Exception:
                continue
            for direction in ("outgoing", "incoming"):
                for lk in all_links.get(direction, []):
                    if lk.link_id in seen:
                        continue
                    seen.add(lk.link_id)
                    rec = _link_dict(lk)
                    rec["source_id"] = _norm(rec["source_id"])
                    rec["target_id"] = _norm(rec["target_id"])
                    out.append(rec)
    return out


def apply_link_plan(registry, plan: dict[str, Any]) -> tuple[int, int, list[dict[str, Any]]]:
    """Re-point the losers' edges, then drop the ones that lost their referent.

    Create-before-delete on purpose: the re-pointed edge exists before its origin is
    removed, so an interrupted run leaves a duplicate (harmless, idempotent to re-run)
    rather than a hole.

    An origin is deleted ONLY once its replacement is known to exist. The first cut
    swallowed every ``ValueError`` as "already exists" and deleted the origin anyway —
    but ``create_link`` also raises ValueError for a non-unified entity id, an unknown
    link type, a self-link and an out-of-range strength. A legacy bare-uuid edge would
    have been refused, silently destroyed, and counted as "1 repointed": the exact
    provenance loss this whole change exists to prevent, dressed as success.

    Returns:
        ``(repointed, deleted, failed)`` — *failed* edges are left INTACT, and the
        caller must surface them.
    """
    from memory.orchestrator.link_registry import LinkType

    repointed = 0
    failed: list[dict[str, Any]] = []
    for lk in plan["link_repoints"]:
        try:
            ltype = LinkType.from_string(lk["link_type"])
            already = registry.find_link(lk["new_source_id"], lk["new_target_id"], ltype)
            if already is None:
                registry.create_link(
                    source_id=lk["new_source_id"],
                    target_id=lk["new_target_id"],
                    link_type=ltype,
                    strength=lk["strength"],
                    metadata={
                        **lk["metadata"],
                        "repointed_from": lk["link_id"],
                        "repointed_by": "dedupe_learned_patterns",
                    },
                    created_by=lk["created_by"],
                )
        except Exception as exc:
            # Keep the origin. A refused re-point means we do not know where the fact
            # lives now — deleting the evidence would be the worse of the two states.
            failed.append({**lk, "error": f"{type(exc).__name__}: {exc}"})
            continue
        registry.delete_link(lk["link_id"], deleted_by="dedupe_learned_patterns")
        repointed += 1

    deleted = 0
    for lk in plan["link_deletes"]:
        if registry.delete_link(lk["link_id"], deleted_by="dedupe_learned_patterns"):
            deleted += 1
    return (repointed, deleted, failed)


def fetch_points(client, with_vectors: bool = False) -> list[dict[str, Any]]:
    points, _ = client.scroll(
        collection_name=COLLECTION,
        limit=10000,
        with_payload=True,
        with_vectors=with_vectors,
    )
    out = []
    for p in points:
        rec = {"id": str(p.id), "payload": p.payload or {}}
        if with_vectors:
            rec["vector"] = p.vector
        out.append(rec)
    return out


def write_backup(client, stamp: str, links: list[dict[str, Any]] | None = None) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    full = fetch_points(client, with_vectors=True)
    path = BACKUP_DIR / f"{COLLECTION}_{stamp}.json"
    # `links` joins the snapshot because this run now mutates the registry too
    # (roadmap 260716 P1.7). A backup that only covers one of the two stores it writes
    # is not a backup.
    #
    # None (the default, used by callers that do not touch the graph — e.g.
    # backfill_content_hash) is serialized as null, NOT []: "not captured" and "captured,
    # there were none" must not look identical to `restore_backup`.
    blob = json.dumps(
        {
            "collection": COLLECTION,
            "points": full,
            "links": list(links) if links is not None else None,
        },
        ensure_ascii=False,
    )
    # Atomic write: the backup is the recovery artifact, so a crash mid-write must not
    # leave it truncated. Write to a temp file, then os.replace (atomic on win32 + posix).
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(blob, encoding="utf-8")
    os.replace(tmp, path)
    return path


def restore_links(registry, links: list[dict[str, Any]]) -> tuple[int, int]:
    """Undo this tool's edge surgery: re-add the snapshot, remove what the run created.

    Returns ``(restored, removed)``. Both halves are needed for `--restore` to be an
    actual rollback: re-adding alone left every re-pointed edge in place next to its
    resurrected original, so the graph ended up with BOTH. Edges created by a run are
    identified by the `repointed_by` stamp `apply_link_plan` writes, so nothing a human
    or another subsystem added is ever touched. Idempotent.
    """
    from memory.orchestrator.link_registry import LinkType

    restored = 0
    for lk in links:
        try:
            ltype = LinkType.from_string(lk["link_type"])
            if registry.find_link(lk["source_id"], lk["target_id"], ltype) is not None:
                continue  # already present
            registry.create_link(
                source_id=lk["source_id"],
                target_id=lk["target_id"],
                link_type=ltype,
                strength=lk["strength"],
                metadata=lk.get("metadata") or {},
                created_by=lk.get("created_by", "system"),
            )
            restored += 1
        except Exception as exc:
            print(f"WARNING: could not restore link {lk.get('link_id')}: {exc}", file=sys.stderr)

    snapshot_ids = {lk["link_id"] for lk in links}
    removed = 0
    for eid in {lk["source_id"] for lk in links} | {lk["target_id"] for lk in links}:
        try:
            all_links = registry.get_all_links(eid)
        except Exception:
            continue
        for direction in ("outgoing", "incoming"):
            for cur in all_links.get(direction, []):
                if cur.link_id in snapshot_ids:
                    continue
                if (cur.metadata or {}).get("repointed_by") != "dedupe_learned_patterns":
                    continue  # not ours — leave it alone
                if registry.delete_link(cur.link_id, deleted_by="dedupe_learned_patterns"):
                    removed += 1
    return (restored, removed)


def restore_backup(client, path: Path) -> tuple[int, int]:
    from qdrant_client.models import PointStruct

    data = json.loads(path.read_text(encoding="utf-8"))
    pts = data.get("points", [])
    structs = [
        PointStruct(id=p["id"], vector=p["vector"], payload=p.get("payload", {}))
        for p in pts
        if p.get("vector") is not None
    ]
    if structs:
        client.upsert(collection_name=COLLECTION, points=structs)

    links_restored = 0
    snap_links = data.get("links")
    if snap_links is None:
        # `null` (not `[]`) means the snapshot predates link capture — say so instead of
        # reporting "0 links restored", which reads as "there were none".
        print(
            f"WARNING: {path.name} carries no link snapshot (written before P1.7 or by "
            "another tool) — the graph is NOT restored.",
            file=sys.stderr,
        )
    elif snap_links:
        try:
            restored, removed = restore_links(_registry(), snap_links)
            links_restored = restored
            print(f"links: {restored} re-added, {removed} run-created removed")
        except Exception as exc:  # points are back; say so, don't pretend links are
            print(f"WARNING: points restored but links were not: {exc}", file=sys.stderr)
    return (len(structs), links_restored)


def apply_plan(client, plan: dict[str, Any]) -> None:
    for upd in plan["survivor_updates"]:
        client.set_payload(
            collection_name=COLLECTION,
            payload={
                "succ": upd["succ"],
                "fail": upd["fail"],
                "application_count": upd["application_count"],
                "confidence": upd["confidence"],
            },
            points=[upd["id"]],
        )
    to_delete = plan["dup_delete_ids"] + plan["test_delete_ids"]
    if to_delete:
        client.delete(collection_name=COLLECTION, points_selector=to_delete)


def main() -> int:
    ap = argparse.ArgumentParser(description="dedupe + cleanup learned_patterns")
    ap.add_argument("--apply", action="store_true", help="execute (default: dry-run)")
    ap.add_argument("--drop-test", action="store_true", help="also drop exact test records")
    ap.add_argument("--no-backup", action="store_true", help="skip backup (not recommended)")
    ap.add_argument("--restore", default=None, help="restore from a backup JSON (needs --apply)")
    ap.add_argument("--stamp", default=None, help="override backup timestamp (tests)")
    args = ap.parse_args()

    try:
        client = _client()
    except Exception as exc:
        print(f"Qdrant unavailable: {exc}", file=sys.stderr)
        return 1

    if args.restore:
        if not args.apply:
            print(f"Dry-run: would restore {COLLECTION} from {args.restore} (use --apply).")
            return 0
        n, nl = restore_backup(client, Path(args.restore))
        print(f"Restored {n} points (+{nl} links) into {COLLECTION} from {args.restore}.")
        return 0

    points = fetch_points(client)

    # Fail-closed: "the registry could not be read" and "there are no edges" produce
    # the same empty list but not the same risk. Planning deletes against an UNKNOWN
    # graph is how this tool would have orphaned 10 edges — so it refuses instead.
    try:
        registry = _registry()
        links = load_links_for(registry, [p["id"] for p in points])
    except Exception as exc:
        print(f"link_registry unavailable: {exc}", file=sys.stderr)
        print("Refusing to plan deletes without the edge graph.", file=sys.stderr)
        return 1

    plan = build_plan(points, drop_test=args.drop_test, links=links)

    print(f"# learned_patterns dedupe (apply={args.apply}, drop_test={args.drop_test})")
    print(
        f"total={plan['total']} unique_content_groups={plan['unique_groups']} "
        f"dup_groups={plan['dup_groups']}"
    )
    print(f"dup copies to delete: {len(plan['dup_delete_ids'])}")
    print(f"survivor stat-merges: {len(plan['survivor_updates'])}")
    print(f"test records to delete: {len(plan['test_delete_ids'])}")
    print(f"final count: {plan['final_count']} (from {plan['total']})")
    print(
        f"links: {len(links)} touching these points -> "
        f"{len(plan['link_repoints'])} repointed, {len(plan['link_deletes'])} dropped"
    )
    for c in plan["canonical_conflicts"]:
        print(
            f"  ! canonical {c['canonical'][:8]} (mirrors) overrides "
            f"heuristic pick {c['heuristic_pick'][:8]} — keeping the canonical"
        )
    if plan["dangling_links"]:
        # Belt-and-braces: build_plan accounts for every edge touching a doomed point,
        # so a non-empty list here means the planner has a hole. Refuse, loudly.
        print(
            f"ABORT: {len(plan['dangling_links'])} edge(s) would be left dangling; "
            "planner bug — not applying.",
            file=sys.stderr,
        )
        return 1

    if not args.apply:
        print("\n-> dry-run; re-run with --apply to execute.")
        return 0

    stamp = args.stamp or _safe_stamp()
    if not args.no_backup:
        bpath = write_backup(client, stamp, links=links)
        print(f"\nbackup: {bpath}")
    # Links first: while both stores are still consistent. If this half fails, the
    # points are untouched and re-running simply re-plans.
    repointed, dropped, failed = apply_link_plan(registry, plan)
    if failed:
        # A refused re-point means an edge we cannot account for. Deleting its point
        # would orphan that edge — the one thing this planner promises not to do.
        print(f"\nABORT: {len(failed)} edge(s) could not be re-pointed; points NOT deleted.")
        for f in failed:
            print(f"  {f['link_id']}: {f['error']}")
        print("Fix the edges (or the registry) and re-run; the run is idempotent.")
        return 1
    apply_plan(client, plan)
    remaining = len(fetch_points(client))
    print(
        f"-> DONE. collection now has {remaining} points; "
        f"links: {repointed} repointed, {dropped} dropped "
        f"(restore: --restore {BACKUP_DIR / (COLLECTION + '_' + stamp + '.json')} --apply)"
    )
    return 0


def _safe_stamp() -> str:
    # Date.now() is fine here (CLI, not a resumable workflow).
    from datetime import datetime

    return datetime.now().strftime("%Y%m%d_%H%M%S")


if __name__ == "__main__":
    raise SystemExit(main())
