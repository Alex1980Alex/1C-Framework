---
name: edt-mcp
description: "EDT-MCP — 70 MCP-инструментов 1C:EDT (метаданные/BSL/отладка/тесты/формы/проект). Триггеры: 'edt-mcp', 'EDT MCP', 'write_module_source', 'create_metadata', 'modify_metadata', 'adopt_metadata_object', 'rename_metadata_object', 'update_database EDT', 'get_project_errors', 'revalidate_objects', 'run_yaxunit_tests', 'create_project', 'create_infobase', 'enable_toolset', 'инструменты EDT'. НЕ для запросов к данным/execute_code (→ 1c-mcp-crud). НЕ для живого RDBG BP-trace (→ 1c-debug-hmr). НЕ для методики написания BSL (→ bsl-development)."
version: 2.3.1
updated: 2026-06-16
tags: [1c, edt, edt-mcp, metadata, bsl, debug, yaxunit]
---
<!-- bundle зарегистрирован в .claude/skills/skill-router-config.json как "edt-mcp" -->
<!-- Полный справочник всех 70 тулов: references/tools.md -->

# EDT-MCP — инструменты 1C:EDT через MCP

## Обзор

EDT-MCP (`com.ditrix.edt.mcp.server`, репозиторий `DitriXNew/EDT-MCP`) — Eclipse-плагин 1C:EDT, поднимающий HTTP MCP-сервер. Даёт **70 инструментов** для работы с конфигурацией 1С прямо в модели EDT: чтение/правка BSL, CRUD метаданных, отладка, YAXUnit-тесты, рендер форм, обновление БД, XML-экспорт/импорт.

Ключевой принцип: тулы работают через **живую модель EDT** (валидация, рефакторинг, AST), а не через текст файлов — поэтому правки каскадируются, ссылки находятся семантически, а имена событий/типов резолвятся в любом ru/en написании.

> Полные параметры/примеры каждого тула — в [`references/tools.md`](references/tools.md) или в рантайме `get_tool_guide('<tool>')`.

---

## Подключение в этом проекте

| Параметр | Значение |
|----------|----------|
| MCP-сервер | `edt-mcp` (в `.mcp.json`) |
| Транспорт | `npx -y mcp-remote http://localhost:8765/mcp` |
| Хост | плагин внутри запущенного **1C:EDT (Lite) 2025.2** (порт 8765 поднимает javaw EDT) |
| Версия плагина | **2.3.1** (OSGi-бандл; обновляется через p2 director — см. memory `reference-edt-mcp-plugin-update`) |
| После обновления плагина | `/mcp reconnect` — иначе сессия держит старый список тулов |
| Безопасность | сервер доверяет ЛЮБОМУ клиенту, достижимому до эндпоинта; все тулы (вкл. `evaluate_expression`, деструктивные) вызываемы — это локальный dev |

Если тул `edt-mcp` не отвечает: проверь, что EDT 2025.2 запущен и `get_edt_version` возвращает версию; при «нет соединения» — `/mcp reconnect`.

---

## Ключевые концепции

### 1. FQN-адресация (двуязычная)
- Топ-объект: `Type.Name` (`Catalog.Products`, `Справочник.Товары`).
- Член: `Type.Name.Kind.Name` (`Catalog.Products.Attribute.Weight`, `InformationRegister.Prices.Dimension.Product`).
- Член формы: `Catalog.X.Form.FormName.<Kind>.ItemName` (Kind = Attribute/Command/Field/Button/Group/Decoration).
- **TYPE/KIND-токены — ru ИЛИ en; части Name — программные имена, НЕ синонимы.**

### 2. Progressive disclosure (тулсеты)
Тулы сгруппированы в **тулсеты**; по умолчанию (`progressiveDisclosure=off`) видны все. Если включено — видна только группа **core**, остальные открываются через `enable_toolset(["code","debug",...])` → **обязательно переснять `tools/list`** (в Claude Code это `/mcp reconnect`). Список групп — `list_toolsets`. В нашей конфигурации после reconnect видны все 70.

