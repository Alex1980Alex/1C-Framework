#!/usr/bin/env python3
"""Cross-store ``content_hash`` index — CLI scanners (§26 P3, D3.1).

Scans every MemoryCube-managed store, derives the canonical ``content_hash`` for
each item, and reports facts that live in **two or more** stores (divergence) —
the input to P3 dedup/sync and the ``cross_store_dup_rate`` metric.

Stores scanned:
  - learned_patterns (Qdrant)            -> payload ``content_hash``/``content``
  - memory_ai        (SQLite)            -> ``important_messages.content`` (hashed)
  - skill_learning   (JSONL)             -> ``patterns.jsonl`` records (hashed)
  - wiki             (Markdown drafts)   -> ``docs/wiki/drafts/*.md`` frontmatter

READ-ONLY (dry-run): builds a report only; never writes/deletes a store
(acceptance D3.1 #5). Each scanner is **fail-soft** — a down store (Qdrant/TEI,
missing file) is skipped with a recorded warning, never aborts the run.

Usage:
  python scripts/cross_store_index.py             # scan + write report + summary
  python scripts/cross_store_index.py --json      # machine-readable summary to stdout
  python scripts/cross_store_index.py --no-report  # don't write the report file
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from memory.orchestrator.content_hash import content_key, hash_content
from memory.orchestrator.cross_store_index import (
    StoreRecord,
    build_index,
    find_cross_store_dups,
    render_report,
    summarize,
)

MEMORY_AI_DB = PROJECT_ROOT / "data" / "memory_ai.db"
SKILL_JSONL = PROJECT_ROOT / "data" / "skill_learning" / "patterns.jsonl"
WIKI_DRAFTS = PROJECT_ROOT / "docs" / "wiki" / "drafts"
REPORTS_DIR = PROJECT_ROOT / "data" / "reports" / "memory"

_FRONTMATTER_HASH = re.compile(r"^content_hash:\s*(\S+)\s*$", re.MULTILINE)


def scan_learned_patterns() -> tuple[list[StoreRecord], str | None]:
    """Qdrant ``learned_patterns`` — reuse the dedupe script's client/scroll."""
    try:
        from scripts.dedupe_learned_patterns import _client, fetch_points

        client = _client()
        points = fetch_points(client)
    except Exception as exc:  # fail-soft per D3.1
        return [], f"{type(exc).__name__}: {exc}"
    records: list[StoreRecord] = []
    for pt in points:
        payload = pt.get("payload", {}) or {}
        ch = payload.get("content_hash") or content_key(payload)
        if not ch:
            continue
        preview = payload.get("content") or payload.get("description") or ""
        records.append(StoreRecord("learned_patterns", str(pt["id"]), ch, preview))
    return records, None


def scan_memory_ai(db_path: Path = MEMORY_AI_DB) -> tuple[list[StoreRecord], str | None]:
    """memory-ai SQLite — hash ``important_messages.content`` (no stored hash yet)."""
    if not db_path.exists():
        return [], f"db not found: {db_path}"
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT id, content FROM important_messages").fetchall()
        finally:
            conn.close()
    except Exception as exc:  # fail-soft
        return [], f"{type(exc).__name__}: {exc}"
    records: list[StoreRecord] = []
    for row in rows:
        content = row["content"] or ""
        ch = hash_content(content)
        if not content:
            continue
        records.append(StoreRecord("memory_ai", str(row["id"]), ch, content))
    return records, None


def scan_skill_learning(jsonl_path: Path = SKILL_JSONL) -> tuple[list[StoreRecord], str | None]:
    """skill-learning JSONL — prefer stored ``content_hash`` else hash ``content``."""
    if not jsonl_path.exists():
        return [], f"file not found: {jsonl_path}"
    records: list[StoreRecord] = []
    try:
        with jsonl_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = rec.get("content") or rec.get("description") or ""
                ch = rec.get("content_hash") or hash_content(content)
                if not content:
                    continue
                item_id = str(rec.get("pattern_id") or rec.get("id") or "?")
                records.append(StoreRecord("skill_learning", item_id, ch, content))
    except Exception as exc:  # fail-soft
        return [], f"{type(exc).__name__}: {exc}"
    return records, None


def scan_wiki(drafts_dir: Path = WIKI_DRAFTS) -> tuple[list[StoreRecord], str | None]:
    """wiki drafts — read ``content_hash`` from MemoryCube frontmatter."""
    if not drafts_dir.exists():
        return [], f"dir not found: {drafts_dir}"
    records: list[StoreRecord] = []
    try:
        for md in sorted(drafts_dir.glob("*.md")):
            try:
                text = md.read_text(encoding="utf-8")
            except Exception:  #skip unreadable file
                continue
            m = _FRONTMATTER_HASH.search(text)
            if not m:
                continue
            records.append(StoreRecord("wiki", md.stem, m.group(1), md.stem))
    except Exception as exc:  # fail-soft
        return [], f"{type(exc).__name__}: {exc}"
    return records, None


def run_scan() -> tuple[list[StoreRecord], dict[str, str]]:
    """Run every scanner; collect records + per-store fail-soft errors."""
    records: list[StoreRecord] = []
    errors: dict[str, str] = {}
    for name, scanner in (
        ("learned_patterns", scan_learned_patterns),
        ("memory_ai", scan_memory_ai),
        ("skill_learning", scan_skill_learning),
        ("wiki", scan_wiki),
    ):
        recs, err = scanner()
        records.extend(recs)
        if err:
            errors[name] = err
    return records, errors


def main() -> int:
    ap = argparse.ArgumentParser(description="cross-store content_hash index (§26 P3 D3.1)")
    ap.add_argument("--json", action="store_true", help="print JSON summary to stdout")
    ap.add_argument("--no-report", action="store_true", help="do not write report file")
    ap.add_argument("--stamp", default=None, help="override timestamp (tests)")
    args = ap.parse_args()

    records, errors = run_scan()
    index = build_index(records)
    dups = find_cross_store_dups(index)
    summary = summarize(records, index, dups)
    stamp = args.stamp or datetime.now().strftime("%Y%m%d_%H%M%S")

    if not args.no_report:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        report = render_report(summary, dups, stamp, errors)
        (REPORTS_DIR / f"cross_store_index_{stamp}.md").write_text(report, encoding="utf-8")
        sidecar = {
            "summary": summary,
            "store_errors": errors,
            "cross_store_dups": [
                {"content_hash": h, "stores": sorted({r.store for r in recs}),
                 "items": [{"store": r.store, "id": r.item_id} for r in recs]}
                for h, recs in dups
            ],
        }
        (REPORTS_DIR / f"cross_store_index_{stamp}.json").write_text(
            json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    if args.json:
        print(json.dumps(summary, ensure_ascii=False))
        return 0

    # ASCII-safe stdout (cyrillic previews stay in the UTF-8 report file).
    print("# cross-store content_hash index")
    print(f"total={summary['total_records']} unique_hashes={summary['unique_hashes']} "
          f"by_store={summary['by_store']}")
    print(f"intra_store_dups={summary['intra_store_dups']} "
          f"cross_store_dups={summary['cross_store_dup_count']} "
          f"rate={summary['cross_store_dup_rate']}")
    if errors:
        print(f"skipped (fail-soft): {errors}")
    if not args.no_report:
        print(f"report: data/reports/memory/cross_store_index_{stamp}.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
