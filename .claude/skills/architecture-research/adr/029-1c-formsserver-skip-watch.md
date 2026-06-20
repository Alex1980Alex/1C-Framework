# ADR-029: 1c-formsserver — SKIP (watch), не adopt сейчас

**Дата:** 2026-06-20
**Статус:** accepted (решение = SKIP/watch)
**Исследование:** [../cache/1c-form-skd-spreadsheet-tooling-2026.md](../cache/1c-form-skd-spreadsheet-tooling-2026.md)

## Контекст
Live-свип 2026-06-20 нашёл [`Desko77/1c-formsserver`](https://github.com/Desko77/1c-formsserver) — выделенный MCP для форм 1С (3 формата, 18 тулов). Изначально выглядел как закрывающий EDT-MCP form-gap, в т.ч. **триггер задачи** — `horizontalStretch` не в assignable-списке `modify_metadata` (пришлось править `Form.form` XML напрямую). Нужна оценка adopt.

## Решение: SKIP (WATCH)
`[web]` Факты (WebFetch README): **MIT** ✓; но **7★ / 0 releases / 17 commits / single-author** = ранняя стадия. 18 тулов = генерация/валидация/конвертация/поиск/reference; Python (fastmcp/lxml/pydantic), транспорт streamable-http (не stdio).

`[own]` НЕ adopt сейчас, потому что:
1. **Не решает триггер.** Это generator + validator + **converter**, НЕ in-place property-editor — `[web]` «no explicit write-to-disk; output is XML returned to Claude», styling-props (size/stretch/width) в доках не описаны. Значит `horizontalStretch`/правка свойств существующих форм остаётся EDT-модель + `Form.form` XML + `clean_project` `[exp]`.
2. **Незрелость.** 7★/0 releases против нашего bar (`[exp]` ecosystem-cache: production ≈ ★>100). Зависеть в проде рано.
3. **Уникальная ценность не востребована сейчас.** `convert_form` (logform↔managed↔edt, semantic-preserving) + form-gen из JSON/metadata + forms-KB — для СОЗДАНИЯ/МИГРАЦИИ форм; мы правим существующие.
4. **Overlap.** Генерация/скриншот частично дублируют EDT-MCP (live-модель, validated). 1c-formsserver — offline-XML (другая ниша), но возвращает XML Claude → всё равно сами write+reload (= наш текущий путь).

## Последствия
### Положительные
- Ничего не ставим/не сопровождаем; зафиксированы watch-критерии.
- Его **forms-KB** (`get_form_prompt` = «complete knowledge base on Form.xml», `get_form_schema`, `get_xcore_model_info`) — ценный reference; можно заимствовать как knowledge БЕЗ запуска сервера.
### Отрицательные
- При будущей потребности в form-format-конверсии/генерации — вернуться к оценке (повторный research).

## Watch-критерии (revisit когда)
- Появится задача **генерации форм из спецификации** ИЛИ **миграции формата** (logform↔edt) → `convert_form`/`generate_form` реально нужны.
- Инструмент созреет: releases + рост ★ + **in-place write со styling-props** (тогда закрыл бы и триггер).
- Нужен offline form-tooling без запущенного EDT.

## Альтернативы (текущий стек — остаётся)
- **EDT-MCP** — основной: live-модель, form snapshot/screenshot (JVM-флаг `nativeFormBufferedLayoutRender` включён 2026-06-20), modify в пределах assignable.
- **`Form.form` XML + `clean_project`** — для свойств вне assignable (`horizontalStretch` и др.) `[exp]`.
- **`1c-mcp-crud execute_code`** — runtime/динамика форм.

## Связанные файлы
- [cache 1c-form-skd-spreadsheet-tooling-2026.md](../cache/1c-form-skd-spreadsheet-tooling-2026.md) (детальные факты + tool-карта)
- skill [edt-mcp](../../edt-mcp/SKILL.md)
