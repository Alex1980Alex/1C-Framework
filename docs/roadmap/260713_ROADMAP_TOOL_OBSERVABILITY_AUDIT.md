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

## §0 Промежуточные итоги (на 2026-07-14)

> Снимок прогресса. Детальные записи — §18 (снизу вверх), раскладка по пунктам — §5.

**Ядро дорожной карты закрыто.** Цикл «лог → анализ → метрика → вердикт → действие» над главным логом инструментов (`data/hook-invocations.jsonl`), диагностированный как разомкнутый (§2), теперь замкнут: корректность записи вылечена, авто-анализ с вердиктами работает, метрики эффективности считаются, MCP-серверы получили health-probe и внутренний per-call лог.

| Пункт | Статус | Суть |
|---|---|---|
| **P0** корректность лога (B1/B2/B3/B4/B5) | ✅ b575a2dc3 | Post-классификация по `tool_response`; `agent_id`; канонический `tool-invocation-logger` (category=tool_call) для built-in; дедуп `llm_complete`. Метрики перестали врать. |
| **P1.1** decision layer (B10) | ✅ 4597efb87 | `analyze_tool_health.py` — вердикты broken/degraded/ineffective/unused/healthy §6.1 + `verdicts.jsonl` + ratchet-baseline; Stop-авто-отчёт + SessionStart-баннер (broken → авто-задача). |
| **P1.2** проактивный MCP health-probe (B7) | ✅ cf260aa42 | `probe_mcp_health.py` пробит зависимости серверов (Qdrant/TEI/SQLite) + баннер при down с картой affects. |
| **P1.4** regression-детектор memory-sinks (B8) | ✅ be5accdb9 | Freshness-детектор замолчавших синков в каденс. Живая находка: 3 stale-синка (propagation/circuit/links >7д). |
| **P2.1** gen_ai.*-алиасы полей | ✅ fb08d72dc | OTel-совместимые `gen_ai.tool.name`/`gen_ai.tool.call.id`/`error.type` (аддитивно) — будущий OTel-экспорт = переименование. |
| **P2.2** rule-слой эффективности | ✅ fb08d72dc | single-source `tool_effectiveness.py` + per-server rollup (Tool Success Rate + Step Efficiency). Живая находка: `edt-mcp` retry-rate 14%. |
| **P2.3** внутренний per-call лог MCP (B9) | ✅ 8a899477c | Shared `mcp_call_log.py` (fail-soft/ротация/opt-out) у memory-orchestrator + 1c-mcp-crud — второй источник истины при падении stdio. |

**Осталось:**
- **P1.3** (оживить `tool-effectiveness.jsonl` из Stop-хука) — фактически перекрыт P1.1 (аналайзер читает `hook-invocations.jsonl` напрямую); при желании — вызов `tool_usage_report.py --rollup` внутри P1.1-отчёта.
- **P2.3 хвост** — остальные 6 MCP-серверов инструментируются по мере касания.
- **P3** (нативный OTel Claude Code → Langfuse self-host + LLM-judge на сэмпле) — тяжёлый путь, отдельным ADR после оценки нагрузки.

**Накопленные находки (сигналы, не баги роадмапа):** 3 замолчавших memory-синка (P1.4); `edt-mcp` retry-rate 14% — кандидат на разбор паттернов взаимодействия (P2.2). **Операционка:** рантайм-эффект P2.3 (правки кода MCP-серверов) — после `/mcp reconnect`; P0–P2 хук/скрипт-часть действует сразу.

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

**Вердикт (исходный, 2026-07-13): архитектурно правильная и местами образцовая, но замкнута фрагментарно.** Слой сбора (логирование) - сильный; слой анализа существует, но самые ценные его части не автоматизированы; слой «действия по метрикам» есть только в 4 локальных контурах.

**Обновление 2026-07-14: асимметрия устранена — центральный контур замкнут (P0–P2).** Колонка «Стало» ниже фиксирует закрытие.

