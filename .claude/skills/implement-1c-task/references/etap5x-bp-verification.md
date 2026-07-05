# Этап 5.x: Live BP verification — 8-шаговый протокол + fallback

**8-шаговый протокол** (для одной точки модификации):

1. `mcp__1c-debug-hmr__debug_connect(infobase_alias=<имя из workspace>)` — если ещё не connected с Этапа 0. Ответ: `{status: "connected", session_id, attach: "registered"}`.
2. `mcp__1c-debug-hmr__debug_set_breakpoint(object_id=<UUID>, line=<MODIFIED_LINE>, module_type=<TYPE>)` — `object_id` берётся из EDT-MCP `get_metadata_details(fqn)` или из ANALYSIS-REPORT (если автор указал UUID); `module_type` ∈ {`ObjectModule`, `ManagerModule`, `FormModule`, `CommandModule`, `ValueManagerModule`, `RecordSetModule`}. Wrapper auto-resolves `propertyID`.
3. `mcp__1c-debug-hmr__debug_get_breakpoints` — verify BP в client cache; ожидаем enabled=true, lineNo совпадает.
4. **Триггер выполнения** (выбрать один из):
   - `mcp__1c-mcp-crud__execute_code` с минимальным BSL-harness'ом, вызывающим изменённую процедуру (например, `НовыйОбъект = Документы.<Имя>.СоздатьДокумент(); НовыйОбъект.<Поле> = ...; НовыйОбъект.Записать(РежимЗаписиДокумента.Проведение);`)
   - `mcp__1c-mcp-crud__execute_query` для HTTP-сервисов / регистров — если изменения в SDBL-логике
   - **ВАЖНО:** harness должен вызывать обновлённую конфигурацию БД — убедиться что шаг 0 Этапа 6 (`update_database`) выполнен ДО триггера, иначе BP fire на старой версии или вообще не fire'нет
5. `mcp__1c-debug-hmr__debug_ping` — wait for `callStackFormed` event (max 3 ping iterations с паузой ~500ms между ними). Ответ содержит `last_stopped_target_id` после fire.
6. **Если stopped:** `mcp__1c-debug-hmr__debug_stack_trace` (без `target_id` — auto-resolve из push event) → assert `frames[0].lineNo == MODIFIED_LINE` и `frames[0].moduleName` содержит ожидаемый объект. Если lineNo не совпадает — pipeline блокируется с error в IMPLEMENTATION-PROGRESS «BP-verification failed: expected line N in <module>, got line M».
7. **Опционально:** `mcp__1c-debug-hmr__debug_variables` (auto-resolve target/stack) для assertion state'а — проверить значения локальных переменных против ожиданий из ANALYSIS-REPORT (если автор указал invariants).
8. `mcp__1c-debug-hmr__debug_step(action="Continue")` — release rphost, дать сценарию завершиться. Без этого rphost остаётся в pause-state, следующие тесты падают по таймауту.

**Fallback при BP не fire'нул** (шаг 5 даёт 3 timeout'а подряд):

a. `mcp__1c-debug-hmr__debug_break_on_next` → повторить триггер. Полезно когда BP стоит на неактивной ветке (условие не сработало) — `break_on_next` ловит ЛЮБУЮ следующую BSL-операцию в attached rphost.
b. Если и `break_on_next` не сработал — **pre-existing rphost gap** (см. roadmap 260508 §10/§11). В dev-среде: `force_recycle_rphost=True` в `debug_connect` — перезапустит rphost, новый процесс получит BP на свежем cold-start (Solution A). В shared base: НЕ recycle (другие пользователи), вместо этого использовать thin client `/Debug` (Solution C, см. 36.7) — оператор открывает Конфигуратор, начинает отладку, BP fire'нет на следующем сценарии.
c. Если оба fallback'а не сработали — BP-verification помечается SKIP в IMPLEMENTATION-PROGRESS с описанием попыток; **pipeline блокируется** перед переходом на Этап 6, требуется ручная диагностика через `scripts/smoke_test_debug_pipeline.py --probe-only --json`.

**Timeout для user-in-the-loop ветки (Solution C, shared base):** если выбран путь «оператор открывает Конфигуратор и запускает отладку вручную», пipelin'у нужен явный таймаут ожидания (default **15 минут** от начала Solution C wait'а). По истечении — BP-verification помечается `SKIP (user-action timeout, N minutes)` в IMPLEMENTATION-PROGRESS, pipeline продолжает на Этап 6 с warning'ом, что fix не валидирован live-trace'ом. Без таймаута pipeline зависает индефинитно при недоступном операторе. Cleanup: при abort'е/timeout'е Этапа 5.x — **обязательно** вызвать `debug_step(action="Continue")` для всех pending BP, иначе rphost остаётся в pause-state и блокирует следующие сессии (try/finally pattern).

**Success criterion Этапа 5:** ВСЕ `[ADDED]`/`[MODIFIED]` точки покрыты BP-trace'ом (либо SKIP с обоснованной причиной). Если хотя бы одна точка не покрыта без причины — **блокировать переход на Этап 6** с error «BP coverage incomplete: N of M MODIFIED points unverified».

**Логирование в IMPLEMENTATION-PROGRESS.md** (для каждой точки):

```markdown
### Точка N — BP verification
- Module: <FQN>:<lineNo>
- BP set: ✓ (propertyID=<auto>, enabled=true)
- Trigger: execute_code "<краткое описание harness>"
- Stack hit: frames[0].lineNo=<actual_line>, moduleName=<actual_module> — assert PASS / FAIL
- Variables (если проверялись): <name=value@stack_level>
- Step Continue: ✓ released rphost
```

## Этап 5.y: Regression diff (опционально, при повторных прогонах)

**Цель:** автоматически детектировать регрессию на повторных запусках `/implement-1c-task` для той же задачи (например, после правки по review).

**Когда применяется:** если в IMPLEMENTATION-PROGRESS.md footer есть `<!-- debug_session_id: <UUID> -->` от предыдущего прогона.

**Шаги:**

1. Прочитать `prev_session_id` из footer существующего IMPLEMENTATION-PROGRESS.md (если файл новый — SKIP с пометкой «no baseline, first run»).
2. После завершения Этапа 5.x (BP verification успешен) — вызвать `mcp__1c-debug-hmr__debug_session_diff(prev_session_id=<UUID из footer>, curr_session_id=<текущий>)`.
3. Парсить `verdict` ∈ {`NO_REGRESSION`, `IMPROVEMENT`, `NEUTRAL`, `REGRESSION`}.
4. **Если `REGRESSION`** — блокировать переход на Этап 6 с error: вывести markdown-таблицу метрик из ответа (UI+ retries, BP fire counts, eval failures) в IMPLEMENTATION-PROGRESS под заголовком «Regression diff vs <prev_session_id>».
5. **Если `NO_REGRESSION` / `IMPROVEMENT` / `NEUTRAL`** — записать таблицу метрик в PROGRESS, продолжить.
