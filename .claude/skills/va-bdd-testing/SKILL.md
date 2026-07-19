---
name: va-bdd-testing
description: >
  Comprehensive skill for VA BDD (Vanessa Automation) testing of 1C:Enterprise
  configurations. Covers the complete workflow: configuration analysis, VA
  documentation lookup, test writing with calibrated step patterns, MANDATORY
  pre-scenario TestDB data check (Stage 4a), and post-execution database
  verification. Based on real calibration experience with ARM forms, DynamicList
  tables, tumblers, modal dialogs, and complex business process chains. Use when
  writing, debugging, or calibrating .feature files for any 1C configuration
  objects.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - WebSearch
  - mcp__edt-mcp__get_form_screenshot
  - mcp__edt-mcp__get_metadata_details
  - mcp__edt-mcp__get_metadata_objects
  - mcp__edt-mcp__read_module_source
  - mcp__edt-mcp__search_in_code
  - mcp__edt-mcp__list_modules
  - mcp__edt-mcp__get_module_structure
  - mcp__1c-mcp-crud__execute_query
  - mcp__1c-mcp-crud__get_metadata
  - mcp__1c-mcp-crud__get_form_structure
  - mcp__1c-mcp-crud__search_code
  - mcp__ast-grep-mcp__ast_grep
  - mcp__ripgrep__search
version: 1.1.0
updated: 2026-04-11
tags: [va, bdd, vanessa-automation, testing, gherkin, 1c, feature, calibration, arm, pre-check, testdb]
changelog:
  - "1.1.0 (2026-04-11): Added Stage 4a — mandatory pre-scenario TestDB data check (5 query templates, 8-point checklist, blocker handling)"
  - "1.0.0 (2026-04-10): Initial skill with 4-stage workflow (analyze config, VA docs, write tests, verify DB)"
commands:
  - /write-1c-tests
  - /run-1c-tests
---

# VA BDD Testing (Vanessa Automation)

## Overview

This skill encodes the complete methodology for writing reliable VA BDD tests
for 1C:Enterprise configurations. It is distilled from real calibration sessions
where dozens of step pattern variants were tried, failed, and corrected against
a live TestDB (platform 8.3.27, Vanessa Automation 1.2.x).

The core insight: **the majority of test failures come from using wrong VA step
patterns or wrong element names, not from logic errors.** Therefore, this skill
focuses heavily on calibrated patterns that are confirmed to work and on the
pre-test analysis that discovers correct element names.

## When to Use This Skill

- Writing new `.feature` files for any 1C configuration objects
- Debugging failed VA BDD test steps ("Не найдена процедура для шага", "Кнопка не найдена", etc.)
- Calibrating existing tests against a live TestDB
- Planning a test suite for a business process chain (ARM workflow, document lifecycle)
- Reviewing `.feature` files for correctness before execution
- Translating manual test plans into automated VA BDD scenarios

## Роль EDT-MCP в этом скилле (узкая — анализ форм)

VA BDD — это **UI-тесты Vanessa**; исполнение идёт через `1c-mcp-crud` + `run-bdd.ps1`. Из EDT-MCP здесь
нужен только **анализ форм** (Stage 1): `get_form_screenshot` · `get_form_layout_snapshot` (⚠ требуют
JVM-флаг `nativeFormBufferedLayoutRender`) · `read_module_source` (Form.Module — имена элементов/обработчики).

⚠ **YAXUnit ≠ VA.** Тестовые EDT-MCP-тулы `run_yaxunit_tests` (+ профилирование `start_profiling` /
`stop_profiling` / `get_profiling_results`) — **отдельный трек юнит-тестов** (см. `mcp-onec-test-runner`
+ Этап 6 `implement-1c-task`), к этому скиллу **не относятся**. Полный справочник 70 тулов — skill
[`edt-mcp`](../edt-mcp/SKILL.md).

