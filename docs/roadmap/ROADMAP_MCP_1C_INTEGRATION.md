# Дорожная карта: MCP-интеграция с 1С:Предприятие

> Цель: подключить Claude Code к серверной базе `Srvr="localhost";Ref="TestDB"` для чтения данных, проведения документов, редактирования справочников, тестирования и работы с метаданными.

## Сводная таблица инструментов (без дублирования)

| #   | Проект                            | Категория    | Уникальные возможности                                                                         | GitHub                                                       |
| --- | --------------------------------- | ------------ | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| 1   | vladimir-kharin/1c_mcp            | Данные       | HTTP-сервис + Python proxy, stdio + SSE, расширение 1С                                         | [link](https://github.com/vladimir-kharin/1c_mcp)            |
| 2   | ROCTUP/1c-mcp-toolkit             | Данные       | REST API + long polling, Docker, .epf обработка, каналы изоляции                               | [link](https://github.com/ROCTUP/1c-mcp-toolkit)             |
| 3   | ruslan-hut/onec-mcp               | Данные       | Go gateway, поиск контрагентов, отчёты продаж                                                  | [link](https://github.com/ruslan-hut/onec-mcp)               |
| 4   | artesk/1C_MCP_metadata            | Метаданные   | Структура метаданных, фильтрация по типам объектов                                             | [link](https://github.com/artesk/1C_MCP_metadata)            |
| 5   | FSerg/mcp-1c-v1                   | Метаданные   | RAG + Qdrant по структуре конфигурации                                                         | [link](https://github.com/FSerg/mcp-1c-v1)                   |
| 6   | alkoleft/mcp-bsl-platform-context | BSL          | Синтакс-помощник платформы 8.3 (уже установлен!)                                               | [link](https://github.com/alkoleft/mcp-bsl-platform-context) |
| 7   | alkoleft/mcp-onec-test-runner     | BSL          | YaXUnit тесты, сборка, EDT CLI                                                                 | [link](https://github.com/alkoleft/mcp-onec-test-runner)     |
| 8   | DitriXNew/EDT-MCP                 | BSL          | 1C:EDT плагин, 33 MCP-инструмента: BSL-анализ, валидация запросов, рефакторинг, скриншоты форм | [link](https://github.com/DitriXNew/EDT-MCP)                 |
| 9   | spremotely/vanessa-app-mcp        | Тестирование | MCP-обёртка для Vanessa Automation (BDD)                                                       | [link](https://lobehub.com/mcp/spremotely-vanessa-app-mcp)   |
| 10  | vanessa-opensource/vanessa-runner | CI/CD        | CLI: сборка, деплой, запуск тестов (поглотил deployka)                                         | [link](https://github.com/vanessa-opensource/vanessa-runner) |
| 11  | oisee/odata_mcp_go                | OData        | Универсальный OData v2/v4 мост (работает с 1С OData)                                           | [link](https://github.com/oisee/odata_mcp_go)                |

**Исключены как дубли:**
- `iflow-mcp-1c` (PyPI) — форк vladimir-kharin/1c_mcp, идентичный функционал
- `Antonio1C/1c-syntax-helper-mcp` — дублирует alkoleft/mcp-bsl-platform-context
- `CDataSoftware/odata-mcp-server` — read-only, oisee/odata_mcp_go мощнее
- `deployka` — поглощена vanessa-runner
- `ARQA` — коммерческий аналог 1c_mcp, не open-source

---

## Сравнение: Vanessa-runner vs аналоги

| Возможность             | vanessa-runner                       | mcp-onec-test-runner      | vanessa-app-mcp         | EDT-MCP       |
| ----------------------- | ------------------------------------ | ------------------------- | ----------------------- | ------------- |
| Запуск BDD (Gherkin)    | CLI команда `vrunner vanessa`        | -                         | MCP tool `run_scenario` | -             |
| Запуск TDD (xUnit)      | CLI `vrunner xunit`                  | MCP `run_tests` (YaXUnit) | -                       | -             |
| Сборка cf/cfe           | `vrunner compile`                    | MCP `build`               | -                       | Через EDT CLI |
| Деплой базы             | `vrunner init-dev`, `vrunner update` | -                         | -                       | -             |
| Создание feature-файлов | -                                    | -                         | MCP `create_feature`    | -             |
| Генерация шагов         | -                                    | -                         | MCP `generate_steps`    | -             |
| Парсинг Gherkin         | -                                    | -                         | MCP `parse_feature`     | -             |
| Валидация запросов 1С   | -                                    | -                         | -                       | MCP tool      |
| BSL-анализ кода         | -                                    | -                         | -                       | MCP tool      |
| Управление сессиями 1С  | `vrunner session`                    | -                         | -                       | -             |
| MCP протокол            | Нет (CLI)                            | Да                        | Да                      | Да            |
| Зрелость                | Зрелый, экосистема                   | Молодой                   | Молодой                 | Молодой       |

**Вывод:** vanessa-runner — самый зрелый, но не имеет MCP. Все 3 MCP-аналога покрывают разные ниши. Оптимально: **vanessa-runner (CLI) + MCP-обёртка** для вызова его команд из Claude.

---

## Детальный анализ ключевых инструментов

### ROCTUP/1c-mcp-toolkit — Лучший выбор для данных + метаданных

**Почему первый:** Docker + .epf = быстрый старт без изменения конфигурации. Даёт и чтение, и запись, и метаданные в одном пакете.

| Критерий               | Значение                                                                           |
| ---------------------- | ---------------------------------------------------------------------------------- |
| MCP Tools              | `execute_query` (запросы 1С), `get_metadata` (структура конфигурации)              |
| Архитектура            | Claude ──MCP──► Python Proxy (FastAPI:6003) ──long polling──► .epf в 1С ──► TestDB |
| Установка              | `docker run -d -p 6003:6003 roctup/1c-mcp-toolkit-proxy` + открыть .epf в 1С       |
| Каналы изоляции        | `?channel=dev` / `?channel=prod` — разделение dev/prod                             |
| REST API               | Параллельный доступ через curl (skill `calling-1c-rest-api-via-curl`)              |
| Платформы              | 8.2.13+ и 8.3                                                                      |
| Не меняет конфигурацию | Да (.epf обработка)                                                                |
| Готовые skills         | Синтаксис запросов 1С, оптимизация, виртуальные таблицы, JOINs                     |

**Ограничения:** 2 MCP-инструмента (создание/проведение документов — через execute_query), long polling задержка.

### DitriXNew/EDT-MCP — Мощнейший инструмент для BSL-разработки

**Почему второй:** 33 MCP-инструмента — мощнее чем bsl-platform-context + serena вместе. Но требует 1C:EDT.

| Tool                           | Категория   | Что делает                                                            |
| ------------------------------ | ----------- | --------------------------------------------------------------------- |
| **Проекты и конфигурация**     |             |                                                                       |
| `list_projects`                | Проекты     | Список проектов в workspace EDT                                       |
| `get_configuration_properties` | Проекты     | Свойства конфигурации (имя, совместимость, вариант скрипта)           |
| `get_applications`             | Проекты     | Список информационных баз проекта (ID для update/debug)               |
| `get_edt_version`              | Проекты     | Версия 1C:EDT                                                         |
| **Метаданные**                 |             |                                                                       |
| `get_metadata_objects`         | Метаданные  | Список объектов с фильтрацией по типу (справочники, документы...)     |
| `get_metadata_details`         | Метаданные  | Детальные свойства объектов (реквизиты, ТЧ, full mode)                |
| `get_tags`                     | Метаданные  | Список тегов проекта                                                  |
| `get_objects_by_tags`          | Метаданные  | Поиск объектов по тегам                                               |
| **BSL-код — чтение**           |             |                                                                       |
| `list_modules`                 | BSL-код     | Список модулей с фильтрами по типу                                    |
| `get_module_structure`         | BSL-код     | Процедуры/функции, сигнатуры, строки, регионы, &НаСервере/&НаКлиенте  |
| `read_module_source`           | BSL-код     | Чтение исходного кода модуля (полный или диапазон строк)              |
| `read_method_source`           | BSL-код     | Чтение конкретной процедуры/функции по имени                          |
| **BSL-код — запись**           |             |                                                                       |
| `write_module_source`          | BSL-код     | Запись в модуль (searchReplace/replace/append) с проверкой синтаксиса |
| **BSL-код — анализ**           |             |                                                                       |
| `get_symbol_info`              | Анализ      | Типизация символа: inferred types, сигнатуры, документация (hover)    |
| `get_content_assist`           | Анализ      | Автодополнение: подсказки типов, методов, документация платформы      |
| `go_to_definition`             | Навигация   | Переход к определению символа (метод, объект метаданных)              |
| `find_references`              | Навигация   | Поиск всех ссылок на объект (код, формы, роли, подсистемы)            |
| `get_method_call_hierarchy`    | Навигация   | Иерархия вызовов: callers/callees через BM-index                      |
| `search_in_code`               | Поиск       | Полнотекстовый поиск по BSL (regex, фильтр по типу метаданных)        |
| **Запросы 1С**                 |             |                                                                       |
| `validate_query`               | Запросы     | Валидация синтаксис + семантика (знает метаданные), режим DCS         |
| **Ошибки и валидация**         |             |                                                                       |
| `get_project_errors`           | Ошибки      | Детальные ошибки с фильтрами (severity, объект, checkId)              |
| `get_problem_summary`          | Ошибки      | Сводка по количеству ошибок/предупреждений                            |
| `get_check_description`        | Ошибки      | Документация по конкретной проверке EDT                               |
| `revalidate_objects`           | Валидация   | Перезапуск валидации проекта или конкретных объектов                  |
| `clean_project`                | Валидация   | Полная очистка и ревалидация проекта                                  |
| **Рефакторинг**                |             |                                                                       |
| `rename_metadata_object`       | Рефакторинг | Переименование с обновлением всех ссылок (preview + confirm)          |
| `delete_metadata_object`       | Рефакторинг | Удаление с очисткой ссылок (preview + confirm)                        |
| `add_metadata_attribute`       | Рефакторинг | Добавление реквизита к объекту                                        |
| **Формы**                      |             |                                                                       |
| `get_form_screenshot`          | Формы       | Скриншот формы из WYSIWYG-редактора (PNG)                             |
| **Навигация**                  |             |                                                                       |
| `get_bookmarks`                | Навигация   | Закладки в коде                                                       |
| `get_tasks`                    | Навигация   | TODO/FIXME маркеры                                                    |
| **Деплой и отладка**           |             |                                                                       |
| `update_database`              | Деплой      | Обновление БД (полное или инкрементальное)                            |
| `debug_launch`                 | Отладка     | Запуск приложения в режиме отладки                                    |

**Требования:** 1C:EDT установлен, проект открыт в workspace. Порт 8765, Streamable HTTP + SSE.

### FSerg/mcp-1c-v1 — Идеи для нашего индексатора (не устанавливать)

**Почему опционально:** У нас уже есть bsl-semantic-search с Qdrant + nomic-embed-text. Docker image 6+ ГБ ради одного `search_1c_documentation` — избыточно. Но идеи ценные:

| Идея из FSerg                                             | Как применить у нас                                       |
| --------------------------------------------------------- | --------------------------------------------------------- |
| Мультивекторный RRF (object_name + friendly_name)         | Добавить в bsl-semantic-search второй вектор по синонимам |
| Обработка `ПолучитьТекстСтруктурыКонфигурацииФайлами.epf` | Взять для выгрузки метаданных, загрузить в наш Qdrant     |
| Коллекции через `x-collection-name`                       | У нас уже есть `bsl_code_v2`, добавить `bsl_metadata`     |
| Веб-интерфейс Loader                                      | Не нужен — у нас есть `scripts/index-folder.bat`          |

**Действие:** Не устанавливать FSerg/mcp-1c-v1. Вместо этого в Фазе 3.5 взять его подход мультивекторного RRF и .epf обработку, интегрировать в наш существующий bsl-semantic-search.

### Сводная матрица

| Критерий                | ROCTUP/toolkit     | DitriXNew/EDT-MCP                                         | FSerg/mcp-1c-v1       |
| ----------------------- | ------------------ | --------------------------------------------------------- | --------------------- |
| **MCP tools**           | 2                  | 33                                                        | 1                     |
| **Чтение данных**       | execute_query      | -                                                         | -                     |
| **Запись данных**       | через запрос       | -                                                         | -                     |
| **Метаданные**          | get_metadata       | list_modules, structure                                   | RAG-поиск             |
| **BSL-анализ**          | -                  | 19 tools (чтение, запись, анализ, навигация, рефакторинг) | -                     |
| **Установка**           | Docker 1 команда   | EDT + плагин                                              | Docker Compose (6 ГБ) |
| **Меняет конфигурацию** | Нет (.epf)         | Нет (плагин)                                              | Нет (выгрузка)        |
| **Реальное время**      | live               | live workspace                                            | по выгрузке           |
| **Рекомендация**        | **Ставить первым** | **Ставить вторым**                                        | **Взять идеи**        |

---

## Фазы внедрения

### Фаза 1: Данные + Метаданные через ROCTUP/1c-mcp-toolkit ✓ COMPLETE (2026-03-14)
> MVP: Claude читает данные, выполняет запросы, видит структуру конфигурации TestDB

**Инструменты:** ROCTUP/1c-mcp-toolkit (Docker + .epf)

**Почему ROCTUP первый (а не OData или vladimir-kharin/1c_mcp):**
- Docker 1 команда — не нужен IIS, не нужно публиковать HTTP-сервис
- .epf обработка — не нужно устанавливать расширение в конфигурацию
- 2 инструмента покрывают и данные (execute_query) и метаданные (get_metadata) сразу
- Каналы изоляции dev/prod — безопасно для тестирования
- REST API параллельно — можно использовать и из скриптов

| Шаг | Действие                                          | Статус | Результат                                   |
| --- | ------------------------------------------------- | ------ | ------------------------------------------- |
| 1.1 | Установить Docker Desktop                         | ✓      | Docker Desktop работает                     |
| 1.2 | Запустить контейнер `roctup/1c-mcp-toolkit-proxy` | ✓      | Порт 6003, Up 5 hours                       |
| 1.3 | Скачать `MCP_Toolkit_Клиент.epf`                  | ✓      | Обработка в 1С                              |
| 1.4 | Открыть .epf в 1С TestDB                          | ✓      | Подключено к TestDB                         |
| 1.5 | Добавить в `.mcp.json`                            | ✓      | `http://localhost:6003/mcp`                 |
| 1.6 | Тест: `execute_query`                             | ✓      | 5 пользователей из Справочник.Пользователи  |
| 1.7 | Тест: `get_metadata`                              | ✓      | 91 справочник, 27 документов, 190 регистров |
| 1.8 | Тест: запись данных                               | ⏳      | Не тестировалось                            |
| 1.9 | Настроить канал изоляции                          | ⏳      | Не требуется (dev only)                     |

**Результат:** Claude читает данные, выполняет запросы 1С, знает структуру конфигурации. Всё в одном инструменте.

**Конфигурация TestDB:**
- Имя: УправлениеТранспортомНаПЛК
- Версия: 2026.1.1.0
- Платформа: 8.3.27.1859
- Справочников: 91, Документов: 27, Регистров: 190

**Конфигурация `.mcp.json`:**
```json
{
  "mcpServers": {
    "1c-toolkit": {
      "url": "http://localhost:6003/mcp",
      "autoApprove": ["execute_query", "get_metadata"]
    }
  }
}
```

---

### Фаза 2: BSL-разработка через EDT-MCP ✓ COMPLETE (2026-03-12)
> Claude анализирует BSL-код, валидирует запросы, навигирует по модулям через 33 инструмента EDT

**Инструменты:** DitriXNew/EDT-MCP + alkoleft/mcp-bsl-platform-context (уже установлен)

**Почему EDT-MCP вторым:**
- 33 MCP-инструмента — мощнее bsl-platform-context + serena вместе
- Валидация запросов 1С в контексте метаданных (знает справочники/документы)
- get_symbol_info — типизация для динамического BSL (то, чего нет у LSP)
- write_module_source — запись в BSL с проверкой синтаксиса
- rename/delete_metadata_object — рефакторинг с обновлением всех ссылок
- get_method_call_hierarchy — семантический граф вызовов через BM-index
- get_form_screenshot — визуализация форм (PNG)
- Но требует 1C:EDT — нужна установка IDE

| Шаг  | Действие                           | Статус | Результат                           |
| ---- | ---------------------------------- | ------ | ----------------------------------- |
| 2.1  | Установить 1C:EDT                  | ✓      | EDT 2025.2.3.30                     |
| 2.2  | Импортировать проект GKSTCPLK-2182 | ✓      | УправлениеТранспортомНаПЛК          |
| 2.3  | Установить EDT-MCP плагин          | ✓      | Из marketplace                      |
| 2.4  | Включить auto-start                | ✓      | Настройки → EDT MCP                 |
| 2.5  | Добавить в `.mcp.json`             | ✓      | Порт 8765                           |
| 2.6  | Тест: `list_modules`               | ✓      | 5 модулей документа                 |
| 2.7  | Тест: `get_module_structure`       | ✓      | 18 proc, 20 func, 1513 lines        |
| 2.8  | Тест: `validate_query`             | ✓      | 0 errors, valid                     |
| 2.9  | Тест: `get_symbol_info`            | ✓      | Types: Соответствие, ДокументСсылка |
| 2.10 | Тест: `get_problems`               | ✓      | 2 errors (Web-client)               |

**Результат:** Claude полноценно анализирует BSL-код — модули, типы, запросы, ошибки.

**Ограничения EDT-MCP:**
- `debug_launch` только **запускает** отладку — управление breakpoints, step over/in/out, чтение переменных — вручную в EDT GUI
- Нет программного управления UI EDT (кнопки, вкладки)
- Для полноценной отладки через MCP нужен bsl-debugger (OneScript runtime)

**bsl-debugger MCP (OneScript runtime):**
- 10 инструментов: `bsl_debug_start/stop`, `bsl_debug_breakpoints`, `bsl_debug_step`, `bsl_debug_stack`, `bsl_debug_variables`, `bsl_debug_evaluate`, `bsl_execute`
- Полный программный контроль breakpoints (условные, hit count, logpoints)
- Работает только с OneScript, **не** с реальной 1С:Предприятие
- Требует `OSCRIPT_HOME` в env для нестандартных путей установки

**Конфигурация `.mcp.json`:**
```json
{
  "mcpServers": {
    "edt-mcp": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:8765/mcp"],
      "timeout": 60000
    }
  }
}
```

**Синергия с Фазой 1:** Claude через get_metadata (ROCTUP) узнаёт структуру данных, через EDT-MCP — структуру кода. Полная картина.

---

### Фаза 3: Расширенный доступ к данным ✓ COMPLETE (2026-03-14)
> Claude создаёт/проводит документы через полноценный HTTP-сервис + OData для быстрого чтения

**Инструменты:** vladimir-kharin/1c_mcp (CRUD) + oisee/odata_mcp_go (быстрое чтение)

| Шаг | Действие                                                             | Статус | Результат                              |
| --- | -------------------------------------------------------------------- | ------ | -------------------------------------- |
| 3.1 | Клонировать репозиторий vladimir-kharin/1c_mcp                       | ✓      | `src/external/1c_mcp/`                 |
| 3.2 | Создать venv + установить зависимости Python proxy                   | ✓      | mcp-1.26.0, fastapi-0.135.1            |
| 3.3 | Создать конфигурацию `.env`                                          | ✓      | TestDB credentials                     |
| 3.4 | Добавить в `.mcp.json` (транспорт: stdio)                            | ✓      | `1c-mcp-crud` server                   |
| 3.5 | Установить расширение `MCP_Сервер.cfe` в TestDB                      | ✓      | Установлено через Конфигуратор         |
| 3.6 | Установить IIS + настроить публикацию TestDB                         | ✓      | IIS + ISAPI + AppPool + default.vrd    |
| 3.7 | Тест: health endpoint + tools/list через HTTP                        | ✓      | health=OK, 2 tools (list+structure)    |
| 3.8 | Тест: tool call list_metadata_objects                                | ✓      | 5 документов, кириллица OK             |
| 3.9 | Включить OData для всех объектов                                     | ✓      | 416 объектов через execute_code         |
| 3.10| Тест: OData endpoint                                                 | ✓      | 420 коллекций, JSON, данные OK          |

**Результат:** Три канала доступа к данным: ROCTUP (универсальный), 1c_mcp (CRUD), OData (быстрое чтение).

**Подготовленные файлы:**
- Расширение: `D:\1C-Enterprise_Framework\src\external\1c_mcp\build\MCP_Сервер.cfe`
- Python Proxy: `D:\1C-Enterprise_Framework\src\external\1c_mcp\venv\`
- Конфигурация: `D:\1C-Enterprise_Framework\src\external\1c_mcp\.env`
- Скрипты (оригинальные): `setup-phase3.bat`, `publish-testdb.bat`, `start-proxy-http.bat`
- Скрипты (новые): `tools/1c-mcp-crud/setup-phase3-iis.ps1`, `install-extension.ps1`, `test-phase3.ps1`, `enable-odata.ps1`
- Инструкция: `install-extension-guide.md`

**Автоматизация (новые скрипты в `tools/1c-mcp-crud/`):**
1. `install-extension.ps1` — установка .cfe через ibcmd/DESIGNER batch mode
2. `setup-phase3-iis.ps1` — полная установка IIS + ISAPI + публикация TestDB
3. `test-phase3.ps1` — верификация всех компонентов (IIS, health, tools, OData)
4. `enable-odata.ps1` — включение/отключение OData в default.vrd

**Ручные шаги:**
1. Открыть Конфигуратор TestDB (`Srvr="KOMPUTER";Ref="TestDB"`)
2. Конфигурация → Расширения → Добавить из файла: `MCP_Сервер.cfe`
3. Запустить `setup-phase3-iis.ps1` от Администратора (установит IIS + ISAPI)
4. Проверить: `test-phase3.ps1`

**Диагностика:**
- IIS не установлен на машине (Windows IoT Enterprise) → нужна установка через DISM
- DESIGNER зависает (вероятно, лицензия не поддерживает batch-режим) → ручная установка
- ibcmd не подключается к SQL (Shared Memory timeout, TCP refused) → SQL Server принимает только Named Pipes через 1C cluster
- `default.vrd` уже сконфигурирован с HTTP-сервисом `mcp_APIBackend`

**Когда нужна Фаза 3 (а не только ROCTUP):**
- Нужно полноценное создание/проведение документов (не через execute_query)
- Нужен быстрый batch-доступ к данным (OData быстрее long polling)
- Нужен прямой HTTP без Docker

---

### Фаза 3.5: Мультивекторный RRF для метаданных ✓ COMPLETE (2026-03-14)
> Интеграция идей FSerg/mcp-1c-v1 в наш bsl-semantic-search

**Вместо установки FSerg/mcp-1c-v1 (6 ГБ Docker)** — взяли его лучшие идеи

| Шаг   | Действие                                                   | Статус | Результат                          |
| ----- | ---------------------------------------------------------- | ------ | ---------------------------------- |
| 3.5.1 | Экспорт метаданных через ROCTUP/1c-mcp-toolkit             | ✓      | 1000 объектов                      |
| 3.5.2 | Создать коллекцию `bsl_metadata` в Qdrant                  | ✓      | Multi-vector config                |
| 3.5.3 | Скрипт загрузки с 2 векторами: object_name + friendly_name | ✓      | `metadata_indexer_v2.py`           |
| 3.5.4 | Загрузка метаданных в Qdrant                               | ✓      | **1000 indexed, 0 failed**         |
| 3.5.5 | Добавить RRF-fusion в поиск                                | ✓      | `search_metadata_rrf` tool         |
| 3.5.6 | Тест: семантический поиск по метаданным                    | ✓      | "лабораторные анализы" → 3 results |

**Результат:** Семантический поиск по метаданным конфигурации через наш существующий Qdrant. Без 6 ГБ Docker.
**Коллекция Qdrant:**
- Имя: `bsl_metadata`
- Векторы: `object_name` (768d) + `friendly_name` (768d)
- Точек: **1000** (индексация завершена)

---

### Фаза 4: Тестирование — Vanessa Automation + YaXUnit (3-4 дня)
> Claude эмулирует действия пользователя (нажатие кнопок, проведение документов), запускает BDD/TDD тесты

**Инструменты:** Vanessa Automation (UI) + vanessa-runner (CLI) + spremotely/vanessa-app-mcp + alkoleft/mcp-onec-test-runner

#### Vanessa Automation — эмуляция пользователя

**Зачем:** COM-соединение (Фаза 1) и EDT-MCP (Фаза 2) работают на сервере — у них нет форм, кнопок, клиентского контекста. Vanessa Automation решает это:

| Возможность                      | COM (ROCTUP) | EDT-MCP | Vanessa Automation   |
| -------------------------------- | ------------ | ------- | -------------------- |
| Нажать кнопку «Провести»         | Нет          | Нет     | **Да**               |
| Выполнить код `&НаКлиенте`       | Нет          | Нет     | **Да** (VAExtension) |
| Заполнить форму как пользователь | Нет          | Нет     | **Да**               |
| Проверить обработчики форм       | Нет          | Нет     | **Да**               |
| Работать с модальными окнами     | Нет          | Нет     | **Да**               |
| Запись действий → генерация кода | Нет          | Нет     | **Да**               |

**Ключевые GitHub-проекты:**

| #   | Проект                        | Назначение                                                            | GitHub                                                                                    |
| --- | ----------------------------- | --------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| 1   | **Vanessa Automation**        | BDD, полная эмуляция пользователя, VAExtension (клиент+сервер код)    | [Pr-Mex/vanessa-automation](https://github.com/Pr-Mex/vanessa-automation)                 |
| 2   | **Vanessa Automation Single** | Однофайловая версия VA, Исследователь формы                           | [Pr-Mex/vanessa-automation-single](https://github.com/Pr-Mex/vanessa-automation-single)   |
| 3   | **Vanessa ADD**               | TDD+BDD, плагин «ТестКлиенты», дымовые тесты всех форм                | [vanessa-opensource/add](https://github.com/vanessa-opensource/add)                       |
| 4   | **Тестер 1С**                 | Сценарное тестирование, запись действий пользователя, видеозапись, CI | [grumagargler/tester](https://github.com/grumagargler/tester)                             |
| 5   | **xUnitFor1C**                | Юнит+сценарное тестирование, тонкий/толстый клиент                    | [xDrivenDevelopment/xUnitFor1C](https://github.com/xDrivenDevelopment/xUnitFor1C)         |
| 6   | **YAxUnit**                   | Современный фреймворк, Allure-отчёты, EDT интеграция                  | [bia-technologies/yaxunit](https://github.com/bia-technologies/yaxunit)                   |
| 7   | **YAxUnit Smoke**             | Дымовые тесты: авто-открытие форм, проверка макетов СКД               | [alexandr-yang/yaxunit-smoke](https://github.com/alexandr-yang/yaxunit-smoke)             |
| 8   | **vanessa-runner**            | CLI-ядро: запуск BDD/TDD, сборка, деплой, сессии                      | [vanessa-opensource/vanessa-runner](https://github.com/vanessa-opensource/vanessa-runner) |
| 9   | **EDT Test Runner**           | Плагин EDT для запуска/отладки YAxUnit тестов                         | [bia-technologies/edt-test-runner](https://github.com/bia-technologies/edt-test-runner)   |
| 10  | **vanessa-app-mcp**           | MCP-обёртка для Vanessa Automation (BDD)                              | [spremotely/vanessa-app-mcp](https://lobehub.com/mcp/spremotely-vanessa-app-mcp)          |
| 11  | **mcp-onec-test-runner**      | MCP для YaXUnit тестов, сборка, EDT CLI                               | [alkoleft/mcp-onec-test-runner](https://github.com/alkoleft/mcp-onec-test-runner)         |
| 12  | **MockServer Client 1C**      | Мок HTTP-сервисов для тестирования интеграций                         | [astrizhachuk/mockserver-client-1c](https://github.com/astrizhachuk/mockserver-client-1c) |
| 13  | **Mutagen**                   | Мутационное тестирование — «тесты для тестов»                         | [oscript-library/mutagen](https://github.com/oscript-library/mutagen)                     |

#### Шаги внедрения

| Шаг  | Действие                                                  | Статус | Результат                                                                                                                                                                                |
| ---- | --------------------------------------------------------- | ------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 4.1  | Установить OneScript + vanessa-runner                     | ✓      | OneScript 2.0.0, vanessa-runner 2.6.0 (GitHub, hub.oscript.io TLS)                                                                                                                       |
| 4.2  | Настроить vanessa-runner для TestDB (`vrunner.json`)      | ✓      | `vrunner.json` в корне проекта                                                                                                                                                           |
| 4.3  | Скачать и установить расширения в TestDB                  | ✓      | YAXUnit 25.12 + VAExtension 1.21 + Smoke 0.2.1 — все активны                                                                                                                             |
| 4.4  | vanessa-app-mcp (MCP для BDD)                             | ⏭      | Не найден на GitHub/npm, пропущен                                                                                                                                                        |
| 4.5  | Добавить mcp-onec-test-runner в `.mcp.json`               | ✓      | JAR v0.5.1, stdio transport. Generic errors — использовать vrunner CLI напрямую                                                                                                          |
| 4.6  | Тест UI: "Открой документ, заполни форму, нажми Провести" | ⚠      | BDD шаги РАБОТАЮТ с ручным TestClient. Автозапуск TestClient (PID=0) не решён. Workaround: GUI подключение                                                                               |
| 4.7  | Тест BDD: "Создай BDD-сценарий"                           | ✓      | Feature `D:\va-test\features\bdd_document.feature` — все шаги пройдены (открытие, создание, закрытие документа)                                                                          |
| 4.8  | Установить mcp-onec-test-runner (MCP для YaXUnit)         | ✓      | `tools/mcp-jars/mcp-yaxunit-runner-0.5.1.jar`                                                                                                                                            |
| 4.9  | Тест TDD: "Запусти unit-тесты"                            | ✓      | **690 smoke-тестов** через `vrunner run` + YAxUnit. 554 passed (80.3%), 57 errors, 25 failures, 54 skipped. Отчёт: `build/reports/junit.xml` (950 KB)                                    |
| 4.10 | Настроить дымовые тесты                                   | ✓      | Конфиг `tools/yaxunit.json`: `ДымовыеТесты: {Использовать: true, ОткрытиеФорм: true}`. Пути в JSON — только обратные слеши (`D:\\...`), иначе `ЭтоАбсолютныйПутьWindows()` не распознаёт |
| 4.11 | Создать MCP-обёртку для vanessa-runner CLI (опционально)  | ⏳      | Не начато. vrunner CLI через Bash работает                                                                                                                                               |

**Результат (2026-03-14):** YAxUnit smoke-тесты полностью работают из CLI (690 тестов). VA BDD шаги **работают** с ручным подключением TestClient в GUI. Автозапуск TestClient (PID=0) не решён — workaround через GUI. Конфигурация: `D:\va-test\` (va.epf, VAParams.json, features/).

**Выбор инструмента по задаче:**

| Задача                                | Инструмент                            |
| ------------------------------------- | ------------------------------------- |
| Нажать «Провести» как пользователь    | **Vanessa Automation**                |
| Проверить клиентский код `&НаКлиенте` | **Vanessa Automation** (VAExtension)  |
| Дымовые тесты всех форм               | **Vanessa ADD** или **YAxUnit Smoke** |
| Юнит-тесты серверного кода            | **YAxUnit** или **xUnitFor1C**        |
| BDD-сценарии через MCP                | **vanessa-app-mcp**                   |
| CI/CD запуск тестов                   | **vanessa-runner** + любой фреймворк  |

**Рабочая схема: Claude + разработчик**

```
Claude (через MCP)                    Разработчик (в EDT GUI)
  │                                      │
  ├── mcp-onec-test-runner               │
  │   ├── запустить тесты ✓              │
  │   ├── получить результаты ✓          │
  │   └── "тест X упал, строка 42" ✓     │
  │                                      │
  │   ────── тест упал? ──────────►      │
  │                                      ├── EDT Test Runner (GUI-плагин)
  │                                      │   ├── Debug As…
  │                                      │   ├── breakpoint на строке 42
  │                                      │   └── step over, смотрит переменные
  │                                      │
  │   ◄────── нашёл причину ──────       │
  │                                      │
  ├── EDT-MCP (write_module_source)      │
  │   └── исправить код ✓                │
  └── mcp-onec-test-runner               │
      └── перезапустить тесты ✓          │
```

**Важно:** EDT Test Runner — GUI-плагин (нет API/CLI/MCP), Claude не может им управлять. Это инструмент разработчика для ручной отладки упавших тестов. `mcp-onec-test-runner` — MCP-аналог от того же автора (alkoleft), через который Claude запускает тесты и получает результаты.

**Статус (2026-03-14):** mcp-onec-test-runner добавлен в `.mcp.json`, но возвращает generic errors. Рабочий путь — `vrunner run` через Bash с `MSYS_NO_PATHCONV=1`.

**Рабочая команда запуска тестов:**
```bash
cd "D:/1С-Framework" && MSYS_NO_PATHCONV=1 \
  "C:/Tools/OneScript/bin/oscript.exe" \
  "C:/Tools/OneScript/lib/vanessa-runner/src/main.os" run \
  --ibconnection '/S"KOMPUTER\TestDB"' \
  --db-user "a.terletskiy@sodru.com" --db-pwd "Alex80Alex" \
  --v8version "8.3.27.1859" \
  --command 'RunUnitTests=D:\1С-Framework\tools\yaxunit.json' --debuglog
```

**Ключевые баги (решены):**
1. Пути в `yaxunit.json` — только `\\`, не `/` (YAxUnit `ЭтоАбсолютныйПутьWindows` проверяет backslash)
2. `ДымовыеТесты` — структура `{Использовать: true, ОткрытиеФорм: true}`, не boolean
3. `MSYS_NO_PATHCONV=1` — Git Bash манглит `/S` в Windows-путь

**vanessa-runner как CLI-ядро:** даже без собственного MCP, vanessa-runner остаётся ядром для CI/CD операций (сборка, деплой, управление сессиями). MCP-серверы (vanessa-app-mcp, onec-test-runner) вызывают его под капотом.

---

### Фаза 5: Метаданные через artesk/1C_MCP_metadata (0.5 дня)
> Дополнительный канал метаданных с поиском и валидацией запросов

**Инструменты:** artesk/1C_MCP_metadata

| Шаг | Действие                                                  | Время  |
| --- | --------------------------------------------------------- | ------ |
| 5.1 | Установить расширение 1C_MCP_metadata в TestDB            | 30 мин |
| 5.2 | Настроить PowerShell stdio-прокси                         | 30 мин |
| 5.3 | Добавить в `.mcp.json`                                    | 10 мин |
| 5.4 | Тест: "Покажи структуру документа гкс_ЛабораторныйАнализ" | 10 мин |

**Результат:** Дополняет ROCTUP: search_metadata (поиск по имени/синониму/комментарию) + validate_query + get_metadata_structure с фильтрацией.

---

## Итоговая архитектура

```
Claude Code
  │
  │ ═══ Фаза 1 (P0) ═══════════════════════════════════════════════════
  ├── ROCTUP Toolkit (1c-mcp-toolkit)         ─── Данные + Метаданные ► Docker:6003 ──► .epf ──► TestDB
  │   ├── execute_query                            Запросы 1С (чтение, запись)
  │   └── get_metadata                             Структура конфигурации
  │
  │ ═══ Фаза 2 (P0) ═══════════════════════════════════════════════════
  ├── EDT MCP (DitriXNew/EDT-MCP)             ─── BSL-разработка ────► 1C:EDT:8765 (33 tools)
  │   ├── list_modules, get_module_structure        Навигация по коду
  │   ├── read/write_module_source                  Чтение и запись BSL-кода
  │   ├── get_symbol_info, content_assist           Типизация, автодополнение
  │   ├── go_to_definition, find_references         Навигация по символам
  │   ├── get_method_call_hierarchy                 Граф вызовов (BM-index)
  │   ├── rename/delete/add_metadata                Рефакторинг метаданных
  │   ├── validate_query                            Валидация запросов (синтаксис + семантика)
  │   ├── get_form_screenshot                       Визуализация форм (PNG)
  │   ├── update_database, debug_launch             Деплой и отладка
  │   └── get_project_errors, get_tasks             Ошибки, TODO/FIXME
  │
  │ ═══ Фаза 3 (P1) ═══════════════════════════════════════════════════
  ├── 1C MCP (vladimir-kharin/1c_mcp)         ─── CRUD + Проведение ► HTTP-сервис ──► TestDB
  ├── OData MCP (oisee/odata_mcp_go)          ─── Быстрое чтение ──► IIS OData ────► TestDB
  │
  │ ═══ Фаза 3.5 (P1) — без установки нового MCP ═════════════════════
  ├── bsl-semantic-search (наш, расширенный)  ─── Мультивекторный RRF по метаданным
  │   └── Идеи из FSerg/mcp-1c-v1                  (object_name + friendly_name, Qdrant bsl_metadata)
  │
  │ ═══ Фаза 4 (P1) ═══════════════════════════════════════════════════
  ├── Vanessa MCP (vanessa-app-mcp)           ─── BDD тесты ────────► vanessa-runner ──► TestDB
  │   └── vanessa-runner CLI                       (ядро: сборка, деплой, сессии)
  ├── Test Runner MCP (mcp-onec-test-runner)  ─── YaXUnit тесты ───► Конфигуратор ────► TestDB
  │
  │ ═══ Фаза 5 (P2) ═══════════════════════════════════════════════════
  ├── Metadata MCP (artesk/1C_MCP_metadata)   ─── search + validate ► HTTP-сервис ────► TestDB
  │
  │ ═══ Фаза 6 (P2) ═══════════════════════════════════════════════════
  ├── bsl-debug-server (Java, DAP)           ─── Runtime-отладка 1С ► TCP:1550 ──► debug agent
  │   ├── debug_set_breakpoints                   Точки останова на строки модулей
  │   ├── debug_get_variables                     Чтение переменных в точке останова
  │   ├── debug_evaluate                          Выполнение выражений в контексте
  │   ├── debug_stack_trace                       Стек вызовов
  │   └── debug_step / debug_continue             Пошаговое выполнение
  │
  │ ═══ Уже работает ══════════════════════════════════════════════════
  └── BSL Platform (mcp-bsl-platform-context) ─── Справка платформы 8.3.27
```

## Приоритеты

| Приоритет | Фаза     | Инструмент                   | Ценность                                                           | Срок    |
| --------- | -------- | ---------------------------- | ------------------------------------------------------------------ | ------- |
| **P0**    | Фаза 1   | ROCTUP/1c-mcp-toolkit        | Данные + метаданные, Docker + .epf, 0 изменений конфигурации       | 1 день  |
| **P0**    | Фаза 2   | DitriXNew/EDT-MCP            | 33 tools: BSL R/W, рефакторинг, валидация, типизация, граф вызовов | 1-2 дня |
| **P1**    | Фаза 3   | 1c_mcp + OData               | Полноценный CRUD + быстрое batch-чтение                            | 2 дня   |
| **P1**    | Фаза 3.5 | Наш bsl-semantic-search      | Мультивекторный RRF по метаданным (идеи FSerg)                     | 1 день  |
| **P1**    | Фаза 4   | Vanessa Automation + YaXUnit | UI-эмуляция пользователя + BDD/TDD тестирование (13 проектов)      | 3-4 дня |
| **P2**    | Фаза 5   | artesk/1C_MCP_metadata       | Дополнительный поиск по метаданным                                 | 0.5 дня |

## Зависимости

```
Фаза 1 (ROCTUP Toolkit) ──► Docker ───────► самостоятельная (СТАРТ ЗДЕСЬ)
Фаза 2 (EDT-MCP) ─────────► 1C:EDT ───────► самостоятельная
Фаза 3 (1c_mcp + OData) ──► IIS ──────────► расширяет Фазу 1
Фаза 3.5 (RRF метаданные) ► наш Qdrant ──► расширяет bsl-semantic-search
Фаза 4 (Тестирование) ────► OneScript ────► vanessa-runner
Фаза 5 (artesk metadata) ─► расширение 1С ► дополняет Фазу 1
```

## Требования к серверу

| Компонент         | Фаза     | Статус                                               |
| ----------------- | -------- | ---------------------------------------------------- |
| Docker Desktop    | Фаза 1   | Нужно установить                                     |
| 1C:EDT            | Фаза 2   | Нужно установить                                     |
| IIS               | Фаза 3   | Уже есть                                             |
| Python 3.11+      | Фаза 3   | Уже есть                                             |
| OneScript 2.0.0   | Фаза 4   | Уже установлен: `C:\Tools\OneScript\bin\oscript.exe` |
| Go (или бинарник) | Фаза 3   | Для сборки odata_mcp_go                              |
| Node.js 16+       | Фаза 4   | Для vanessa-app-mcp                                  |
| Qdrant            | Фаза 3.5 | Уже работает (localhost:6333)                        |
                                                                                                                                            
  
### Фаза 6: Runtime-отладка 1С через bsl-debug-server ⏳ TODO
> Claude программно ставит breakpoints, читает переменные и управляет выполнением BSL в реальной 1С

**Инструменты:** [1c-syntax/bsl-debug-server](https://github.com/1c-syntax/bsl-debug-server) (Java) + vsc-bsl-dap (VS Code) + MCP-DAP адаптер (создать)

**Зачем:** Фазы 1–4 дают доступ к данным, коду и тестам, но не к **runtime-состоянию**. Отладка позволяет:
- Остановить 1С на конкретной строке и прочитать значения переменных
- Выполнить произвольное выражение в контексте остановки
- Шагнуть по коду (step over/in/out)
- Понять **почему** код работает именно так, а не просто **что** он делает

**Архитектура:**

```
┌──────────────┐                ┌──────────────────┐                ┌─────────────────┐
│   VS Code    │  DAP Protocol  │ bsl-debug-server │   TCP :1550    │ 1С:Предприятие  │
│ + vsc-bsl-dap│ ◄────────────► │     (Java)       │ ◄────────────► │  (debug agent)  │
└──────────────┘   JSON-RPC     └──────────────────┘                └─────────────────┘
       │                               ▲
       │ Breakpoints, Variables,       │
       │ Step Over, Call Stack         │ DAP Protocol
       │                               │
┌──────────────┐                ┌──────────────────┐
│  Claude Code │  MCP Protocol  │  MCP-DAP адаптер │
│  (AI-агент)  │ ◄────────────► │   (создать)      │
└──────────────┘                └──────────────────┘
```

**Два клиента — один отладчик:**
- **VS Code** — визуально: видишь код, красные точки, жёлтую строку останова, панель переменных
- **Claude** — программно: те же команды через MCP, без GUI

**Workflow (как это выглядит для пользователя):**

1. Запускаешь 1С с отладкой: `/Debug -http -port 1550`
2. bsl-debug-server подключается к 1С (мост DAP ↔ debug agent)
3. VS Code подключается к bsl-debug-server (видишь BSL-код)
4. Claude через MCP ставит breakpoint: `setBreakpoints("МодульОбъекта", строка 142)`
5. **Ты работаешь в 1С** — открываешь документ, нажимаешь "Провести"
6. 1С доходит до строки 142 → **останавливается**
7. VS Code подсвечивает строку жёлтым
8. Claude читает переменные:
   ```
   Контрагент = СправочникСсылка.Контрагенты: "ООО Ясная Поляна"
   МассаНетто = 25400.5
   Результат = Неопределено
   ```
9. Claude выполняет выражение: `evaluate("Контрагент.ИНН")` → `"2507123456"`
10. Claude командует `stepOver()` или `continue()`

**Что видит пользователь в VS Code:**

```
┌─ Переменные ─────────────────────┐  ┌─ Call Stack ──────────────────┐
│ ▼ Локальные                      │  │ ОбработкаПроведения() : 142   │ ← останов
│   Контрагент = СправочникСсылка  │  │ Записать() : 89               │
│   МассаНетто = 25400.5           │  │ ОбработкаКоманды() : 15       │
│   Результат  = Неопределено      │  └───────────────────────────────┘
└──────────────────────────────────┘
```

**DAP-команды (программный доступ для Claude через MCP):**

| DAP-команда | MCP-инструмент | Что делает |
|-------------|---------------|------------|
| `setBreakpoints` | `debug_set_breakpoints` | Поставить точки останова на строки модуля |
| `variables` | `debug_get_variables` | Прочитать значения переменных в точке останова |
| `evaluate` | `debug_evaluate` | Выполнить выражение в контексте текущего фрейма |
| `stackTrace` | `debug_stack_trace` | Получить стек вызовов |
| `continue` | `debug_continue` | Продолжить выполнение |
| `stepOver` / `stepIn` | `debug_step` | Шагнуть через/внутрь вызова |

**Шаги внедрения:**

| Шаг | Действие                                              | Статус | Результат |
| --- | ----------------------------------------------------- | ------ | --------- |
| 6.1 | Установить Java Runtime (JRE 11+)                     | ⏳      |           |
| 6.2 | Скачать bsl-debug-server JAR                           | ⏳      |           |
| 6.3 | Установить vsc-bsl-dap в VS Code                      | ⏳      |           |
| 6.4 | Запустить 1С с /Debug, подключить bsl-debug-server     | ⏳      |           |
| 6.5 | Тест: breakpoint в VS Code → останов → переменные     | ⏳      |           |
| 6.6 | Создать MCP-DAP адаптер (MCP tools → DAP commands)    | ⏳      |           |
| 6.7 | Тест: Claude ставит breakpoint, читает переменные     | ⏳      |           |

**Требования:**
- Java Runtime (JRE 11+)
- BSL-файлы модулей (выгрузка из EDT или Конфигуратора в `src/bsl/`)
- 1С запущена с флагом отладки
- Порт 1550 свободен (TCP, debug agent)
- Порт 4711 свободен (DAP, bsl-debug-server)

**Уже есть (не путать):**
- `bsl-debugger` MCP (Node.js) — отладка **OneScript** (не 1С:Предприятие)
- `EDT-MCP debug_launch` — только **запускает** отладку, без программного управления
