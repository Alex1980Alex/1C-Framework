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

### 3.1 Opening Forms

**Opening data processor forms (ARM):**
```gherkin
# CORRECT — use e1cib/app/ for data processors
Когда я открываю навигационную ссылку "e1cib/app/Обработка.гкс_ПриемкаТранспорта"

# WRONG — e1cib/form/ causes "Неверный тип навигационной ссылки" on platform 8.3.27
# Когда я открываю навигационную ссылку "e1cib/form/Обработка.гкс_ПриемкаТранспорта.Форма.Форма"
```

**Opening document lists:**
```gherkin
Когда я открываю навигационную ссылку "e1cib/list/Документ.гкс_РегистрацияНаПЛК"
Тогда открылось окно "Регистрации на ПЛК"
```

**Opening information register lists:**
```gherkin
Когда я открываю навигационную ссылку "e1cib/list/РегистрСведений.гкс_ЭлектронныеТабло"
Тогда открылось окно "*лектронные табло*"
```

**Navigation link patterns:**

| Object Type | Pattern |
|-------------|---------|
| Data processor (open) | `e1cib/app/Обработка.{Name}` |
| Report (open) | `e1cib/app/Отчет.{Name}` |
| Document list | `e1cib/list/Документ.{Name}` |
| Catalog list | `e1cib/list/Справочник.{Name}` |
| Info register list | `e1cib/list/РегистрСведений.{Name}` |
| Accumulation register list | `e1cib/list/РегистрНакопления.{Name}` |
| Business process list | `e1cib/list/БизнесПроцесс.{Name}` |
| Task list | `e1cib/list/Задача.{Name}` |
| Exchange plan list | `e1cib/list/ПланОбмена.{Name}` |
| Chart of accounts list | `e1cib/list/ПланСчетов.{Name}` |

### 3.2 Window Title Matching

**Use wildcard patterns to avoid fragile exact matches:**
```gherkin
# CORRECT — wildcard catches title variations
Тогда открылось окно "*риемк*"                    # АРМ Приемка
Тогда открылось окно "*звешивани*"                 # Взвешивание
Тогда открылось окно "*ормировани*роб*"            # Формирование номера пробы
Тогда открылось окно "*абораторн*анализ*"          # Лабораторный анализ
Тогда открылось окно "*аправлени*азгрузк*"         # Направление на разгрузку
Тогда открылось окно "*егистрации на ПЛК*"         # Регистрации на ПЛК (list)
Тогда открылось окно "*егистрация на ПЛК*"         # Регистрация на ПЛК (single doc)
Тогда открылось окно "*оменклатура*"               # Номенклатура (catalog)
Тогда открылось окно "*онтрагент*"                 # Контрагенты (catalog)
Тогда открылось окно "*лектронные табло*"           # Электронные табло

# WILDCARD RULES:
# - Start with * to skip uncertain first character (capitalization, article)
# - Use * in the middle to bridge optional words
# - Keep enough characters to be unique
```

### 3.3 Buttons

**Standard form buttons (by element name):**
```gherkin
И я нажимаю на кнопку с именем 'ФормаСоздать'
И я нажимаю на кнопку с именем 'ФормаПровестиИЗакрыть'
И я нажимаю на кнопку с именем 'ФормаЗаписатьИЗакрыть'
```

**Custom command buttons (by element name):**
```gherkin
И я нажимаю на кнопку с именем 'РедактироватьВесНаВъезде'
И я нажимаю на кнопку с именем 'РедактироватьНомерПробы'
И я нажимаю на кнопку с именем 'КомандаПробыПриняты'
И я нажимаю на кнопку с именем 'РедактироватьАнализ'
И я нажимаю на кнопку с именем 'РедактироватьНаправлениеНаРазгрузку'
И я нажимаю на кнопку с именем 'КомандаПодтверждениеРазгрузки'
И я нажимаю на кнопку с именем 'РедактироватьВесНаВыезде'
И я нажимаю на кнопку с именем 'РедактированиеПриемка'
```

**CRITICAL DISTINCTION — button by name vs button by title:**
```gherkin
# By ELEMENT NAME (in Form.xml) — reliable, use this
И я нажимаю на кнопку с именем 'ВвестиВесВручную'

# By DISPLAY TITLE (user-visible text) — fragile, avoid when possible
И я нажимаю кнопку "Да"

# WRONG — "нажимаю кнопку" without "на" and with double quotes for custom buttons
# И я нажимаю кнопку "Автоперевозка"  -- "Не найдена процедура для шага"
```

**Choice button (magnifying glass icon):**
```gherkin
И я нажимаю кнопку выбора у поля с именем 'ТочкаМаршрута'
И я нажимаю кнопку выбора у поля с именем 'Номенклатура'
И я нажимаю кнопку выбора у поля с именем 'Контрагент'
И я нажимаю кнопку выбора у поля с именем 'ТранспортноеСредство'
И я нажимаю кнопку выбора у поля с именем 'Весы'
```

### 3.4 Tumblers (RadioButtonField with Tumbler type)

```gherkin
# CORRECT — use display text of the option, NOT the enum value
И я меняю значение переключателя с именем 'ОтборВидПеревозки' на 'Автоперевозка'
И я меняю значение переключателя с именем 'ОтборТипРегистрации' на 'Приемка'
И я меняю значение переключателя с именем 'ОтборТипРегистрации' на 'Отгрузка'

# WRONG patterns that DO NOT WORK:
# И я нажимаю на кнопку с именем 'ОтборВидПеревозки'  -- "Кнопка не найдена"
# И я нажимаю кнопку "Автоперевозка"                   -- "Не найдена процедура для шага"
# И я устанавливаю переключатель 'ОтборВидПеревозки'   -- wrong step

# IMPORTANT: use DISPLAY TEXT ('Автоперевозка'), NOT enum value ('Автомобиль')
# The RadioButtonField has ChoiceList items with different Presentation vs Value
```

