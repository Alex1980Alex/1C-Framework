# fix-state-write-observability — потеря записи session_state стала видимой

**Дата:** 2026-07-26 · **Закрывает** пункт «остаётся открытым» из
[roadmap 260725 §18](../../docs/roadmap/260725_ROADMAP_SESSION_RETRO.md): класс лечился
фолбэками, частота была неизвестна.

## 1. План

Границы дефекта проверены по коду, не по памяти:

| Точка | Было |
|---|---|
| [`_save_state`](../../.claude/hooks/shared/session_state.py) | честно ре-райзит провал `os.replace` (6×20мс ретрая) |
| `_mutate` | исключение пробрасывает, следа не оставляет |
| `session_state.py` целиком | ни одного лог-сайта (`grep` logg/warn/stderr/jsonl — пусто) |
| 5 вызывающих: `task-protocol-observer`, `task-protocol-enforcer`, `code-skill-enforcer`, `skill-router`, `skill-eval-enforcer-shell` | `except Exception: pass` — факт умирает здесь |

Вывод: правка по вызывающим = 5+ мест и вечный дрейф; крошка нужна в единой точке `_mutate`.

## 2. Дизайн

- **Что писать:** `event=mutation_lost` (дефект: state разошёлся с реальностью) и
  `event=lock_fail_open` (**ведущий** индикатор lost-update — лок не взят, мутация прошла
  без взаимного исключения; потеря записи по отношению к нему запаздывающая).
- **Метка операции** — из фрейма вызывающего (`sys._getframe(1).f_code.co_name`), а не
  параметром в 13 местах: новый мутатор подписывается сам, «забыли метку» невозможно.
  Стоимость — одно чтение фрейма на мутацию (мутации редки, не hot path).
- **Куда:** `.claude/cache/session-state-failures.jsonl` (gitignored), путь резолвится по
  вызову с `CLAUDE_CACHE_DIR`-override — как в `scripts/mcp_call_log.py`; оттуда же приём
  ротации (256КБ → сохраняем новейшую половину).
- **Инварианты:** happy path не пишет ничего; провал записи крошки НЕ подменяет исходное
  исключение (fail-soft); поведение вызывающих не меняется (ре-райз как был); opt-out
  `SESSION_STATE_FAILLOG_DISABLE=1`.
- **Читатель обязателен:** сток без потребителя в этом репо уже был (`verdicts.jsonl` писался
  месяц до N-P1.2). Поэтому `shared/session_state_failures.py` (`read_events`/`summary`/
  `banner_line` + stdlib CLI) и строка `[STATE-WRITE]` в баннере каденса — инлайн read-only
  по паттерну P1.4 `_check_regressions`. Одинокий `lock_fail_open` в баннер не идёт: шум
  обесценил бы сигнал.
- Место читателя — `shared/`, а не `scripts/`: потребитель — хук, кросс-древесных
  импортов не нужно.

## 3. Реализация

`shared/session_state.py` (`_faillog_path`, `_record_anomaly`, `_mutate` + `op` из фрейма,
`_ipc_lock` создаёт каталог) · `shared/session_state_failures.py` (новый читатель+CLI) ·
`task-protocol-observer.py` (два независимых `try` + `_try`) ·
`memory-maintenance-cadence.py` (`_check_state_failures` → баннер обеих ветвей).

**Два дефекта того же корня, найденные по ходу:**
1. Наблюдатель держал `record_skill_checked` и `add_activated_skill` в одном `try` — падение
   первой уносило вторую, хотя они питают РАЗНЫЕ энфорсеры (это и объясняет, почему в
   инциденте имя скилла выглядело «уже зарегистрированным», а фаза — нет).
2. `_ipc_lock` на несуществующем каталоге состояния уходил в fail-open (каталог создавал
   только `_save_state`, т.е. позже) — ПЕРВАЯ мутация сессии шла без взаимного исключения.
   Поймано новым тестом на `lock_fail_open`, исправлено в продукте.

## 4. Тест

[`tests/unit/test_session_state_failure_log.py`](../../tests/unit/test_session_state_failure_log.py)
— 14 тестов: крошка + ре-райз; провал записи крошки не маскирует исходную ошибку; opt-out;
happy path молчит; ротация (старое отрезано, новое дописано); `lock_fail_open` при
fail-open и его отсутствие при взятом локе; независимость мутаций наблюдателя; окно/агрегаты
читателя; молчание баннера без потерь; строка баннера при потерях; битый JSON и отсутствие
файла; `parse_since`; сюрфейс каденса.

Прогон: 14 passed, 426 в затронутых наборах (session_state / task_protocol / code_skill /
gate-parity / pipeline-protocol / blocked-write / llm-delegation), ruff clean, compile OK.
**Live-контракт** (изолированный процесс, реальные пути через env): успешная мутация — лога
нет; сломанный `os.replace` → `{"event":"mutation_lost","op":"record_decomposition",
"error_type":"PermissionError","locked":true}` + исключение поднято + баннер
`[STATE-WRITE] 1 потерянных мутаций…`. **Саботаж:** снятие крошки краснит ровно
`test_lost_mutation_is_recorded_and_still_raises`; возврат мутаций в один `try` — ровно
`test_observer_registers_skill_even_if_phase_write_fails`.

**Не сделано осознанно:** бюджет ретраев `os.replace` не тронут — сначала окно замера 7-14д,
тюнинг без данных был бы гаданием.
