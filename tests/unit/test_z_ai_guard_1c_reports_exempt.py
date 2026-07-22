"""z-ai-write-guard: артефакты 1С-пайплайна освобождены, прочая длинная .md-проза - нет.

Тот же класс, что test_z_ai_guard_bsl_exempt.py: пиним ОБЕ стороны инварианта,
иначе откат исключения останется зелёным.

Ловушки (проверены на живом гарде):
  - файл ВНЕ репозитория освобождается раньше проверки расширения -> tmp_path не годится,
    пути должны быть внутри _PROJECT_ROOT;
  - .claude/ и pipeline/ уже в _MD_EXEMPT_PREFIXES -> контрольный кейс берём из
    configuration/ с другим именем файла;
  - без заглушек shared.llm_health / shared.session_state тест зависит от состояния
    машины: любой llm_complete в окне 30 мин пропускает запись мимо гарда, и позитивные
    кейсы зеленеют по ложной причине (а негативные - краснеют).
"""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"

_TASK_DIR = "configuration/260304_GKSTCPLK-2182 Тестовая задача/docs/260722_GKSTCPLK-2673"


def _load_guard():
    sys.path.insert(0, str(_HOOKS))
    try:
        spec = importlib.util.spec_from_file_location(
            "z_ai_write_guard", _HOOKS / "z-ai-write-guard.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(_HOOKS))


def _no_delegation(monkeypatch) -> None:
    """Гард считает: провайдер жив, делегирования в сессии НЕ было.

    Импорты в хуке локальные, поэтому подменяем sys.modules (зеркало
    _no_delegation из test_z_ai_guard_bsl_exempt.py).
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


def _verdict(module, rel_path: str, lines: int):
    """Вердикт гарда на запись .md указанной длины (None = пропустил)."""
    inp = module.HookInput(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {
                "file_path": str(Path(module._PROJECT_ROOT) / rel_path),
                "content": "\n".join(f"строка отчёта {i}" for i in range(lines)),
            },
        }
    )
    return module.ZAIWriteGuard().execute(inp)


def _assert_blocked(module, rel_path: str, lines: int) -> None:
    result = _verdict(module, rel_path, lines)
    assert result is not None, f"{rel_path} обязан требовать делегирования"
    # Привязка к decision, а не к тексту: перефразировка причины тест не роняет,
    # а подмена block на system_message - должна.
    assert result._data.get("decision") == "block"


def test_analysis_report_exempt(monkeypatch):
    """ANALYSIS-REPORT.md в папке 1С-задачи пишется без делегирования."""
    _no_delegation(monkeypatch)
    module = _load_guard()
    assert _verdict(module, f"{_TASK_DIR}/ANALYSIS-REPORT.md", 500) is None


def test_implementation_progress_exempt(monkeypatch):
    """IMPLEMENTATION-PROGRESS.md - тот же артефакт этапа реализации."""
    _no_delegation(monkeypatch)
    module = _load_guard()
    assert _verdict(module, f"{_TASK_DIR}/IMPLEMENTATION-PROGRESS.md", 300) is None


def test_other_large_md_in_configuration_still_blocked(monkeypatch):
    """Обратная сторона: произвольная длинная .md в той же папке по-прежнему блокируется."""
    _no_delegation(monkeypatch)
    module = _load_guard()
    _assert_blocked(module, f"{_TASK_DIR}/Заметки по задаче.md", 500)


def test_analysis_report_outside_configuration_still_blocked(monkeypatch):
    """Скоуп узкий: то же имя вне configuration/ не освобождается."""
    _no_delegation(monkeypatch)
    module = _load_guard()
    _assert_blocked(module, "src/reports/ANALYSIS-REPORT.md", 500)


def test_analysis_report_in_lookalike_dir_still_blocked(monkeypatch):
    """Скоуп - сегмент пути, а не подстрока: my_configuration/ не освобождается.

    Без якоря на границу сегмента любой каталог, чьё имя ЗАКАНЧИВАЕТСЯ на
    'configuration', тихо получал бы исключение.
    """
    _no_delegation(monkeypatch)
    module = _load_guard()
    _assert_blocked(module, "src/my_configuration/docs/ANALYSIS-REPORT.md", 500)


def test_small_md_never_blocked(monkeypatch):
    """Порог 50 строк не тронут."""
    _no_delegation(monkeypatch)
    module = _load_guard()
    assert _verdict(module, f"{_TASK_DIR}/Заметки по задаче.md", 10) is None
