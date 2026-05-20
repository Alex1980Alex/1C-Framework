# Tasks for GKSTCPLK-2507 — Автоматическая установка вида допуска в РМ Приёмка/отгрузка по номенклатуре

## 1. Preparation

- [ ] **1.1** Подтвердить актуальность ANALYSIS-REPORT.md (verify ✓ get_metadata, ✓ validate_query)
- [ ] **1.2** Создать ветку фичи в submodule `ИБTransportManagementDevelop/Конфигурация`
- [ ] **1.3** Открыть проект в EDT, убедиться `state=ready` через `mcp__edt-mcp__list_projects`
- [ ] **1.4** Snapshot `гкс_СтатусыДопускаВагоновКВскрытию` для regression baseline (`execute_query`)

## 2. Создание нового регистра сведений (Точка 1)

- [ ] **2.1** Создать `.mdo` `гкс_НастройкиЗапретаВскрытияПоНоменклатуре` (новые UUID, `comment=GKSTCPLK-2507`)
- [ ] **2.2** Измерения: `Номенклатура` (`CatalogRef.Номенклатура`, mainFilter+denyIncompleteValues), `ДопускКВскрытию` (`EnumRef.гкс_ДопускиКВскрытиюВагонов`, mainFilter+denyIncompleteValues), `ДатаНачала` (`Date`, mainFilter)
- [ ] **2.3** Ресурс `Активен` (`Boolean`)
- [ ] **2.4** Реквизиты `ДатаОкончания`, `Комментарий(150)`, `ДатаВремяИзменения`, `Пользователь`
- [ ] **2.5** `ManagerModule.bsl` с RLS: `РазрешитьЧтениеИзменение ГДЕ ЗначениеРазрешено(Номенклатура)`

## 2. Implementation

- [ ] **2.1** Implement core logic
- [ ] **2.2** Add error handling
- [ ] **2.3** Write unit tests

## 3. Integration

- [ ] **3.1** Integration testing
- [ ] **3.2** Documentation
- [ ] **3.3** Code review
