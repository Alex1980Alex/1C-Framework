# ADR-004: BSL Refactoring Architecture — Scenario 1+3 hybrid (multilspy primary, ast-grep fallback)

**Date**: 2026-04-17 (revised)
**Status**: Accepted (revised after deeper R0.1 verification)
**Context**: §5.5 BSL Refactoring v4.5 — R0 Research Validation

> **Revision note**: first draft selected Scenario 3 (ast-grep only) because cross-file
> rename returned 1 edit. After studying BSL LS source on GitHub
> (`BSLLanguageServer.initialize` → `setConfigurationRoot` → `populateContext`,
> `ReferenceIndexFiller` event-driven on `DocumentContextContentChangedEvent`),
> it turned out the test-workspace lacked per-module XML descriptors, so
> `mdclasses` could not build module metadata, leaving `ReferenceIndex` empty.
> With a proper 1C configuration dump, cross-file rename returns **2 edits / 2 files**.

## Decision

**Гибрид Scenario 1 + Scenario 3**:
- **multilspy + BSL LS как primary** для semantic cross-file rename на реальных 1C-выгрузках (всегда содержат XML-метаданные модулей).
- **ast-grep + tree-sitter-bsl как fallback** для: (а) workspace'ов без XML-метаданных, (б) pattern-based массовых замен, (в) случаев, когда `mdclasses` не парсит конфигурацию.
- **Pre-flight validator** перед вызовом rename: проверить наличие per-module XML рядом с `CommonModules/<Name>/`, `Catalogs/<Name>.xml`, и `Configuration.xml` с `xmlns="http://v8.1c.ru/8.3/MDClasses"`. Нет XML → ast-grep; есть → multilspy.

## Context

Требуется реализовать cross-file rename для BSL (1C:Enterprise) кода. Исследованы 3 подхода:

### R0.1 multilspy + BSL LS — PASS (после правки workspace)

**Итерация 1 (FAIL)** — минимальный workspace без XML-метаданных:
- Cross-file rename: 1 edit. References/Definition: 0. workspace/symbol: 1.
- Bulk preload + 10s sleep — не помогли.

**Анализ исходников BSL LS** (`BSLLanguageServer.java`, `ServerContext.java`,
`ReferenceIndexFiller.java`, `LanguageServerConfiguration.java`):
- `initialize()` извлекает `configurationRoot` из первого `workspaceFolders`.
- `initialized()` запускает `context.populateContext()` асинхронно в ForkJoinPool.
- `ReferenceIndexFiller` подписан через `@EventListener` на
  `DocumentContextContentChangedEvent` (генерируется при `rebuild()` DocumentContext).
- `ServerContext.createDocumentContext()` вызывает `mdclasses` для парсинга
  структуры конфигурации — без XML-дескрипторов `mdclasses` возвращает пустые
  metadata, и cross-file lookup проваливается.

**Итерация 2 (PASS)** — добавлены:
- `Configuration.xml` с `xmlns="http://v8.1c.ru/8.3/MDClasses"`
- `CommonModules/ТестоваяУтилита.xml` и `ТестовыйВызыватель.xml` с полями
  Name/Server/Global/ServerCall и т. п.
- `.bsl-language-server.json` в корне (опционально)

Результат: **cross-file rename = 2 edits в 2 файлах** (`ТестоваяУтилита/Module.bsl:0:8-24` + `ТестовыйВызыватель/Module.bsl:1:28-44`). DoD достигнут.

References/Definition при position-запросе всё ещё возвращают 0 — вероятно UTF-16
offset на кириллице (отдельная задача для R1).

### R0.1-EXT Real-project validation (2026-04-17, 2 прогона)

**Цель:** подтвердить, что Scenario 1 держит нагрузку на реальной конфигурации, а не только на 2-файловом test-workspace.

**Проект:** `260304_GKSTCPLK-2182`, 2 027 `.bsl` файлов, корректная структура (XML-дескрипторы модулей уже есть).
**Target:** `гкс_ОчередьСообщенийRMQ.СоздатьСообщенияПоСобытиюОбъекта` — 7 файлов-caller'ов (включая definition).