**Alternative syntax for group of radio buttons (also works):**
```gherkin
И из группы переключателей с именем 'ОтборТипРегистрации' я выбираю 'Отгрузка'
```

### 3.5 Input Fields

**Text input:**
```gherkin
И в поле с именем 'НомерДокументаПоставщика' я ввожу текст 'TEST-001'
И в поле с именем 'Вес' я ввожу текст '28000'
И в поле с именем 'ВесПоДокументам' я ввожу текст '15000'
И в поле с именем 'ДатаДокументаПоставщика' я ввожу текст '08.04.2026'
```

**Dropdown selection:**
```gherkin
И из выпадающего списка с именем 'УсловиеПроезда' я выбираю по строке 'DAP'
И из выпадающего списка с именем 'ВидПеревозки' я выбираю по строке 'Автомобиль'
И из выпадающего списка с именем 'Организация' я выбираю по строке 'СОДРУЖЕСТВО-СОЯ ЗАО'
И из выпадающего списка с именем 'ТипРегистрации' я выбираю по строке 'Отгрузка'
```

**Checkbox:**
```gherkin
И я устанавливаю флаг с именем 'Внутригрупповой'
И я снимаю флаг с именем 'Внутригрупповой'
```

**Composite type field (auto-suggest):**
```gherkin
# For fields with composite type (e.g. Организация+Контрагент), direct text input triggers auto-suggest
И в поле с именем 'Собственник' я ввожу текст 'Торговый дом Содружество'
И Пауза 2
```

### 3.6 Catalog Selection (Search in Reference Lists)

**Pattern for selecting from catalogs with search:**
```gherkin
# 1. Click choice button
И я нажимаю кнопку выбора у поля с именем 'Номенклатура'
Тогда открылось окно "*оменклатура*"

# 2. Switch to flat list (disable hierarchy) — IMPORTANT for search
И я нажимаю на кнопку с именем '*ИерархическийСписок'
И Пауза 1

# 3. Activate search bar
И в таблице "Список" я активизирую дополнение формы с именем "СписокСтрокаПоиска"

# 4. Type search text
И в таблице "Список" в дополнение формы с именем 'СписокСтрокаПоиска' я ввожу текст 'Пшеница 3 кл'
И Пауза 5

# 5. Select current (first found) row
И в таблице "Список" я выбираю текущую строку
```

**Notes on catalog search:**
- `*ИерархическийСписок` uses wildcard because the button name may have a prefix
- `Пауза 5` after search is critical — database search takes time
- `Пауза 1` after hierarchy switch allows UI to refresh
- Search bar is a "form extension" (ДополнениеФормы), NOT a regular field

**Simplified pattern for catalogs with a few items (no search needed):**
```gherkin
И я нажимаю кнопку выбора у поля с именем 'ТочкаМаршрута'
Тогда открылось окно "Точки маршрута"
И в таблице "Список" я перехожу к строке:
    | 'Наименование' |
    | 'ПЛК Светлый'  |
И в таблице "Список" я выбираю текущую строку
```

### 3.7 DynamicList Table Navigation

**Navigate to a specific row by column value (works for string/primitive columns):**
```gherkin
И в таблице "СписокРегистрации" я перехожу к строке:
    | 'Авто'   |
    | 'M012YX' |
```

**Navigate to first row (safer for reference-type columns):**
```gherkin
# USE THIS when column values are reference types (ТранспортноеСредство, Контрагент)
# because перехожу к строке with reference value DOES NOT WORK in DynamicList
И в таблице "СписокРегистрации" я перехожу к первой строке
```

**CRITICAL: DynamicList vs ValueTable search behavior:**
```
DynamicList (dynamic query):
  - String/number column search: WORKS with "перехожу к строке"
  - Reference column search: FAILS (value representation mismatch)
  - Use "перехожу к первой строке" as fallback

ValueTable (in-memory):
  - All column types: WORKS with "перехожу к строке"
```

**Select current row (double-click equivalent):**
```gherkin
И в таблице "Список" я выбираю текущую строку
```

### 3.8 ПоказатьВопрос() Dialogs (Yes/No Confirmations)

```gherkin
# CORRECT pattern for 1C standard question dialogs:
Тогда открылось окно "1С:Предприятие"
И я нажимаю на кнопку 'Да'

# ALSO WORKS (with single quotes):
И я нажимаю на кнопку 'Нет'

# ALTERNATIVE (timed, useful when dialog may or may not appear):
И через 2 секунд я нажимаю кнопку 'Да' в вопросе
```

**WRONG patterns:**
```gherkin
# WRONG: title is "1С:Предприятие", NOT the message text
# Тогда открылось окно "*Подтвердите*"   -- may or may not work depending on VA version

# WRONG: double quotes + "нажимаю кнопку" (no "на") for dialog buttons
# И я нажимаю кнопку "Да"  -- "Не найдена процедура для шага" in some VA versions
```

**IMPORTANT DISAMBIGUATION (confirmed from real test runs):**

In calibrated real tests, BOTH of these patterns have been observed to work:
```gherkin
# Pattern A (from probe_arm_tumbler.feature — confirmed working):
Тогда открылось окно "1С:Предприятие"
И я нажимаю на кнопку 'Да'

# Pattern B (from 06_arm_workflow.feature — also used):
Тогда открылось окно "*Подтвердите*"
И я нажимаю кнопку "Да"
```

