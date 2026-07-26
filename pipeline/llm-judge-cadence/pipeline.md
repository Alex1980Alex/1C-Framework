# LLM-judge в каденс качества — Часть 1 роадмапа 260725 (J-P0…J-P3)

**Роадмап:** [260725_ROADMAP_LLM_JUDGE_CADENCE_SETFIT_DATASET.md](../../docs/roadmap/260725_ROADMAP_LLM_JUDGE_CADENCE_SETFIT_DATASET.md)
**Тип:** medium · **Статус:** реализовано, окно замера J-P3 впереди

## 1. Планирование

Пробел: `scripts/tool_llm_judge.py` (H-P4) написан и покрыт тестами, но запускался
только вручную — семантический слой не жил, тогда как rule-слой уже в каденсе.
Живой замер: 650 вызовов в per-call логах, 640 `ok=true` (98%). Класс дефекта,
который правила не видят, — успех без достижения цели (запрос с неверным полем
возвращает `ok=true` и пустую выборку).

## 2. Дизайн

Уточнён по факту: проверка живых логов **опровергла** допущение плана — в
`.claude/cache/mcp-*-calls.jsonl` только `{error_type, ms, ok, server, tool, ts}`,
args/result отсутствуют по контракту «metadata only». Адаптер по исходному плану
выдавал бы пустой батч молча. J-P0 переработан в три шага (собственный контент-лог,
native OTel, общие адаптеры). План отревьюирован независимой моделью — 5 поправок
вшиты (курсор вместо окна, порог промоута заранее, дизамбигуация, frozen held-out,
per-job cooldown).

## 3. Кодирование

| Шаг | Что сделано | Файлы |
|---|---|---|
| J-P0.1 | `args_digest`/`result_digest` под `MCP_CALL_LOG_CONTENT=1` (off по умолчанию), редакция секретов в 2 эшелона fail-closed, `capture` через `track_call`; обвязаны 3 своих сервера | [`mcp_call_log.py`](../../scripts/mcp_call_log.py), `vector_memory/server.py`, `memory_orchestrator.py`, `skill_learning/server.py` |
| J-P0.2 | адаптер native OTel (built-in тулы + чужие серверы), коэрсинг `stringValue` | [`tool_llm_judge.py`](../../scripts/tool_llm_judge.py) |
| J-P0.3 | `--source {mcp-calls,otel,jsonl,auto}`, курсор, fail-loud `content_disabled` | там же |
| J-P1 | detached-спавн из каденса, свой cooldown 24ч (`last_judge`), opt-out, fail-soft при провайдере down | [`memory-maintenance-cadence.py`](../../.claude/hooks/memory-maintenance-cadence.py) |
| J-P2 | `read_judge_verdicts` + секция «Семантика (advisory)» + ключ `llm_judge` в sidecar | [`analyze_tool_health.py`](../../scripts/analyze_tool_health.py) |
| J-P3 | валидатор промоута: пороги в коде, промоут по категориям, judgy-поправка на ошибку судьи | [`tool_judge_validation.py`](../../scripts/tool_judge_validation.py) |

## 4. Тестирование

**439 тестов зелёные** (66 новых + 373 регрессионных, включая gate-parity harness).

- Живой прогон: флаг off → внятная причина вместо тишины; флаг on → секрет в
  аргументе стал `"token": ***`, бизнес-запрос сохранён; сквозной цикл
  вызов → судья → агрегация → секция отчёта отработал.
- Саботаж-проверки: отключение `_redact_struct` и продвижения курсора краснят
  ровно целевые тесты.
- Ревьюер (`code-verify`, quality-review) вернул FAIL с 5 замечаниями — все
  исправлены, commit `5208ad908`:
  Р1 утечка вложенного секрета мимо regex · Р2 падение одного источника уносило
  второй · Р3 `cap` резал выборку, а курсор уезжал на конец файла (на живом логе
  первый прогон съел бы историю) · Р4 тесты оставались зелёными при удалении
  проводки из `execute()` · Р5 путь в выводе и половинчатая калибровка.

## Коммиты

`f13db73ea` (J-P0.1/0.2/0.3, J-P1) · `b49f14903` (J-P2, J-P3) · `5208ad908` (фиксы ревью)

## Не сделано (осознанно)

- **Окно замера J-P3** — требует 14 дней и ручной разметки расхождений в
  `judge-review.jsonl`; валидатор сейчас честно отвечает `insufficient-data`.
- **Активация на живых данных** — нужен `MCP_CALL_LOG_CONTENT=1` + `/mcp reconnect`
  (правки серверного кода не действуют до реконнекта).
- **Часть 2 роадмапа** (S-P0…S-P2, автосбор датасета SetFit) — не начиналась.
