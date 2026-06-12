"""memory-ai input/output chains on a tmp DB (roadmap 260612 P1, test map §3).

Chains covered here (unit layer; live MCP/hook runs tracked in roadmap §18):
  - A1  W1 happy + dedup + content_hash lands in row metadata
  - A2  W1 importance coercion ("high" / 1.5 / -1 / None → REAL in [0,1])
  - A3-lite  W2 save_to_sqlite: content_hash stamped, already_saved dedups by
    session_id, auto-importance within [0.5, 0.95]
  - A4  W3 _save_to_target("memory-ai") writes a row with content_hash
  - A7  W6 delete_message: honest success / second delete honest failure
  - A8  concurrent writers through the shared WAL connect (no lost rows,
    no "database is locked" escaping)
  - C2  malformed tags JSON / NULL category do not break readers

A5/A6 (propagation, rollback) live in test_propagation_honest.py /
test_governance_wiring.py — not duplicated here (roadmap §5 re-inventory).
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _make_server(tmp_path, monkeypatch):
    """Import the memory-ai MCP server module pointed at a tmp DB."""
    import src.memory.ai_memory.server as ai

    db = tmp_path / "memory_ai.db"
    monkeypatch.setattr(ai, "DB_PATH", db)
    ai.ensure_db()
    return ai, db


def _rows(db):
    conn = sqlite3.connect(str(db))
    try:
        conn.row_factory = sqlite3.Row
        return conn.execute("SELECT * FROM important_messages").fetchall()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# A1 — W1 happy path + dedup + content_hash in metadata
# ---------------------------------------------------------------------------
async def test_a1_save_dedup_and_content_hash(tmp_path, monkeypatch):
    ai, db = _make_server(tmp_path, monkeypatch)

    msg = {"content": "память должна нести content_hash", "category": "decision"}
    r1 = json.loads((await ai.save_important_message(msg))[0].text)
    assert r1["action"] == "saved"

    r2 = json.loads((await ai.save_important_message(msg))[0].text)
    assert r2["action"] == "dup"
    assert r2["id"] == r1["id"]

    rows = _rows(db)
    assert len(rows) == 1
    md = json.loads(rows[0]["metadata"])
    from src.memory.orchestrator.content_hash import hash_content

    assert md["content_hash"] == hash_content(msg["content"])

    # Output side: row is readable back through the MCP read tool.
    out = json.loads((await ai.get_important_messages({"min_importance": 0.0}))[0].text)
    assert out["count"] == 1
    assert out["messages"][0]["metadata"]["content_hash"] == md["content_hash"]


# ---------------------------------------------------------------------------
# A2 — W1 importance coercion (F2 must not regress)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("raw", "expected"),
    [("high", 0.9), (1.5, 1.0), (-1, 0.0), (None, 0.7), ("garbage", 0.7)],
)
async def test_a2_importance_coercion(tmp_path, monkeypatch, raw, expected):
    ai, db = _make_server(tmp_path, monkeypatch)
    args = {"content": f"importance probe {raw!r}", "importance": raw}
    r = json.loads((await ai.save_important_message(args))[0].text)
    assert r["action"] == "saved"

    stored = _rows(db)[0]["importance"]
    assert isinstance(stored, float)
    assert stored == pytest.approx(expected)
    assert 0.0 <= stored <= 1.0


# ---------------------------------------------------------------------------
# A3-lite — W2 Stop-hook writer (module-level functions, no transcript needed)
# ---------------------------------------------------------------------------
def _load_session_hook():
    hooks_dir = PROJECT_ROOT / ".claude" / "hooks"
    if str(hooks_dir) not in sys.path:
        sys.path.insert(0, str(hooks_dir))
    spec = importlib.util.spec_from_file_location(
        "session_memory_save_chain_test", str(hooks_dir / "session-memory-save.py")
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a3_session_save_hash_dedup_importance(tmp_path, monkeypatch):
    import src.memory.ai_memory.server as ai

    db = tmp_path / "memory_ai.db"
    monkeypatch.setattr(ai, "DB_PATH", db)
    ai.ensure_db()

    hook = _load_session_hook()
    monkeypatch.setattr(hook, "SQLITE_DB", db)

    ctx = {
        "session_id": "sess-260612-test",
        "files_changed": ["src/memory/a.py", "tests/unit/b.py", "docs/c.md"],
        "commits": ["feat: chain test"],
        "skills": ["memory-unified"],
        "completed_tasks": ["P1"],
    }
    assert hook.is_meaningful(ctx)
    assert hook.save_to_sqlite(ctx) is True

    rows = _rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert row["category"] == "session_summary"
    assert 0.5 <= row["importance"] <= 0.95
    md = json.loads(row["metadata"])
    assert md["session_id"] == ctx["session_id"]
    assert md["content_hash"], "W2 must stamp content_hash (write-contract)"

    # Second Stop of the same session → dedup, no second row.
    assert hook.already_saved(ctx["session_id"]) is True


# ---------------------------------------------------------------------------
# A4 — W3 route_and_save target writer (orchestrator direct path)
# ---------------------------------------------------------------------------
async def test_a4_save_to_target_memory_ai(tmp_path, monkeypatch):
    import src.memory.ai_memory.server as ai

    db = tmp_path / "memory_ai.db"
    monkeypatch.setattr(ai, "DB_PATH", db)
    ai.ensure_db()
    monkeypatch.setenv("MEMORY_AI_DB_PATH", str(db))

    from src.memory.orchestrator.memory_orchestrator import MemoryOrchestrator

    orch = MemoryOrchestrator.__new__(MemoryOrchestrator)
    eid = await orch._save_to_target(
        "memory-ai",
        "решение: эпизодика хранится в SQLite",
        {"importance": "high", "category": "decision", "tags": ["adr"]},
    )
    assert eid

    rows = _rows(db)
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == eid
    assert row["importance"] == pytest.approx(0.9)  # label coerced
    md = json.loads(row["metadata"])
    assert md.get("content_hash"), "W3 must stamp content_hash"


# ---------------------------------------------------------------------------
# A7 — W6 delete cycle is honest
# ---------------------------------------------------------------------------
async def test_a7_delete_message_honest(tmp_path, monkeypatch):
    ai, db = _make_server(tmp_path, monkeypatch)
    r = json.loads(
        (await ai.save_important_message({"content": "to be deleted"}))[0].text
    )

    d1 = json.loads((await ai.delete_message({"message_id": r["id"]}))[0].text)
    assert d1 == {"success": True, "deleted": 1}
    assert not _rows(db)

    # Second delete of the same id → honest failure, not silent success.
    d2 = json.loads((await ai.delete_message({"message_id": r["id"]}))[0].text)
    assert d2 == {"success": False, "deleted": 0}


# ---------------------------------------------------------------------------
# A8 — concurrent writers: WAL + busy_timeout, no lost rows
# ---------------------------------------------------------------------------
def test_a8_concurrent_writers_no_lost_rows(tmp_path, monkeypatch):
    import src.memory.ai_memory.server as ai
    from src.memory.ai_memory.db import connect

    db = tmp_path / "memory_ai.db"
    monkeypatch.setattr(ai, "DB_PATH", db)
    ai.ensure_db()

    threads, per_thread = 4, 25

    def writer(t: int) -> None:
        for i in range(per_thread):
            conn = connect(db)
            try:
                conn.execute(
                    "INSERT INTO important_messages "
                    "(id, content, importance, category, created_at, updated_at) "
                    "VALUES (?, ?, 0.5, 'test', '2026-06-12', '2026-06-12')",
                    (f"t{t}-i{i}", f"row {t}/{i}"),
                )
                conn.commit()
            finally:
                conn.close()

    with ThreadPoolExecutor(max_workers=threads) as pool:
        # .result() re-raises: a "database is locked" escaping = chain failure.
        for f in [pool.submit(writer, t) for t in range(threads)]:
            f.result()

    assert len(_rows(db)) == threads * per_thread
    conn = sqlite3.connect(str(db))
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# C2 — malformed rows do not break readers
# ---------------------------------------------------------------------------
async def test_c2_malformed_rows_skip_not_crash(tmp_path, monkeypatch):
    ai, db = _make_server(tmp_path, monkeypatch)
    conn = sqlite3.connect(str(db))
    conn.execute(
        "INSERT INTO important_messages "
        "(id, content, importance, category, tags, created_at, updated_at, metadata) "
        "VALUES ('bad-1', 'битая строка', 0.9, NULL, 'not-json{', "
        "'2026-06-12', '2026-06-12', 'also-not-json')"
    )
    conn.commit()
    conn.close()

    out = json.loads((await ai.get_important_messages({"min_importance": 0.0}))[0].text)
    assert out["count"] == 1
    msg = out["messages"][0]
    assert msg["tags"] == ["not-json{"]  # wrapped, not crashed
    assert msg["metadata"] == {}

    found = json.loads((await ai.search_messages({"query": "битая"}))[0].text)
    assert found["count"] == 1

    cats = json.loads((await ai.get_categories({}))[0].text)
    assert isinstance(cats["categories"], list)