### 3. contentHash round-trip (безопасная правка BSL)
`read_module_source` отдаёт `contentHash` (revision-токен по ВСЕМУ файлу). Передавай его в `write_module_source` как `expectedHash` — это guard от потерянного апдейта (правка отклонится, если файл изменился после чтения).

### 4. Текстовые vs модельные тулы
- **Текстовый** (буквально, НЕ ru/en-aware): `search_in_code`.
- **Модельные** (находят идентификатор в любом написании): `find_references`, `go_to_definition`, `get_method_call_hierarchy`, `validate_query`.
- Для идентификаторов/ссылок — модельные; `search_in_code` — для произвольного текста/комментариев.

> ⚠ **Поиск по кодовой базе = ИНДЕКСЫ, а не `search_in_code`** (В1 260718, W2). `search_in_code`
> сканирует workspace вживую → p95 **12с** (2× baseline, degraded). Для «где встречается X / кто
> вызывает / найти эталон» бери **`mcp__bsl-semantic-search__bsl_search`/`bsl_hybrid_search`**
> (семантика по 37k-чанковому индексу) или **`mcp__bsl-code-search__search_symbols`/`find_callers`**
> (символы/вызовы по SQLite call-graph). `search_in_code` (edt-mcp) — только для **точечного**
> текстового контекста в уже открытом модуле при refactor'е, не для обзорного поиска по конфигурации.

### 5. Confirm-preview гейт (деструктивные)
Двухфазно: без `confirm` → превью (ничего не меняется), `confirm=true` → выполнить.
**Гейтированы:** `update_database`, `delete_metadata`, `rename_metadata_object`, `delete_project`, `delete_launch_config`, `delete_infobase`. Остальные write-тулы (`create_metadata`, `modify_metadata`, `write_module_source`) НЕ гейтированы (обратимы обратным вызовом / `delete_metadata`).

---

## Каталог по тулсетам (70)

**Core** (всегда): `list_projects` · `list_modules` · `read_module_source` · `get_module_structure` · `get_metadata_objects` · `get_metadata_details` · `search_in_code` · `get_edt_version` · `get_server_status` · `list_toolsets` · `enable_toolset` · `get_tool_guide`

**Code**: `write_module_source` · `read_method_source` · `find_references` · `go_to_definition` · `get_method_call_hierarchy` · `get_symbol_info` · `get_content_assist` · `validate_query` · `get_platform_documentation`

**Metadata**: `create_metadata` · `modify_metadata` · `rename_metadata_object` · `delete_metadata` · `adopt_metadata_object` · `get_configuration_properties` · `list_subsystems` · `get_subsystem_content` · `get_tags` · `get_objects_by_tags`

**Debug**: `debug_launch` · `debug_status` · `set_breakpoint` · `remove_breakpoint` · `list_breakpoints` · `wait_for_break` · `get_variables` · `evaluate_expression` · `step` · `resume` · `terminate_launch` · `get_applications`

**Testing**: `run_yaxunit_tests` · `debug_yaxunit_tests` (deprecated)

**Profiling**: `start_profiling` · `stop_profiling` · `get_profiling_results`

**Forms**: `get_form_screenshot` · `get_form_layout_snapshot` (требуют JVM-флаг, см. ниже)

**Translation**: `generate_translation_strings` · `translate_configuration` · `get_translation_project_info`

**Project**: `update_database` · `clean_project` · `revalidate_objects` · `resync_to_disk` · `get_project_errors` · `get_problem_summary` · `get_markers` · `get_check_description` · `export_configuration_to_xml` · `import_configuration_from_xml` · `create_project` · `create_infobase` · `delete_infobase` · `create_launch_config` · `delete_launch_config` · `list_configurations` · `delete_project`

