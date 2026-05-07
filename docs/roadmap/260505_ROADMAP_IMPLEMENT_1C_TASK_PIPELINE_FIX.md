# Дорожная карта: восстановление работоспособности `/implement-1c-task`

> **Дата:** 2026-05-05 (создана) → **2026-05-07 (DONE)**
> **Триггер:** smoke-test реального выполнения команды `/implement-1c-task` — pipeline корректно остановился на Этапе 0 (Preflight v2.3.0).
> **Скилл:** [implement-1c-task/SKILL.md](../../.claude/skills/implement-1c-task/SKILL.md) (**v2.4.0** — TCP-probe + Stage 5 fallback)
> **Связанные документы:** [16.5_MCP_серверы_для_1С.md](../framework%20documentation/16_ПОДКЛЮЧЕНИЕ_1С/16.5_MCP_серверы_для_1С.md), [16.6_EDT_MCP_setup.md](../framework%20documentation/16_ПОДКЛЮЧЕНИЕ_1С/16.6_EDT_MCP_setup.md) (новый), [09.9_MCP_Health_Dashboard.md](../framework%20documentation/09_АДМИНИСТРИРОВАНИЕ/09.9_MCP_Health_Dashboard.md), [260331_ROADMAP_MCP_IMPROVEMENTS.md](260331_ROADMAP_MCP_IMPROVEMENTS.md)

## Status (2026-05-07)

