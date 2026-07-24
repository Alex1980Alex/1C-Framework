"""User-mandated BSL rules linter (2026-07-24) - detector unit tests.

Codifies recurring customer code-review findings into machine checks; each
detector gets a positive case and a false-positive guard, so the rule set
stays honest as it grows.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_CORE_PATH = (
    Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "shared" / "bsl_user_rules.py"
)
_spec = importlib.util.spec_from_file_location("bsl_user_rules", _CORE_PATH)
core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(core)


def _rules(text: str, is_fragment: bool = True) -> set[str]:
    return {f["rule"] for f in core.check_fragment(text, is_fragment=is_fragment)}


# --- strshablon-not-concat ---


def test_concat_three_parts_flagged() -> None:
    assert "strshablon-not-concat" in _rules('ИмяФайла = Наименование + "." + Расширение;')


def test_concat_trivial_single_plus_tolerated() -> None:
    assert "strshablon-not-concat" not in _rules('Сообщение = "Ошибка: " + Описание;')


def test_concat_inside_query_line_skipped() -> None:
    assert "strshablon-not-concat" not in _rules('\t|\tПоле1 + "." + Поле2 КАК Имя')


def test_concat_pluses_inside_literal_tolerated() -> None:
    # Review FP-guard: plus signs INSIDE a string literal are not concatenation.
    assert "strshablon-not-concat" not in _rules('Формула = "А+Б+В";')


def test_concat_pluses_in_tail_comment_tolerated() -> None:
    assert "strshablon-not-concat" not in _rules('Имя = ПолноеИмя; // было: Фамилия + " " + Имя')


def test_own_procedure_named_like_deprecated_global_tolerated() -> None:
    # Review FP-guard: wrapper modules legally declare same-named procedures.
    assert "bsp-deprecated-globals" not in _rules(
        "Процедура СообщитьПользователю(Знач Текст) Экспорт"
    )


def test_group_by_field_in_imperative_code_tolerated() -> None:
    # Review FP-guard: `.Комментарий` in imperative code must not cross-trip
    # with a СГРУППИРОВАТЬ ПО elsewhere in the same fragment.
    text = 'Объект.Комментарий = "х";\nТекст = "ВЫБРАТЬ Т.Поле\n\t|СГРУППИРОВАТЬ ПО Т.Поле";'
    assert "group-by-long-string" not in _rules(text)


def test_find_by_code_in_comment_tolerated() -> None:
    assert "predefined-not-hardcode" not in _rules('// Было: Спр.НайтиПоКоду("123")')


def test_concat_with_strshablon_on_line_tolerated() -> None:
    assert "strshablon-not-concat" not in _rules('Имя = СтрШаблон("%1.%2", А, Б) + "суффикс" + Х;')


# --- predefined-not-hardcode ---


def test_find_by_code_literal_flagged() -> None:
    assert "predefined-not-hardcode" in _rules(
        'Показатель = Справочники.гкс_Показатели.НайтиПоКоду("гкс000003");'
    )


def test_find_by_name_literal_flagged() -> None:
    assert "predefined-not-hardcode" in _rules('Эл = Спр.НайтиПоНаименованию("Влажность");')


def test_find_by_code_variable_tolerated() -> None:
    assert "predefined-not-hardcode" not in _rules("Эл = Спр.НайтиПоКоду(КодИзНастройки);")


# --- bsp-deprecated-globals ---


def test_global_soobshit_flagged() -> None:
    assert "bsp-deprecated-globals" in _rules('СообщитьПользователю("текст");')


def test_bsp_wrapped_soobshit_tolerated() -> None:
    assert "bsp-deprecated-globals" not in _rules('ОбщегоНазначения.СообщитьПользователю("текст");')


def test_global_error_repr_flagged_wrapped_tolerated() -> None:
    assert "bsp-deprecated-globals" in _rules(
        "Т = ПодробноеПредставлениеОшибки(ИнформацияОбОшибке());"
    )
    assert "bsp-deprecated-globals" not in _rules(
        "Т = ОбработкаОшибок.ПодробноеПредставлениеОшибки(ИнформацияОбОшибке());"
    )


# --- no-subquery-wrap ---


def test_subquery_in_from_flagged() -> None:
    query = (
        'Текст = "ВЫБРАТЬ Т.Поле\n'
        "\t|ИЗ (ВЫБРАТЬ Х.Поле КАК Поле\n"
        '\t|\tИЗ Справочник.Х КАК Х) КАК Т";'
    )
    assert "no-subquery-wrap" in _rules(query)


def test_plain_from_tolerated() -> None:
    assert "no-subquery-wrap" not in _rules(
        'Текст = "ВЫБРАТЬ Т.Поле ПОМЕСТИТЬ ВТ_X ИЗ Справочник.Х КАК Т";'
    )


# --- tekushchaya-data-seansa ---


def test_tekushchaya_data_flagged() -> None:
    assert "tekushchaya-data-seansa" in _rules("Дата = ТекущаяДата();")


def test_tekushchaya_data_seansa_tolerated() -> None:
    assert "tekushchaya-data-seansa" not in _rules("Дата = ТекущаяДатаСеанса();")


# --- group-by-long-string ---


def test_group_by_with_kommentariy_hinted() -> None:
    text = '\t|СГРУППИРОВАТЬ ПО\n\t|\tТаб.Комментарий";'
    assert "group-by-long-string" in _rules(text)


def test_group_by_refs_only_tolerated() -> None:
    assert "group-by-long-string" not in _rules('\t|СГРУППИРОВАТЬ ПО Таб.Организация";')


# --- jira-task-markers ---

_FIVE_CODE_LINES = "А = 1;\nБ = 2;\nВ = 3;\nГ = 4;\nД = 5;\nЕ = 6;"


def test_fragment_without_marker_hinted() -> None:
    assert "jira-task-markers" in _rules(_FIVE_CODE_LINES, is_fragment=True)


def test_fragment_with_marker_tolerated() -> None:
    assert "jira-task-markers" not in _rules(
        "// GKSTCPLK-2685 Начало\n" + _FIVE_CODE_LINES, is_fragment=True
    )


def test_full_module_not_marker_checked() -> None:
    assert "jira-task-markers" not in _rules(_FIVE_CODE_LINES, is_fragment=False)


# --- formatting ---


def test_format_findings_caps_and_labels() -> None:
    findings = core.check_fragment('ИмяФайла = А + "." + Б;')
    msg = core.format_findings(findings, "Module.bsl")
    assert "[bsl-user-rules]" in msg
    assert "Module.bsl" in msg
    assert "strshablon-not-concat" in msg