---

## Канонические workflow (копируй и адаптируй)

### A. Навигация и чтение
```
list_projects                              # узнать projectName (нужен state=ready)
list_modules(projectName, nameFilter)      # найти src/-путь модуля
get_module_structure(projectName, modulePath)   # оглавление: методы, строки, контекст
read_method_source(projectName, …, methodName)  # одно тело метода
read_module_source(projectName, modulePath)     # весь модуль + contentHash
```

### B. Безопасная правка BSL
```
1. read_module_source(projectName, modulePath)         → запомни contentHash
2. write_module_source(projectName, modulePath,
       mode="searchReplace", oldSource="<точный фрагмент>",
       source="<новый фрагмент>", expectedHash="<contentHash>")
3. get_project_errors(projectName, objects=[...])       # проверь, что не сломал
```
- `oldSource` должен совпадать РОВНО один раз (иначе отказ — читай заново / бери больший фрагмент).
- Создать новый модуль может только `mode="replace"` (он же создаёт папки).

### C. Метаданные: создать/изменить + применить к БД
```
get_metadata_objects(projectName, metadataType)        # discovery
get_metadata_details(projectName, [fqn], assignable=true)  # узнать settable-свойства + допустимые значения
create_metadata(projectName, fqn="Catalog.X.Attribute.Y")
modify_metadata(projectName, fqn, properties=[{name:"type", value:{types:[{kind:"String", ...}]}}])
get_project_errors(projectName)                         # верификация
update_database(launchConfigurationName, confirm=true)  # ДЕСТРУКТИВНО — только по запросу пользователя
```

### D. Расширение конфигурации (override / перехват события)
```
create_project(projectKind="extension", name=..., baseProjectName="<база>")  # дождись state=ready
adopt_metadata_object(projectName="<база>", fqn="Document.Order.Form.DocumentForm")
create_metadata(projectName="<расширение>",
    fqn="Document.Order.Form.DocumentForm.Field.Date.Handler.OnChange",
    callType="After", properties=[{name:"procedure", value:"ext_DateOnChangeAfter"}])
write_module_source(projectName="<расширение>", objectName="Document.Order",
    moduleType="FormModule", formName="DocumentForm", mode="append",
    source="&AtClient\nProcedure ext_DateOnChangeAfter(Item)\n  // ...\nEndProcedure")
get_project_errors(projectName="<расширение>")
```
Перехват МЕТОДА (не события формы) = обычный аннотированный BSL (`&Before/&After/&Around/&ChangeAndValidate`) через `write_module_source` (host-модуль расширения должен существовать).

### E. Инфобаза + конфиг запуска
```
create_infobase(projectName, infobaseFile="C:\\infobases\\X")   # или mode="register"
get_applications(projectName)                                    # → applicationId / defaultApplicationId
create_launch_config(projectName, clientType="thin")
update_database(projectName, applicationId, confirm=true)        # залить конфигурацию в новую (пустую) ИБ
```

### F. Отладка (клиент или сервер)
```
set_breakpoint(projectName, modulePath, lineNumber)
debug_launch(launchConfigurationName=...)        # клиент; для СЕРВЕРНОГО кода — Attach-конфиг по имени
wait_for_break(applicationId, timeout=60)        # → frameRef / topFrameRef / threadId
get_variables(frameRef) | evaluate_expression(frameRef, expression) | step(threadId, kind="over")
resume(threadId)                                 # → снова wait_for_break
terminate_launch(launchConfigurationName=...)
```
- `frameRef` протухает после КАЖДОГО step/resume — бери свежий из ответа.
- Attach достижим ТОЛЬКО через `launchConfigurationName`.

