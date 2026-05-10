# Roadmap — Интеграция `1c-debug-hmr` в команды `/analyze-1c-task` и `/implement-1c-task`

**Дата:** 2026-05-10
**Статус:** 📋 Planning — анализ выполнен, исполнение pending approval
**Приоритет:** Высокий — закрывает фундаментальный gap «static-only verification» в обеих командах
**Связано:**
- [`260508_ROADMAP_BSL_DEBUG_WRAPPER_POST_BP_HANDSHAKE.md`](260508_ROADMAP_BSL_DEBUG_WRAPPER_POST_BP_HANDSHAKE.md) — родительский roadmap debug-wrapper'а (P1-P3 closed)
- [`260505_ROADMAP_IMPLEMENT_1C_TASK_PIPELINE_FIX.md`](260505_ROADMAP_IMPLEMENT_1C_TASK_PIPELINE_FIX.md) — preflight-hook для `/implement-1c-task`
- [`docs/framework documentation/36_AUTONOMOUS_DEBUG_CONTROL/`](../framework%20documentation/36_AUTONOMOUS_DEBUG_CONTROL/) — Level 1/2/3 + 36.7 HMR wrapper
- [`.claude/skills/1c-debug-hmr/SKILL.md`](../../.claude/skills/1c-debug-hmr/SKILL.md)

---

## 0. Executive Summary

`1c-debug-hmr` — это MCP-сервер для live BSL-отладки через 1С RDBG протокол (commit `1872dff` от 2026-05-10), wrapped в HMR subprocess для prod-grade reload без потери session к dbgs. 13 tools покрывают connect/BP/inspection/step/eval. После сегодняшних фиксов (unified `ping()` dispatch + persistent `.active.json` + cache-first error envelope) wrapper готов к интеграции в производственные slash-команды.

**Цель**: добавить `1c-debug-hmr` как **обязательный компонент verification + опциональный компонент analysis** в существующие команды `/analyze-1c-task` и `/implement-1c-task` без слома backward-compat.

**Результат**:
- Реализация фиксов **доказывается** live BP-trace'ом, а не только static-анализом
- Сложные runtime-сценарии (обработка проведения, регламенты, HTTP-сервисы с условной логикой) **читаемы** без guessing
- Регрессии **детектируются автоматически** через `debug_session_diff` против baseline
- Среда **проверяется за <1с** через `debug_health_check` вместо 5-7 manual probes

**Объём**: 3 фазы по ~3-5ч каждая, ~10-15ч суммарно. Основной риск — **environment dependency** (RDBG требует dbgs.exe запущенным с `-debug -http` + dev-уровень доступа), что покрыто Solution C (thin client `/Debug`) когда force-recycle нежелателен.

---

## 1. Current State

### 1.1 `/analyze-1c-task` v5-фазный pipeline

| Фаза | Что делает | Источник истины |
|---|---|---|
| 1. Требования | Парсит ТЗ | static (file read) |
| 2. Объекты | Список метаданных + структура | `bsl-semantic-search`, `1c-mcp-crud.get_metadata` |
| 3. Алгоритм | Reverse-engineer существующего поведения | static reading кода |
| 4. План | Точки модификации + diff-карты | static |
| 5. Верификация | Чек-лист (в ANALYSIS-REPORT) | static |

**Gap**: фазы 2-3 строятся на чтении кода. Когда код **сильно условен** (вычислительная развилка по типу контрагента, режиму проведения, контексту вызова), static reading даёт неточный «верхнеуровневый» алгоритм. Нужен runtime trace.

### 1.2 `/implement-1c-task` v2.3 (8 этапов)

| Этап | Что делает | Tools |
|---|---|---|
| 0. Preflight | Probes доступности MCP-серверов, выбор pipeline-mode | manual probes |
| 1. Подготовка | Чтение кода / формирование плана | EDT-MCP, `bsl-semantic-search` (fallback) |
| 2. Валидация запросов | `validate_query` ДО записи | `1c-mcp-crud` |
| 3. BSL | `write_module_source` | EDT-MCP |
| 4. Статанализ | OneScript линтер | `bsl-debug-server.bsl_analyze` (note: **НЕ** live RDBG) |
| 5. Верификация | `get_project_errors` + `execute_query` | EDT-MCP, `1c-mcp-crud` |
| 6. Тестирование | VA BDD UI-тесты | `va-bdd-testing` |
| 7. Документация | IMPLEMENTATION-PROGRESS.md | docs |
| 8. Git | commit | git |

