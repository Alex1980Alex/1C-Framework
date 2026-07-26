"""Заблокированный гардом вызов ≠ правка кода (инцидент 2026-07-26).

Отклонённый энфорсером Write оставляет в ``data/hook-invocations.jsonl`` до 12 Pre-записей
(по одной на хук цепочки: блокирующий отдаёт ``decision:"block"``, при котором цепочка
доходит до логгера), хотя ни один файл не записан и git-дерево чистое. Тесты пинят ОБЕ
стороны инварианта: блок не считается правкой (нет ложного требования пайплайна) и реальная
правка считается всегда (гейт не ослаблен, вкл. ветку без телеметрии).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_HOOKS = _ROOT / ".claude" / "hooks"
SID = "s1"
BASE = datetime(2026, 7, 26, 4, 39, 28)


def _load(modname: str, path: Path):
    """Имена файлов хуков с дефисами обычным import не грузятся."""
    spec = importlib.util.spec_from_file_location(modname, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pp = _load("pipeline_protocol_stop_blocked", _HOOKS / "pipeline-protocol-stop.py")
cvr = _load("code_verify_reminder_blocked", _HOOKS / "code-verify-reminder.py")

if str(_ROOT / "scripts") not in sys.path:
    sys.path.append(str(_ROOT / "scripts"))

import analyze_tool_health as ath  # report-слой — для parity-теста
import tool_effectiveness as te  # single-source предиката


def _rec(off: float = 0.0, **kw) -> dict:
    """Запись invocation-лога: дефолт = «хук пропустил Write» (не блок, не canonical)."""
    rec = {
        "session": SID,
        "event": "PreToolUse",
        "tool": "Write",
        "category": "hook",
        "outcome": "allow",
        "ts": (BASE + timedelta(seconds=off)).isoformat(),
    }
    rec.update(kw)
    return rec


def _patch(monkeypatch, recs: list[dict]) -> None:
    lines = [json.dumps(r, ensure_ascii=False) for r in recs]
    monkeypatch.setattr(pp, "_read_tail_lines", lambda: lines)


def _blocked_chain(off: float = 0.0) -> list[dict]:
    """Живая форма лога: 12 Pre-записей ОДНОГО отклонённого Write."""
    chain = [_rec(off=off + i / 100, hook=f"Guard{i}") for i in range(10)]
    chain.append(_rec(off=off + 0.01, hook="TaskProtocolEnforcer", outcome="block"))
    chain.append(
        _rec(off=off + 0.1, hook="ToolInvocationLogger", category="tool_call", tool_call_id="blk")
    )
    return chain


# ── сигнал «была правка» ───────────────────────────────────────────────────────


def test_blocked_write_is_not_an_edit(monkeypatch):
    _patch(monkeypatch, _blocked_chain())
    had, start = pp._session_writes_and_start(SID)
    assert had is False  # тул не исполнялся → правки не было
    assert start is not None  # старт сессии по-прежнему определён


def test_real_write_after_block_counts(monkeypatch):
    _patch(
        monkeypatch,
        _blocked_chain() + [_rec(off=30, category="tool_call", tool_call_id="real")],
    )
    assert pp._session_writes_and_start(SID)[0] is True


def test_two_canonical_one_block(monkeypatch):
    """Расходуемое 1:1 — один блок объясняет РОВНО один вызов, второй остаётся правкой."""
    _patch(
        monkeypatch,
        [
            _rec(off=0, category="tool_call", tool_call_id="a"),
            _rec(off=30, category="tool_call", tool_call_id="b"),
            _rec(off=0.01, outcome="block", hook="TaskProtocolEnforcer"),
        ],
    )
    assert pp._session_writes_and_start(SID)[0] is True


def test_block_from_other_session_ignored(monkeypatch):
    _patch(
        monkeypatch,
        [
            _rec(off=0, category="tool_call", tool_call_id="a"),
            # session="s10" (а не "s2") намеренно: строка содержит "s1" как подстроку →
            # пре-фильтр `sid not in line` её НЕ отсеет, работает именно сверка session.
            _rec(off=0.01, outcome="block", session="s10"),
        ],
    )
    assert pp._session_writes_and_start(SID)[0] is True


def test_block_for_other_tool_ignored(monkeypatch):
    _patch(
        monkeypatch,
        [
            _rec(off=0, category="tool_call", tool_call_id="a"),
            _rec(off=0.01, outcome="block", tool="Bash"),
        ],
    )
    assert pp._session_writes_and_start(SID)[0] is True


def test_block_outside_window_ignored(monkeypatch):
    """±BLOCK_MATCH_SEC: блок минутой позже — про другой вызов, не про этот."""
    _patch(
        monkeypatch,
        [
            _rec(off=0, category="tool_call", tool_call_id="a"),
            _rec(off=60, outcome="block"),
        ],
    )
    assert pp._session_writes_and_start(SID)[0] is True


def test_no_canonical_records_fail_closed(monkeypatch):
    """Логгер молчит (нет category=tool_call) → прежнее поведение: считаем правкой."""
    _patch(monkeypatch, [_rec(off=0, hook="SomeGuard"), _rec(off=0.02, hook="Other")])
    assert pp._session_writes_and_start(SID)[0] is True


def test_canonical_with_unparsable_ts_fail_closed(monkeypatch):
    """Сопоставить нельзя → не вычитаем (иначе битый ts открывал бы дыру в гейте)."""
    _patch(
        monkeypatch,
        [
            _rec(category="tool_call", tool_call_id="a", ts="не-дата"),
            _rec(off=0.01, outcome="block"),
        ],
    )
    assert pp._session_writes_and_start(SID)[0] is True


def test_helper_unavailable_keeps_gate_strict(monkeypatch):
    """Нет tool_effectiveness (заглушки) → вычета нет, гейт строгий как раньше."""
    monkeypatch.setattr(pp, "_is_guard_block", lambda _e: False)
    _patch(monkeypatch, _blocked_chain())
    assert pp._session_writes_and_start(SID)[0] is True


def test_no_write_records_at_all(monkeypatch):
    _patch(monkeypatch, [_rec(tool="Read", category="tool_call", tool_call_id="r")])
    assert pp._session_writes_and_start(SID)[0] is False


def test_other_session_records_ignored(monkeypatch):
    # "s10" содержит "s1" → проходит пре-фильтр, отсекается сверкой session (не подстрокой)
    _patch(monkeypatch, [_rec(category="tool_call", tool_call_id="a", session="s10")])
    assert pp._session_writes_and_start(SID) == (False, None)


def test_multiedit_canonical_counts(monkeypatch):
    _patch(monkeypatch, [_rec(tool="MultiEdit", category="tool_call", tool_call_id="m")])
    assert pp._session_writes_and_start(SID)[0] is True


# ── parity: одно определение блокировки на report- и enforcement-слой ──────────


def test_is_guard_block_matches_report_layer(tmp_path):
    recs = [
        _rec(outcome="block", hook="Enforcer"),  # блок с тулом — единственный настоящий
        _rec(outcome="block", hook="StopGate", tool=None),  # Stop-блок без тула
        _rec(),  # allow
        _rec(outcome="message", hook="Advisory"),  # advisory-сообщение
    ]
    log = tmp_path / "hook-invocations.jsonl"
    log.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n", encoding="utf-8"
    )
    by_tool = ath.guard_blocks_by_tool(BASE + timedelta(minutes=1), 14, logs=[log])
    assert sum(len(v) for v in by_tool.values()) == 1  # report-слой видит один блок
    assert sum(1 for r in recs if te.is_guard_block(r)) == 1  # и предикат — тот же один


# ── code-verify-reminder: задача на ФАКТ записи, не на намерение ───────────────


def _inp(event: str, file_path: str = "scripts/x.py") -> SimpleNamespace:
    return SimpleNamespace(
        detected_event=event,
        tool_name="Write",
        tool_input={"file_path": file_path},
        session_id=SID,
    )


def test_pre_tool_use_does_not_create_task(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(cvr, "add_task", lambda **kw: bool(calls.append(kw)) or True)
    assert cvr.CodeVerifyReminder().execute(_inp("PreToolUse")) is None
    assert calls == []  # блокированный Write не оставит фантомной mandatory-задачи


def test_post_tool_use_creates_task(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(cvr, "add_task", lambda **kw: bool(calls.append(kw)) or True)
    out = cvr.CodeVerifyReminder().execute(_inp("PostToolUse"))
    assert len(calls) == 1  # Post приходит только у исполнившегося вызова
    assert out is not None


def test_post_tool_use_skips_non_code_file(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(cvr, "add_task", lambda **kw: bool(calls.append(kw)) or True)
    assert cvr.CodeVerifyReminder().execute(_inp("PostToolUse", "docs/readme.md")) is None
    assert calls == []