### G. YAXUnit-тесты
```
list_configurations(type="client")                      # имя runtime-client конфига
run_yaxunit_tests(launchConfigurationName=..., tests="Модуль.Тест", timeout=60)
# Если вернулось Pending — повтори с ИДЕНТИЧНЫМИ аргументами (re-attach к идущему прогону)
# Debug-цикл: run_yaxunit_tests(..., debug=true) → wait_for_break → … (пин ОДНОГО теста)
```

### H. Профилирование (= покрытие)
```
debug_launch(...) → start_profiling(applicationId) → <прогон> → stop_profiling(applicationId)
→ get_profiling_results(moduleFilter, minFrequency)
```

### I. Формы (WYSIWYG)
```
get_form_screenshot(projectName, formPath="Catalog.X.Forms.ItemForm")   # PNG
get_form_layout_snapshot(projectName, formPath, mode="compact")         # YAML-раскладка
```
> ⚠ EDT-MCP форму только **читает** (screenshot/snapshot) и НЕ мутирует; `create_metadata` не привязывает поле к члену `ConstantsSet`. **Мутация формы** (добавить/изменить элемент, DCS, макет) → **codepilot1c** `mutate_form_model`/`apply_form_recipe`/`dcs_manage`/`render_template` (skill [`codepilot1c`](../codepilot1c/SKILL.md)).
⚠ **Два ортогональных JVM-флага в `1cedt.ini -vmargs`** (см. cache `1c-doc-research/edt-mcp-form-render-flags`):
- `-DnativeFormBufferedLayoutRender=true` — нужен для **скриншота** (`get_form_screenshot`), иначе PNG пустой.
- `-DnativeFormLayoutRender=false` — нужен для **per-element bounds** в `get_form_layout_snapshot`. Дефолт EDT `=true` (native C++) → `elementsWithBounds: 0` **by design** (НЕ баг). Bounds считаются только в Java-режиме (`boundsSource: layoutProjection`).
После правки — рестарт EDT (JVM-arg только при старте) + `/mcp reconnect`; проверь `get_server_status.formRenderFlags`. Java-режим раскладки тяжелее для IDE — включать под задачи с bounds, иначе вернуть `true`.

### J. XML-экспорт/импорт
```
export_configuration_to_xml(projectName, outputPath="C:\\dump")
import_configuration_from_xml(importPath="C:\\dump", projectName="<НОВЫЙ>")
```
Требуют плагин `com._1c.g5.v8.dt.cli.api`.

---

## Диагностика

