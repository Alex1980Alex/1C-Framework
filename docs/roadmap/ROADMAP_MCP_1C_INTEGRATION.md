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

## Фазы внедрения

### Фаза 1: Чтение данных (1-2 дня)
> Минимальный MVP: Claude читает справочники и документы из TestDB

**Инструменты:** oisee/odata_mcp_go (OData мост)

| Шаг | Действие | Время |
|-----|----------|-------|
| 1.1 | Включить OData в конфигураторе TestDB (Администрирование → Публикация) | 15 мин |
| 1.2 | Опубликовать на IIS: `http://localhost/TestDB/odata/standard.odata/` | 30 мин |
| 1.3 | Собрать и настроить `odata_mcp_go` | 30 мин |
| 1.4 | Добавить в `.mcp.json` как MCP-сервер | 10 мин |
| 1.5 | Тест: "Покажи список справочника гкс_ГруппыТС" | 10 мин |

**Результат:** Claude может читать любые опубликованные объекты через OData.

**Ограничения OData:** read-only для сложных операций, нет проведения документов.

---

### Фаза 2: Запись и проведение (2-3 дня)
> Claude создаёт документы, редактирует справочники, проводит

**Инструменты:** vladimir-kharin/1c_mcp

| Шаг | Действие | Время |
|-----|----------|-------|
| 2.1 | Установить расширение `1c_ext` в TestDB | 30 мин |
| 2.2 | Опубликовать HTTP-сервис `mcp_APIBackend` на IIS | 30 мин |
| 2.3 | Настроить Python proxy: `pip install iflow-mcp-1c-alexmiawat-server` | 15 мин |
| 2.4 | Добавить в `.mcp.json` (транспорт: stdio) | 10 мин |
| 2.5 | Тест: "Создай элемент справочника Контрагенты с наименованием Тест" | 15 мин |
| 2.6 | Тест: "Создай и проведи документ РеализацияТоваровУслуг" | 30 мин |
| 2.7 | Настроить RLS/права для MCP-пользователя | 1 час |

**Результат:** Claude полноценно работает с данными — как реальный пользователь.

---

### Фаза 3: Метаданные конфигурации (1 день)
> Claude знает структуру конфигурации: какие справочники, реквизиты, регистры

**Инструменты:** artesk/1C_MCP_metadata + FSerg/mcp-1c-v1

| Шаг | Действие | Время |
|-----|----------|-------|
| 3.1 | Установить расширение 1C_MCP_metadata в TestDB | 30 мин |
| 3.2 | Настроить PowerShell stdio-прокси | 30 мин |
| 3.3 | Добавить в `.mcp.json` | 10 мин |
| 3.4 | Тест: "Покажи структуру документа гкс_ЛабораторныйАнализ" | 10 мин |
| 3.5 | (Опционально) Настроить FSerg/mcp-1c-v1 для RAG по метаданным | 2 часа |

**Результат:** Claude знает что есть в конфигурации без ручного описания.

**Синергия с Фазой 2:** Claude сначала читает метаданные (Фаза 3), потом корректно создаёт объекты (Фаза 2).

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

### Фаза 5: IDE-интеграция и BSL-анализ (1 день)
> Claude анализирует BSL-код через EDT и синтакс-помощник

**Инструменты:** alkoleft/mcp-bsl-platform-context (уже установлен) + DitriXNew/EDT-MCP

| Шаг | Действие | Время |
|-----|----------|-------|
| 5.1 | mcp-bsl-platform-context уже работает — проверить актуальность | 10 мин |
| 5.2 | Установить EDT (если не установлен) | 1 час |
| 5.3 | Установить EDT-MCP плагин | 30 мин |
| 5.4 | Тест: "Проверь синтаксис запроса в модуле менеджера" | 15 мин |

**Результат:** Claude валидирует BSL-код и запросы 1С через EDT.

---

### Фаза 6: Полная интеграция и ROCTUP/1c-mcp-toolkit (1 день)
> Альтернативный канал данных + Docker + REST API

**Инструменты:** ROCTUP/1c-mcp-toolkit

| Шаг | Действие | Время |
|-----|----------|-------|
| 6.1 | `docker pull roctup/1c-mcp-toolkit-proxy` | 10 мин |
| 6.2 | Загрузить `MCP_Toolkit_Клиент.epf` в TestDB | 15 мин |
| 6.3 | Настроить каналы изоляции (dev/prod) | 30 мин |
| 6.4 | Добавить в `.mcp.json` как резервный канал | 10 мин |

**Результат:** Резервный канал доступа к данным. Полезен если HTTP-сервис из Фазы 2 недоступен.

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