## Mandatory 4-Stage Workflow

**NEVER write test steps without completing stages 1 and 2 first.**

```
Stage 1: ANALYZE CONFIGURATION
    Form.xml -> element names, types, custom buttons, visibility conditions
        |
Stage 2: ANALYZE VA DOCUMENTATION
    https://pr-mex.github.io/vanessa-automation/dev/ + WebSearch
        |
Stage 3: WRITE TESTS
    Using confirmed element names + calibrated VA step patterns
        |
Stage 4: VERIFY IN DATABASE
    Check created documents, register records, state transitions
```

---

## Stage 1: Analyze Configuration

### Form Analysis Checklist

For EACH document/processing form involved in the test, complete this checklist
BEFORE writing any Gherkin steps:

```
[ ] 1. Find Form.xml — Grep for Button names, field names, table names
[ ] 2. Check AutoCommandBar — if present, standard buttons (ФормаПровестиИЗакрыть, etc.) are available
[ ] 3. Check custom post buttons — e.g. ФормаСформироватьНомерПробыИЗакрытьДокумент (NOT standard!)
[ ] 4. Identify field types for EACH field:
       - InputField (editable) -> "я ввожу текст"
       - LabelField (readonly) -> CANNOT type into it! Find the real input mechanism
       - RadioButtonField (Tumbler) -> "я меняю значение переключателя"
       - CheckBoxField -> "я устанавливаю флаг" / "я снимаю флаг"
       - DropdownList -> "из выпадающего списка ... я выбираю по строке"
[ ] 5. Check required fields in ОбработкаПроверкиЗаполнения (BSL) AND on the form (FillChecking property)
       THEY MAY DIFFER! The BSL check may be stricter or have conditional logic.
[ ] 6. Check button visibility/accessibility conditions (roles, states, form properties)
[ ] 7. Check if form opens modal dialogs (ПоказатьВводЧисла, ПоказатьВопрос, custom modal forms)
[ ] 8. Check DataPath for fields — the element name on the form may differ from the attribute name
       Example: element name 'Вес' -> DataPath 'Объект.ВесБрутто'
```

### How to Find Element Names

**Primary method — Form.xml analysis:**
```python
# Find ALL buttons on the form
Grep(pattern="<Button.*name=", path="path/to/Form.xml")
# or
Grep(pattern='name="\\w+"', path="path/to/Form.xml")

# Find field types
Grep(pattern="(InputField|LabelField|RadioButtonField|CheckBoxField)", path="path/to/Form.xml")

# Find table names (for DynamicList)
Grep(pattern="<Table.*name=", path="path/to/Form.xml")

# Find command bar
Grep(pattern="AutoCommandBar", path="path/to/Form.xml")
```

**Secondary method — EDT MCP (if available):**
```python
mcp__edt-mcp__get_form_screenshot(project="ProjectName", metadataObject="DataProcessor.Name.Form.FormName")
mcp__edt-mcp__get_metadata_details(project="ProjectName", metadataObject="Document.Name")
```

**Tertiary method — BSL module analysis:**
```python
# Find what happens when a button is clicked
mcp__ast-grep-mcp__ast_grep(
    pattern="Процедура $NAME($$$ARGS)",
    path="path/to/Module.bsl",
    language="bsl"
)

# Search for specific handler
Grep(pattern="Процедура.*Команда\\(", path="path/to/Module.bsl")
```

### Custom Buttons vs Standard Buttons

Standard buttons come from AutoCommandBar and have predictable names:

| Standard Button | Element Name | Behavior |
|----------------|-------------|----------|
| Провести и закрыть | ФормаПровестиИЗакрыть | Post + close |
| Записать | ФормаЗаписать | Write without posting |
| Записать и закрыть | ФормаЗаписатьИЗакрыть | Write + close |
| Создать | ФормаСоздать | Create new |

**Custom buttons override or replace standard ones. ALWAYS check Form.xml!**

