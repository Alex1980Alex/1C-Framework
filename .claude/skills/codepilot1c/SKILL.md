---
name: codepilot1c
description: codepilot1c (1С Copilot) — MCP-сервер 1С:EDT для МУТАЦИЙ, которых нет у EDT-MCP. ИСПОЛЬЗУЙ для правки элементов форм (create_form/mutate_form_model/apply_form_recipe/inspect_form_layout), схем компоновки данных (dcs_manage), прав ролей (inspect_role_rights/mutate_role_rights), макетов печатных форм (render_template/inspect_template), QA Vanessa/YAxUnit через модель (qa_*/author_yaxunit_tests). Триггеры 'мутация формы', 'добавить элемент формы', 'флажок на форму', 'mutate_form_model', 'create_form', 'apply_form_recipe', 'inspect_form_layout', 'схема компоновки данных', 'dcs_manage', 'права роли 1С', 'mutate_role_rights', 'макет печатной формы', 'render_template', 'codepilot1c', '1С Copilot'. НЕ для написания BSL-кода/метаданных (→ edt-mcp/bsl-development), НЕ для запросов к данным (→ 1c-mcp-crud), НЕ для статического чтения формы-скриншота (→ edt-mcp get_form_screenshot).
metadata:
  type: reference
---

# codepilot1c (1С Copilot) — MCP-сервер 1С:EDT

## Обзор

codepilot1c — MCP-сервер поверх 1С:EDT (в `.mcp.json`, tools **deferred** — грузятся через `ToolSearch`/`discover_tools`). Пересекается с EDT-MCP по BSL/метаданным/отладке, но **уникален там, где EDT-MCP пасует: мутация форм, DCS, права ролей, макеты, QA-конвейер**. Работает на том же EDT-проекте (`inspect_form_layout` читает через EDT BM API).

**Почему нужен отдельно от EDT-MCP:** EDT-MCP умеет форму только **читать** (`get_form_screenshot`/`get_form_layout_snapshot`), а `create_metadata` НЕ привязывает поле к члену `ConstantsSet` (dotted `dataPath` трактует как колонку динсписка). codepilot1c формы **мутирует**. DCS / права ролей / макеты у EDT-MCP отсутствуют вовсе.

## Когда какой сервер (маршрут)

| Нужно | Сервер |
|---|---|
| Правка **элемента формы** (поле/группа/кнопка/флажок), новая форма | **codepilot1c** `mutate_form_model`/`create_form`/`apply_form_recipe` |
| **Схема компоновки данных** (СКД) | **codepilot1c** `dcs_manage` |
| **Права роли** (объектные/флаги; не RLS) | **codepilot1c** `mutate_role_rights` |
| **Макет печатной формы** (.mxl из JSON) | **codepilot1c** `render_template` |
| **QA Vanessa BDD / YAxUnit** через модель | **codepilot1c** `qa_*` / `author_yaxunit_tests` |
| Запись **BSL-модуля** (searchReplace + syntax check) | edt-mcp `write_module_source` |
| CRUD **метаданных** (константа/реквизит/объект) | edt-mcp `create_metadata`/`modify_metadata` (или codepilot1c `create_metadata`/`update_metadata`) |
| Запрос к **данным** БД, `execute_code`, журнал | 1c-mcp-crud |
| Live RDBG BP-trace | 1c-debug-hmr |

> Метаданные/BSL/debug — можно и codepilot1c, но в 1С-пайплайне (`implement-1c-task`) основной путь для них — EDT-MCP. codepilot1c берём ПРИЦЕЛЬНО под его нишу.

## ОБЯЗАТЕЛЬНЫЙ гейт: validation_token

Любая **мутация** (metadata/forms/DCS/extension/external/roles) требует одноразовый токен:

```
1. inspect_form_layout / inspect_role_rights / dcs_manage(read)   # понять текущее состояние
2. edt_validate_request(<точный payload операций>)  → validation_token   # ОБЯЗАТЕЛЬНО
3. mutate_form_model / apply_form_recipe / mutate_role_rights / dcs_manage(write)
     (validation_token = НЕИЗМЕНЁННЫЙ токен ровно под ЭТОТ payload)
4. get_project_errors (EDT) / revalidate_objects   # верификация
```

