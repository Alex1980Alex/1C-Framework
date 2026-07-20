"""Unit-тесты z-ai-write-guard: BSL/OneScript исключены из делегирования, прочий код — нет.

Контекст (2026-07-20). Гард требует делегировать генерацию кода >15 строк на Z.AI.
Для BSL это противоречило стоячему правилу пользователя «Z.AI — исполнитель кода ДЛЯ ВСЕХ
языков КРОМЕ 1С» (Z.AI не знает платформу и галлюцинирует API 1С). Конфликт разрешён
исключением `.bsl`/`.os` из `_CODE_EXTENSIONS`.

Тесты пинят ОБЕ стороны инварианта: BSL проходит, Python по-прежнему блокируется.
Без второй половины правка выродилась бы в «отключили гард».

Детерминированы (marker `unit`, без сети/1С): хук грузится через importlib
(имя файла с дефисами → spec_from_file_location).
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

_HOOK = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "z-ai-write-guard.py"


def _load():
    spec = importlib.util.spec_from_file_location("z_ai_write_guard", _HOOK)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.mark.unit
def test_bsl_not_in_code_extensions():
    """BSL/OneScript не считаются делегируемым кодом — правило «BSL пишет только Opus»."""
    m = _load()
    assert ".bsl" not in m._CODE_EXTENSIONS
    assert ".os" not in m._CODE_EXTENSIONS


@pytest.mark.unit
def test_delegatable_languages_still_guarded():
    """Обратная сторона инварианта: остальные языки остались под гардом.

    Саботаж-проверка правки: если кто-то «починит» гард, вычистив _CODE_EXTENSIONS
    целиком, этот тест покраснеет.
    """
    m = _load()
    for ext in (".py", ".ts", ".js", ".java", ".go"):
        assert ext in m._CODE_EXTENSIONS, f"{ext} должен оставаться под гардом делегирования"


@pytest.mark.unit
def test_bsl_is_not_silently_skipped_as_non_code():
    """BSL исключён именно из code-ветки, а НЕ добавлен в _SKIP_EXTENSIONS.

    Разница смысловая: `.bsl` — код (его пишет Opus), а не «не-код» вроде .md/.json.
    Если бы его положили в _SKIP_EXTENSIONS, любая будущая проверка, опирающаяся на
    «это не код», начала бы врать про BSL.
    """
    m = _load()
    assert ".bsl" not in m._SKIP_EXTENSIONS
    assert ".os" not in m._SKIP_EXTENSIONS


def _long_source(head: str, body: str, tail: str) -> str:
    """Тело заведомо длиннее _LINE_THRESHOLD (15 строк)."""
    return "\n".join([head, *[body.format(i=i) for i in range(40)], tail])


def _repo_path(m, *parts: str) -> str:
    """Путь ВНУТРИ репозитория: вне репо гард освобождает файл раньше проверки расширения."""
    return str(Path(m._PROJECT_ROOT).joinpath(*parts))


def _no_delegation(monkeypatch) -> None:
    """Гард считает: провайдер жив, делегирования в сессии НЕ было.

    Без этих заглушек тест зависел бы от реального состояния сессии: любой недавний
    llm_complete (окно 30 мин) заставил бы гард пропустить запись, и тест позеленел бы
    по ложной причине. Импорты в хуке локальные, поэтому подменяем sys.modules.
    """
    fake_health = types.ModuleType("shared.llm_health")
    fake_health.is_provider_down = lambda: False

    class _State:
        @staticmethod
        def has_llm_delegation() -> bool:
            return False

    fake_state = types.ModuleType("shared.session_state")
    fake_state.SessionState = _State

    monkeypatch.setitem(sys.modules, "shared.llm_health", fake_health)
    monkeypatch.setitem(sys.modules, "shared.session_state", fake_state)


@pytest.mark.unit
def test_long_bsl_in_configuration_not_blocked(monkeypatch):
    """Сквозная: длинный .bsl в дереве конфигурации пишется без делегирования."""
    m = _load()
    _no_delegation(monkeypatch)

    source = _long_source(
        "Функция НепечатаемыеПлейсхолдеры(Шаблон) Экспорт",
        "\tЗначение{i} = {i};",
        "\tВозврат Новый Массив;\nКонецФункции",
    )
    file_path = _repo_path(
        m, "ИБTransportManagementDevelop", "Конфигурация", "src", "CommonModules", "X", "Module.bsl"
    )
    inp = m.HookInput(
        {"tool_name": "Write", "tool_input": {"file_path": file_path, "content": source}}
    )

    assert m.ZAIWriteGuard().execute(inp) is None, "BSL пишет Opus — делегирование не требуется"


@pytest.mark.unit
def test_long_python_in_repo_still_blocked(monkeypatch):
    """Контроль: длинный .py внутри репозитория вне exempt-путей по-прежнему блокируется.

    Парная половина инварианта. Путь намеренно `src/` — не `tests/`, `docs/`, `data/`,
    `.claude/`: они освобождены, и тест позеленел бы, ничего не проверив.
    """
    m = _load()
    _no_delegation(monkeypatch)

    source = _long_source("def handler():", "    x{i} = {i}", "    return 1")
    file_path = _repo_path(m, "src", "pdf_framework", "service_probe.py")
    inp = m.HookInput(
        {"tool_name": "Write", "tool_input": {"file_path": file_path, "content": source}}
    )

    result = m.ZAIWriteGuard().execute(inp)
    assert result is not None, "длинный Python обязан требовать делегирования"
    # Точнее «не None», но по-прежнему без привязки к тексту сообщения: перефразировка
    # причины блокировки не должна ронять тест, а вот подмена block на system_message — должна.
    assert result._data.get("decision") == "block"