Known custom buttons (calibrated):

| Document | Custom Button Name | Replaces |
|----------|-------------------|----------|
| гкс_ФормированиеНомераПробы | ФормаСформироватьНомерПробыИЗакрытьДокумент | ФормаПровестиИЗакрыть |
| гкс_ЛабораторныйАнализ | ФормаПровестиИЗакрыть (standard) | -- (but needs Статус + indicators) |
| гкс_НаправлениеНаРазгрузку | ФормаПровестиИЗакрыть (via AutoCommandBar) | -- (needs role ДоступенДиспетчер) |
| гкс_Взвешивание | ФормаПровестиИЗакрыть (standard) | -- |

---

## Stage 2: Analyze VA Documentation

### Documentation Sources

1. **Official VA docs:** https://pr-mex.github.io/vanessa-automation/dev/
2. **WebSearch** for non-standard controls: `WebSearch("vanessa automation шаг переключатель RadioButton")`
3. **VA source code** (if available): search for step definitions in `vanessa-automation/` directory

### When to Search VA Docs

Search VA documentation when you encounter ANY of these:
- A control type you have not tested before (RadioButtonField, SpreadsheetDocumentField, etc.)
- A VA step that results in "Не найдена процедура для шага"
- A need to interact with a modal dialog (questions, number input, date picker)
- Table operations (row navigation, cell editing, column search)
- A need to wait for asynchronous operations (Пауза, ОбработкаОжидания)

---

## Stage 3: Calibrated VA Step Patterns

Full calibrated step-pattern reference (opening forms, window titles, buttons,
tumblers, input fields, catalog search, DynamicList navigation, Да/Нет
dialogs, closing windows, plus GKSTCPLK-specific examples 3.9-3.15:
weight-input modal, pauses, NnR conditional visibility, lab-analysis status,
choice-form table names, TS pollution) —
[full step-patterns reference](references/step-patterns.md).

**Critical rules to remember (most common failure causes):**
- Use `e1cib/app/` for data processors, NOT `e1cib/form/` ("Неверный тип навигационной ссылки")
- Use element NAME (`с именем 'X'`), not display TITLE (`"X"`), for buttons/fields
- Window titles: wildcard `"*часть*"` — exact titles are fragile
- Tumblers: use the DISPLAY TEXT of the option, not the underlying enum value
- DynamicList: reference-type column search FAILS — use `перехожу к первой строке`
- ПоказатьВопрос() dialogs: prefer `Тогда открылось окно "1С:Предприятие"` + `я нажимаю на кнопку 'Да'`

---

## Stage 4a: Pre-scenario TestDB Data Check (MANDATORY)

**NEVER run a `.feature` scenario without verifying that all referenced
TestDB data exists first.** Missing data (not logic errors) caused 4 of 6
real-world calibration failures; VA burns 120-200s per scenario before
failing on a missing catalog entry — pre-checks eliminate this waste.

Pre-check is automated via **`tools/vanessa/preflight-probe.py`** — a
YAML-driven probe engine (`tools/vanessa/probes/*.yaml`) referenced from the
`.feature` METADATA header (`TS:`, `Catalog:`, `Setting:`, `Role:` tags).
Built-in probes, adding new probes without touching Python, check-engine
primitives, parser types, query templates, the pre-check checklist, output
formats, and the FAIL-handling workflow (create data vs `@pending`) — full
detail in [full pre-check reference](references/testdb-precheck.md).

**Rule:** Run pre-check before `/write-1c-tests` writes steps AND again
before `/run-1c-tests` launches VA (TestDB state may have drifted since
write-time).

---

## Stage 4: Database Verification

After a scenario runs, verify results directly against TestDB: document
existence by number, register records created by the document, catalog
element lookup, info-register latest-value slice. Generic query templates
plus GKSTCPLK examples (checking created documents, state transitions in
`гкс_СостоянияРегистрации`, electronic scoreboard) —
[full DB-verification reference](references/db-verification.md).

