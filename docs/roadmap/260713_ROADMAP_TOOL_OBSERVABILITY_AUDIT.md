# 260713 - Аудит логирования инструментов/MCP + замкнутый цикл метрик эффективности

> Аудит по запросу: «во фреймворке настроено логирование при работе MCP и других инструментов - проанализировать,
> как это сделано, все ли инструменты покрываются; идея: после логирования идёт анализ работоспособности и
> эффективности инструмента, собираются данные, формируются метрики - насколько идея реализована».
> Факты собраны двумя независимыми инвентаризациями кода (эмиттеры логов + потребители/метрики, все ссылки file:line
> подтверждены), best practices - из кеш-исследования
> [`tool-call-observability-effectiveness-2026.md`](../../.claude/skills/architecture-research/cache/tool-call-observability-effectiveness-2026.md)
> (2026-06-17: OTel GenAI `execute_tool`, нативный OTel Claude Code - эмпирически верифицирован, Langfuse/LangSmith,
> MCP-спека logging, deepeval/MCP-Bench метрики). Два свежих `ecosystem_scan` (30-дневное окно) - пусто, кеш остаётся
> актуальной базой. Связанные главы: 42.8 (Claude Code OTel), 28.1 (auto-reports), ADR-035 (advisory toolgate).

## §1 Как логирование реализовано сейчас (карта)

### 1.1 Ядро - хук-уровень, единый синк `data/hook-invocations.jsonl`

Два механизма записи, контракт - [`shared/invocation_logger.py`](../../.claude/hooks/shared/invocation_logger.py):

| Механизм | Что пишет | Качество записи |
|---|---|---|
| **Авто-лог хуков**: `BaseHook.run()` finally-блок ([`base/protocol.py:200-225`](../../.claude/hooks/base/protocol.py)) | Каждое срабатывание каждого хука: `hook/event/tool/outcome/elapsed_ms/run_id/error`, `category="hook"` | `tool_call_id`/`args_hash`/`agent_id` НЕ проставляются |
| **Явный MCP-лог**: [`mcp-invocation-logger.py`](../../.claude/hooks/mcp-invocation-logger.py), единственный универсальный матчер `mcp__.*` Pre+Post (settings.json:369-390) | `category="mcp_call"` + `tool_call_id` (tool_use_id), `args_hash` (sha1[:12]), `error_type` из `tool_response` | Каноническая строка на вызов; подавляет двойной автолог (`_NoAutoLogMcpLogger`) |

Контракт записи современный и выше среднего по индустрии: **CloudEvents v1.0** (specversion/id/source/type/correlationid/causationid) + **W3C traceparent** (детерминированный trace_id из run_id), опциональный crypto-shred поля `error`, JSON-Schema валидация opt-in, ротация 10MB. Живой: 3.4MB/4827 строк + 10MB ротированный.

### 1.2 Прочие синки (15+)

Живые: `gate-decisions.jsonl` (gate-оркестратор), `onec-toolgate-events.jsonl` (ADR-035), `delegation-outcomes.jsonl` (bandit), `skill-accuracy.jsonl`/`skill-quality-metrics.jsonl` (роутер), `memory-metrics.jsonl` + 8 memory-sinks (`trace_log.py`), `llm-rotation-completions/metrics.jsonl`, `indexing-progress.jsonl` (46MB), `ci-failures.jsonl`, `tdd-guard-events.jsonl`. Устаревший: **`tool-effectiveness.jsonl` (stale с 2026-06-16)** - пишется только ручным `tool_usage_report.py`.

### 1.3 Карта покрытия инструментов

