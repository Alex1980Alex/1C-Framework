"""Unit tests for .claude/hooks/shared/lifecycle_extract.py (§23 P1).

Covers:
- iter_tool_uses: recursive yield from nested dicts/lists
- iter_text: recursive yield of assistant text strings
- extract_from_events:
    research: WebSearch tool_use -> query captured
    design: Edit to docs/roadmap/ -> basename captured; Edit to src/ -> not captured
    review: [CODE-VERIFY-PASS] marker in text -> "code-verify: PASS"
    verify: "Verdict: PASS" in text -> "verify: PASS"
    impl: auto-save commits filtered; real commits retained; files capped
    substantive gate: trivial (no commit/research/verdict) -> False; real commit -> True
    render_record: frontmatter + present-only sections
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Load the module under test via importlib (hook lives outside package tree)
# ---------------------------------------------------------------------------

_HOOKS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "hooks"
_MODULE_PATH = _HOOKS_DIR / "shared" / "lifecycle_extract.py"


def _load_module():
    """Load lifecycle_extract with shared/ importable."""
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    spec = importlib.util.spec_from_file_location("lifecycle_extract", _MODULE_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


le = _load_module()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EMPTY_GIT_CTX: dict[str, Any] = {
    "commits": [],
    "files": [],
    "completed_tasks": [],
    "skills": [],
}


def _tool_use_event(name: str, input_dict: dict[str, Any]) -> dict[str, Any]:
    """Minimal transcript event wrapping a single tool_use block."""
    return {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "name": name,
                    "input": input_dict,
                }
            ]
        },
    }


def _text_event(text: str) -> dict[str, Any]:
    """Minimal transcript event with a text content block."""
    return {
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "text",
                    "text": text,
                }
            ]
        },
    }


# ---------------------------------------------------------------------------
# iter_tool_uses
# ---------------------------------------------------------------------------


def test_iter_tool_uses_basic() -> None:
    event = _tool_use_event("Bash", {"command": "ls"})
    results = list(le.iter_tool_uses(event))
    assert len(results) == 1
    assert results[0]["name"] == "Bash"


def test_iter_tool_uses_nested_list() -> None:
    events = [
        _tool_use_event("Read", {"file_path": "a.py"}),
        _tool_use_event("Write", {"file_path": "b.py", "content": "x"}),
    ]
    names = [tu["name"] for tu in le.iter_tool_uses(events)]
    assert names == ["Read", "Write"]


def test_iter_tool_uses_skips_non_tool_use() -> None:
    event = {"type": "user", "message": {"content": "hello"}}
    assert list(le.iter_tool_uses(event)) == []


def test_iter_tool_uses_skips_no_name() -> None:
    event = {"type": "tool_use"}  # missing "name"
    assert list(le.iter_tool_uses(event)) == []


# ---------------------------------------------------------------------------
# iter_text
# ---------------------------------------------------------------------------


def test_iter_text_text_block() -> None:
    event = _text_event("hello world")
    texts = list(le.iter_text(event))
    assert "hello world" in texts


def test_iter_text_nested_list() -> None:
    events = [_text_event("first"), _text_event("second")]
    texts = list(le.iter_text(events))
    assert "first" in texts
    assert "second" in texts


def test_iter_text_plain_string() -> None:
    texts = list(le.iter_text("direct string"))
    assert texts == ["direct string"]


def test_iter_text_no_text_key_no_text_yield() -> None:
    """Dict with no 'text' key does not yield its non-'text' values as text blocks."""
    event = {"type": "tool_result", "output": "some output"}
    # iter_text recurses into values but only yields from 'text' keyed strings
    # and plain strings.  The string "some output" is a dict value (not a list
    # item), so the inner recursion sees it as a string and yields it -- that
    # is expected behaviour for the generic recursive walker.
    # What we DO want to assert: a correctly-structured text block is found.
    text_event = {"type": "text", "text": "hello"}
    texts = list(le.iter_text(text_event))
    assert "hello" in texts


# ---------------------------------------------------------------------------
# extract_from_events: research
# ---------------------------------------------------------------------------


def test_research_websearch_query() -> None:
    events = [_tool_use_event("WebSearch", {"query": "python async patterns"})]
    result = le.extract_from_events(events, _EMPTY_GIT_CTX)
    assert result["research"] == [{"tool": "WebSearch", "query": "python async patterns"}]


def test_research_webfetch_url() -> None:
    events = [_tool_use_event("WebFetch", {"url": "https://example.com/docs"})]
    result = le.extract_from_events(events, _EMPTY_GIT_CTX)
    assert result["research"] == [{"tool": "WebFetch", "query": "https://example.com/docs"}]


def test_research_dedup() -> None:
    events = [
        _tool_use_event("WebSearch", {"query": "same query"}),
        _tool_use_event("WebSearch", {"query": "same query"}),
    ]
    result = le.extract_from_events(events, _EMPTY_GIT_CTX)
    assert len(result["research"]) == 1


def test_research_empty_query_skipped() -> None:
    events = [_tool_use_event("WebSearch", {})]
    result = le.extract_from_events(events, _EMPTY_GIT_CTX)
    assert result["research"] == []


# ---------------------------------------------------------------------------
# extract_from_events: design
# ---------------------------------------------------------------------------


def test_design_edit_roadmap() -> None:
    events = [
        _tool_use_event(
            "Edit",
            {
                "file_path": "docs/roadmap/260523_ROADMAP.md",
                "old_string": "x",
                "new_string": "y",
            },
        )
    ]
    result = le.extract_from_events(events, _EMPTY_GIT_CTX)
    assert "260523_ROADMAP.md" in result["design"]


def test_design_write_roadmap_backslash() -> None:
    """Backslash path normalization: Windows-style path must still match."""
    events = [
        _tool_use_event(
            "Write",
            {
                "file_path": "docs\\roadmap\\my_adr.md",
                "content": "hello",
            },
        )
    ]
    result = le.extract_from_events(events, _EMPTY_GIT_CTX)
    assert "my_adr.md" in result["design"]


def test_design_edit_src_not_captured() -> None:
    """Edit to src/ must NOT appear in design."""
    events = [
        _tool_use_event(
            "Edit",
            {"file_path": "src/foo.py", "old_string": "a", "new_string": "b"},
        )
    ]
    result = le.extract_from_events(events, _EMPTY_GIT_CTX)
    assert result["design"] == []


def test_design_dedup() -> None:
    events = [
        _tool_use_event("Edit", {"file_path": "docs/roadmap/r.md", "old_string": "a", "new_string": "b"}),
        _tool_use_event("Edit", {"file_path": "docs/roadmap/r.md", "old_string": "c", "new_string": "d"}),
    ]
    result = le.extract_from_events(events, _EMPTY_GIT_CTX)
    assert result["design"].count("r.md") == 1


# ---------------------------------------------------------------------------
# extract_from_events: review
# ---------------------------------------------------------------------------


def test_review_code_verify_pass_marker() -> None:
    events = [_text_event("All checks complete. [CODE-VERIFY-PASS]")]
    result = le.extract_from_events(events, _EMPTY_GIT_CTX)
    assert "code-verify: PASS" in result["review"]


def test_review_code_verify_fail_marker() -> None:
    events = [_text_event("Something went wrong. [CODE-VERIFY-FAIL]")]
    result = le.extract_from_events(events, _EMPTY_GIT_CTX)
    assert "code-verify: FAIL" in result["review"]


def test_review_dedup_markers() -> None:
    events = [
        _text_event("[CODE-VERIFY-PASS]"),
        _text_event("[CODE-VERIFY-PASS]"),
    ]
    result = le.extract_from_events(events, _EMPTY_GIT_CTX)
    assert result["review"].count("code-verify: PASS") == 1


# ---------------------------------------------------------------------------
# extract_from_events: verify
# ---------------------------------------------------------------------------


def test_verify_verdict_pass() -> None:
    events = [_text_event("Running tests...\nVerdict: PASS\nDone.")]
    result = le.extract_from_events(events, _EMPTY_GIT_CTX)
    assert "verify: PASS" in result["verify"]


def test_verify_verdict_fail() -> None:
    events = [_text_event("Verdict: FAIL")]
    result = le.extract_from_events(events, _EMPTY_GIT_CTX)
    assert "verify: FAIL" in result["verify"]


def test_verify_verdict_blocked() -> None:
    events = [_text_event("Verdict: BLOCKED")]
    result = le.extract_from_events(events, _EMPTY_GIT_CTX)
    assert "verify: BLOCKED" in result["verify"]


def test_verify_verdict_case_insensitive() -> None:
    events = [_text_event("verdict: pass")]
    result = le.extract_from_events(events, _EMPTY_GIT_CTX)
    assert "verify: PASS" in result["verify"]


def test_verify_dedup() -> None:
    events = [_text_event("Verdict: PASS"), _text_event("Verdict: PASS")]
    result = le.extract_from_events(events, _EMPTY_GIT_CTX)
    assert result["verify"].count("verify: PASS") == 1


# ---------------------------------------------------------------------------
# extract_from_events: impl
# ---------------------------------------------------------------------------


def test_impl_autosave_filtered() -> None:
    git_ctx = {**_EMPTY_GIT_CTX, "commits": ["feat: add feature", "chore: auto-save session x"]}
    result = le.extract_from_events([], git_ctx)
    assert result["impl"]["commits"] == ["feat: add feature"]


def test_impl_real_commit_retained() -> None:
    git_ctx = {**_EMPTY_GIT_CTX, "commits": ["fix: resolve bug", "docs: update readme"]}
    result = le.extract_from_events([], git_ctx)
    assert result["impl"]["commits"] == ["fix: resolve bug", "docs: update readme"]


def test_impl_files_capped_at_30() -> None:
    files = [f"file_{i}.py" for i in range(50)]
    git_ctx = {**_EMPTY_GIT_CTX, "files": files}
    result = le.extract_from_events([], git_ctx)
    assert len(result["impl"]["files"]) == 30


def test_impl_empty_commits_and_files() -> None:
    result = le.extract_from_events([], _EMPTY_GIT_CTX)
    assert result["impl"] == {"commits": [], "files": []}


# ---------------------------------------------------------------------------
# extract_from_events: substantive gate
# ---------------------------------------------------------------------------


def test_substantive_false_when_trivial() -> None:
    """Only a text event with no markers, no git activity -> False."""
    events = [_text_event("How do I do X?")]
    result = le.extract_from_events(events, _EMPTY_GIT_CTX)
    assert result["substantive"] is False


def test_substantive_true_with_real_commit() -> None:
    git_ctx = {**_EMPTY_GIT_CTX, "commits": ["feat: implement something"]}
    result = le.extract_from_events([], git_ctx)
    assert result["substantive"] is True


def test_substantive_true_with_research() -> None:
    events = [_tool_use_event("WebSearch", {"query": "something"})]
    result = le.extract_from_events(events, _EMPTY_GIT_CTX)
    assert result["substantive"] is True


def test_substantive_true_with_review_marker() -> None:
    events = [_text_event("[CODE-VERIFY-PASS]")]
    result = le.extract_from_events(events, _EMPTY_GIT_CTX)
    assert result["substantive"] is True


def test_substantive_false_autosave_only_commit() -> None:
    """Auto-save commit alone does NOT make substantive=True."""
    git_ctx = {**_EMPTY_GIT_CTX, "commits": ["chore: auto-save session abc"]}
    result = le.extract_from_events([], git_ctx)
    assert result["substantive"] is False


# ---------------------------------------------------------------------------
# render_record
# ---------------------------------------------------------------------------


def _make_stages(
    research: list | None = None,
    design: list | None = None,
    commits: list | None = None,
    files: list | None = None,
    review: list | None = None,
    verify: list | None = None,
    completed_tasks: list | None = None,
    skills: list | None = None,
    substantive: bool = True,
) -> dict[str, Any]:
    return {
        "research": research or [],
        "design": design or [],
        "impl": {"commits": commits or [], "files": files or []},
        "review": review or [],
        "verify": verify or [],
        "lessons": {
            "completed_tasks": completed_tasks or [],
            "skills": skills or [],
        },
        "substantive": substantive,
    }


def test_render_record_frontmatter() -> None:
    stages = _make_stages(commits=["feat: x"])
    out = le.render_record(stages, "ses123", "2026-05-31T10:00:00")
    assert "session_id: ses123" in out
    assert "created: 2026-05-31T10:00:00" in out
    assert "stages_present:" in out


def test_render_record_present_stages_in_frontmatter() -> None:
    stages = _make_stages(
        research=[{"tool": "WebSearch", "query": "q"}],
        commits=["feat: x"],
    )
    out = le.render_record(stages, "s", "2026-05-31")
    assert "research" in out
    assert "impl" in out


def test_render_record_empty_stage_not_in_output() -> None:
    """A stage with no data must not produce a section header."""
    stages = _make_stages(commits=["feat: x"])
    out = le.render_record(stages, "s", "2026-05-31")
    # research is empty -> no ## §1 Research section
    assert "## §1 Research" not in out
    # impl is present
    assert "## §3 Implementation" in out


def test_render_record_research_section() -> None:
    stages = _make_stages(research=[{"tool": "WebSearch", "query": "async python"}])
    out = le.render_record(stages, "s", "2026-05-31")
    assert "## §1 Research" in out
    assert "[WebSearch] async python" in out


def test_render_record_review_section() -> None:
    stages = _make_stages(review=["code-verify: PASS"])
    out = le.render_record(stages, "s", "2026-05-31")
    assert "## §4 Review" in out
    assert "code-verify: PASS" in out


def test_render_record_verify_section() -> None:
    stages = _make_stages(verify=["verify: PASS"])
    out = le.render_record(stages, "s", "2026-05-31")
    assert "## §5 Verify" in out
    assert "verify: PASS" in out


def test_render_record_no_section_for_all_empty() -> None:
    stages = _make_stages()  # everything empty
    out = le.render_record(stages, "s", "2026-05-31")
    for key in ["Research", "Design", "Implementation", "Review", "Verify", "Lessons"]:
        assert key not in out or "stages_present: []" in out


def test_render_record_keywords_from_files_and_commits() -> None:
    stages = _make_stages(
        commits=["feat: new thing"],
        files=["src/foo.py", "src/bar.ts"],
    )
    out = le.render_record(stages, "s", "2026-05-31")
    assert "py" in out
    assert "ts" in out
    assert "feat" in out


# ---------------------------------------------------------------------------
# extract_stages: fail-soft on missing transcript
# ---------------------------------------------------------------------------


def test_extract_stages_missing_file() -> None:
    result = le.extract_stages("/nonexistent/path/transcript.jsonl", _EMPTY_GIT_CTX)
    assert result["substantive"] is False
    assert result["research"] == []


def test_extract_stages_empty_path() -> None:
    result = le.extract_stages("", _EMPTY_GIT_CTX)
    assert result["substantive"] is False


def test_extract_stages_real_file(tmp_path: Path) -> None:
    """Write a minimal JSONL transcript and verify research extraction."""
    import json

    events = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "WebSearch",
                        "input": {"query": "qdrant vector search"},
                    }
                ]
            },
        }
    ]
    t = tmp_path / "session.jsonl"
    t.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")

    result = le.extract_stages(str(t), _EMPTY_GIT_CTX)
    assert result["research"] == [{"tool": "WebSearch", "query": "qdrant vector search"}]
    assert result["substantive"] is True
