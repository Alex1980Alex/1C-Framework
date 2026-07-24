"""User-mandated BSL code rules — machine-checkable subset.

Codifies the customer's recurring 1C code-review findings (stored as
feedback-* memory notes) into deterministic checks, so compliance no longer
depends on memory surfacing at generation time. Advisory only: the hook
returns findings to Claude in the same turn; nothing is blocked.

Rule sources (memory notes): feedback-1c-strshablon-not-concat,
feedback-1c-predefined-not-hardcode-codes, feedback-1c-bsp-deprecated-globals,
feedback-1c-no-subquery-wrap-use-temp-tables, feedback-1c-group-by-unlimited-string,
implement-1c-task Правило 1 (JIRA-маркеры), БСП-стандарт ТекущаяДатаСеанса.

Full (non-machinable) rule set lives in bsl-development SKILL.md,
section «Стоячие правила пользователя».
"""

from __future__ import annotations

import re
from typing import Any

# Lines that belong to a 1C query text: leading `|` continuation. Rules that
# target imperative BSL (concatenation, globals) must skip those lines.
_QUERY_LINE = re.compile(r"^\s*\|")

# String assembled from 3+ parts: a string literal present AND >=2 plus signs
# on the line (canonical review case: А + "." + Б). A single `"x" + Y` is
# tolerated - память explicitly allows trivial one-off concatenation.
_STRING_LITERAL = re.compile(r'"[^"\n]*"')

# Catalog element addressed by hard-coded code/name literal.
_FIND_BY_LITERAL = re.compile(r"(НайтиПоКоду|НайтиПоНаименованию)\s*\(\s*\"")

# Deprecated globals that must go through БСП wrappers. Negative lookbehind
# rejects the wrapped forms (ОбщегоНазначения.СообщитьПользователю etc.).
_DEPRECATED_GLOBAL = re.compile(
    r"(?<![\wА-Яа-яЁё.])(СообщитьПользователю|ПодробноеПредставлениеОшибки|КраткоеПредставлениеОшибки)\s*\("
)

# Nested subquery in ИЗ — spans lines, `|` continuations allowed inside.
_SUBQUERY_IN_FROM = re.compile(r"\bИЗ\b[\s|]*\(\s*[\s|]*ВЫБРАТЬ", re.IGNORECASE)

_TEKUSHCHAYA_DATA = re.compile(r"(?<![\wА-Яа-яЁё.])ТекущаяДата\s*\(")

_GROUP_BY = re.compile(r"СГРУППИРОВАТЬ\s+ПО", re.IGNORECASE)
_LONG_STRING_FIELD = re.compile(r"\.(Адрес|ЮрАдрес|Комментарий)\b")

_JIRA_MARKER = re.compile(r"//\s*G[A-Z]+-\d+")

_CODE_LINE = re.compile(r"\S")
_COMMENT_LINE = re.compile(r"^\s*//")

# Own procedure/function declarations may legally reuse deprecated-global names
# (wrapper modules) - the declaration line itself is not a call site.
_METHOD_DECL = re.compile(r"\s*(Процедура|Функция|Procedure|Function)\s", re.IGNORECASE)


