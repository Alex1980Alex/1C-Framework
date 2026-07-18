# 260718 — Tool Observability NEXT: аудит реализации 260713 + дорожная карта досборки

> Продолжение [260713_ROADMAP_TOOL_OBSERVABILITY_AUDIT.md](260713_ROADMAP_TOOL_OBSERVABILITY_AUDIT.md).
> Аудит 2026-07-18: 3 параллельных верификационных агента (P0/P1/P2 срезы, все claims сверены с кодом
> file:line) + проверка ЖИВЫХ данных контура (свежесть артефактов, распределение вердиктов,
> эмпирический зонд error-детекта). Вывод: **код P0–P2 реализован как заявлено, контур крутится,
> но живые данные вскрыли 3 дефекта класса «метрики снова врут» + §6 decision layer собран наполовину.**

## §1 Что подтверждено реализованным (verified 2026-07-18)

| Блок | Вердикт аудита | Живое доказательство |
|---|---|---|
| P0 корректность лога (B1–B5) | ✅ CONFIRMED полностью | `detected_event` по `tool_response`; `agent_id` теперь ЗАПОЛНЯЕТСЯ платформой (256 canonical-строк с agent_id в последних 5k); canonical `tool_call` 964 строк / `mcp_call` 120 в последних 5k; Pre/Post паритет 486/478 |
| P1.1 decision layer | ✅ код CONFIRMED (см. §2 расхождения) | Отчёт `_latest.md` свежий (22ч при cooldown 24ч); verdicts.jsonl 672 строки; ratchet/TTL/reset-baseline/rotation — всё в коде |
| P1.2 MCP health-probe | ✅ CONFIRMED | `mcp-health.jsonl` свежесть 0.5ч — probe реально фаерится на SessionStart |
| P1.4 memory-sinks regression | ✅ CONFIRMED | `[REGRESSION]`-парсер в каденсе; throttle = Stop×N сессий (осознанно) |
| P2.1 gen_ai.* алиасы | ✅ CONFIRMED | Живые строки несут `gen_ai.tool.name`/`gen_ai.tool.call.id`/`error.type` |
| P2.2 rule-слой + rollup | ✅ CONFIRMED | Sidecar `servers`: 8 серверов, edt-mcp step_efficiency 0.40 (retry-hotspot жив) |
| P2.3 per-call лог (2 сервера) | ✅ CONFIRMED + работает | `.claude/cache/mcp-memory-orchestrator-calls.jsonl` (0.4ч), `mcp-1c-mcp-crud-calls.jsonl` + `-mfm-` (инстансы НЕ слились — `_instance_slug` работает) |

Минорный дрейф (не баги): §1.3 таблица покрытия в 260713 описывает ДО-P0 состояние (Read/Grep/Glob
«только Pre» — уже неправда, покрыты Pre+Post); `_CANONICAL_CATEGORIES` в `audit_query.py` — инлайн-литерал,
константа живёт только в `tool_usage_report.py:45`.

## §2 Найденные дефекты (NB — new bugs, по живым данным)

### NB1 🔴 CRITICAL — error-детект built-in мёртв на живом payload → success_rate=1.0 везде

**Эмпирически доказано зондом 2026-07-18:** Bash-команда `exit 42` → canonical строка
`outcome=allow success=True error_type=''`. На всём окне: **164/164 Bash Post = success**, включая
реальные фейлы (jq exit 127, UnicodeEncodeError). Все 1526 built-in вызовов — 0 ошибок; все server
rollups — error_rate 0.0.

- Код `_classify_outcome` ([tool-invocation-logger.py:127-165](../../.claude/hooks/tool-invocation-logger.py))
  ждёт `exit_code`/`exitCode` int в dict `tool_response` — живой payload Claude Code этой формы
  **не несёт** (юнит-тест кормит фикстуру нужной формы → зелёный, live — мимо).