---

## Business Process Chains (Reference)

GKSTCPLK has two calibrated chains: **Приемка** (Светлый, 8 ARM buttons:
Прибыл -> ВзвешенБрутто -> ВзятыПробы -> ПринятыПробы -> КачествоПринято ->
ВыгрузкаРазрешена -> Выгружен -> ВзвешенТара -> Убыл) and **Отгрузка** (КАТ,
4 ARM buttons, with a WEIGHT INVERSION vs Приемка — Въезд=Тара / Выезд=Брутто).
Full state diagrams, ARM button -> element name -> document mapping, and the
document map for both chains —
[full business-process-chains reference](references/business-process-chains.md).

---

## Known Issues and Gotchas

Top recurring gotchas: TS names in TestDB are **Cyrillic look-alikes**
(М/Х/А/В/Е), NOT Latin — Latin lookups return 0 rows; DynamicList column
search **fails for reference-type columns** (use `перехожу к первой строке`
instead); form element **name may differ from DataPath/label** (always use
the Form.xml element name, not the visible label). 10 calibrated gotchas in
full — catalog-vs-ARM-table search, form group visibility conditions,
role-gated buttons, re-opening existing documents, ЛабораторныйАнализ status
requirement, automatic "Прибыл" state, Грузополучатель vs Организация —
[full known-issues reference](references/known-issues.md).

---

## Feature File Structure Template

```gherkin
# language: ru

@{TASK-ID} @{category} @{priority}
Функционал: {Descriptive name}
    Как {role}
    Я хочу {goal}
    Чтобы {benefit}

    # METADATA:
    #   Configuration objects: {list}
    #   TestDB data: {list of test entities}
    #   Dependencies: {list of prerequisite feature files}
    #
    # CALIBRATION LOG:
    #   V1  status  Description of verified/unverified point
    #   V2  status  ...

    Контекст:
        Допустим Я запускаю сценарий открытия TestClient или подключаю уже существующий

    @{tag}
    Сценарий: {Short descriptive name}
        # Cleanup
        И Я закрыл все окна клиентского приложения

        # === Precondition: {description} ===
        # ... steps to create prerequisite data ...

        # === Main action: {description} ===
        # ... steps for the test action ...

        # === Verification ===
        # ... assertions and checks ...

        # Cleanup
        И Я закрываю текущее окно
```

### Tagging Conventions

| Tag | Meaning |
|-----|---------|
| `@smoke` | Basic accessibility test (forms open/close) |
| `@P0` | Critical path test |
| `@calibration` | Requires/contains calibration points |
| `@manual_reglament` | Depends on manual scheduled job execution |
| `@probe` | Exploratory/calibration test (not for CI) |
| `@ARM` | Tests ARM (data processor) workflow |
| `@KAT` | Tests on KAT point (dispatch) |
| `@svetly` | Tests on Svetly point (reception) |
| `@real-data` | Uses real TestDB data (not idempotent) |
| `@INT-X.Y` | Integration test, section X.Y |

---

## VA BDD Runner

```powershell
# Single feature file:
powershell -File tools\vanessa\run-bdd.ps1 -Feature "gkstcplk2256/00_smoke.feature"

# All feature files in a directory:
powershell -File tools\vanessa\run-bdd.ps1

# With custom timeout (default 120s):
powershell -File tools\vanessa\run-bdd.ps1 -Feature "..." -TimeoutSec 300
```

