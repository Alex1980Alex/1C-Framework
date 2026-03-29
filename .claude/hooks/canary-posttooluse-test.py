#!/usr/bin/env python3
# === CANARY TEST: PostToolUse v2.1.87 ===
# Temporary diagnostic - writes file BEFORE any imports to prove process starts
# DELETE after test
try:
    from pathlib import Path as _P
    from datetime import datetime as _DT
    import sys as _S
    _canary = _P(__file__).resolve().parent.parent / "cache" / "canary-posttooluse.txt"
    _canary.parent.mkdir(parents=True, exist_ok=True)
    _stdin = ""
    try:
        _stdin = _S.stdin.buffer.read().decode("utf-8", errors="replace")[:500]
    except Exception:
        _stdin = "STDIN_READ_FAILED"
    _canary.write_text(
        f"CANARY PostToolUse {_DT.now().isoformat()}\n"
        f"Python: {_S.version}\n"
        f"stdin: {_stdin}\n",
        encoding="utf-8"
    )
except Exception as _e:
    try:
        from pathlib import Path as _P2
        _P2(__file__).resolve().parent.parent.joinpath(
            "cache", "canary-posttooluse-error.txt"
        ).write_text(str(_e))
    except Exception:
        pass
# === END CANARY ===
