"""J-P0.1 (roadmap 260725): опциональные контент-дайджесты в mcp_call_log.

Инвариант, который тут пинится в ОБЕ стороны:
  - флаг off  → запись бит-в-бит прежнего формата (контракт «metadata only»);
  - флаг on   → args_digest/result_digest есть, усечены, секреты вычищены.

Саботаж-проверка (feedback-sabotage-check-tests): откат правки `log_mcp_call`
краснит `test_content_written_when_flag_on`; откат `_redact` — `test_secret_redacted`.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture
def mcl(tmp_path, monkeypatch):
    """Свежий модуль с cache-dir в tmp_path (env читается ПО ВЫЗОВУ, но модуль перезагружаем)."""
    monkeypatch.setenv("CLAUDE_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("MCP_CALL_LOG_DISABLE", raising=False)
    monkeypatch.delenv("MCP_CALL_LOG_CONTENT", raising=False)
    monkeypatch.delenv("MCP_CALL_LOG_CONTENT_CAP", raising=False)
    import mcp_call_log

    return importlib.reload(mcp_call_log)


def _records(tmp_path: Path, server: str = "srv") -> list[dict]:
    path = tmp_path / f"mcp-{server}-calls.jsonl"
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


# ── флаг OFF: прежний формат бит-в-бит ────────────────────────────────────────


def test_no_content_fields_when_flag_off(mcl, tmp_path):
    mcl.log_mcp_call(
        "srv", "execute_query", ok=True, ms=12.3, args={"q": "SELECT 1"}, result="rows"
    )
    rec = _records(tmp_path)[0]
    assert set(rec) == {"ts", "server", "tool", "ok", "ms"}, "контракт metadata-only нарушен"


def test_record_shape_identical_to_legacy(mcl, tmp_path):
    """Ключи и их порядок совпадают с до-J-P0.1 форматом (регресс на дрейф схемы)."""
    mcl.log_mcp_call("srv", "t", ok=False, ms=1.0, error_type="HTTPStatusError", args={"a": 1})
    rec = _records(tmp_path)[0]
    assert list(rec) == ["ts", "server", "tool", "ok", "ms", "error_type"]


# ── флаг ON: контент пишется ──────────────────────────────────────────────────


def test_content_written_when_flag_on(mcl, tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_CALL_LOG_CONTENT", "1")
    mcl.log_mcp_call(
        "srv", "execute_query", ok=True, ms=5.0, args={"q": "SELECT 1"}, result="4 rows"
    )
    rec = _records(tmp_path)[0]
    assert rec["args_digest"] == '{"q": "SELECT 1"}'
    assert rec["result_digest"] == "4 rows"


def test_absent_content_not_written_even_when_flag_on(mcl, tmp_path, monkeypatch):
    """Флаг включён, но вызывающий контент не передал — полей нет (не пустые строки)."""
    monkeypatch.setenv("MCP_CALL_LOG_CONTENT", "1")
    mcl.log_mcp_call("srv", "ping", ok=True, ms=1.0)
    rec = _records(tmp_path)[0]
    assert "args_digest" not in rec and "result_digest" not in rec


def test_truncated_at_cap(mcl, tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_CALL_LOG_CONTENT", "1")
    monkeypatch.setenv("MCP_CALL_LOG_CONTENT_CAP", "20")
    mcl.log_mcp_call("srv", "t", ok=True, ms=1.0, args="x" * 500)
    digest = _records(tmp_path)[0]["args_digest"]
    assert digest.endswith("…[truncated]") and digest[:20] == "x" * 20


# ── редакция секретов ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "payload",
    [
        {"password": "hunter2"},
        {"api_key": "sk-live-abcdef"},
        {"token": "ghp_realsecret"},
        "Authorization: Bearer eyJhbGciOi.payload.sig",
        "connect --secret=topsecret --host=db",
    ],
)
def test_secret_redacted(mcl, tmp_path, monkeypatch, payload):
    monkeypatch.setenv("MCP_CALL_LOG_CONTENT", "1")
    mcl.log_mcp_call("srv", "t", ok=True, ms=1.0, args=payload)
    digest = _records(tmp_path)[0]["args_digest"]
    for leaked in (
        "hunter2",
        "sk-live-abcdef",
        "ghp_realsecret",
        "eyJhbGciOi.payload.sig",
        "topsecret",
    ):
        assert leaked not in digest, f"секрет утёк в лог: {digest}"
    assert "***" in digest


@pytest.mark.parametrize(
    "payload,leak",
    [
        # ⚠ Р1 (code-verify): вложенный объект как значение секретного ключа —
        # regex по тексту обрывался на пробеле и хвост утекал сырым.
        ({"auth": {"token": "ghp_nested"}}, "ghp_nested"),
        ({"secret": {"k": "v-inner"}}, "v-inner"),
        ({"outer": {"inner": {"password": "deep_pw"}}}, "deep_pw"),
        ({"items": [{"api_key": "in_list"}]}, "in_list"),
        # Authorization без слова Bearer + альтернативные схемы
        ("Authorization: opaque-token-xyz", "opaque-token-xyz"),
        ("Authorization: Basic dXNlcjpwYXNz", "dXNlcjpwYXNz"),
        # ключи вне прежнего алфавита
        ({"pwd": "old_pwd"}, "old_pwd"),
        ({"private_key": "-----BEGINKEY-----"}, "BEGINKEY"),
        ({"cookie": "session=abc123"}, "abc123"),
        ({"credentials": "user:pass"}, "user:pass"),
    ],
)
def test_secret_variants_redacted(mcl, tmp_path, monkeypatch, payload, leak):
    monkeypatch.setenv("MCP_CALL_LOG_CONTENT", "1")
    mcl.log_mcp_call("srv", "t", ok=True, ms=1.0, args=payload)
    digest = _records(tmp_path)[0]["args_digest"]
    assert leak not in digest, f"секрет утёк: {digest}"


def test_recursive_redaction_keeps_business_data(mcl, tmp_path, monkeypatch):
    """Чистим ТОЛЬКО секретные ключи: остальное судье нужно видеть."""
    monkeypatch.setenv("MCP_CALL_LOG_CONTENT", "1")
    mcl.log_mcp_call(
        "srv",
        "execute_query",
        ok=True,
        ms=1.0,
        args={"query": "ВЫБРАТЬ Ссылка ИЗ Документ.Заказ", "auth": {"token": "sk-1"}},
    )
    digest = _records(tmp_path)[0]["args_digest"]
    assert "Документ.Заказ" in digest and "sk-1" not in digest


def test_benign_connection_string_survives(mcl, tmp_path, monkeypatch):
    """Строка подключения 1С — не секрет; глушить её нельзя, иначе судья слеп."""
    monkeypatch.setenv("MCP_CALL_LOG_CONTENT", "1")
    mcl.log_mcp_call("srv", "t", ok=True, ms=1.0, args='Srvr="HOST";Ref="TestDB"')
    assert _records(tmp_path)[0]["args_digest"] == 'Srvr="HOST";Ref="TestDB"'


def test_redaction_failure_drops_field(mcl, tmp_path, monkeypatch):
    """fail-closed: невозможность отредактировать = поля нет (не сырое значение)."""
    monkeypatch.setenv("MCP_CALL_LOG_CONTENT", "1")
    monkeypatch.setattr(mcl, "_redact", lambda _text: None)
    mcl.log_mcp_call("srv", "t", ok=True, ms=1.0, args={"q": "secret data"})
    rec = _records(tmp_path)[0]
    assert "args_digest" not in rec
    assert rec["ok"] is True, "провал редакции не должен ронять саму запись"


# ── track_call ────────────────────────────────────────────────────────────────


def test_track_call_passes_content(mcl, tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_CALL_LOG_CONTENT", "1")
    with mcl.track_call("srv", "unified_search") as st:
        st["args"] = {"query": "как работает гейт"}
        st["result"] = {"hits": 3}
    rec = _records(tmp_path)[0]
    assert "как работает гейт" in rec["args_digest"]
    assert rec["result_digest"] == '{"hits": 3}'


def test_track_call_content_on_exception(mcl, tmp_path, monkeypatch):
    """Аргументы упавшего вызова — самые ценные для судьи, их терять нельзя."""
    monkeypatch.setenv("MCP_CALL_LOG_CONTENT", "1")
    with pytest.raises(ValueError), mcl.track_call("srv", "t") as st:
        st["args"] = {"bad": "input"}
        raise ValueError("boom")
    rec = _records(tmp_path)[0]
    assert rec["ok"] is False and rec["error_type"] == "ValueError"
    assert rec["args_digest"] == '{"bad": "input"}'


def test_kill_switch_still_wins(mcl, tmp_path, monkeypatch):
    monkeypatch.setenv("MCP_CALL_LOG_CONTENT", "1")
    monkeypatch.setenv("MCP_CALL_LOG_DISABLE", "1")
    mcl.log_mcp_call("srv", "t", ok=True, ms=1.0, args={"a": 1})
    assert _records(tmp_path) == []