**Recommendation:** Prefer Pattern A (with "1С:Предприятие" and single quotes) as it is
confirmed from the final calibrated probe tests. Use Pattern B only when you know
the exact dialog title. When uncertain, run a probe test to determine which works
in your specific VA + platform version combination.

---

> **Sections 3.9–3.15 below are CALIBRATED EXAMPLES from the GKSTCPLK transport
> management project.** They illustrate patterns for specific forms and objects.
> For your configuration, perform Stage 1 analysis to discover equivalent patterns.
> The universal VA step syntax (3.1–3.8) applies to any configuration.

### 3.9 Weight Input (Complex Modal Pattern) — *GKSTCPLK example*

When the weight field on the main form is a LabelField (readonly), weight is entered
through a separate mechanism:

```gherkin
# Step 1: Select weighing equipment
И я нажимаю кнопку выбора у поля с именем 'Весы'
Тогда открылось окно "*борудовани*"    # справочник гкс_ОборудованиеПЛК, NOT "Весы"
И в таблице "Список" я перехожу к первой строке
И в таблице "Список" я выбираю текущую строку

# Step 2: Click pencil button for manual weight entry
И я нажимаю на кнопку с именем 'ВвестиВесВручную'
И Пауза 1

# Step 3: Fill weight in modal form (ФормаВводаВесаВручную)
И в поле с именем 'Вес' я ввожу текст '28000'
И я нажимаю на кнопку с именем 'ФормаОК'
И Пауза 1

# Step 4: Post the document
И я нажимаю на кнопку с именем 'ФормаПровестиИЗакрыть'
```

**When to use simple vs complex weight pattern:**

| Situation | Pattern |
|-----------|---------|
| Weight field is InputField (editable) | Simple: `И в поле с именем 'Вес' я ввожу текст '28000'` |
| Weight field is LabelField (readonly) | Complex: Весы selection -> ВвестиВесВручную -> Modal form |
| Not sure | Check Form.xml for field type! |

### 3.10 Pauses and Waiting

```gherkin
# After ARM button press — wait for ARM to refresh
И Пауза 5
Тогда открылось окно "*риемк*"
И Пауза 3

# After catalog search
И Пауза 5    # database search takes time

# After hierarchy toggle
И Пауза 1

# After posting a document
И Пауза 2

# After modal dialog interaction
И Пауза 1

# Before closing ARM (let background handler finish)
И Пауза 3
```

**WHY pauses are necessary:**
- ARM uses `ПодключитьОбработчикОжидания` (0.5s one-shot + 7s background)
- Document posting triggers async register writes
- Catalog search queries the database asynchronously
- Modal dialogs take time to fully initialize

### 3.12 НнР (гкс_НаправлениеНаРазгрузку) — Conditional Field Visibility (calibrated 2026-04-10)

**Critical algorithm** (ObjectModule.bsl:111-117 + Form.Module.bsl:57-82, 150-157):

```bsl
// ObjectModule — обязательна только СлужебнаяНоменклатура (для Приемка)
Если ТипРегистрации = Перечисления.гкс_ТипРегистрации.Приемка Тогда
    ПроверяемыеРеквизиты.Добавить("СлужебнаяНоменклатура");
КонецЕсли;

// Form.Module.ОбработкаПроверкиЗаполненияНаСервере — условная проверка:
Если КачествоНеПринято И Не Объект.ПринятьКачество Тогда
    → "Необходимо Принять качество"
Если КачествоНеПринято И Не ЗначениеЗаполнено(Объект.Комментарий) Тогда
    → "Необходимо заполнить комментарий"
Если Не ЗначениеЗаполнено(Объект.Склад) Тогда
    → "Необходимо заполнить силос"
Если Не ЗначениеЗаполнено(Объект.ЯмаРазгрузки) Тогда
    → "Необходимо заполнить яму разгрузки"

// ПринятьКачествоПриИзменении — динамическая видимость:
ВидимостьСклада = Не КачествоНеПринято ИЛИ Объект.ПринятьКачество;
Элементы.Склад.Видимость = ВидимостьСклада;         ← КЛЮЧ!
Элементы.ЯмаРазгрузки.Видимость = ВидимостьСклада;
```

**ТRAP:** Склад и ЯмаРазгрузки **скрыты по умолчанию** (когда КачествоНеПринято=Истина).
Попытка клика по choice button выдаёт `"Неподходящий тип элемента управления для вызванного действия"`.

**Correct fill order for НнР:**
```gherkin
# 1. СлужебнаяНоменклатура (ObjectModule required for Приемка)
#    Форма: ФормаВыбораСлужебнойНоменклатуры, таблица = 'СписокНоменклатуры' (НЕ 'Список')
И я нажимаю кнопку выбора у поля с именем 'СлужебнаяНоменклатура'
Тогда открылось окно "*оменклатура*"
И Пауза 2
И в таблице "СписокНоменклатуры" я перехожу к первой строке
И в таблице "СписокНоменклатуры" я выбираю текущую строку
И Пауза 1

# 2. ПринятьКачество flag ← CRITICAL — делает Склад/Яма видимыми
И я устанавливаю флаг с именем 'ПринятьКачество'
И Пауза 2

# 3. Комментарий (обязателен когда КачествоНеПринято)
И в поле с именем 'Комментарий' я ввожу текст 'Автотест'
И Пауза 1

# 4. Склад (теперь видимый)
И я нажимаю кнопку выбора у поля с именем 'Склад'
Тогда открылось окно "*аршрут*"
И в таблице "Список" я перехожу к первой строке
И в таблице "Список" я выбираю текущую строку
И Пауза 1

# 5. ЯмаРазгрузки (теперь видимая)
И я нажимаю кнопку выбора у поля с именем 'ЯмаРазгрузки'
Тогда открылось окно "*аршрут*"
И в таблице "Список" я перехожу к первой строке
И в таблице "Список" я выбираю текущую строку
И Пауза 1

И я нажимаю на кнопку с именем 'ФормаПровестиИЗакрыть'
```

