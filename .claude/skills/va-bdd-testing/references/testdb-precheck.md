# Stage 4a: Pre-scenario TestDB Data Check (Full Reference)

> Extracted from `va-bdd-testing` SKILL.md (progressive disclosure, audit 260705 BP G1).
> See [SKILL.md](../SKILL.md) for the mandatory-check summary.

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
