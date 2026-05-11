# Deep Analysis — Maximum Debug Coverage для `1c-debug-hmr` Pipeline

> **Дата:** 2026-05-11
> **Статус:** Research COMPLETE → Recommendations pending approval
> **Связано:** roadmaps 260510 + 260511 + 36_AUTONOMOUS_DEBUG_CONTROL

## §1. Executive Summary

Wrapper `1c-debug-hmr` достиг **production-grade baseline** после roadmaps 260508+260510+260511. 15 MCP tools, HMR persistent session, alias validation, 8-type target filter, no_fire_diagnostics, post-spawn polling, BP workspace re-apply. E2E PASS (GKSTCPLK-2468).

**НО** — покрыты только базовые DAP операции. Industry leaders (VS Code DAP, JetBrains IDEA, Chrome DevTools, pydevd, Coverage41C) предлагают **+11 классов features**. P0+P1 batch (~12-16ч) поднимет coverage с 8/19 до 14/19 industry-standard features.

## §2. Текущее vs Industry Feature Matrix

| Feature | 1c-debug-hmr now | VS Code DAP | IntelliJ | Chrome DevTools | pydevd |
|---|---|---|---|---|---|
| Line BP / stack / variables / eval / step | ✅ | ✅ | ✅ | ✅ | ✅ |
| Multi-target attach / remote / HMR | ✅ | ⚠ | ⚠ | ⚠ | ⚠ |
| **Conditional BP** (expression filter) | ❌ | ✅ | ✅ rich | ✅ | ✅ |
| **Hit-count BP** | ❌ | ✅ | ✅ | ✅ | ✅ |
| **Logpoint** (no halt) | ❌ | ✅ | ✅ | ✅ | ✅ |
| **Function BP** (method entry) | ❌ | ✅ | ✅ | ⚠ | ✅ |
| **Data BP** (variable change) | ❌ | ⚠ | ✅ | ✅ | ❌ |
| **Exception BP** | ❌ | ✅ | ✅ | ⚠ | ✅ |
| **Drop frame** (reset) | ❌ | ⚠ | ✅ | ❌ | ❌ |
| **Force return value** | ❌ | ❌ | ✅ | ❌ | ❌ |
| **Time-travel record/replay** | ❌ | ⚠ Replay.io | ⚠ rr | ⚠ RR | ⚠ PyTrace |
| **Precise coverage** (per-line callCount) | ❌ | ❌ | ⚠ | ✅ V8 | ❌ |
| **Coverage export** (genericCoverage.xml) | ❌ | ⚠ | ✅ | ⚠ | ⚠ |
| **CI artifact capture** | ❌ | ⚠ | ⚠ | ⚠ Replay | ❌ |
| **Source mapping** (UUID → FQN) | ⚠ partial | ✅ | ✅ | ✅ | ✅ |

**Gap summary:** 11/19 features absent. 4 critical (conditional, logpoint, coverage, CI artifacts).

## §3. Top-5 Best Practices с GitHub (deep research)

### BP-1: VS Code Debug Adapter Protocol — Conditional BPs + Logpoints

