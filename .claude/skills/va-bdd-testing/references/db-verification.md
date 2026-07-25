# Stage 4: Database Verification (Full Reference)

> Extracted from `va-bdd-testing` SKILL.md (progressive disclosure, audit 260705 BP G1).
> See [SKILL.md](../SKILL.md) for the summary.

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