| Метрика | Run 1 | Run 2 | Коммент |
|---------|------:|------:|--------|
| init | 4 835 ms | 4 703 ms | Java subprocess + BSL LS init |
| bulk preload 2 027 файлов | 5 963 ms | 5 408 ms | 340–375 files/s через batched `didOpen` |
| populate wait (heuristic) | 60 s | 60 s | фиксированный sleep после preload |
| `prepare_rename` (первый семантический запрос) | **28 073 ms** | **21 944 ms** | блокируется до завершения `populateContext` + `ReferenceIndex` |
| `rename` | 11.6 ms | 10.1 ms | по готовому индексу |
| **Итог rename** | **10 edits / 7 files** | **10 edits / 7 files** | детерминированный |

**Выводы:**
1. Cross-file rename **стабилен и детерминирован** на 2k файлов — 10 edits / 7 файлов оба раза.
2. Throughput preload ≈ 340–375 files/s — 2k файлов прогреваются за ~6 с, 10k проект оценочно ~30 с.
3. Главный bottleneck — не preload, а **populateContext/ReferenceIndex build**: `prepare_rename` становится доступен только после завершения индексации (~22-28 с после 60-с sleep = фактически ~80-90 с с холодного старта).
4. Сам `rename` после готового индекса — **10 мс**, независимо от числа callers.

**Импликации для R1:**
- R1.2 (persistent subprocess) — амортизирует init+populate, что критично: cold start ~90 с vs последующие rename ~10 мс.
- R1.3 (bulk_open_workspace) — заменить фикс. sleep на ожидание `$/progress` / `window/workDoneProgress` от BSL LS.
- R1.8 (verification) — стабильность двух прогонов даёт высокий confidence, но нужен автотест с намеренно ломающимся rename.