| Подсистема | Цикл (было) | Стало (2026-07-14) |
|---|---|---|
| Indexing | ✅ замкнут | ✅ без изменений (эталонный паттерн `run_end` → `analyze_run.py`) |
| CI | ✅ замкнут | ✅ без изменений (catchup on-start/on-stop → digest) |
| Advisory-гейты (toolgate ADR-035, tdd-guard) | 🟡 до рекомендации | 🟡 без изменений (промоут ручной — осознанно) |
| Memory | 🟡 наполовину | ✅ **замкнут** — freshness/regression-детектор memory-sinks в каденс (P1.4); первый же авто-прогон нашёл 3 замолчавших синка |
| LLM-rotation | 🟡 наполовину | 🟡 без изменений (`is_provider_down` авто-bypass есть; дашборд ручной) |
| **Главный лог инструментов (`hook-invocations.jsonl`)** | 🔴 разомкнут | ✅ **замкнут** — корректность записи (P0) + авто Stop-отчёт с вердиктами §6.1 + баннер (P1.1) + rule-слой эффективности per-tool/per-server (P2.2) + gen_ai.*-совместимые поля (P2.1) |
| Health MCP-серверов | 🔴 отсутствует | ✅ **есть** — проактивный probe зависимостей серверов + баннер при down с картой affects (P1.2); внутренний per-call лог у критичных серверов (P2.3) |

**Итог:** богатейший центральный лог получил автозапуск, пороги и действия (авто-задача на broken); осталась только ручная отчётность в двух дешёвых контурах (LLM-rotation дашборд, advisory-промоут) — осознанно.

## §3 Best practices (GitHub/индустрия 2026) и сопоставление

Из кеша `tool-call-observability-effectiveness-2026.md` (канонические источники: OTel semconv GenAI, code.claude.com/docs/monitoring-usage, Langfuse, deepeval/Confident-AI, MCP-Bench arXiv:2508.20453, AWS):

