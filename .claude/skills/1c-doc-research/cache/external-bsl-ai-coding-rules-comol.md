---
topic: "Внешний набор AI-правил кодирования 1С/BSL (comol/cursor_rules_1c → ai_rules_1c)"
object_type: "общий"
created: "2026-06-15"
last_verified: "2026-06-15"
doc_version: "8.3.27"
source_sections: []
source_chunk_ids: []
content_hash: ""
keywords:
  - "стандарты кодирования BSL"
  - "правила AI 1С cursor rules"
  - "зарезервированные имена свойств формы"
  - "БСП не изобретать велосипед ssl_search"
  - "канонические области модуля 1С"
  - "анти-паттерны 1С async Ждать"
  - "ошибки ручной генерации metadata XML"
  - "стратегия логирования ЖурналРегистрации"
  - "query-writing query-optimization 1С"
  - "comol ai_rules_1c"
---

# Внешний набор AI-правил кодирования 1С/BSL — comol/cursor_rules_1c

> ⚠ **Источник = внешний community-репозиторий, НЕ официальная документация 8.3.27.**
> По протоколу `1c-doc-research`: первоисточник — docs 8.3.27; это **дополнение** `[web]`.
> **Лицензия:** отсутствует явно — «Никакой лицензии, берите и используйте как хотите» (фактически public-domain).
> Репозиторий: portable rule-set для AI-разработки 1С (адаптеры Cursor / Claude Code / Codex / OpenCode / Kilo Code).
> Правила в `content/rules/*.md`, параметризация через `.dev.env` (`PREFIX`/`COMPANY`/`DEVELOPER`/`PLATFORM_VERSION`).

## 1. Структура модуля (`module-structure.md`)
Канонические шаблоны **обязательных областей** под каждый тип модуля: общий, объекта, менеджера, формы.
Предписаны препроцессорные директивы и обязательные секции внутри каждой категории. `[web]`

## 2. Именование и стиль (`dev-standards-core.md`)
Параметры/стиль/комментарии/именование/заголовки-документирования выводятся из `.dev.env`
(`PREFIX` — префикс объектов, `COMPANY`, `DEVELOPER`). Шаблоны комментариев-заголовков правки — для единообразия. `[web]`

## 3. Формы (`dev-standards-forms.md`, `form-reserved-names.md`)
**Зарезервированные имена свойств модуля формы — НЕЛЬЗЯ использовать как локальные переменные:**
`ПараметрыВыбора`, `СвязиПараметровВыбора`, `СписокВыбора`, `ПараметрыОтбора`, `ОтборСтрок`. `[web]`
Правила модификации управляемых форм + размещение элементов.

## 4. БСП-first (`1c-ssl-mcp` / `ssl_search`)
Перед написанием утилитного кода — проверить наличие готового в БСП («не изобретать велосипед»),
`ssl_search` валидирует, что эквивалента нет. `[web]`
(Согласуется с нашим опытом: `ОбщегоНазначения.*` вместо deprecated-глобальных, чтение реквизитов через БСП.)

## 5. Запросы (`query-writing.md`, `query-optimization.md`)
Отдельные правила на составление новых запросов и оптимизацию производительности; синтаксис сверяется
по версии платформы (`1C-docs-mcp`, `PLATFORM_VERSION`). `[web]`

## 6. Анти-паттерны (`anti-patterns.md`, `async-methods.md`)
- Тихая потеря исключения без `Ждать` (Await) в async-методах.
- `Асинх` в обработчиках событий формы (некорректный контекст).
- Неверные границы транзакций и блокировок. `[web]`

## 7. Ошибки ручной генерации metadata-XML (`metadata-xml-workarounds.md`)
- Пропуск `LineNumber` в табличных частях.
- Опечатка `PagesGroupExtInfo`.
- Пропуск `Page.enabled`. `[web]`

## 8. Логирование (`logging-strategy.md`)
Писать в `ЖурналРегистрации` с явными уровнями важности, структурированными `Данные`,
**без секретов/PII**, со стандартизованными именами событий. `[web]`

## Ключевые источники
- `[web]` github.com/comol/cursor_rules_1c (отображается как `ai_rules_1c`) — WebFetch 2026-06-15. Лицензия: нет (public-domain по заявлению автора).
- Структура: `content/rules/{dev-standards-core,module-structure,dev-standards-architecture,dev-standards-forms,metadata-xml-workarounds,anti-patterns,query-writing,query-optimization,async-methods,logging-strategy,form-reserved-names}.md`.