- **Каскад:** error_rate≡0 → вердикты `broken` (success-rate<50%) и `ineffective` (abandonment
  error-based) **недостижимы в принципе** → авто-эскалация broken никогда не сработает →
  decision layer слеп к реальным отказам. Держится только `degraded` по латентности (см. NB2 — и тот FP).
- Урок класса [[feedback-deterministic-test-robustness]]: форма hook-payload — контракт ПЛАТФОРМЫ,
  юнит-фикстура его не пинит; нужен live-контракт-тест.

### NB2 🟠 HIGH — degraded по p95×2-baseline = FP-фабрика на content-variable инструментах

Живой прогон: **все 6 degraded** — чисто латентностные при success_rate=1.0:
`Bash p95 65901ms > 2× baseline 1236ms`, `Grep 3996 vs 230`, `Read 408 vs 189`, `Skill`, `TaskUpdate`,
`execute_code 4956 vs 1876`. Длительность Bash/Grep/Read/execute_code определяется СОДЕРЖИМЫМ вызова
(pytest-прогон ≠ echo), а не здоровьем инструмента — baseline, пойманный на «лёгком» окне, красит
любое рабочее окно в degraded. Баннер кричит волк → alert fatigue, реальный сигнал утонет.

### NB3 🟠 HIGH — «окно 14 дней» фактически ~1 день: ротация съедает данные, аналайзер архив не читает

Живой лог `hook-invocations.jsonl` начинается `2026-07-17T17:28` (~12ч истории на момент аудита);
скорость записи ~8МБ/день при cap ротации 10МБ; `hook-invocations.1.jsonl` (10.4МБ) аналайзером
**не читается**. `window_incomplete=True` честно проставлен, но вердикты (особенно **unused=18**,
вкл. WebSearch) посчитаны на сутках данных → unused-вердикты в основном FP, TTL-prune и будущий
месячный отчёт «кандидаты на отключение» дадут мусор.

### NB4 🟡 MED — §6.1/§6.3 decision layer реализован наполовину (роадмап 260713 over-claims)

- §6.1: из 4 условий `broken` реализованы только 2 (success-rate). Условия **«MCP health_check down
  ≥2 дня»** и **«sink freshness-регрессия»** молча выброшены — probe (P1.2) и sink-детектор (P1.4)
  живут параллельными потоками и **в вердикты не сходятся**.
- §6.3: `verdicts.jsonl` — **write-only** (читателей нет). «Повторный broken за 30д → needs-human p1»
  и «re-verify после фикса на свежем окне» — не реализованы (re-verify существует только как текст
  внутри авто-задачи).
- §6.1 unused → «месячный отчёт кандидатов на отключение» — нет потребителя.

### NB5 🟡 MED — probe-покрытие узкое: 1С-контур не пробится вообще

`probe_mcp_health.py` покрывает 4 инфра-зависимости (Qdrant/TEI/2×SQLite). Без покрытия: **все 5
инстансов 1c-mcp-crud** (HTTP-бэкенд Apache — пробится дёшево `MCP_ONEC_URL`), edt-mcp (retry-hotspot
40%!), codepilot1c, skill-learning, auto-documenter, bsl-debugger. RDBG — осознанно исключён (on-demand).

### NB6 🟢 LOW — хвосты

- `tool-effectiveness.jsonl` stale 32 дня; писатель ручной; напоминание в `onec-task-completion-stop`
  до сих пор указывает на мёртвый файл → решить судьбу (ретирнуть или автоматизировать).
- `elapsed_ms` canonical-строки = время хука (~20мс), не инструмента (реальная латентность — только
  Pre→Post pairing; аналайзер так и считает, но поле в логе вводит в заблуждение).
- `agent_id` теперь течёт (платформа начала слать) — потребителя нет (мониторинг делегирования
  из 260713 B2 стал ВОЗМОЖЕН, но не построен).
- Doc-drift §1.3 таблицы покрытия 260713 + отсутствие `_CANONICAL_CATEGORIES` в audit_query.

## §3 Дорожная карта NEXT (декомпозиция)

