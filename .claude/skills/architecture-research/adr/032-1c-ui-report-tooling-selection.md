# ADR-032: Выбор инструментария AI-правки 1C UI/report-артефактов — cc-1c-skills + codepilot1c-edt + EDT-MCP

**Дата:** 2026-06-21
**Статус:** accepted
**Исследование:** [../cache/1c-form-skd-spreadsheet-tooling-2026.md](../cache/1c-form-skd-spreadsheet-tooling-2026.md) (рейтинг ≥12 решений + LIVE-прогоны)
**Связь:** конкретизирует [ADR-030](030-1c-ui-report-artifact-editing-strategy.md) (стратегия слой-под-артефакт) и [ADR-031](031-cc-1c-skills-adopt-offline-mxl-dcs-editor.md) (adopt cc-1c-skills)

## Контекст

Два свипа GitHub (2026-06-21) дали рейтинг ≥12 инструментов для 4 способностей: анализ DCS, правка/создание DCS, табличный документ (`.mxl/.mxlx`) правка+создание, формы анализ+создание. Большинство — нишевые (runtime-в-базе, read-only MCP, бинарные распаковщики, OneScript-GUI). Кредитоспособны для нашего стека ТРИ, и они **дополняют**, а не заменяют друг друга. Нужно зафиксировать роли, чтобы не выбирать инструмент ad-hoc на каждой задаче и не плодить новые MCP (запрет из ADR-030).

Что проверено в сессии (не по README):
- **cc-1c-skills** — live end-to-end (ADR-031): round-trip `.mxlx` (84/84 текст-значения), чтение `.dcs` (наборы/поля/параметры), `skd-edit add-parameter`, **полный цикл правка→`update_database`→рендер PDF→откат git CLEAN**.
- **codepilot1c-edt** — live read контента: `inspect_template`/`dcs_manage` **сломаны** (0/«файл не найден»); write-поверхность подтверждена source-инспекцией + шлюзом `edt_validate_request` (полную мутацию не исполняли).
- **EDT-MCP (DitriXNew, наш)** — live: `get_project_errors`, `update_database` (деплой recompiled `.mxlx` сработал), `validate_query(dcsMode)`.

## Решение

**Трёхинструментальный стек с разделением ролей** [own]:

1. **cc-1c-skills (offline, ОСНОВНОЙ)** — дефолт для чтения и правки существующих артефактов-файлов: `.dcs` (`skd-info/edit/compile/validate`), `.mxl/.mxlx` (`mxl-decompile/compile/info/validate`), формы (`form-info/compile/edit/add`). Вендорено `external/cc-1c-skills` (pin `3d36c20`). Закрывает все 4 способности offline; единственный с offline round-trip табличного документа. [exp]
2. **codepilot1c-edt (EDT-live, ЗАПИСЬ при необходимости модели)** — когда нужна мутация, осознающая модель EDT (каскад ссылок; layout-свойства FormField, которые EDT-MCP не выставляет). **НЕ для чтения** существующего контента макетов/`.dcs` (сломано). Opt-in: конфликт порта `:8765` с EDT-MCP + AGPL-3.0. [own]
3. **EDT-MCP / DitriXNew (BASELINE, наш текущий)** — метаданные CRUD, `update_database` (деплой в ИБ), `validate_query` (вкл. DCS-режим), `get_project_errors`/`revalidate`, form inspect/screenshot. «Клей» + конвейер деплоя. [exp]

**Runtime-fallback:** `1c-mcp-crud execute_code` (`КонструкторСхемыКомпоновкиДанных`, `СериализаторXDTO`, `ТабличныйДокумент`) — генерация/рендер/верификация на живых данных. [exp]

