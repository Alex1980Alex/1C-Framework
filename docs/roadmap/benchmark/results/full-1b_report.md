# Benchmark Report - full-1b

**Tasks:** 20 | **Results:** 40

## Per-Backend Summary

| Backend | Success | Rollback | p50 ms | p95 ms | p99 ms |
|---------|---------|----------|--------|--------|--------|
| MultilspyBackend | 15.0% | 0.0% | 0 | 1 | 12 |
| AstGrepBackend | 95.0% | 0.0% | 1175 | 1473 | 1684 |

## Per-Category Success Rate

| Category | AstGrepBackend | MultilspyBackend |
|----------|--------|--------|
| CAT-1-local-variable | 100.0% | 50.0% |
| CAT-2-module-local-proc | 100.0% | 0.0% |
| CAT-3-cross-file-export | 100.0% | 25.0% |
| CAT-4-form-handler | 100.0% | 0.0% |
| CAT-5-edge-case | 75.0% | 0.0% |

## Failure Taxonomy

### MultilspyBackend
- T02
- T04
- T05
- T06
- T07
- T08
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

### AstGrepBackend
- T17