| Категория | Покрытие | Деталь |
|---|---|---|
| **MCP tools (все серверы, вкл. будущие)** | ✅ полное | Универсальный `mcp__.*` Pre+Post, каноническая строка с `tool_call_id`/`args_hash` |
| Bash, Write/Edit, Skill, WebSearch/WebFetch | ✅ косвенное | Побочный эффект enforcer-хуков (несколько строк на вызов, без canonical row) |
| Read/Grep/Glob | ⚠ только Pre | Один Pre-хук (`bsl-tool-router`), **PostToolUse нет** → нет длительности/ошибок |
| PowerShell | ⚠ только Pre | `process-guard`; PostToolUse нет |
| TodoWrite, NotebookEdit, TaskGet/List/Output, ExitPlanMode | ❌ невидимы | Ни одного матчера → 0 записей |
| Субагенты (Task/Agent) | ❌ де-факто | Поле `agent_id` в контракте есть, но не передаётся (см. B2) |
| Внутри самих MCP-серверов | ❌ у всех 8 | Только stderr-логгеры + доменные data-jsonl; per-call аудита вызовов tools нет ни у одного (memory-orchestrator - in-memory `_track()` + снапшоты; ai_memory/skill_learning/bsl-semantic-search/1c-mcp-crud/auto-documenter/bsl-debugger - ничего) |

## §2 Насколько реализована идея «лог → анализ → метрики → действие»

**Вердикт: архитектурно правильная и местами образцовая, но замкнута фрагментарно.** Слой сбора (логирование) - сильный; слой анализа существует, но самые ценные его части не автоматизированы; слой «действия по метрикам» есть только в 4 локальных контурах.

| Подсистема | Цикл | Состояние |
|---|---|---|
| Indexing | ✅ замкнут | `run_end` → Stop-hook → detached `analyze_run.py` → отчёт+anomalies. Эталонный паттерн |
| CI | ✅ замкнут | catchup on-start/on-stop → digest |
| Advisory-гейты (toolgate ADR-035, tdd-guard) | 🟡 до рекомендации | Лог → авто SessionStart-анализ (presence/follow_rate) → вердикт-баннер; промоут ручной (осознанно); логи почти пусты → `insufficient-data` |
| Memory | 🟡 наполовину | `memory-effectiveness-analyzer` (Stop, авто) работает; но `memory_observability_report.py` с **freshness/regression-детектором** (ловит «замолчавший sink») запускается только вручную → детектор регрессий ни разу не сработал сам |
| LLM-rotation | 🟡 наполовину | `is_provider_down()` авто-используется в действии (bypass записи), но дашборд/отчётность ручные |
| **Главный лог инструментов (`hook-invocations.jsonl`)** | 🔴 разомкнут | Все три потребителя (`audit_query.py` - 6 DuckDB-views вкл. p95/error-rate/mcp-latency; `tool_usage_report.py` - retry/abandonment; `framework_effectiveness_report.py` - единственный сводный) **ручные**. Отчёт эффективности существует в одном экземпляре от 2026-06-30 и сам констатирует «инструментировано, но пусто» |
| Health MCP-серверов | 🔴 отсутствует | `health_check`-tools есть у 4 серверов - автоматически не вызываются никем; ни порогов, ни алертинга деградации |

**Асимметрия:** автоматизированы дешёвые локальные контуры; над богатейшим центральным логом - только ручная аналитика без порогов и действий.

## §3 Best practices (GitHub/индустрия 2026) и сопоставление

Из кеша `tool-call-observability-effectiveness-2026.md` (канонические источники: OTel semconv GenAI, code.claude.com/docs/monitoring-usage, Langfuse, deepeval/Confident-AI, MCP-Bench arXiv:2508.20453, AWS):

