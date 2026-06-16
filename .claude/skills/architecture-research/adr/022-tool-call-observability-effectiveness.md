# ADR-022: Достоверная observability и оценка эффективности tool-call'ов

**Дата:** 2026-06-17
**Статус:** accepted
**Исследование:** [../cache/tool-call-observability-effectiveness-2026.md](../cache/tool-call-observability-effectiveness-2026.md)

## Контекст

Подсистема логирования инструментов (`data/hook-invocations.jsonl` + `tool_usage_report.py` + `audit_query.py`) имеет широкий охват, но **недостоверна для оценки эффективности** (аудит 2026-06-17):

- **MCP-тулы логируются только на `PreToolUse`** (`settings.json` matcher `mcp__.*` висел лишь в PreToolUse) → 0 Post-строк → ветка классификации ошибок мёртвая, ошибки MCP не ловятся, Pre/Post-разностью латентность не посчитать.
- **`elapsed_ms` = время хука-наблюдателя, а не инструмента** (`BaseHook.elapsed_ms` от `__init__`). ~20 ms у всех тулов, включая `update_database`. `tool_usage_report` суммирует это как «латентность», `audit_query latency-p95` считает p95 по тому же полю + мешает overhead хуков с бизнес-длительностью слэш-ранов (нет фильтра по `category`).
- **Нативные тулы** (Read/Write/Bash/…) видны лишь косвенно как триггер N хуков → `calls` = число наблюдателей, не вызовов; латентности нет вовсе.
- **Нет связки «вызов → исход»**; `causationid` спроектирован, но не заполняется; `tool_call_id` отсутствует как join-ключ.

Внешняя практика (OTel GenAI `execute_tool`, **встроенный OTel Claude Code** `claude_code.tool.execution`, LangSmith/Langfuse, deepeval/MCP-Bench): реальная длительность из start/end спана; структурный низкокардинальный `error.type`/`success`; стабильный `tool_call_id`(=`gen_ai.tool.call.id`); эффективность = детерминированные правила (success-rate, retry/abandonment, tool-selection) + LLM-judge, пришпиленные к трейсу; cost-per-tool.

**Ключевой факт:** Claude Code уже эмитит точную телеметрию инструментов нативно (`CLAUDE_CODE_ENABLE_TELEMETRY=1`) — хук-логгер этого в принципе не может (меряет себя).

## Решение

Трёхфазная адаптация (JSONL-first с OTel-совместимыми именами; тяжёлый OTel — opt-in).

**P0 (lightweight, сейчас) — сделать существующие метрики честными:**
1. Добавить matcher `mcp__.*` в `PostToolUse` → включается классификация ошибок MCP + появляется Pre/Post-пара.
2. `tool_usage_report.aggregate()` — реальная латентность MCP через пару `ts(post) − ts(pre)` (join по `tool_call_id`, fallback FIFO по `(session, tool, correlationid)`); `calls` MCP дедуплицируются (Pre+Post = один вызов); флаг `latency_real`. Для не-MCP (overhead хука) латентность помечается `~`/`n/a`, не выдаётся за время инструмента.
3. `audit_query.py` — `latency-p95` исключает `category='slash_run'`; добавлен view `mcp-latency` (реальная длительность через LAG-pairing Pre/Post).
4. OTel-совместимые поля в записи лога: `tool_call_id`(=`tool_use_id`), `success`, `error_type` → апгрейд в OTel = переименование, не переписывание.

**P1 (deterministic, следующий срез):** retry/abandonment-счётчик (повтор тул+аргументы в run_id); tool-success-rate; связка «инструменты этапа → verify-PASS/FAIL» в `LOOPS.md`/`tool_usage_report`.

**P2 (opt-in, heavy):** включить встроенный OTel Claude Code (`CLAUDE_CODE_ENABLE_TELEMETRY=1`) → локальный Langfuse self-host (MIT, OTLP) / SigNoz: точные спаны, cost-per-tool, цепочки субагентов, online LLM-judge на сэмпле. JSONL остаётся лёгким hot-path'ом. Подключить лежащий без дела `otel_exporter.py` как мост (или полагаться на нативную эмиссию).

> **Реализовано (scaffold, 2026-06-17, opt-in default OFF):** тоггл `scripts/otel/enable_claude_otel.py`
> (`--console` zero-infra / `--otlp <endpoint>` +Langfuse Basic-auth / `--disable` / `--status`) пишет
> OTel-env в gitignored `settings.local.json` — team `settings.json` не трогается. How-to —
> `docs/framework documentation/42_MONITOR_CI/42.8_Claude_Code_OTel_Tool_Telemetry.md`. Бэкенд
> (Langfuse/SigNoz) НЕ вендорится в репо (тяжёлый, версионируется) — поднимается официально по how-to.
> Тоггл верифицирован (console/otlp/disable + сохранность чужого env, cp1251-safe вывод); сквозная
> эмиссия OTel — за пользователем при opt-in (из скрипта/хука не проверяема).

## Последствия

**Положительные:** ошибки и латентность MCP становятся достоверными за P0 (часы); метрики перестают вводить в заблуждение; поля готовы к OTel-миграции; P2 даёт точную телеметрию без потолка хук-логгера.

**Отрицательные/риски:** P0.1 удваивает mcp-строки в логе (Pre+Post) — учтено дедупом в `aggregate`; latency реальна только когда сработал Post (известный баг PostToolUse #6305 — деградирует в `n/a`, не врёт). Нативная латентность по-прежнему недоступна в JSONL — закрывается только P2 (OTel `tool_result.duration_ms`). P2 тянет инфру (Docker-бэкенд) — потому opt-in.

## Альтернативы

- **Выделенный native-tool логгер** (зеркало mcp-invocation-logger) — даёт честный счёт нативных вызовов, но не латентность (тот же overhead-таймер); P2/OTel решает обе → отклонено в пользу OTel для нативных.
- **Сразу полный OTel-бэкенд** — точнее всего, но тянет инфру немедленно; не оправдано, пока JSONL+DuckDB покрывают success-rate/retry/cost/корреляцию → OTel сделан opt-in (P2).
- **Оставить как есть** — отклонено: «латентность»/«ошибки» в отчётах активно вводят в заблуждение.

## Связанные файлы

`.claude/settings.json` (PostToolUse matcher), `.claude/hooks/shared/invocation_logger.py`, `.claude/hooks/mcp-invocation-logger.py`, `scripts/tool_usage_report.py`, `scripts/audit_query.py`, `tests/unit/test_tool_usage_report.py`. Расширяет §15 observability (CloudEvents/traceparent); потенциально активирует `.claude/hooks/shared/otel_exporter.py` (P2).
