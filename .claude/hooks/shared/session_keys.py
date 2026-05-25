"""Per-session symmetric key management for crypto-shredding (§15 P0 P0.4).

Stores one AES-256 key per Claude Code session_id. Key erasure (delete)
makes all ciphertext encrypted with that key unrecoverable — this is the
GDPR retention mechanism per roadmap 260523 §15.2 item 7 + §15.5
"crypto-shredding critical urgency".

Storage layout:
    ~/.claude/projects/<project>/keys/<session_id>.key (32 bytes binary)

The directory is per-project (matches existing MEMORY.md layout) so that
keys don't leak between projects on the same machine. File perms set to
0o600 on POSIX; Windows uses standard NTFS ACLs from parent dir.

Public API:
    get_or_create_key(session_id) -> bytes (32 bytes, AES-256)
    delete_key(session_id) -> bool (True if existed and deleted)
    list_keys() -> list[dict] (session_id, age_days, size)
    gc_old_keys(days: int) -> int (count deleted)

Graceful: any I/O error → returns None / False (never raises). Encryption
becomes a no-op when key unavailable (crypto_shred.encrypt returns None).

Per roadmap 260523 §15.6 P0 item 4.
"""

from __future__ import annotations

import datetime as dt
import os
import secrets
from pathlib import Path

KEY_SIZE_BYTES = 32  # AES-256


def _project_slug() -> str:
    """Derive project slug matching Claude Code's `~/.claude/projects/<slug>/` layout.

    Claude Code replaces all non-[A-Za-z0-9_-] chars (including Cyrillic letters,
    drive colons, path separators) with `-`. Example:

        "C:\\1С-Framework"  →  "C--1--Framework"

    Path arithmetic: session_keys.py lives at `.claude/hooks/shared/session_keys.py`
    — four levels deep from project root.
    """
    # shared → hooks → .claude → project root
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    raw = str(project_root)
    out: list[str] = []
    for ch in raw:
        if ch.isascii() and (ch.isalnum() or ch in "-_"):
            out.append(ch)
        else:
            out.append("-")
    return "".join(out).strip("-") or "default"


def _keys_dir() -> Path:
    """Directory containing per-session key files. Created on demand."""
    home = Path.home()
    return home / ".claude" / "projects" / _project_slug() / "keys"


def _key_path(session_id: str) -> Path:
    """Path to one session's key file.

    session_id может содержать unsafe chars — sanitize до alphanumeric+hyphen.
    """
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in session_id)[:64]
    if not safe:
        safe = "default"
    return _keys_dir() / f"{safe}.key"


def get_or_create_key(session_id: str) -> bytes | None:
    """Return existing key for session or create new one.

    Returns None on I/O failure (caller treats as "encryption unavailable").
    """
    if not session_id:
        return None
    try:
        keys_dir = _keys_dir()
        keys_dir.mkdir(parents=True, exist_ok=True)
        path = _key_path(session_id)
        if path.exists():
            data = path.read_bytes()
            if len(data) == KEY_SIZE_BYTES:
                return data
            # Corrupted — regenerate
        key = secrets.token_bytes(KEY_SIZE_BYTES)
        path.write_bytes(key)
        # POSIX: tighten perms (no-op on Windows; standard NTFS ACL inherits)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return key
    except OSError:
        return None


def delete_key(session_id: str) -> bool:
    """Delete the key for session_id (irreversible erasure).

    Returns True if file existed and was deleted. After this, any
    ciphertext encrypted with this key becomes permanently unreadable
    (crypto-shredding per §15.2 item 7).
    """
    if not session_id:
        return False
    try:
        path = _key_path(session_id)
        if path.exists():
            path.unlink()
            return True
    except OSError:
        pass
    return False


def list_keys() -> list[dict]:
    """Return metadata for all stored session keys."""
    out: list[dict] = []
    keys_dir = _keys_dir()
    if not keys_dir.exists():
        return out
    now = dt.datetime.now()
    try:
        for path in keys_dir.iterdir():
            if not path.is_file() or path.suffix != ".key":
                continue
            try:
                stat = path.stat()
                mtime = dt.datetime.fromtimestamp(stat.st_mtime)
                age_days = (now - mtime).days
                out.append(
                    {
                        "session_id": path.stem,
                        "age_days": age_days,
                        "size_bytes": stat.st_size,
                        "path": str(path),
                    }
                )
            except OSError:
                continue
    except OSError:
        return out
    out.sort(key=lambda d: d["age_days"], reverse=True)
    return out


def gc_old_keys(days: int) -> int:
    """Delete keys older than `days`. Returns count of deleted."""
    if days <= 0:
        return 0
    count = 0
    now = dt.datetime.now().timestamp()
    cutoff = now - days * 86400
    keys_dir = _keys_dir()
    if not keys_dir.exists():
        return 0
    try:
        for path in keys_dir.iterdir():
            if not path.is_file() or path.suffix != ".key":
                continue
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink()
                    count += 1
            except OSError:
                continue
    except OSError:
        pass
    return count
