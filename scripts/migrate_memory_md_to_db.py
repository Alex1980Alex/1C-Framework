#!/usr/bin/env python3
"""
migrate_memory_md_to_db.py — One-shot migration of .md memory files to SQLite.

Migrates markdown memory files from the Claude project memory directory into
`important_messages` SQLite table. Idempotent via SHA-256 content hash stored
in row metadata, so re-running the script safely skips already-migrated files.

Usage:
    python scripts/migrate_memory_md_to_db.py
    python scripts/migrate_memory_md_to_db.py --dry-run -v
    python scripts/migrate_memory_md_to_db.py --memory-dir /path/to/memory

Exit codes:
    0 — success (no errors)
    1 — one or more files failed
"""

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQLITE_DB = PROJECT_ROOT / "data" / "memory_ai.db"
MEMORY_DIR = Path(
    os.environ.get(
        "CLAUDE_MEMORY_DIR",
        Path.home() / ".claude" / "projects" / "D--1--Framework" / "memory",
    )
)

IMPORTANCE_BY_TYPE = {
    "feedback": 0.8,
    "user": 0.7,
    "project": 0.6,
    "reference": 0.5,
}
DEFAULT_IMPORTANCE = 0.55


def parse_frontmatter(content: str) -> dict:
    """Parse YAML-like frontmatter. Returns {name, description, type, body}."""
    result = {"name": "", "description": "", "type": "", "body": ""}
    if not content.startswith("---"):
        result["body"] = content
        return result
    parts = content.split("---", 2)
    if len(parts) < 3:
        result["body"] = content
        return result
    fm = parts[1]
    result["body"] = parts[2].strip()
    for line in fm.strip().splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key in ("name", "description", "type"):
                result[key] = val
    return result


def content_hash(text: str) -> str:
    """SHA-256 of stripped content."""
    return hashlib.sha256(text.strip().encode("utf-8", errors="replace")).hexdigest()


def compute_importance(frontmatter_type: str) -> float:
    return IMPORTANCE_BY_TYPE.get(frontmatter_type.lower(), DEFAULT_IMPORTANCE)


def extract_tags(fm_type: str, filename: str, body: str) -> list:
    """Auto-extract tags. Max 10."""
    tags = set()
    if fm_type:
        tags.add(fm_type)
    base = filename.replace(".md", "").lower()
    for part in re.split(r"[_\-]", base):
        if 2 < len(part) < 20:
            tags.add(part)
    body_low = body.lower()
    if "bsl" in body_low or "1с" in body_low or "1c" in body_low:
        tags.add("1c")
    if "qdrant" in body_low:
        tags.add("qdrant")
    if "hook" in body_low:
        tags.add("hooks")
    if "skill" in body_low:
        tags.add("skills")
    if "memory" in body_low:
        tags.add("memory")
    return sorted(tags)[:10]


def already_migrated(conn, chash: str) -> bool:
    """Check by metadata->content_hash."""
    row = conn.execute(
        "SELECT 1 FROM important_messages WHERE metadata LIKE ?",
        (f'%"content_hash": "{chash}"%',),
    ).fetchone()
    return row is not None


def insert_row(conn, filename, fm, body, chash, dry_run=False):
    """Insert one memory file as important_messages row."""
    name = fm.get("name", "") or filename.replace(".md", "")
    desc = fm.get("description", "")
    fm_type = (fm.get("type") or "").lower() or "reference"

    content_parts = []
    if name:
        content_parts.append(name)
    if desc:
        content_parts.append(desc)
    body_snippet = body[:1500] if body else ""
    if body_snippet:
        content_parts.append(body_snippet)
    content = " | ".join(content_parts)

    importance = compute_importance(fm_type)
    tags = extract_tags(fm_type, filename, body)
    now = datetime.now().isoformat()
    metadata = {
        "source": "memory_md_migration",
        "source_file": filename,
        "content_hash": chash,
        "fm_type": fm_type,
        "fm_name": name,
        "fm_description": desc,
    }

    if dry_run:
        return (str(uuid4()), content[:80], importance, fm_type, tags)

    conn.execute(
        "INSERT INTO important_messages "
        "(id, content, importance, category, tags, created_at, updated_at, metadata) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            str(uuid4()),
            content,
            importance,
            fm_type,
            json.dumps(tags, ensure_ascii=False),
            now,
            now,
            json.dumps(metadata, ensure_ascii=False),
        ),
    )
    conn.commit()
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Migrate memory .md files to SQLite important_messages",
    )
    parser.add_argument("--memory-dir", type=str, help="Override memory dir")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--skip", nargs="*", default=["MEMORY.md"], help="Filenames to skip")
    args = parser.parse_args()

    memory_dir = Path(args.memory_dir) if args.memory_dir else MEMORY_DIR
    if not memory_dir.exists():
        print(f"[ERROR] Memory dir not found: {memory_dir}")
        return 1

    if not SQLITE_DB.exists():
        print(f"[ERROR] SQLite DB not found: {SQLITE_DB}")
        return 1

    md_files = sorted([f for f in memory_dir.glob("*.md") if f.name not in args.skip])
    if not md_files:
        print(f"[INFO] No .md files in {memory_dir}")
        return 0

    print(f"[INFO] Found {len(md_files)} .md files in {memory_dir}")
    if args.dry_run:
        print("[INFO] DRY RUN — no writes to DB")

    conn = sqlite3.connect(str(SQLITE_DB), timeout=5)

    inserted = 0
    skipped = 0
    errors = 0

    for md_file in md_files:
        try:
            content = md_file.read_text(encoding="utf-8")
            chash = content_hash(content)
            fm = parse_frontmatter(content)

            if already_migrated(conn, chash):
                skipped += 1
                if args.verbose:
                    print(f"[skip] {md_file.name} — already migrated (hash={chash[:8]})")
                continue

            result = insert_row(
                conn,
                md_file.name,
                fm,
                fm["body"],
                chash,
                dry_run=args.dry_run,
            )
            inserted += 1
            if args.verbose or args.dry_run:
                if args.dry_run and result:
                    print(
                        f"[dry] would insert: {md_file.name} -> "
                        f"{result[3]} (imp={result[2]}) tags={result[4]}",
                    )
                else:
                    print(f"[ok] {md_file.name} -> inserted")
        except Exception as e:
            errors += 1
            print(f"[ERROR] {md_file.name}: {e}")

    conn.close()
    print(f"\n[SUMMARY] Inserted: {inserted}, Skipped: {skipped}, Errors: {errors}")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
