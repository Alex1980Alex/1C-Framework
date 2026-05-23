# Benchmark Report - full-1d

**Tasks:** 20 | **Results:** 40

## Per-Backend Summary

| Backend | Success | Rollback | p50 ms | p95 ms | p99 ms |
|---------|---------|----------|--------|--------|--------|
| MultilspyBackend | 85.0% | 0.0% | 0 | 1 | 9 |
| AstGrepBackend | 95.0% | 0.0% | 1176 | 1387 | 1617 |

## Per-Category Success Rate

| Category | AstGrepBackend | MultilspyBackend |
|----------|--------|--------|
| CAT-1-local-variable | 100.0% | 75.0% |
| CAT-2-module-local-proc | 100.0% | 100.0% |
| CAT-3-cross-file-export | 100.0% | 100.0% |
| CAT-4-form-handler | 100.0% | 100.0% |
| CAT-5-edge-case | 75.0% | 50.0% |

## Failure Taxonomy

### MultilspyBackend
- T04
- T17
- T18

### AstGrepBackend
- T17
