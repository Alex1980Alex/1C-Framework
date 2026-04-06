## ADDED

## Requirements

### REQ-8: get_metadata — структура конфигурации
- Без параметров: возвращает типы объектов + количество + свойства конфигурации
- С фильтрами: metadata_type, name_filter, limit, offset
- Поддержка расширений конфигурации

### REQ-9: get_event_log — журнал регистрации
- Параметры: count (default 20, max 100), start_date, end_date, level
- Возвращает: date, level, event, comment, user, metadata, session

### REQ-10: get_object_by_link — объект по навигационной ссылке
- Параметр: `link` (формат `e1cib/data/Тип.Имя?ref=hex`)
- Возвращает все реквизиты объекта в TOON-формате

### REQ-11: get_link_of_object — навигационная ссылка
- Параметр: `object_description` с `_objectRef: true`
- Возвращает: навигационную ссылку `e1cib/data/...?ref=...`

### REQ-12: find_references_to_object — ссылки на объект
- Параметры: `target_object_description`, `search_scope` (английские имена типов)
- Лимиты: limit_hits (200), limit_per_meta (20), timeout_budget_sec (30)

### REQ-13: get_access_rights — права доступа
- Параметр: `metadata_object` (формат `Справочник.ИмяСправочника`)
- Возвращает: список прав, роли и их настройки
