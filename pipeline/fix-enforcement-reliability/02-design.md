# Дизайн: надёжность enforcement-слоя (2 фикса)

Триггер — баги, всплывшие в анализе внедрения (сессия 89133dc8): делегирование
недоступно, а `session-skills.json` повредился до строки пробелов.

## Fix 1 — graceful ZAIWriteGuard при недоступном провайдере
**Проблема:** гард хард-блокирует большие code-write без делегирования. Когда llm-rotation
недоступен, делегировать нельзя → блок = чистая friction (форсит futile 60с-вызов).
**Решение:** новый `shared/llm_health.py::is_provider_down()` — читает СОБСТВЕННЫЕ логи
llm-rotation (`data/llm-rotation-{metrics,completions}.jsonl`); если свежие (окно 30 мин)
вызовы преимущественно провальные (`success:false` / `provider:error` / `error~"no available
providers|all failed|down"`) → провайдер недоступен. Гард перед блоком: `if is_provider_down(): allow`.
**Инвариант:** best-effort — нет данных/неоднозначно → False → поведение гарда не меняется.
Детект invocation-логом отвергнут: таймаут MCP логируется как `outcome=allow success=True`.

## Fix 2 — atomic write `session-skills.json`
**Проблема:** `_save_state` пишет `open(STATE_FILE,"w")` напрямую. Гонка ~19 UPS-хуков →
truncate-then-write окно → повреждение (наблюдалось: файл = строка пробелов) → `get_task_protocol`
отдаёт дефолтную фазу `idle` → `TaskProtocolEnforcer` ложно блокирует легитимную запись.
**Решение:** `tempfile.mkstemp(dir=STATE_DIR)` → `json.dump` → `os.replace(tmp, STATE_FILE)`
(atomic rename на той же ФС). На сбое — уборка temp + re-raise (как прежнее поведение).

## Скоуп
- `.claude/hooks/shared/llm_health.py` (new), `tests/unit/test_llm_health.py` (new, 5)
- `.claude/hooks/z-ai-write-guard.py` (+graceful-проверка), `.claude/hooks/shared/session_state.py` (atomic `_save_state`)
- `tests/unit/test_session_state_atomic.py` (new)
Без правок settings.json / новых хуков. code-verify обязателен.
