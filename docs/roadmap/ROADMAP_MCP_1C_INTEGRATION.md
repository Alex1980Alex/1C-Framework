# Дорожная карта: MCP-интеграция с 1С:Предприятие

> Цель: подключить Claude Code к серверной базе `Srvr="localhost";Ref="TestDB"` для чтения данных, проведения документов, редактирования справочников, тестирования и работы с метаданными.

## Сводная таблица инструментов (без дублирования)

| # | Проект | Категория | Уникальные возможности | GitHub |
|---|--------|-----------|----------------------|--------|
| 1 | vladimir-kharin/1c_mcp | Данные | HTTP-сервис + Python proxy, stdio + SSE, расширение 1С | [link](https://github.com/vladimir-kharin/1c_mcp) |
| 2 | ROCTUP/1c-mcp-toolkit | Данные | REST API + long polling, Docker, .epf обработка, каналы изоляции | [link](https://github.com/ROCTUP/1c-mcp-toolkit) |
| 3 | ruslan-hut/onec-mcp | Данные | Go gateway, поиск контрагентов, отчёты продаж | [link](https://github.com/ruslan-hut/onec-mcp) |
| 4 | artesk/1C_MCP_metadata | Метаданные | Структура метаданных, фильтрация по типам объектов | [link](https://github.com/artesk/1C_MCP_metadata) |
| 5 | FSerg/mcp-1c-v1 | Метаданные | RAG + Qdrant по структуре конфигурации | [link](https://github.com/FSerg/mcp-1c-v1) |
| 6 | alkoleft/mcp-bsl-platform-context | BSL | Синтакс-помощник платформы 8.3 (уже установлен!) | [link](https://github.com/alkoleft/mcp-bsl-platform-context) |
| 7 | alkoleft/mcp-onec-test-runner | BSL | YaXUnit тесты, сборка, EDT CLI | [link](https://github.com/alkoleft/mcp-onec-test-runner) |
| 8 | DitriXNew/EDT-MCP | BSL | 1C:EDT плагин, 33 MCP-инструмента: BSL-анализ, валидация запросов, рефакторинг, скриншоты форм | [link](https://github.com/DitriXNew/EDT-MCP) |
| 9 | spremotely/vanessa-app-mcp | Тестирование | MCP-обёртка для Vanessa Automation (BDD) | [link](https://lobehub.com/mcp/spremotely-vanessa-app-mcp) |
| 10 | vanessa-opensource/vanessa-runner | CI/CD | CLI: сборка, деплой, запуск тестов (поглотил deployka) | [link](https://github.com/vanessa-opensource/vanessa-runner) |
| 11 | oisee/odata_mcp_go | OData | Универсальный OData v2/v4 мост (работает с 1С OData) | [link](https://github.com/oisee/odata_mcp_go) |

**Исключены как дубли:**
- `iflow-mcp-1c` (PyPI) — форк vladimir-kharin/1c_mcp, идентичный функционал
- `Antonio1C/1c-syntax-helper-mcp` — дублирует alkoleft/mcp-bsl-platform-context
- `CDataSoftware/odata-mcp-server` — read-only, oisee/odata_mcp_go мощнее
- `deployka` — поглощена vanessa-runner
- `ARQA` — коммерческий аналог 1c_mcp, не open-source

---

## Сравнение: Vanessa-runner vs аналоги

| Возможность | vanessa-runner | mcp-onec-test-runner | vanessa-app-mcp | EDT-MCP |
|-------------|---------------|---------------------|-----------------|---------|
| Запуск BDD (Gherkin) | CLI команда `vrunner vanessa` | - | MCP tool `run_scenario` | - |
| Запуск TDD (xUnit) | CLI `vrunner xunit` | MCP `run_tests` (YaXUnit) | - | - |
| Сборка cf/cfe | `vrunner compile` | MCP `build` | - | Через EDT CLI |
| Деплой базы | `vrunner init-dev`, `vrunner update` | - | - | - |
| Создание feature-файлов | - | - | MCP `create_feature` | - |
| Генерация шагов | - | - | MCP `generate_steps` | - |
| Парсинг Gherkin | - | - | MCP `parse_feature` | - |
| Валидация запросов 1С | - | - | - | MCP tool |
| BSL-анализ кода | - | - | - | MCP tool |
| Управление сессиями 1С | `vrunner session` | - | - | - |
| MCP протокол | Нет (CLI) | Да | Да | Да |
| Зрелость | Зрелый, экосистема | Молодой | Молодой | Молодой |

**Вывод:** vanessa-runner — самый зрелый, но не имеет MCP. Все 3 MCP-аналога покрывают разные ниши. Оптимально: **vanessa-runner (CLI) + MCP-обёртка** для вызова его команд из Claude.

---

## Детальный анализ ключевых инструментов

### ROCTUP/1c-mcp-toolkit — Лучший выбор для данных + метаданных

**Почему первый:** Docker + .epf = быстрый старт без изменения конфигурации. Даёт и чтение, и запись, и метаданные в одном пакете.

| Критерий | Значение |
|----------|----------|
| MCP Tools | `execute_query` (запросы 1С), `get_metadata` (структура конфигурации) |
| Архитектура | Claude ──MCP──► Python Proxy (FastAPI:6003) ──long polling──► .epf в 1С ──► TestDB |
| Установка | `docker run -d -p 6003:6003 roctup/1c-mcp-toolkit-proxy` + открыть .epf в 1С |
| Каналы изоляции | `?channel=dev` / `?channel=prod` — разделение dev/prod |
| REST API | Параллельный доступ через curl (skill `calling-1c-rest-api-via-curl`) |
| Платформы | 8.2.13+ и 8.3 |
| Не меняет конфигурацию | Да (.epf обработка) |
| Готовые skills | Синтаксис запросов 1С, оптимизация, виртуальные таблицы, JOINs |

**Ограничения:** 2 MCP-инструмента (создание/проведение документов — через execute_query), long polling задержка.

### DitriXNew/EDT-MCP — Мощнейший инструмент для BSL-разработки

**Почему второй:** 33 MCP-инструмента — мощнее чем bsl-platform-context + serena вместе. Но требует 1C:EDT.

| Tool | Категория | Что делает |
|------|-----------|-----------|
| **Проекты и конфигурация** | | |
| `list_projects` | Проекты | Список проектов в workspace EDT |
| `get_configuration_properties` | Проекты | Свойства конфигурации (имя, совместимость, вариант скрипта) |
| `get_applications` | Проекты | Список информационных баз проекта (ID для update/debug) |
| `get_edt_version` | Проекты | Версия 1C:EDT |
| **Метаданные** | | |
| `get_metadata_objects` | Метаданные | Список объектов с фильтрацией по типу (справочники, документы...) |
| `get_metadata_details` | Метаданные | Детальные свойства объектов (реквизиты, ТЧ, full mode) |
| `get_tags` | Метаданные | Список тегов проекта |
| `get_objects_by_tags` | Метаданные | Поиск объектов по тегам |
| **BSL-код — чтение** | | |
| `list_modules` | BSL-код | Список модулей с фильтрами по типу |
| `get_module_structure` | BSL-код | Процедуры/функции, сигнатуры, строки, регионы, &НаСервере/&НаКлиенте |
| `read_module_source` | BSL-код | Чтение исходного кода модуля (полный или диапазон строк) |
| `read_method_source` | BSL-код | Чтение конкретной процедуры/функции по имени |
| **BSL-код — запись** | | |
| `write_module_source` | BSL-код | Запись в модуль (searchReplace/replace/append) с проверкой синтаксиса |
| **BSL-код — анализ** | | |
| `get_symbol_info` | Анализ | Типизация символа: inferred types, сигнатуры, документация (hover) |
| `get_content_assist` | Анализ | Автодополнение: подсказки типов, методов, документация платформы |
| `go_to_definition` | Навигация | Переход к определению символа (метод, объект метаданных) |
| `find_references` | Навигация | Поиск всех ссылок на объект (код, формы, роли, подсистемы) |
| `get_method_call_hierarchy` | Навигация | Иерархия вызовов: callers/callees через BM-index |
| `search_in_code` | Поиск | Полнотекстовый поиск по BSL (regex, фильтр по типу метаданных) |
| **Запросы 1С** | | |
| `validate_query` | Запросы | Валидация синтаксис + семантика (знает метаданные), режим DCS |
| **Ошибки и валидация** | | |
| `get_project_errors` | Ошибки | Детальные ошибки с фильтрами (severity, объект, checkId) |
| `get_problem_summary` | Ошибки | Сводка по количеству ошибок/предупреждений |
| `get_check_description` | Ошибки | Документация по конкретной проверке EDT |
| `revalidate_objects` | Валидация | Перезапуск валидации проекта или конкретных объектов |
| `clean_project` | Валидация | Полная очистка и ревалидация проекта |
| **Рефакторинг** | | |
| `rename_metadata_object` | Рефакторинг | Переименование с обновлением всех ссылок (preview + confirm) |
| `delete_metadata_object` | Рефакторинг | Удаление с очисткой ссылок (preview + confirm) |
| `add_metadata_attribute` | Рефакторинг | Добавление реквизита к объекту |
| **Формы** | | |
| `get_form_screenshot` | Формы | Скриншот формы из WYSIWYG-редактора (PNG) |
| **Навигация** | | |
| `get_bookmarks` | Навигация | Закладки в коде |
| `get_tasks` | Навигация | TODO/FIXME маркеры |
| **Деплой и отладка** | | |
| `update_database` | Деплой | Обновление БД (полное или инкрементальное) |
| `debug_launch` | Отладка | Запуск приложения в режиме отладки |

**Требования:** 1C:EDT установлен, проект открыт в workspace. Порт 8765, Streamable HTTP + SSE.

### FSerg/mcp-1c-v1 — Идеи для нашего индексатора (не устанавливать)

**Почему опционально:** У нас уже есть bsl-semantic-search с Qdrant + nomic-embed-text. Docker image 6+ ГБ ради одного `search_1c_documentation` — избыточно. Но идеи ценные:

| Идея из FSerg | Как применить у нас |
|---------------|-------------------|
| Мультивекторный RRF (object_name + friendly_name) | Добавить в bsl-semantic-search второй вектор по синонимам |
| Обработка `ПолучитьТекстСтруктурыКонфигурацииФайлами.epf` | Взять для выгрузки метаданных, загрузить в наш Qdrant |
| Коллекции через `x-collection-name` | У нас уже есть `bsl_code_v2`, добавить `bsl_metadata` |
| Веб-интерфейс Loader | Не нужен — у нас есть `scripts/index-folder.bat` |

**Действие:** Не устанавливать FSerg/mcp-1c-v1. Вместо этого в Фазе 3.5 взять его подход мультивекторного RRF и .epf обработку, интегрировать в наш существующий bsl-semantic-search.

### Сводная матрица

| Критерий | ROCTUP/toolkit | DitriXNew/EDT-MCP | FSerg/mcp-1c-v1 |
|----------|---------------|-------------------|-----------------|
| **MCP tools** | 2 | 33 | 1 |
| **Чтение данных** | execute_query | - | - |
| **Запись данных** | через запрос | - | - |
| **Метаданные** | get_metadata | list_modules, structure | RAG-поиск |
| **BSL-анализ** | - | 19 tools (чтение, запись, анализ, навигация, рефакторинг) | - |
| **Установка** | Docker 1 команда | EDT + плагин | Docker Compose (6 ГБ) |
| **Меняет конфигурацию** | Нет (.epf) | Нет (плагин) | Нет (выгрузка) |
| **Реальное время** | live | live workspace | по выгрузке |
| **Рекомендация** | **Ставить первым** | **Ставить вторым** | **Взять идеи** |

---

## Фазы внедрения

### Фаза 1: Данные + Метаданные через ROCTUP/1c-mcp-toolkit (1 день)
> MVP: Claude читает данные, выполняет запросы, видит структуру конфигурации TestDB

**Инструменты:** ROCTUP/1c-mcp-toolkit (Docker + .epf)

**Почему ROCTUP первый (а не OData или vladimir-kharin/1c_mcp):**
- Docker 1 команда — не нужен IIS, не нужно публиковать HTTP-сервис
- .epf обработка — не нужно устанавливать расширение в конфигурацию
- 2 инструмента покрывают и данные (execute_query) и метаданные (get_metadata) сразу
- Каналы изоляции dev/prod — безопасно для тестирования
- REST API параллельно — можно использовать и из скриптов

| Шаг | Действие | Время |
|-----|----------|-------|
| 1.1 | Установить Docker Desktop (если нет) | 15 мин |
| 1.2 | `docker run -d -p 6003:6003 -e ALLOW_DANGEROUS_WITH_APPROVAL=true --restart unless-stopped --name 1c-mcp-toolkit-proxy roctup/1c-mcp-toolkit-proxy` | 5 мин |
| 1.3 | Скачать `MCP_Toolkit_Клиент.epf` из `build/` репозитория | 5 мин |
| 1.4 | Открыть .epf в 1С TestDB, указать URL прокси: `http://localhost:6003` | 10 мин |
| 1.5 | Добавить в `.mcp.json` (или `.mcp/bsl.json`) | 10 мин |
| 1.6 | Тест чтение: `execute_query("ВЫБРАТЬ Наименование ИЗ Справочник.гкс_ГруппыТС")` | 10 мин |
| 1.7 | Тест метаданные: `get_metadata()` — получить структуру конфигурации | 10 мин |
| 1.8 | Тест запись: создать элемент справочника через execute_query | 15 мин |
| 1.9 | Настроить канал изоляции: `?channel=dev` | 10 мин |

**Результат:** Claude читает данные, выполняет запросы 1С, знает структуру конфигурации. Всё в одном инструменте.

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

| Шаг | Действие | Статус | Результат |
|-----|----------|--------|-----------|
| 2.1 | Установить 1C:EDT | ✓ | EDT 2025.2.3.30 |
| 2.2 | Импортировать проект GKSTCPLK-2182 | ✓ | УправлениеТранспортомНаПЛК |
| 2.3 | Установить EDT-MCP плагин | ✓ | Из marketplace |
| 2.4 | Включить auto-start | ✓ | Настройки → EDT MCP |
| 2.5 | Добавить в `.mcp.json` | ✓ | Порт 8765 |
| 2.6 | Тест: `list_modules` | ✓ | 5 модулей документа |
| 2.7 | Тест: `get_module_structure` | ✓ | 18 proc, 20 func, 1513 lines |
| 2.8 | Тест: `validate_query` | ✓ | 0 errors, valid |
| 2.9 | Тест: `get_symbol_info` | ✓ | Types: Соответствие, ДокументСсылка |
| 2.10 | Тест: `get_problems` | ✓ | 2 errors (Web-client) |

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

### Фаза 3: Расширенный доступ к данным (2 дня)
> Claude создаёт/проводит документы через полноценный HTTP-сервис + OData для быстрого чтения

**Инструменты:** vladimir-kharin/1c_mcp (CRUD) + oisee/odata_mcp_go (быстрое чтение)

| Шаг | Действие | Время |
|-----|----------|-------|
| 3.1 | Установить расширение `1c_ext` из vladimir-kharin/1c_mcp в TestDB | 30 мин |
| 3.2 | Опубликовать HTTP-сервис `mcp_APIBackend` на IIS | 30 мин |
| 3.3 | Настроить Python proxy: `pip install iflow-mcp-1c-alexmiawat-server` | 15 мин |
| 3.4 | Добавить в `.mcp.json` (транспорт: stdio) | 10 мин |
| 3.5 | Тест: "Создай и проведи документ" через 1c_mcp | 30 мин |
| 3.6 | Включить OData в конфигураторе TestDB | 15 мин |
| 3.7 | Опубликовать на IIS: `http://localhost/TestDB/odata/standard.odata/` | 30 мин |
| 3.8 | Собрать и настроить `odata_mcp_go` | 30 мин |
| 3.9 | Настроить RLS/права для MCP-пользователя | 1 час |

**Результат:** Три канала доступа к данным: ROCTUP (универсальный), 1c_mcp (CRUD), OData (быстрое чтение).

**Когда нужна Фаза 3 (а не только ROCTUP):**
- Нужно полноценное создание/проведение документов (не через execute_query)
- Нужен быстрый batch-доступ к данным (OData быстрее long polling)
- Нужен прямой HTTP без Docker

---

### Фаза 3.5: Мультивекторный RRF для метаданных (1 день)
> Интеграция идей FSerg/mcp-1c-v1 в наш bsl-semantic-search

**Вместо установки FSerg/mcp-1c-v1 (6 ГБ Docker)** — берём его лучшие идеи:

| Шаг | Действие | Время |
|-----|----------|-------|
| 3.5.1 | Скачать .epf обработку `ПолучитьТекстСтруктурыКонфигурацииФайлами` из FSerg/mcp-1c-v1 | 10 мин |
| 3.5.2 | Выгрузить метаданные конфигурации из TestDB через обработку | 15 мин |
| 3.5.3 | Создать коллекцию `bsl_metadata` в нашем Qdrant (768d nomic-embed-text) | 30 мин |
| 3.5.4 | Написать скрипт загрузки метаданных с 2 векторами: object_name + friendly_name | 2 часа |
| 3.5.5 | Добавить RRF-fusion в bsl-semantic-search для мультивекторного поиска | 2 часа |
| 3.5.6 | Тест: "Найди все регистры связанные с качеством" — семантический поиск по метаданным | 15 мин |

**Результат:** Семантический поиск по метаданным конфигурации через наш существующий Qdrant. Без 6 ГБ Docker.

---

### Фаза 4: Тестирование — Vanessa Automation + YaXUnit (3-4 дня)
> Claude эмулирует действия пользователя (нажатие кнопок, проведение документов), запускает BDD/TDD тесты

**Инструменты:** Vanessa Automation (UI) + vanessa-runner (CLI) + spremotely/vanessa-app-mcp + alkoleft/mcp-onec-test-runner

#### Vanessa Automation — эмуляция пользователя

**Зачем:** COM-соединение (Фаза 1) и EDT-MCP (Фаза 2) работают на сервере — у них нет форм, кнопок, клиентского контекста. Vanessa Automation решает это:

| Возможность | COM (ROCTUP) | EDT-MCP | Vanessa Automation |
|---|---|---|---|
| Нажать кнопку «Провести» | Нет | Нет | **Да** |
| Выполнить код `&НаКлиенте` | Нет | Нет | **Да** (VAExtension) |
| Заполнить форму как пользователь | Нет | Нет | **Да** |
| Проверить обработчики форм | Нет | Нет | **Да** |
| Работать с модальными окнами | Нет | Нет | **Да** |
| Запись действий → генерация кода | Нет | Нет | **Да** |

**Ключевые GitHub-проекты:**

| # | Проект | Назначение | GitHub |
|---|--------|-----------|--------|
| 1 | **Vanessa Automation** | BDD, полная эмуляция пользователя, VAExtension (клиент+сервер код) | [Pr-Mex/vanessa-automation](https://github.com/Pr-Mex/vanessa-automation) |
| 2 | **Vanessa Automation Single** | Однофайловая версия VA, Исследователь формы | [Pr-Mex/vanessa-automation-single](https://github.com/Pr-Mex/vanessa-automation-single) |
| 3 | **Vanessa ADD** | TDD+BDD, плагин «ТестКлиенты», дымовые тесты всех форм | [vanessa-opensource/add](https://github.com/vanessa-opensource/add) |
| 4 | **Тестер 1С** | Сценарное тестирование, запись действий пользователя, видеозапись, CI | [grumagargler/tester](https://github.com/grumagargler/tester) |
| 5 | **xUnitFor1C** | Юнит+сценарное тестирование, тонкий/толстый клиент | [xDrivenDevelopment/xUnitFor1C](https://github.com/xDrivenDevelopment/xUnitFor1C) |
| 6 | **YAxUnit** | Современный фреймворк, Allure-отчёты, EDT интеграция | [bia-technologies/yaxunit](https://github.com/bia-technologies/yaxunit) |
| 7 | **YAxUnit Smoke** | Дымовые тесты: авто-открытие форм, проверка макетов СКД | [alexandr-yang/yaxunit-smoke](https://github.com/alexandr-yang/yaxunit-smoke) |
| 8 | **vanessa-runner** | CLI-ядро: запуск BDD/TDD, сборка, деплой, сессии | [vanessa-opensource/vanessa-runner](https://github.com/vanessa-opensource/vanessa-runner) |
| 9 | **EDT Test Runner** | Плагин EDT для запуска/отладки YAxUnit тестов | [bia-technologies/edt-test-runner](https://github.com/bia-technologies/edt-test-runner) |
| 10 | **vanessa-app-mcp** | MCP-обёртка для Vanessa Automation (BDD) | [spremotely/vanessa-app-mcp](https://lobehub.com/mcp/spremotely-vanessa-app-mcp) |
| 11 | **mcp-onec-test-runner** | MCP для YaXUnit тестов, сборка, EDT CLI | [alkoleft/mcp-onec-test-runner](https://github.com/alkoleft/mcp-onec-test-runner) |
| 12 | **MockServer Client 1C** | Мок HTTP-сервисов для тестирования интеграций | [astrizhachuk/mockserver-client-1c](https://github.com/astrizhachuk/mockserver-client-1c) |
| 13 | **Mutagen** | Мутационное тестирование — «тесты для тестов» | [oscript-library/mutagen](https://github.com/oscript-library/mutagen) |

#### Шаги внедрения

| Шаг | Действие | Статус | Результат |
|-----|----------|--------|-----------|
| 4.1 | Установить OneScript + vanessa-runner | ✓ | OneScript 2.0.0, vanessa-runner 2.6.0 (GitHub, hub.oscript.io TLS) |
| 4.2 | Настроить vanessa-runner для TestDB (`vrunner.json`) | ✓ | `vrunner.json` в корне проекта |
| 4.3 | Скачать и установить расширения в TestDB | ✓ | YAXUnit 25.12 + VAExtension 1.21 + Smoke 0.2.1 — все активны |
| 4.4 | vanessa-app-mcp (MCP для BDD) | ⏭ | Не найден на GitHub/npm, пропущен |
| 4.5 | Добавить mcp-onec-test-runner в `.mcp.json` | ✓ | JAR v0.5.1, stdio transport. Generic errors — использовать vrunner CLI напрямую |
| 4.6 | Тест UI: "Открой документ, заполни форму, нажми Провести" | ⏸ | VA TestClient не подключается к серверной базе. Отложено |
| 4.7 | Тест BDD: "Создай BDD-сценарий" | ⏸ | Зависит от 4.6 (TestClient). Feature-файл `features/smoke.feature` создан |
| 4.8 | Установить mcp-onec-test-runner (MCP для YaXUnit) | ✓ | `tools/mcp-jars/mcp-yaxunit-runner-0.5.1.jar` |
| 4.9 | Тест TDD: "Запусти unit-тесты" | ✓ | **690 smoke-тестов** через `vrunner run` + YAxUnit. 554 passed (80.3%), 57 errors, 25 failures, 54 skipped. Отчёт: `build/reports/junit.xml` (950 KB) |
| 4.10 | Настроить дымовые тесты | ✓ | Конфиг `tools/yaxunit.json`: `ДымовыеТесты: {Использовать: true, ОткрытиеФорм: true}`. Пути в JSON — только обратные слеши (`D:\\...`), иначе `ЭтоАбсолютныйПутьWindows()` не распознаёт |
| 4.11 | Создать MCP-обёртку для vanessa-runner CLI (опционально) | ⏳ | Не начато. vrunner CLI через Bash работает |

**Результат (2026-03-14):** YAxUnit smoke-тесты полностью работают из CLI. 690 тестов открытия форм за ~5 минут. VA BDD-тестирование отложено до настройки TestClient.

**Выбор инструмента по задаче:**

| Задача | Инструмент |
|---|---|
| Нажать «Провести» как пользователь | **Vanessa Automation** |
| Проверить клиентский код `&НаКлиенте` | **Vanessa Automation** (VAExtension) |
| Дымовые тесты всех форм | **Vanessa ADD** или **YAxUnit Smoke** |
| Юнит-тесты серверного кода | **YAxUnit** или **xUnitFor1C** |
| BDD-сценарии через MCP | **vanessa-app-mcp** |
| CI/CD запуск тестов | **vanessa-runner** + любой фреймворк |

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

**Статус:** `mcp-onec-test-runner` **не добавлен** в `.mcp.json` — будет настроен при выполнении Фазы 4.

**vanessa-runner как CLI-ядро:** даже без собственного MCP, vanessa-runner остаётся ядром для CI/CD операций (сборка, деплой, управление сессиями). MCP-серверы (vanessa-app-mcp, onec-test-runner) вызывают его под капотом.

---

### Фаза 5: Метаданные через artesk/1C_MCP_metadata (0.5 дня)
> Дополнительный канал метаданных с поиском и валидацией запросов

**Инструменты:** artesk/1C_MCP_metadata

| Шаг | Действие | Время |
|-----|----------|-------|
| 5.1 | Установить расширение 1C_MCP_metadata в TestDB | 30 мин |
| 5.2 | Настроить PowerShell stdio-прокси | 30 мин |
| 5.3 | Добавить в `.mcp.json` | 10 мин |
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
  │ ═══ Уже работает ══════════════════════════════════════════════════
  └── BSL Platform (mcp-bsl-platform-context) ─── Справка платформы 8.3.27
```

## Приоритеты

| Приоритет | Фаза | Инструмент | Ценность | Срок |
|-----------|-------|-----------|----------|------|
| **P0** | Фаза 1 | ROCTUP/1c-mcp-toolkit | Данные + метаданные, Docker + .epf, 0 изменений конфигурации | 1 день |
| **P0** | Фаза 2 | DitriXNew/EDT-MCP | 33 tools: BSL R/W, рефакторинг, валидация, типизация, граф вызовов | 1-2 дня |
| **P1** | Фаза 3 | 1c_mcp + OData | Полноценный CRUD + быстрое batch-чтение | 2 дня |
| **P1** | Фаза 3.5 | Наш bsl-semantic-search | Мультивекторный RRF по метаданным (идеи FSerg) | 1 день |
| **P1** | Фаза 4 | Vanessa Automation + YaXUnit | UI-эмуляция пользователя + BDD/TDD тестирование (13 проектов) | 3-4 дня |
| **P2** | Фаза 5 | artesk/1C_MCP_metadata | Дополнительный поиск по метаданным | 0.5 дня |

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

| Компонент | Фаза | Статус |
|-----------|-------|--------|
| Docker Desktop | Фаза 1 | Нужно установить |
| 1C:EDT | Фаза 2 | Нужно установить |
| IIS | Фаза 3 | Уже есть |
| Python 3.11+ | Фаза 3 | Уже есть |
| OneScript 2.0.0 | Фаза 4 | Уже установлен: `C:\Tools\OneScript\bin\oscript.exe` |
| Go (или бинарник) | Фаза 3 | Для сборки odata_mcp_go |
| Node.js 16+ | Фаза 4 | Для vanessa-app-mcp |
| Qdrant | Фаза 3.5 | Уже работает (localhost:6333) |
