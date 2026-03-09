# Чеклист готовности: Фаза 62 — Knowledge Graph объектов 1С

**Приоритет:** MEDIUM | **Срок:** 4-6 дней | **Зависимости:** нет

## Предусловия
- [ ] Выгрузка конфигурации 1С в XML (папки `Catalogs/`, `Documents/`, `InformationRegisters/` и др.)
- [ ] Python 3.11+, `lxml` для парсинга XML
- [ ] Определена директория хранения: `data/knowledge_graph.db`
- [ ] Доступны примеры BSL файлов для тестирования связности модулей с объектами

## Артефакты (файлы/код)
- [ ] `src/bsl/knowledge_graph/xml_parser.py` — парсер XML конфигурации
- [ ] `src/bsl/knowledge_graph/schema.sql` — DDL таблиц (objects, attributes, relations, subsystems)
- [ ] `src/bsl/knowledge_graph/builder.py` — ETL pipeline: XML → SQLite
- [ ] `src/bsl/knowledge_graph/queries.py` — API: get_object_info, get_doc_registers, get_subsystem_objects
- [ ] `src/bsl/knowledge_graph/linker.py` — привязка BSL модулей к объектам метаданных
- [ ] `data/knowledge_graph.db` — заполненная БД

## Метрики приёмки
- [ ] Coverage >= 95%: все Catalogs, Documents, Registers, Subsystems из XML в БД
- [ ] Integrity = 100%: нет "висячих" ссылок (все referenced объекты существуют)
- [ ] Время построения <= 30s для конфигурации до 1000 объектов
- [ ] Точность запроса "какие регистры у документа X": проверка на 5 эталонных документах

## Интеграционные проверки
- [ ] SQL Integrity: `PRAGMA foreign_key_check` без ошибок
- [ ] Query Test: get_subsystem_objects("Логистика") возвращает корректный список
- [ ] BSL Linkage: для объекта метаданных находится привязанный BSL модуль
- [ ] No Duplication: нет дублей узлов с одинаковыми именами

## Блокеры для следующих фаз
- [ ] Без knowledge graph блокируется Фаза 63 (Contextual Search: контекст объектов)
- [ ] Без связей Document→Register блокируется Фаза 66 (Coding Assistant: контекст проводок)
- [ ] Без линковки BSL→объект блокируется Фаза 64 (MCP: get_object_info)