**Note on Склад/Яма persistence:** Despite filling the choice values, the final document
may have `Склад=<>` and `ЯмаРазгрузки=<>` because `гкс_ПриемкаТранспорта.ПропуститьИнициализациюМестаРазгрузки(ВидПеревозки)`
returns True for Автомобиль, which makes these fields optional at posting time. The document still posts
successfully. The values are stored in tabular section `ДоступныеМестаРазгрузки` for persistence.

### 3.13 ЛабораторныйАнализ — Statе Transition Requirement (calibrated 2026-04-10)

The lab analysis does NOT transition state to КачествоПринято automatically on post. It requires:
- `Статус = "Выполнен"` (NOT "Выполнено"! — enum value: `гкс_СтатусыЛабораторногоАнализа.Выполнен`)
- Other quality indicators (if КачествоНеПринято)

```gherkin
И я нажимаю на кнопку с именем 'РедактироватьАнализ'
Тогда открылось окно "*абораторн*анализ*"
# Статус по умолчанию = "Отбор пробы" — НЕ переведёт в КачествоПринято
И из выпадающего списка с именем 'Статус' я выбираю по строке 'Выполнен'
И Пауза 1
И я нажимаю на кнопку с именем 'ФормаПровестиИЗакрыть'
И Пауза 2
```

**Enum values for `гкс_СтатусыЛабораторногоАнализа`:**
- `ОтборПробы` / "Отбор пробы" (default)
- `Выполняется` / "Выполняется"
- `Выполнен` / "Выполнен" ← use this for test
- `ПовторныйАнализ` / "Повторный анализ"
- `ВозвратОтмена` / "Возврат (Отмена)"

After setting `Выполнен`, state transitions to `РезультатыПробПолучены` (not directly to КачествоПринято,
but this IS enough for the "На разгрузку" button to activate).

### 3.14 Choice Forms Table Names (calibrated 2026-04-10)

Not all catalog choice forms use the standard `'Список'` table name. Known exceptions:

| Catalog | Choice Form | Table Name |
|---------|------------|------------|
| Номенклатура (СлужебнаяНоменклатура context) | ФормаВыбораСлужебнойНоменклатуры | **`СписокНоменклатуры`** |
| Номенклатура (standard) | ФормаВыбора | `Список` |
| гкс_ТочкиМаршрута | ФормаВыбора | `Список` |
| ТранспортныеСредства | ФормаВыбора | `Список` |

**Rule:** When opening a custom choice form (title contains "Выбор X: ..."), check Form.xml
for the actual `<Table name="...">` element.

### 3.15 TS Registration Pollution — Fresh TS Per Scenario

When a test creates multiple registrations for the same TS, the ARM table accumulates
stale rows. VA's `перехожу к строке` may select the wrong row (oldest match instead of newest).

**Rule:** Use a **different fresh ПЛК ТС** for each test scenario. Fresh = `ЭтоСправочникПЛК=Да`
with zero active registrations (all previous registrations are in `Убыл` state).

```gherkin
# Bad — both scenarios use same TS, ARM shows 2 rows, test picks wrong one
Сценарий: ARM-TM1 ... использует М360ЕВ
Сценарий: ARM-FULL ... использует М360ЕВ

# Good — separate TS per scenario
Сценарий: ARM-TM1 ... использует М213КВ
Сценарий: ARM-FULL ... использует М360ЕВ
```

### 3.11 Closing Windows

```gherkin
# Close by title
И Я закрываю окно "Регистрации на ПЛК"

# Close current window
И Я закрываю текущее окно

# Close ALL windows (cleanup before scenario)
И Я закрыл все окна клиентского приложения
```

---

## Stage 4a: Pre-scenario TestDB Data Check (MANDATORY)

**NEVER run a `.feature` scenario without verifying that all referenced TestDB data
exists first.** 4 out of 6 real-world test failures in calibration sessions were
caused by missing test data — not by logic errors. VA takes 120–200 seconds per
scenario before failing on a missing catalog entry; pre-checks eliminate this waste.

### Automated preflight (YAML-driven, since 2026-04-11)

Pre-check is automated via **`tools/vanessa/preflight-probe.py`** — a universal,
YAML-driven probe engine. Drop probe definitions into `tools/vanessa/probes/*.yaml`
and reference them from the METADATA header of the `.feature` file:

```gherkin
# METADATA:
#   Task: GKSTCPLK-2256                # freeform — used by /run-1c-tests
#   Dependencies: 00_smoke.feature     # freeform — chain graph
#
#   # Machine-readable probes — consumed by preflight-probe.py
#   TS: М012УХ, Х985ХМ36RUS (fresh, PLK)
#   Catalog: Номенклатура[Рапс (Россия), Пшеница 3 кл 13.5% протеин]
#   Catalog: Контрагенты[ЯхимовщинаАгро]
#   Setting: НастройкаЭлектронногоТабло[ПЛК Светлый/НеПрошедшиеРегистрацию]
#   Role: ДоступенДиспетчер
```

**Built-in probes** (`tools/vanessa/probes/`):

| Tag | YAML file | Scope | Parser |
|-----|-----------|-------|--------|
| `Catalog` | `catalog.yaml` | Universal — any 1C catalog | `bracketed_list` |
| `Role` | `role.yaml` | Universal — always SKIP | `literal` |
| `TS` | `ts.yaml` | Project-specific (ТранспортныеСредства + ЭтоСправочникПЛК + гкс_СостоянияРегистрации) | `csv_with_flags` |
| `Setting` | `setting.yaml` | Project-specific (гкс_НастройкаЭлектронногоТабло) | `bracketed_slashed` |