def _line_no(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def check_fragment(text: str, is_fragment: bool = True) -> list[dict[str, Any]]:
    """Check an added/modified BSL fragment against the user rule set.

    is_fragment=True for Edit/searchReplace payloads (enables fragment-scoped
    hints like the JIRA-marker rule); False for whole-module writes.
    Returns findings: {rule, severity, line, message}.
    """
    findings: list[dict[str, Any]] = []
    lines = text.split("\n")

    for idx, line in enumerate(lines, start=1):
        if _QUERY_LINE.match(line) or _COMMENT_LINE.match(line):
            continue
        # Mask string literals, then drop a trailing // comment: plus signs are
        # counted only in actual code (review fix: "А+Б+В" formulas, one-line
        # query literals and tail comments must not trip the concat rule).
        masked = _STRING_LITERAL.sub('""', line)
        code_part = masked.split("//", 1)[0]
        is_declaration = _METHOD_DECL.match(line) is not None
        if '""' in code_part and code_part.count("+") >= 2 and "СтрШаблон" not in line:
            findings.append(
                {
                    "rule": "strshablon-not-concat",
                    "severity": "warn",
                    "line": idx,
                    "message": "Сборка строки конкатенацией `+` с русским литералом - используй "
                    'СтрШаблон("%1...", ...) [память feedback-1c-strshablon-not-concat, '
                    "ревью GKSTCPLK-2573]",
                }
            )
        if _DEPRECATED_GLOBAL.search(code_part) and not is_declaration:
            findings.append(
                {
                    "rule": "bsp-deprecated-globals",
                    "severity": "warn",
                    "line": idx,
                    "message": "Устаревший глобальный метод - используй БСП: "
                    "ОбщегоНазначения.СообщитьПользователю / ОбработкаОшибок.Подробное(Краткое)"
                    "ПредставлениеОшибки [память feedback-1c-bsp-deprecated-globals, ревью GKSTCPLK-2521]",
                }
            )
        if _TEKUSHCHAYA_DATA.search(code_part):
            findings.append(
                {
                    "rule": "tekushchaya-data-seansa",
                    "severity": "hint",
                    "line": idx,
                    "message": "ТекущаяДата() в серверном коде - БСП-стандарт: ТекущаяДатаСеанса()",
                }
            )

    comment_lines = {idx for idx, ln in enumerate(lines, start=1) if _COMMENT_LINE.match(ln)}

    for m in _FIND_BY_LITERAL.finditer(text):
        if _line_no(text, m.start()) in comment_lines:
            continue
        findings.append(
            {
                "rule": "predefined-not-hardcode",
                "severity": "warn",
                "line": _line_no(text, m.start()),
                "message": "Поиск элемента справочника по коду/наименованию-литералу - используй "
                "предопределённые элементы (v8std #std697): Справочники.<X>.<ИмяПредопределённого> / "
                "ПредопределённоеЗначение() [память feedback-1c-predefined-not-hardcode-codes, "
                "ревью GKSTCPLK-2671]",
            }
        )

    for m in _SUBQUERY_IN_FROM.finditer(text):
        findings.append(
            {
                "rule": "no-subquery-wrap",
                "severity": "warn",
                "line": _line_no(text, m.start()),
                "message": "Вложенный подзапрос в ИЗ - «так никогда не делай»: временные таблицы "
                "(ПОМЕСТИТЬ ВТ_X + второй запрос пакета) [память "
                "feedback-1c-no-subquery-wrap-use-temp-tables, GKSTCPLK-2692]",
            }
        )

    if _GROUP_BY.search(text):
        # Scope the long-string field to QUERY lines only (review fix: imperative
        # `Объект.Комментарий = ...` in the same fragment must not cross-trip).
        m = None
        for idx, ln in enumerate(lines, start=1):
            if _QUERY_LINE.match(ln):
                fm = _LONG_STRING_FIELD.search(ln)
                if fm:
                    m = fm
                    m_line = idx
                    break
        if m:
            findings.append(
                {
                    "rule": "group-by-long-string",
                    "severity": "hint",
                    "line": m_line,
                    "message": "СГРУППИРОВАТЬ ПО рядом с полем строки неограниченной длины "
                    "(Адрес/Комментарий) - группируй по ссылочным ключам в ВТ, детали джойни вторым "
                    "запросом [память feedback-1c-group-by-unlimited-string, GKSTCPLK-2536]",
                }
            )

    if is_fragment and not _JIRA_MARKER.search(text):
        code_lines = [ln for ln in lines if _CODE_LINE.search(ln) and not _COMMENT_LINE.match(ln)]
        if len(code_lines) >= 5:
            findings.append(
                {
                    "rule": "jira-task-markers",
                    "severity": "hint",
                    "line": 1,
                    "message": "Добавленный блок без маркеров задачи - оберни "
                    "// <JIRA> Начало ... // <JIRA> Конец (Правило 1 implement-1c-task)",
                }
            )

    return findings


def format_findings(findings: list[dict[str, Any]], source_label: str, cap: int = 8) -> str:
    """Render findings for the hook's advisory message."""
    shown = findings[:cap]
    parts = [
        f"[bsl-user-rules] {len(findings)} замечание(й) по своду правил пользователя в {source_label}:"
    ]
    for f in shown:
        parts.append(f"  L{f['line']} [{f['severity']}/{f['rule']}] {f['message']}")
    if len(findings) > cap:
        parts.append(f"  ... и ещё {len(findings) - cap}")
    parts.append(
        "Исправь до Sonar-скана. Полный свод: bsl-development SKILL.md → «Стоячие правила пользователя»."
    )
    return "\n".join(parts)