1. **OTel GenAI `execute_tool`** - стандартный спан: `gen_ai.tool.name` (Req), `error.type` низкокардинальный, `gen_ai.tool.call.id`; длительность из start/end спана. Наш лог структурно совместим (CloudEvents+traceparent), но имена полей свои → рекомендация «именовать по `gen_ai.*` - апгрейд в OTel станет переименованием».
2. **Claude Code нативный OTel** (`CLAUDE_CODE_ENABLE_TELEMETRY=1` + `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1`, эмпирически верифицирован на v2.1.179): спаны `claude_code.tool`/`tool.execution`/`tool.blocked_on_user`, событие `claude_code.tool_result` (`success`, `duration_ms`, `error_type`, размеры), `claude_code.mcp_server_connection` (**health MCP-подключений из коробки**), джойн по `tool_use_id`. Это готовый второй источник истины, который закрывает наши слепые зоны built-in tools **без единого хука** - мы его не используем.
3. **Консенсус метрик эффективности - 2 слоя**: детерминированные правила (Tool Success Rate, Tool Correctness, Step Efficiency = % избыточных вызовов, retry-vs-abandonment) + LLM-judge на сэмпле (Argument Correctness, Task Completion), всё пришпилено к трейсу. У нас правила частично есть (`tool_usage_report._effectiveness`: repeats/abandonment) - но не запускаются; LLM-judge слоя нет (осознанно можно отложить).
4. **Лёгкий vs тяжёлый путь**: JSONL+DuckDB локально (наш путь - правильный выбор) с полями по `gen_ai.*`; тяжёлый - OTLP→Langfuse/SigNoz. Индустрия не требует прыжка: наш DuckDB-слой (`audit_query.py`) уже соответствует лёгкому пути, не хватает только автозапуска и порогов.
5. **MCP-спека**: логирование - `notifications/message` (RFC-5424 уровни), трейсинга в протоколе нет (proposal #269 открыт) → внутренний per-call лог сервера - ответственность реализации; минимум для production - структурный лог ошибок + health endpoint. Наши серверы дают только stderr.

## §4 Найденные ошибки (Bugs)

| # | Ошибка | Где | Эффект |
|---|---|---|---|
| **B1** | `detected_event` мисклассифицирует PostToolUse→PreToolUse: ищет `tool_result`, платформа шлёт `tool_response`; обход захардкожен только в `mcp-invocation-logger.py:66-71` | [`base/protocol.py:52-55`](../../.claude/hooks/base/protocol.py) | Все прочие Post-хуки могут писать `event="PreToolUse"` → Pre/Post-пэйринг и латентности built-in tools битые |
| **B2** | `agent_id` заявлен в контракте (Phase 7, `invocation_logger.py:111`) и схеме, но `BaseHook.run()` его не передаёт | `base/protocol.py:214-223` | Вызовы субагентов неотличимы от основной сессии; мониторинг делегирования через лог не работает |
| **B3** | Нет канонической строки для built-in tools: один вызов Bash → 4 строки (по числу совпавших enforcer'ов), все `category="hook"`, без `tool_call_id`/`args_hash` | settings.json матчеры + BaseHook | Двойной/четверной счёт вызовов; метрики top-tools/error-rate по built-in искажены |
| **B4** | `mcp__llm-rotation__llm_complete` логируется дважды (`task-protocol-observer` category=hook + `mcp-invocation-logger` category=mcp_call) | settings.json:360-390 | Дубль в подсчётах MCP |
| **B5** | Пробелы покрытия: Read/Grep/Glob и PowerShell без PostToolUse; TodoWrite/NotebookEdit/Task*/ExitPlanMode без матчеров вовсе | settings.json | Слепые зоны аудита |
| **B6** | `tool-effectiveness.jsonl` stale (2026-06-16): онлайн-пополнение отсутствует, `--rollup` только по напоминанию из `onec-task-completion-stop.py:384` | `scripts/tool_usage_report.py` | Метрики эффективности не отражают реальность |
| **B7** | MCP `health_check`-tools (memory-orchestrator, vector-memory, skill-learning, 1c-debug) не вызываются автоматически нигде | grep hooks/scripts: 0 вызовов | Деградация/падение MCP-сервера обнаруживается только при живом отказе в работе |
| **B8** | Regression/freshness-детектор memory-sinks (`memory_observability_report.py:238-283`) запускается только вручную | scripts/ | Способность ловить «замолчавший sink» не используется |
| **B9** | Ни один из 8 собственных MCP-серверов не ведёт внутренний per-call лог: при краше/таймауте stdio до Post-хука вызов теряется бесследно | src/memory/*, src/bsl/*, tools/* | Нет второго источника истины при отказах транспорта |
| **B10** | Единый сводный отчёт (`framework_effectiveness_report.py`) ручной, один прогон от 2026-06-30 | scripts/ | «Метрики формируются» - формально да, фактически раз в 2 недели руками |

## §5 Дорожная карта

### P0 - корректность самого лога (без этого метрики врут)

- **P0.1 Fix Post-классификации `detected_event` (B1). ✅ реализовано 2026-07-14 (commit b575a2dc3).** В `base/protocol.py` детект PostToolUse по `tool_response` (с легаси-фоллбэком `tool_result`, hook_event_name - приоритет); обход из `mcp-invocation-logger.py` удалён (`event = inp.detected_event`); латентный дубль в `base/base.py` тоже поправлен. 4 регресс-unit. code-verify PASS.
- **P0.2 Прокинуть `agent_id` (B2). ✅ реализовано 2026-07-14.** `HookInput.agent_id` (из `agent_id`/`agentId`) → `BaseHook.run()` прокидывает в `log_invocation`. Аддитивно: платформа сейчас не шлёт (0/5291 строк) → "". 3 unit.
- **P0.3 Канонический tool-invocation-logger для built-in (B3, B5). ✅ реализовано 2026-07-14.** Новый `tool-invocation-logger.py` (Pre+Post, matcher built-in tools, `category="tool_call"`, `tool_call_id`+`args_hash`, `_NoAutoLogToolLogger` подавляет автолог), зарегистрирован в `settings.json`. Потребители обобщены: `tool_usage_report._CANONICAL_CATEGORIES={mcp_call,tool_call}`, `audit_query top-tools` считает канонические PostToolUse. 7 unit. **Отклонение от плана:** BaseHook НЕ трогали для built-in (canonical row + фильтр потребителей достаточен, меньше blast-radius).
- **P0.4 Дедуп `llm_complete` (B4). ✅ реализовано 2026-07-14.** `BaseHook.run()` подавляет автолог mcp__ тула при `outcome=allow` (systemic: покрывает task-protocol-observer и любой будущий хук на mcp-туле; block/error сохранены). 3 unit.

> **Итог P0 (2026-07-14, commit b575a2dc3):** все 4 фикса + 18 unit (test_hook_invocation_logging_p0 + test_tool_invocation_logger) + 28/11 существующих зелёные + code-verify reviewer PASS. Лог инструментов теперь даёт честные счётчики вызовов по каноническим категориям — метрики P1 можно строить на нём.

### P1 - замкнуть цикл: авто-анализ + health + пороги

- **P1.1 Авто tool-health-отчёт (B10, паттерн `post-indexing-analyzer`). ✅ реализовано 2026-07-14.** `scripts/analyze_tool_health.py` (stdlib-only, НЕ duckdb — надёжно в detached-контексте): читает канонические строки за окно 14д → per-tool calls/errors/success-rate/реальная Pre→Post p50-p95/repeats/abandonment → **вердикты §6.1** (broken/degraded/ineffective/unused/healthy) → `data/reports/tools/_latest.md` + `_latest.json` sidecar + `verdicts.jsonl` (append-history) + ratchet `baseline.json`. Stop-хук `tool-health-analyzer-stop.py` (cooldown 24ч, detached-спавн) + SessionStart-баннер `tool-health-banner-on-start.py` (сюрфейсит broken/degraded, эскалирует broken авто-задачей через task_master с 72ч-дедупом, degraded — за человеком; тихо при healthy). 27 unit + code-verify PASS (2 рекомендации применены: `DEGRADED_MIN_CALLS=3` против шума от транзиентных ошибок + tz-guard). **Ключевой FP устранён:** idempotent-polling (100% success + повторы args_hash) = healthy, repeats НЕ движут вердикт. *Acceptance выполнен:* детач-спавн отработал end-to-end (отчёт+verdicts+baseline записаны); баннер молчит при healthy, сюрфейсит alerts иначе. **DuckDB-views из audit_query остаются для интерактива** (аналайзер их не требует).
- **P1.2 Авто MCP health-check (B7). ✅ реализовано 2026-07-14.** Ключевое отклонение от плана: `health_check`-tools серверов вызвать из хука НЕЛЬЗЯ (это MCP-tools, исполняемые клиентом; серверы async + тяжёлая инициализация) → вместо них пробим их **зависимости** — `scripts/probe_mcp_health.py` (stdlib): Qdrant `GET /healthz` (env `QDRANT_URL`, как читают серверы), TEI `POST /embed`, memory-ai `memory_ai.db` + bsl-code-search `bsl_call_graph.db` (SQLite ro-PRAGMA) → `data/mcp-health.jsonl` (история) + `_mcp_health.json` (sidecar down+affects). SessionStart-хук `mcp-health-probe-on-start.py` (inline, быстрый когда up, баннер с картой «что деградирует» только при down, opt-out `MCP_HEALTH_PROBE_DISABLE=1`, graceful). RDBG не пробится (on-demand → был бы шум). 9 unit + code-verify (PARTIAL→FIXED: memory-ai пробил легаси `conversations.db` вместо `memory_ai.db`; Qdrant-env `VECTOR_STORE__QDRANT_URL`→`QDRANT_URL`). Генерация probe делегирована Z.AI (token economy), отревьюена (RUF100-fix). *Отклонение:* inline-probe (не detached) — быстрый когда healthy, немедленный сигнал при down.
- **P1.3 Оживить `tool-effectiveness` (B6).** Вызов `tool_usage_report.py` detached из Stop-хука 1С-гейта (вместо напоминания в `onec-task-completion-stop.py:384`) + weekly `--rollup` внутри P1.1-отчёта. *Оценка:* 1-2 ч.
- **P1.4 Regression-детектор memory-sinks в каденс (B8).** `memory_observability_report.py --json` (freshness/regression секция) в существующий `memory-maintenance-cadence` Stop-хук; stale-sink → та же ALERTS-секция P1.1. *Оценка:* 1-2 ч.

### P2 - метрики эффективности по консенсусу 2026

- **P2.1 `gen_ai.*`-совместимые имена полей.** В `invocation_logger` дополнить запись алиасами `gen_ai.tool.name`/`gen_ai.tool.call.id`/`error.type` (аддитивно, без ломки потребителей) - будущий OTel-экспорт станет переименованием. *Оценка:* 1 ч.
- **P2.2 Rule-слой эффективности в P1.1-отчёт.** Tool Success Rate per-tool/per-server, Step Efficiency (% избыточных вызовов), retry-vs-abandonment (цикл «тот же падающий вызов ×N») - функции уже есть в `tool_usage_report._effectiveness`, вынести в общий модуль и считать cross-task. *Оценка:* 2-3 ч.
- **P2.3 Внутренний per-call лог у критичных MCP-серверов (B9, частично).** Общий helper (по образцу `trace_log.write_trace`) в `call_tool`-обёртку минимум у memory-orchestrator и 1c-mcp-crud (наиболее критичные): `{ts, tool, ok, ms, error_type}` → `.claude/cache/mcp-<server>-calls.jsonl` с ротацией. Остальные серверы - по мере касания. *Оценка:* 2-3 ч на сервер.

### P3 - тяжёлый путь (опционально, после P1-P2)

- **P3.1 Нативный OTel Claude Code как второй источник.** `CLAUDE_CODE_ENABLE_TELEMETRY=1` + beta-traces → локальный OTLP-коллектор → Langfuse self-host (Docker, уже исследован - кеш `langfuse-llm-observability-2026`). Закрывает слепые зоны built-in без хуков; джойн с `hook-invocations.jsonl` по `tool_use_id`. Решение отдельным ADR после оценки нагрузки. *Оценка:* 1-2 дня.
- **P3.2 LLM-judge на сэмпле.** Argument Correctness / Task Completion (deepeval-паттерн) на 5-10% вызовов через `llm_complete` (z.ai, token economy). Только если P2-метрики покажут потребность. *Оценка:* 1 день.

**Порядок:** P0.1→P0.2→P0.4 (мелкие фиксы одним срезом) → P0.3 → P1.1 → P1.2-P1.4 → P2. P3 - по отдельному решению.

## §6 Контур вердиктов и принятия решений (decision layer)

Ответ на вопрос «данные собраны - как получается итоговый вывод и принимается решение о повышении эффективности или исправлении неработающего инструмента». Слой решений строится на уже проверенных во фреймворке паттернах: окно-валидация (`acceptance_watch`/`tdd_guard_validation`/`onec_toolgate_validation` - метрика за окно → вердикт → человек промоутит), авто-действие только для детерминированных случаев (`llm_health.is_provider_down` → bypass), re-verify после фикса (паттерн `sonar_rescan_verify`).

### 6.1 Вердикты per-tool (выход `analyze_tool_health.py`, P1.1)

Каждому инструменту/MCP-tool за скользящее окно (default 14 дней, min 5 вызовов для статистики) присваивается один вердикт:

| Вердикт | Правило (детерминированное) | Кто решает дальше |
|---|---|---|
| **broken** | success-rate < 50% при ≥5 вызовах, ИЛИ 0 успешных при ≥3 попытках, ИЛИ MCP `health_check` down ≥2 дня подряд, ИЛИ sink инструмента «замолчал» (freshness-регрессия) | **авто-эскалация** (6.2) |
| **degraded** | error-rate > 10% за окно, ИЛИ p95 > 2× baseline, ИЛИ рост error-rate > +5пп к прошлому окну (ratchet) | advisory-баннер, решение за человеком |
| **ineffective** | success-rate ок, но retry-циклы («тот же падающий вызов ×3+») или abandonment > 30% (вызов упал и брошен), step efficiency низкая | advisory-баннер + evidence, решение за человеком |
| **unused** | 0 вызовов за окно | месячный отчёт «кандидаты на отключение» (lazy-mcp / снятие из автозагрузки) |
| **healthy** | всё остальное | - |

Baseline: первый прогон пишет `data/reports/tools/baseline.json` (p95, error-rate per-tool); дальше сравнение окно-к-окну + ratchet (ухудшение фиксируется, улучшение обновляет baseline) - паттерн mypy-baseline.

### 6.2 Принятие решения (по тяжести, зеркалит ADR-035 «advisory → validation → ручной промоут»)

1. **broken → авто-эскалация, но НЕ авто-фикс.** SessionStart-баннер (hard-заметный, не advisory) + авто-создание mandatory-задачи «диагностировать инструмент X» (паттерн knowledge-cache-reminder) с приложенным evidence-пакетом: топ `error_type`, последние N падений с `args_hash`, correlationid для трейса. Исправление идёт стандартным пайплайном (root-cause → fix → re-verify). Молчаливый авто-фикс запрещён - принцип фреймворка (bounded AUTO + needs-human, гл.43 P3.2).
2. **degraded/ineffective → рекомендация с доказательствами.** Баннер формата валидаторов (`onec_toolgate_validation`): метрика, дельта к baseline, вердикт-кандидат («тюнить таймаут/промпт/параметры», «инструмент дублирует Y - маршрутизировать туда»). Решение - за человеком; принятые решения фиксируются ADR (авто, [[feedback-sdd-4step-auto-adr]]).
3. **Детерминированный авто-обход** разрешён только там, где действие обратимо и безопасно: provider/сервер down → graceful bypass зависимых операций (уже реализовано в `z-ai-write-guard` через `is_provider_down`; расширить на MCP-health из P1.2).

### 6.3 Замыкание петли (как решение о фиксе считается исполненным)

- После фикса вердикт НЕ снимается вручную: re-verify тем же валидатором на **свежем** окне после даты фикса (паттерн `sonar_rescan_verify`: «анализ свежее правок»). Окно чистое → вердикт healthy, baseline обновлён.
- История вердиктов - append-only `data/reports/tools/verdicts.jsonl` (`{ts, tool, verdict, window, evidence_ref}`) → тренд виден, повторный broken того же инструмента за 30 дней = эскалация приоритета (needs-human p1).
- Итог по эффективности (не только работоспособности): quarterly-срез в `framework_effectiveness_report` - какие инструменты дают retry/abandonment хуже медианы → кандидаты на редизайн/замену; решение оформляется ADR со ссылкой на verdicts-историю.

**Реализация:** вердикты 6.1 + verdicts.jsonl входят в P1.1; эскалация broken (авто-задача) - добавка к P1.1 (+1-2 ч); quarterly-срез - в P2.2.

## §18 Progress Log

> Append-only, reverse-chronological. Новые записи сверху.

### 2026-07-14 - P1.2 реализован (проактивный MCP health-probe)

- `probe_mcp_health.py` (Qdrant/TEI/SQLite deps) + SessionStart-хук `mcp-health-probe-on-start.py` (баннер при down с картой affects). health_check-tools серверов из хука недостижимы → пробим их зависимости. 9 unit + code-verify PARTIAL→FIXED (memory-ai DB + Qdrant env). Генерация probe делегирована Z.AI + ревью.
- Следующее: P1.3 (оживить tool-effectiveness из Stop), P1.4 (regression-детектор memory-sinks в каденс).

### 2026-07-14 - P1.1 реализован (decision layer: авто-отчёт + вердикты)

- `analyze_tool_health.py` (вердикты §6.1 + verdicts.jsonl + ratchet baseline) + Stop-хук (cooldown 24ч, detached) + SessionStart-баннер (эскалация broken авто-задачей). 27 unit + code-verify PASS. Цикл «лог → анализ → вердикт → действие» замкнут.
- Отклонения: аналайзер stdlib-only (не duckdb) для надёжности; ineffective = только abandonment (repeats не движут вердикт — FP на polling-тулах); `DEGRADED_MIN_CALLS=3`.
- Следующее: P1.2 (авто-каденс MCP health-check), P1.3/P1.4.

### 2026-07-14 - P0 реализован (корректность лога)

- B1/B2/B4 в `base/protocol.py` + удалён обход в mcp-логгере + латентный B1 в base.py; B3/B5 новый `tool-invocation-logger.py` (category=tool_call) + settings.json; потребители обобщены на `_CANONICAL_CATEGORIES`. 18 unit + code-verify PASS. Commit b575a2dc3.
- Следующее: P1.1 (авто tool-health-отчёт + вердикты §6).

### 2026-07-13 - Добавлен §6 decision layer

- Вердикты broken/degraded/ineffective/unused/healthy + правила эскалации (авто-эскалация без авто-фикса, re-verify на свежем окне, verdicts.jsonl).

### 2026-07-13 - Аудит проведён, роадмап создан

- Две независимые инвентаризации кода (эмиттеры + потребители), 10 ошибок B1-B10, дорожная карта P0-P3.
- Best practices: кеш `tool-call-observability-effectiveness-2026.md` (2026-06-17) актуален; 2× `ecosystem_scan` за 30 дней - пусто.
- Реализация - не начата (roadmap-only).