**Gaps**:
1. **Этап 0** делает manual probes — не использует готовый `debug_health_check`
2. **Этап 5** проверяет «нет ошибок компиляции» + «query даёт ожидаемый результат», но **не доказывает что новый код вообще исполнялся** по ожидаемому пути. Code path coverage отсутствует.
3. Между **Этап 5 и 6** нет промежуточного «server-side BSL inspection». VA BDD тестирует UI; когда тест падает, разработчик возвращается к manual breakpoint workflow вне pipeline.
4. **Регрессия** ловится через accidentally failing test, не через structured метрики.

### 1.3 Что уже есть на 2026-05-10

- ✅ `1c-debug-hmr` MCP-сервер (`.mcp.json`) с 13 tools, schema стабильна
- ✅ HMR wrapper, persistent `.active.json`, unified `ping()` dispatch — фиксы залиты в submodule `1872dff`, parent `e74e2fcbd`
- ✅ Skill `1c-debug-hmr` (29 keywords, 14 weighted, 10 utterances) зарегистрирован в router
- ✅ Документация: глава 36.7 + обновлённый CLAUDE.md
- ✅ Level 1 (`debug_health_check`), Level 2 (`autonomous_debug_test.py`), Level 3 (`debug_session_summary` / `_diff`) — задокументированы в 36.2-36.4

---

## 2. Gap Analysis & Integration Surface

### 2.1 Что добавляется в `/analyze-1c-task`

| Где | Что добавить | Эффект |
|---|---|---|
| Фаза 2.5 (новая, опц.) | **Runtime trace mode**: при флаге `--trace` устанавливаем BP на entry-point подозрительной процедуры → триггерим через `1c-mcp-crud.execute_code` → читаем `debug_stack_trace` + `debug_variables` → пишем «runtime call graph» в ANALYSIS-REPORT | Точный actual call path вместо static-угадывания |
| Фаза 5 (Верификация) | Чек-лист пункт: «Для критических точек модификации: BP-сценарий — set BP → trigger → expected stop event достижим» | Acceptance criterion проверяем ДО реализации |

### 2.2 Что добавляется в `/implement-1c-task`

| Где | Что добавить | Эффект |
|---|---|---|
| Этап 0 Preflight | **Заменить** manual probes на `debug_health_check(mode="probe")`. На warn'ы offer `mode="prepare"` (whitelist actions: kill-stale-rphosts, restart-ragent) | <1с структурированный health-check + recommended_workflow |
| Этап 5 Верификация | **Live BP verification step** (новый, обязательный для `[ADDED]`/`[MODIFIED]` точек): set BP на изменённой строке → execute_code триггер → assert `debug_stack_trace` показывает stop на правильной строке → `debug_variables` валидирует state | Доказательство что новый код реально исполняется по ожидаемому пути |
| Этап 5 Верификация | **Regression baseline diff** (новый, опц.): если есть `prev_session_id` (из git-attached metadata) — `debug_session_diff(prev_session_id)` → assert verdict ≠ REGRESSION | Автоматический catch-all для метрик (BP fire counts, eval failures, UI+ retries) |
| Этап 6 Тестирование | **Fallback debug** (опц.): когда VA BDD тест падает, attach `1c-debug-hmr` → repeat trigger → catch offending BSL line → пишем server-side trace в IMPLEMENTATION-PROGRESS | Сокращение MTTR для UI-тестов с server-side root cause |
| Этап 7 Документация | В IMPLEMENTATION-PROGRESS.md секция «Debug session»: вывод `debug_session_summary(format="markdown")` | Audit trail в PR |

### 2.3 Что добавляется в инфраструктуру (cross-cut)

- **Hook-уровень**: расширение `implement-1c-task-preflight.py` — добавить `debug_health_check` probe в smoke_test_implement_1c_task.py
- **Skills-уровень**: skill `analyze-1c-task-v2` и skill-bundle `implement-1c-task` пополняются inline-инструкциями про BP-workflow (ссылки на skill `1c-debug-hmr`)
- **Слот в `.mcp.json`**: уже есть и `1c-debug` (plain), и `1c-debug-hmr` (HMR). Команды используют `1c-debug-hmr` по умолчанию (быстрее iteration). На CI можно переключить env-переменной на plain `1c-debug`.

---

## 3. Phase 1 — `/implement-1c-task` Preflight + Verification (5-7ч)

