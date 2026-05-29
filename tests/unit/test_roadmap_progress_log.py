"""Unit tests for scripts/roadmap_progress_log.py (§18 Progress Log tooling).

Covers pure functions: section extraction, entry parsing, structural validation,
append-only freshness verdict, skeleton build + insertion. Git-free, marker `unit`.
"""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "roadmap_progress_log.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("roadmap_progress_log", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rpl = _load_module()

# Minimal roadmap fixture with a heading-based §18 and a following §19.
_DOC = """# Roadmap

## §17 Decisions

text

## §18 Implementation Progress Log (live)

**Updated manually.** Reverse chronological.

### 2026-05-29 — newest entry

body a

### 2026-05-28 — older entry

body b

## §19 Auto-update protocol

protocol text
"""


# ── extract_section_18 ────────────────────────────────────────────────────────


def test_extract_section_found_and_bounded():
    sec = rpl.extract_section_18(_DOC)
    assert sec is not None
    assert sec.startswith("## §18")
    assert "newest entry" in sec
    # Must stop before §19.
    assert "Auto-update protocol" not in sec
    assert "§17 Decisions" not in sec


def test_extract_section_absent():
    assert rpl.extract_section_18("# Roadmap\n\n## §1 Scope\n\ntext") is None


def test_extract_section_runs_to_eof_when_no_next():
    doc = "## §18 Progress\n\n### 2026-01-01 — x\n\nbody"
    sec = rpl.extract_section_18(doc)
    assert sec is not None and sec.endswith("body")


# ── parse_entries ─────────────────────────────────────────────────────────────


def test_parse_entries_multiple():
    entries = rpl.parse_entries(rpl.extract_section_18(_DOC))
    assert [d for d, _ in entries] == ["2026-05-29", "2026-05-28"]
    assert entries[0][1] == "— newest entry"


def test_parse_entries_with_suffix():
    sec = "## §18 x\n\n### 2026-05-29 (ночь) — title here\n\nbody"
    assert rpl.parse_entries(sec) == [("2026-05-29", "(ночь) — title here")]


def test_parse_entries_empty():
    assert rpl.parse_entries("## §18 x\n\nno dated entries") == []


# ── validate_structure ────────────────────────────────────────────────────────


def test_validate_ok():
    sec = rpl.extract_section_18(_DOC)
    assert rpl.validate_structure(sec, date(2026, 5, 30)) == []


def test_validate_no_entries():
    problems = rpl.validate_structure("## §18 x\n\nnothing", date(2026, 5, 30))
    assert any("no dated" in p for p in problems)


def test_validate_invalid_calendar_date():
    sec = "## §18 x\n\n### 2026-13-45 — bad\n\nbody"
    problems = rpl.validate_structure(sec, date(2026, 5, 30))
    assert any("invalid calendar date" in p for p in problems)


def test_validate_future_date():
    sec = "## §18 x\n\n### 2027-01-01 — future\n\nbody"
    problems = rpl.validate_structure(sec, date(2026, 5, 30))
    assert any("future-dated" in p for p in problems)


def test_validate_future_within_skew_ok():
    # +2 days skew tolerated.
    sec = "## §18 x\n\n### 2026-06-01 — slight future\n\nbody"
    assert rpl.validate_structure(sec, date(2026, 5, 30)) == []


def test_validate_not_reverse_chronological():
    sec = "## §18 x\n\n### 2026-05-28 — older first\n\nb\n\n### 2026-05-29 — newer below\n\nb"
    problems = rpl.validate_structure(sec, date(2026, 5, 30))
    assert any("reverse-chronological" in p for p in problems)


def test_validate_same_day_entries_ok():
    sec = "## §18 x\n\n### 2026-05-29 — a\n\nb\n\n### 2026-05-29 — b\n\nb"
    assert rpl.validate_structure(sec, date(2026, 5, 30)) == []


# ── freshness_problem (append-only) ────────────────────────────────────────────


def test_freshness_unchanged_ok():
    assert rpl.freshness_problem(_DOC, _DOC) is None


def test_freshness_new_entry_ok():
    head = _DOC.replace(
        "### 2026-05-29 — newest entry",
        "### 2026-05-30 — brand new\n\nfresh body\n\n### 2026-05-29 — newest entry",
    )
    assert rpl.freshness_problem(_DOC, head) is None


def test_freshness_same_day_second_entry_ok():
    head = _DOC.replace(
        "### 2026-05-29 — newest entry",
        "### 2026-05-29 — second same day\n\nx\n\n### 2026-05-29 — newest entry",
    )
    assert rpl.freshness_problem(_DOC, head) is None


