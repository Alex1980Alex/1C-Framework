#!/usr/bin/env python3
"""Normalize legacy "light" learned_patterns records into full LearnedPattern schema.

The collection mixes two payload shapes:
  - RICH  (real LearnedPattern): pattern_id, pattern_type, confidence, succ/fail, ...
  - LIGHT (migrated out of memory-ai): original_id, content, category, importance, source.

When a LIGHT record is read via _pattern_from_payload it loses its real category
(falls back to models.DEFAULT_PATTERN_TYPE — "workflow-pattern" since roadmap 260716;
"code-convention" before that) and importance (defaults to 0.5). This rewrites each
mappable LIGHT record into the full schema:
  - pattern_type  via CATEGORY_MAP[category]   (decision -> architectural-principle, etc.)
  - confidence    via importance               (denorm field; honors the migrated signal)
  - succ/fail     via seed_counts_from_legacy(importance, application_count)   (= 0,0 here)
  - metadata      provenance (original_id, original_category, original_importance, source)
  - tags          parsed to a real list (LIGHT stored them as the string "[]")
  - vector        unchanged (re-embed only with --reembed)

Section 22 note: effective_confidence (the Beta signal used in ranking) starts at the
prior 0.70 because these records have NO real application history. We do NOT fabricate
success evidence out of `importance` -- that would invent fake observations. importance
is preserved as the denorm confidence + in metadata. Use --seed-importance N to inject
N synthetic pseudo-observations at the importance ratio if you explicitly want
effective approx importance immediately (off by default).

SAFETY: dry-run by default (--apply required); vector-inclusive atomic backup before
any write (restore via scripts/dedupe_learned_patterns.py --restore). Records whose
category is NOT in CATEGORY_MAP (e.g. session_summary -- episodic, not a pattern) are
SKIPPED and reported, never force-typed.

Usage:
  python scripts/normalize_light_patterns.py                 # dry-run plan
  python scripts/normalize_light_patterns.py --apply
  python scripts/normalize_light_patterns.py --apply --seed-importance 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COLLECTION = "learned_patterns"
BACKUP_DIR = PROJECT_ROOT / "data" / "memory" / "backups"

# category (memory-ai) -> pattern_type (PatternType enum value). Anything absent here
# is treated as "not a pattern" and skipped (e.g. session_summary = episodic log).
#
# Membership stays local (it decides what IS a pattern), but the category→type
# mapping itself resolves through the ONE alias table in vector_memory.models
# (roadmap 260716 P0.1) — this map used to be copy-pasted here and in
# hooks/shared/reflection.py, so the three could drift apart.
_MAPPED_CATEGORIES = (
    "decision",
    "preference",
    "bugfix",
    "implementation",
    "reference",
    "feedback",
    "project",
    "code-convention",
)


def _category_map() -> dict[str, str]:
    src = str(PROJECT_ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from memory.vector_memory.models import PatternType

    return {c: PatternType.coerce(c).value for c in _MAPPED_CATEGORIES}


CATEGORY_MAP = _category_map()


def is_light(payload: dict[str, Any]) -> bool:
    """LIGHT = migrated shape: has original_id and lacks the rich pattern_id field."""
    return bool(payload.get("original_id")) and not payload.get("pattern_id")


def derive_name(content: str) -> str:
    """Title from content: text before the first pipe if early, else first line; <=80 ch."""
    head = content.strip()
    bar = head.find("|")
    if 0 < bar < 100:
        title = head[:bar].strip()
    else:
        title = head.splitlines()[0].strip() if head else ""
    return title[:80]


def parse_tags(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            v = json.loads(raw)
            return v if isinstance(v, list) else []
        except (ValueError, json.JSONDecodeError):
            return []
    return []


def _seed_counts(importance: float, application_count: int, seed_importance: int):
    """succ/fail seed. seed_importance>0 injects synthetic pseudo-observations at the
    importance ratio (effective approx importance); else honest seeding (0,0 here)."""
    n = application_count + seed_importance
    try:
        src = str(PROJECT_ROOT / "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from memory.vector_memory.confidence import seed_counts_from_legacy

        return seed_counts_from_legacy(importance, n)
    except Exception:
        return (importance * n, (1.0 - importance) * n)


def _content_hash(content: str) -> str | None:
    """§26 content_hash for the rewritten payload, always DERIVED from the content.

    roadmap 260716 M10: this script writes with `overwrite_payload`, which REPLACES the
    payload wholesale, and the dict below never carried `content_hash` — so normalizing
    a record silently dropped the field.

    ⚠ Scope, corrected after review: this does NOT fix write-time dedup. That dedup keys
    on the DERIVED POINT ID (`save_pattern`/`pattern_harvest` upsert at
    `uuid5(NS, hash_content(content))` and skip if it exists), not on this payload field,
    and a LIGHT record's id is a random uuid inherited from the memory-ai migration — so
    a later save of the same content lands on its own point either way. The field matters
    to READ-time consumers (cross-store sync, the curation banner), and that is the whole
    claim.

    The stored value is deliberately not reused: a payload field is untrusted input (P0),
    and a stale hash copied into the canonical schema would point readers at the wrong
    fact. `hash_content` is total and free, so there is nothing to trade.
    """
    try:
        src = str(PROJECT_ROOT / "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from memory.orchestrator.content_hash import hash_content

        return str(hash_content(content))
    except Exception:
        return None  # honest omission beats a hash computed by a different rule


def normalize_payload(
    point_id: str,
    payload: dict[str, Any],
    now_iso: str,
    seed_importance: int = 0,
) -> dict[str, Any] | None:
    """Build a full LearnedPattern payload from a LIGHT record, or None to skip."""
    category = payload.get("category", "")
    ptype = CATEGORY_MAP.get(category)
    if ptype is None:
        return None  # unmapped (e.g. session_summary) -> skip, never force-type
    content = payload.get("content") or payload.get("description") or ""
    importance = payload.get("importance")
    importance = float(importance) if isinstance(importance, (int, float)) else 0.5
    appc = int(payload.get("application_count", 0) or 0)
    succ, fail = _seed_counts(importance, appc, seed_importance)
    created = payload.get("created_at") or now_iso
    chash = _content_hash(content)
    out = {
        "pattern_id": point_id,
        "pattern_type": ptype,
        "name": derive_name(content),
        "description": "",
        "content": content,
        "confidence": round(importance, 6),
        "evidence_sources": [],
        "created_at": created,
        "updated_at": now_iso,
        "last_applied": None,
        "succ": round(succ, 6),
        "fail": round(fail, 6),
        "last_decay_at": created,
        "expired_at": None,
        "decay_rate": 0.05,
        "application_count": appc,
        "version": 1,
        "tags": parse_tags(payload.get("tags")),
        "metadata": {
            "migrated_from": payload.get("source", "memory_ai_session"),
            "original_id": payload.get("original_id"),
            "original_category": category,
            "original_importance": importance,
            "normalized_at": now_iso,
        },
    }
    if chash:
        out["content_hash"] = chash
    return out


def build_plan(points: list[Any], now_iso: str, seed_importance: int) -> dict[str, Any]:
    normalized: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    rich = 0
    for p in points:
        pl = p.payload or {}
        if not is_light(pl):
            rich += 1
            continue
        new = normalize_payload(str(p.id), pl, now_iso, seed_importance)
        if new is None:
            skipped.append({"id": str(p.id), "category": pl.get("category", "?")})
        else:
            normalized.append(
                {
                    "id": str(p.id),
                    "category": pl.get("category"),
                    "pattern_type": new["pattern_type"],
                    "payload": new,
                }
            )
    return {
        "total": len(points),
        "rich_untouched": rich,
        "normalize": normalized,
        "skipped": skipped,
    }


def _client():
    from qdrant_client import QdrantClient

    return QdrantClient(host="127.0.0.1", port=6333, timeout=30)


def write_backup(client, stamp: str) -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    pts, _ = client.scroll(COLLECTION, limit=10000, with_payload=True, with_vectors=True)
    blob = json.dumps(
        {
            "collection": COLLECTION,
            "points": [{"id": str(p.id), "vector": p.vector, "payload": p.payload} for p in pts],
        },
        ensure_ascii=False,
    )
    path = BACKUP_DIR / f"{COLLECTION}_{stamp}_normalize.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(blob, encoding="utf-8")
    os.replace(tmp, path)
    return path


def _safe_stamp() -> str:
    from datetime import datetime

    return datetime.now().strftime("%Y%m%d_%H%M%S")


def main() -> int:
    ap = argparse.ArgumentParser(description="normalize light learned_patterns into full schema")
    ap.add_argument("--apply", action="store_true", help="execute (default: dry-run)")
    ap.add_argument("--no-backup", action="store_true")
    ap.add_argument(
        "--seed-importance",
        type=int,
        default=0,
        help="inject N synthetic pseudo-observations at importance ratio (default 0)",
    )
    ap.add_argument("--stamp", default=None)
    args = ap.parse_args()

    try:
        client = _client()
        points, _ = client.scroll(COLLECTION, limit=10000, with_payload=True, with_vectors=False)
    except Exception as exc:
        print(f"Qdrant unavailable: {exc}", file=sys.stderr)
        return 1

    from datetime import datetime

    now_iso = args.stamp or datetime.now().isoformat()
    plan = build_plan(points, now_iso, args.seed_importance)

    print(
        f"# normalize light patterns (apply={args.apply}, seed_importance={args.seed_importance})"
    )
    print(
        f"total={plan['total']} rich_untouched={plan['rich_untouched']} "
        f"to_normalize={len(plan['normalize'])} skipped={len(plan['skipped'])}"
    )
    for n in plan["normalize"]:
        print(
            f"  NORMALIZE {n['id'][:8]} category={n['category']} -> pattern_type={n['pattern_type']}"
        )
    for s in plan["skipped"]:
        print(f"  SKIP      {s['id'][:8]} category={s['category']} (not a pattern -> left as-is)")

    if not args.apply:
        print("\n-> dry-run; re-run with --apply to write.")
        return 0
    if not plan["normalize"]:
        print("\n-> nothing to normalize.")
        return 0

    stamp = args.stamp or _safe_stamp()
    if not args.no_backup:
        bpath = write_backup(client, stamp)
        print(f"\nbackup: {bpath}")

    for n in plan["normalize"]:
        client.overwrite_payload(collection_name=COLLECTION, payload=n["payload"], points=[n["id"]])
    try:
        from memory.vector_memory.epoch import bump

        bump()
    except Exception:
        pass
    print(
        f"-> NORMALIZED {len(plan['normalize'])} records "
        f"(restore: dedupe_learned_patterns.py --restore <backup> --apply)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