### N-P0 — данные снова честные (без этого вердикты врут; приоритет над всем)

- **N-P0.1 Реанимировать error-детект built-in (NB1).** *~2-4ч.*
  1. Захват живой формы payload: временный debug-дамп `tool_response` (первые N вызовов,
     `TOOL_LOGGER_DEBUG_DUMP=1` → `.claude/cache/tool-response-shapes.jsonl`, авто-выкл по N) —
     НЕ чинить вслепую.
  2. Расширить `_classify_outcome` под фактическую форму (кандидаты: string-ответ с префиксом
     `Exit code N`, вложенный `tool_result.content[].text`, top-level поля) — только после п.1.
  3. **Live-контракт-тест** (класс NB1 навсегда): pytest-marker `live`, реальный проход зонда
     «упавший Bash → в логе outcome=error» + саботаж-проверка.
  4. Acceptance: на свежем окне error_rate(Bash) > 0 при наличии реальных фейлов; вердикт
     `broken` достижим (синтетический прогон).
- **N-P0.2 Реальное окно анализа (NB3).** *~1-2ч.*
  1. `iter_window_rows` читает `hook-invocations.1.jsonl` (и `.2` при появлении) до покрытия окна.
  2. Поднять хранение: ротация в 2-3 нумерованных архива (сейчас 1) ИЛИ поднять cap — расчёт от
     ~8МБ/день × 14д ≈ 110МБ → компромисс: окно 7д + 3 архива по 10МБ (задокументировать выбор).
  3. Acceptance: `window_incomplete=False` на целевом окне; количество unused-вердиктов падает
     (пересчёт на полном окне).
- **N-P0.3 Убрать p95-FP (NB2).** *~1-2ч.*
  1. Классифицировать инструменты: `CONTENT_VARIABLE = {Bash, PowerShell, Read, Grep, Glob, Skill,
     Task*, execute_code, execute_query, …}` — для них p95-ветка degraded ОТКЛЮЧЕНА (только
     error-rate/ratchet по error), латентность — в отчёт информационно.
  2. Для остальных — оставить p95×2, но с полом абсолюта (p95 < 500мс не деградация независимо
     от baseline — иначе Read 408 vs 189 светится).
  3. Acceptance: на текущих данных 6 degraded → 0-1; синтетический тест «медленный не-variable
     инструмент всё ещё ловится».

### N-P1 — досборка §6 decision layer (то, что 260713 задекларировал, но не доделал)

- **N-P1.1 Join трёх потоков сигналов в вердикты (NB4-§6.1).** *~2-3ч.*
  1. `analyze_tool_health` читает `data/_mcp_health.json`: сервер down (по jsonl-истории ≥2 дня
     подряд) → verdict `broken` для его tools (карта affects уже есть).
  2. Читает `[REGRESSION]`-выход observability-отчёта (или его sidecar): stale-sink → `degraded`
     для инструментов memory-серверов.
  3. Регресс: юнит на каждый join + отсутствие сигналов = поведение как сейчас.
- **N-P1.2 verdicts.jsonl получает читателя (NB4-§6.3).** *~2-3ч.*
  1. В баннер-хуке: повторный `broken` того же tool за 30д (по verdicts-истории) → задача
     priority p1 + пометка `repeat` в evidence.
  2. Re-verify после фикса: авто-задача broken несёт `fix_marker`; снятие вердикта — только когда
     свежее окно ПОСЛЕ даты фикса чистое (паттерн `sonar_rescan_verify` — «анализ свежее правок»).
  3. Тренд-секция в `_latest.md`: verdict-переходы за 30д (broken→healthy = вылечено,
     healthy→broken = регресс).
- **N-P1.3 unused-контур (после N-P0.2, иначе мусор).** *~1ч.* Месячный срез «кандидаты на
  отключение» (unused ≥30д на ПОЛНОМ окне) в `_latest.md` + рекомендация lazy-mcp.
