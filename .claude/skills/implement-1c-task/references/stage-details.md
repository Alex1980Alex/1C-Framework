# Детали этапов реализации (Этап 0, 1, 3R, 4, 5.x, 6, 7)

Развёрнутые шаги, вынесенные из SKILL.md (progressive disclosure). Оглавление:

- [Этап 0: Preflight — детали (шаги 2-6)](#этап-0-preflight--детали-шаги-2-6)
- [Этап 1: Подготовка — детали fallback'ов (шаг 3)](#этап-1-подготовка--детали-fallbackов-шаг-3)
- [Этап 3R: Рефакторинг через bsl-semantic-search refactor (условный)](#этап-3r-рефакторинг-через-bsl-semantic-search-refactor-условный)
- [Этап 4: Статический анализ — детали (шаги 3-5, false-positives, логирование)](#этап-4-статический-анализ--детали-шаги-3-5-false-positives-логирование)
- [Этап 5.x: Live BP verification — 8-шаговый протокол + fallback](#этап-5x-live-bp-verification--8-шаговый-протокол--fallback)
- [Этап 5.y: Regression diff](#этап-5y-regression-diff-опционально-при-повторных-прогонах)
- [Этап 6: Тестирование на живых данных — детали (шаги 0-5)](#этап-6-тестирование-на-живых-данных--детали-шаги-0-5)
- [Этап 7: Документация — шаблон IMPLEMENTATION-PROGRESS.md](#этап-7-документация--шаблон-implementation-progressmd)

---

## Этап 0: Preflight — детали (шаги 2-6)

Продолжение шага 1 (проверка трёх ключевых серверов через `ToolSearch`) из SKILL.md.

2. **TCP-probe ключевых портов** — отдельный сигнал от наличия MCP-tool в сессии (tool может быть зарегистрирован, но HTTP-bridge упасть):

   | Порт | Сервис | Команда | Ожидание |
   |---|---|---|---|
   | `:8765` | EDT-MCP HTTP-bridge | `Test-NetConnection -ComputerName localhost -Port 8765 -InformationLevel Quiet` | `True` для режимов **Full** и **Code-only** |
   | `:1550` | 1С debug agent (`ragent.exe -debug`) | `Test-NetConnection -ComputerName localhost -Port 1550 -InformationLevel Quiet` | `True` только если нужна runtime-отладка в Этапе 4 |

   Альтернатива одной командой:
   ```powershell
   python scripts/smoke_test_implement_1c_task.py
   ```
   Скрипт парсит [.mcp.json](../../../../.mcp.json), TCP-probe + MCP-handshake, возвращает exit-code `0` (Full) / `1` (degraded) / `2` (unusable). Подробности: [16.6 EDT-MCP setup](../../../../docs/framework%20documentation/3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.6_EDT_MCP_setup.md).

3. **Debug environment health** — вызвать `mcp__1c-debug-hmr__debug_health_check(mode="probe")` (structured <1с health-check вместо 5-7 manual probes). Парсить ответ:

   - `ready: true` → BP-verification в Этапе 5 доступна, продолжить
   - `ready: false` + непустой `auto_prepare_available[]` → предложить пользователю prepare-actions (whitelist: kill-stale-rphosts, restart-ragent через `mode="prepare"`); НЕ запускать без подтверждения (shared-state action)
   - `ready: false` + manual fix only → BP-verification в Этапе 5 будет SKIP с пометкой; surface `recommended_workflow` token из ответа
   - tool недоступен (debug-hmr не зарегистрирован) → fallback к `mcp__1c-debug__*` (plain wrapper), либо BP-verification SKIP

4. Сопоставить результат с матрицей капабилити:

   | edt-mcp | 1c-mcp-crud | bsl-debugger | 1c-debug-hmr | Режим pipeline |
   |---|---|---|---|---|
   | ✓ | ✓ | ✓ | ✓ | **Full** — все 8 этапов работают как описано, Этап 5 включает BP-verification |
   | ✓ | ✓ | ✓ | ✗ | **Full (no-BP)** — все этапы работают, Этап 5 BP-verification SKIP (заметка в IMPLEMENTATION-PROGRESS.md) |
   | ✓ | ✗ | * | * | **Code-only** — Этапы 1, 3 (write), 4, 5, 7, 8. Этап 2 — только `validate_query` (синтаксис), без `execute_query`. Этап 6 — SKIP с пометкой "ожидает ручного тестирования". BP-verification доступна если debug-hmr ✓ |
   | ✗ | ✓ | * | * | **Read-only verify** — Этап 2 на данных, Этап 6 на данных. Запись кода невозможна (нет `write_module_source`) → STOP с просьбой запустить EDT |
   | ✗ | ✗ | * | * | **Read-only research** — только Этап 1 через fallback (см. ниже), сбор контекста. Запись и валидация невозможны → STOP перед Этапом 2 |

   `1c-debug-hmr` — ортогональная ось: его отсутствие НЕ блокирует pipeline, только отключает live BP-verification в Этапе 5 (см. §5.x). Smoke-test `scripts/smoke_test_implement_1c_task.py --json` отражает доступность в поле `mcp_health.debug_hmr`.

5. Если режим не **Full** — сообщить пользователю явно: какие серверы отсутствуют, какие этапы будут пропущены, что нужно поднять (EDT на `localhost:8765`, путь к `1c-mcp-crud` в `.mcp.json`, см. [16.6](../../../../docs/framework%20documentation/3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.6_EDT_MCP_setup.md)). Если debug-hmr unavailable но pipeline-mode иначе Full — это **Full (no-BP)**, не блокировать, только warn. Дождаться решения: продолжить в деградированном режиме или прервать.

6. Сохранить выбранный режим в IMPLEMENTATION-PROGRESS.md под заголовком `Pipeline mode: Full | Full (no-BP) | Code-only | Read-only verify | Read-only research`. Если debug-hmr ✓ — также записать `debug_session_id` (из `debug_health_check` response или `debug_connect` Этапа 5) в footer файла как `<!-- debug_session_id: <UUID> -->` (используется в §5.x regression diff на повторных прогонах той же задачи).

---

## Этап 1: Подготовка — детали fallback'ов (шаг 3)

**Path-fallback при File-not-found (Designer→EDT flatten):**

ANALYSIS-REPORT'ы используют Designer-style пути из выгрузки конфигурации (например `Documents/<Имя>/Ext/ManagerModule.bsl`, `DataProcessors/<Имя>/Forms/<Форма>/Ext/Form/Module.bsl`). EDT в открытом проекте хранит модули по своему layout'у (`DataProcessors/<Имя>/Forms/<Форма>/Module.bsl` без `Ext/Form/`). При расхождении `read_method_source(project, <designer_path>, ...)` падает с `File not found`.

```
EDT-MCP: list_modules(project, objectName="<ИмяОбъектаКонфигурации>")
  → массив { module_path, module_type } для всех модулей объекта
```

Из массива выбрать `module_path` совпадающий по типу (`ManagerModule` / `ObjectModule` / `FormModule` / `CommandModule`) и повторить `read_method_source` с EDT-путём. Соответствие Designer→EDT зафиксировать в IMPLEMENTATION-PROGRESS.md, чтобы последующие точки той же задачи использовали уже разрешённый путь без повторного fallback'а.

**Fallback (edt-mcp недоступен):** структура модуля и тело метода читаются без EDT.
```
bsl-code-search: get_module_ast(file_path)
  → процедуры/функции в модуле (имена + диапазоны строк)
ИЛИ
bsl-semantic-search: bsl_object_info(object_name)
  → метаданные объекта + список модулей + call graph stats
bsl-semantic-search: bsl_coding_context(object_name, task_description)
  → агрегированный контекст: object info + dependencies + style + similar code

Read(file_path, offset=method_start_line, limit=method_length)
  → текущий код точки вставки (через стандартный Read)
```

**Ограничения fallback'а** (зафиксировать в IMPLEMENTATION-PROGRESS.md):
- Нет `get_content_assist` — автодополнение имён перечислений/регистров недоступно, проверять вручную через `bsl-platform-context` или `Grep` по конфигурации.
- Нет `get_symbol_info` — типы параметров/возвращаемых значений выводить из сигнатуры в `get_module_ast` или из аннотаций кода.
- Нет `search_in_code` по проекту EDT — заменяется на `Grep` + `bsl_search` (семантический).

---

## Этап 3R: Рефакторинг через bsl-semantic-search refactor (условный)

**Применяется только если decision gate (SKILL.md) определил операцию как рефакторинг.**

1. **Классифицировать символ** (routing matrix v2 — `src/bsl/semantic_search/refactor/routing_matrix.yaml`):
   - `local_variable` / `parameter` / `module_local_proc` → ast-grep in-file (confidence 0.95)
   - `module_export_proc` → ast-grep cross-file через Neo4j граф (confidence 0.85)
   - `form_handler` → ast-grep + XML (confidence 0.95 после R5.5 calibration)
   - `unknown` / динамические вызовы (`Выполнить()`) → **manual tier**

2. **Вызвать нужный инструмент** (ВСЕГДА сначала `dry_run: true`):
   ```
   mcp__bsl-semantic-search__bsl_rename_symbol(
       uri: "file:///path/to/Module.bsl",
       line: N, character: M,
       new_name: "НовоеИмя",
       dry_run: true
   )
   ```
   Или `bsl_replace_method_body` / `bsl_insert_after_method` — см. [bsl-symbol-editing](../../bsl-symbol-editing/SKILL.md).

3. **Проверить план** (dry_run response):
   - `status: "plan"` → показать `files_affected` + `edits`
   - `status: "manual_required"` → переключиться на manual tier (Grep + Edit)

4. **Подтвердить изменения** (`dry_run: false` с `confirm_token` из plan).

5. **Верифицировать через EDT-MCP:**
   ```
   EDT-MCP: get_project_errors(project, severity="ERROR") → 0 ошибок
   ```

6. **Логировать в IMPLEMENTATION-PROGRESS.md:** backend (ast-grep/multilspy/manual), confidence, N файлов изменено.

Полный workflow: [bsl-refactoring-workflow/SKILL.md](../../bsl-refactoring-workflow/SKILL.md).

---

## Этап 4: Статический анализ — детали (шаги 3-5, false-positives, логирование)

Продолжение шагов 0-2 (автоформат → bsl_lint.py → parse-error triage) из SKILL.md.

3. Для новых процедур с чистой логикой (без обращений к базе):
   ```
   bsl-debugger: bsl_execute(code_fragment)
     → проверить что логика работает (условия, циклы, массивы)
   ```

4. При сложной логике (вложенные циклы, условия) — пошаговая отладка:
   ```
   bsl-debugger: bsl_debug_start(file, breakpoints)
   bsl-debugger: bsl_debug_step(session, "stepInto")
   bsl-debugger: bsl_debug_variables(session)
     → проверить значения на каждом шаге
   bsl-debugger: bsl_debug_stop(session)
   ```

5. **Live runtime debug в Этапе 4 — экспериментальный шаг, НЕ путать с обязательной BP-verification Этапа 5.x.**

   Этот шаг используется опционально для проверки сложной чистой логики (вложенные циклы по runtime-данным) ДО выхода в Этап 5. Обязательная live-валидация изменённого кода против ANALYSIS-REPORT — это **Этап 5.x BP verification** (8-шаговый протокол), а не этот шаг.

   Базовый вызов (через `1c-debug-hmr` MCP, fallback к `1c-debug`):
   ```
   1c-debug-hmr: debug_connect(infobase_alias="<база>")  # если не connected с Этапа 0
   1c-debug-hmr: debug_set_breakpoint(object_id="<UUID>", line=42, module_type="ObjectModule")
   1c-debug-hmr: debug_ping()
   ```
   После срабатывания BP (post-BP-fire handshake, roadmap §13 / 2026-05-09):
   ```
   1c-debug-hmr: debug_stack_trace()       # без target_id — auto-resolve last_stopped
   1c-debug-hmr: debug_variables()         # значения переменных в кадре stop'а
   1c-debug-hmr: debug_evaluate(expression="Контрагент.ИНН")
   1c-debug-hmr: debug_step(action="StepIn")
   1c-debug-hmr: debug_step(action="Continue")  # release rphost
   ```
   Smoke-проверка инфраструктуры до начала: `python scripts/smoke_test_debug_pipeline.py --probe-only --json` — exit_code=0 значит handshake OK. Если `IMPLEMENT_1C_USE_PLAIN_DEBUG=true` — заменить `1c-debug-hmr` на `1c-debug`.

6. Исправить найденные **реальные** проблемы (повторить Этап 3 для исправлений).

**Known false-positive'ы `bsl_analyze` (OneScript-парсер ≠ 1С-компилятор):**

| Паттерн | Сообщение парсера | Корректное поведение |
|---|---|---|
| `#Если ТолстыйКлиентОбычноеПриложение Или Сервер ... Тогда` (директива препроцессора в строке 1) | `Неожиданный токен: Тогда` | Стандартная BSL-директива препроцессора. EDT компилирует. Игнорировать. |
| `Запрос.Выполнить().Пустой()` (chained method call) | `Ожидается имя свойства` | Стандартный паттерн 1С. Игнорировать. |
| `НовыйОбъект.Записать(РежимЗаписиДокумента.Проведение)` (composite ref в аргументе) | разные | Если EDT принимает — игнорировать. |

**Workaround при падении на препроцессоре:** передавать в `bsl_analyze(source=<тело_метода>)` только тело новой функции (без директив препроцессора), а не весь файл через `file=...`.

**Когда ПРОПУСТИТЬ bsl_execute/bsl_debug (но НЕ bsl_analyze):**
- Код состоит только из вызовов методов 1С (РегистрыСведений, Документы)
- Код — простой SQL-запрос + проверка результата
- В этих случаях достаточно bsl_analyze (или его graceful-skip)

**Логирование в IMPLEMENTATION-PROGRESS.md:**
- `bsl_analyze: 0 errors / N warnings` — успех
- `bsl_analyze: SKIP (OneScript false-positive on <pattern>); EDT errors = 0` — tool-limitation, проверка через EDT

---

## Этап 5.x: Live BP verification — 8-шаговый протокол + fallback

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

**Timeout для user-in-the-loop ветки (Solution C, shared base):** если выбран путь «оператор открывает Конфигуратор и запускает отладку вручную», pipeline'у нужен явный таймаут ожидания (default **15 минут** от начала Solution C wait'а). По истечении — BP-verification помечается `SKIP (user-action timeout, N minutes)` в IMPLEMENTATION-PROGRESS, pipeline продолжает на Этап 6 с warning'ом, что fix не валидирован live-trace'ом. Без таймаута pipeline зависает индефинитно при недоступном операторе. Cleanup: при abort'е/timeout'е Этапа 5.x — **обязательно** вызвать `debug_step(action="Continue")` для всех pending BP, иначе rphost остаётся в pause-state и блокирует следующие сессии (try/finally pattern).

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

---

## Этап 6: Тестирование на живых данных — детали (шаги 0-5)

0. **ОБНОВЛЕНИЕ КОНФИГУРАЦИИ БД** (ОБЯЗАТЕЛЬНО, никогда не пропускать):

   **Основной путь (автоматически):**
   ```
   EDT-MCP: get_applications(projectName)
     → найти applicationId работающего инфобейса
   EDT-MCP: update_database(projectName, applicationId, fullUpdate=false, autoRestructure=true)
     → инкрементальное обновление; полное (fullUpdate=true) — если меняется структура хранения
   ```
   Примечание: `update_database` модифицирует live-инфобазу — это **shared-state action** (CLAUDE.md). Если в инфобазе работают другие пользователи или это production — ОСТАНОВИТЬСЯ и спросить у пользователя.

   **Программный gate (вместо LLM-judgment):** перед `update_database` обязательно проверить число активных подключений:
   ```
   EDT-MCP: get_applications(projectName)
     → если len(applications) > 1 (есть подключения помимо текущей сессии Claude) —
       HARD-STOP, явно показать список подключений и запросить подтверждение пользователя.
   ```
   Это убирает зависимость от того, «вспомнит» ли LLM о shared-state риске. Без программного gate можно случайно ребилднуть БД при работающих коллегах.

   **Ручной путь (когда `update_database` отсутствует или нужна ручная проверка):**
   - Сообщить пользователю: «Обнови конфигурацию БД через EDT (Project → Update Database) или через Конфигуратор (F7 → Обновить конфигурацию базы данных). После обновления скажи 'готово'.»
   - Дождаться подтверждения.

   **Smoke-test что обновление прошло:** вызвать изменённую функцию через `execute_code` на одном тестовом объекте; результат должен соответствовать новой логике.

1. **Подготовка тестовых данных** (если требуется в тест-плане):
   ```
   1c-mcp-crud: execute_query(find_test_candidates)
     → найти подходящие объекты для тестирования
   1c-mcp-crud: execute_code(create_test_data)
     → создать тестовые записи согласно тест-плану
   1c-mcp-crud: execute_query(verify_test_data)
     → убедиться что тестовые данные созданы
   ```

2. **Проведение документа** — ПОЛЬЗОВАТЕЛЬ проводит документ вручную в 1С.
   Claude НЕ МОЖЕТ провести документ (нет GUI). Сообщить пользователю:
   ```
   "Проведи документ [ссылка/описание] в 1С:Предприятие.
   После проведения скажи 'готово' — я проверю результат."
   ```

3. **Проверка результата**:
   ```
   1c-mcp-crud: execute_query(verification_query)
     → проверить что данные изменились как ожидалось
   ```

4. **Очистка тестовых данных** (если создавались):
   ```
   1c-mcp-crud: execute_code(cleanup_test_data)
     → вернуть данные к исходному состоянию
   ```

5. Зафиксировать результаты в IMPLEMENTATION-PROGRESS.md, включая:
   - Способ обновления БД (auto через update_database / manual через EDT)
   - Подтверждение что live-вызов изменённой функции вернул новое значение

**Альтернатива при невозможности обновить БД** (production-окружение, другие пользователи в БД, отсутствие applicationId):
- **SQL-симуляция новой логики** через `execute_query` — построить запрос, повторяющий поведение изменённой функции на тех же данных. Сравнить старое vs новое поведение на репрезентативных кейсах из тест-плана. Зафиксировать как `Тест: симуляция через SQL (без обновления БД)` — это НЕ полная live-валидация, требует пометки в IMPLEMENTATION-PROGRESS.md.

**ВАЖНО:** Этот этап ИНТЕРАКТИВНЫЙ — требует участия пользователя для проведения документов и (часто) для обновления БД.
Если пользователь не может провести сейчас — пометить как "ожидает ручного тестирования", при этом SQL-симуляция должна быть выполнена в любом случае.

**YAxUnit unit-тесты (first-class deliverable, параллельно с live-тестированием):**
Если реализация затронула серверные методы (общий модуль / модуль объекта / модуль менеджера) —
выполнить `/write-1c-unit-tests <папка задачи>` → skill `yaxunit-unit-testing`:
- Написать тест-модули в `src/bsl/exts/UnitTests/CommonModules/` (positive + boundary + negative кейсы)
- Задеплоить расширение UnitTests (`LoadConfigFromFiles + UpdateDBCfg`)
- Smoke-прогон `mcp__mcp-onec-test-runner__run_module_tests` → `passed > 0, failed == 0`
Полный прогон с обновлением `.run-state.json` — через `/run-1c-unit-tests <папка задачи>`.
YAxUnit дополняет `run_yaxunit_tests` (EDT-MCP, быстрый smoke) и BDD-трек (`/run-1c-tests`), но не заменяет их.

---

## Этап 7: Документация — шаблон IMPLEMENTATION-PROGRESS.md

**Создать/обновить файл IMPLEMENTATION-PROGRESS.md** в той же папке docs/:

```markdown
# НОМЕР-ЗАДАЧИ — Прогресс реализации

## Статус: В работе / Завершено / Ожидает тестирования

Pipeline mode: Full | Full (no-BP) | Code-only | Read-only verify | Read-only research

## Выполненные точки модификации

### Точка N: Описание
- **Файл:** путь
- **Действие:** что сделано
- **Строки:** актуальные (из EDT-MCP)
- **Валидация запросов:** validate_query OK / исправлен (описание)
- **Ошибки EDT:** 0 / исправлены (описание)
- **bsl_analyze:** 0 ошибок / N предупреждений (список)
- **BP verification:** PASS (frames[0].lineNo=N) / SKIP (причина) / FAIL (детали)
- **Тест на данных:** пройден / ожидает / не требуется
- **Отклонения от ANALYSIS-REPORT:** нет / описание

## Debug session (если режим Full)

- session_id: <UUID>
- session_summary: вывод `debug_session_summary(format="markdown")` — счётчики BP fire, eval, UI+ retries
- Regression diff vs prev (если был baseline): verdict, изменения метрик

## Результаты тестирования
- Тест X.Y: PASS / FAIL / SKIP (причина)

## Открытые вопросы (если есть)

<!-- debug_session_id: <UUID последнего успешного прогона; читается следующим запуском /implement-1c-task для regression diff Этапа 5.y> -->
```

**Правила footer'а:**
- `debug_session_id` записывается ТОЛЬКО при успешном завершении всего pipeline (Этап 5.x PASS, Этап 6 PASS).
- При REGRESSION verdict в Этапе 5.y — footer НЕ перезаписывается (baseline сохраняется для следующей попытки исправления).
- Если режим не Full и BP-verification была SKIP — footer не создаётся (нет валидной session для diff).
