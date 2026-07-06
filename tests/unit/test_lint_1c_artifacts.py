"""Unit-тесты линтера полноты 1С-артефактов (advisory). marker: unit.

Collision-immune (importlib). Покрытие: lint_text (analysis/implementation) — тонкий артефакт флагается
(score < 70, missing core-секции), каноничный проходит (100); _kind_from_name; exit 0 (advisory).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_S = Path(__file__).resolve().parents[2] / "scripts" / "lint_1c_artifacts.py"
_spec = importlib.util.spec_from_file_location("lint_1c_artifacts_t", _S)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

_CANON_ANALYSIS = """
# GKSTCPLK-1234 — ANALYSIS-REPORT
## 1. Описание задачи
### 1.1 Требования [REQ-1] ...
## 2. Задействованные объекты
- [MODIFIED] Документ.гкс_X — поле Y
## 3. Детальный анализ механизма
паттерн ...
## 4. План изменений
### Точка модификации 1: ...
## 6. Риски и открытые вопросы
## 7. Тест-план
## 9. Резюме
## 11. Следующие шаги: Маршрут /implement-1c-task
МЕТАДАННЫЕ: GKSTCPLK-1234
"""

_THIN_ANALYSIS = """
# GKSTCPLK-1234 — отчёт
## 1. Задача
Сделать форму.
## 2. Recall
нашёл.
## 5. План реализации
1. данные.
"""

_CANON_IMPL = """
# GKSTCPLK-1234 — Прогресс реализации
## Статус: Завершено
Pipeline mode: Full
## Выполненные точки модификации
### Точка 1: ... EDT errors: 0
- Отклонения от ANALYSIS-REPORT: нет
## Результаты тестирования
Тест 1: PASS
## Сообщение коммита
МЕТАДАННЫЕ: GKSTCPLK-1234
"""

_THIN_IMPL = """
# GKSTCPLK-1234 — Прогресс
## Статус: готово
## Реализовано
данные.
## Тестирование render-verify PASS
## Git: данные в dev
"""


def test_canonical_analysis_passes():
    r = mod.lint_text(_CANON_ANALYSIS, "analysis")
    assert r["ok"] and r["score"] == 100 and r["missing"] == []


def test_thin_analysis_flagged():
    r = mod.lint_text(_THIN_ANALYSIS, "analysis")
    assert not r["ok"] and r["score"] < 70
    # ключевые отсутствия пойманы
    miss = " ".join(r["missing"])
    assert "Требования" in miss and "Объекты" in miss and "Резюме" in miss


def test_canonical_impl_passes():
    r = mod.lint_text(_CANON_IMPL, "implementation")
    assert r["ok"] and r["score"] == 100 and r["missing"] == []


def test_thin_impl_flagged():
    r = mod.lint_text(_THIN_IMPL, "implementation")
    assert not r["ok"] and r["score"] < 70
    miss = " ".join(r["missing"])
    assert "Отклонения" in miss and "МЕТАДАННЫЕ" in miss  # ключевые core-секции пойманы


_IMPL_METADATA_MENTION_NO_MSG = """
# GKSTCPLK-1234 — Прогресс
## Статус: Завершено
## Выполненные точки модификации
### Точка 1: ... EDT errors: 0
## Отклонения от ANALYSIS-REPORT: нет
## Результаты тестирования
Тест 1: PASS
Метаданные объекта проверены через get_metadata.
"""

_IMPL_WITH_COMMIT_SECTION = """
# GKSTCPLK-1234 — Прогресс
## Статус: Завершено
## Выполненные точки модификации
### Точка 1: ...
## Отклонения от ANALYSIS-REPORT: нет
## Результаты тестирования
Тест 1: PASS
## Сообщение коммита
feat: Доработано X
Как было: ...
Как стало/список результатов: ...
МЕТАДАННЫЕ: GKSTCPLK-1234
"""


def test_impl_metadata_mention_without_commit_message_flagged():
    # tightening: голое упоминание «метаданные» (без футера МЕТАДАННЫЕ:JIRA и без секции
    # «## Сообщение коммита») больше НЕ засчитывается за наличие сообщения коммита
    r = mod.lint_text(_IMPL_METADATA_MENTION_NO_MSG, "implementation")
    assert any("Сообщение коммита" in m for m in r["missing"])


def test_impl_with_commit_section_present():
    r = mod.lint_text(_IMPL_WITH_COMMIT_SECTION, "implementation")
    assert not any("Сообщение коммита" in m for m in r["missing"])


def test_kind_autodetect():
    assert mod._kind_from_name("/x/ANALYSIS-REPORT.md") == "analysis"
    assert mod._kind_from_name("/x/IMPLEMENTATION-PROGRESS.md") == "implementation"
    assert mod._kind_from_name("/x/other.md") == "analysis"  # дефолт


def test_empty_not_ok():
    r = mod.lint_text("", "analysis")
    assert not r["ok"] and r["score"] == 0


def test_cli_exit_zero_advisory(tmp_path, capsys):
    # advisory → всегда exit 0, даже на тонком файле
    p = tmp_path / "ANALYSIS-REPORT.md"
    p.write_text(_THIN_ANALYSIS, encoding="utf-8")
    assert mod.main([str(p)]) == 0
    assert mod.main(["--json", str(p)]) == 0
