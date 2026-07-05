# Этап 4: Статический анализ — детали (шаги 3-5, false-positives, логирование)

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