**Цель**: добавить debug-hmr в Этап 0 (preflight) и Этап 5 (verification) — высокая ROI, минимум блокеров.

### 3.1 Расширить Этап 0 Preflight (1-2ч)

**Subtask 1.1.1** — обновить `.claude/skills/implement-1c-task/SKILL.md`:
- Этап 0 sub-step «Debug environment health»: вызвать `mcp__1c-debug-hmr__debug_health_check(mode="probe")`. Парсить ответ:
  - `ready: true` → continue
  - `ready: false` + `auto_prepare_available[]` → offer prepare-actions с user prompt
  - `ready: false` + manual fix only → block pipeline, surface `recommended_workflow` token
- Pipeline-mode selection теперь учитывает `1c-debug-hmr` доступность:
  - `Full` (все 4 MCP-сервера) — debug-hmr ready
  - `Code-only` — debug-hmr unavailable, ОК (verification fallback к static)
  - `Read-only verify` — debug-hmr ready но edt-mcp нет (degraded write path)

**Subtask 1.1.2** — обновить `scripts/smoke_test_implement_1c_task.py`:
- Добавить probe `debug_health_check`, парсить JSON, в `--json` режиме включать `mcp_health` блок
- Не блокирующее: при недоступности — `mode="Code-only verification"` без debug-step

**Subtask 1.1.3** — обновить `.claude/hooks/implement-1c-task-preflight.py`:
- В systemMessage перед запуском pipeline добавлять строку про `debug-hmr` доступность из smoke-test'а
- Логирование в `data/hook-invocations.jsonl` с `category="preflight"` уже есть, добавить поле `debug_hmr_ready: bool`

**Acceptance**:
- ✅ `python scripts/smoke_test_implement_1c_task.py --json` возвращает `mcp_health.debug_hmr` блок
- ✅ `/implement-1c-task` preflight выводит «Debug environment: ready / not-ready» в systemMessage
- ✅ Existing smoke-tests (preflight + smoke-stop alert) — все проходят без регрессий

### 3.2 Live BP verification в Этап 5 (2-3ч)

**Subtask 1.2.1** — обновить `.claude/skills/implement-1c-task/SKILL.md`:
- Этап 5 sub-step «Live BP verification» (для каждой `[ADDED]`/`[MODIFIED]` точки из ANALYSIS-REPORT):
  1. `mcp__1c-debug-hmr__debug_connect(infobase_alias=...)` — если ещё не connected
  2. `mcp__1c-debug-hmr__debug_set_breakpoint(object_id=<UUID>, line=<MODIFIED_LINE>, module_type=<TYPE>)` — propertyID auto-resolves
  3. `mcp__1c-debug-hmr__debug_get_breakpoints` — verify BP в client cache
  4. Триггер: `mcp__1c-mcp-crud__execute_code` с минимальным BSL который вызывает изменённую процедуру (либо HTTP-trigger через `mcp__1c-mcp-crud__execute_query` для HTTP-services)
  5. `mcp__1c-debug-hmr__debug_ping` — wait for callStackFormed (max 3 ping iterations)
  6. Если stopped: `mcp__1c-debug-hmr__debug_stack_trace` → assert `lineNo` совпадает с MODIFIED_LINE
  7. Опционально: `mcp__1c-debug-hmr__debug_variables` для assertion state'а
  8. `mcp__1c-debug-hmr__debug_step("Continue")` — release rphost
- Если BP не сработал: fallback к `debug_break_on_next` + retry; если всё ещё нет — `force_recycle_rphost=True` (Solution A)
- Этап 5 success criterion: ВСЕ MODIFIED точки покрыты BP-trace'ом, иначе блокируем переход на Этап 6 с error в IMPLEMENTATION-PROGRESS

**Subtask 1.2.2** — обновить `.claude/commands/implement-1c-task.md`:
- В секцию «Обязательные циклы» добавить: «**После записи кода с [MODIFIED]:** `set_breakpoint` → trigger → `stack_trace` → assert lineNo correct»
- В секцию «Результат» добавить: «BP-trace для каждой MODIFIED точки в IMPLEMENTATION-PROGRESS.md»

**Subtask 1.2.3** — добавить smoke-тест `scripts/test_implement_1c_task_bp_verification.py`:
- Mock-based: подменяет `1c-debug-hmr` MCP responses, проверяет что pipeline корректно вызывает все 8 шагов в правильном порядке
- 5 тестов: happy path, BP timeout, force_recycle fallback, stack_trace lineNo mismatch, debug-hmr unavailable

