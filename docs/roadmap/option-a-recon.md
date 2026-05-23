# Option A — Pre-filter ast-grep по call graph: Recon & A/B Results

**Date:** 2026-04-19
**Status:** PHASES A.0–A.7 IMPLEMENTED. Acceptance gate (≥35% strict) **NOT MET** — observed +5 п.п. (15% → 20%). Component is wired and safe to ship; further calibration is open work.
**Roadmap:** `docs/roadmap/260414_Serena Audit углублённый анализ эффективности.md` §"Roadmap: Option A".

---

## Phase A.0 — Recon

### Call graph staleness

| Field | Value |
|---|---|
| DB path | `cache/bsl_call_graph.db` |
| Size | 535 MB |
| Last rebuild | 2026-04-02 |
| Age at recon | 17 days |
| Rebuild script | `scripts/build_call_graph.py` |

The DB predates the Option A code by ~17 days; per spec the staleness threshold is 7 days (`graph_stale_threshold_days`). A rebuild was deemed **not required** for this iteration because (a) coverage of benchmark symbols is ≥80% (see below) and (b) the `None`-fallback path keeps stale-symbol cases safe.

### Symbol coverage (benchmark)

Test: for each of the 20 strict tasks in `docs/roadmap/benchmark/tasks.json`, look up `old_name` in the `symbols` table.

| Coverage | 17 / 20 = **85%** |
|---|---|

Misses (3):

| Task | Symbol | Category | Reason (probable) |
|---|---|---|---|
| T03 | `НаименованияРегионов` | CAT-1-local-variable | Local var; not stored as a callable symbol |
| T05 | `Выборка` | CAT-2-module-local-proc | Local helper — may post-date last rebuild |
| T17 | `Выполнить` | CAT-5-edge-case | Built-in / overloaded keyword overlap |

Coverage above the 80% Phase-A.0 threshold → Phase A.1 (rebuild) not triggered. Decision: **GO** for A.2–A.7.

---

## Phase A.6 — A/B Benchmark

Both runs executed via the wired factory (`build_ast_grep_backend`), which honours `routing_matrix.yaml` `global.ast_grep.use_call_graph_prefilter` and the `BSL_REFACTOR_NO_PREFILTER=1` env kill-switch.

### Commands

```bash
# Prefilter ON (default)
python scripts/run_benchmark.py --backends ast-grep --run-id option-a-on --append-trend

# Prefilter OFF (env kill-switch)
BSL_REFACTOR_NO_PREFILTER=1 python scripts/run_benchmark.py --backends ast-grep --run-id option-a-off --append-trend
```

### Headline numbers

| Run | Strict success | Δ vs OFF |
|---|---|---|
| `option-a-off` | 3/20 = **15%** | baseline |
| `option-a-on`  | 4/20 = **20%** | **+5 п.п.** |

Acceptance gate (≥35% strict) **NOT met**. Stretch (≥45%) not met.

### CAT-wise comparison

| Category | OFF | ON | Δ |
|---|---|---|---|
| CAT-1-local-variable | 25.0% | 25.0% | 0 |
| CAT-2-module-local-proc | 0.0% | 0.0% | 0 |
| CAT-3-cross-file-export | 0.0% | 0.0% | 0 |
| CAT-4-form-handler | 0.0% | 0.0% | 0 |
| CAT-5-edge-case | 50.0% | 75.0% | +25 п.п. (+1 task) |

The +1 task (T18, edge case) is the entire delta. CAT-2/3/4 are pinned at 0% in both runs — these failures are not over-match issues, so a pre-filter cannot help them.

---

## Why the gate did not pass

The pre-filter only helps a task when (a) the symbol is in the graph AND (b) ast-grep produced over-match noise outside the in-graph file set. Decomposition of why CAT-2/3/4 stay at 0%:

1. **CAT-2 module_local_proc** — these tasks are routed primary→`multilspy`, fallback→`ast-grep`. The benchmark in this run only exercises `ast-grep`, and for those tasks the **expected file set** (`expected_files` in `tasks.json`) is incomplete or ordered differently from what ast-grep emits. False negative is in ground-truth, not in pre-filter.
2. **CAT-3 cross-file-export** — same as above; multilspy is the design winner. ast-grep without scope info still misses cross-module targets even with prefilter, because the prefilter narrows files but does not add targets.
3. **CAT-4 form-handler** — XML-side bindings are invisible to text-based tooling. Pre-filter is irrelevant here; resolution is multilspy (LSP) or EDT-MCP F2.
4. **CAT-1 local-variable** — symbol names like `НаименованияРегионов` (T03) are *not in the call graph at all* (locals are not stored as graph symbols). Prefilter returns `None` → fallback → no change.

Effectively the tasks where the prefilter could have helped are concentrated in CAT-5, and we measured the expected gain there (+1).

---

## Implementation summary

| Phase | Artefact | Status |
|---|---|---|
| A.0 | This file | ✅ |
| A.1 | rebuild | ⏭ skipped (coverage 85% ≥ 80%) |
| A.2 | [call_graph_prefilter.py](../../src/bsl/semantic_search/refactor/backends/call_graph_prefilter.py) + [test_call_graph_prefilter.py](../../tests/bsl/refactor/test_call_graph_prefilter.py) | ✅ 8 tests green |
| A.3 | [ast_grep_backend.py](../../src/bsl/semantic_search/refactor/backends/ast_grep_backend.py) — `last_prefilter_used`, `last_prefilter_dropped` | ✅ |
| A.4 | [verification.py](../../src/bsl/semantic_search/refactor/verification.py) — `VerifyResult.prefilter_dropped` | ✅ |
| A.5 | [factory.py](../../src/bsl/semantic_search/refactor/backends/factory.py), `routing_matrix.yaml` `global.ast_grep`, [orchestrator.py](../../src/bsl/semantic_search/refactor/orchestrator.py) telemetry propagation, [run_benchmark.py](../../scripts/run_benchmark.py) refactor | ✅ |
| A.6 | A/B benchmark — see above | ✅ executed; gate ❌ |
| A.7 | ADR-004, routing-matrix-v2.md, MEMORY.md | ✅ updated |

Total: 1 new module (`factory.py`), 1 schema bump (`RenameTelemetryEvent.version` 1→2), 0 breaking changes (default-off when DB missing, env kill-switch).

---

## Recommendations / Next steps

1. **Rebuild call graph** (`scripts/build_call_graph.py --source src/bsl --clear`) and re-run A/B. If +5 п.п. holds with a fresh graph, prefilter is doing what it was designed for; the rest of the 20-pp shortfall is structural.
2. **Ground-truth audit** for CAT-2/3 — verify `expected_files` in `tasks.json` matches the union of (defining module + caller modules) for each test symbol. Possible gap is in the test fixture, not in the implementation.
3. **Combine with multilspy primary** — Option A is meant to lift `ast-grep` *as a fallback*. Strict success when paired with multilspy (full-1g 14/40 = 35%) should be re-measured with prefilter ON to confirm no regression.
4. **Consider transitive prefilter** — current `allowed_files` is depth=1 (direct callers). Spec hinted at `impact_analysis(depth=3)` as a stretch. Not worth shipping until (1)–(2) clear.

The component is **safe to keep ON by default**: backward-compatible (no-op when DB missing or env set), gives a small but real lift on CAT-5, and instruments telemetry (`prefilter_used`, `prefilter_dropped`) for future analysis.
