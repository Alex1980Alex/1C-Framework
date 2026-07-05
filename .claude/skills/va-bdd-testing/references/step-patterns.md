# Step Patterns (Full Reference)

> Extracted from `va-bdd-testing` SKILL.md Stage 3 (progressive disclosure, audit 260705 BP G1).
> See [SKILL.md](../SKILL.md) for the condensed critical-rules cheat sheet and overall workflow.

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

