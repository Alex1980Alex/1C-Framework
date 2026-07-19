"""Unit: shared/onec_change_scope (В2 260718 W1) — детект правки экспортного метода.

Условие применимости bsl_impact_analysis для честного applicable-знаменателя валидатора
(вместо survivorship-presence на всех задачах). Pure-ядро без git; I/O — инъекцией.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_MOD = Path(__file__).resolve().parents[3] / ".claude" / "hooks" / "shared" / "onec_change_scope.py"
_spec = importlib.util.spec_from_file_location("_onec_change_scope", _MOD)
cs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cs)

_EXPORTED = """Процедура ВнутренняяА()
    Возврат;
КонецПроцедуры

Функция ПубличнаяБ(Парам) Экспорт
    Возврат Парам;
КонецФункции

Процедура ВнутренняяВ()
    Х = 1;
КонецПроцедуры
"""

_MULTILINE_SIG = """Функция ДлиннаяСигнатура(
        Парам1,
        Парам2) Экспорт
    Возврат Парам1;
КонецФункции
"""


def test_spans_detects_only_exported():
    spans = cs.exported_method_spans(_EXPORTED)
    # ровно один экспортный метод — ПубличнаяБ (строки 5..7, 1-based)
    assert spans == [(5, 7)]


def test_spans_multiline_signature():
    """Экспорт на 4-й строке многострочной сигнатуры — распознан (в окне сигнатуры)."""
    spans = cs.exported_method_spans(_MULTILINE_SIG)
    assert len(spans) == 1 and spans[0][0] == 1


def test_spans_no_exported():
    assert cs.exported_method_spans("Процедура Локальная()\n  А = 1;\nКонецПроцедуры\n") == []


def test_spans_empty_text():
    assert cs.exported_method_spans("") == []


def test_spans_export_in_body_comment_not_exported():
    """code-verify #1в: `Экспорт` в //-комментарии ТЕЛА не делает метод экспортным."""
    txt = "Процедура Локальная()\n    // тут был Экспорт раньше\n    А = 1;\nКонецПроцедуры\n"
    assert cs.exported_method_spans(txt) == []


def test_spans_export_in_body_string_not_exported():
    """`Экспорт` в строковом литерале тела не делает метод экспортным (сигнатура закрыта)."""
    txt = 'Процедура Локальная()\n    Т = "Экспорт";\n    А = 1;\nКонецПроцедуры\n'
    assert cs.exported_method_spans(txt) == []


def test_spans_async_exported():
    """FN-фикс: `Асинхронная Функция ... Экспорт` распознаётся как экспортная."""
    txt = "Асинхронная Функция Публичная() Экспорт\n    Возврат 1;\nКонецФункции\n"
    assert cs.exported_method_spans(txt) == [(1, 3)]


def test_spans_no_end_of_method_no_crash():
    """Обрыв файла без КонецПроцедуры не роняет; спан до конца текста."""
    txt = "Функция Оборванная() Экспорт\n    Возврат 1;"
    spans = cs.exported_method_spans(txt)
    assert spans == [(1, 2)]


def test_spans_multiple_methods_mixed():
    """Несколько методов: только экспортные попадают, спаны корректны."""
    txt = (
        "Функция Э1() Экспорт\n Возврат 1;\nКонецФункции\n"  # 1..3
        "Процедура Л1()\n А=1;\nКонецПроцедуры\n"  # 4..6
        "Процедура Э2(П) Экспорт\n Б=П;\nКонецПроцедуры\n"  # 7..9
    )
    assert cs.exported_method_spans(txt) == [(1, 3), (7, 9)]


def _fake(changed, ranges_map, text):
    """Инъекции для edits_exported_method без git."""
    return dict(
        changed_paths=lambda _root: set(changed),
        owning_tree=lambda _root, rel: (Path("/x"), rel),
        line_ranges=lambda _root, rel: ranges_map.get(rel),
        read_text=lambda _p: text,
    )


def test_edits_exported_change_inside_exported_method():
    """Изменённая строка внутри экспортного метода (6) → applicable=True."""
    dep = _fake(["src/Module.bsl"], {"src/Module.bsl": [(6, 6)]}, _EXPORTED)
    assert cs.edits_exported_method("/root", **dep) is True


