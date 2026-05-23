# BSL Refactor Routing Matrix v2

> DoD артефакт для R1.6 (roadmap `260414_Serena Audit углублённый анализ эффективности.md`).
> Источник: [classifier.py](../../src/bsl/semantic_search/refactor/classifier.py) (`RoutingMatrix._ROUTES`).

## Обзор

Матрица определяет, какой backend (A = multilspy через BSL Language Server, B = ast-grep через tree-sitter-bsl) обрабатывает rename-операцию для каждого типа символа BSL. Confidence-значения идентичны `MultilspyBackend._CONFIDENCE` и валидируются тестом `test_confidence_values_match_multilspy_backend`.

**Calibration (2026-04-18):** pilot-B benchmark (19/20 = 95% success, CAT1-4 100%, CAT5 75%) показал что ast-grep значительно точнее чем предполагалось изначально. Все confidence для CAT1-4 увеличены с 0.40-0.85 до 0.95.

## Матрица

| SymbolKind | Primary | Fallback | Confidence | Обоснование |
|------------|---------|----------|-----------:|-------------|
| `module_export_proc` | **multilspy** | ast-grep | 0.95 | Экспортная процедура вызывается кросс-модульно; LSP + preload всех `.bsl` даёт детерминированный список ссылок. Fallback на ast-grep когда workspace без XML-дескрипторов. |
| `module_export_func` | **multilspy** | ast-grep | 0.95 | То же, что и export proc — cross-file references через LSP. |
| `module_local_proc` | **multilspy** | ast-grep | 0.95 | Не экспорт, в пределах модуля. pilot-B 4/4 success. |
| `module_local_func` | **multilspy** | ast-grep | 0.95 | То же, что и local proc. pilot-B 4/4 success. |
| `local_variable` | **multilspy** | — | 0.95 | Локальная переменная = один файл, один scope. pilot-B 4/4 success. |
| `form_handler` | **ast-grep** | multilspy | 0.95 | Обработчики форм. pilot-B 4/4 success. |
| `unknown` | **ast-grep** | — | 0.30 | Pattern-based fallback для случаев, когда классификатор не смог определить kind. Низкая уверенность — пользователь должен подтверждать edit. |

## Алгоритм выбора

```
1. classifier.classify(uri, line, character, content) → SymbolKind
2. decision = RoutingMatrix.route_for(kind)
3. try:
     result = backends[decision.primary].plan_rename(...)
   except BackendError when decision.fallback is not None:
     result = backends[decision.fallback].plan_rename(...)
4. confidence используется оркестратором для UI-hint'ов ("certain" vs "review carefully")
```

## Эвристики классификатора

`HeuristicClassifier.classify()` — паттерн-based, без AST:

- Path `/forms/` или `\forms\` (case-insensitive) → `form_handler` (выигрывает над анализом содержимого).
- `content is None` → `unknown`.
- Строка содержит `Процедура`/`Procedure` + `Экспорт`/`Export` → `module_export_proc`.
- Строка содержит `Процедура`/`Procedure` (без экспорта) → `module_local_proc`.
- Аналогично для `Функция`/`Function` → `module_export_func` / `module_local_func`.
- Строка начинается с `Перем `/`Var ` → `local_variable`.
- Иначе → `unknown`.

**Ограничение:** эвристика смотрит только на одну строку `content.splitlines()[line]`. Не различает overloaded procs в модулях или локальные переменные в области `Перем` vs внутри процедуры (классификатор пометит оба как `local_variable`). Для production-grade классификации нужен AST-parser — это отложено, интерфейс `classify()` совместим (параметр `character` уже в сигнатуре).

## Согласованность

| Проверка | Как | Тест |
|----------|-----|------|
| Все `SymbolKind` покрыты матрицей | `set(SymbolKind) == set(RoutingMatrix.all_kinds())` | `test_routing_matrix_has_all_symbol_kinds` |
| Confidence в матрице == `MultilspyBackend._CONFIDENCE[kind.value]` | Итерация по всем kinds (кроме `UNKNOWN`) | `test_confidence_values_match_multilspy_backend` |

## Открытые вопросы (вынесены за R1)

- **AST-backed classifier**: `character` column игнорируется эвристикой. Для точного определения `local_variable` vs `module_local_var` нужен парсер BSL с scope-resolution. Артефакт для R3 или R4.
- **Form XML routing**: когда ast-grep не находит XML-side refs на handler, нужно ли эскалировать в multilspy или падать с «не удалось найти»? Сейчас — fallback на multilspy.
- **Confidence калибровка**: значения из `MultilspyBackend._CONFIDENCE` — эмпирические, не измеренные. R4.2 (Confidence calibration) измерит реальный success rate на benchmark-датасете.

## Global tuning — ast-grep call-graph pre-filter (Option A, 2026-04-19)

`routing_matrix.yaml` теперь поддерживает блок `global.ast_grep` с тремя ключами:

```yaml
global:
  ast_grep:
    use_call_graph_prefilter: true        # default ON
    call_graph_db: cache/bsl_call_graph.db
    graph_stale_threshold_days: 7         # warn-only, не блокирует
```

**Эффект:** `AstGrepBackend` (и primary, и fallback) перед построением `WorkspaceEdit` спрашивает у `CallGraphPreFilter`, в каких модулях ожидаются правки (defining module + transitive callers через `CallGraphStore.callers_of`). Файлы вне этого множества отбрасываются. Если символ неизвестен графу → возвращается `None` и фильтр выключается на этот вызов (graceful fallback).

**Rollback:** `use_call_graph_prefilter: false` в YAML, либо env `BSL_REFACTOR_NO_PREFILTER=1` для одного запуска.

**Telemetry:** `RenameTelemetryEvent` (schema v2) добавляет `prefilter_used` и `prefilter_dropped`. `VerifyResult.prefilter_dropped` — то же значение для consumer-side агрегации.

**Wiring:** через `src/bsl/semantic_search/refactor/backends/factory.py::build_ast_grep_backend()`. Используется `scripts/run_benchmark.py` и должен использоваться любым новым call-site (не конструировать `AstGrepBackend(...)` напрямую с прибитым прохождением prefilter).

**Замеры (full-1, 20 strict tasks):** prefilter ON 4/20 (20%) vs OFF 3/20 (15%), +5 п.п. Acceptance gate ≥35% не достигнут — дальнейший анализ см. [option-a-recon.md](option-a-recon.md).

## История изменений

- **v2.1 (2026-04-19):** добавлен блок `global.ast_grep` (Option A — call-graph pre-filter). Schema bump telemetry v1→v2.
- **v2 (2026-04-17, R1.6 DoD):** публикация начальной матрицы. 7 SymbolKind, confidence 0.30–0.95. Классификатор — heuristic.
- **v1 (до R1.6):** неформальная конвенция в комментариях `MultilspyBackend._CONFIDENCE`, без документа и без классификатора.