- **N-P1.4 Судьба `tool-effectiveness.jsonl` (NB6).** *~0.5ч.* Рекомендация: **ретирнуть** —
  убрать напоминание из `onec-task-completion-stop`, файл в архив, доки поправить (метрики живут
  в `analyze_tool_health` напрямую). Альтернатива (если нужен per-task срез) — detached `--rollup`
  из Stop-хука; не рекомендуется без потребности.

### N-P2 — покрытие и гигиена

- **N-P2.1 Probe-покрытие 1С-контура (NB5).** *~1-2ч.* +5 инстансов `1c-mcp-crud` (HTTP HEAD
  по `MCP_ONEC_URL` из `.mcp.json`/env каждого); edt-mcp (HTTP-порт плагина); skill-learning
  (storage-dir RW-probe). Карта affects → баннер.
- **N-P2.2 P2.3-хвост per-call логов.** *по ~30мин/сервер, по мере касания.* Helper готов;
  очередь по ценности: vector-memory → skill-learning → ai-memory → bsl-semantic-search →
  framework-search → 1c-debug. Не батчить искусственно — правило «по мере касания» оставить.
- **N-P2.3 Doc-sync + гигиена.** *~1ч.* §1.3 таблицу 260713 привести к факту; `_CANONICAL_CATEGORIES`
  вынести в общий модуль (tool_effectiveness.py) и импортировать в оба потребителя; аннотировать
  `elapsed_ms` в схеме (hook-time, не tool-time); глава 42.x/43.3 — синхронизировать.
- **N-P2.4 (опционально) Потребитель `agent_id`.** *~1-2ч.* Разрез per-agent в отчёте (делегирование:
  сколько вызовов/ошибок в субагентах vs основной сессии) — теперь данные есть.

### N-P3 — тяжёлый путь (без изменений против 260713)

- **N-P3.1 OTel → Langfuse** — отдельный ADR; ценность выросла: нативная телеметрия = независимая
  проверка нашего error-детекта (NB1) и второй источник для built-in.
- **N-P3.2 LLM-judge на сэмпле** — только ПОСЛЕ N-P0.1 (judge поверх врущих success-меток бессмыслен).

**Порядок:** N-P0.1 → N-P0.2 → N-P0.3 → N-P1.1 → N-P1.2 → N-P1.4 → N-P2.3 → остальное по мере
касания/потребности. N-P0 — один спринт (~1 день с тестами и code-verify), N-P1 — второй.

## §4 Acceptance всего роадмапа

1. Зонд «Bash exit 42» → canonical строка `outcome=error` (сейчас: success=True). Live-контракт-тест зелёный.
2. `window_incomplete=False` на целевом окне; unused-список пересчитан и правдоподобен.
3. На здоровой системе degraded-вердиктов 0-1 (сейчас 6 FP); синтетический broken достижим и
   эскалируется задачей p1 при повторе.
4. Down MCP-сервера ≥2д виден как `broken` его tools в ОДНОМ отчёте (не тремя параллельными баннерами).
5. `verdicts.jsonl` имеет читателя; тренд-секция в отчёте.

## §18 Progress Log

> Append-only, reverse-chronological.

### 2026-07-18 — Аудит реализации 260713 + роадмап NEXT создан

- 3 верификационных агента: P0 CONFIRMED полностью, P1/P2 код CONFIRMED, §6.1/§6.3 — реализованы
  наполовину (2 из 4 broken-условий, verdicts write-only).
- Живые данные: контур крутится (отчёт 22ч, probe 0.5ч, per-call логи живы, agent_id течёт).
- **Эмпирический зонд NB1**: `exit 42` → `success=True` — error-детект built-in мёртв на живом
  payload; 1526 вызовов / 0 ошибок; вердикты broken/ineffective недостижимы.
- NB2 (6/6 degraded = p95-FP на content-variable), NB3 (окно ~1 день вместо 14), NB4-NB6.
- Реализация NEXT — не начата (roadmap-only).