**Adding a new probe** (no Python changes needed):

```yaml
# tools/vanessa/probes/document.yaml
tag: Document
enabled: true
parser:
  type: bracketed_list
  pattern: '^(?P<catalog>\S+)\[(?P<items>.+)\]$'
  item_separator: ","
  item_label: "{catalog}[{item}]"
checks:
  - name: exists
    always: true
    query: |
      ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Cnt ИЗ Документ.{catalog}
      ГДЕ Номер = &Name И НЕ ПометкаУдаления
    params: {Name: "{item}"}
    expect: field_positive
    expect_field: Cnt
    on_fail: "not found"
    on_pass_label: "found"
```

After saving the YAML, add `Document: ЗаказКлиента[ЗК-001, ЗК-002]` to any
feature file's METADATA — preflight auto-discovers the new probe.

**Check engine primitives** (all probes compose from these):

| `expect` type | Behaviour | Use for |
|---|---|---|
| `non_empty` | At least 1 row returned | existence / role |
| `field_truthy` | `rows[0][<field>]` is truthy | boolean flags like `ЭтоСправочникПЛК` |
| `field_positive` | `int(rows[0][<field>]) > 0` | `КОЛИЧЕСТВО(*)` > 0 |
| `field_zero` | `int(rows[0][<field>]) == 0` or empty | freshness / "no active X" |
| `field_equals` | `rows[0][<field>] == expect_value` | exact value match |

**Parser types** (how METADATA raw string becomes check items):

| Parser | METADATA example | Items produced |
|---|---|---|
| `csv_with_flags` | `Name1, Name2 (fresh, PLK)` | `[{item: Name1, flags: {fresh, plk}}, {item: Name2, ...}]` |
| `bracketed_list` | `Catalog[item1, item2]` | `[{catalog: Catalog, item: item1}, ...]` |
| `bracketed_slashed` | `Name[Point/Kind]` | `[{name, point, kind, item: raw}]` |
| `literal` | `RoleName` | `[{item: RoleName, literal: RoleName}]` |

**Reglament triggers** (`tools/vanessa/jobs/*.yaml`) use the same pattern:
each YAML defines a named BSL snippet. `trigger-reglament.py --job <name>`
loads and executes it. Add new jobs without touching Python.

Freeform METADATA fields (`Task`, `Logical block`, `Dependencies`, `Configuration objects`,
`CALIBRATION LOG`) **coexist** in the same block — preflight-probe ignores unknown
tags; `/run-1c-tests` reads `Dependencies` for its chain graph.

---

### Why This Matters

Every `.feature` file implicitly depends on TestDB state:
- Catalog entries (ТС, Номенклатура, Контрагенты, Точки маршрута)
- Register settings (гкс_НастройкаЭлектронногоТабло, etc.)
- User roles (ДоступенДиспетчер, etc.)
- Fresh-state transports (TS with zero active registrations)

If ANY of these are missing, VA will fail somewhere in the middle of the scenario
with a misleading error ("Кнопка не найдена", "Строка не найдена в таблице"). The
real cause — missing data — is not obvious from the VA log.

**Rule:** Before launching `/run-1c-tests` (or any manual VA run), execute a
pre-check query for EVERY referenced data item.

### When to Run Pre-check

- **Always** before writing `.feature` files (as part of `/write-1c-tests` Фаза 4)
- **Always** before running a scenario (as part of `/run-1c-tests` pre-flight)
- **Always** after restoring/resetting the TestDB

### Pre-check Query Templates

**1. Catalog entry existence (generic):**
```python
mcp__1c-mcp-crud__execute_query(
    query="""ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Кол
    ИЗ Справочник.ТранспортныеСредства
    ГДЕ Наименование = &Name И НЕ ПометкаУдаления""",
    parameters={"Name": "М012ВР"}
)
# Expected: Кол = 1. If 0 -> BLOCKER.
```

**2. Fresh transport (no active registrations):**
```python
mcp__1c-mcp-crud__execute_query(
    query="""ВЫБРАТЬ ТС.Наименование
    ИЗ Справочник.ТранспортныеСредства КАК ТС
        ЛЕВОЕ СОЕДИНЕНИЕ РегистрСведений.гкс_СостоянияРегистрации.СрезПоследних КАК Сост
            ПО Сост.ДокументРегистрации.ТранспортноеСредство = ТС.Ссылка
                И Сост.Состояние <> ЗНАЧЕНИЕ(Перечисление.гкс_СостоянияРегистрации.Убыл)
    ГДЕ ТС.Наименование = &Name
        И ТС.ЭтоСправочникПЛК = ИСТИНА
        И НЕ ТС.ПометкаУдаления
    СГРУППИРОВАТЬ ПО ТС.Наименование
    ИМЕЮЩИЕ КОЛИЧЕСТВО(Сост.Состояние) = 0""",
    parameters={"Name": "М360ЕВ"}
)
# Expected: 1 row. If empty -> TS has active registrations, pick another.
```

**3. Information register setting exists:**
```python
mcp__1c-mcp-crud__execute_query(
    query="""ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Кол
    ИЗ РегистрСведений.гкс_НастройкаЭлектронногоТабло
    ГДЕ ТочкаМаршрута = &Point И ВидТабло = &Kind""",
    parameters={"Point": "ПЛК Светлый", "Kind": "НеПрошедшиеРегистрацию"}
)
# Expected: Кол >= 1. If 0 -> add setting before running test.
```

