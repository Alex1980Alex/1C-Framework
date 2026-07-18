# 260718 — Тяжёлый путь tool-observability: нативный OTel → Langfuse self-host + LLM-judge

> Активация отложенного пути [ADR-051](../../.claude/skills/architecture-research/adr/051-tool-observability-heavy-path-gating.md).
> **Триггер сработал 2026-07-18**: явный мандат пользователя (= триггер (б) «независимый второй
> источник built-in-покрытия» + (в) «внешнее требование»). Продолжение
> [260718_ROADMAP_TOOL_OBSERVABILITY_NEXT.md](260718_ROADMAP_TOOL_OBSERVABILITY_NEXT.md).
> Research-база: кеши [`tool-call-observability-effectiveness-2026`](../../.claude/skills/architecture-research/cache/tool-call-observability-effectiveness-2026.md)
> (вкл. **EMPIRICAL GROUND-TRUTH** — нативная эмиссия верифицирована живьём 2026-06-17, гл. 42.8) +
> [`langfuse-llm-observability-2026`](../../.claude/skills/architecture-research/cache/langfuse-llm-observability-2026.md).

## §1 Зачем (что тяжёлый путь даёт, чего лёгкий не может)

Лёгкий контур (hook-JSONL + `analyze_tool_health.py`) после N-P0.1 честен, но с известными
слепыми зонами (см. диалог 2026-07-18):

| Слепая зона лёгкого пути | Что даёт нативный OTel |
|---|---|
| Провал built-in = **непарный Pre** (косвенный сигнал): не различает тип провала, завышается обрывом сессии, «висящий вызов» = ложный непарный | Событие `claude_code.tool_result` несёт **прямые** `success`, `error_type`, `duration_ms` per-call [web, верифицировано эмиссией 2026-06-17] |
| `elapsed_ms` = время хука; латентность только из Pre→Post pairing | Спан `claude_code.tool.execution` — реальная длительность + **split «ожидание разрешения» (`tool.blocked_on_user`) vs исполнение** |
| Нет кросс-сессионной корреляции за пределами JSONL-окна | Trace ID + `session.id`/`prompt.id`/`tool_use_id`; цепочка делегирования субагентов = один трейс |
| Cost неатрибутируем | `claude_code.cost.usage`/`token.usage` per-модель; per-тул cost через trace-джойн |
| Семантика («правильные ли аргументы», «решена ли задача») — вне rule-слоя | Слой LLM-judge (Argument Correctness / Task Completion) поверх трейсов, на сэмпле |

**Главная ценность для нас — H-P3**: независимая сверка нативных `success`-меток с нашим
unpaired-Pre детектом = валидация/калибровка всего decision layer (NB1-класс закрыт навсегда
вторым источником).

## §2 Архитектура (целевая)

```
Claude Code (нативная эмиссия, opt-in env)
  │ OTLP http/protobuf → localhost:4318
  ▼
otel-collector (Docker, уже отработан в 42.8)
  ├─ exporter otlphttp → Langfuse /api/public/otel  (трейсы; HTTP, gRPC у Langfuse нет)
  └─ exporter file     → data/otel/*.jsonl          (сырец: события/метрики для DuckDB-сверки)
       ▼
Langfuse self-host (Docker Compose: web + worker + Postgres + ClickHouse + Redis/S3-minio)
  ├─ UI: трейсы, P50/P99, sessions, per-agent
  └─ Scores ← H-P4 LLM-judge (llm_complete / z.ai, сэмпл 5–10%)

Сверка (H-P3): scripts/otel_crosscheck.py — join `tool_use_id` ↔ `gen_ai.tool.call.id`
  (hook-invocations.jsonl ↔ data/otel/*.jsonl) → секция в data/reports/tools/_latest.md
```

Ключевые факты, снимающие риски заранее [web+exp, кеш]:
- Трейсы = beta: `CLAUDE_CODE_ENABLE_TELEMETRY=1` + `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1` — **реально работают** (проверено эмиссией).
- Контент (промпты/args/results) **off по умолчанию** — включать не планируем (секреты/PII: resource attrs уже несут `user.email` → ретеншн/доступ учесть в ADR-052).
- Langfuse принимает OTLP только **http** (`/api/public/otel`), маппит `gen_ai.*` сам (v3.22+).
- Cost per-tool НЕ атрибут метрики — только trace-джойн (не обещать дашборд «cost per tool» из коробки).

