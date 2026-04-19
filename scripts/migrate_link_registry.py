"""Migrate link_registry.db to support new link types.

Adds promoted_to, superseded_by, mirrors, graph_node to the CHECK constraint.
Uses CREATE NEW + COPY DATA + DROP OLD pattern (SQLite limitation).

Usage:
    python scripts/migrate_link_registry.py --dry-run
    python scripts/migrate_link_registry.py --apply
    python scripts/migrate_link_registry.py --rollback
"""

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "link_registry.db"
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"

OLD_TYPES = {"based_on", "supports", "contradicts", "extends", "derives_from", "session_context"}
NEW_TYPES = OLD_TYPES | {"promoted_to", "superseded_by", "mirrors", "graph_node"}


def get_current_version(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT value FROM schema_info WHERE key = 'version'").fetchone()
        return int(row[0]) if row else 0
    except sqlite3.OperationalError:
        return 0
    finally:
        conn.close()


def count_links(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT COUNT(*) FROM entity_links").fetchone()
        return row[0]
    finally:
        conn.close()


def count_new_type_links(db_path: str) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    try:
        counts = {}
        for lt in NEW_TYPES - OLD_TYPES:
            row = conn.execute(
                "SELECT COUNT(*) FROM entity_links WHERE link_type = ?", (lt,)
            ).fetchone()
            counts[lt] = row[0]
        return counts
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()


def dry_run(db_path: str):
    if not db_path.exists():
        print(f"SKIP: {db_path} does not exist")
        return

    version = get_current_version(str(db_path))
    total = count_links(str(db_path))
    new_type_links = count_new_type_links(str(db_path))

    print(f"Database: {db_path}")
    print(f"Current schema version: {version}")
    print(f"Total links: {total}")

    if version >= 2:
        print("Already migrated (version >= 2). No action needed.")
        return

    print(f"\nDry-run: would migrate to version 2")
    print(f"New link types to be added: {', '.join(sorted(NEW_TYPES - OLD_TYPES))}")
    if new_type_links:
        print(f"WARNING: Found links with new types (should be 0 before migration):")
        for lt, cnt in new_type_links.items():
            if cnt > 0:
                print(f"  {lt}: {cnt}")

    print(f"\nAll {total} existing links will be preserved.")
    print("Run with --apply to execute.")


def apply_migration(db_path: str):
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist")
        sys.exit(1)

    version = get_current_version(str(db_path))
    if version >= 2:
        print(f"Already at version {version}. Nothing to do.")
        return

    backup_path = db_path.with_suffix(".db.backup-pre-migration")
    shutil.copy2(db_path, backup_path)
    print(f"Backup: {backup_path}")

    sql_path = MIGRATIONS_DIR / "001_extend_link_types.sql"
    sql = sql_path.read_text(encoding="utf-8")

    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(sql)
        print(f"Migration applied. New version: {get_current_version(str(db_path))}")
    except Exception as e:
        conn.close()
        print(f"ERROR: Migration failed: {e}")
        print(f"Restoring from backup...")
        shutil.copy2(backup_path, db_path)
        print("Restored.")
        sys.exit(1)
    finally:
        conn.close()


def rollback(db_path: str):
    if not db_path.exists():
        print(f"ERROR: {db_path} does not exist")
        sys.exit(1)

    version = get_current_version(str(db_path))
    if version < 2:
        print(f"Already at version {version}. Nothing to rollback.")
        return

    backup_path = db_path.with_suffix(".db.backup-pre-migration")
    shutil.copy2(db_path, backup_path)
    print(f"Backup: {backup_path}")

    new_type_links = count_new_type_links(str(db_path))
    has_new = any(c > 0 for c in new_type_links.values())
    if has_new:
        print("WARNING: Links using new types will be DELETED:")
        for lt, cnt in new_type_links.items():
            if cnt > 0:
                print(f"  {lt}: {cnt}")

    sql_path = MIGRATIONS_DIR / "001_rollback.sql"
    sql = sql_path.read_text(encoding="utf-8")

    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(sql)
        print(f"Rollback applied. Version: {get_current_version(str(db_path))}")
    except Exception as e:
        conn.close()
        print(f"ERROR: Rollback failed: {e}")
        print(f"Restoring from backup...")
        shutil.copy2(backup_path, db_path)
        print("Restored.")
        sys.exit(1)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Migrate link_registry.db")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="Preview migration without applying")
    group.add_argument("--apply", action="store_true", help="Apply migration")
    group.add_argument("--rollback", action="store_true", help="Rollback to previous version")
    args = parser.parse_args()

    if args.dry_run:
        dry_run(DB_PATH)
    elif args.apply:
        apply_migration(DB_PATH)
    elif args.rollback:
        rollback(DB_PATH)


if __name__ == "__main__":
    main()
