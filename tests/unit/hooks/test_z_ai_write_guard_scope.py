"""z-ai-write-guard must police shipped code only.

2026-07-17: the guard blocked a throwaway line-index script under the session scratchpad
(Temp/claude/**/scratchpad/), which lives outside the repo and so matched no entry in
_EXEMPT_PREFIXES. Delegating a one-shot byte-precise edit script to Z.AI costs a
round-trip and a review for code that is deleted minutes later — the same reason tests/
is already exempt. Product code must still be blocked.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[3]
_HOOK = _ROOT / ".claude" / "hooks" / "z-ai-write-guard.py"
_PY = _ROOT / ".venv" / "Scripts" / "python.exe"
_BIG = "\n".join(f"x = {i}" for i in range(30))  # > _LINE_THRESHOLD


def _load():
    spec = importlib.util.spec_from_file_location("zai_guard", _HOOK)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _blocked(file_path: str) -> bool:
    """Drive the hook end-to-end; True when it emits the block."""
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": _BIG},
    }
    r = subprocess.run(
        [str(_PY), str(_HOOK)],
        input=json.dumps(payload),  # json.dumps, NOT shell interpolation: raw newlines
        capture_output=True,        # make the payload invalid and the hook degrades to
        text=True,                  # allow, which silently passes any assertion
        encoding="utf-8",
    )
    return "WRITE GUARD" in (r.stdout + r.stderr)


def test_threshold_constant_still_meaningful() -> None:
    mod = _load()
    assert _BIG.count("\n") + 1 > mod._LINE_THRESHOLD, "fixture must exceed the threshold"


@pytest.mark.skipif(not _PY.exists(), reason=".venv python required")
def test_product_code_is_blocked() -> None:
    assert _blocked(str(_ROOT / "src" / "pdf_framework" / "zzz_guard_probe.py"))


@pytest.mark.skipif(not _PY.exists(), reason=".venv python required")
def test_scratchpad_outside_repo_is_exempt() -> None:
    outside = "C:/Users/T/AppData/Local/Temp/claude/P/sess/scratchpad/tool.py"
    assert not _blocked(outside)


@pytest.mark.skipif(not _PY.exists(), reason=".venv python required")
@pytest.mark.parametrize("rel", ["tests/unit/probe.py", ".claude/hooks/probe.py"])
def test_existing_exemptions_survive(rel: str) -> None:
    assert not _blocked(str(_ROOT / rel))
