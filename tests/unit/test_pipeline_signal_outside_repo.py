"""Правка ВНЕ корня проекта не считается «правкой кода» (pipeline-protocol, 2026-07-26).

Инцидент: сессия чистой верификации писала только память в `~/.claude/projects/.../memory/`
(git-дерево чистое, правок в репозитории ноль) и получала блок «правки кода без пайплайна».
Сохранение памяти — обязательная часть протокола, поэтому добросовестное исполнение одного
правила штатно нарушало другое.

Тесты пинят ОБЕ стороны инварианта: запись вне репо не требует пайплайна, запись внутри —
требует; отсутствие бита деградирует в прежнее (fail-closed) поведение.
"""

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"


def _load(name: str, filename: str):
    """Загрузить хук по пути (имена файлов с дефисами не импортируются как модуль)."""
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    spec = importlib.util.spec_from_file_location(name, HOOKS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pp = _load("pipeline_protocol_stop", "pipeline-protocol-stop.py")
til = _load("tool_invocation_logger", "tool-invocation-logger.py")

SID = "test-session-outside-repo"


def _row(*, in_repo=None, blocked=False, ts="2026-07-26T23:00:00.000000", tool="Write"):
    """Строка invocation-лога: canonical Pre (или block-запись энфорсера)."""
    row = {
        "ts": ts,
        "event": "PreToolUse",
        "tool": tool,
        "session": SID,
        "hook": "TaskProtocolEnforcer" if blocked else "ToolInvocationLogger",
        "outcome": "block" if blocked else "allow",
        "category": "hook" if blocked else "tool_call",
    }
    if blocked:
        row["reason"] = "SKILL REQUIRED"
    if in_repo is not None:
        row["in_repo"] = in_repo
    return json.dumps(row, ensure_ascii=False)


def _had_write(rows, monkeypatch):
    monkeypatch.setattr(pp, "_read_tail_lines", lambda: list(rows))
    had_write, _ = pp._session_writes_and_start(SID)
    return had_write


# ── потребитель: решение гейта ────────────────────────────────────────────────


def test_outside_repo_write_is_not_an_edit(monkeypatch):
    """Запись памяти вне корня проекта не требует пайплайна (исходный инцидент)."""
    assert _had_write([_row(in_repo=False)], monkeypatch) is False


def test_in_repo_write_still_counts(monkeypatch):
    """Обратная сторона: правка внутри репозитория по-прежнему требует пайплайна."""
    assert _had_write([_row(in_repo=True)], monkeypatch) is True


def test_missing_bit_is_fail_closed(monkeypatch):
    """Старые записи без бита ⟶ прежнее поведение, гейт не ослабевает."""
    assert _had_write([_row()], monkeypatch) is True


def test_outside_does_not_excuse_inside(monkeypatch):
    """Одна внешняя запись не «оправдывает» реальную правку кода в той же сессии."""
    rows = [_row(in_repo=False), _row(in_repo=True, ts="2026-07-26T23:00:05.000000")]
    assert _had_write(rows, monkeypatch) is True


def test_outside_write_does_not_consume_block(monkeypatch):
    """«Вне репо» и «вызов отклонён» независимы: внешняя запись не съедает block-запись.

    Если бы внешняя строка расходовала блок, внутренняя осталась бы неоправданной и гейт
    сработал бы ложно — ровно тот дефект, который правка обязана исключить.
    """
    rows = [
        _row(in_repo=False),
        _row(in_repo=True, ts="2026-07-26T23:00:05.000000"),
        _row(blocked=True, ts="2026-07-26T23:00:05.100000"),
    ]
    assert _had_write(rows, monkeypatch) is False


def test_orphan_block_from_outside_write_does_not_excuse_real_edit(monkeypatch):
    """Блок от ОТКЛОНЁННОЙ внешней записи не должен оправдывать правку в репозитории.

    Находка ревьюера 2026-07-26 (направление — ложный allow): block-запись бита `in_repo`
    не несёт, поэтому пропуск внешней строки оставлял её блок бесхозным, и тот гасил
    настоящую правку, попавшую в окно BLOCK_MATCH_SEC. Внешняя запись обязана забрать
    свой блок, оставаясь при этом «не правкой».
    """
    rows = [
        _row(in_repo=False, ts="2026-07-26T23:00:00.000000"),  # отклонённый внешний Write
        _row(blocked=True, ts="2026-07-26T23:00:00.100000"),  # его блок
        _row(in_repo=True, ts="2026-07-26T23:00:02.000000"),  # реальная правка в репо
    ]
    assert _had_write(rows, monkeypatch) is True


def test_outside_write_with_unparsable_ts_is_not_an_edit(monkeypatch):
    """Битый ts у ВНЕШНЕЙ записи не поднимает fail-closed флаг: она и так не правка."""
    assert _had_write([_row(in_repo=False, ts="not-a-date")], monkeypatch) is False


def test_unparsable_ts_inside_repo_is_fail_closed(monkeypatch):
    """А вот битый ts у записи В репозитории по-прежнему считается правкой."""
    assert _had_write([_row(in_repo=True, ts="not-a-date")], monkeypatch) is True


# ── источник бита ─────────────────────────────────────────────────────────────


def test_target_in_repo_detects_project_file():
    inside = str(Path(til._PROJECT_ROOT) / "src" / "shared" / "llm_rotation" / "service.py")
    assert til._target_in_repo({"file_path": inside}) is True


def test_target_in_repo_detects_memory_file(tmp_path):
    """Каталог памяти лежит в профиле пользователя — вне корня проекта."""
    outside = str(tmp_path / "memory" / "feedback_x.md")
    assert til._target_in_repo({"file_path": outside}) is False


def test_target_in_repo_handles_notebook_path():
    inside = str(Path(til._PROJECT_ROOT) / "notebooks" / "demo.ipynb")
    assert til._target_in_repo({"notebook_path": inside}) is True


def test_target_in_repo_none_without_file_target():
    """Bash/Read не несут файловой цели ⟶ ключ не пишется вовсе (не null-шум)."""
    assert til._target_in_repo({"command": "ls"}) is None
    assert til._target_in_repo(None) is None


def test_relative_path_treated_as_inside():
    """Относительный путь резолвится от корня — консервативно, в пользу гейта."""
    assert til._target_in_repo({"file_path": "src/api/main.py"}) is True


# ── контракт лога ─────────────────────────────────────────────────────────────


def test_record_shape_unchanged_without_bit(monkeypatch, tmp_path):
    """Вызовы без in_repo пишут запись бит-в-бит как прежде (ключа нет)."""
    sys.path.insert(0, str(HOOKS))
    from shared import invocation_logger as il

    log = tmp_path / "hook-invocations.jsonl"
    monkeypatch.setattr(il, "_get_log_file", lambda: log)
    il.log_invocation(hook="H", event="PreToolUse", tool="Write", category="tool_call")
    rec = json.loads(log.read_text(encoding="utf-8").strip())
    assert "in_repo" not in rec


@pytest.mark.parametrize("value,expected", [(True, True), (False, False)])
def test_bit_written_when_known(monkeypatch, tmp_path, value, expected):
    sys.path.insert(0, str(HOOKS))
    from shared import invocation_logger as il

    log = tmp_path / "hook-invocations.jsonl"
    monkeypatch.setattr(il, "_get_log_file", lambda: log)
    il.log_invocation(hook="H", event="PreToolUse", tool="Write", in_repo=value)
    rec = json.loads(log.read_text(encoding="utf-8").strip())
    assert rec["in_repo"] is expected


def test_logger_actually_passes_the_bit(monkeypatch):
    """ПРОВОДКА: execute() обязан передать бит в log_invocation.

    Без этого теста фикс мёртв при зелёном наборе — проверено саботажем: удаление
    `in_repo=_target_in_repo(...)` из вызова не роняло НИ ОДНОГО теста, потому что
    остальные проверяют функцию и потребителя по отдельности, а не связь между ними.
    """
    sys.path.insert(0, str(HOOKS))
    from base import HookInput

    from shared import invocation_logger as il

    captured = {}
    monkeypatch.setattr(il, "log_invocation", lambda **kw: captured.update(kw))

    outside = str(Path.home() / ".claude" / "projects" / "x" / "memory" / "note.md")
    inp = HookInput(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": outside},
            "session_id": SID,
        }
    )
    til.ToolInvocationLogger().execute(inp)

    assert captured.get("in_repo") is False, "бит не доехал до логгера (проводка порвана)"


def test_start_time_still_derived_from_outside_rows(monkeypatch):
    """Внешняя запись пропускается как правка, но время старта сессии из неё берётся.

    Иначе git-fallback (`_git_session_edit`) остался бы без якоря mtime.
    """
    monkeypatch.setattr(pp, "_read_tail_lines", lambda: [_row(in_repo=False)])
    _, start = pp._session_writes_and_start(SID)
    assert start == datetime(2026, 7, 26, 23, 0, 0)