**Acceptance**:
- ✅ Skill инструкции `implement-1c-task` содержат BP-verification step
- ✅ Smoke-тест `test_implement_1c_task_bp_verification.py` 5/5 PASS
- ✅ Live test на ИБTransportManagementDevelop: реализация trivial fix → BP-verification step ловит lineNo, IMPLEMENTATION-PROGRESS содержит блок BP trace

### 3.3 Regression baseline через session_diff (1-2ч)

**Subtask 1.3.1** — git-attached session metadata:
- Convention: `IMPLEMENTATION-PROGRESS.md` имеет в footer строку `<!-- debug_session_id: <UUID> -->` с session_id последнего успешного прогона
- При новом /implement: skill читает prev session_id из baseline file (если есть), вызывает `debug_session_diff(prev_session_id, curr_session_id=<current>)`
- Assert verdict ∈ {NO_REGRESSION, IMPROVEMENT}, иначе — block с diff-блоком в output

**Subtask 1.3.2** — обновить skill `implement-1c-task`:
- Этап 5 sub-step «Regression diff» (опц., только если есть baseline session_id)
- В Этап 7 «Документация» — записать новый session_id в IMPLEMENTATION-PROGRESS.md footer

**Acceptance**:
- ✅ Если baseline есть — diff-проверка работает, выводит markdown-таблицу метрик
- ✅ Если baseline нет — pipeline корректно skip'ает с warning «no baseline, first run»

---

## 4. Phase 2 — `/analyze-1c-task` Runtime Trace mode (3-4ч)

**Цель**: опциональная фаза 2.5 — runtime tracing для сложных алгоритмов.

### 4.1 Новая фаза 2.5 «Runtime Trace» (2-3ч)

**Subtask 2.1.1** — обновить `.claude/skills/analyze-1c-task-v2/SKILL.md`:
- Добавить **опциональную фазу 2.5** (между «Объекты» и «Алгоритм»):
  - Триггер: пользователь добавил флаг `--trace` ИЛИ skill самостоятельно решил («алгоритм имеет ≥3 ветвлений по runtime значениям»)
  - Шаги:
    1. `debug_connect` (если ещё не attached)
    2. Identify entry-point: модуль + строка из metadata
    3. `debug_set_breakpoint` на entry
    4. Trigger через `execute_code` (минимальный harness)
    5. `debug_ping` → callStackFormed
    6. Iteratively: `debug_stack_trace` + `debug_variables(stack_level=N)` для каждого frame
    7. `debug_step("Step")` через критические ветвления, capture state на каждой остановке
    8. `debug_step("Continue")` для очистки
  - Output: новая секция в ANALYSIS-REPORT.md «3.x Runtime trace» — actual call graph + variable snapshots vs static prediction

**Subtask 2.1.2** — обновить `.claude/commands/analyze-1c-task.md`:
- В `allowed-tools` добавить `mcp__1c-debug-hmr__*` (все 13 tools)
- В секцию «ВАЖНО» добавить: «Для сложных runtime-алгоритмов используй опциональную фазу 2.5 Runtime Trace через `1c-debug-hmr` (см. skill для протокола)»

### 4.2 ANALYSIS-REPORT шаблон (0.5-1ч)

**Subtask 2.2.1** — обновить шаблон ANALYSIS-REPORT (если такой есть в skill):
- Добавить секцию «3.x Runtime Trace (опц.)» со структурой:
  - **Entry**: модуль:строка, BP UUID
  - **Stack** (jq-compatible JSON для post-processing)
  - **Variables snapshot**: таблица `name: value@stack_level`
  - **Branch evaluation**: какие условия истинны на runtime, vs предположение из static анализа
  - **Discrepancies**: список где static и runtime разошлись (важно для assumptions revision)

**Acceptance**:
- ✅ Runtime trace section появляется в ANALYSIS-REPORT при `--trace` флаге
- ✅ Discrepancies section ненулевая когда runtime отличается от static (тестовый кейс: ветвление по `Пользователи.ТекущийПользователь()` которое static reading не покажет)
- ✅ Без `--trace` фаза skipped, время analysis не растёт

---

## 5. Phase 3 — Cross-command consistency + автотесты (2-3ч)

### 5.1 Унификация preflight (1ч)