def test_edits_exported_change_only_in_local_method():
    """Изменения только в локальном методе (строка 2) → applicable=False."""
    dep = _fake(["src/Module.bsl"], {"src/Module.bsl": [(2, 2)]}, _EXPORTED)
    assert cs.edits_exported_method("/root", **dep) is False


def test_edits_exported_untracked_file_with_export():
    """line_ranges=None (untracked/новый) + есть экспорт → applicable=True (fail-closed)."""
    dep = _fake(["src/New.bsl"], {"src/New.bsl": None}, _EXPORTED)
    assert cs.edits_exported_method("/root", **dep) is True


def test_edits_exported_no_bsl_changed():
    dep = _fake([], {}, _EXPORTED)
    assert cs.edits_exported_method("/root", **dep) is False


def test_spans_async_keyword_asinh():
    """Грамматика bsl-parser: async-ключевое слово — `Асинх`, не «Асинхронная».
    Саботаж-фикс 2026-07-19: прежний regex такие методы не матчил вовсе (FN)."""
    txt = "Асинх Функция Публичная() Экспорт\n    Возврат 1;\nКонецФункции\n"
    assert cs.exported_method_spans(txt) == [(1, 3)]


def test_spans_english_keywords():
    """BSLLexer.g4: ключевые слова двуязычны — Procedure/Function/Export/EndProcedure."""
    txt = "Procedure PublicP() Export\n    A = 1;\nEndProcedure\nFunction LocalF()\n    Return 1;\nEndFunction\n"
    assert cs.exported_method_spans(txt) == [(1, 3)]


def test_spans_export_in_signature_string_literal_not_exported():
    """Дефолт параметра `П = "Экспорт"` в сигнатуре — НЕ экспорт (строки вырезаются)."""
    txt = 'Процедура Локальная(П = "Экспорт")\n    А = 1;\nКонецПроцедуры\n'
    assert cs.exported_method_spans(txt) == []


def test_edits_exported_session_paths_narrow():
    """session_paths сужают скан: грязный WIP-файл с экспортом игнорируется,
    сессионный файл без экспортных правок → False."""
    texts = {
        "wip/Module.bsl": _EXPORTED,
        "mine/Module.bsl": "Процедура Л()\n А=1;\nКонецПроцедуры\n",
    }
    dep = dict(
        changed_paths=lambda _r: set(texts),
        owning_tree=lambda _r, rel: (Path("/x"), rel),
        line_ranges=lambda _r, rel: None,
        read_text=lambda p: texts[Path(p).relative_to("/x").as_posix()],
    )
    assert (
        cs.edits_exported_method("/root", session_paths={r"C:\repo\mine\Module.bsl"}, **dep)
        is False
    )
    assert (
        cs.edits_exported_method("/root", session_paths={r"C:\repo\wip\Module.bsl"}, **dep) is True
    )
    # пустое пересечение (сессионные пути не из changed) → fallback на полный скан → True
    assert cs.edits_exported_method("/root", session_paths={r"C:\repo\other\X.bsl"}, **dep) is True


def test_edits_exported_files_scan_cap():
    """Перф-кап: сканируется не более _MAX_FILES_SCAN файлов (Stop-хук под таймаутом)."""
    reads = []
    many = {f"m/{i:03d}/Module.bsl" for i in range(200)}
    dep = dict(
        changed_paths=lambda _r: many,
        owning_tree=lambda _r, rel: (Path("/x"), rel),
        line_ranges=lambda _r, rel: None,
        read_text=lambda p: (reads.append(p), "Процедура Л()\n А=1;\nКонецПроцедуры\n")[1],
    )
    assert cs.edits_exported_method("/root", **dep) is False
    assert len(reads) == cs._MAX_FILES_SCAN


def test_edits_exported_file_without_export_not_applicable():
    """Изменён .bsl без экспортных методов → False даже при untracked."""
    dep = _fake(["src/Loc.bsl"], {"src/Loc.bsl": None}, "Процедура Л()\n А=1;\nКонецПроцедуры\n")
    assert cs.edits_exported_method("/root", **dep) is False