**4. User roles available:**
```python
mcp__1c-mcp-crud__get_access_rights(
    object_description={"name": "Обработка.гкс_ПриемкаТранспорта"}
)
# Check response for required roles (ДоступенДиспетчер, etc.)
# If missing -> grant role or use different test user.
```

**5. Enum value exists (for ТипРегистрации, ВидПеревозки, Состояния):**
```python
mcp__1c-mcp-crud__execute_query(
    query="""ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Кол
    ИЗ Перечисление.гкс_СостоянияРегистрации
    ГДЕ Ссылка = ЗНАЧЕНИЕ(Перечисление.гкс_СостоянияРегистрации.Прибыл)"""
)
# Expected: Кол = 1. Enum shouldn't disappear, but sanity check for renamed enums.
```

### Pre-check Checklist per Scenario

For each scenario in the `.feature` file, run through this list:

- [ ] All vehicle numbers (ТС) exist in `Справочник.ТранспортныеСредства`
- [ ] All vehicles used have `ЭтоСправочникПЛК = Истина` (if the form filters by it)
- [ ] All vehicles are "fresh" (no active registrations) OR the scenario tolerates stale state
- [ ] All catalog items (Номенклатура, Контрагенты, Организации, Склады, ЯмыРазгрузки) exist
- [ ] All route points (Точки маршрута) exist
- [ ] Required register settings exist (табло, настройки, параметры)
- [ ] Test user has all required roles for buttons/commands used in the scenario
- [ ] Enum values referenced in verification queries exist

### Pre-check Output Formats

**In `.feature` file header** (document the data assumptions):
```gherkin
# METADATA:
#   TestDB data requirements:
#     - ТС: М360ЕВ, М213КВ (must be fresh, ЭтоСправочникПЛК=Истина)
#     - Номенклатура: Пшеница 3кл, Пшеница 4кл
#     - Контрагенты: Торговый дом Содружество
#     - Настройки: ПЛК Светлый / НеПрошедшиеРегистрацию (2 шт)
#     - Роли пользователя: ДоступенДиспетчер
#
#   Pre-check status (YYYY-MM-DD):
#     [OK]    ТС М360ЕВ exists, fresh
#     [OK]    ТС М213КВ exists, fresh
#     [FAIL]  Роль ДоступенДиспетчер НЕ назначена пользователю a.terletskiy
#             -> BLOCKER: grant role before running
```

**In Claude's output to user** (before launching VA):
```
Pre-check GKSTCPLK-2256 / 06_arm_workflow.feature:
  [OK]    3/3 ТС exist and are fresh (М360ЕВ, М213КВ, Х985ХМ36RUS)
  [OK]    5/5 номенклатур найдены
  [OK]    Настройка "ПЛК Светлый / НеПрошедшиеРегистрацию" существует
  [FAIL]  Роль ДоступенДиспетчер отсутствует у тестового пользователя

BLOCKER: scenario ARM-FULL will fail on step "я нажимаю на кнопку РедактироватьНаправлениеНаРазгрузку"
         -> grant ДоступенДиспетчер OR mark scenario as @pending
```

### What to Do on Pre-check FAIL

Two options, depending on the blocker type:

**Option 1 — Create missing data** (preferred for predictable setup):
```python
# Use execute_code to prepare data on TestDB
mcp__1c-mcp-crud__execute_code(code="""
    Контрагент = Справочники.Контрагенты.СоздатьЭлемент();
    Контрагент.Наименование = "Тестовый контрагент BDD";
    Контрагент.Записать();
""")
```
Then re-run pre-check to confirm.

**Option 2 — Mark scenario as `@pending`** (when data creation is non-trivial):
```gherkin
@pending
Сценарий: ARM-FULL — full workflow
  # BLOCKED by: role ДоступенДиспетчер missing on test user
  # Unblock: grant role in configurator, re-run pre-check
  ...
```

Scenarios marked `@pending` are SKIPPED by `/run-1c-tests` until unblocked.

### Integration with /write-1c-tests and /run-1c-tests

**During `/write-1c-tests` Фаза 4** (test writing):
- BEFORE writing scenario steps, run pre-check for ALL data items the scenario
  will reference
- Include pre-check results in the METADATA header
- If any blockers — either generate `execute_code` setup in `Контекст:` block OR
  mark the scenario `@pending`

**During `/run-1c-tests` pre-flight** (test execution):
- Re-run pre-check on CURRENT TestDB state (data may have changed since write-time)
- Fail fast: if any blocker — do NOT launch VA, report to user
- Only launch VA after all scenarios pass pre-check

### Time Budget Analysis

| Approach | Time per scenario (on FAIL) |
|----------|-----------------------------|
| No pre-check | 120–200s (VA timeout + teardown) |
| Pre-check via `execute_query` | 0.5–2s per query |
| Pre-check for whole scenario (~10 items) | 5–20s total |

**Savings:** ~95% of wasted time on data-related failures. Real calibration session
of `features/gkstcplk2256/` had 4 FAILs averaging 150s each = 10 minutes wasted.
Pre-check would have caught all 4 in ~30 seconds.

---

## Stage 4: Database Verification

### Generic Verification Templates (any configuration)

**Document exists by number:**
```python
mcp__1c-mcp-crud__execute_query(
    query="""ВЫБРАТЬ Номер, Дата, Проведен
    ИЗ Документ.{ТипДокумента}
    ГДЕ Номер = &Num И НЕ ПометкаУдаления""",
    parameters={"Num": "TEST-001"}
)
```

**Register records created by document:**
```python
mcp__1c-mcp-crud__execute_query(
    query="""ВЫБРАТЬ * ИЗ РегистрНакопления.{ИмяРегистра}
    ГДЕ Регистратор = &Ref""",
    parameters={"Ref": "<document-uuid>"}
)
```

