#!/usr/bin/env python3
"""Детект узкого условия применимости high-leverage 1С-инструментов (В2 260718, W1).

Ключ «переворота использования» (roadmap 260718 T-P0): presence high-leverage тулов
меряли на ВСЕХ 331 задачах (survivorship-caveat ADR-035). Для честного baseline и
безопасного будущего hard-промоута нужно знать, где инструмент вообще ПРИМЕНИМ.

Пока один детектор — `edits_exported_method`: правка/добавление **экспортного** метода
(`Процедура/Функция ... Экспорт`) = условие применимости `bsl_impact_analysis` (правка
экспортной точки → потенциальная регрессия «кто вызывает»). Reuse changed-.bsl/changed-lines
из `sonar_rescan_state` (не дублируем git-логику). Pure-ядро (`exported_method_spans`,
`_intersects`) тестируемо без git; I/O-обёртка инъектируема.

Флип advisory→hard ЗДЕСЬ не делается — это только измерительный сигнал `impact_applicable`
для event-лога + валидатора. Промоут — после окна (T-P0.5).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

# Заголовок метода / конец / признак экспорта. Ключевые слова BSL двуязычны (официальная
# грамматика 1c-syntax/bsl-parser BSLLexer.g4: PROCEDURE_KEYWORD = 'ПРОЦЕДУРА'|'PROCEDURE',
# EXPORT_KEYWORD = 'ЭКСПОРТ'|'EXPORT', ASYNC_KEYWORD = 'АСИНХ'|'ASYNC') — кириллица-only
# давала FN на англоязычных модулях. Async-префикс — именно `Асинх`/`Async` (8.3.18+),
# прежний `Асинхронная` был неверным словом (async-методы вообще не матчились заголовком);
# `Асинх(?:ронная)?` оставлен толерантным к обоим. re.IGNORECASE — нестандартный регистр.
# Методы в BSL НЕ вложены.
_METHOD_HEADER = re.compile(
    r"^\s*(?:(?:Асинх(?:ронная)?|Async)\s+)?(Процедура|Функция|Procedure|Function)\b",
    re.IGNORECASE,
)
_METHOD_END = re.compile(
    r"^\s*(КонецПроцедуры|КонецФункции|EndProcedure|EndFunction)\b", re.IGNORECASE
)
_EXPORT = re.compile(r"\b(Экспорт|Export)\b", re.IGNORECASE)
_STRING_LIT = re.compile(r'"[^"]*(?:""[^"]*)*"?')

# Страховочный потолок строк сигнатуры (реальные ≤ этого; больше — почти наверняка обрыв/тело).
_SIGNATURE_MAX_LINES = 12

# Перф-кап: Stop-хук зовёт детект best-effort под таймаутом; на грязном work-tree
# (чужой WIP в сабмодулях) changed-файлов бывают сотни, а каждый = чтение + 2 git-вызова
# (`ls-files` + `diff`) в line_ranges. Без потолка worst-case (нет экспортных правок →
# нет short-circuit) уходит в минуты и таймаут убивает ВЕСЬ хук. Скан детерминирован (sorted).
_MAX_FILES_SCAN = 50


def _strip_comment(line: str) -> str:
    """Отрезать строчный `//`-комментарий и `"…"`-строковые литералы. Комментарий — чтобы
    `// … Экспорт` не давал ложный экспорт (code-verify #1в); литералы — чтобы дефолт
    параметра `П = "Экспорт"` в сигнатуре не срабатывал как ключевое слово."""
    line = _STRING_LIT.sub('""', line)
    idx = line.find("//")
    return line[:idx] if idx >= 0 else line


def exported_method_spans(text: str) -> list[tuple[int, int]]:
    """1-based строковые спаны [(start, end)] ЭКСПОРТНЫХ методов (заголовок → Конец…).

    Метод экспортный, если `Экспорт` встречается **в СИГНАТУРЕ** — от заголовка до строки,
    где закрывается список параметров (баланс скобок вернулся к 0). Экспорт в BSL стоит
    после `)` сигнатуры, поэтому за её пределами (в теле) `Экспорт` в комментарии/строке
    ложно НЕ срабатывает (фикс code-verify #1в: прежнее «окно N строк» захватывало первые
    строки тела). Комментарии `//` срезаются. Методы в BSL не вложены → плоский скан."""
    lines = text.splitlines()
    n = len(lines)
    spans: list[tuple[int, int]] = []
    i = 0
    while i < n:
        if _METHOD_HEADER.match(lines[i]):
            start = i + 1  # 1-based
            exported = _signature_is_exported(lines, i, n)
            j = i + 1
            while j < n and not _METHOD_END.match(lines[j]):
                j += 1
            end = (j + 1) if j < n else n  # включая строку Конец…
            if exported:
                spans.append((start, end))
            i = j + 1
        else:
            i += 1
    return spans


def _signature_is_exported(lines: list[str], header_idx: int, n: int) -> bool:
    """Есть ли `Экспорт` в сигнатуре метода (заголовок → закрытие списка параметров).

    Скобочный баланс от `(` заголовка: сигнатура закрыта, когда depth вернулся к 0 после
    открытия. `Экспорт` ищем только в строках сигнатуры (с вырезанными `//`-комментами)."""
    depth = 0
    opened = False
    for k in range(header_idx, min(header_idx + _SIGNATURE_MAX_LINES, n)):
        code = _strip_comment(lines[k])
        if _EXPORT.search(code):
            return True
        depth += code.count("(") - code.count(")")
        if "(" in code:
            opened = True
        if opened and depth <= 0:
            break  # список параметров закрыт — дальше тело, Экспорт там не бывает
    return False


def _intersects(ranges: list[tuple[int, int]], spans: list[tuple[int, int]]) -> bool:
    """Пересекается ли хоть один changed-range с хоть одним export-span (1-based incl.)."""
    for rs, re_ in ranges:
        for ss, se in spans:
            if rs <= se and ss <= re_:
                return True
    return False


def _session_tail(p: str) -> str:
    """Нормализованный хвост пути (последние 2 сегмента, lower, forward-slash) — ключ
    сопоставления session-путей (абсолютных, из транскрипта) с repo-относительными changed."""
    parts = p.replace("\\", "/").lower().rstrip("/").split("/")
    return "/".join(parts[-2:])


def edits_exported_method(
    root,
    *,
    changed_paths: Callable[[object], set[str]] | None = None,
    owning_tree: Callable[[Path, str], tuple[Path, str]] | None = None,
    line_ranges: Callable[[object, str], list[tuple[int, int]] | None] | None = None,
    read_text: Callable[[Path], str] | None = None,
    session_paths: set[str] | None = None,
) -> bool:
    """True, если изменённые .bsl касаются экспортного метода (условие применимости impact).

    Дефолты берут git-логику из `sonar_rescan_state` (changed-.bsl + changed-lines vs HEAD);
    инъекция зависимостей — для юнит-тестов без git. Fail-safe: ошибка ЧТЕНИЯ файла → пропуск
    файла; ошибка `changed_paths` → False (не роняем гейт). `line_ranges is None` (untracked/
    дифф не получен) + есть экспорт → **applicable=True** (fail-closed «применимо»: impact-analysis
    на новом/непрослеживаемом .bsl с экспортом точно уместен).

    `session_paths` — .bsl-пути, тронутые ЭТОЙ сессией (из транскрипта): work-tree бывает
    хронически грязным чужим WIP (живой замер 2026-07-19: 159 changed-.bsl в сабмодулях) →
    без сужения applicable вырождается в «всегда True» и честный знаменатель валидатора
    (В2/рек.3) ломается. Непустой набор → скан только пересечения (по хвосту пути);
    пустой/None → прежний полный скан (правки через внешние инструменты не теряем)."""
    if changed_paths is None or owning_tree is None or line_ranges is None:
        try:
            from shared import sonar_rescan_state as _srs
        except Exception:
            return False
        changed_paths = changed_paths or _srs.changed_bsl_paths
        owning_tree = owning_tree or _srs._owning_tree
        line_ranges = line_ranges or _srs.changed_line_ranges
    _read = read_text or (lambda p: Path(p).read_text(encoding="utf-8", errors="replace"))

    root_p = Path(root)
    try:
        changed = changed_paths(root)
    except Exception:
        return False
    if session_paths:
        tails = {_session_tail(p) for p in session_paths}
        narrowed = {rel for rel in changed if _session_tail(rel) in tails}
        # пустое пересечение (правки уже закоммичены / пути не совпали) → полный скан
        if narrowed:
            changed = narrowed
    for rel in sorted(changed)[:_MAX_FILES_SCAN]:
        try:
            tree, rel_in = owning_tree(root_p, rel)
            text = _read(tree / rel_in)
        except OSError:
            continue
        spans = exported_method_spans(text)
        if not spans:
            continue
        try:
            ranges = line_ranges(root, rel)
        except Exception:
            ranges = None
        if ranges is None:  # untracked/нет дифа → применимо (есть экспорт в затронутом файле)
            return True
        if _intersects(ranges, spans):
            return True
    return False


__all__ = ["exported_method_spans", "edits_exported_method", "_session_tail"]