## §3 Декомпозиция

### H-P0 — Подготовка (без инфраструктуры) *(~2-3ч)*

- **H-P0.1 `duration_ms`-захват** (одобрен ADR-051 как дешёвый предшественник, делается ПЕРВЫМ
  и независимо от остального): `tool-invocation-logger`/`mcp-invocation-logger` читают
  `PostToolUse.duration_ms` → аддитивное поле; `pair_durations` предпочитает его паре.
  Acceptance: поле в canonical-строках; p95 в отчёте считается из него при наличии. Unit + live-зонд.
- **H-P0.2 ADR-052 «OTel-топология, ретеншн, безопасность»** (требование ADR-051 при срабатывании
  триггера): выбор компонентов (§2), ретеншн (предложение: Langfuse 30д, file-сырец 14д ротацией),
  безопасность (localhost-only bind, creds в gitignored `.env.otel`, `user.email` в resource attrs,
  контент-флаги остаются OFF), нагрузка (ClickHouse ~2ГБ RAM — оценить на машине), реверс.
- **H-P0.3 Ревизия гл. 42.8** (операционка эксперимента 2026-06-17): что переиспользуем
  (конфиг коллектора, env-флаги), что устарело (версия Claude Code, имена спанов — быстрая сверка).

### H-P1 — Нативная эмиссия → коллектор *(~2-4ч, повтор отработанного 42.8)*

- **H-P1.1** `otel-collector` контейнер: `docker/docker-compose.otel.yml` (receiver otlp :4318,
  экспортеры file + debug; Langfuse-экспортер добавится в H-P2). Ротация file-exporter.
- **H-P1.2** Включение эмиссии **локально** (`settings.local.json` env, team `settings.json` не трогаем):
  `CLAUDE_CODE_ENABLE_TELEMETRY=1`, `CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1`,
  `OTEL_{METRICS,LOGS,TRACES}_EXPORTER=otlp`, `OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf`,
  `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318`. Graceful: коллектор down → Claude Code
  работает как раньше (проверить, что нет блокировки/латентности старта).
- **H-P1.3** Smoke: сессия → `data/otel/` содержит `claude_code.tool_result` с
  `success`/`error_type`/`duration_ms` и спаны `tool.execution`. Зонд «Bash exit 42» →
  `success=false` в нативном событии (то, чего hook-путь не видит в принципе).
- Acceptance H-P1: зонд-провал виден в нативном сырце; overhead старта сессии не вырос заметно.

### H-P2 — Langfuse self-host *(~3-5ч, операционный)*

- **H-P2.1** `docker/docker-compose.langfuse.yml` (официальный compose: web/worker/Postgres/
  ClickHouse/Redis/minio), порты localhost-only, креды в `.env.otel` (gitignored),
  headless-init (org/project/API-keys через env).
- **H-P2.2** Коллектор += exporter `otlphttp` → `http://localhost:3000/api/public/otel`
  (Basic auth pk/sk). Проверка маппинга: `claude_code.tool`-спаны видны как observations,
  сессии группируются по `session.id`.
- **H-P2.3** Операционка: старт по требованию (не автозапуск с ОС), ретеншн-джоб из ADR-052,
  строка в probe (`probe_mcp_health.py` += Langfuse `/api/public/health`, severity=info —
  down ≠ деградация разработки).
- Acceptance H-P2: живой трейс сессии открывается в UI; P50/P99 по `tool_name` доступны;
  сервисы переживают перезапуск Docker.

### H-P3 — Сверка native ↔ hook-JSONL (главная ценность) *(~3-4ч)*

- **H-P3.1** `scripts/otel_crosscheck.py` (stdlib/DuckDB): join `tool_use_id` ↔
  `gen_ai.tool.call.id`; отчёт: (а) провалы, видимые OTel но не unpaired-Pre (наши FN);
  (б) unpaired-Pre без OTel-провала (наши FP — обрыв сессии/висящие); (в) дельта латентности
  pairing vs `tool.execution`; (г) покрытие (доля вызовов с обеих сторон).
