"""Regression: the session-memory-save dedup path must leave an ingest trace.

The hook deduped by session_id and returned silently, so the §26 ingestion log only
ever saw `saved` from this writer. Measured 2026-07-17: 155 rows in memory_ai.db but
only 2 `memory_ai` events in memory-ingestion.log, and `dup` structurally 0 — while
`learned_patterns` showed 5365 dups. The dedup worked; it was simply invisible.

See pipeline/fix-memory-ai-zero-criteria/ and roadmap 260612 §P4 (criterion
`dup_nonzero`).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.unit

_HOOKS_DIR = Path(__file__).resolve().parents[3] / ".claude" / "hooks"


def _load() -> Any:
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    spec = importlib.util.spec_from_file_location(
        "session_memory_save_mod", _HOOKS_DIR / "session-memory-save.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


sms = _load()


def _ctx() -> dict[str, Any]:
    """A context shaped exactly like collect_context()'s return value."""
    return {
        "session_id": "sess-1",
        "created_at": "2026-07-17T10:00:00",
        "skills": ["memory-unified"],
        "files_changed": ["src/memory/ai_memory/server.py"],
        "commits": ["fix: something"],
        "completed_tasks": [],
    }


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, dict[str, Any]]]:
    """Capture _record_ingest calls; neutralise the side-effecting neighbours."""
    recorded: list[tuple[str, str, dict[str, Any]]] = []

    def _fake_record(action: str, content_hash: str = "", **kw: Any) -> None:
        recorded.append((action, content_hash, kw))

    monkeypatch.setattr(sms, "_record_ingest", _fake_record)
    monkeypatch.setattr(sms, "_emit_langfuse_span", lambda *a, **k: None)
    monkeypatch.setattr(sms, "collect_context", _ctx)
    monkeypatch.setattr(sms, "is_meaningful", lambda ctx: True)
    return recorded


def _execute() -> None:
    sms.SessionMemorySave().execute(object())


def _incumbent(reason: str = "session_already_saved", h: str = "incumbent-hash-1") -> Any:
    return lambda sid: {"content_hash": h, "reason": reason}


def test_dedup_path_emits_dup_event(
    calls: list[tuple[str, str, dict[str, Any]]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sms, "already_saved", _incumbent())

    _execute()

    assert len(calls) == 1, "a silenced write must still be one write attempt"
    action, content_hash, kw = calls[0]
    assert action == "dup"
    assert kw.get("reason") == "session_already_saved"
    assert content_hash, "content_hash lets fact-trace thread the silenced write"


def test_dup_event_carries_the_incumbent_hash_not_a_fresh_one(
    calls: list[tuple[str, str, dict[str, Any]]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """ctx is rebuilt from live git state and drifts between Stops.

    Hashing format_summary(ctx) at dup time would emit a content_hash for a candidate
    that exists in no store — fact-trace would show an orphan event, and the row that
    actually caused the dedup would show none.
    """
    monkeypatch.setattr(sms, "already_saved", _incumbent(h="hash-of-stored-row"))
    monkeypatch.setattr(sms, "_content_hash", lambda c: "hash-of-fresh-candidate")

    _execute()

    assert calls[0][1] == "hash-of-stored-row"


def test_reason_names_the_key_that_actually_matched(
    calls: list[tuple[str, str, dict[str, Any]]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """already_saved has two keys: session_id, else today's date. When session-skills.json
    is missing or raced to garbage, session_id is empty and the date branch matches — the
    log must not then claim the *session* was already saved."""
    monkeypatch.setattr(sms, "already_saved", _incumbent(reason="date_already_saved"))

    _execute()

    assert calls[0][2].get("reason") == "date_already_saved"


def test_dedup_path_does_not_write_the_row(
    calls: list[tuple[str, str, dict[str, Any]]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The event must not come at the cost of the dedup itself."""
    monkeypatch.setattr(sms, "already_saved", _incumbent())
    wrote: list[bool] = []
    monkeypatch.setattr(sms, "save_to_sqlite", lambda ctx: wrote.append(True))

    _execute()

    assert wrote == []
    assert [c[0] for c in calls] == ["dup"]


def test_fresh_session_saves_and_reports_saved(
    calls: list[tuple[str, str, dict[str, Any]]], monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Non-dup path: the row is written and reported `saved`, never `dup`.

    save_to_sqlite runs for real against a tmp DB — stubbing it out made the old version
    of this test vacuous (no _record_ingest fired, so `"dup" not in []` passed even with
    execute() gutted).
    """
    import sqlite3

    db = tmp_path / "m.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        "CREATE TABLE important_messages (id TEXT, content TEXT, importance REAL, "
        "category TEXT, tags TEXT, created_at TEXT, updated_at TEXT, metadata TEXT)"
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(sms, "SQLITE_DB", db)
    monkeypatch.setattr(sms, "already_saved", lambda sid: None)
    monkeypatch.setattr(sms, "save_to_wiki_log", lambda ctx: True)
    monkeypatch.setattr(sms, "try_promote_patterns", lambda: None)

    _execute()

    rows = sqlite3.connect(str(db)).execute("SELECT COUNT(*) FROM important_messages").fetchone()
    assert rows[0] == 1, "the fresh path must actually persist the row"
    assert [c[0] for c in calls] == ["saved"]


def test_trivial_session_emits_nothing(
    calls: list[tuple[str, str, dict[str, Any]]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A trivial session was never a write attempt — it must not inflate dup-rate."""
    monkeypatch.setattr(sms, "is_meaningful", lambda ctx: False)
    monkeypatch.setattr(sms, "already_saved", _incumbent())

    _execute()

    assert calls == []
