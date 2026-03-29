#!/usr/bin/env python3
# CANARY: PostToolUse matcher matrix test. DELETE after testing.
try:
    from pathlib import Path as _P
    from datetime import datetime as _DT
    import sys as _S, json as _J
    _stdin = _S.stdin.buffer.read().decode("utf-8", errors="replace")[:1000]
    _data = _J.loads(_stdin) if _stdin.strip() else {}
    _tool = _data.get("tool_name", "unknown")
    _event = _data.get("hook_event_name", "unknown")
    _has_response = "tool_response" in _data
    _log = _P(__file__).resolve().parent.parent / "cache" / "canary-matrix.log"
    _log.parent.mkdir(parents=True, exist_ok=True)
    with open(_log, "a", encoding="utf-8") as _f:
        _f.write(f"{_DT.now().isoformat()} | event={_event} | tool={_tool} | has_response={_has_response} | stdin_len={len(_stdin)}\n")
except Exception as _e:
    try:
        _P(__file__).resolve().parent.parent.joinpath("cache","canary-matrix-error.log").open("a").write(f"{_e}\n")
    except: pass