| Симптом | Причина | Решение |
|---------|---------|---------|
| Тул не отвечает / нет соединения | EDT не запущен или MCP-прокси держит мёртвую сессию | Запусти EDT 2025.2; `get_edt_version`; `/mcp reconnect` |
| Новые тулы не видны после обновления плагина | Сессия закэшировала старый `tools/list` | `/mcp reconnect` |
| `write_module_source` отказ «oldSource matched 0/multiple» | Фрагмент неуникален/устарел | Перечитай `read_module_source`, возьми больший уникальный `oldSource` |
| Запись отклонена по `expectedHash` | Файл изменился после чтения (lost-update) | Перечитай → возьми свежий `contentHash` → повтори |
| `search_in_code` не находит русский/англ. идентификатор | Текстовый поиск НЕ ru/en-aware | Используй `find_references`/`go_to_definition`/`get_method_call_hierarchy` |
| Скриншот формы пустой | Нет `-DnativeFormBufferedLayoutRender=true` | Добавь в `1cedt.ini -vmargs`, рестарт EDT + `/mcp reconnect` |
| `elementsWithBounds: 0` при непустой форме | `nativeFormLayoutRender=true` (native C++-режим, дефолт) — НЕ баг | Флипни в `=false` (Java-режим) в `1cedt.ini -vmargs`, рестарт + `/mcp reconnect`; verify `get_server_status.formRenderFlags` + `boundsSource: layoutProjection` |
| «BSL model is not available» / «still building» | Проект ещё индексируется | Дождись `state=ready` (`list_projects`) или `clean_project` |
| `update_database` `stateAfter≠UPDATED` | Обновление не доехало (лок/чужой сеанс/платформенный отказ) | Смотри **журнал EDT**, а не только ответ; `fullUpdate=true` - это full-vs-incremental, а **НЕ** подтверждение диалога (прежняя формулировка была домыслом, снята 2026-07-25) |
| **`timed out after 60s`** на `update_database`/`create_project`/`delete_project`/`modify_metadata` | **Клиентский потолок 60с < длительности операции.** Операция обычно УСПЕШНА: журнал EDT показал `outcome=ok` при 60 253мс (`create_project`), 134 035/203 137мс (`delete_project`), 119 398/215 360/3 147 392мс (`update_database`) | НЕ повторять вызов слепо (повтор после успеха даёт `Project not found` / `METADATA_ALREADY_EXISTS` / `Project is building`). Сначала проверить факт: `python scripts/edt_journal.py --tool <имя> --failures` (парсер журнала; сырой вариант — `grep "Completed tools/call" <workspace>/.metadata/.log`). Метрики tool-health такой вызов больше НЕ считают провалом — вычитается в `client_timeout` (см. секцию «Серверные исходы» в `data/reports/tools/_latest.md`) |
| Вызов встал, в журнале `Destructive-consent gate: user allowed '<tool>' …` | **Гейт самого плагина** ждёт клика человека (дефолт `ask_always`); отпускается на всю сессию EDT одним подтверждением | Настройки EDT → страница **«MCP Server»**: `mcpDestructiveConsentLevel` → `per_tool` + `mcpDestructiveAllowedTools`, либо `allow_all`. Файл `.metadata/.plugins/org.eclipse.core.runtime/.settings/com.ditrix.edt.mcp.server.prefs` |
| Вызов встал, в журнале `Ошибка исключительной блокировки информационной базы … Отмена/Повторить/Обновить динамически` | Инфобазу держат **чужие** сеансы (Тонкий клиент, Designer). `terminateRunningClients=true` их НЕ гасит - только клиентов, запущенных ЭТИМ EDT | Закрыть сеансы до обновления (`rac session terminate`) либо ответить «Обновить динамически» в EDT |
| `persisted=false` в ответе create/modify | Экспорт в `.mdo` не подтверждён | Перепроверь объект перед опорой на диск; при рассинхроне — `resync_to_disk` |
| `delete_metadata` `action='blocked'` | Неавтоочищаемые metadata-ссылки | Убери ссылки заранее, либо `force=true` (оставит dangling) |
| `update_database` на `ServerApplication.*` стартует RUN | Это standalone-server | Обновляй через `debug_launch`/`run_yaxunit_tests(updateBeforeLaunch=true)` |

---

## Антипаттерны

| Плохо | Почему | Как правильно |
|-------|--------|---------------|
| Править BSL без `expectedHash` | Молча затрёшь чужие правки (lost update) | Всегда round-trip `read_module_source.contentHash` → `write_module_source.expectedHash` |
| `search_in_code` для поиска вызовов метода | Текстовый, пропустит другое ru/en написание | `get_method_call_hierarchy` / `find_references` |
| `update_database confirm=true` без запроса пользователя | Деструктивно/необратимо | Сначала превью (без confirm); применять только по явному запросу |
| Адресовать объект синонимом | Резолв только по программному Name | Используй Name; синоним задаётся как свойство |
| `modify_metadata` свойством наугад | Невалидное свойство → НИЧЕГО не пишется | Сначала `get_metadata_details(assignable=true)` за именами+допустимыми значениями |
| Move item формы вместе с правкой свойств | Move структурный, не комбинируется | Сначала move (`parent`/`position`), потом отдельный `modify_metadata` |
| Ждать ошибку launch в ответе `debug_launch` | Запуск асинхронный | Поллируй `debug_status`, потом `wait_for_break`; ошибки — в EDT error log |
| Переиспользовать `frameRef` после step | Протухает после каждого шага | Бери свежий frameRef/topFrameRef из ответа step/wait_for_break |

