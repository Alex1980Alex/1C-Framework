# Preflight Probes for VA BDD Testing

YAML-driven preflight checks that verify TestDB data before running VA BDD scenarios.
The `preflight-probe.py` engine reads every `.yaml` file from this directory, parses
`METADATA` tags from `.feature` files, and executes 1C queries against the live TestDB.

No Python changes needed to add a new probe — just drop a YAML file here.

## 1. Quick Start

**30 seconds to a working probe:**

```yaml
# tools/vanessa/probes/document.yaml
tag: Document
description: Document existence by number
enabled: true

parser:
  type: bracketed_list
  item_separator: ","
  item_label: "{catalog}[{item}]"

checks:
  - name: exists
    always: true
    query: |
      ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Cnt
      ИЗ Документ.{catalog}
      ГДЕ Номер = &Name И НЕ ПометкаУдаления
    params:
      Name: "{item}"
    expect: field_positive
    expect_field: Cnt
    on_fail: "not found"
    on_pass_label: "found"
```

Use in your `.feature` file:

```gherkin
# METADATA:
#   Document: ЗаказКлиента[ЗК-001, ЗК-002]
```

Done. Preflight will check both documents before VA launch.

---

## 2. YAML Structure Reference

### Top-Level Fields

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `tag` | string | Yes | — | METADATA key this probe reacts to |
| `description` | string | No | `""` | Human-readable description |
| `enabled` | bool | No | `true` | Set `false` to disable without deleting |
| `default_status` | string | No | — | Override result (e.g. `SKIP` for role.yaml) |
| `default_message` | string | No | — | Message when default_status is used |

### `parser` Block

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | Yes | `csv_with_flags`, `bracketed_list`, `bracketed_slashed`, `literal` |
| `pattern` | regex | No | Override regex for parsing (named groups become variables) |
| `item_separator` | string | No | Separator between items (default `,`) |
| `flags_regex` | regex | No | Regex to extract flags (csv_with_flags only) |
| `flag_separator` | string | No | Separator between flags (default `,`) |
| `item_label` | string | No | Label template for log messages |

### `checks[]` Block

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | Yes | Check name (used in log output) |
| `always` | bool | No | `true` = run unconditionally |
| `if_flag` | string | No | Run only when this flag is present in parsed data |
| `query` | string | Yes* | 1C query (ВЫБРАТЬ...). Template vars: `{item}`, `{catalog}`, etc. |
| `params` | dict | No | Query parameters: `{ParamName: "{variable}"}` |
| `expect` | string | Yes* | Check primitive: `non_empty`, `field_truthy`, `field_positive`, `field_zero`, `field_equals` |
| `expect_field` | string | No* | Field name for field_* checks |
| `expect_value` | string | No | Expected value for `field_equals` |
| `on_fail` | string | No | Message on failure (supports `{field}` substitution) |
| `on_pass_label` | string | No | Short label on success (e.g. "found", "fresh") |

*Not required if `default_status` is set at top level (e.g. role.yaml).

---

## 3. Parser Types

### csv_with_flags

Comma-separated items with optional flags in parentheses.

**METADATA:** `TS: М012УХ, Х985ХМ36RUS (fresh, PLK)`

**YAML:**
```yaml
parser:
  type: csv_with_flags
  item_separator: ","
  flags_regex: '\(([^)]*)\)'
  flag_separator: ","
```

**Variables in checks:** `{item}` — each item name. Flags accessed via `if_flag: "PLK"`.

**Reference:** [ts.yaml](ts.yaml)

---

### bracketed_list

Type name followed by items in square brackets.

**METADATA:** `Catalog: Номенклатура[Пшеница 3 кл, Рапс (Россия)]`

**YAML:**
```yaml
parser:
  type: bracketed_list
  pattern: '^(?P<catalog>\S+)\[(?P<items>.+)\]$'
  item_separator: ","
  item_label: "{catalog}[{item}]"
```

**Variables in checks:** `{catalog}` — type before brackets, `{item}` — each item.

**Reference:** [catalog.yaml](catalog.yaml)

---

### bracketed_slashed

Name with slash-separated segments in brackets.

**METADATA:** `Setting: НастройкаЭлектронногоТабло[ПЛК Светлый/НеПрошедшиеРегистрацию]`

**YAML:**
```yaml
parser:
  type: bracketed_slashed
  pattern: '^(?P<name>\S+)\[(?P<point>[^/]+)/(?P<kind>[^\]]+)\]$'
  item_label: "{name}[{point}/{kind}]"
```

**Variables in checks:** `{name}`, `{point}`, `{kind}` — from named groups in pattern.

**Reference:** [setting.yaml](setting.yaml)