**MCP-native alternative — codepilot1c `qa_*`** (`qa_inspect`→`qa_run`): прогон Vanessa из сессии без
PowerShell, через хост EDT-плагина. Proven 2026-07-18 (MFM смоук junit 1/0/0), но рабочий **только
binary-путь** (EDT-runtime сломан на 2025.2.6). Рецепт+ловушки (`bin_path`=exe, `ib_connection` c `Usr=`,
LFS-`.epf`, ложный `infra_error`, слоты dev-лицензии) — skill [`codepilot1c`](../codepilot1c/SKILL.md) +
память `reference_codepilot1c_qa_run_binary_path`. ⚠ `run-bdd.ps1` несёт stale-пути (D:\va-test) → для нового окружения qa_* надёжнее.

**Execution order matters.** Feature files are numbered intentionally:
```
00_smoke.feature           # Basic form accessibility
01_tm1_states.feature      # State transition basics
02_tm3_exclude.feature     # Exclusion scenarios
03_m1_settings.feature     # Settings tests
05_regression.feature      # Regression tests
06_arm_workflow.feature    # Full ARM workflow (depends on 00, 01)
07_kat_dispatch.feature    # KAT dispatch chain (depends on 00)
```

---

## Probe Testing Methodology

When encountering a new form or unfamiliar control, use the probe testing approach:

### Step 1: Smoke Probe
```gherkin
# Can the form be opened at all?
Когда я открываю навигационную ссылку "e1cib/app/Обработка.{Name}"
Тогда открылось окно "*...*"
И Я закрываю текущее окно
```

### Step 2: Element Probe
```gherkin
# Does the button/field exist and is accessible?
И я нажимаю на кнопку с именем '{ButtonName}'
# If this step fails -> wrong element name or button not visible
```

### Step 3: Interaction Probe
```gherkin
# Does the full interaction work?
И я нажимаю на кнопку с именем '{ButtonName}'
Тогда открылось окно "*...*"
# Fill fields...
И я нажимаю на кнопку с именем 'ФормаПровестиИЗакрыть'
# If posting fails -> check required fields
```

### Step 4: Chain Probe
```gherkin
# Does the state transition happen correctly?
# Run steps 1-3, then verify state in database
```

**Create separate `probe_*.feature` files for exploratory tests.** Do not mix probe
scenarios with production test scenarios. Probes may be deleted after calibration
is complete.

---

## Calibration Log Format

Maintain a calibration log in feature file comments:

```gherkin
# CALIBRATION LOG:
#   V1  verified-status  Description
#   V2  verified-status  Description
#
# Status values:
#   confirmed  — verified by successful test run
#   pending    — requires real test run to verify
#   failed     — step does not work, needs alternative
#   workaround — works with alternative step pattern
```

---

## Common Error Messages and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| "Неверный тип навигационной ссылки" | Using `e1cib/form/` for data processors | Use `e1cib/app/Обработка.{Name}` |
| "Кнопка не найдена" | Wrong element name or button not visible | Check Form.xml, check visibility conditions |
| "Не найдена процедура для шага" | Wrong VA step syntax | Check VA docs, use correct step pattern |
| "Поле не найдено" | Wrong field name or field not visible | Check Form.xml element name, check group visibility |
| "Таблица не найдена" | Wrong table name | Check Form.xml for exact table element name |
| "Не удалось перейти к строке" | DynamicList reference column search | Use `перехожу к первой строке` instead |
| "Не удалось открыть форму" | Form requires specific roles | Check access rights for test user |
| "Ошибка при проведении" | Required fields not filled | Check ОбработкаПроверкиЗаполнения for requirements |

---

## How Claude Uses This Skill

### When asked to write VA BDD tests:

1. **Read the task requirements** — understand what needs to be tested
2. **Execute Stage 1** — analyze Form.xml for all involved forms:
   - Find element names, field types, button names
   - Identify custom buttons vs standard AutoCommandBar
   - Check visibility conditions and required fields
3. **Execute Stage 2** — search VA documentation for unfamiliar controls:
   - Use `WebSearch("vanessa automation {control type} шаг")` if needed
