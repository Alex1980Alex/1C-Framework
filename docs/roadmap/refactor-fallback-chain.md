# Refactor Fallback Chain — Reference

## Flowchart

```
bsl_rename_symbol(uri, line, char, new_name)
  │
  ├─ classify(uri, line, char, content)
  │    └─ SymbolKind: {module_export_proc, module_export_func,
  │         module_local_proc, module_local_func, local_variable,
  │         form_handler, unknown}
  │
  ├─ RoutingMatrix.route_for(kind) → RouteDecision
  │    └─ {primary, fallback, manual_fallback, confidence, reason}
  │
  ├─ primary.plan_rename()
  │    ├─ edits non-empty → USE (skip fallback)
  │    └─ empty/exception → try fallback
  │
  ├─ fallback.plan_rename()  (if RouteDecision.fallback is not None)
  │    ├─ edits non-empty → USE
  │    └─ empty/exception → both failed
  │
  ├─ BOTH FAILED?
  │    ├─ manual_fallback=True → return OrchestratorResult(manual_instruction=...)
  │    │    └─ caller receives ManualFallbackInstruction with approach + warnings
  │    └─ manual_fallback=False → raise BackendError(all_backends_failed)
  │
  ├─ dry_run=True → return plan with confirm_token
  └─ dry_run=False + matching token → verify_and_apply()
       ├─ error count did not rise → SUCCESS
       └─ error count rose → auto-ROLLBACK
```

## Per-SymbolKind Routing Table

| SymbolKind | Primary | Fallback | Manual | Confidence | Notes |
|---|---|---|---|---|---|
| `module_export_proc` | multilspy | ast-grep | no | 0.95 | Cross-file via LSP preload; Phase 0b confirmed B-only for cross-file |
| `module_export_func` | multilspy | ast-grep | no | 0.95 | Same as export proc |
| `module_local_proc` | multilspy | ast-grep | no | 0.85 | Module-scope LSP rename |
| `module_local_func` | multilspy | ast-grep | no | 0.85 | Same as local proc |
| `local_variable` | multilspy | — | no | 0.70 | Single file, no fallback |
| `form_handler` | ast-grep | multilspy | **yes** | 0.60 | May have XML-side refs; manual if both fail |
| `unknown` | ast-grep | — | **yes** | 0.30 | Pattern-based; manual if ast-grep fails |

## When Manual Tier Fires

When `manual_fallback=True` and both backends produce no edits:

1. The orchestrator returns `OrchestratorResult(manual_instruction=ManualFallbackInstruction(...))` instead of raising `BackendError`
2. The caller receives `reason="manual_required"` and a structured instruction with:
   - `suggested_approach`: e.g., "Grep+Edit or EDT GUI refactor F2"
   - `warnings`: known pitfalls for this SymbolKind
   - `rationale`: why automation failed

**Agent guidance:** When `manual_instruction` is present, the calling agent should present the suggestion to the user rather than retrying.

## Calibration Invalidation

Recalibrate confidence values when:
- BSL LS version changes (affects multilspy backend accuracy)
- ast-grep BSL grammar rules are updated
- `SymbolKind` enum is extended with new kinds
- `routing_matrix.yaml` is manually edited (verify with `test_routing_matrix_yaml_roundtrip`)
- After accumulating ≥50 real telemetry events (use `scripts/aggregate_refactor_telemetry.py`)

## Telemetry

Every rename operation emits a `RenameTelemetryEvent` to `data/refactor-telemetry.jsonl` (daily rotation). Fields: timestamp, uri, symbol_kind, primary_backend, fallback_used, applied, rolled_back, duration_ms, error_code, confidence, token_matched.

Aggregation: `scripts/aggregate_refactor_telemetry.py` computes per-(symbol_kind, backend) success/fallback/rollback rates and proposes confidence updates in `data/refactor-telemetry-proposed.yaml`.