---

### literal

Entire value as a single string. No parsing.

**METADATA:** `Role: ДоступенДиспетчер`

**YAML:**
```yaml
parser:
  type: literal
  item_label: "{literal}"
```

**Variables in checks:** `{item}`, `{literal}` — the raw string.

**Reference:** [role.yaml](role.yaml)

---

## 4. Check Primitives

### non_empty

Query must return **at least 1 row**.

```yaml
- name: exists
  query: |
    ВЫБРАТЬ ТС.Наименование
    ИЗ Справочник.ТранспортныеСредства КАК ТС
    ГДЕ ТС.Наименование = &Name И НЕ ТС.ПометкаУдаления
  params:
    Name: "{item}"
  expect: non_empty
```

### field_truthy

`rows[0][field]` is truthy (not empty, not `0`, not `Ложь`).

```yaml
- name: plk_flag
  query: |
    ВЫБРАТЬ ТС.ЭтоСправочникПЛК КАК PLK
    ИЗ Справочник.ТранспортныеСредства КАК ТС
    ГДЕ ТС.Наименование = &Name
  params:
    Name: "{item}"
  expect: field_truthy
  expect_field: PLK
```

### field_positive

`int(rows[0][field]) > 0`. Best for `КОЛИЧЕСТВО(*)`.

```yaml
- name: exists
  query: |
    ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Cnt
    ИЗ Справочник.{catalog}
    ГДЕ Наименование = &Name И НЕ ПометкаУдаления
  params:
    Name: "{item}"
  expect: field_positive
  expect_field: Cnt
```

### field_zero

`int(rows[0][field]) == 0` or empty. Best for "no active X" checks.

```yaml
- name: fresh
  query: |
    ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Active
    ИЗ РегистрСведений.гкс_СостоянияРегистрации.СрезПоследних КАК Сост
    ГДЕ Сост.ДокументРегистрации.ТранспортноеСредство.Наименование = &Name
      И Сост.Состояние <> ЗНАЧЕНИЕ(Перечисление.гкс_СостоянияРегистрации.Убыл)
  params:
    Name: "{item}"
  expect: field_zero
  expect_field: Active
```

### field_equals

`rows[0][field] == expect_value`. Exact match.

```yaml
- name: correct_status
  query: |
    ВЫБРАТЬ Статус КАК Status
    ИЗ Документ.гкс_ЛабораторныйАнализ
    ГДЕ Номер = &Num
  params:
    Num: "{item}"
  expect: field_equals
  expect_field: Status
  expect_value: "Выполнен"
```

---

## 5. Recipe Cookbook

### Recipe 1: Document by number

```yaml
# document.yaml
tag: Document
description: Document existence by number
enabled: true
parser:
  type: bracketed_list
  item_separator: ","
  item_label: "{catalog}[{item}]"
checks:
  - name: exists
    always: true
    query: |
      ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Cnt ИЗ Документ.{catalog}
      ГДЕ Номер = &Name И НЕ ПометкаУдаления
    params: { Name: "{item}" }
    expect: field_positive
    expect_field: Cnt
    on_fail: "not found"
    on_pass_label: "found"
```

METADATA: `Document: ЗаказКлиента[ЗК-001, ЗК-002]`

---

### Recipe 2: Document is posted

```yaml
# posted_doc.yaml
tag: PostedDoc
description: Document exists and is posted
enabled: true
parser:
  type: bracketed_list
  item_separator: ","
  item_label: "{catalog}[{item}]"
checks:
  - name: exists
    always: true
    query: |
      ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Cnt ИЗ Документ.{catalog}
      ГДЕ Номер = &Name И НЕ ПометкаУдаления
    params: { Name: "{item}" }
    expect: field_positive
    expect_field: Cnt
    on_fail: "document not found"
  - name: posted
    always: true
    query: |
      ВЫБРАТЬ Проведен КАК Posted ИЗ Документ.{catalog}
      ГДЕ Номер = &Name И НЕ ПометкаУдаления
    params: { Name: "{item}" }
    expect: field_truthy
    expect_field: Posted
    on_fail: "exists but NOT posted"
    on_pass_label: "posted"
```

METADATA: `PostedDoc: РеализацияТоваров[РТ-001]`

---

### Recipe 3: Accumulation register balance > 0