**Catalog element by name:**
```python
mcp__1c-mcp-crud__execute_query(
    query="""ВЫБРАТЬ Ссылка, Код, Наименование
    ИЗ Справочник.{ИмяСправочника}
    ГДЕ Наименование = &Name И НЕ ПометкаУдаления""",
    parameters={"Name": "TestValue"}
)
```

**Info register latest value:**
```python
mcp__1c-mcp-crud__execute_query(
    query="""ВЫБРАТЬ * ИЗ РегистрСведений.{ИмяРегистра}.СрезПоследних(, {Измерение} = &Val)""",
    parameters={"Val": "SomeValue"}
)
```

### GKSTCPLK Project Examples

> The examples below use `гкс_*` object names from the GKSTCPLK transport management
> configuration. Replace with your own object names.

**Checking Created Documents** *(GKSTCPLK example)*

```python
# After test run, verify documents were created:
mcp__1c-mcp-crud__execute_query(
    query="""ВЫБРАТЬ
        Рег.Ссылка,
        Рег.Номер,
        Рег.Дата,
        Рег.ТранспортноеСредство,
        Рег.Проведен
    ИЗ Документ.гкс_РегистрацияНаПЛК КАК Рег
    ГДЕ Рег.НомерДокументаПоставщика = &НомерТН
    УПОРЯДОЧИТЬ ПО Рег.Дата УБЫВ""",
    limit=5
)
```

### Checking Register Records

```python
# Verify state transitions in СостоянияРегистрации:
mcp__1c-mcp-crud__execute_query(
    query="""ВЫБРАТЬ
        С.ДокументРегистрации,
        С.Состояние,
        С.Период
    ИЗ РегистрСведений.гкс_СостоянияРегистрации КАК С
    ГДЕ С.ДокументРегистрации = &Ссылка
    УПОРЯДОЧИТЬ ПО С.Период""",
    limit=20
)
```

### Checking Electronic Scoreboard

```python
# Verify scoreboard content:
mcp__1c-mcp-crud__execute_query(
    query="""ВЫБРАТЬ
        Т.ВидТабло,
        Т.ТранспортноеСредство,
        Т.НомерСтроки
    ИЗ РегистрСведений.гкс_ЭлектронныеТабло КАК Т
    ГДЕ Т.ТочкаМаршрута = &ТочкаМаршрута""",
    limit=50
)
```

---

## Business Process Chains (Reference)

### Chain 1: Приемка (Светлый) — 8 ARM buttons

```
гкс_РегистрацияНаПЛК (auto "Прибыл")
    |
    v
АРМ (ОтборВидПеревозки=Автоперевозка, ОтборТипРегистрации=Приемка):

Прибыл
    | [Въезд: РедактироватьВесНаВъезде -> гкс_Взвешивание]
    v
ВзвешенБрутто
    | [Номер пробы: РедактироватьНомерПробы -> гкс_ФормированиеНомераПробы]
    v
ВзятыПробы
    | [Принять пробы: КомандаПробыПриняты -> Вопрос Да/Нет]
    v
ПринятыПробы
    | [Анализ: РедактироватьАнализ -> гкс_ЛабораторныйАнализ]
    v
КачествоПринято
    | [На разгрузку: РедактироватьНаправлениеНаРазгрузку -> гкс_НаправлениеНаРазгрузку]
    v
ВыгрузкаРазрешена
    | [Разгрузка: КомандаПодтверждениеРазгрузки -> Вопрос Да/Нет]
    v
Выгружен
    | [Выезд: РедактироватьВесНаВыезде -> гкс_Взвешивание]
    v
ВзвешенТара
    | [Приемка: РедактированиеПриемка -> прямой Убыл / ФормаОтклонениеНормПогрузки]
    v
Убыл
```

### Chain 2: Отгрузка (КАТ) — 4 ARM buttons

```
гкс_РегистрацияНаПЛК (ТипРегистрации=Отгрузка, auto "Прибыл")
    |
    v
АРМ (ОтборВидПеревозки=Автоперевозка, ОтборТипРегистрации=Отгрузка):

Прибыл
    | [Въезд=Тара: РедактироватьВесНаВъезде -> гкс_Взвешивание]
    v
ВзвешенТара                    ** WEIGHT INVERSION vs Приемка **
    | [Погрузка: КомандаПодтверждениеРазгрузки -> Вопрос "погружен"]
    v
Погружен
    | [Выезд=Брутто: РедактироватьВесНаВыезде -> гкс_Взвешивание]
    v
ВзвешенБрутто                  ** WEIGHT INVERSION vs Приемка **
    | [Убытие: РедактированиеПриемка -> прямой Убыл]
    v
Убыл
```

**WEIGHT INVERSION RULE:**
```
Приемка:  Въезд = Брутто (loaded truck arrives),   Выезд = Тара (empty truck leaves)
Отгрузка: Въезд = Тара   (empty truck arrives),    Выезд = Брутто (loaded truck leaves)
```

### ARM Button -> Element Name -> Document Mapping

| Button (UI) | Element Name | Document | Post Button |
|-------------|-------------|----------|-------------|
| Въезд | РедактироватьВесНаВъезде | гкс_Взвешивание | ФормаПровестиИЗакрыть |
| Номер пробы | РедактироватьНомерПробы | гкс_ФормированиеНомераПробы | ФормаСформироватьНомерПробыИЗакрытьДокумент |
| Принять пробы | КомандаПробыПриняты | (dialog Да/Нет) | кнопка 'Да' |
| Анализ | РедактироватьАнализ | гкс_ЛабораторныйАнализ | ФормаПровестиИЗакрыть |
| На разгрузку | РедактироватьНаправлениеНаРазгрузку | гкс_НаправлениеНаРазгрузку | ФормаПровестиИЗакрыть |
| Разгрузка | КомандаПодтверждениеРазгрузки | (dialog Да/Нет) | кнопка 'Да' |
| Выезд | РедактироватьВесНаВыезде | гкс_Взвешивание | ФормаПровестиИЗакрыть |
| Приемка | РедактированиеПриемка | (direct state change / ФормаОтклонениеНормПогрузки) | -- |

