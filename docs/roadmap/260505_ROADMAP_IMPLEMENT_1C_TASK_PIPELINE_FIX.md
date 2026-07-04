# Дорожная карта: восстановление работоспособности `/implement-1c-task`

> **Дата:** 2026-05-05 (создана) → **2026-05-07 (DONE)**
> **Триггер:** smoke-test реального выполнения команды `/implement-1c-task` — pipeline корректно остановился на Этапе 0 (Preflight v2.3.0).
> **Скилл:** [implement-1c-task/SKILL.md](../../.claude/skills/implement-1c-task/SKILL.md) (**v2.4.0** — TCP-probe + Stage 5 fallback)
> **Связанные документы:** [16.5_MCP_серверы_для_1С.md](../framework%20documentation/3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.5_MCP_серверы_для_1С.md), [16.6_EDT_MCP_setup.md](../framework%20documentation/3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.6_EDT_MCP_setup.md) (новый), [09.9_MCP_Health_Dashboard.md](../framework%20documentation/7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.9_MCP_Health_Dashboard.md), [260331_ROADMAP_MCP_IMPROVEMENTS.md](260331_ROADMAP_MCP_IMPROVEMENTS.md)

## Status (2026-05-07)

| Фаза | Статус | Артефакт |
|---|---|---|
| Phase 1: восстановить `1c-mcp-crud` | ✅ DONE | Путь мигрирован на `C:\1С-Framework\external\1c_mcp\` (commit `bf887153e`); `MCP_ONEC_PASSWORD` заполнен; mirror-конфиги признаны устаревшими и не добавлены |
| Phase 2: восстановить `edt-mcp` | ✅ DONE | EDT IDE поднята пользователем, порт `:8765` LISTENING; новый раздел [16.6_EDT_MCP_setup.md](../framework%20documentation/3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.6_EDT_MCP_setup.md) |
| Phase 3: runtime debug 1С (`:1550`) | ✅ DOCUMENTED (2026-05-08) | Smoke-test уже probe'ит `:1550` ([smoke_test_implement_1c_task.py:47-51](../../scripts/smoke_test_implement_1c_task.py#L47)) — отдельной интеграции не требуется. 16.6 §«1С debug agent» расширена: добавлены (а) callout «Когда это реально нужно vs можно пропустить» — runtime-debug опционален для типичных bug-fix/new-procedure прогонов, (б) cross-link на smoke-test, (в) troubleshooting-блок «Если :1550 закрыт» (5 шагов: висящий socket / firewall / версия платформы 8.3.13+ / правильный билд ragent / fallback на static `bsl_analyze`). Операционный запуск ragent.exe -debug -port 1550 остаётся за пользователем. Не блокер — `bsl_analyze` + EDT `get_project_errors` = 0 покрывают Этап 4 |
| Phase 4: усилить SKILL.md fallback'ами | ✅ DONE | SKILL.md v2.4.0: TCP-probe `:8765`/`:1550` в Stage 0; Stage 5 fallback — `bsl-code-search:find_callers` + `bsl-semantic-search:bsl_call_graph` + `bsl-debugger:bsl_analyze` |
| Phase 5: smoke-test + preflight hook | ✅ DONE | [`scripts/smoke_test_implement_1c_task.py`](../../scripts/smoke_test_implement_1c_task.py) — paths/ports/handshakes, exit 0/1/2 = Full/degraded/unusable. Preflight hook [`.claude/hooks/implement-1c-task-preflight.py`](../../.claude/hooks/implement-1c-task-preflight.py) добавлен 2026-05-07 (UserPromptSubmit, ловит `/implement-1c-task` через `<command-name>`-тег / raw-slash, запускает smoke-test JSON-mode, эмитит `systemMessage` с режимом и нерабочими серверами, лог `category="preflight"` с `run_id` от slash-command-tracker; timeout 30s) |
| Phase 6: документация | ✅ DONE | 16.5 ссылается на 16.6; КОМАНДЫ_CLAUDE_CODE.md содержит блок «Требования к среде» у `/implement-1c-task`; новая memory `feedback_mcp_json_paths.md` |

Pipeline mode без debug agent (типичный сценарий) — `Code-only` (запись и валидация работают, runtime-debug опционален).

---

## TL;DR

| Что сломано | Где | Корневая причина | Сложность |
|---|---|---|---|
| `1c-mcp-crud` (+ 3 mirror-конфига) | [`.mcp.json:144-187`](../../.mcp.json) | Путь `D:\1C-Enterprise_Framework\src\external\1c_mcp\` не существует — репо мигрирован, но `.mcp.json` не обновлён | **S** |
| `edt-mcp` | [`.mcp.json:124-128`](../../.mcp.json) | Конфиг `npx -y mcp-remote http://localhost:8765/mcp` — порт `:8765` закрыт, EDT IDE не запущена | **S** (операционная) |
| Runtime debug 1С | [`.mcp.json:188-196`](../../.mcp.json) | `1c-debug` MCP-сервер запущен, но 1С debug agent на `:1550` отсутствует | **M** |
| Этапы 2, 3 (write), 5, 6 SKILL.md | hard-stop без `edt-mcp` + `1c-mcp-crud` | Нет ни записи кода, ни верификации на живых данных | **L** (решается фиксом блокеров выше) |

