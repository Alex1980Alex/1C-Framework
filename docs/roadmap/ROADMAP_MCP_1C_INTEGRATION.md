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
| 8 | DitriXNew/EDT-MCP | BSL | 1C:EDT плагин, валидация запросов, BSL-анализ | [link](https://github.com/DitriXNew/EDT-MCP) |
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

**Почему второй:** 13 MCP-инструментов — мощнее чем bsl-platform-context + serena вместе. Но требует 1C:EDT.

| Tool | Категория | Что делает |
|------|-----------|-----------|
| `list_projects` | Проекты | Список проектов в workspace EDT |
| `get_project_info` | Проекты | Свойства конфигурации проекта |
| `get_problems` | Ошибки | Ошибки и предупреждения с фильтрами |
| `get_problem_summary` | Ошибки | Сводка по количеству ошибок/предупреждений |
| `get_check_description` | Ошибки | Документация по конкретной проверке |
| `revalidate_project` | Валидация | Перезапуск валидации проекта |
| `validate_query` | Запросы 1С | Валидация синтаксис + семантика (знает метаданные), режим DCS |
| `list_modules` | BSL-код | Список модулей с фильтрами по типу (документы, справочники, регистры...) |
| `get_module_structure` | BSL-код | Процедуры/функции, сигнатуры, строки, регионы, &НаСервере/&НаКлиенте |
| `get_symbol_info` | BSL-код | Типизация символа: inferred types, сигнатуры, документация (hover) |
| `content_assist` | Автодополнение | Подсказки типов, методов, документация платформы |
| `get_bookmarks` | Навигация | Закладки в коде |
| `get_tasks` | Навигация | TODO/FIXME маркеры |

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
| **MCP tools** | 2 | 13 | 1 |
| **Чтение данных** | execute_query | - | - |
| **Запись данных** | через запрос | - | - |
| **Метаданные** | get_metadata | list_modules, structure | RAG-поиск |
| **BSL-анализ** | - | 5 tools + валидация | - |
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

### Фаза 2: BSL-разработка через EDT-MCP (1-2 дня)
> Claude анализирует BSL-код, валидирует запросы, навигирует по модулям через 13 инструментов EDT

**Инструменты:** DitriXNew/EDT-MCP + alkoleft/mcp-bsl-platform-context (уже установлен)

**Почему EDT-MCP вторым:**
- 13 MCP-инструментов — мощнее bsl-platform-context + serena вместе
- Валидация запросов 1С в контексте метаданных (знает справочники/документы)
- get_symbol_info — типизация для динамического BSL (то, чего нет у LSP)
- Но требует 1C:EDT — нужна установка IDE

| Шаг | Действие | Время |
|-----|----------|-------|
| 2.1 | Установить 1C:EDT (если не установлен) | 1 час |
| 2.2 | Импортировать проект GKSTCPLK-2182 в EDT workspace | 30 мин |
| 2.3 | Установить EDT-MCP плагин (из marketplace или вручную) | 30 мин |
| 2.4 | Включить auto-start в настройках плагина | 5 мин |
| 2.5 | Добавить в `.mcp.json` | 10 мин |
| 2.6 | Тест: `list_modules` — получить все модули документа гкс_ЛабораторныйАнализ | 10 мин |
| 2.7 | Тест: `get_module_structure` — структура модуля менеджера | 10 мин |
| 2.8 | Тест: `validate_query` — проверить запрос из модуля проведения | 10 мин |
| 2.9 | Тест: `get_symbol_info` — типизация переменной в процедуре | 10 мин |
| 2.10 | Тест: `get_problems` — список всех ошибок проекта | 10 мин |

**Результат:** Claude полноценно анализирует BSL-код — модули, типы, запросы, ошибки.

**Конфигурация `.mcp.json`:**
```json
{
  "mcpServers": {
    "edt-mcp": {
      "url": "http://localhost:8765/mcp"
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

### Фаза 4: Тестирование — Vanessa + YaXUnit (2-3 дня)
> Claude запускает BDD/TDD тесты и анализирует результаты

**Инструменты:** vanessa-runner (CLI) + spremotely/vanessa-app-mcp + alkoleft/mcp-onec-test-runner

| Шаг | Действие | Время |
|-----|----------|-------|
| 4.1 | Установить OneScript + vanessa-runner: `opm install vanessa-runner` | 30 мин |
| 4.2 | Настроить vanessa-runner для TestDB (`vrunner.json`) | 1 час |
| 4.3 | Установить vanessa-app-mcp (MCP для BDD) | 30 мин |
| 4.4 | Добавить в `.mcp.json` | 10 мин |
| 4.5 | Тест: "Создай BDD-сценарий проверки блокировки ТС" | 30 мин |
| 4.6 | Установить mcp-onec-test-runner (MCP для YaXUnit) | 30 мин |
| 4.7 | Тест: "Запусти unit-тесты модуля гкс_ВходнойКонтрольКачества" | 30 мин |
| 4.8 | Создать MCP-обёртку для vanessa-runner CLI (опционально) | 2 часа |

**Результат:** Claude пишет и запускает тесты — BDD через Vanessa, TDD через YaXUnit.

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
  ├── OData MCP (oisee/odata_mcp_go)          ─── Быстрое чтение ───► IIS OData ──► TestDB
  │
  ├── 1C MCP (vladimir-kharin/1c_mcp)         ─── CRUD + Проведение ► HTTP-сервис ─► TestDB
  │
  ├── Metadata MCP (artesk/1C_MCP_metadata)   ─── Структура конфиг. ► HTTP-сервис ─► TestDB
  │
  ├── Vanessa MCP (vanessa-app-mcp)           ─── BDD тесты ────────► vanessa-runner ──► TestDB
  │   └── vanessa-runner CLI                       (ядро: сборка, деплой, сессии)
  │
  ├── Test Runner MCP (mcp-onec-test-runner)  ─── YaXUnit тесты ───► Конфигуратор ──► TestDB
  │
  ├── BSL Platform (mcp-bsl-platform-context) ─── Справка платформы   (уже работает)
  │
  ├── EDT MCP (DitriXNew/EDT-MCP)             ─── BSL-анализ, запросы ► 1C:EDT
  │
  └── Toolkit (ROCTUP/1c-mcp-toolkit)         ─── Резервный канал ──► .epf ─────────► TestDB
```

## Приоритеты

| Приоритет | Фаза | Ценность |
|-----------|-------|----------|
| P0 (сейчас) | Фаза 1: OData чтение | Мгновенный доступ к данным, 0 изменений конфигурации |
| P0 (сейчас) | Фаза 2: 1c_mcp запись | Полноценная работа с базой |
| P1 (неделя) | Фаза 3: Метаданные | Claude "видит" структуру конфигурации |
| P1 (неделя) | Фаза 4: Тестирование | Автоматизация QA |
| P2 (позже) | Фаза 5: EDT + BSL | Валидация кода |
| P3 (резерв) | Фаза 6: Toolkit | Резервный канал |

## Зависимости

```
Фаза 1 (OData) ──────────────────────────► самостоятельная
Фаза 2 (1c_mcp) ─────────────────────────► самостоятельная
Фаза 3 (Метаданные) ─────────────────────► самостоятельная, усиливает Фазу 2
Фаза 4 (Тестирование) ───► OneScript ────► vanessa-runner
Фаза 5 (EDT) ────────────► 1C:EDT ───────► самостоятельная
Фаза 6 (Toolkit) ────────► Docker ────────► самостоятельная
```

## Требования к серверу

- IIS (для публикации OData и HTTP-сервисов) — уже есть на сервере
- OneScript 2.0.0 — уже установлен: `C:\Tools\OneScript\bin\oscript.exe`
- Python 3.11+ — уже есть
- Docker (опционально, для Фазы 6)
- Go (для сборки odata_mcp_go, или скачать бинарник)
- Node.js 16+ (для vanessa-app-mcp)