| Фаза | Статус | Артефакт |
|---|---|---|
| Phase 1: восстановить `1c-mcp-crud` | ✅ DONE | Путь мигрирован на `C:\1С-Framework\external\1c_mcp\` (commit `bf887153e`); `MCP_ONEC_PASSWORD` заполнен; mirror-конфиги признаны устаревшими и не добавлены |
| Phase 2: восстановить `edt-mcp` | ✅ DONE | EDT IDE поднята пользователем, порт `:8765` LISTENING; новый раздел [16.6_EDT_MCP_setup.md](../framework%20documentation/16_ПОДКЛЮЧЕНИЕ_1С/16.6_EDT_MCP_setup.md) |
| Phase 3: runtime debug 1С (`:1550`) | 🟡 DOCUMENTED | Операционка остаётся за пользователем; пошаговая инструкция в 16.6 §«1С debug agent». Не блокер — `bsl_analyze` покрывает Этап 4 |
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
   - **Вариант B:** репо удалён → клонировать заново. Структура `src/external/1c_mcp/` (proxy.py + расширение MCP_Сервер) описана в [16.5_MCP_серверы_для_1С.md](../framework%20documentation/16_ПОДКЛЮЧЕНИЕ_1С/16.5_MCP_серверы_для_1С.md).
   - **Вариант C:** репо переехал внутрь основного фреймворка (например, `C:\1С-Framework\external\1c_mcp\`) → обновить путь в `.mcp.json`.
2. **Создать venv и поставить зависимости** (после доступности исходников):
   ```powershell
   python -m venv <repo_root>\src\external\1c_mcp\venv
   <repo_root>\src\external\1c_mcp\venv\Scripts\pip install -r <repo_root>\src\external\1c_mcp\requirements.txt
   ```
3. **Обновить 4 секции** в [.mcp.json](../../.mcp.json): `1c-mcp-crud`, `1c-mcp-crud-infeeda`, `1c-mcp-crud-daily`, `1c-mcp-crud-dev39144`. Каждая ссылается на `mcp_entrypoint.py`, отличается только `MCP_ONEC_URL` (TestDB / tm_infeeda / DAILY_TM_BAT / DEV_ATERLETSKIY_39144_MFM).
4. **Smoke-test:** перезапустить сессию Claude Code, выполнить `mcp__1c-mcp-crud__get_metadata` — должен вернуть структуру конфигурации `TestDB`.
5. **Backstop:** добавить алёрт на `1c-mcp-crud`/`edt-mcp` в [`scripts/mcp_health_monitor.py`](../../scripts/mcp_health_monitor.py) (см. [09.9](../framework%20documentation/09_АДМИНИСТРИРОВАНИЕ/09.9_MCP_Health_Dashboard.md)) — запускать при `UserPromptSubmit` для команды `/implement-1c-task` (PreToolUse-подобный preflight на уровне хука).

**Критерий завершения:** `ToolSearch select:mcp__1c-mcp-crud__get_metadata` возвращает schema, не "No matching deferred tools".

---

### Фаза 2 — Восстановить `edt-mcp` (P0, блокер) — 30 мин ручной работы

Цель: вернуть `mcp__edt-mcp__list_projects` / `read_method_source` / `write_module_source` / `validate_query`.

1. **Создать `docs/framework documentation/16_ПОДКЛЮЧЕНИЕ_1С/16.6_EDT_MCP_setup.md`** с шагами:
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
4. Документировать в `16.6_EDT_MCP_setup.md` или в [09.9 Dashboard](../framework%20documentation/09_АДМИНИСТРИРОВАНИЕ/09.9_MCP_Health_Dashboard.md).

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
3. **Запись в** [`data/hook-invocations.jsonl`](../../data/hook-invocations.jsonl) с `category="preflight"` (см. Universal MCP logging в [CLAUDE.md](../../CLAUDE.md)) — для ретроспективы.
4. **Алёрт в Stop-hook**, если smoke-test упал в течение последних 24ч и пользователь запускал `/implement-1c-task`.

**Критерий завершения:** `python scripts/smoke_test_implement_1c_task.py` в чистой среде показывает текущий режим pipeline и точно совпадает с тем, что Preflight Этапа 0 видит из сессии.

---

### Фаза 6 — Документация (P2) — 0.5 дня

1. Обновить [16.5_MCP_серверы_для_1С.md](../framework%20documentation/16_ПОДКЛЮЧЕНИЕ_1С/16.5_MCP_серверы_для_1С.md): актуализировать пути после Фазы 1, убрать упоминания устаревшего MCPToolkit (см. [memory: 1c-mcp-toolkit deprecation](../../../Users/Tech.%20Boutique/.claude/projects/C--1--Framework/memory/project_1c_mcp_replacement.md)).
2. Создать `docs/framework documentation/16_ПОДКЛЮЧЕНИЕ_1С/16.6_EDT_MCP_setup.md` (см. Фаза 2.1).
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
3. **Нужна ли поддержка одновременной работы с 4 базами** (`TestDB` / `tm_infeeda` / `DAILY_TM_BAT` / `DEV_ATERLETSKIY_39144_MFM`)? Сейчас 4 отдельных MCP-сервера, но `/implement-1c-task` использует только базовый `1c-mcp-crud` (TestDB). Если нужно — добавить в Этап 6 явный выбор базы.

---

## 6. Связь с другими дорожными картами

- [260331_ROADMAP_MCP_IMPROVEMENTS.md](260331_ROADMAP_MCP_IMPROVEMENTS.md) — фоновое улучшение MCP-экосистемы (Фазы 5-12, DONE); этот документ дополняет фазами «health & recovery».
- [ROADMAP_MCP_1C_INTEGRATION.md](ROADMAP_MCP_1C_INTEGRATION.md) — базовая интеграция (Фазы 1-4).
- [260414_Serena Audit углублённый анализ эффективности.md](260414_Serena%20Audit%20углублённый%20анализ%20эффективности.md) — обоснование откатов в SKILL.md v2.1.1 (Этап 0 «Активация Serena» был удалён).

---

**Статус документа:** ✅ DONE (2026-05-07). См. таблицу Status в шапке. Открытые вопросы §5.1 (расположение исходников `1c_mcp`) разрешены — Variant C (внутри основного фреймворка, `C:\1С-Framework\external\1c_mcp\`).