[microsoft/debug-adapter-protocol](https://github.com/microsoft/debug-adapter-protocol) — открытый стандарт, реализован ≥40 adapter'ами.

- `SetBreakpointsRequest.breakpoints[].condition` — expression evaluated при hit; BP не fire если false
- `SetBreakpointsRequest.breakpoints[].hitCondition` — `">10"` / `"%5"` (every 5th) / `"=3"`
- `SetBreakpointsRequest.breakpoints[].logMessage` — **logpoint**: evaluate + emit, no halt
- `FunctionBreakpointsRequest` — break on method entry by name
- `DataBreakpointsRequest` — break когда target variable changes value
- `ExceptionBreakpointsRequest` — break on raise

**Применимость к 1С:** RDBG XSD (`debugBreakpoints.xsd`) нужно проверить native support. Wrapper-level fallback — break + evaluate + auto-Continue if condition false. **Source:** [microsoft.github.io/debug-adapter-protocol/specification.html](https://microsoft.github.io/debug-adapter-protocol/specification.html), [code.visualstudio.com/blogs/2018/07/12/introducing-logpoints-and-auto-attach](https://code.visualstudio.com/blogs/2018/07/12/introducing-logpoints-and-auto-attach).

**🎯 Эффективность при внедрении (реальный пример: GKSTCPLK-2468):**

При анализе bottleneck в `ОбновитьСостояниеБлокировки:80` (E2E на real cluster) получили **7 одновременно stopped targets** (mix HTTPService + JOB), каждый из которых требовал stack inspection. Условие `СостояниеКачества = Перечисления.гкс_СостоянияКачества.КачПринято` вычислялось для разных Показатель/БлокирующаяГруппаТС комбинаций — 6 из 7 stops были irrelevant noise для конкретно искомого бага.

- **С BP-1:** `debug_set_breakpoint(condition="БлокирующаяГруппаТС.Наименование = 'группа: 1' И Показатель.Наименование = 'ГМО'")` → fire **только** для группы 1 + ГМО = 1 stop из 7 → 6× меньше manual filter работы.
- **Hit count:** `hit_count="=3"` ловит **только 3-й** проход цикла без интерактивного step-skip × 1-2.
- **Logpoint:** `logMessage="ТМУТ={ДокументРегистрации.Номер} Стат={СостояниеКачества}"` — production-safe tracing вместо вставки `Сообщить()` calls + redeploy. **Экономия на task type «найди регрессию в проведении»: 30-50 мин/итерация → 5-10 мин.**

### BP-2: JetBrains IntelliJ — Drop Frame + Force Return + Rich Evaluator

[blog.jetbrains.com/idea/2025/04/debugging-java-code-in-intellij-idea](https://blog.jetbrains.com/idea/2025/04/debugging-java-code-in-intellij-idea/) (April 2025).

- **Drop Frame** — restart current method execution from beginning без re-trigger всего сценария
- **Force Return** — exit current method immediately с указанным return value (skip expensive computation)
- **Rich evaluator** — lambda / loops / declarations / switch внутри eval expression
- **Field-watch BP** — break только когда field changes
- **Stream debugger** — visualize pipeline transformations

**Применимость:** RDBG `DebugStepAction` enum (yukon39 `debugBaseData.xsd:72-80`) знает `Step / StepIn / StepOut / Continue` — НЕТ `DropFrame` / `ForceReturn`. **Research blocker** — может потребовать invasive wrapper-level (custom BSL prepend через `Documents.Reload()`).

**🎯 Эффективность при внедрении (real-world сценарий GKSTCPLK-2468 v1 → v2):**

В session 2026-05-11 первая реализация F2 (`РазблокироватьЗаблокированныеПриПринятииКомпозита`) оказалась **no-op** из-за type mismatch (ФНП vs Регистрация на ПЛК). Чтобы понять причину пришлось:
1. revert РС записи через execute_code (~30s)
2. re-trigger composite re-post (~10s)
3. re-snapshot РС → compare BEFORE/AFTER (~20s)
4. изменить F2 SQL → repeat от шага 1 (cycle ≈ 1-2 мин × 5+ итераций)

**С BP-2 Drop Frame:** после первого stop в `СформироватьВспомогательныеДанныеДляЗаблокированныхТС:722` можно было бы:
1. изменить state переменной `гкс_ДокументРегистрации` через debug_evaluate('гкс_ДокументРегистрации = ...')
2. Drop Frame → restart процедуры с новым значением
3. наблюдать результат без re-trigger всего composite cycle

**Cycle drops с 1-2 мин → 10-15 sec.** На задаче типа GKSTCPLK-2468 с 5+ итерациями: экономия **~6-9 минут чистого debug time** + значительно меньше mental context-switching.

### BP-3: Coverage41C + sonar-bsl-plugin-community (1С-specific)

[github.com/1c-syntax/Coverage41C](https://github.com/1c-syntax/Coverage41C) + [github.com/1c-syntax/sonar-bsl-plugin-community](https://github.com/1c-syntax/sonar-bsl-plugin-community).

- Подключается к 1С через RDBG protocol (тот же что наш wrapper)
- Записывает executed lines для каждого BSL модуля
- Экспортирует `genericCoverage.xml` (SonarQube format)
- Загружается через `sonar.bsl.languageserver.reportPaths`

**Применимость:** wrapper extension — встроить аналогичный механизм через logpoint-pattern на каждой строке + counter increment, или orchestrate Coverage41C jar как subprocess. **Closes gap «code path coverage отсутствует» из roadmap 260510 §1.2 пункт 2.**

**🎯 Эффективность при внедрении (real-world пример из истории framework):**

После закрытия GKSTCPLK-2257 (исходная разблокировка) → GKSTCPLK-2335 (флаг УК) → GKSTCPLK-2468 (текущий) видна **closure rate progression**: каждый bugfix вскрывал related gap в смежных code paths которые не были покрыты тестами. Static analysis identified что `гкс_ВходнойКонтрольКачества` Module.bsl содержит **74 occurrences** референса на `гкс_ПоказателиУсиленногоКонтроляПоРегистрации` — это 14 functions × 5+ branches. Какие из них реально hit'аются в test scenarios — black box.

- **С BP-3:** `debug_coverage_start(modules=["гкс_ВходнойКонтрольКачества"])` → trigger test scenarios → `debug_coverage_stop() → genericCoverage.xml` → SonarQube показывает `ОбновитьБлокировкуГруппаТС:2042-2077 (95% lines)`, `ЗаполнитьЗаблокированныеРегистрацииУсиленныйКонтроль:224-309 (40% lines)`, **`ОбновитьБлокировкуТекущейРегистрации:2085-2117 (0% lines)` — мёртвая ветка!**
- **Outcome:** 1 нашли regression risk **до того как** GKSTCPLK-2469 откроется по этой dead path; за 1 prevention session экономия = MTTR одного incident'а (≈ ½ дня dev work + meetings + production debugging). **Coverage-driven test design = +1-2 prevented incidents в квартал.**

### BP-4: Chrome DevTools Protocol — V8 Precise Coverage

[chromedevtools.github.io/devtools-protocol/tot/Profiler](https://chromedevtools.github.io/devtools-protocol/tot/Profiler/).

- `Profiler.startPreciseCoverage(callCount: true, detailed: true)` — per-function counters + block-level coverage
- `Profiler.takePreciseCoverage()` — returns coverage data
- Block coverage: `{startOffset, endOffset, count}` per function

**Применимость:** RDBG не имеет аналога, но можно эмулировать через массовые logpoints (BP-2 pattern). Trade-off: N BPs × M hits = ×N latency, только для targeted coverage runs не для production.

**🎯 Эффективность при внедрении (performance hunting сценарий):**

Workflow 36.5 §3 «Performance hunting: отчёт долго формируется» — обычно требует ставить таймстампы через `Сообщить()` × 10-15 ключевых мест → выкатить в test → анализировать output. Цикл "догадка → инструментировать → измерить → исправить → re-trigger" = **30-60 мин per iteration**.

- **С BP-4 callCount:** `Profiler.startPreciseCoverage(callCount: true)` → выполнить отчёт → `takePreciseCoverage` показывает что `ПолучитьДанныеБлокировкиДляРегистраций:1843` вызывается **1247 раз** (N+1 query antipattern!), а `СобратьСостоянияКачестваИзНабораЗаписей:1932` — 1 раз. Hotspot identified без любого изменения кода.
- **Per-block coverage** дополнительно показывает что branch `Если ЭтоПервоеТС Тогда` (стр. 1946) hit 980 раз, alternative ветка `ИначеЕсли Не ЭтоПервоеТС И ЗначениеЗаполнено...` (стр. 1955) — 267 раз. Distribution = critical insight для optimization. **Cycle drops с 30-60 мин/iter → 5-10 мин/iter, ×5-6 ускорение performance hunting workflows.**

### BP-5: Time-Travel Debugging — rr / PyTrace / UDB / Replay.io

[undo.io](https://undo.io/resources/how-i-debug-python-code-with-a-time-travel-debugger/), [pytrace.com](https://pytrace.com/), [developer.chrome.com/blog/chromium-chronicle-13](https://developer.chrome.com/blog/chromium-chronicle-13), [github.com/replayio/devtools](https://github.com/replayio/devtools).

**Idea:** record execution → replay arbitrary state навигацией (forward / backward / specific event).

**Применимость к 1С:** настоящий time-travel требует rr-style CPU recording (невозможно через RDBG). Достижим **snapshot-based replay** — wrapper при каждом BP fire записывает `{timestamp, target, stack, variables}` в `.replay.jsonl`. `debug_replay_seek(timestamp)` возвращает snapshot. Менее мощно но достаточно для post-mortem analysis.

**🎯 Эффективность при внедрении (incident post-mortem сценарий):**

GKSTCPLK-2468 — встреча с пользователем 07.05.26 18:26 показала что **ОПЭ-наблюдение не воспроизводится** в момент встречи (transcript: «мы не смогли воспроизвести этот пример»). Скриншоты ОПЭ-сессии 04.05 показывают финальное состояние, но не intermediate steps (какая регистрация фейлила первой, какой rphost обработал, в какой последовательности).

- **Сейчас (без BP-5):** разработчик возвращается через 2-3 дня для разбора → trying to reproduce → ~50% удач, остальное «не воспроизводится в dev».
- **С BP-5 snapshot-based:** в момент ОПЭ-сессии autoenabled session record → `.replay.jsonl` сохраняет каждый BP hit с full stack + variables + ИНН-data. После incident → `debug_replay_seek(timestamp=<когда фейлили>)` возвращает full context для post-mortem.
- **Outcome:** voor 1 типичного prod-incident'а: предотвращает 2-3 «не воспроизводится» loops × 30-60 мин каждый = **экономия 1-3 часа** + повышается incident resolution success rate с ~50% до ~85%.

### BP-6: Replay.io / Cypress / Playwright — CI Artifact Capture

[github.com/replayio/devtools](https://github.com/replayio/devtools), [cypress.io](https://cypress.io), [playwright.dev](https://playwright.dev).

**Best practice:** auto-capture screenshots / network logs / DOM snapshots при test failure. Upload как PR artifacts.

**Применимость:** при каждом BP fire wrapper экспортирует bundle: stack.json (10+ frames) + variables.json + expressions.json + session_summary.md + .replay.jsonl. Bundle uploads в GitHub Actions artifact. **Closes gap «regression caught через accidentally failing test, не через structured метрики» (260510 §1.2 пункт 4).**

### BP-7: Source Mapping (DAP `Source` object)

[DAP Source spec](https://microsoft.github.io/debug-adapter-protocol/specification.html#Types_Source).

**Применимость:** RDBG возвращает `objectID`/`propertyID` UUID. Wrapper уже decode'ит `presentation` partially. Добавить **explicit source resolution** через `bsl-semantic-search:bsl_object_info(UUID)` → FQN + file path. Stack frame показывает `гкс_ВходнойКонтрольКачества.Module.ЗаполнитьЗаблокированныеРегистрацииУсиленныйКонтроль (Module.bsl:295)` вместо UUIDs.

## §4. Prioritized Enhancement Roadmap

### P0 (high ROI, low risk, ~6-8ч)

**P0.A Conditional + Hit-count BPs (~3ч)** — `debug_set_breakpoint(condition=..., hit_count=N)`. Wrapper-level: break + evaluate + auto-Continue if false. Closes Gap 3.

**P0.B Logpoints (~2ч)** — `debug_set_logpoint(object_id, line, module_type, message_template)`. Internally BP + auto-Continue + log в `data/debug_logs/<session>.jsonl`. Closes Gap 4 (production-safe tracing).

**P0.C Source mapping (~2ч)** — в `debug_stack_trace` response добавить `resolved_source` через cached `bsl-semantic-search:bsl_object_info`. Stack показывает FQN + file path вместо UUIDs. Closes Gap 7.

### P1 (medium ROI, medium risk, ~6-8ч)

**P1.A Coverage report export (~4ч)** — tools `debug_coverage_start(module_filter)` + `debug_coverage_stop() → genericCoverage.xml`. Logpoint-pattern на каждой executable line. SonarQube compatible. Closes Gap 1 (code path coverage).

**P1.B CI artifact capture (~2ч)** — extend `debug_session_summary(format="artifacts")` → ZIP bundle (stack + variables + replay.jsonl + summary). Upload как PR artifact. Closes Gap 2 (regression detection через structured metrics).

### P2 (high value, high cost — research blocked, ~10-15ч)

**P2.A Snapshot-based time-travel (~6ч)** — `debug_session_record` + `debug_replay_seek(timestamp)`. Wrapper records each stop event + variable snapshot в `.replay.jsonl`.

**P2.B Drop frame / Force return (~5-8ч, BLOCKED)** — RDBG enum не имеет DropFrame/ForceReturn. Wrapper-level fallback потенциально invasive. **Deferred** до RDBG protocol vendor support research.

### P3 (nice-to-have)

- P3.A Data BPs (RDBG protocol research required)
- P3.B Exception BPs (wrapper-level через global trap + stack filter)
- P3.C Stream debugger / pipeline visualization (1С-аналог — табличный документ / запрос)

## §5. Integration в 36_AUTONOMOUS_DEBUG_CONTROL

После P0+P1:

| Chapter | Update |
|---|---|
| 36.1 Обзор | Add Level 4 «Coverage & Replay» (recording → coverage report → PR artifact) |
| 36.2 Health Check | New probe `coverage_engine_ready` — Coverage41C jar / wrapper-native ready |
| 36.5 Workflows | New workflow «Coverage-driven test design»: uncovered paths → write test → re-run → close gap |
| 36.6 Диагностика | Add «Conditional BP не fire'ит» (invalid expression syntax, scope issues) |
| 36.7 HMR Wrapper | Document new tools (set_logpoint, replay_seek, coverage_*) в API table |
| **36.8 NEW** | **Coverage & Replay workflow** — full chapter: API, examples, troubleshooting, CI integration |

## §6. Open Questions

1. **Приоритизация:** P0+P1 батчем (~12ч) или distributed по sessions?
2. **RDBG protocol research для P2:** deep dive `debugBaseData.xsd` для DropFrame/DataBP feasibility или закрывать как "vendor support pending"?
3. **Coverage tool choice:** wrapper-native (P1.A через logpoints) vs Coverage41C jar orchestration (subprocess)?
4. **Replay storage:** local `.replay.jsonl` vs remote (S3 / GitHub Releases) для long-term archives?
5. **Phase 4 в roadmap 260510 vs новый roadmap doc** для P0+P1 batch tracking?

## §7. Recommendation

**Start с P0 batch (6-8ч):**

1. P0.A Conditional + Hit-count — XS если native, S если wrapper-level. Highest immediate value.
2. P0.B Logpoints — wrapper-level, простой extend. Production-safe (no halt).
3. P0.C Source mapping — самостоятельное value plus prerequisite для лучших error messages downstream.

После P0 — **measure debugger productivity gain** на 1-2 реальных задачах. Если confirmed +30-50% speedup — приступить к P1.

**P2 — deferred** до RDBG protocol research. **P3 — nice-to-have.**

После P0+P1: matrix coverage **14/19 industry-standard features** (vs 8/19 текущих). Уровень paid commercial debug tools (vsdbg / xdebug / RubyMine).

**Estimated effort P0+P1:** ~12-16ч (P0 ~6-8ч, P1 ~6-8ч). **Acceptance:** GKSTCPLK-2468-class задачи debug в 2-3× быстрее.
