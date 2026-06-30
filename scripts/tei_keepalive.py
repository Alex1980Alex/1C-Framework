#!/usr/bin/env python3
"""
tei_keepalive.py — periodic warm-up pinger for the TEI embedder (pdf-rag-tei).

Keeps the embedding path hot so memory-first-hook / prework-similar-code don't pay
cold-start latency (TEI cold ~400-600ms vs warm ~80ms — see memory-first-hook header).
Sends a tiny 1-token POST /embed every INTERVAL seconds. Best-effort: any error is
swallowed and the loop continues (TEI down → keeps retrying cheaply).

Single-instance via a heartbeat lockfile (.claude/cache/tei-keepalive.lock): if a live
instance is heartbeating (last beat < 2*interval ago), a new launch exits immediately —
so repeated SessionStarts never stack duplicate daemons. Bounded lifetime (DURATION) so
the daemon can never become a permanent orphan; the SessionStart hook respawns it.

Usage:
  python scripts/tei_keepalive.py [--interval 240] [--duration 21600] [--once]

  --once  single warm-up ping then exit (no loop, no lock).

Env:
  TEI_KEEPALIVE_DISABLE=1  → no-op (exit immediately)
  TEI_URL                  → base URL (default http://localhost:8080); "/embed" appended
  TEI_KEEPALIVE_INTERVAL   → seconds between pings (default 240; floored at 30)
  TEI_KEEPALIVE_DURATION   → total run seconds (default 21600 = 6h)
"""

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCK = PROJECT_ROOT / ".claude" / "cache" / "tei-keepalive.lock"
TEI_URL = os.environ.get("TEI_URL", "http://localhost:8080").rstrip("/") + "/embed"


def _ping(timeout: float = 5.0) -> bool:
    """One tiny /embed call. Returns True on HTTP 200, False on any failure."""
    data = json.dumps({"inputs": "warmup", "truncate": True}).encode("utf-8")
    req = urllib.request.Request(TEI_URL, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read(64)
            return getattr(r, "status", 200) == 200
    except Exception:
        return False


def _read_lock() -> dict | None:
    try:
        return json.loads(LOCK.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_lock(pid: int, started: float, heartbeat: float) -> bool:
    try:
        LOCK.parent.mkdir(parents=True, exist_ok=True)
        tmp = LOCK.with_suffix(".lock.tmp")
        tmp.write_text(
            json.dumps({"pid": pid, "started": started, "heartbeat": heartbeat}),
            encoding="utf-8",
        )
        os.replace(tmp, LOCK)
        return True
    except OSError:
        return False


def main() -> int:
    if os.environ.get("TEI_KEEPALIVE_DISABLE") == "1":
        return 0

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--interval",
        type=float,
        default=float(os.environ.get("TEI_KEEPALIVE_INTERVAL", "240")),
    )
    ap.add_argument(
        "--duration",
        type=float,
        default=float(os.environ.get("TEI_KEEPALIVE_DURATION", "21600")),
    )
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()

    if a.once:
        _ping()
        return 0

    interval = max(30.0, a.interval)
    pid = os.getpid()
    start = time.time()

    # single-instance guard: a fresh heartbeat means another daemon is alive → bail.
    existing = _read_lock()
    if existing:
        hb = existing.get("heartbeat", 0)
        if isinstance(hb, (int, float)) and (time.time() - hb) < (2 * interval):
            return 0

    if not _write_lock(pid, start, time.time()):
        return 0

    deadline = start + max(interval, a.duration)
    while time.time() < deadline:
        _ping()
        # bail if another instance took over the lock; else refresh our heartbeat.
        cur = _read_lock()
        if cur and cur.get("pid") != pid:
            return 0
        _write_lock(pid, start, time.time())
        time.sleep(interval)

    # release our lock on clean exit (only if still ours)
    cur = _read_lock()
    if cur and cur.get("pid") == pid:
        try:
            LOCK.unlink()
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