Токен привязан к точному payload — менять операции после `edt_validate_request` нельзя (перезапросить токен). Read-only tools (`inspect_*`, `scan_metadata_index`, `edt_*` readers) токен НЕ требуют.

## Каталог (по категориям; `discover_tools(category)` раскрывает)

**forms** (4): `create_form` · `apply_form_recipe` · `mutate_form_model` (add_field/add_group/add_table/set_item/remove_item/move_item; виджеты INPUT_FIELD/CHECK_BOX_FIELD/LABEL_FIELD/…) · `inspect_form_layout`.
**dcs** (1): `dcs_manage` — читает/создаёт основную СКД, обновляет наборы данных, параметры, вычисляемые поля.
**metadata** (22): `create_metadata`/`update_metadata`/`add_metadata_child`/`delete_metadata` · `edt_field_type_candidates` · `inspect_role_rights`/`mutate_role_rights` · `inspect_template`/`render_template` · `edt_metadata_details`/`scan_metadata_index`/`edt_list_modules`/`edt_get_module_structure` · `edt_go_to_definition`/`edt_get_symbol_info`/`edt_get_method_call_hierarchy` · `inspect_platform_reference` · `edt_get_configuration_properties`/`edt_get_tags`/`edt_get_objects_by_tags` · `ensure_module_artifact` · `edt_validate_request`.
**qa** (7): `qa_plan_scenario` → `qa_generate` → `qa_validate_feature` → `qa_run` (Vanessa BDD) · `qa_inspect` · `qa_prepare_form_context` · `author_yaxunit_tests` (YAxUnit + регистрация ИсполняемыеСценарии). ⚠ `qa_run` **проверен рабочим** (MFM смоук junit 1/0/0), но **только binary-путь** (`edt.use_runtime=false` + `bin_path=…\1cv8c.exe` + `ib_connection` c `Usr=`; `.epf` из git LFS; `status:infra_error` при exit 0 — ложный, истина в junit) — EDT-runtime путь сломан на EDT 2025.2.6 (`getThickClientInfo` в API отсутствует). Рецепт: `reference_codepilot1c_qa_run_binary_path`.
**bsl** / **extensions** / **diagnostics** / **workspace**: `bsl_list_methods`/`bsl_get_method_body`/`bsl_analyze_method`/`bsl_module_context`; `extension_manage`/`external_manage`; `get_diagnostics`/`tail_edt_logs`/`get_profiling_results`; `connect_infobase`/`import_project_from_infobase`/`edit_file`/`read_file`/`glob`/`grep`.

## Шаблон: элемент формы (частый кейс)

```
inspect_form_layout(project, form_fqn, include_properties=true)   # id родительской группы + существующие поля
edt_validate_request(<add_field payload>) → validation_token
mutate_form_model(project, form_fqn, operations=[
  {op:"add_field", parent_item_name:"<Группа>", name:"<Имя>",
   data_path:"НаборКонстант.<Константа>", type:"CHECK_BOX_FIELD"}], validation_token=<token>)
get_project_errors(project, objects=["CommonForm.<Форма>"])       # 0 ошибок
```
Реквизит формы `mutate_form_model` НЕ создаёт — только визуальные items; реквизит данных → `apply_form_recipe attributes[] action=create/upsert`. Форма набора констант (`ConstantsFormExtInfo`) обслуживает любую референсуемую константу — регистрировать в реквизите `НаборКонстант` не надо.

## Диагностика

