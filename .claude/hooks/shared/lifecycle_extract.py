"""lifecycle_extract -- §23 P1 pure lifecycle extractor.

Extracts structured lifecycle stage data from Claude Code transcript events
and git context.  No I/O side effects except the thin ``extract_stages``
path-reader wrapper.

Public API
----------
iter_tool_uses(entry)                            -- yield tool_use dicts recursively
iter_text(entry)                                 -- yield assistant text strings recursively
extract_from_events(events, git_ctx) -> dict     -- core pure extractor
extract_stages(transcript_path, git_ctx) -> dict -- thin I/O wrapper
render_record(stages, session_id, now_iso) -> str -- markdown renderer

ADR-D5: roadmap 260523_ROADMAP_FULL_DEV_LIFECYCLE_ANALYSIS.md §23
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TRANSCRIPT_READ_LIMIT = 5 * 1024 * 1024  # 5 MB tail
_MAX_EVENTS = 5000  # cap event count to keep extraction bounded

_RESEARCH_TOOLS = frozenset({"WebSearch", "WebFetch"})
_DESIGN_TOOLS = frozenset({"Edit", "Write"})

_VERIFY_VERDICT_RE = re.compile(r"Verdict:\s*(PASS|FAIL|BLOCKED|SKIP)", re.IGNORECASE)
_CODE_VERIFY_PASS_RE = re.compile(r"\[CODE-VERIFY-PASS\]")
_CODE_VERIFY_FAIL_RE = re.compile(r"\[CODE-VERIFY-FAIL\]")

_REVIEW_SKILL_NAMES = frozenset({"code-review", "review"})
_VERIFY_SKILL_NAMES = frozenset({"verify"})

_AUTO_SAVE_PREFIX = "chore: auto-save"


# ---------------------------------------------------------------------------
# Recursive transcript walkers (adapted from roadmap-progress-enforcer)
# ---------------------------------------------------------------------------


def iter_tool_uses(entry: Any) -> Iterator[dict]:  # type: ignore[type-arg]
    """Recursively yield dicts that have ``type=="tool_use"`` and a ``name``."""
    if isinstance(entry, dict):
        if entry.get("type") == "tool_use" and entry.get("name"):
            yield entry
        for v in entry.values():
            yield from iter_tool_uses(v)
    elif isinstance(entry, list):
        for item in entry:
            yield from iter_tool_uses(item)


def iter_text(entry: Any) -> Iterator[str]:
    """Recursively yield assistant text strings.

    Yields from:
    - Content blocks ``{"type": "text", "text": "..."}``
    - Any dict with a top-level ``"text"`` string value
    - Plain string entries in lists
    """
    if isinstance(entry, dict):
        if entry.get("type") == "text" and isinstance(entry.get("text"), str):
            yield entry["text"]
        elif "text" in entry and isinstance(entry["text"], str):
            yield entry["text"]
        for v in entry.values():
            yield from iter_text(v)
    elif isinstance(entry, list):
        for item in entry:
            yield from iter_text(item)
    elif isinstance(entry, str):
        yield entry


# ---------------------------------------------------------------------------
# Core pure extractor
# ---------------------------------------------------------------------------


def extract_from_events(events: list[dict[str, Any]], git_ctx: dict[str, Any]) -> dict[str, Any]:
    """Extract lifecycle stage data from transcript events and git context.

    Args:
        events:  List of JSONL-parsed transcript event dicts.
        git_ctx: Caller-supplied git context dict with keys:
                 ``commits``         -- list[str] of commit messages this session
                 ``files``           -- list[str] of changed file paths
                 ``completed_tasks`` -- list[str] of completed task descriptions
                 ``skills``          -- list[str] of activated skill names

    Returns:
        Dict with keys: research, design, impl, review, verify, lessons,
        substantive.
    """
    # research: WebSearch / WebFetch tool_use -> unique queries/URLs
    research: list[dict[str, str]] = []
    _research_seen: set[str] = set()

    # design: Edit/Write to docs/roadmap/ or /adr/ paths -> unique basenames
    design: list[str] = []
    _design_seen: set[str] = set()

    # review: [CODE-VERIFY-PASS/FAIL] markers + named-skill invocations
    review: list[str] = []
    _review_seen: set[str] = set()

    # verify: lines matching Verdict: X + named-skill invocations
    verify: list[str] = []
    _verify_seen: set[str] = set()

    for event in events:
        # --- tool_use walk ---
        for tu in iter_tool_uses(event):
            name: str = tu.get("name", "")
            inp: dict[str, Any] = tu.get("input") or {}

            # research
            if name in _RESEARCH_TOOLS:
                query: str = inp.get("query") or inp.get("url", "")
                if query and query not in _research_seen:
                    _research_seen.add(query)
                    research.append({"tool": name, "query": query})

            # design
            if name in _DESIGN_TOOLS:
                raw_path: str = inp.get("file_path", "")
                norm_path = raw_path.replace("\\", "/")
                if "docs/roadmap/" in norm_path or "/adr/" in norm_path:
                    bname = os.path.basename(norm_path)
                    if bname and bname not in _design_seen:
                        _design_seen.add(bname)
                        design.append(bname)

            # review / verify via named-skill tool_use block
            # tool name == "Skill", input has a "skill" key
            if name == "Skill":
                sname: str = inp.get("skill", "")
                if sname in _REVIEW_SKILL_NAMES:
                    tag = "named-skill: " + sname
                    if tag not in _review_seen:
                        _review_seen.add(tag)
                        review.append(tag)
                if sname in _VERIFY_SKILL_NAMES:
                    tag2 = "named-skill: " + sname
                    if tag2 not in _verify_seen:
                        _verify_seen.add(tag2)
                        verify.append(tag2)

        # --- text walk ---
        for text in iter_text(event):
            if not text:
                continue
            # review markers
            if _CODE_VERIFY_PASS_RE.search(text):
                marker = "code-verify: PASS"
                if marker not in _review_seen:
                    _review_seen.add(marker)
                    review.append(marker)
            if _CODE_VERIFY_FAIL_RE.search(text):
                marker = "code-verify: FAIL"
                if marker not in _review_seen:
                    _review_seen.add(marker)
                    review.append(marker)
            # verify: Verdict: X lines
            for match in _VERIFY_VERDICT_RE.finditer(text):
                verdict_val = match.group(1).upper()
                entry_str = "verify: " + verdict_val
                if entry_str not in _verify_seen:
                    _verify_seen.add(entry_str)
                    verify.append(entry_str)

    # impl: filter auto-save noise from commits; cap files to 30
    raw_commits: list[str] = git_ctx.get("commits") or []
    filtered_commits = [c for c in raw_commits if not c.lower().startswith(_AUTO_SAVE_PREFIX)]
    raw_files: list[str] = git_ctx.get("files") or []
    impl: dict[str, Any] = {
        "commits": filtered_commits,
        "files": raw_files[:30],
    }

    # lessons: completed tasks + activated skills from git_ctx
    lessons: dict[str, Any] = {
        "completed_tasks": git_ctx.get("completed_tasks") or [],
        "skills": git_ctx.get("skills") or [],
    }

    # substantive gate: skip trivial Q&A with no commit/research/verdict
    substantive: bool = bool(impl["commits"]) or bool(research) or bool(review) or bool(verify)

    return {
        "research": research,
        "design": design,
        "impl": impl,
        "review": review,
        "verify": verify,
        "lessons": lessons,
        "substantive": substantive,
    }


# ---------------------------------------------------------------------------
# Thin I/O wrapper
# ---------------------------------------------------------------------------


def extract_stages(transcript_path: str, git_ctx: dict[str, Any]) -> dict[str, Any]:
    """Read transcript JSONL and call extract_from_events.

    Reads at most the last 5 MB of the transcript and caps events at
    ``_MAX_EVENTS``.  Fail-soft: bad lines are skipped; missing / unreadable
    file yields empty events (returns ``substantive=False``).

    Args:
        transcript_path: Absolute path to the session transcript JSONL file.
        git_ctx:         As per ``extract_from_events``.

    Returns:
        Dict from ``extract_from_events``.
    """
    events: list[dict[str, Any]] = []
    if transcript_path:
        p = Path(transcript_path)
        if p.exists():
            try:
                with open(p, "rb") as fh:
                    fh.seek(0, 2)
                    size = fh.tell()
                    fh.seek(max(0, size - _TRANSCRIPT_READ_LIMIT))
                    blob = fh.read().decode("utf-8", errors="replace")
                for line in blob.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict):
                            events.append(obj)
                    except (ValueError, json.JSONDecodeError):
                        continue
                    if len(events) >= _MAX_EVENTS:
                        break
            except OSError:
                pass  # fail-soft
    return extract_from_events(events, git_ctx)


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------


def _derive_keywords(stages: dict[str, Any]) -> list[str]:
    """Derive keywords from impl files (extensions) + commit-type prefixes."""
    keywords: list[str] = []
    seen: set[str] = set()

    # file extensions
    for fp in stages.get("impl", {}).get("files", []):
        ext = os.path.splitext(fp)[-1].lstrip(".")
        if ext and ext not in seen and len(ext) <= 10:
            seen.add(ext)
            keywords.append(ext)

    # commit-type prefixes: feat / fix / chore / docs / refactor / test / etc.
    _prefix_re = re.compile(r"^([a-z]+)[(:  ]")
    for commit in stages.get("impl", {}).get("commits", []):
        m = _prefix_re.match(commit.lower())
        if m:
            prefix = m.group(1)
            if prefix not in seen:
                seen.add(prefix)
                keywords.append(prefix)

    return keywords


def render_record(stages: dict[str, Any], session_id: str, now_iso: str) -> str:
    """Render lifecycle stages as a compact markdown record.

    Args:
        stages:     Dict returned by extract_from_events / extract_stages.
        session_id: Session identifier string.
        now_iso:    ISO-8601 creation timestamp string.

    Returns:
        Markdown string with YAML-ish frontmatter and per-stage sections.
        Only present (non-empty) stages get a section.
    """

    def _is_present(key: str) -> bool:
        val = stages.get(key)
        if isinstance(val, list):
            return bool(val)
        if isinstance(val, dict):
            return any(bool(v) for v in val.values())
        return False

    stage_keys = ["research", "design", "impl", "review", "verify", "lessons"]
    present = [k for k in stage_keys if _is_present(k)]
    keywords = _derive_keywords(stages)

    lines: list[str] = []

    # frontmatter
    lines.append("---")
    lines.append("session_id: " + session_id)
    lines.append("created: " + now_iso)
    lines.append("stages_present: [" + ", ".join(present) + "]")
    lines.append("keywords: [" + ", ".join(keywords) + "]")
    lines.append("---")
    lines.append("")

    stage_labels = {
        "research": "Research",
        "design": "Design",
        "impl": "Implementation",
        "review": "Review",
        "verify": "Verify",
        "lessons": "Lessons",
    }

    for idx, key in enumerate(stage_keys, start=1):
        if key not in present:
            continue
        label = stage_labels[key]
        lines.append("## §" + str(idx) + " " + label)
        val = stages[key]

        if key == "research":
            for item in val:
                lines.append("- [" + item["tool"] + "] " + item["query"])

        elif key == "design":
            for bname in val:
                lines.append("- " + bname)

        elif key == "impl":
            if val.get("commits"):
                lines.append("**Commits:**")
                for c in val["commits"]:
                    lines.append("- " + c)
            if val.get("files"):
                lines.append("**Files:**")
                for f in val["files"]:
                    lines.append("- " + f)

        elif key == "review":
            for item in val:
                lines.append("- " + item)

        elif key == "verify":
            for item in val:
                lines.append("- " + item)

        elif key == "lessons":
            if val.get("completed_tasks"):
                lines.append("**Completed tasks:**")
                for t in val["completed_tasks"]:
                    lines.append("- " + t)
            if val.get("skills"):
                lines.append("**Skills:**")
                for s in val["skills"]:
                    lines.append("- " + s)

        lines.append("")

    return "\n".join(lines)