1. **OTel GenAI `execute_tool`** - стандартный спан: `gen_ai.tool.name` (Req), `error.type` низкокардинальный, `gen_ai.tool.call.id`; длительность из start/end спана. Наш лог структурно совместим (CloudEvents+traceparent), но имена полей свои → рекомендация «именовать по `gen_ai.*` - апгрейд в OTel станет переименованием».
2. **Claude Code нативный OTel** (`CLAUDE_CODE_ENABLE_TELEMETRY=1` + `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1`, эмпирически верифицирован на v2.1.179): спаны `claude_code.tool`/`tool.execution`/`tool.blocked_on_user`, событие `claude_code.tool_result` (`success`, `duration_ms`, `error_type`, размеры), `claude_code.mcp_server_connection` (**health MCP-подключений из коробки**), джойн по `tool_use_id`. Это готовый второй источник истины, который закрывает наши слепые зоны built-in tools **без единого хука** - мы его не используем.
3. **Консенсус метрик эффективности - 2 слоя**: детерминированные правила (Tool Success Rate, Tool Correctness, Step Efficiency = % избыточных вызовов, retry-vs-abandonment) + LLM-judge на сэмпле (Argument Correctness, Task Completion), всё пришпилено к трейсу. У нас правила частично есть (`tool_usage_report._effectiveness`: repeats/abandonment) - но не запускаются; LLM-judge слоя нет (осознанно можно отложить).
4. **Лёгкий vs тяжёлый путь**: JSONL+DuckDB локально (наш путь - правильный выбор) с полями по `gen_ai.*`; тяжёлый - OTLP→Langfuse/SigNoz. Индустрия не требует прыжка: наш DuckDB-слой (`audit_query.py`) уже соответствует лёгкому пути, не хватает только автозапуска и порогов.
5. **MCP-спека**: логирование - `notifications/message` (RFC-5424 уровни), трейсинга в протоколе нет (proposal #269 открыт) → внутренний per-call лог сервера - ответственность реализации; минимум для production - структурный лог ошибок + health endpoint. Наши серверы дают только stderr.

## §4 Найденные ошибки (Bugs)

> Колонка **Статус** отражает закрытие на 2026-07-14. Детали фиксов — §5 / §18.

| # | Ошибка | Где | Эффект | Статус |
|---|---|---|---|---|
| **B1** | `detected_event` мисклассифицирует PostToolUse→PreToolUse: ищет `tool_result`, платформа шлёт `tool_response`; обход захардкожен только в `mcp-invocation-logger.py:66-71` | [`base/protocol.py:52-55`](../../.claude/hooks/base/protocol.py) | Все прочие Post-хуки могут писать `event="PreToolUse"` → Pre/Post-пэйринг и латентности built-in tools битые | ✅ P0.1 (b575a2dc3) |
| **B2** | `agent_id` заявлен в контракте (Phase 7, `invocation_logger.py:111`) и схеме, но `BaseHook.run()` его не передаёт | `base/protocol.py:214-223` | Вызовы субагентов неотличимы от основной сессии; мониторинг делегирования через лог не работает | ✅ P0.2 (аддитивно; платформа пока не шлёт `agent_id`) |
| **B3** | Нет канонической строки для built-in tools: один вызов Bash → 4 строки (по числу совпавших enforcer'ов), все `category="hook"`, без `tool_call_id`/`args_hash` | settings.json матчеры + BaseHook | Двойной/четверной счёт вызовов; метрики top-tools/error-rate по built-in искажены | ✅ P0.3 (`tool-invocation-logger`, category=tool_call) |
| **B4** | `mcp__llm-rotation__llm_complete` логируется дважды (`task-protocol-observer` category=hook + `mcp-invocation-logger` category=mcp_call) | settings.json:360-390 | Дубль в подсчётах MCP | ✅ P0.4 (BaseHook подавляет автолог mcp__ при allow) |
| **B5** | Пробелы покрытия: Read/Grep/Glob и PowerShell без PostToolUse; TodoWrite/NotebookEdit/Task*/ExitPlanMode без матчеров вовсе | settings.json | Слепые зоны аудита | ✅ P0.3 (built-in канонизированы; хвост доп-матчеров — по мере нужды) |
| **B6** | `tool-effectiveness.jsonl` stale (2026-06-16): онлайн-пополнение отсутствует, `--rollup` только по напоминанию из `onec-task-completion-stop.py:384` | `scripts/tool_usage_report.py` | Метрики эффективности не отражают реальность | 🟡 перекрыт P1.1+P2.2 (метрики теперь из `hook-invocations.jsonl` напрямую); оживление jsonl-writer = P1.3 |
| **B7** | MCP `health_check`-tools (memory-orchestrator, vector-memory, skill-learning, 1c-debug) не вызываются автоматически нигде | grep hooks/scripts: 0 вызовов | Деградация/падение MCP-сервера обнаруживается только при живом отказе в работе | ✅ P1.2 (cf260aa42 — probe зависимостей + баннер) |
| **B8** | Regression/freshness-детектор memory-sinks (`memory_observability_report.py:238-283`) запускается только вручную | scripts/ | Способность ловить «замолчавший sink» не используется | ✅ P1.4 (be5accdb9 — в каденс) |
| **B9** | Ни один из 8 собственных MCP-серверов не ведёт внутренний per-call лог: при краше/таймауте stdio до Post-хука вызов теряется бесследно | src/memory/*, src/bsl/*, tools/* | Нет второго источника истины при отказах транспорта | ✅ P2.3 (8a899477c — memory-orchestrator + 1c-mcp-crud; ост. 6 по мере касания) |
| **B10** | Единый сводный отчёт (`framework_effectiveness_report.py`) ручной, один прогон от 2026-06-30 | scripts/ | «Метрики формируются» - формально да, фактически раз в 2 недели руками | ✅ P1.1 (4597efb87 — авто Stop-отчёт `analyze_tool_health` + баннер) |

## §5 Дорожная карта

### P0 - корректность самого лога (без этого метрики врут) — ✅ закрыт

- **P0.1 Fix Post-классификации `detected_event` (B1). ✅ реализовано 2026-07-14 (commit b575a2dc3).** В `base/protocol.py` детект PostToolUse по `tool_response` (с легаси-фоллбэком `tool_result`, hook_event_name - приоритет); обход из `mcp-invocation-logger.py` удалён (`event = inp.detected_event`); латентный дубль в `base/base.py` тоже поправлен. 4 регресс-unit. code-verify PASS.
- **P0.2 Прокинуть `agent_id` (B2). ✅ реализовано 2026-07-14.** `HookInput.agent_id` (из `agent_id`/`agentId`) → `BaseHook.run()` прокидывает в `log_invocation`. Аддитивно: платформа сейчас не шлёт (0/5291 строк) → "". 3 unit.
- **P0.3 Канонический tool-invocation-logger для built-in (B3, B5). ✅ реализовано 2026-07-14.** Новый `tool-invocation-logger.py` (Pre+Post, matcher built-in tools, `category="tool_call"`, `tool_call_id`+`args_hash`, `_NoAutoLogToolLogger` подавляет автолог), зарегистрирован в `settings.json`. Потребители обобщены: `tool_usage_report._CANONICAL_CATEGORIES={mcp_call,tool_call}`, `audit_query top-tools` считает канонические PostToolUse. 7 unit. **Отклонение от плана:** BaseHook НЕ трогали для built-in (canonical row + фильтр потребителей достаточен, меньше blast-radius).
- **P0.4 Дедуп `llm_complete` (B4). ✅ реализовано 2026-07-14.** `BaseHook.run()` подавляет автолог mcp__ тула при `outcome=allow` (systemic: покрывает task-protocol-observer и любой будущий хук на mcp-туле; block/error сохранены). 3 unit.

> **Итог P0 (2026-07-14, commit b575a2dc3):** все 4 фикса + 18 unit (test_hook_invocation_logging_p0 + test_tool_invocation_logger) + 28/11 существующих зелёные + code-verify reviewer PASS. Лог инструментов теперь даёт честные счётчики вызовов по каноническим категориям — метрики P1 можно строить на нём.

### P1 - замкнуть цикл: авто-анализ + health + пороги — ✅ закрыт (P1.1/1.2/1.4 реализованы, P1.3 перекрыт)

- **P1.1 Авто tool-health-отчёт (B10, паттерн `post-indexing-analyzer`). ✅ реализовано 2026-07-14.** `scripts/analyze_tool_health.py` (stdlib-only, НЕ duckdb — надёжно в detached-контексте): читает канонические строки за окно 14д → per-tool calls/errors/success-rate/реальная Pre→Post p50-p95/repeats/abandonment → **вердикты §6.1** (broken/degraded/ineffective/unused/healthy) → `data/reports/tools/_latest.md` + `_latest.json` sidecar + `verdicts.jsonl` (append-history) + ratchet `baseline.json`. Stop-хук `tool-health-analyzer-stop.py` (cooldown 24ч, detached-спавн) + SessionStart-баннер `tool-health-banner-on-start.py` (сюрфейсит broken/degraded, эскалирует broken авто-задачей через task_master с 72ч-дедупом, degraded — за человеком; тихо при healthy). 27 unit + code-verify PASS (2 рекомендации применены: `DEGRADED_MIN_CALLS=3` против шума от транзиентных ошибок + tz-guard). **Ключевой FP устранён:** idempotent-polling (100% success + повторы args_hash) = healthy, repeats НЕ движут вердикт. *Acceptance выполнен:* детач-спавн отработал end-to-end (отчёт+verdicts+baseline записаны); баннер молчит при healthy, сюрфейсит alerts иначе. **DuckDB-views из audit_query остаются для интерактива** (аналайзер их не требует).
- **P1.2 Авто MCP health-check (B7). ✅ реализовано 2026-07-14.** Ключевое отклонение от плана: `health_check`-tools серверов вызвать из хука НЕЛЬЗЯ (это MCP-tools, исполняемые клиентом; серверы async + тяжёлая инициализация) → вместо них пробим их **зависимости** — `scripts/probe_mcp_health.py` (stdlib): Qdrant `GET /healthz` (env `QDRANT_URL`, как читают серверы), TEI `POST /embed`, memory-ai `memory_ai.db` + bsl-code-search `bsl_call_graph.db` (SQLite ro-PRAGMA) → `data/mcp-health.jsonl` (история) + `_mcp_health.json` (sidecar down+affects). SessionStart-хук `mcp-health-probe-on-start.py` (inline, быстрый когда up, баннер с картой «что деградирует» только при down, opt-out `MCP_HEALTH_PROBE_DISABLE=1`, graceful). RDBG не пробится (on-demand → был бы шум). 9 unit + code-verify (PARTIAL→FIXED: memory-ai пробил легаси `conversations.db` вместо `memory_ai.db`; Qdrant-env `VECTOR_STORE__QDRANT_URL`→`QDRANT_URL`). Генерация probe делегирована Z.AI (token economy), отревьюена (RUF100-fix). *Отклонение:* inline-probe (не detached) — быстрый когда healthy, немедленный сигнал при down.
- **P1.3 Оживить `tool-effectiveness` (B6). 🟢 закрыт супер-седом (P1.1+P2.2), 2026-07-14.** Исходная потребность (метрики эффективности не отражают реальность из-за stale `tool-effectiveness.jsonl`) снята иначе: `analyze_tool_health` (P1.1) и rule-слой (P2.2) считают success-rate/retry/abandonment/step-efficiency **напрямую из `hook-invocations.jsonl`** за окно 14д, не завися от `tool-effectiveness.jsonl`. Отдельный detached-вызов `tool_usage_report.py --rollup` из Stop-хука — необязательная добавка (per-task `TOOL-USAGE-REPORT.md` пишется по требованию); заводить только если понадобится per-task-срез вне 1С-гейта. *Оценка была:* 1-2 ч.
- **P1.4 Regression-детектор memory-sinks в каденс (B8). ✅ реализовано 2026-07-14.** `memory-maintenance-cadence.py` при фаере каденса (раз в N сессий) синхронно (read-only, <1с) прогоняет `memory_observability_report.py` через `_check_regressions()` → парсит машиночитаемую `[REGRESSION] N stale sink(s): [...]` строку → сюрфейсит замолчавшие синки прямо в баннер каденса. Раньше freshness-детектор запускался ТОЛЬКО вручную (никогда не срабатывал сам). 6 unit + e2e preflight. **Живая находка при первом прогоне:** 3 stale-синка (`propagation`, `circuit`, `links` — memory-orchestrator перестал в них писать >7д) — ровно тот класс регрессии, что B8 ловит. *Реализация проще плана:* не отдельный `--json` + ALERTS-секция P1.1, а маркер-строка из отчёта в баннер каденса (отчёт уже её печатает).

### P2 - метрики эффективности по консенсусу 2026 — ✅ закрыт (P2.1/2.2/2.3; хвост P2.3 — ост. 6 серверов по мере касания)

- **P2.1 `gen_ai.*`-совместимые имена полей. ✅ реализовано 2026-07-14.** `invocation_logger` пишет аддитивные dotted-алиасы `gen_ai.tool.name`/`gen_ai.tool.call.id`/`error.type` (дословно дублируют плоские `tool`/`tool_call_id`/`error_type`; единый источник `err_type`+`success` — нет дрейфа). Схема `additionalProperties:true` → валидация не ломается; потребители по плоским именам не затронуты; будущий OTel-экспорт = переименование. Подтверждено на живом логе (хуки — свежие субпроцессы, reconnect не нужен). *Оценка была:* 1 ч.
- **P2.2 Rule-слой эффективности в P1.1-отчёт. ✅ реализовано 2026-07-14.** Дублирующие детерминированные функции (pair-duration/percentile/retry-abandonment) вынесены из `tool_usage_report`+`analyze_tool_health` в single-source [`scripts/tool_effectiveness.py`](../../scripts/tool_effectiveness.py) (stdlib-only); оба потребителя делегируют (алиасы `_pct`/`_pair_duration_list` сохранены для тестов, behavior-preserving). Добавлен **per-server rollup** (Tool Success Rate + Step Efficiency = % избыточных retry-вызовов + abandonment_tools) в `analyze_tool_health` → секция «Эффективность (rule-слой, per-server)» в `_latest.md` + `servers` в sidecar. Cross-task = скользящее окно 14д (уже в P1.1). 90 unit (73 существующих зелёные + 17 новых) + code-verify PASS. **Живая находка:** `edt-mcp` step-eff 14% (retry-rate) — выше прочих серверов. *Оценка была:* 2-3 ч.
- **P2.3 Внутренний per-call лог у критичных MCP-серверов (B9, частично). ✅ реализовано 2026-07-14.** Общий stdlib-only helper `scripts/mcp_call_log.py` (`log_mcp_call` + контекст-менеджер `track_call` — таймер + auto-лог ok/error_type + ре-райз исключения; ротация 2MB `os.replace`, fail-soft, opt-out `MCP_CALL_LOG_DISABLE=1`) → `.claude/cache/mcp-<server>-calls.jsonl`. **memory-orchestrator** (наш код): защитный импорт `scripts.mcp_call_log` + no-op fallback, `call_tool`→тонкая обёртка `track_call`, тело в `_dispatch_tool`, error-ветки явно метят `state` (без эвристик). **1c-mcp-crud** (вендоренный сабмодуль `external/1c_mcp/` НЕ тронут): монки-патч `OneCClient.call_tool` в лаунчере `scripts/mcp_1c_stdio_launcher.py`, идемпотентный флаг `_mcp_call_logged`, `isError`→`tool_error`. **Регрессия поймана+исправлена:** `sys.path.append(project_root)` тащил регулярный пакет `<root>/src/` в скан → шедоуил namespace-пакет `external/1c_mcp/src/` → ломал `from src.py_server.main import main`; фикс — на path каталог `scripts/` + bare `import mcp_call_log`. 11 unit + code-verify quality-review PASS. **⚠ Рантайм-эффект gated на `/mcp reconnect`** (правит код серверов, stdio держит старый). Остальные 6 серверов — по мере касания. *Оценка была:* 2-3 ч на сервер.

### P3 - тяжёлый путь (опционально, после P1-P2) — ⏳ открыт (отдельным ADR)

- **P3.1 Нативный OTel Claude Code как второй источник.** `CLAUDE_CODE_ENABLE_TELEMETRY=1` + beta-traces → локальный OTLP-коллектор → Langfuse self-host (Docker, уже исследован - кеш `langfuse-llm-observability-2026`). Закрывает слепые зоны built-in без хуков; джойн с `hook-invocations.jsonl` по `tool_use_id`. Решение отдельным ADR после оценки нагрузки. *Оценка:* 1-2 дня.
- **P3.2 LLM-judge на сэмпле.** Argument Correctness / Task Completion (deepeval-паттерн) на 5-10% вызовов через `llm_complete` (z.ai, token economy). Только если P2-метрики покажут потребность. *Оценка:* 1 день.

**Порядок (исполнен):** P0.1→P0.2→P0.4 → P0.3 → P1.1 → P1.2 → P1.4 → P2.3 → P2.1+P2.2. **Все ✅ 2026-07-14** (P1.3 перекрыт P1.1+P2.2). Остаётся только **P3** — по отдельному решению/ADR.

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

### 2026-07-14 - P2.1 + P2.2 реализованы (gen_ai-алиасы + rule-слой эффективности)

- P2.1: `invocation_logger` пишет OTel-алиасы `gen_ai.tool.name`/`gen_ai.tool.call.id`/`error.type` (аддитивно, единый `err_type`) — подтверждено на живом логе.
- P2.2: single-source `scripts/tool_effectiveness.py` (pair-duration/percentile/retry-abandonment вынесены из 2 дублей) + per-server rollup (Tool Success Rate + step-efficiency) в отчёт P1.1. 90 unit + code-verify PASS. Живая находка: `edt-mcp` retry-rate 14%.
- **Ядро роадмапа закрыто** (P0, P1.1, P1.2, P1.4, P2.1, P2.2, P2.3). Осталось только: P1.3 (частично перекрыт P1.1), P3 (нативный OTel → Langfuse + LLM-judge — тяжёлый, отдельный ADR).

### 2026-07-14 - P2.3 реализован (внутренний per-call лог MCP-серверов)

- Shared stdlib-only helper `scripts/mcp_call_log.py` (`log_mcp_call`+`track_call`, ротация/fail-soft/opt-out) → `.claude/cache/mcp-<server>-calls.jsonl`. Обёрнуты memory-orchestrator (`call_tool`→`_dispatch_tool`) и 1c-mcp-crud (монки-патч `OneCClient.call_tool` в лаунчере, сабмодуль не тронут). 11 unit + code-verify PASS.
- Поймана+исправлена регрессия sys.path (корневой `src/` шедоуил namespace-`src` сабмодуля → фикс: scripts-dir на path + bare import). Рантайм-эффект gated на `/mcp reconnect`.
- Осталось: P2.1 (gen_ai.*-поля), P2.2 (rule-слой эффективности), P1.3 (частично перекрыт P1.1), P3 (OTel, LLM-judge). Остальные 6 MCP-серверов — по мере касания.

### 2026-07-14 - P1.4 реализован (memory-sinks regression в каденс)

- `memory-maintenance-cadence.py` при фаере синхронно прогоняет observability-отчёт, парсит `[REGRESSION]`-маркер, сюрфейсит замолчавшие синки в баннер. 6 unit + e2e. Живая находка: 3 stale-синка (propagation/circuit/links >7д).
- Осталось из P1.x: P1.3 (оживить tool-effectiveness — частично перекрыт P1.1). Далее P2 (gen_ai.*-поля, per-call лог MCP), P3 (OTel, LLM-judge).

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
