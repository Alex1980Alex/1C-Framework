# Пайплайн (trivial-трек) — ADR-022 P2: верификация сквозной OTel-эмиссии Claude Code

**Тип:** trivial (диагностика + правка одного дока по ground-truth). Цепочка Планирование→Дизайн→Кодирование→Тестирование в компактной форме.

## Планирование
Прошлая сессия включила opt-in OTel (`settings.local.json`: `CLAUDE_CODE_ENABLE_TELEMETRY=1` + `ENHANCED_TELEMETRY_BETA=1` + OTLP→`localhost:4318`) и подняла otel-collector, но рестарт был преждевременным (env ещё не читался). Открытый вопрос: реально ли `claude` эмитит спаны (`claude_code.tool.execution`) — в офиц. доках beta-флаг не нашёлся, формулировка дока 42.8 была под сомнением.

## Дизайн
После рестарта `claude` (env активен, коллектор поднят) → собрать ground-truth из `docker logs claude-otel-collector`: классифицировать сигналы (spans vs metrics vs events), сверить КАЖДОЕ имя из таблицы дока 42.8 с фактической эмиссией, исправить док по факту (не по догадке). Источник истины — живая эмиссия, не доки.

## Кодирование (фактически — верификация + правка дока)
- **Подтверждено живьём** (сессия Claude Code `2.1.179`): полное дерево спанов под одним `Trace ID` (`llm_request`→`tool`→`tool.execution`+`tool.blocked_on_user`, scope `com.anthropic.claude_code.tracing 1.0.0`); метрики `cost.usage`/`token.usage`/`active_time.total`/`session.count`; события `tool_result`/`tool_decision`/`api_request`/`hook_execution_*`/`mcp_server_connection`/`user_prompt`. Beta-флаг → трейсы РАБОТАЮТ.
- **Honest-коррекция дока:** `claude_code.cost.usage` атрибутируется по `model`+`query_source`, **НЕ** по `mcp_tool.name`/`skill.name` (подтверждено и офиц. monitoring docs «стоимость по модели») → строка 16 таблицы 42.8 переписана; per-тул cost = джойн через трейс по `tool_use_id`.
- **3 правки** в `docs/framework documentation/42_MONITOR_CI/42.8_Claude_Code_OTel_Tool_Telemetry.md`: (1) строка cost-атрибуции + уточняющий блок; (2) §2а — «верифицирована end-to-end» с точным контрактом имён; (3) «⚠ Граница верификации» → «✅ закрыта».
- `scripts/otel/enable_claude_otel.py` — правка НЕ нужна (env-имена доказаны рабочими; коммент про spans подтверждён фактом).

## Тестирование
- Ground-truth получен из реального приёма коллектором (не синтетика): `docker logs` показал ResourceSpans/ResourceMetrics/ResourceLog с реальными `session.id`/`request_id`.
- Markdown-таблица дока перечитана после правки — валидна.
- Контракт имён сверён 1:1 с эмиссией — все заявленные доком имена подтверждены; единственный overclaim (cost per-tool) исправлен.