**Текущий результат запуска `/implement-1c-task` (2026-05-05):** `Pipeline mode = Read-only research` → STOP перед Этапом 2. Реальные задачи из `configuration/.../docs/<TASK>/ANALYSIS-REPORT.md` выполнить нельзя.

---

## 1. Что проверено

Skill активирован, прошли только Preflight + сбор контекста.

### 1.1 Probe-результаты MCP-серверов (через ToolSearch в текущей сессии)

| Сервер | Статус | Probe |
|---|---|---|
| `mcp__edt-mcp__list_projects` | ❌ нет | `select:mcp__edt-mcp__list_projects` → `No matching deferred tools` |
| `mcp__edt-mcp__*` (любой) | ❌ нет | `query:"edt-mcp ..."` — 0 совпадений семейства |
| `mcp__1c-mcp-crud__*` | ❌ нет | `query:"1c-mcp-crud"` + `"+1c crud get_metadata"` — 0 совпадений |
| `mcp__bsl-debugger__bsl_analyze` | ✅ | прямой `select` |
| `mcp__1c-debug__debug_targets` | ✅ | прямой `select` (но `debug_connect` не пройдёт — agent не работает) |
| `mcp__bsl-semantic-search__*` | ✅ | используется в Этапе 1 fallback |
| `mcp__bsl-code-search__get_module_ast` | ✅ | используется в Этапе 1 fallback |

### 1.2 Состояние портов (хост `localhost`)

| Порт | Сервис | Состояние |
|---|---|---|
| `:8765` | EDT-MCP HTTP-bridge | **CLOSED** |
| `:1550` | 1С debug agent (`ragent.exe`) | **CLOSED** |
| `:6333` | Qdrant | LISTENING |

Команда проверки: `Test-NetConnection -ComputerName localhost -Port <port> -InformationLevel Quiet`.

### 1.3 Файловые пути из `.mcp.json`