---

## Лучшие практики

1. **Сессию начинай с `list_projects`** — узнать точные `projectName` и что проект `ready` (building-проект небезопасен для чтения/записи модели).
2. **После любой write-операции — `get_project_errors`** (детали) или `get_problem_summary` (счётчики): EDT-валидация ловит то, что статикой не видно.
3. **Деструктивное — только по явному запросу пользователя** и сначала в режиме превью (без `confirm`).
4. **Тяжёлое vs лёгкое**: точечная ре-валидация — `revalidate_objects(objects=[...])`; полная пересборка/«застряло» — `clean_project` (отбрасывает несохранённые in-memory правки — сохрани раньше).
5. **Для серверного кода (HTTP-сервисы, фоновые задания)** — Attach-конфиг через `debug_launch(launchConfigurationName=...)`; runtime-client туда не дотянется.
6. **`get_tool_guide('<tool>')`** перед нетривиальным вызовом — там полные параметры и preconditions, которых нет в кратком описании.
7. **Исход долгой операции читай в журнале EDT, а не по ответу клиента.** Плагин пишет пару `Processing tools/call: <tool>` → `Completed tools/call: <tool> in Nms, outcome=ok|error` (+ `Failed tools/call: … - <текст>`) в `<workspace>/.metadata/.log` (ротация в `.bak_N.log`). Это ЕДИНСТВЕННЫЙ источник, различающий «упало» и «клиент не дождался»: при `timed out after 60s` операция чаще всего завершилась успешно уже после обрыва. Текст ошибки для вызова, на который не пришёл PostToolUse, ищется в транскрипте сессии (`tool_result.is_error`) - в hook-логе и native OTel его нет. Разбор на живых данных - [ретро 260725 §5 P1](../../../docs/roadmap/260725_ROADMAP_SESSION_RETRO.md).
8. **Память проекта**: правки макетов `.mxlx` EDT-MCP может не подхватывать — см. memory `feedback-edt-mcp-mxlx-not-compiled`; `write_module_source` может работать на устаревшем снапшоте — см. `feedback-edt-mcp-stale-snapshot` (verify git diff перед commit).

---

## Связанные скиллы (НЕ дублировать)

- `codepilot1c` — **мутации, которых нет у EDT-MCP**: элементы форм (`mutate_form_model`/`create_form`), DCS (`dcs_manage`), права ролей (`mutate_role_rights`), макеты (`render_template`). Тот же EDT-проект; гейт `edt_validate_request`.
- `1c-mcp-crud` — запросы к **данным** БД, `execute_code`, журнал регистрации (другой MCP — Python stdio, не EDT-MCP).
- `1c-debug-hmr` — живой RDBG BP-trace (в проекте — основной путь отладки; EDT-MCP debug-тулы — альтернатива внутри EDT).
- `bsl-development` — методика написания BSL-кода/стандарты БСП.
- `bsl-symbol-editing` — symbol-anchored обёртки над read_method_source/write_module_source (узкий refactoring-workflow).
- `analyze-1c-task` / `implement-1c-task` / `run-1c-task` — пайплайн задачи 1С (оркестрируют эти тулы).
- `va-bdd-testing` — UI BDD-тесты Vanessa (не YAXUnit).

---

## Ссылки

| Ресурс | URL |
|--------|-----|
| Полный справочник тулов (70) | [`references/tools.md`](references/tools.md) |
| Репозиторий | https://github.com/DitriXNew/EDT-MCP |
| Документация тулов | https://github.com/DitriXNew/EDT-MCP/tree/master/docs/tools |
| Update site (p2) | https://ditrixnew.github.io/EDT-MCP/ |
| Рантайм-гайд тула | `get_tool_guide('<tool>')` |