**Subtask 3.1.1** — `.claude/hooks/`:
- Создать shared helper `.claude/hooks/shared/debug_hmr_health.py` — функция `probe_debug_hmr_ready() -> dict` (вызов `debug_health_check` через subprocess MCP-stdio или прямой импорт)
- Использовать в обоих preflight-hook'ах (`implement-1c-task-preflight.py` уже есть; для `/analyze-1c-task` создать `analyze-1c-task-preflight.py` по той же модели)

### 5.2 Обновить документацию (0.5-1ч)

**Subtask 3.2.1** — `КОМАНДЫ_CLAUDE_CODE.md` line 19-20: расширить описание `/analyze-1c-task` и `/implement-1c-task` упоминанием `1c-debug-hmr` integration

**Subtask 3.2.2** — `17.5_КОМАНДЫ_ПАЙПЛАЙНА.md` (если есть): добавить debug-hmr step'ы в pipeline-диаграмму

**Subtask 3.2.3** — `36.5_Workflows.md`: добавить новый workflow «Bug fix via /implement-1c-task с BP-verification» — пошаговый чеклист использующий новые этапы

### 5.3 Cross-skill ссылки (0.5-1ч)

**Subtask 3.3.1** — обновить `1c-debug-hmr/SKILL.md`:
- Секция «Связанные скиллы» — добавить prominent ссылки на `analyze-1c-task-v2` и `implement-1c-task` с фразой «used by /analyze-1c-task --trace and /implement-1c-task Этап 5 BP-verification»
- Шаблон 5 (новый): «BP-verification в /implement-1c-task pipeline» — копия из skill `implement-1c-task`

**Subtask 3.3.2** — обновить `analyze-1c-task-v2/SKILL.md`:
- Phase 2.5 как отдельный referenced template; ссылка на `1c-debug-hmr` для tool-protocol

**Subtask 3.3.3** — обновить `implement-1c-task/SKILL.md`:
- Этап 5.x BP-verification как отдельный referenced template
- В Этап 0 — ссылка на `debug_health_check` shared helper

### 5.4 Регрессионные тесты (1ч)

**Subtask 3.4.1** — `tools/bsl-debug-server/tests/`:
- Smoke `test_implement_1c_task_bp_verification.py` — уже добавлен в Phase 1.2
- Новый `test_analyze_1c_task_runtime_trace.py` — mock-based проверка fазы 2.5

**Subtask 3.4.2** — обновить `pyproject.toml` test discovery (если нужно)

**Subtask 3.4.3** — добавить в `.pre-commit-config.yaml` smoke-check для slash-commands integration (опц., если pattern-based проверка будет полезна)

---

## 6. Acceptance Criteria (Phase 1+2+3 closure)

| Критерий | Метод проверки |
|---|---|
| `/analyze-1c-task --trace` создаёт ANALYSIS-REPORT с секцией Runtime Trace | Live test на реальной задаче с условной логикой |
| Discrepancies между static и runtime в analysis surface'ятся явно | Manual review секции |
| `/implement-1c-task` preflight выводит «Debug environment: ready/not-ready» | smoke-test JSON output |
| `/implement-1c-task` Этап 5 ловит missing-execution (когда новый код **не вызывается**) | Сценарий: ANALYSIS говорит изменить процедуру А, реализация изменяет процедуру Б случайно — должно блокироваться на BP-verification |
| `debug_session_diff` ловит regression в счётчиках (UI+ retries увеличились ×2) | Сценарий: edit вводит infinite-recovery-loop → diff verdict=REGRESSION |
| Backward compat: `/implement-1c-task` без debug-hmr (Code-only mode) работает как раньше | Test runner с замоканным `1c-debug-hmr` returning unavailable |
| 199+ unit-tests + 5 новых mock-based тестов PASS | `pytest tools/bsl-debug-server/ scripts/` |
| Документация: КОМАНДЫ_CLAUDE_CODE.md, 17.5, 36.5, 36.7, skill files обновлены | grep verification |

---

## 7. Risks & Mitigations