Артефакты: `tools/bsl-ls/bench_multilspy_real.py`, `tools/bsl-ls/multilspy-logs-real/` (summary.json + 2 trace'а + 2 rename JSON).

### R0.2 tree-sitter-bsl coverage — PARTIAL
- Протестированы указанные в ТЗ модули: `гкс_ОчередьСообщенийRMQ` (679 lines, 12 ERRs),
  `гкс_ФормировательСообщенийRMQ` ObjectModule (217 lines, 2 ERRs),
  `гкс_Взвешивание.ФормаДокумента` (622 lines, **0 ERRs**, parse OK).
- Покрывает: preprocessor, compile directives (annotation), Экспорт, async/await, regions.
- **14 ERROR nodes суммарно на 1 518 строк (≈0.9%)** — подтверждённая причина:
  **скобочные группирующие выражения** в RHS/условиях, которые грамматика не умеет парсить.
  - гкс_ОчередьСообщенийRMQ:11 — `СинхронныйОтвет = (СвойстваСообщения["Заголовки"].Получить("SyncCallback") = Истина);`
  - гкс_ОчередьСообщенийRMQ:129 — `ЭтоСостояние = (ТипЗнч(НаборЗаписей) = Тип("..."));`
  - гкс_ФормировательСообщенийRMQ:119 — `Если ... И (Событие = "..." ИЛИ Объект.ПометкаУдаления) Тогда`
- **GAP: query language** (ВЫБРАТЬ/ГДЕ) — подтверждён отдельной проверкой на
  `АдресныйКлассификатор.Module.bsl` (11 литеральных `ВЫБРАТЬ` в коде):
  - `0` dedicated query-node types в AST
  - 3 `const_expression` со строкой, содержащей `ВЫБРАТЬ` — то есть SQL остаётся opaque string-domain.
  - В RMQ-выборке `queries=0` — просто потому что в этих модулях нет SQL; grammar-gap не зависит от выборки.
- Форма парсится чисто — coverage достаточен для rename в формах.
- Предыдущий тест (v1) на MCPToolkit-form (12 442 строки, 181 ERR) см. `tree-sitter-coverage.v1.md` — не репрезентативен, модуль замещён.
- Скрипт проверки query-gap: `tools/bsl-ls/check_query_gap.py`.

### R0.3 ast-grep — VIABLE
- 3 YAML правила созданы и валидированы (`rename-export-method`, `rename-local-var`, `rename-catalog-method`).
- customLanguages BSL через tree-sitter-bsl .dll.
- Быстрый (Rust-based), JSON output, --update-all для in-place.
- `expandoChar: _` для BSL ($ конфликтует).
- **Baseline timing зафиксирован** (`tools/bsl-ls/ast-grep-baseline.md`):
  - test-workspace (2 файла): median 27–38 ms (startup-dominated).
  - real-project (**2 027 .bsl файлов**): median **1.2–1.7 s**, 10 969 / 151 282 / 124 989 matches соответственно.
  - Throughput ≈ 1 050–1 720 files/sec.

### R0.4 Bulk preload pattern — NOT HELPFUL
- multilspy ref-counted open_file + ExitStack работает
- Но BSL LS не использует открытые файлы для cross-file анализа

## Decision Rationale

| Критерий | Scenario 1 (multilspy) | Scenario 2 (BSL LS fork) | Scenario 3 (ast-grep) |
|----------|----------------------|------------------------|---------------------|
| Cross-file rename | **PASS** (при правильной структуре) | Possible (Java) | PASS (text search) |
| Семантика | Да (через `mdclasses` + `ReferenceIndex`) | Полная | Нет (structural only) |
| Сложность | Низкая | Высокая (Java fork) | Средняя |
| Init latency | ~4.4s (Java subprocess) | Медленно | ~25 ms (cold scan) |
| Поддержка | multilspy стабильный | Fork — ручной support | ast-grep активный |
| Coverage | Полное (если workspace валиден) | Полный | Частичный (query gap, скобочные выражения) |
| Time-to-value | 1-2 недели (+ валидатор структуры) | 2-3 недели | 1 неделя |

**Scenario 2 отклонён**: Java fork BSL LS — высокая стоимость поддержки, не нужен после R0.1 PASS.
**Scenario 1 ПРИНЯТ как primary**: cross-file rename работает, семантичен, поддерживается upstream.
**Scenario 3 ПРИНЯТ как fallback**: быстрый, работает без metadata, покрывает edge-cases.

## Consequences

### Positive
- Быстрый time-to-value (ast-grep rules работают уже сейчас)
- Rust performance: median 1.2–1.7 s на 2 027 файлов (замер R0.3)
- YAML rules — легко читаемые, расширяемые
- tree-sitter-bsl покрывает ≈99% строк BSL для rename (14 ERRs на 1 518 строк на RMQ-выборке)

### Negative
- Нет semantic analysis (ast-grep не понимает типы, scopes)
- Динамика `Выполнить("Метод()")` не покрывается — нужен regex fallback
- Query language не парсится — rename внутри запросов = manual
- Parse errors на скобочных выражениях в присваиваниях (server-side модули RMQ)

### Mitigations
- Semantic gaps: fallback на text-search + confirmation dialog
- Query language: отдельный tree-sitter-1c-query grammar (R2.2)
- Parse errors: форк tree-sitter-bsl с патчами для скобочных выражений

## Implementation Path (revised)

- **R1 (multilspy primary)** — возвращаем в план:
  - R1.1: `MultilspyBackend` протокольный класс (с `plan_rename`/`can_handle`).
  - R1.2: subprocess lifecycle + circuit breaker (3 краша → disable, fallback на Scenario 3).
  - R1.3: bulk_open_workspace — батчированный `didOpen`, throttling.
  - R1.4: rename driver (`workspace/executeCommand` + raw `rename`).
  - R1.5: WorkspaceEdit applier с snapshot для rollback.
  - **R1.9 (новое) — workspace validator**: проверка per-module XML перед rename;
    нет XML → skip и отправить в ast-grep backend.
- **R2 (ast-grep fallback)**:
  - R2.1: tree-sitter-bsl как git submodule.
  - R2.2: форк + фиксы скобочных группирующих выражений (RHS/условия).
  - R2.3: 4+ YAML правил (export/local/manager/form handler).
  - R2.4: ast-grep runner (Python wrapper).
  - R2.5: routing matrix с приоритетом: (a) multilspy если workspace валиден → (b) ast-grep.
- **R3-R5**: SCIP + Orchestrator + Benchmark — без изменений.

## Addendum: Call-graph pre-filter for ast-grep (Option A, 2026-04-19)

**Problem.** `AstGrepBackend` is text-pattern based. On the strict full-1g benchmark it scored 15% (3/20) because identical-name occurrences in unrelated modules (`Параметры` in 1 679 files, `РезультатЗапроса` in 223, etc.) get rewritten alongside the intended target. Denylist v4.6 mitigates the most common 30 names but does not help locally-unique-but-text-frequent identifiers.

**Decision.** Add a scope filter that uses the existing BSL call graph (`cache/bsl_call_graph.db`, `src/bsl/call_graph/store.py::CallGraphStore`) to compute *expected* edit sites — defining module + transitive callers — and drop ast-grep matches falling outside that set. Implemented as `CallGraphPreFilter` (`backends/call_graph_prefilter.py`), wired through a factory (`backends/factory.py`) so `AstGrepBackend` itself stays stateless about call-graph concerns.

**Semantics of `allowed_files(old_name, module_hint)`:**

- `None` → symbol unknown to graph → **no filtering** (safe fallback)
- `set()` → symbol known but 0 callers and no defining module → backend produces empty edit
- `{paths…}` → restrict matches to this set

**Configuration.** New `global.ast_grep` block in `routing_matrix.yaml`:

```yaml
global:
  ast_grep:
    use_call_graph_prefilter: true        # default ON
    call_graph_db: cache/bsl_call_graph.db
    graph_stale_threshold_days: 7
```

Kill switches:

1. `use_call_graph_prefilter: false` in YAML → orchestrator passes `prefilter=None`
2. `BSL_REFACTOR_NO_PREFILTER=1` env → factory bypasses prefilter for one process
3. Missing `cache/bsl_call_graph.db` → factory logs warning, falls back to no-prefilter (prevents CI breakage when DB not committed)

**Telemetry.** `RenameTelemetryEvent` schema bumped 1→2 with `prefilter_used: bool` and `prefilter_dropped: int`. `VerifyResult.prefilter_dropped` mirrors the value for downstream aggregation.

**Result.** Strict success: 15% (off) → 20% (on), +5 п.п., entirely from CAT-5. Acceptance gate ≥35% not met. CAT-2/3/4 unchanged because their failure mode is "missing target", not "over-match noise" — pre-filter cannot create matches it does not see. Detailed analysis in [option-a-recon.md](option-a-recon.md). Component is safe to ship (default-off via env, no breaking changes); further calibration tracked there.

**Files.**

- `src/bsl/semantic_search/refactor/backends/call_graph_prefilter.py` — filter logic
- `src/bsl/semantic_search/refactor/backends/factory.py` — wiring (`build_ast_grep_backend`)
- `src/bsl/semantic_search/refactor/backends/ast_grep_backend.py` — drop-counter integration (`last_prefilter_used`, `last_prefilter_dropped`)
- `src/bsl/semantic_search/refactor/orchestrator.py` — telemetry + result propagation
- `src/bsl/semantic_search/refactor/verification.py` — `VerifyResult.prefilter_dropped`
- `src/bsl/semantic_search/refactor/telemetry.py` — schema v2
- `src/bsl/semantic_search/refactor/classifier.py` — `RoutingMatrix.ast_grep_global()` accessor
- `src/bsl/semantic_search/refactor/routing_matrix.yaml` — `global.ast_grep` block
- `tests/bsl/refactor/test_call_graph_prefilter.py`, `test_factory.py`, `test_ast_grep_backend.py`, `test_routing_matrix_yaml.py`, `test_telemetry.py` — coverage

## References
- `tools/bsl-ls/multilspy_recon.py` + `multilspy-logs/` — R0.1 артефакт
- `tools/bsl-ls/tree-sitter-coverage.md` — R0.2 results (RMQ + ФормаДокумента)
- `tools/bsl-ls/tree-sitter-coverage.v1.md` — R0.2 первая итерация (для истории)
- `tools/bsl-ls/ast-grep-rules/` — R0.3 rules (3 YAML)
- `tools/bsl-ls/ast-grep-baseline.md` + `.json` + `bench_ast_grep.py` — R0.3 baseline timing
- `tools/bsl-ls/check_query_gap.py` — R0.2 query-language gap proof
- `tools/bsl-ls/bench_multilspy_real.py` + `multilspy-logs-real/` — R0.1-EXT real-project validation (2 027 файлов)
- `docs/roadmap/multilspy-pattern-notes.md` — R0.1 + R0.4 analysis
