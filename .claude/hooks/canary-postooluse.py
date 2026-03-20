#!/usr/bin/env python3
"""Canary: does PostToolUse fire on v2.1.80? Delete after testing."""
try:
    from pathlib import Path as _P
    from datetime import datetime as _DT
    import sys

    _canary = _P(__file__).resolve().parent.parent / "cache" / "canary-posttooluse.txt"
    _canary.parent.mkdir(parents=True, exist_ok=True)

    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    _canary.write_text(
        f"FIRED {_DT.now().isoformat()}\nSTDIN_LEN={len(raw)}\nSTDIN={raw[:500]}\n",
        encoding="utf-8",
    )
except Exception as e:
    try:
        _canary.write_text(f"ERROR {e}\n", encoding="utf-8")
    except Exception:
        pass