4. **Execute Stage 3** — write `.feature` file using ONLY calibrated patterns from this skill:
   - Never invent step patterns — use the exact patterns documented above
   - When uncertain about a pattern, flag it with a calibration comment (V-tag)
   - Add appropriate pauses after state-changing operations
5. **Execute Stage 4** — recommend verification queries for database checks

### When asked to debug a failing test:

1. **Read the error message** — match against the Common Error Messages table
2. **Read the Form.xml** of the form where the step fails
3. **Identify the correct element name or step pattern**
4. **Suggest the fix** using calibrated patterns from this skill

### When asked to extend tests to a new configuration object:

1. **Analyze the new object's Form.xml** (Stage 1)
2. **Map all buttons, fields, tables** with their types
3. **Identify the business process chain** the object belongs to
4. **Write probe tests first**, then production scenarios
5. **Document calibration points** for future reference

---

## Best Practices

### Test Design

- **One scenario = one state transition or one business action.** Do not combine unrelated actions.
- **Always clean up:** start with `И Я закрыл все окна клиентского приложения`
- **Always verify:** after state changes, verify the result (Пауза + window check or DB query)
- **Use numbered file naming** (`00_`, `01_`, ...) to control execution order
- **Separate probe tests** from production tests (use `probe_` prefix)

### Step Writing

- **Prefer element names** (`с именем 'X'`) over display titles (`"X"`)
- **Use wildcard window titles** (`"*часть*имени*"`) to avoid fragile exact matches
- **Add Пауза after async operations** (posting, search, ARM refresh)
- **Do NOT chain multiple actions without pauses** in ARM workflows
- **After EVERY ARM button press** that changes state, wait for ARM refresh:
  ```gherkin
  И Пауза 5
  Тогда открылось окно "*риемк*"
  И Пауза 3
  ```

### Data Management

- **Use unique identifiers** in test data (`'ARM-TM1-001'`, `'KAT-FULL-001'`) for traceability
- **Document real TestDB data** in feature file comments (TS names, catalog values)
- **Check TS name encoding** — in GKSTCPLK TestDB, TS names use Cyrillic characters that look like Latin (М, Х, А, В, Е). Always verify via `execute_query` for your specific configuration

### Calibration

- **Every unverified assumption gets a V-tag** (V1, V2, ...) with status
- **Run probe tests before production tests** for new forms
- **Document failures in calibration log** — they are valuable for future test writers
- **After calibration, update V-tag status** from `pending` to `confirmed` or `failed`

## Common Pitfalls

- Using `e1cib/form/` instead of `e1cib/app/` for data processors
- Using Cyrillic characters when vehicle names are Latin
- Trying to search DynamicList by reference-type column values
- Forgetting to set tumblers before interacting with form groups that depend on them
- Not adding pauses after async operations (ARM refresh, catalog search)
- Using the wrong button name (display title vs element name)
- Assuming standard `ФормаПровестиИЗакрыть` exists when a custom button replaces it
- Confusing form label text with element/attribute names
- Not checking role requirements for button visibility
- Writing tests without analyzing Form.xml first

## Related Skills

- 1c-testing-roadmap — Test roadmap creation methodology (no dedicated skill yet)
- 1c-forms — Managed forms architecture reference (no dedicated skill yet)
- [bsl-development](../bsl-development/SKILL.md) — General 1C/BSL development
- [analyze-1c-task-v2](../analyze-1c-task-v2/SKILL.md) — Task analysis (precedes test writing)
- 1c-registers — Register reference for verification queries (no dedicated skill yet)
- [1c-mcp-crud](../1c-mcp-crud/SKILL.md) — Live database tools (for Stage 4 verification)

## Supporting Resources

- [VA Official Documentation](https://pr-mex.github.io/vanessa-automation/dev/)
- [VA GitHub Repository](https://github.com/pr-mex/vanessa-automation)
- Real calibrated feature files: `features/gkstcplk2256/*.feature`
- BDD Runner: `tools/vanessa/run-bdd.ps1`
