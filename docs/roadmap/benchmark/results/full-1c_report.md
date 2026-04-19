# Benchmark Report - full-1c

**Tasks:** 20 | **Results:** 40

## Per-Backend Summary

| Backend | Success | Rollback | p50 ms | p95 ms | p99 ms |
|---------|---------|----------|--------|--------|--------|
| MultilspyBackend | 80.0% | 0.0% | 0 | 2 | 10 |
| AstGrepBackend | 20.0% | 0.0% | 0 | 1399 | 1409 |

## Per-Category Success Rate

| Category | AstGrepBackend | MultilspyBackend |
|----------|--------|--------|
| CAT-1-local-variable | 75.0% | 75.0% |
| CAT-2-module-local-proc | 25.0% | 75.0% |
| CAT-3-cross-file-export | 0.0% | 100.0% |
| CAT-4-form-handler | 0.0% | 100.0% |
| CAT-5-edge-case | 0.0% | 50.0% |

## Failure Taxonomy

### MultilspyBackend
- T04
- T05
- T17
- T18

### AstGrepBackend
- T02
- T06
- T07
- T08
- T09
- T10
- T11
- T12
- T13
- T14
- T15
- T16
- T17
- T18
- T19
- T20