- **H-P3.2** Секция «OTel cross-check» в `data/reports/tools/_latest.md` (через
  `analyze_tool_health` при наличии сырца; нет сырца → секции нет, поведение прежнее).
- **H-P3.3** По результатам — калибровка unpaired-Pre (исключение хвоста сессии? порог висящих?)
  отдельным решением, НЕ автоматически.
- Acceptance H-P3: отчёт числами отвечает «насколько врёт/честен unpaired-Pre» (FP/FN rate);
  регресс-unit на join.

### H-P4 — LLM-judge на сэмпле *(~3-4ч, только после H-P3)*

- **H-P4.1** `scripts/tool_llm_judge.py`: сэмпл 5–10% завершённых tool-call'ов (стратифицированный:
  все провалы + случайные успехи), судья через `llm_complete` (z.ai, token-economy [[feedback-delegation-aggressive]]),
  метрики Argument Correctness + Task Completion (deepeval-рубрики из кеша), выход —
  Langfuse Scores API (`{name, value, comment}` на observation) + локальный jsonl.
- **H-P4.2** Каденс: detached после Stop с cooldown 24ч (паттерн `tool-health-analyzer-stop`),
  бюджет-кап вызовов/день; opt-out env.
- **H-P4.3** Потребитель: секция «semantic flags» в `_latest.md` (только surfacing, вердикты
  rule-слоя judge НЕ двигает — advisory, лестница как ADR-035).
- Acceptance H-P4: ≥1 живая находка класса «вызов успешен, но аргументы/результат сомнительны»,
  недостижимая rule-слоем; расход в бюджете.

## §4 Порядок, оценка, риски

**Порядок:** H-P0.1 (сразу, независим) → H-P0.2/H-P0.3 → H-P1 → H-P2 → H-P3 → H-P4.
Точка «минимальной ценности» = H-P1+H-P3 (сверка возможна и по file-сырцу БЕЗ Langfuse —
если H-P2 задержится, H-P3 не блокируется, джойнить `data/otel/*.jsonl` напрямую).

**Оценка:** ~2 рабочих сессии (H-P0..H-P1 + smoke; H-P2..H-P3), H-P4 — третья по потребности.

| Риск | Митигация |
|---|---|
| ClickHouse/Compose тяжёлые для машины | замер в H-P0.2; fallback — остаться на file-сырце + DuckDB (H-P3 работает без Langfuse) |
| Beta-статус enhanced telemetry: формат спанов может дрейфовать | file-сырец + версия-в-отчёте; cross-check ломается громко (unit на схему) |
| Секреты/PII (`user.email`, промпты) | контент-флаги OFF; localhost-only; `.env.otel` gitignored; ретеншн в ADR-052 |
| Инфра-footprint в код-сессиях (возражение ADR-051 §2) | старт по требованию; вся телеметрия opt-in в `settings.local.json`; реверс = снять env + `docker compose down` |
| Judge-шум/расход | сэмпл + кап + advisory-only (не двигает вердикты) |

## §5 Acceptance роадмапа целиком

1. Зонд «Bash exit 42» виден как `success=false` в **нативном** источнике (лёгкий путь его не видит).
2. Cross-check отчёт числами: FP/FN-rate unpaired-Pre детекта, дельта латентности.
3. Живой трейс в Langfuse UI (session → tools → субагенты одним деревом).
4. LLM-judge даёт ≥1 семантическую находку на сэмпле в рамках бюджета (H-P4, отложенный критерий).
5. Полный реверс документирован и проверен (env снят + контейнеры down → контур = сегодняшний лёгкий путь).

## §18 Progress Log

> Append-only, reverse-chronological.

### 2026-07-18 — Роадмап создан (триггер ADR-051 сработал)

- Мандат пользователя = триггер (б)+(в) ADR-051; тяжёлый путь переходит из deferred в план.
- Research переиспользован из кешей 2026-05-22/2026-06-17 (вкл. эмпирическую верификацию нативной
  эмиссии — спаны/метрики/события реально приходили в локальный коллектор, гл. 42.8).
- Декомпозиция H-P0..H-P4; точка минимальной ценности = H-P1+H-P3 (сверка без Langfuse возможна).
- Реализация не начата (roadmap-only). Следующий шаг: H-P0.1 (`duration_ms`-захват) + ADR-052.