| Путь | Сервер | Существует? |
|---|---|---|
| `D:\1C-Enterprise_Framework\src\external\1c_mcp\venv\Scripts\python.exe` | `1c-mcp-crud` (+ `-infeeda`, `-daily`, `-dev39144`) | **❌ нет** |
| `D:\` (корень) | — | ✅ есть (1.45 TB free; на нём только `hf-cache`, `hf-manual`, `va-test` — репо `1C-Enterprise_Framework` отсутствует) |
| `C:\1С-Framework\.venv\Scripts\python.exe` | большинство Python-серверов | ✅ |
| `C:\1С-Framework\tools\bsl-debug-server\mcp_debug_server.py` | `1c-debug` | ✅ |
| `C:\1С-Framework\tools\bsl-debugger\dist\index.js` | `bsl-debugger` | ✅ |

### 1.4 Git-история `.mcp.json`

```
bf887153e chore(mcp): migrate .mcp.json D:/1С-Framework -> C:/1С-Framework
```

Этот миграционный коммит (Phase 5 path migration, упомянут в [CLAUDE.md](../../CLAUDE.md)) перенёс пути **самого фреймворка** с `D:\1С-Framework\` на `C:\1С-Framework\`, но **пути для `1c-mcp-crud`** (которые указывают на отдельный репо `D:\1C-Enterprise_Framework\`) **не были тронуты**. Несколько свежих `chore: auto-save .mcp.json` подтверждают, что конфиг живой и регулярно модифицируется.

---

## 2. Покрытие 8 этапов SKILL.md vs текущая реальность

| Этап | Цель | Требуемые MCP | Работает? | Блокировка |
|---|---|---|---|---|
| 0. Preflight | Определить режим pipeline | `ToolSearch` | ✅ | — |
| 1. Подготовка | Контекст модулей | `edt-mcp` (основной) / `bsl-code-search` + `bsl-semantic-search` (fallback) | ⚠️ Только fallback | Утрачены `get_content_assist`, `get_symbol_info`, `search_in_code` по EDT-проекту |
| 2. Валидация запросов | `validate_query` + `execute_query` | `edt-mcp` + `1c-mcp-crud` | ❌ | Оба сервера отсутствуют |
| 3. BSL-изменения | `write_module_source` | `edt-mcp` | ❌ | `edt-mcp` отсутствует |
| 3R. Рефакторинг | `bsl_rename_symbol` etc. | `bsl-semantic-search` (refactor) | ⚠️ | Доступен, но не smoke-tested на этом релизе |
| 4. Статический анализ | `bsl_analyze` (static) + runtime debug | `bsl-debugger` + `1c-debug` | ⚠️ | Static OK; runtime блокирован отсутствием agent на `:1550` |
| 5. Кросс-зависимости | `find_references`, `get_project_errors` | `edt-mcp` | ❌ | Fallback через `bsl_call_graph`/`find_callers` доступен, но не описан в SKILL.md |
| 6. Тестирование на данных | `execute_query` + `execute_code` | `1c-mcp-crud` | ❌ | `1c-mcp-crud` отсутствует |
| 7. Документация | Write IMPLEMENTATION-PROGRESS.md | стандартный Write | ✅ | — |
| 8. Git commit | `git add` + `git commit` | Bash | ✅ | — |

**Доступных задач для запуска (когда среда поднимется):** 17 свежих `ANALYSIS-REPORT.md` в [`configuration/260304_GKSTCPLK-2182.../docs/`](../../configuration/260304_GKSTCPLK-2182%20Доработать%20создание%20Направление%20на%20разгрузку%20для%20заблокированных%20ТС/docs/) с зеркалом в `ИБTransportManagementDevelop/docs/`. Свежайшие: `260422_STAGE_tm_kat_01` (GKSTCPLK-2368), `260422_GKSTCPLK-2360`, `260421_GKSTCPLK-2407`.

---

## 3. План исправления

### Фаза 1 — Восстановить `1c-mcp-crud` (P0, блокер) — 1-2 часа

Цель: вернуть `mcp__1c-mcp-crud__execute_query` / `execute_code` / `get_metadata`.

1. **Уточнить актуальное расположение репо `1C-Enterprise_Framework`** (вопрос пользователю — см. раздел 5):
   - **Вариант A:** репо клонирован, но не на ожидаемом пути → перенести/симлинкнуть на `D:\1C-Enterprise_Framework\` либо обновить пути в `.mcp.json`.
   - **Вариант B:** репо удалён → клонировать заново. Структура `src/external/1c_mcp/` (proxy.py + расширение MCP_Сервер) описана в [16.5_MCP_серверы_для_1С.md](../framework%20documentation/3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.5_MCP_серверы_для_1С.md).
   - **Вариант C:** репо переехал внутрь основного фреймворка (например, `C:\1С-Framework\external\1c_mcp\`) → обновить путь в `.mcp.json`.
2. **Создать venv и поставить зависимости** (после доступности исходников):
   ```powershell
   python -m venv <repo_root>\src\external\1c_mcp\venv
   <repo_root>\src\external\1c_mcp\venv\Scripts\pip install -r <repo_root>\src\external\1c_mcp\requirements.txt
   ```
3. **Обновить 4 секции** в [.mcp.json](../../.mcp.json): `1c-mcp-crud`, `1c-mcp-crud-infeeda`, `1c-mcp-crud-daily`, `1c-mcp-crud-dev39144`. Каждая ссылается на `mcp_entrypoint.py`, отличается только `MCP_ONEC_URL` (TestDB / tm_infeeda / DAILY_TM_BAT / DEV_ATERLETSKIY_39144_MFM).
4. **Smoke-test:** перезапустить сессию Claude Code, выполнить `mcp__1c-mcp-crud__get_metadata` — должен вернуть структуру конфигурации `TestDB`.
5. **Backstop:** добавить алёрт на `1c-mcp-crud`/`edt-mcp` в [`scripts/mcp_health_monitor.py`](../../scripts/mcp_health_monitor.py) (см. [09.9](../framework%20documentation/7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.9_MCP_Health_Dashboard.md)) — запускать при `UserPromptSubmit` для команды `/implement-1c-task` (PreToolUse-подобный preflight на уровне хука).

**Критерий завершения:** `ToolSearch select:mcp__1c-mcp-crud__get_metadata` возвращает schema, не "No matching deferred tools".

---

### Фаза 2 — Восстановить `edt-mcp` (P0, блокер) — 30 мин ручной работы

Цель: вернуть `mcp__edt-mcp__list_projects` / `read_method_source` / `write_module_source` / `validate_query`.

1. **Создать `docs/framework documentation/3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.6_EDT_MCP_setup.md`** с шагами:
   - Запуск EDT IDE (с какой `workspace`).
   - Активация MCP-плагина (Settings → Tools → MCP Server).
   - Проверка порта: `Test-NetConnection -ComputerName localhost -Port 8765 -InformationLevel Quiet`.
   - Что делать, если порт занят (`Get-NetTCPConnection -LocalPort 8765`).
2. **Опционально: автозапуск EDT при `SessionStart`** — `.claude/hooks/edt-autostart.py`, который проверяет `:8765` и при необходимости запускает `edt.exe -workspace <path>`. Только если процедура старта не конфликтует с UI.
3. **Smoke-test:** `mcp__edt-mcp__list_projects` возвращает список EDT-проектов.

**Критерий завершения:** `ToolSearch select:mcp__edt-mcp__list_projects` возвращает schema.

---

### Фаза 3 — Восстановить runtime-отладку 1С (P2, не блокер) — 1 час

Цель: вернуть пошаговую отладку в Этапе 4 (опционально).

1. Поднять 1С debug agent: `ragent.exe -debug -port 1550` либо запустить «Конфигуратор» с поддержкой отладки.
2. Проверить порт: `Test-NetConnection -ComputerName localhost -Port 1550 -InformationLevel Quiet`.
3. Smoke-test: `mcp__1c-debug__debug_targets` возвращает список debug-сессий вместо пустого/error-ответа.
4. Документировать в `16.6_EDT_MCP_setup.md` или в [09.9 Dashboard](../framework%20documentation/7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.9_MCP_Health_Dashboard.md).

**Не блокер для Этапа 3** — `bsl_analyze` (статический анализатор `bsl-debugger`) работает без agent и покрывает базовый Этап 4.

---

### Фаза 4 — Усилить SKILL.md fallback'ами (P1) — 2 часа

| Этап | Текущий fallback | Предлагаемое расширение |
|---|---|---|
| 2 (validate_query) | нет | `bsl-semantic-search` для семантической проверки полей по графу метаданных + `Grep` по `.bsl` — частичная статическая проверка |
| 3 (write) | нет (hard-stop) | **Не оправдан** — `Write`/`Edit` без `get_project_errors` теряет контроль качества, лучше оставить hard-stop |
| 5 (find_references) | нет | `mcp__bsl-code-search__find_callers` + `mcp__bsl-semantic-search__bsl_call_graph` (оба в Code-only режиме доступны) |
| 6 (verify on data) | нет | Если `1c-mcp-crud` есть, но `edt-mcp` нет → режим **Read-only verify** уже описан в матрице, но без примеров |

Дополнительно: **расширить Preflight Этапа 0** — добавить TCP-проверку `:8765` и `:1550` через PowerShell-обёртку или прямую проверку из хука. Это сделает определение режима точнее (учтёт edt-bridge и debug agent отдельно от наличия MCP-tools).

**Критерий завершения:** обновлённый SKILL.md проходит smoke-test в каждом из 4 режимов матрицы (Full / Code-only / Read-only verify / Read-only research) и поведение задокументировано.

---

### Фаза 5 — Регрессионный smoke-test (P1) — 1 день

Цель: ловить «MCP отвалился — никто не заметил» автоматически.

1. **Скрипт** `scripts/smoke_test_implement_1c_task.py`:
   - Парсит [.mcp.json](../../.mcp.json), проверяет существование путей в `command:` (python.exe / node / java).
   - TCP-connect для HTTP-bridge серверов (`:8765`).
   - Запускает MCP-handshake (initialize JSON-RPC) для каждого stdio-сервера и проверяет наличие 8 ключевых tools из 4 серверов: `edt-mcp`, `1c-mcp-crud`, `bsl-debugger`, `bsl-semantic-search`.
   - Возвращает `Pipeline mode` и exit-code: `0` = Full, `1` = degraded, `2` = unusable.
2. **Cron / hook**: ✅ DONE — `.claude/hooks/implement-1c-task-preflight.py` зарегистрирован в `settings.json` после `slash-command-tracker.py`, `timeout: 30`. Содержит content-based фильтр на `/implement-1c-task` (тэг + raw + backtick-noise обход), запускает smoke-test через subprocess, парсит `--json`, при `exit_code=0/1/2` рендерит `OK/WARN/FAIL` в `systemMessage`. Не блокирует: даже при unusable пользователь может принудительно продолжить.
3. **Запись в** [`data/hook-invocations.jsonl`](../../data/hook-invocations.jsonl) с `category="preflight"` (см. Universal MCP logging в [CLAUDE.md](../../CLAUDE.md)) — для ретроспективы. Поле `outcome="mode=<Mode>;exit=<code>"`, `run_id` подхватывается через `shared.run_context.get_run_id(session_id)` (заполняется `slash-command-tracker`, который в `settings.json` стоит выше по UPS-цепочке) — даёт полную трассу `slash-run start → preflight → MCP-вызовы → Stop`. ✅ DONE.
4. **Алёрт в Stop-hook**, если smoke-test упал в течение последних 24ч и пользователь запускал `/implement-1c-task`. ✅ DONE (2026-05-08) — [`.claude/hooks/implement-1c-task-smoke-stop-alert.py`](../../.claude/hooks/implement-1c-task-smoke-stop-alert.py). Stop-hook читает tail `data/hook-invocations.jsonl` (512 KB), фильтрует за 24ч `category="preflight"` с `exit≥1` И `category="slash_run"` с `outcome="start"` для `slash:implement-1c-task`. Если оба условия выполнены — эмитит informational `systemMessage` (severity FAIL/WARN, последний outcome, ссылки на smoke-test и 16.6 EDT-MCP setup). Per-session cooldown через cookie-файл `.claude/cache/smoke-stop-alert-sessions.json` (бутит до 50 сессий). Не блокирует. Зарегистрирован в settings.json после `slash-command-tracker` (чтобы тот залогал end-события сначала) и перед enforcer'ами; timeout 5s. Smoke-tested: на чистом логе тихий, на инжектированном `exit=2`+`start` эмитит сообщение, повторный stop в той же сессии — silent.

**Критерий завершения:** `python scripts/smoke_test_implement_1c_task.py` в чистой среде показывает текущий режим pipeline и точно совпадает с тем, что Preflight Этапа 0 видит из сессии.

---

### Фаза 6 — Документация (P2) — 0.5 дня

1. Обновить [16.5_MCP_серверы_для_1С.md](../framework%20documentation/3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.5_MCP_серверы_для_1С.md): актуализировать пути после Фазы 1, убрать упоминания устаревшего MCPToolkit (см. [memory: 1c-mcp-toolkit deprecation](../../../Users/Tech.%20Boutique/.claude/projects/C--1--Framework/memory/project_1c_mcp_replacement.md)).
2. Создать `docs/framework documentation/3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.6_EDT_MCP_setup.md` (см. Фаза 2.1).
3. В [КОМАНДЫ_CLAUDE_CODE.md](../framework%20documentation/КОМАНДЫ_CLAUDE_CODE.md) рядом с `/implement-1c-task` добавить блок «Требования к среде» со ссылкой на этот roadmap и smoke-test скрипт.
4. Добавить запись в `MEMORY.md` (категория `feedback`): «путь `D:\1C-Enterprise_Framework` в `.mcp.json` устарел; при правках конфига сверяться с этим roadmap» — чтобы при следующих авто-правках не залить старое значение из истории.

---

## 4. Чеклист регрессии (после Фазы 1+2)

Запустить вручную после восстановления `edt-mcp` и `1c-mcp-crud`:

- [ ] `ToolSearch select:mcp__edt-mcp__list_projects` → возвращает schema
- [ ] `ToolSearch select:mcp__1c-mcp-crud__get_metadata` → возвращает schema
- [ ] `mcp__edt-mcp__list_projects` → реальный список проектов EDT
- [ ] `mcp__1c-mcp-crud__get_metadata` → структура конфигурации `TestDB`
- [ ] `Test-NetConnection -ComputerName localhost -Port 8765 -InformationLevel Quiet` → `True`
- [ ] `python scripts/mcp_health_monitor.py .mcp.json` → 0 серверов в статусе ERR/TMO/DIS из критичных (`edt-mcp`, `1c-mcp-crud`, `bsl-debugger`, `bsl-semantic-search`)
- [ ] `/implement-1c-task <ANALYSIS-REPORT path>` в чистой сессии: Preflight выбирает режим **Full**
- [ ] Pipeline доходит до Этапа 8 на одной из 17 готовых задач из `configuration/260304_GKSTCPLK-2182.../docs/`

---

## 5. Открытые вопросы

1. **Где сейчас живут исходники `1c_mcp`?** Нужен ответ от пользователя — без него Фаза 1 не может стартовать. Возможные варианты A/B/C перечислены в Фазе 1.1.
2. **Как стандартизировать запуск EDT для команды разработчиков?** Документация (Фаза 2.1) или auto-start хук (Фаза 2.2)?
3. **Нужна ли поддержка одновременной работы с 4 базами** (`TestDB` / `tm_infeeda` / `DAILY_TM_BAT` / `DEV_ATERLETSKIY_39144_MFM`)? ✅ RESOLVED (2026-05-08) — **N/A, multi-base support отклонён**. Корректировка premise: на момент написания roadmap'а (2026-05-05) предполагалось наличие 4 mirror-серверов в `.mcp.json`. После path-миграции (commit `bf887153e`) и memory `feedback_mcp_json_paths.md` mirror-конфиги были признаны устаревшими — текущий `.mcp.json` содержит **один** `1c-mcp-crud` сервер с `MCP_ONEC_URL=http://localhost/transport` (TestDB). Решение: pipeline остаётся однобазовым (TestDB через single `1c-mcp-crud`), переключение на другую базу — ручная подмена `MCP_ONEC_URL` в `.mcp.json` + restart Claude Code сессии. Расширение SKILL.md Этапа 6 на multi-base — не требуется. Если в будущем появится операционная необходимость одновременно работать с двумя базами в одной сессии — реактивировать как новый roadmap с обоснованием use case (например, сравнение поведения staging vs production).

