# Known Issues and Gotchas (Full Reference)

> Extracted from `va-bdd-testing` SKILL.md (progressive disclosure, audit 260705 BP G1).
> See [SKILL.md](../SKILL.md) for the top-gotchas summary.

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
