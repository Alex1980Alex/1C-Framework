#!/usr/bin/env python3
"""CLI for crypto-shredding session keys (§15 P0 P0.4 erasure operation).

Operations:
- --session-id <id>   Delete one session key (one-way erasure)
- --list              List all stored keys with age
- --gc <days>         Delete keys older than N days
- --decrypt-error <session_id> <enc_blob>
                      Decrypt one error envelope (debugging helper)

Per roadmap 260523 §15.5: "Crypto-shredding в первой итерации.
Immutability работает против нас — каждый день задержки = new plaintext
events которые нельзя ретроактивно зашифровать."

Usage examples:
    # Delete one session's key (erasure)
    python scripts/shred_session.py --session-id abc-123-def

    # List all keys, see what's stored
    python scripts/shred_session.py --list

    # GC keys older than 90 days (GDPR retention)
    python scripts/shred_session.py --gc 90

    # Decrypt one error blob (debugging, requires key still present)
    python scripts/shred_session.py --decrypt-error abc-123 'enc::Bcv...'
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS_DIR))

from shared.crypto_shred import decrypt
from shared.session_keys import (
    delete_key,
    gc_old_keys,
    get_existing_key,
    list_keys,
)


def cmd_delete(session_id: str) -> int:
    """Erase one session key. After this all error_enc with this key dead."""
    ok = delete_key(session_id)
    if ok:
        print(f"Deleted key for session: {session_id}")
        print(
            "Note: all `error_enc` fields encrypted with this key are now permanently unreadable."
        )
        return 0
    print(f"No key found for session: {session_id}")
    return 1


def cmd_list() -> int:
    """Show all stored keys."""
    keys = list_keys()
    if not keys:
        print("No session keys stored.")
        return 0
    print(f"{'session_id':<48} {'age_days':>8}  {'size':>5}")
    print("-" * 70)
    for k in keys:
        print(f"{k['session_id']:<48} {k['age_days']:>8}  {k['size_bytes']:>5}")
    print(f"\nTotal: {len(keys)} keys")
    return 0


def cmd_gc(days: int) -> int:
    """Delete keys older than `days`."""
    if days <= 0:
        print("ERROR: --gc requires positive integer (use --session-id для wipe one).")
        return 1
    n = gc_old_keys(days=days)
    print(f"GC: deleted {n} keys older than {days} days.")
    return 0


def cmd_decrypt(session_id: str, blob: str) -> int:
    """Debug helper: decrypt one error envelope (requires session key).

    Uses `get_existing_key` (read-only) — does NOT create a new key if the
    session has been shredded, which would otherwise leak a phantom key file.
    """
    key = get_existing_key(session_id)
    if not key:
        print(f"No key available for session: {session_id} (missing or shredded)")
        return 1
    pt = decrypt(blob, key)
    if pt is None:
        print(f"Decryption FAILED (wrong key, malformed blob, or already shredded)")
        return 2
    print(f"Decrypted: {pt}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--session-id", help="Delete one session's key")
    group.add_argument("--list", action="store_true", help="List all stored keys")
    group.add_argument("--gc", type=int, metavar="DAYS", help="Delete keys older than N days")
    group.add_argument(
        "--decrypt-error",
        nargs=2,
        metavar=("SESSION_ID", "BLOB"),
        help="Decrypt one error envelope (debugging)",
    )
    args = parser.parse_args()

    if args.list:
        return cmd_list()
    if args.gc is not None:
        return cmd_gc(args.gc)
    if args.session_id:
        return cmd_delete(args.session_id)
    if args.decrypt_error:
        return cmd_decrypt(args.decrypt_error[0], args.decrypt_error[1])
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