def test_freshness_edit_without_new_entry_fails():
    # Body edited, no new dated entry → append-only violation.
    head = _DOC.replace("body a", "body a EDITED IN PLACE")
    problem = rpl.freshness_problem(_DOC, head)
    assert problem is not None and "append-only" in problem


def test_freshness_date_rename_fails():
    # Rename an existing entry's date in-place (history rewrite) → a base heading
    # disappears → must FAIL (heading-based detector, reviewer finding #1).
    head = _DOC.replace("### 2026-05-28 — older entry", "### 2026-05-27 — older entry")
    problem = rpl.freshness_problem(_DOC, head)
    assert problem is not None


def test_freshness_title_edit_without_new_entry_fails():
    # Editing an existing entry's title (heading changes, none added) → FAIL.
    head = _DOC.replace("### 2026-05-29 — newest entry", "### 2026-05-29 — RETITLED entry")
    problem = rpl.freshness_problem(_DOC, head)
    assert problem is not None


def test_freshness_new_section_ok():
    base = "# Roadmap\n\n## §1 Scope\n\nno log yet"
    assert rpl.freshness_problem(base, _DOC) is None


def test_freshness_head_without_section_ok():
    head = "# Roadmap\n\n## §1 Scope\n\nno log"
    assert rpl.freshness_problem(_DOC, head) is None


# ── build_skeleton + insert_entry ──────────────────────────────────────────────


def test_build_skeleton_with_pr():
    s = rpl.build_skeleton("2026-05-29", "my summary", pr="99")
    assert s.startswith("### 2026-05-29 — my summary")
    assert "pull/99" in s
    assert "TODO" in s


def test_build_skeleton_without_pr():
    s = rpl.build_skeleton("2026-05-29", "no pr")
    assert "pull/" not in s


def test_insert_entry_before_first_entry():
    skeleton = rpl.build_skeleton("2026-05-30", "inserted")
    out = rpl.insert_entry(_DOC, skeleton)
    sec = rpl.extract_section_18(out)
    dates = [d for d, _ in rpl.parse_entries(sec)]
    # New entry must be first (reverse-chrono top).
    assert dates == ["2026-05-30", "2026-05-29", "2026-05-28"]
    # §19 must remain intact and after §18.
    assert out.index("## §18") < out.index("## §19")


def test_insert_entry_no_existing_entries():
    doc = "## §18 Progress Log\n\n**note**\n\n## §19 next\n"
    out = rpl.insert_entry(doc, rpl.build_skeleton("2026-05-30", "first"))
    assert "### 2026-05-30 — first" in out
    assert out.index("## §18") < out.index("### 2026-05-30") < out.index("## §19")


def test_insert_entry_no_section_raises():
    with pytest.raises(ValueError):
        rpl.insert_entry("# Roadmap\n\nno section", "skel")


# ── boundary regression: §18 must not match §180 / §181 ───────────────────────


def test_section_heading_not_matched_by_180():
    doc = (
        "## §17 x\n\nt\n\n## §180 Other section\n\n### 2026-01-01 — not §18\n\nbody\n"
    )
    # §18 heading absent → no section (must not pick up §180).
    assert rpl.extract_section_18(doc) is None


def test_section_18_bounded_by_following_180():
    doc = (
        "## §18 Log\n\n### 2026-05-29 — real\n\nbody\n\n"
        "## §180 Appendix\n\nunrelated\n"
    )
    sec = rpl.extract_section_18(doc)
    assert sec is not None
    assert "real" in sec
    assert "Appendix" not in sec  # next `## §` (incl. §180) terminates the section


# ── git layer (monkeypatched subprocess) ──────────────────────────────────────


def test_git_show_returns_content(monkeypatch):
    class _R:
        returncode = 0
        stdout = "file content at ref"

    monkeypatch.setattr(rpl.subprocess, "run", lambda *a, **k: _R())
    assert rpl._git_show("origin/master", "docs/roadmap/x.md") == "file content at ref"


def test_git_show_returns_none_on_failure(monkeypatch):
    class _R:
        returncode = 128
        stdout = ""

    monkeypatch.setattr(rpl.subprocess, "run", lambda *a, **k: _R())
    assert rpl._git_show("bad-ref", "docs/roadmap/x.md") is None


def test_git_show_graceful_on_exception(monkeypatch):
    def _boom(*a, **k):
        raise OSError("git not found")

    monkeypatch.setattr(rpl.subprocess, "run", _boom)
    assert rpl._git_show("origin/master", "x.md") is None
