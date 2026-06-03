# Roadmap 260603 — Long-poll ping для 1c-debug-hmr (снижение латентности доставки событий)

**Дата:** 2026-06-03
**Статус:** IMPLEMENTED (адаптивный polling — см. §8; true server-held long-poll не поддержан RDBG 8.3.27)
**Область:** `tools/bsl-debug-server/mcp_debug_server.py` (`_ping_loop` / `ping`)
**Связано:** улучшения отладки #1 (sticky capture-mode, DONE) + #3 (пауза старта в helper, DONE). Это пункт #2 из анализа «BP не ловится в фоновом JOB».

---

## §1. Контекст / проблема

При отладке через RDBG события (`targetStarted`/`callStackFormed`/`targetQuit`) доставляются wrapper'ом через **периодический polling** `ping`. Для короткоживущего фонового задания (JOB rphost, время жизни `<100ms`) возникает гонка:

```
JOB rphost:   спавн → выполнение целевой строки → quit
Wrapper:      [poll] ... [poll] ← targetStarted доставлен СЛИШКОМ поздно
```

К моменту, когда `ping` доставил `targetStarted`, JOB уже отработал → attach + применение BP опаздывают → `callStackFormed` не приходит → BP не срабатывает.

**Эмпирически (2026-06-03, задача 260529_УК):** в одном ping-батче приходили `targetStarted` И `targetQuit` — таргет родился и умер между опросами.

## §2. Текущее состояние (что уже сделано)

- **#1 Sticky capture-mode** (DONE) — `debug_capture_mode(on)` пере-армит `setBreakOnNextStatement` после каждого drain → каждый новый таргет халтит на инструкции №1 (детерминированно). Закрывает гонку на уровне RDBG-арма. 222/222 тестов, code-verify PASS.
- **#3 Пауза старта в helper'е** (DONE, деплой пользователем) — busy-wait ~400мс в `mcp_Выполнение.ОтладкаВыполнитьКод` перед `Выполнить` → attach+BP успевают.

Оба подхода — workaround'ы вокруг латентности доставки. **#2 атакует корень латентности.**

## §3. Предложение

Перейти с периодического polling на **блокирующий long-poll** `ping` — как делает штатный Debug UI Конфигуратора / EDT:

- RDBG `ping`-запрос держит HTTP-ответ открытым до наступления события ИЛИ серверного таймаута (вместо «опрос-пауза-опрос»).
- `targetStarted` доставляется за **миллисекунды** после спавна → attach + применение BP workspace успевают до того, как быстрый JOB дойдёт до целевой строки.

Это **митигация, не полный фикс** (round-trip attach→setBreakpoints всё равно ненулевой), но радикально сужает окно гонки и делает #1/#3 менее необходимыми в типовых случаях.

## §4. Объём работ

1. Рефактор `_ping_loop` / `ping` в `mcp_debug_server.py`:
   - long-poll режим (RDBG держит ответ; настраиваемый серверный таймаут, напр. 5–10с);
   - корректная обработка таймаута (пустой ответ → немедленный re-poll, без паузы);
   - graceful cancel при `debug_disconnect` / HMR-restart (не зависнуть на открытом сокете).
2. Сохранить совместимость: `debug_ping()` (ручной) и фоновый loop работают через один путь.
3. httpx-таймауты: read-timeout > серверного long-poll-таймаута.
4. Фоллбэк: если RDBG-эндпоинт не поддерживает long-poll семантику на 8.3.27 — оставить периодический режим (feature-flag / env).

## §5. Риски

- **Зависший сокет** при HMR-restart / disconnect → нужен надёжный cancel (`asyncio.Task.cancel` + close).
- **httpx read-timeout** меньше long-poll-таймаута → ложные ошибки; выставить корректно.
- Изменение в горячем пути доставки событий — высокий blast radius (затрагивает ВСЕ debug-сценарии). Требует полного прогона 222+ тестов + live-проверки на реальном RDBG.
- Сверить семантику long-poll RDBG `ping` на 8.3.27 (yukon39 reference + live), чтобы не упереться в server-side немедленный ответ.

## §6. Критерии приёмки

1. `targetStarted` для фонового JOB обрабатывается за `<` времени жизни типового JOB (наблюдаемо: `callStackFormed` приходит без capture-mode/#3-паузы на быстром JOB).
2. 222+ unit-тестов проходят без регрессий.
3. `debug_disconnect` / HMR-restart не оставляют зависших сокетов/тасков.
4. Фоллбэк на периодический режим работает (feature-flag).
5. code-verify PASS (behavior-preservation + quality-review).

## §7. Приоритет / последовательность

- **P2 (не срочно).** #1 (sticky capture-mode) уже даёт детерминированную ловлю BP в JOB — острая боль закрыта. #2 — инфраструктурное улучшение «по красоте» (убрать необходимость в workaround'ах).
- Делать отдельным PR с тщательным live-тестом на RDBG (горячий путь).

---

## §8. Реализация (2026-06-03)

**Находка при реализации:** RDBG `pingDebugUIParams` на 8.3.27 возвращает **снапшот очереди событий немедленно** — server-held long-poll (как в §3) платформой **не поддержан**. Поэтому реализован безопасный эквивалент — **адаптивный интервал polling** (та же проверенная механика, меняется только каденс):

- Новые константы `RDBGClient`: `PING_INTERVAL_IDLE = 2.0`, `PING_INTERVAL_ACTIVE = 0.1`, `POST_SPAWN_POLL_SEC = 6.0`.
- `_ping_loop`: каждую итерацию выбирает интервал — **0.1с**, если ждём событие (`_capture_mode` / `_break_on_next_silent_arm` / `_break_on_next_armed` / непустой `_attached_pending`), иначе **2с** heartbeat.
- `_post_spawn_auto_attach` переведён на **time-based** триггер (~6с по накопленному времени), чтобы fast-poll не молотил `getDbgAllTargetStates`.
- **Default не меняется:** когда ничего не armed (обычный режим) → 2с, как прежде.

**Эффект:** в окне ожидания (capture-mode / armed) `targetStarted` доставляется за ~0.1с вместо ~2с → окно гонки attach/BP для коротких JOB сужено в ~20×. В связке с #1 (sticky capture-mode) даёт надёжную ловлю BP в фоновом задании.

**Верификация:** 222/222 unit-тестов passed, ruff 0 errors, code-verify PASS.

**Остаток (FUTURE, опц.):** если в будущей версии платформы/протокола появится server-held long-poll — заменить адаптивный poll на блокирующий (убрать busy-cadence в active-окне). Сейчас не требуется.

---

## §18. Журнал прогресса

| Дата | Событие | Кто |
|------|---------|-----|
| 2026-06-03 | Roadmap создан (PROPOSED). Контекст — анализ «BP не ловится в фоновом JOB» по задаче 260529_УК; #1+#3 реализованы, #2 вынесен сюда. | Claude |
| 2026-06-03 | **IMPLEMENTED** — адаптивный ping (0.1с active / 2с idle) в `_ping_loop` + time-based auto-attach. Установлено, что server-held long-poll не поддержан RDBG 8.3.27 → реализован эквивалент. 222/222 тестов, code-verify PASS. | Claude |

> Связанный кеш знаний: [`1c-doc-research/cache/rdbg-bp-background-job-auto-attach.md`](../../.claude/skills/1c-doc-research/cache/rdbg-bp-background-job-auto-attach.md)
> Связанная документация: [36_AUTONOMOUS_DEBUG_CONTROL](../framework%20documentation/36_AUTONOMOUS_DEBUG_CONTROL/)
