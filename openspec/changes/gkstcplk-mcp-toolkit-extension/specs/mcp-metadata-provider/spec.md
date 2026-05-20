## ADDED Requirements

### Requirement: get_metadata — структура конфигурации

Инструмент `get_metadata` MUST возвращать структуру конфигурации 1С.

- Без параметров: типы объектов + количество + свойства конфигурации
- С фильтрами: `metadata_type`, `name_filter`, `limit`, `offset`
- Поддержка расширений конфигурации

#### Scenario: пустой запрос

- **WHEN** клиент вызывает `get_metadata()` без параметров
- **THEN** возвращается сводка по всем типам метаданных с количествами

#### Scenario: фильтр по типу

- **WHEN** `metadata_type="Справочник"`, `name_filter="Конт*"`, `limit=10`
- **THEN** возвращается ≤ 10 справочников с именем, начинающимся на «Конт»

### Requirement: get_event_log — журнал регистрации

Инструмент `get_event_log` MUST возвращать записи журнала.

- Параметры: `count` (default 20, max 100), `start_date`, `end_date`, `level`
- Возвращает: `date, level, event, comment, user, metadata, session`

#### Scenario: фильтр по уровню Error

- **WHEN** `get_event_log(level="Error", count=50)`
- **THEN** возвращаются ≤ 50 записей с `level = "Error"`, отсортированные по `date DESC`

### Requirement: get_object_by_link — объект по навигационной ссылке

Инструмент `get_object_by_link` MUST разрешать навигационную ссылку в объект.

- Параметр: `link` (формат `e1cib/data/Тип.Имя?ref=hex`)
- Возвращает все реквизиты объекта в TOON-формате

#### Scenario: валидная ссылка справочника

- **WHEN** `link = "e1cib/data/Справочник.Контрагенты?ref=8a..."` валиден
- **THEN** возвращается TOON-сериализация всех реквизитов контрагента

#### Scenario: битая ссылка

- **WHEN** ссылка указывает на несуществующий объект
- **THEN** возвращается ошибка с типом `ObjectNotFound`

### Requirement: get_link_of_object — навигационная ссылка

Инструмент `get_link_of_object` MUST формировать ссылку для объекта.

- Параметр: `object_description` с `_objectRef: true`
- Возвращает: ссылку `e1cib/data/...?ref=...`

#### Scenario: ссылка справочника

- **WHEN** `object_description = {_objectRef: true, type: "Справочник.Контрагенты", id: "..."}`
- **THEN** возвращается строка `e1cib/data/Справочник.Контрагенты?ref=<hex>`

### Requirement: find_references_to_object — ссылки на объект

Инструмент `find_references_to_object` MUST находить ссылки на объект.

- Параметры: `target_object_description`, `search_scope`
- Лимиты: `limit_hits` (200), `limit_per_meta` (20), `timeout_budget_sec` (30)

#### Scenario: поиск ссылок на контрагента

- **WHEN** `target = <Контрагент>`, `search_scope = ["Documents", "Catalogs"]`
- **THEN** возвращаются объекты из Documents/Catalogs со ссылками, не более 200 итого и не более 20 на тип