| Риск | Митигация |
|---|---|
| Pre-existing rphost gap (см. roadmap §10/§11) — BP не fire'ит на рабочих rphost'ах | Solution A (`force_recycle_rphost=True` в Этап 0) для dev-сред + Solution C (UI thin client) для shared baz; doc'ed в diagnostics table |
| dbgs.exe не запущен или ragent без `-debug -http` | `debug_health_check` ловит на Этап 0, выдаёт recommended fix `scripts/enable-1c-server-debug-http.cmd` |
| Schema cache в Claude Code harness кеширует old MCP-tool params | Doc'ed в 36.7 «Известные ограничения» — пользователь делает `/mcp` reconnect после крупных edit'ов wrapper'а |
| BP-verification замедляет /implement-1c-task | Опционально: env-флаг `IMPLEMENT_1C_SKIP_BP_VERIFY=true` для CI/быстрых итераций; default остаётся ON |
| Long Russian path в working tree блокирует stash | `git -c core.longpaths=true` уже использован в работе с этой проблемой |
| Backward compat: старые ANALYSIS-REPORT без runtime trace section | Pipeline ничего не требует от прошлых отчётов; новый раздел опционален |

---

## 8. Implementation Order (recommended)

```
Phase 1  →  Phase 2  →  Phase 3
(5-7ч)      (3-4ч)      (2-3ч)
   │           │           │
   ▼           ▼           ▼
preflight   analyze     unify +
+ verify    --trace     test +
            (opt)       docs
```

**Why this order**:
- Phase 1 закрывает основной gap (verification-as-proof) — **наибольший немедленный ROI**
- Phase 2 опциональна для analysis (не каждая задача требует runtime trace), значит может быть rolled out incrementally
- Phase 3 cleanup — после того как 1+2 stabilize'нутся

**Suggested first-PR scope**: только Phase 1 (5-7ч) — закрывает 70% value. Остальные две — отдельные PR'ы.

---

## 9. Out-of-scope (для следующих roadmap'ов)

- **GUI-trigger automation**: автоматизация UI-actions в thin client (например, нажатие кнопки «Провести» через UI Automation) для покрытия сценариев где `execute_code` не подходит. Требует Win32 GUI automation library.
- **Multi-target debug**: одновременное BP в 2+ rphost'ах. RDBG поддерживает; wrapper не оптимизирован.
- **Conditional breakpoints**: RDBG поддерживает только line BP, conditions через `rteOnBPCondition` event handler пока не обёрнут.
- **Debug в production-инфобазах**: `force_recycle_rphost` рискован в shared production. Нужен audit-trail mode с явным opt-in.
- **VA BDD ↔ debug-hmr unification**: автозапуск debug-hmr trace когда VA test fail'ится — отдельный roadmap, требует PIPE между VA runner'ом и debug-wrapper'ом.

---

## 10. Validation Test Plan

После Phase 1 closure — прогон на реальной задаче из `configuration/`:

1. **Подготовка**: выбрать closed task с уже принятым ANALYSIS-REPORT (для regression baseline)
2. **Phase 1 verification**:
   - Запустить `/implement-1c-task` на trivial fix
   - Assert preflight выводит debug-hmr ready ✓
   - Assert Этап 5 BP-verification срабатывает на каждой MODIFIED точке
   - Assert IMPLEMENTATION-PROGRESS содержит BP trace
   - Assert session_id записан в footer
3. **Regression test**:
   - Изменить trivial fix чтобы внести infinite-loop-style регрессию (например, забытый Continue в цикле)
   - Запустить /implement-1c-task ещё раз
   - Assert `debug_session_diff` verdict=REGRESSION ловит это
   - Assert pipeline блокируется на Этап 5 с actionable error
4. **Phase 2 verification** (после rollout):
   - Запустить `/analyze-1c-task --trace` на задаче с условной логикой
   - Assert ANALYSIS-REPORT содержит Runtime Trace section
   - Assert Discrepancies section непуста (если static gut-feel разошёлся с runtime)

---

## 11. Roadmap-связи и история debug-wrapper'а

```
260505 (impl-1c-task pipeline fix) ──┐
                                     ├──► 260510 (этот roadmap)
260508 (debug post-BP handshake) ────┘     │
                                           ▼
260510 фиксы wrapper'а (HMR + ping):     ┌───────────────────────┐
  ├─ HMR session restoration  ✓          │ Production integration │
  ├─ debug_stack_trace fix    ✓          │ /analyze-1c-task       │
  ├─ Unified ping() dispatch  ✓          │ /implement-1c-task     │
  └─ Documentation 36.7       ✓          └───────────────────────┘
```

Зависимости: Phase 1 требует уже-merged'нутые коммиты `1872dff` (submodule) + `e74e2fcbd` (parent) + skill `1c-debug-hmr`. Все на 2026-05-10 в master/feat-branch.