### Document Map (Both Chains)

| Document | Приемка | Отгрузка | Created By |
|----------|---------|----------|------------|
| гкс_ЗаписьВОчередьПриемкиПЛК | Yes | -- | Manual form |
| гкс_ЗаписьВОчередьОтгрузкиПЛК | -- | Yes | Manual form |
| гкс_РегистрацияНаПЛК | Yes | Yes | Manual form |
| гкс_Взвешивание | x2 (Въезд + Выезд) | x2 (Въезд + Выезд) | ARM buttons |
| гкс_ФормированиеНомераПробы | Yes | -- | ARM button |
| гкс_ЛабораторныйАнализ | Yes | -- | ARM button |
| гкс_НаправлениеНаРазгрузку | Yes (ARM) | Yes (external) | ARM / external |

---

## Known Issues and Gotchas

### 1. Transport Vehicle Names are CYRILLIC (calibrated 2026-04-10)

**CORRECTION:** In the TestDB, TS names are **Cyrillic**, NOT Latin:
```
Х985ХМ36RUS, Х987ВТ193RUS, А088ЕА62RUS, М012УХ, М360ЕВ, М213КВ
```
All characters before `RUS` are **Cyrillic**. Using Latin lookalikes (`M`, `X`, `Y`, `A`)
causes search to return 0 rows. Verified via `mcp__1c-mcp-crud__execute_code` —
database returns Cyrillic representations.

**Choice form filter `ЭтоСправочникПЛК=Истина`:** When selecting TS from a
Регистрация/НнР form, the choice form pre-filters by `ЭтоСправочникПЛК=Истина`
AND `ВидПеревозки=Автомобиль`. If the TS you search for has `ЭтоСправочникПЛК=Нет`,
the search returns 0 rows even though the TS exists.

Query to find usable ПЛК ТС without active registrations:
```sql
ВЫБРАТЬ ТС.Наименование ИЗ Справочник.ТранспортныеСредства КАК ТС
    ЛЕВОЕ СОЕДИНЕНИЕ РегистрСведений.гкс_СостоянияРегистрации.СрезПоследних КАК Сост
        ПО Сост.ДокументРегистрации.ТранспортноеСредство = ТС.Ссылка
            И Сост.Состояние <> ЗНАЧЕНИЕ(Перечисление.гкс_СостоянияРегистрации.Убыл)
ГДЕ ТС.ЭтоСправочникПЛК = ИСТИНА
    И НЕ ТС.ПометкаУдаления
    И ТС.ВидПеревозки = ЗНАЧЕНИЕ(Перечисление.гкс_ТипыТранспортныхСредствДоставки.Автомобиль)
СГРУППИРОВАТЬ ПО ТС.Наименование
ИМЕЮЩИЕ КОЛИЧЕСТВО(Сост.Состояние) = 0
```

### 2. Search in Catalog vs ARM Table

- Catalog search (Справочник): uses partial match (`М012УХ` finds `M012YX` sometimes)
- ARM table (DynamicList): shows full representation (may include `RUS` suffix)
- Always verify the exact representation in the ARM table before writing row search steps

### 3. DynamicList Column Search Limitation

`перехожу к строке` with column value does NOT work for reference-type columns in
DynamicList. The value representation does not match what VA expects.

**Workaround:** Use `перехожу к первой строке` when you can guarantee the target
row is first, or ensure the search column contains a string/number (not a reference).

### 4. Form Group Visibility Conditions

ARM main group may be hidden until both tumblers are set:
```
ГруппаОсновная.Видимость = УстановленОтборТочкаМаршрута И УстановленОтборВидПеревозки
```
Set ALL tumblers before trying to interact with the main form area, and add a Пауза
after setting them to allow the form to refresh.

### 5. Button Availability Depends on Roles

Example: `РедактироватьНаправлениеНаРазгрузку` requires role `ДоступенДиспетчер`.
If the test user does not have this role, the button will not be visible/clickable.

### 6. Re-opening Existing Documents

If the TS has already passed through a state, clicking the ARM button opens the
existing document (not creation). Custom buttons may be hidden for existing
(already posted) documents.

### 7. ЛабораторныйАнализ is NOT Just "Провести"

For production scenarios, ЛабораторныйАнализ requires:
- Статус = "Выполнено" (set via the status field)
- Quality indicator checkboxes (varies by configuration)

For test scenarios without quality deviations, the form may be postable immediately
if required fields are pre-filled.

### 8. State "Прибыл" is AUTOMATIC

The initial state "Прибыл" is set as a document movement when гкс_РегистрацияНаПЛК
is posted (ManagerModule). No manual register write is needed. The state appears
immediately after `ФормаПровестиИЗакрыть` on the registration document.

### 9. Grузополучатель vs Организация

On the form, the field may be labeled "Грузополучатель" but the metadata attribute
name is `Организация`. ALWAYS use the metadata attribute name (element name from
Form.xml), NOT the form label.

### 10. Field Name =/= DataPath

The element name on the form may differ from the data path:
```
Element name: 'Вес'            -> DataPath: 'Объект.ВесБрутто'
Element name: 'ВесПоДокументам' -> DataPath: 'Объект.ВесНетто'
```
Use the ELEMENT NAME in VA steps, not the DataPath or attribute name.

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
