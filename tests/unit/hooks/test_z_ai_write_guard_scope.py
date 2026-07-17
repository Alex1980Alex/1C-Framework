"""z-ai-write-guard must police shipped code only — and must still police it.

2026-07-17, two exemptions added and reviewed:
  1. Paths outside the repo root. The guard blocked a throwaway line-index script under
     the session scratchpad (Temp/claude/**/scratchpad/), which matches no
     _EXEMPT_PREFIXES. Delegating a one-shot byte-precise edit costs a round-trip and a
     review for code deleted minutes later — the reason tests/ is already exempt.
  2. pipeline/ for large .md. ADR-018 (pipeline-protocol-stop) hard-blocks completion
     without pipeline/<slug>/*.md, while this guard forbade writing them (>50-line .md
     outside .claude/). Two enforcers, one demanding what the other refused.

Both must stay NARROW, which is what most of this file pins: the first review round put
"pipeline/" into _EXEMPT_PREFIXES too, and since those match as substrings it silently
exempted infra/pipeline/**/*.py — 127 tracked product files.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[3]
_HOOK = _ROOT / ".claude" / "hooks" / "z-ai-write-guard.py"
_BIG = "\n".join(f"x = {i}" for i in range(30))  # > _LINE_THRESHOLD
_MD = "\n".join(f"line {i}" for i in range(60))  # > _LARGE_MD_THRESHOLD


def _blocked(file_path: str, body: str = _BIG, *, tmp_path: Path) -> bool:
    """Drive the hook end-to-end; True when it emits the block.

    Runs under sys.executable, NOT .venv/Scripts/python.exe: that path only exists on
    Windows, so a skipif on it turned this whole file into a silent no-op on CI's ubuntu
    runner — the guard could regress with master green.

    CLAUDE_CACHE_DIR / session state are redirected at a tmp dir: the hook consults live
    SessionState.has_llm_delegation() and is_provider_down(), so one real llm_complete
    during the session would flip every negative assertion here to vacuously true.
    """
    payload = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": body},
    }
    env = {
        **dict(__import__("os").environ),
        "CLAUDE_CACHE_DIR": str(tmp_path),
        "CLAUDE_SESSION_STATE_PATH": str(tmp_path / "session-skills.json"),
    }
    r = subprocess.run(
        [sys.executable, str(_HOOK)],
        input=json.dumps(payload),  # json.dumps, not shell interpolation: raw newlines
        capture_output=True,  # would make the payload invalid and the hook degrade to
        text=True,  # allow, passing every assertion for the wrong reason
        encoding="utf-8",
        env=env,
    )
    return "WRITE GUARD" in (r.stdout + r.stderr)


def _const(name: str) -> int:
    """Read a threshold from source — importing the hook would insert .claude/hooks at
    sys.path[0] for the rest of the session ([[feedback-hook-src-shared-collision]])."""
    # \s* — _LARGE_MD_THRESHOLD lives inside execute(), not at module level
    m = re.search(rf"^\s*{name} = (\d+)", _HOOK.read_text(encoding="utf-8"), re.M)
    assert m, f"{name} not found — guard restructured?"
    return int(m.group(1))


def test_fixtures_exceed_the_thresholds() -> None:
    """Anchors the harness: if the fixtures stopped tripping the guard, every
    'not blocked' assertion below would pass for the wrong reason."""
    assert _BIG.count("\n") + 1 > _const("_LINE_THRESHOLD")
    assert _MD.count("\n") + 1 > _const("_LARGE_MD_THRESHOLD")


def test_product_code_is_blocked(tmp_path: Path) -> None:
    assert _blocked(str(_ROOT / "src" / "pdf_framework" / "zzz_probe.py"), tmp_path=tmp_path)


def test_large_docs_md_still_enforced(tmp_path: Path) -> None:
    """The .md exemption must stay narrow: long prose under docs/ is delegatable."""
    assert _blocked(str(_ROOT / "docs" / "zzz_probe.md"), _MD, tmp_path=tmp_path)


def test_scratchpad_outside_repo_is_exempt(tmp_path: Path) -> None:
    outside = "C:/Users/T/AppData/Local/Temp/claude/P/sess/scratchpad/tool.py"
    assert not _blocked(outside, tmp_path=tmp_path)


def test_pipeline_artefacts_are_exempt(tmp_path: Path) -> None:
    """ADR-018 makes these mandatory; blocking them deadlocks against pipeline-protocol-stop."""
    assert not _blocked(
        str(_ROOT / "pipeline" / "slug" / "01-architecture.md"), _MD, tmp_path=tmp_path
    )


@pytest.mark.parametrize("rel", ["tests/unit/probe.py", ".claude/hooks/probe.py"])
def test_existing_exemptions_survive(rel: str, tmp_path: Path) -> None:
    assert not _blocked(str(_ROOT / rel), tmp_path=tmp_path)


def test_pipeline_exemption_does_not_leak_to_nested_product_code(tmp_path: Path) -> None:
    """_EXEMPT_PREFIXES match as substrings, so a bare "pipeline/" entry would exempt
    infra/pipeline/**/*.py (127 tracked files). The .md exemption must not reach code."""
    assert _blocked(
        str(_ROOT / "infra" / "pipeline" / "orchestrator" / "zzz.py"), tmp_path=tmp_path
    )


def test_pipeline_md_exemption_is_anchored_to_the_artefact_tree(tmp_path: Path) -> None:
    """A large .md merely *named* pipeline elsewhere is still delegatable prose."""
    assert _blocked(str(_ROOT / "docs" / "guides" / "zzz_probe.md"), _MD, tmp_path=tmp_path)


def test_oserror_branch_is_fail_closed_by_source() -> None:
    """The `except OSError: pass` (unknown → keep enforcing) has no behavioural test.

    Reaching it needs resolve() to raise, which a normal path never does, and the hook
    runs in a subprocess so it cannot be monkeypatched from here. Sabotaging it to
    `return None` leaves every other test green — i.e. nothing pins it. This asserts the
    source shape instead: weak, but honest about being a source check, and it does catch
    the one regression that matters (silently turning the unknown into a bypass).
    """
    src = _HOOK.read_text(encoding="utf-8")
    assert "except ValueError:\n            return None" in src, "provably-outside must exempt"
    assert "except OSError:\n            pass" in src, "could-not-tell must keep enforcing"