```yaml
# balance.yaml
tag: Balance
description: Accumulation register balance is positive
enabled: true
parser:
  type: bracketed_slashed
  pattern: '^(?P<register>\S+)\[(?P<warehouse>[^/]+)/(?P<product>[^\]]+)\]$'
  item_label: "{register}[{warehouse}/{product}]"
checks:
  - name: has_balance
    always: true
    query: |
      ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Cnt
      ИЗ РегистрНакопления.{register}.Остатки(, Склад.Наименование = &Wh
        И Номенклатура.Наименование = &Prod) КАК Ост
      ГДЕ Ост.КоличествоОстаток > 0
    params:
      Wh: "{warehouse}"
      Prod: "{product}"
    expect: field_positive
    expect_field: Cnt
    on_fail: "zero balance"
    on_pass_label: "has stock"
```

METADATA: `Balance: ТоварыНаСкладах[ОсновнойСклад/Пшеница 3 кл]`

---

### Recipe 4: Info register record exists

```yaml
# info_reg.yaml
tag: InfoReg
description: Information register record exists
enabled: true
parser:
  type: bracketed_list
  item_separator: ","
  item_label: "{catalog}[{item}]"
checks:
  - name: exists
    always: true
    query: |
      ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Cnt
      ИЗ РегистрСведений.{catalog}
      ГДЕ Валюта.Наименование = &Name
    params: { Name: "{item}" }
    expect: field_positive
    expect_field: Cnt
    on_fail: "no records"
    on_pass_label: "found"
```

METADATA: `InfoReg: КурсыВалют[USD, EUR]`

---

### Recipe 5: Constant is filled

```yaml
# constant.yaml
tag: Constant
description: Constant has a non-empty value
enabled: true
parser:
  type: literal
  item_label: "{literal}"
checks:
  - name: is_set
    always: true
    query: |
      ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Cnt
      ИЗ Константы КАК К
      ГДЕ К.{literal} <> ЗНАЧЕНИЕ(Справочник.Организации.ПустаяСсылка)
    params: {}
    expect: field_positive
    expect_field: Cnt
    on_fail: "constant is empty"
    on_pass_label: "filled"
```

METADATA: `Constant: ОсновнаяОрганизация`

---

### Recipe 6: Enum value exists

```yaml
# enum.yaml
tag: Enum
description: Enum value exists in configuration
enabled: true
parser:
  type: bracketed_list
  item_separator: ","
  item_label: "{catalog}.{item}"
checks:
  - name: exists
    always: true
    query: |
      ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Cnt
      ИЗ Перечисление.{catalog}
      ГДЕ Ссылка = ЗНАЧЕНИЕ(Перечисление.{catalog}.{item})
    params: {}
    expect: field_positive
    expect_field: Cnt
    on_fail: "enum value not found"
    on_pass_label: "exists"
```

METADATA: `Enum: гкс_СостоянияРегистрации[Прибыл, Убыл]`

---

### Recipe 7: Scheduled job enabled

```yaml
# job.yaml
tag: Job
description: Scheduled job is enabled
enabled: true
parser:
  type: literal
  item_label: "{literal}"
checks:
  - name: is_enabled
    always: true
    query: |
      ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Cnt
      ИЗ Справочник.РегламентныеЗадания
      ГДЕ Наименование = &Name И Использование = ИСТИНА
    params: { Name: "{literal}" }
    expect: field_positive
    expect_field: Cnt
    on_fail: "job disabled or not found"
    on_pass_label: "enabled"
```

METADATA: `Job: ОбновлениеИндексаПолнотекстовогоПоиска`

---

### Recipe 8: User exists

```yaml
# user.yaml
tag: User
description: User exists in the infobase
enabled: true
parser:
  type: literal
  item_label: "{literal}"
checks:
  - name: exists
    always: true
    query: |
      ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Cnt
      ИЗ Справочник.Пользователи
      ГДЕ Наименование = &Name И НЕ ПометкаУдаления
    params: { Name: "{literal}" }
    expect: field_positive
    expect_field: Cnt
    on_fail: "user not found"
    on_pass_label: "exists"
```

METADATA: `User: a.terletskiy@sodru.com`

---

### Recipe 9: Tabular section has rows

```yaml
# tab_rows.yaml
tag: TabRows
description: Document tabular section is not empty
enabled: true
parser:
  type: bracketed_slashed
  pattern: '^(?P<doc_type>[^[]+)\[(?P<doc_num>[^/]+)/(?P<tab_name>[^\]]+)\]$'
  item_label: "{doc_type}[{doc_num}/{tab_name}]"
checks:
  - name: has_rows
    always: true
    query: |
      ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Cnt
      ИЗ {doc_type}.{tab_name}
      ГДЕ Ссылка.Номер = &Num И НЕ Ссылка.ПометкаУдаления
    params: { Num: "{doc_num}" }
    expect: field_positive
    expect_field: Cnt
    on_fail: "tabular section is empty"
    on_pass_label: "has rows"
```

METADATA: `TabRows: Документ.ЗаказКлиента[ЗК-001/Товары]`

---

