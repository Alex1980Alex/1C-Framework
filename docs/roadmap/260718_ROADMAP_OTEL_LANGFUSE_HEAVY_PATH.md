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

### 2026-07-18 — H-P0..H-P4 РЕАЛИЗОВАНЫ (макс-эффорт, автономно); живые данные поймали 2 бага

Полная реализация тяжёлого пути за сессию. Ключевая находка на входе: инфраструктура
ADR-022 P2 **уже развёрнута** (коллектор запущен, `enable_claude_otel.py`, эмиссия
верифицирована 2026-06-17) → расширяю существующее, а не строю параллельное.

- **H-P0.1 duration_ms-захват** (commit 3c62c7106): платформа кладёт настоящую длительность
  тула top-level полем `duration_ms` в PostToolUse (эмпирика — дамп). `extract_duration_ms`
  (Post-only, отбраковка bool/neg) + параметр `log_invocation` + оба логгера + `tool_durations`
  (предпочитает прямое паре, behavior-preserving). **Live-contract:** реальный лог несёт
  duration_ms (Bash 2057мс vs elapsed_ms хука ~20мс). 13 unit.
- **H-P1 file-exporter** (commit 495d28fa4): расширил СУЩЕСТВУЮЩИЙ коллектор (порт 4318
  занят живым → параллельный compose дал бы конфликт) — `file/logs`+`file/traces` → `data/otel/`
  (gitignored); debug-ветка ADR-022 цела. **Live:** POST синтетики → 200 → запись; нативная
  эмиссия уже течёт (OTel включён), реальные `claude_code.tool_result`.
- **H-P3 cross-check** (главная ценность): `otel_crosscheck.py` — native `tool_result` ↔
  hook unpaired-Pre по `tool_use_id` (эмпирически 100% overlap) → FN/FP/TP + latency. Секция
  в `_latest.md` (graceful). **⚠ Живые данные поймали КРИТИЧЕСКИЙ баг, что unit пропустил:**
  реальный Claude Code кодирует `success`+`duration_ms` как `stringValue` ("false"/"3879"),
  не boolValue/intValue → наивный `bool("false")`==True читал бы ВСЕ провалы как успех
  (NB1-класс на OTel-парсинге). Фикс `_coerce_bool`/`_coerce_int` (саботаж-тест на реальной
  кодировке). **Результат:** детектор unpaired-Pre идеально согласован с native (0 FN, 0 FP,
  1 TP); latency native↔hook-direct дельта **0мс** на 25 совпадений (H-P0.1 захват точен
  бит-в-бит), native↔пэйринг p50 227мс / **max 9888мс** (ошибка FIFO-пары, которую H-P0.1
  убирает). 13 unit.
- **H-P4 LLM-judge** (commit 563d02833): `tool_llm_judge.py` — stratified sample (все провалы
  + детерминированный хеш-сэмпл успехов) → рубрики Argument Correctness/Task Completion →
  robust JSON-разбор → jsonl + опц. Langfuse Scores; default-судья = LLMRotationService
  (z.ai). Advisory-only, content off by default → активация осознанна. 11 unit (fake-судья).
- **H-P0.2 ADR-052** (топология fan-out / ретеншн / безопасность): коллектор = единственный
  fan-out (у Claude ОДИН OTLP-endpoint); Langfuse opt-in (не default — RAM ~3ГБ, H-P3 не
  требует); контент OFF; localhost-bind; секреты в gitignored `.env.otel`.
- **H-P2 Langfuse self-host**: `docker-compose.langfuse.yml` (эталонный, порты на 127.0.0.1),
  `.env.otel.example`, `otel-collector-langfuse.yaml` (fan-out overlay, сохраняет file-путь
  H-P3), `langfuse_up.py` (генерит секреты, up, ждёт health, пересоздаёт коллектор). Probe-таргет
  (severity=info, gated на `.env.otel`). Compose config валиден, статус bring-up — см. ниже.
- **H-P2 END-TO-END ВЕРИФИЦИРОВАН на живом стеке:** 6 контейнеров up (ClickHouse healthy),
  langfuse-web health 200, коллектор форвардит нативную эмиссию Claude Code → Langfuse
  (2 трейса в `/api/public/traces`), file-путь H-P3 сохранён (fan-out). Bring-up вскрыл 3
  правки (email-валидация / ClickHouse-порт 9000 занят SonarQube → 9010 / `otlphttp`→`otlp_http`).
- **code-verify (read-only ревьюер) → PARTIAL → все закрыты:** must-fix краш `render_md`
  `KeyError('info')` (Langfuse-severity протекал в `_VERDICT_MARK`) + 3 minor (missing-success
  манфактурил FN / 2× fd-утечка urlopen / F541). 3 регресс-теста.
- **Итог кода:** 40 unit (H-P0.1+H-P3+H-P4+фиксы) + 157 tool-obs зелёные, ruff clean. Коммиты
  3c62c7106 (H-P0.1), 495d28fa4 (H-P1), 61862dc55 (H-P2), 904b18708 (bring-up фиксы), 881fccd85
  (code-verify) + auto-save absorb. Langfuse оставлен запущенным (opt-in, `langfuse_up.py down`
  останавливает). ⚠ MCP-серверных правок нет.

### 2026-07-18 — Роадмап создан (триггер ADR-051 сработал)

- Мандат пользователя = триггер (б)+(в) ADR-051; тяжёлый путь переходит из deferred в план.
- Research переиспользован из кешей 2026-05-22/2026-06-17 (вкл. эмпирическую верификацию нативной
  эмиссии — спаны/метрики/события реально приходили в локальный коллектор, гл. 42.8).
- Декомпозиция H-P0..H-P4; точка минимальной ценности = H-P1+H-P3 (сверка без Langfuse возможна).
- Реализация не начата (roadmap-only). Следующий шаг: H-P0.1 (`duration_ms`-захват) + ADR-052.
