# Дизайн: тяжёлый путь OTel→Langfuse (H-P0..H-P4)

**Статус:** approved (self-approve — мандат пользователя «реализуй всё без промежуточных одобрений»).

## Ревизия существующего (H-P0.3) — что переиспользуем

Аудит вскрыл, что инфраструктура ADR-022 P2 **уже существует и работает**:
- `claude-otel-collector` (контейнер, up 2 дня), `docker-compose.otel-collector.yml`, `otel-collector.yaml` (только `debug`-exporter).
- Тоггл `scripts/otel/enable_claude_otel.py` (console/otlp/disable/status, пишет в `settings.local.json`, реверсивен).
- Эмиссия верифицирована end-to-end 2026-06-17 (гл. 42.8): спаны `claude_code.tool.execution`, события `claude_code.tool_result` (несут `success`/`duration_ms`/`error_type`/`tool_use_id`).
- `duration_ms` в PostToolUse-payload **эмпирически подтверждён** (дамп tool-response-shapes.jsonl).

**Решение-отклонение от роадмапа:** НЕ создавать параллельный `docker-compose.otel.yml` (порт 4317/4318 занят живым коллектором → конфликт). Вместо этого **расширяю существующий** `otel-collector.yaml` (добавляю `file`-exporter → `data/otel/`) — паттерн «reuse beats rebuild» (память [[project_roadmap_audit_pattern]]). Дешевле и не плодит конкурирующую инфру.

## Компоненты

| Фаза | Файл(ы) | Что |
|---|---|---|
| H-P0.1 | `shared/invocation_logger.py`, `tool-invocation-logger.py`, `mcp-invocation-logger.py`, `tool_effectiveness.py` | `duration_ms`-параметр в `log_invocation`; логгеры читают его из PostToolUse-payload; `pair_durations` предпочитает прямой при наличии |
| H-P0.2 | `adr/052-otel-langfuse-topology-retention-security.md` | топология/ретеншн/безопасность |
| H-P1 | `otel-collector.yaml`, `docker-compose.otel-collector.yml` | `file`-exporter → `data/otel/claude-otel.jsonl` (logs+traces), volume mount |
| H-P2 | `docker-compose.langfuse.yml`, `.env.otel.example`, `scripts/otel/langfuse_up.py` | Langfuse self-host (pinned images); wiring через `enable_claude_otel --otlp langfuse` |
| H-P3 | `scripts/otel_crosscheck.py`, `analyze_tool_health.py` (секция), `probe_mcp_health.py` (langfuse-таргет) | join native `tool_result` ↔ hook unpaired-Pre → FP/FN числами → секция отчёта |
| H-P4 | `scripts/tool_llm_judge.py` | сэмпл 5-10% → llm_complete-судья → Scores + jsonl |

## Контракт данных для H-P3 (главная ценность)

Native источник = `data/otel/claude-otel.jsonl` (OTLP JSON от file-exporter). Ключевой сигнал —
log-события `claude_code.tool_result` с плоскими атрибутами `tool_name`/`tool_use_id`/`success`/
`duration_ms`/`error_type`. Hook источник = `hook-invocations.jsonl` (canonical `tool_call`/`mcp_call`).
Join по `tool_use_id`(native) ↔ `tool_call_id`(hook) = `gen_ai.tool.call.id`.

Отчёт cross-check: (а) OTel-провалы без unpaired-Pre = **наши FN**; (б) unpaired-Pre без OTel-провала
= **наши FP**; (в) дельта латентности pairing vs native `duration_ms`; (г) покрытие.

## Инварианты безопасности

- Всё opt-in в `settings.local.json` (team `settings.json` не трогаем); реверс = `enable_claude_otel --disable` + `docker compose down`.
- Контент-флаги (промпты/args/result) OFF по умолчанию (PII); `user.email` в resource attrs → localhost-only bind, `.env.otel` gitignored.
- H-P3 работает по file-сырцу БЕЗ Langfuse → H-P2 не блокирует главную ценность.
- Все новые скрипты graceful: нет сырца → секция отсутствует, поведение как сегодня.
- Langfuse-probe severity=info (down ≠ деградация разработки).

## Порядок

H-P0.1 → H-P1 (file-exporter, bring-up, verify) → H-P3 (crosscheck+report+probe) → H-P4 → H-P2 (артефакты) → ADR-052 → docs → verify → commit.