### Recipe 10: Specific field value

```yaml
# field_val.yaml
tag: FieldVal
description: Catalog element has expected field value
enabled: true
parser:
  type: bracketed_slashed
  pattern: '^(?P<catalog>[^[]+)\[(?P<name>[^/]+)/(?P<field>\w+)=(?P<expected>[^\]]+)\]$'
  item_label: "{catalog}[{name}].{field}={expected}"
checks:
  - name: value_match
    always: true
    query: |
      ВЫБРАТЬ {field} КАК Val
      ИЗ Справочник.{catalog}
      ГДЕ Наименование = &Name И НЕ ПометкаУдаления
    params: { Name: "{name}" }
    expect: field_equals
    expect_field: Val
    expect_value: "{expected}"
    on_fail: "expected {expected}, got different value"
    on_pass_label: "matches"
```

METADATA: `FieldVal: Контрагенты[ЯхимовщинаАгро/ИНН=1234567890]`

---

## 6. Conditional Checks (if_flag)

Checks can run only when a specific flag is present in parsed data.
Use `if_flag` for conditional, `always: true` for unconditional.

**Example from [ts.yaml](ts.yaml):**

```yaml
parser:
  type: csv_with_flags        # parses "М012УХ (fresh, PLK)"

checks:
  - name: exists
    always: true               # always runs
    query: ...
    expect: non_empty

  - name: plk_flag
    if_flag: "PLK"             # only runs if (PLK) flag present
    query: ...
    expect: field_truthy
    expect_field: PLK

  - name: fresh
    if_flag: "fresh"           # only runs if (fresh) flag present
    query: ...
    expect: field_zero
    expect_field: Active
```

With METADATA `TS: М012УХ (fresh, PLK)` all 3 checks run.
With METADATA `TS: В123АБ45` only `exists` runs.

---

## 7. Debugging

### Verbose output

```powershell
python preflight-probe.py --feature features/test.feature --verbose
```

Shows each probe, parsed items, SQL queries, and results.

### Filter by tag

```powershell
python preflight-probe.py --feature features/test.feature --tag TS
```

Runs only probes matching the specified tag.

### Common errors

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Unknown tag: MyTag` | YAML file not in `probes/` dir or `enabled: false` | Check filename and `enabled` field |
| `Parse error` | METADATA string doesn't match parser regex | Check `pattern` regex against actual METADATA |
| `Query error` | Invalid 1C query syntax | Test query in `mcp__1c-mcp-crud__validate_query` first |
| `KeyError: '{field}'` | `expect_field` doesn't match query alias | Ensure `КАК Alias` matches `expect_field` |
| Probe returns PASS but data is wrong | Wrong `expect` type | Use `field_equals` instead of `non_empty` for value checks |
| Cyrillic garbled | File saved without UTF-8 | Ensure YAML is UTF-8 (with or without BOM) |

---

## 8. Adding Probes to Feature Files

Probes live in the `# METADATA:` block at the top of each `.feature` file.
Freeform fields (Task, Dependencies) and machine-readable probe tags coexist:

```gherkin
# language: ru

# METADATA:
#   Task: GKSTCPLK-2256
#   Logical block: Документ.гкс_РегистрацияНаПЛК
#   Dependencies: 00_smoke.feature
#
#   # Machine-readable probes (one per line, can repeat tags)
#   TS: М012УХ, Х985ХМ36RUS (fresh, PLK)
#   Catalog: Номенклатура[Пшеница 3 кл, Рапс (Россия)]
#   Catalog: Контрагенты[ЯхимовщинаАгро]
#   Setting: НастройкаЭлектронногоТабло[ПЛК Светлый/НеПрошедшиеРегистрацию]
#   Role: ДоступенДиспетчер
#   Document: гкс_Взвешивание[ВЗВ-001]
```

**Rules:**
- Each tag line is `# TAG: value` (inside a `#` comment block)
- Tags can repeat (two `Catalog:` lines = two separate checks)
- Unknown tags are silently ignored (forward-compatible)
- Preflight runs ALL matching probes from all YAML files in this directory
- Order of tags doesn't matter (all probes run independently)

---

## Existing Probes

| File | Tag | Parser | Checks | Scope |
|------|-----|--------|--------|-------|
| [catalog.yaml](catalog.yaml) | `Catalog` | bracketed_list | exists | Universal |
| [ts.yaml](ts.yaml) | `TS` | csv_with_flags | exists, PLK, fresh | GKSTCPLK project |
| [setting.yaml](setting.yaml) | `Setting` | bracketed_slashed | exists | GKSTCPLK project |
| [role.yaml](role.yaml) | `Role` | literal | SKIP | Universal |