| Симптом | Причина | Решение |
|---|---|---|
| `-32000` / нет ответа | MCP-хост codepilot1c выключен / Bearer 401 | поднять хост; см. память `reference_codepilot1c_mcp_host` |
| tools не видны | deferred | `ToolSearch "select:mcp__codepilot1c__<tool>"` или `discover_tools(category)` |
| мутация отклонена «token» | payload изменился после `edt_validate_request` | перезапросить `validation_token` под точный payload |
| результат > лимита токенов | `inspect_form_layout` большой формы | grep по сохранённому файлу результата (по имени элемента) |
| .mxlx/.dcs не читаются напрямую | ограничение | см. память `reference_codepilot1c_form_template_dcs_tools` |
| `qa_run` → `ThickClientInfo … null` / `getThickClientInfo(InfobaseReference)` NoSuchMethodError | EDT-runtime путь сломан на EDT 2025.2.6 (метода нет в API — апстрим-баг) | binary-путь: `edt.use_runtime=false` + `platform.bin_path=…\1cv8c.exe` (exe!) + `ib_connection` c `Usr=`; `reference_codepilot1c_qa_run_binary_path` |
| `qa_run` `status:infra_error` при exit 0 | ложный (стартер 1cv8c детачится, va.log не прокинут) | истина в `<run_dir>/junit/junit.xml`; ждать ~30-60 с |
| `qa_run` «Превышено ограничение лицензии… Тонкий клиент запрещён» | зависшие клиенты съели слоты dev-лицензии | `rac session list`/`terminate` зависших 1CV8C + kill сирот; надёжно — ПРОФ |
| `inspect_form_layout` → `[METADATA_NOT_FOUND] formFqn is required` **хотя параметр передан** | ⚠ **сообщение врёт**: схема тула требует `form_fqn` (snake_case), а текст ошибки называет `formFqn` — послушавшись сообщения, получишь тот же отказ | передавать **`form_fqn`**; `form_id`/`formFqn` не существуют (разбор W9а, ретро 260725) |
| `apply_form_recipe` → `[INVALID_METADATA_CHANGE] Unknown form property: data_path` | ⚠ **дефект апстрима**: `attributes[].data_path` описан в схеме тула, но сервером отвергается | `data_path` указывать ТОЛЬКО в `layout[].add_field`; в `attributes[]` — `name` + `type` |
| `apply_form_recipe` → `[EDT_TRANSACTION_FAILED] The path can not be resolved: /<Реквизит>` | реквизит создаётся и связывается `add_field` в ОДНОМ рецепте — layout резолвится раньше материализации реквизита | двумя вызовами: сначала рецепт только с `attributes[]`, затем отдельный с `layout[]` |
| повтор рецепта → `[METADATA_ALREADY_EXISTS] Form attribute already exists` | ⚠ рецепт **НЕ атомарен**: на упавшем layout-шаге реквизит остаётся созданным, несмотря на `TRANSACTION_FAILED` | в повторе `action:"upsert"` вместо `create` (либо снять реквизит перед повтором) |
| `mutate_form_model` → `Unknown form property: <Заголовок>` | русское имя свойства в `set_item` | имена свойств — английские (`title`, `toolTip`); ru/en-aware только FQN-токены |
| `mutate_form_model` → `Target parent item is not a container: id=null` | `parent_item_id`/`parent_item_name` не указывает на группу | взять id родителя из `inspect_form_layout` |

## Антипаттерны

| Плохо | Почему | Правильно |
|---|---|---|
| Ручная правка `Form.form`/`.mxl`/`.dcs` при доступном codepilot1c | обход валидации, легко сломать XML | `inspect_*` → `edt_validate_request` → `mutate_*` |
| `mutate_*` без `edt_validate_request` | отклонится (нет токена) | всегда получить `validation_token` под точный payload |
| Ждать, что EDT-MCP замутирует форму | EDT-MCP форму только читает | форму мутирует codepilot1c |
| Мутировать без предварительного `inspect_*` | не знаешь id родителя/существующие items | сначала `inspect_form_layout`/`inspect_role_rights` |

## Связанные скиллы (НЕ дублировать)

- `edt-mcp` — BSL/метаданные/debug через EDT-MCP (другой сервер; основной путь пайплайна для кода).
- `1c-mcp-crud` — запросы к данным БД, `execute_code`.
- `implement-1c-task` — 1С-пайплайн (оркестрирует: EDT-MCP для кода/метаданных + codepilot1c для форм/DCS/ролей/макетов).
- `va-bdd-testing` / `yaxunit-unit-testing` — методики тестов (codepilot1c `qa_*`/`author_yaxunit_tests` = MCP-путь тех же тестов).