---

## 6. Связь с другими дорожными картами

- [260331_ROADMAP_MCP_IMPROVEMENTS.md](260331_ROADMAP_MCP_IMPROVEMENTS.md) — фоновое улучшение MCP-экосистемы (Фазы 5-12, DONE); этот документ дополняет фазами «health & recovery».
- [ROADMAP_MCP_1C_INTEGRATION.md](ROADMAP_MCP_1C_INTEGRATION.md) — базовая интеграция (Фазы 1-4).
- [260414_Serena Audit углублённый анализ эффективности.md](260414_Serena%20Audit%20углублённый%20анализ%20эффективности.md) — обоснование откатов в SKILL.md v2.1.1 (Этап 0 «Активация Serena» был удалён).

---

**Статус документа:** ✅ DONE (2026-05-07). См. таблицу Status в шапке. Открытые вопросы §5.1 (расположение исходников `1c_mcp`) разрешены — Variant C (внутри основного фреймворка, `C:\1С-Framework\external\1c_mcp\`).

---

## 7. Validation end-to-end (2026-05-07)

После закрытия всех фаз pipeline прогнан на реальной задаче в той же сессии — впервые с момента smoke-test'а 2026-05-05, который и инициировал этот roadmap.

**Кейс:** `GKSTCPLK-2182-A` — заполнение `гкс_ДатаНачалаАнализа`/`гкс_ДатаОкончанияАнализа` в `КомандаЗаполнитьСредневзвешеннымиНаСервере` АРМ «Композитные пробы», чтобы регистр `гкс_ФактическиеПоказателиКачества` получал движения для назначения `ПриёмкаКомпозит`. ANALYSIS-REPORT: [`configuration/260304_GKSTCPLK-2182.../docs/260507_…/ANALYSIS-REPORT.md`](../../configuration/260304_GKSTCPLK-2182%20Доработать%20создание%20Направление%20на%20разгрузку%20для%20заблокированных%20ТС/docs/260507_Фактичекие%20показатели%20качества%20приемка%20композит/ANALYSIS-REPORT.md). Прогресс: [`IMPLEMENTATION-PROGRESS.md`](../../configuration/260304_GKSTCPLK-2182%20Доработать%20создание%20Направление%20на%20разгрузку%20для%20заблокированных%20ТС/docs/260507_Фактичекие%20показатели%20качества%20приемка%20композит/IMPLEMENTATION-PROGRESS.md).

| Stage | Статус | Доказательство |
|---|---|---|
| 0 Preflight | ✅ Full | `smoke_test_implement_1c_task.py` exit 0; все 4 критичных MCP handshake'ятся; preflight-hook `implement-1c-task-preflight.py` проверен real chain-тестом (slash-tracker → preflight, `run_id=92e0c05c…88b0a` идентичен в обоих лог-записях) |
| 1 Подготовка | ✅ | EDT path resolution: ANALYSIS-REPORT'овский Designer-style `Documents/.../Ext/ManagerModule.bsl` flatten'ится в EDT до `DataProcessors/.../Forms/Форма/Module.bsl` — обнаружено через `list_modules` (fallback от `read_method_source` File-not-found) |
| 2 Validate queries | ⏭ SKIP | в правке нет SQL |
| 3 BSL write | ✅ | `mcp__edt-mcp__write_module_source` mode=searchReplace, syntax check passed (990→1004 строки), `get_project_errors(objects=[DataProcessor.гкс_АРМКомпозитныеПробы], severity=ERRORS)` → 0 |
| 4 Static analyze | ✅ graceful | `bsl_analyze(file=...)` падает на line 355 (известный OneScript false-positive на production BSL — задокументировано в SKILL.md v2.5.0); `bsl_analyze(source=<body>)` PASS, 0 ошибок, 1 процедура распознана с annotation `&НаСервере` |
| 5 Cross-deps | ✅ | `find_references` → 37 references, все валидные; `get_project_errors` whole project → 2 pre-existing baseline ошибки в other objects (`Справочник.гкс_ВходящиеДанныеWarehouse`, `ОбщийМодуль.гкс_ИнтеграцияСКверионКлиент`), не связаны с правкой |
| 6 Live verify | ✅ partial | `update_database(applicationId=3a3cfb6b-..., fullUpdate=false, autoRestructure=true)` → `INCREMENTAL_UPDATE_REQUIRED → UPDATED`; baseline через `execute_query` точно совпал с ANALYSIS-REPORT §1.2 (72/53/18/0/67); sanity-симуляция через `execute_code` без записи на ЛА `ЕВУТ-000009`: даты до — пусты `01.01.0001`, после — обе `07.05.2026 19:26:09`. T1 через АРМ — за пользователем (Rule 7) |
| 7 Documentation | ✅ | IMPLEMENTATION-PROGRESS.md, 179 строк, полная stage-trace |
| 8 Git commit | ✅ | 4 коммита в 3 git-репозиториях: inner submodule `Конфигурация` `d3db501` (BSL), main repo `71a9ba481` (gitlink Конфигурация), docs submodule `c6616817` (PROGRESS), main repo `907b89ce1` (gitlink configuration/260304). **Discovery:** `ИБTransportManagementDevelop/` — обычная подпапка main repo (не отдельный standalone repo, как пишет SKILL.md v2.5.0 §Этап 8); фактическая структура — main tracks 2 submodule напрямую: `configuration/<TaskFolder>` и `ИБTransportManagementDevelop/Конфигурация`. **Resolved in SKILL.md v2.6.0 + v2.6.1 (2026-05-07):** §Этап 8 переписан под точную 3-уровневую структуру (level 2 — обычная директория без `.git/`, level 3 — submodule с gitlink mode 160000); удалён шаг «commit gitlink в middle repo» из v2.5.0; добавлен diagnostic-блок с проверкой `git ls-files --stage` для обоих gitlink'ов и detection level-2 аномалии (`test -d <dir>/.git`) |

**Известные ограничения, обнаруженные в ходе e2e** (все резолвлены в SKILL.md):
- `1c-mcp-crud:execute_query` падает на сериализации перечислений с прямой выборкой `Ссылка` — обходим через `ПРЕДСТАВЛЕНИЕ()` (SKILL.md v2.5.0 §«Известные ограничения 1c-mcp-crud» → Ограничение 2).
- `1c-mcp-crud:execute_code` запрещает `Возврат` вне процедуры/функции — переписывать через `Если/Иначе` с присваиванием `Результат` в каждой ветке (SKILL.md **v2.6.2** (2026-05-08) §Ограничение 3).
- ANALYSIS-REPORT'ы используют Designer-style пути (`.../Ext/ManagerModule.bsl`), EDT их flatten'ит — Stage 1 имеет явный fallback `list_modules` (через `objectName=...`) когда `read_method_source` возвращает File-not-found (SKILL.md v2.6.0 §Этап 1 → Path-fallback).

**Что ушло на пользователя:**
- T1 happy-path в АРМ (Rule 7).
- Backfill 53 уже-Выполнен ЛА с пустыми датами (open question §6.1 ANALYSIS-REPORT'а).
- Реальный номер задачи (§6.3) — закоммичено с условным `GKSTCPLK-2182-A`.
- Push: локальные коммиты не запушены, перед push — ротация пароля БД из утечки `fce77bbca` (см. §«Soft fix» в commit `ce75d2f0f`).