### Матрица «способность → инструмент»
| Способность | Основной | Альтернатива | Деплой/verify |
|---|---|---|---|
| Анализ DCS (`.dcs`) | cc-1c-skills `skd-info` | tools_ui_1c (runtime) | — |
| Правка/создание DCS | cc-1c-skills `skd-edit/compile` | codepilot `DcsUpsert*` (EDT) | EDT-MCP `validate_query` → `update_database` |
| Табличный документ (`.mxl/.mxlx`) | **cc-1c-skills `mxl-*`** (безальтернативно offline) | codepilot `RenderTemplate` (write) | EDT-MCP `update_database` → `execute_code` PDF-render |
| Формы анализ | cc-1c-skills `form-info` / EDT-MCP `inspect_form_layout` | mdclasses (Java, промышл.) | — |
| Формы создание/правка | cc-1c-skills `form-compile/edit` (offline) | codepilot `UpdateFormModel` (layout-свойства) / 1c-formsserver (convert) | EDT-MCP `update_database` |

### Сравнение трёх (ключевые оси)
| Ось | cc-1c-skills | codepilot1c-edt | EDT-MCP (наш) |
|---|---|---|---|
| Тип | 📄 offline (файлы) | 🧩 EDT-live | 🧩 EDT-live |
| Чтение DCS/макета | ✅ | 🔴 сломано | ◑ (DCS=validate_query; макет=🔴) |
| Запись DCS/макета | ✅ offline | ✅ (write API) | ❌ / 🔴 |
| Формы write | ✅ offline | ✅ layout-aware | ◑ modify_metadata (layout-gap) |
| Деплой в ИБ | ❌ (нужен EDT/Конф.) | через EDT | ✅ `update_database` |
| Формат | EDT XML (`.mxlx/.dcs`) ✅ | модель EDT | модель EDT |
| Лицензия | MIT | AGPL-3.0 | ~MIT |
| Зрелость | 409★ активн. | 131★ растущ. | зрелый, наш |
| Verified (сессия) | ✅ end-to-end | ◑ read❌/write-gateway✅ | ✅ |

## Последствия

### Положительные
- Каждая способность имеет именованный основной инструмент → нет ad-hoc выбора. [own]
- Не вводим новый MCP-сервер (cc-1c-skills = скрипт-набор, вызывается через Bash) — соблюдён запрет ADR-030. [own]
- Покрыты обе модели: offline-файлы (cc-1c-skills) и EDT-live (codepilot/EDT-MCP) + runtime (execute_code). [own]
- Деплой-конвейер проверен: offline-правка → EDT-MCP `update_database` → render-verify (ADR-031). [exp]

### Отрицательные / риски
- 3 инструмента = выше когнитивная нагрузка; митигировано матрицей выше. [own]
- codepilot1c-edt и EDT-MCP делят порт `:8765` → одновременно не поднять (codepilot держать как opt-in/переключаемый). [own]
- codepilot read контента сломан — легко забыть и получить пустой результат; правило: **read контента макетов/DCS — только cc-1c-skills/прямой XML**. [exp]
- `external/cc-1c-skills` — внешняя зависимость (pin + VENDOR.md митигируют). [own]

## Альтернативы (отклонены)
- **Один инструмент на всё** — ни один не покрывает 4 способности + деплой: cc-1c-skills не деплоит в ИБ; EDT-MCP не правит DCS/макеты; codepilot не читает контент. Отклонено. [own]
- **Новый собственный MCP-сервер (СКД/mxl)** — дублирует cc-1c-skills, нарушает ADR-030 «новых MCP не вводим». Отклонено. [own]
- **Только runtime (execute_code)** — не даёт offline-правки исходников в репозитории задач. Остаётся как verify/fallback. [own]
- **mdclasses / 1c-formsserver как основные** — mdclasses = анализ-grade Java-lib (не AI-правка); 1c-formsserver = только формы + генерит (не in-place), 7★. Вторичны. [web]

## Связанные файлы
- Кеш: `cache/1c-form-skd-spreadsheet-tooling-2026.md` (рейтинг + live-прогоны)
- ADR-030 (стратегия), ADR-031 (adopt cc-1c-skills)
- Вендор: `external/cc-1c-skills/` (pin `3d36c20`, VENDOR.md)
- Память: `reference_codepilot1c_form_template_dcs_tools`, `feedback_edt_mcp_mxlx_not_compiled` (уточнена)
- Follow-up (не сделано): live-прогон mdclasses (чтение форм, Java-build) и 1c-formsserver (convert, HTTP-сервер) — отдельный setup-тяжёлый срез
