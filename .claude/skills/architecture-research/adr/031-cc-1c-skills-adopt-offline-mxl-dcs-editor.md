# ADR-031: Adopt cc-1c-skills как offline-редактор .mxl/.mxlx и .dcs (round-trip DSL, live-verified)

**Дата:** 2026-06-21
**Статус:** accepted
**Исследование:** [../cache/1c-form-skd-spreadsheet-tooling-2026.md](../cache/1c-form-skd-spreadsheet-tooling-2026.md) (§Доп-свип 2026-06-21)
**Амендит:** [ADR-030](030-1c-ui-report-artifact-editing-strategy.md) (вывод «Табличный = LOW, offline-парсера .mxl нет»)

## Контекст

ADR-030 (2026-06-21) зафиксировал градиент tractability AI-правки артефактов 1С: data-composition (HIGH) > Формы (MEDIUM) > Табличный документ (**LOW** — «offline-парсера .mxl/.mxlx НЕТ, программно только runtime-BSL»). Тогда же live-проверка codepilot1c показала: его read-сторона для `.mxlx` (`inspect_template`) и `.dcs` (`dcs_manage`) **сломана** — содержимое не читается (хардкод пути `.mxl`; тело `.dcs` не парсится → датасеты/параметры = 0 даже у типового отчёта).

Доп-свип GitHub/web (2026-06-21, вечер) нашёл инструмент, прямо закрывающий обе дыры: **`Nikolay-Shirokov/cc-1c-skills`** (MIT, 409★ / 1198 commits / 19 releases, активный; PowerShell 5.1+ И Python 3.x + lxml) — набор AI-agent-скиллов с абстракцией DSL ↔ XML-форматы 1С, работающий над тем же XML, что хранит EDT (`SpreadsheetDocument.xml`/`DataCompositionSchema.xml` = наши `.mxlx`/`.dcs`).

## Решение

**ADOPT `cc-1c-skills`** как offline-слой чтения и правки табличных документов (`.mxl`/`.mxlx`) и data-composition схем (`.dcs`) в нашем стеке. Использовать **Python-порт** (встраивается в `.venv`, dep = lxml, уже стоит 6.0.4). [own]

Распределение ролей в инструментарии 1С после adopt: [own]
- **cc-1c-skills** — offline read/edit `.mxl/.mxlx` (`/mxl-decompile`↔`/mxl-compile`, `/mxl-info`, `/mxl-validate`) и `.dcs` (`/skd-info`, `/skd-edit` 30+ операций in-place, `/skd-compile`, `/skd-validate`).
- **codepilot1c-edt** — write-сторона форм (mutate через токен; read контента макетов/`.dcs` НЕ использовать — сломан).
- **edt-mcp** — метаданные/модель форм/`validate_query`.
- **1c-mcp-crud `execute_code`** — runtime-проверка на живых данных + рендер в PDF (verify).

### Live-верификация (на реальных файлах проекта `Конфигурация`/ИБTransportManagementDevelop) [own]
Драйвер прогнал 3 теста — **все PASS**:
1. **MXL round-trip** на `ПФ_MXL_АктРасхожденияВеса_by.mxlx` (28 719 б): decompile rc=0 (распознал Areas 2 / Rows 30 / Columns 34 / Merges 47) → compile rc=0; текстовые значения ячеек **84/84 общих, потеряно 0** (структурных элементов меньше — нормализация дефолтов, контент не теряется).
2. **DCS read** на `гкс_РеестрОтгрузки/…/Template.dcs` (414 строк): прочитал 1 набор [Query] с 10 полями + запрос, 1 вычисляемое поле, 4 ресурса, 3 параметра, 2 варианта с фильтрами — **ровно то, что codepilot `dcs_manage` отдавал как 0**.
3. **DCS edit** на КОПИИ: `add-parameter` rc=0 «[OK] added» → стало 4 параметра; **оригинал не тронут** (md5 совпал) — in-place правка изолирована.

## Последствия

### Положительные
- Табличный документ переходит **LOW → MEDIUM** (появился offline JSON round-trip read/edit). Амендит градиент ADR-030. [own]
- Read-дыра codepilot закрывается на нашей стороне: структуру макетов/`.dcs` читаем и правим через cc-1c-skills offline, без EDT/Конфигуратора. [own]
- Формат совпадает с EDT (`.mxlx`/`.dcs`) → прямо применимо к репозиторию задач без конвертации. [exp]
- MIT, Python-порт → можно вендорить в `external/` или вызывать as-is; нет AGPL-обязательств (в отличие от codepilot1c-edt). [web]
- Самописный helper не нужен — готовое решение зрелее и валидируется на 930+ реальных схемах. [own]

### Отрицательные / риски
- Внешняя зависимость (single-author, хоть и активная 1198 commits). Митигировать: вендорить зафиксированную версию в `external/cc-1c-skills`. [own]
- `mxl-compile` нормализует XML (1238→858 элементов, меньше) — контент сохраняется. ~~риск R-1~~ **R-1 ЗАКРЫТ (live 2026-06-21):** деплой recompiled `.mxlx` с маркером в `ПФ_MXL_АктРасхожденияВеса_by` → EDT авто-подхватил дисковую правку (`INCREMENTAL_UPDATE_REQUIRED`) → `update_database` (EDT 2025.2 + edt-mcp 2.3.1) → ИБ: `marker=YES`, `pdfBytes=41553` (рендер OK, H/W целы) → откат из backup → `update_database` → `marker=NO`, git CLEAN. Полный цикл «правка→платформа принимает→рендер» доказан; **уточняет** [[feedback-edt-mcp-mxlx-not-compiled]] (в этой связке подхват сработал через workspace auto-refresh). [own]
- Скилл-набор скриптов, не MCP-сервер → вызывается через Bash/subprocess, не через MCP-протокол (не интегрируется в tool-роутинг автоматически). [own]
- `.mxlx` после правки в EDT-проекте: EDT может не рекомпилировать внешние правки (см. [[feedback-edt-mcp-mxlx-not-compiled]]) → грузить через `update_database`, не `clean_project`. [exp]

## Альтернативы (отклонены)
- **Самописный Python-парсер `.dcs`/`.mxlx`** — дублирует cc-1c-skills, без валидации на корпусе схем. Отклонён.
- **Фикс read-стороны codepilot1c-edt (PR/форк)** — правильно, но дорого (EDT target platform + Tycho + BM API + AGPL); оставлен как parallel-track (issue апстриму), НЕ блокер. [own]
- **Только runtime-BSL** (вывод ADR-030) — остаётся для генерации на живых данных и рендер-verify, но не закрывает offline-правку существующего макета/схемы. cc-1c-skills дополняет, не заменяет. [own]

## Связанные файлы
- Кеш фактов: `cache/1c-form-skd-spreadsheet-tooling-2026.md`
- Память: `reference_codepilot1c_form_template_dcs_tools`
- Амендит: `adr/030-1c-ui-report-artifact-editing-strategy.md`
- Затрагивает воркфлоу: правка печатных форм / отчётов в `configuration/*/docs/*` (задачи типа GKSTCPLK-2566 АктРасхожденияВеса, GKSTCPLK-2567 АктВозврата)
