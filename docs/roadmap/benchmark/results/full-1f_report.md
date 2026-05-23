# Benchmark Report - full-1f

**Tasks:** 20 | **Results:** 40

## Per-Backend Summary

| Backend | Success | Rollback | p50 ms | p95 ms | p99 ms |
|---------|---------|----------|--------|--------|--------|
| MultilspyBackend | 55.0% | 0.0% | 0 | 2 | 10 |
| AstGrepBackend | 15.0% | 0.0% | 1182 | 1532 | 1720 |

## Per-Category Success Rate

| Category | AstGrepBackend | MultilspyBackend |
|----------|--------|--------|
| CAT-1-local-variable | 25.0% | 100.0% |
| CAT-2-module-local-proc | 0.0% | 100.0% |
| CAT-3-cross-file-export | 25.0% | 25.0% |
| CAT-4-form-handler | 0.0% | 0.0% |
| CAT-5-edge-case | 25.0% | 50.0% |

## Failure Taxonomy

### MultilspyBackend
- T09
- T11
- T12
- T13
- T14
- T15
- T16
- T19
- T20

### AstGrepBackend
- T01
- T02
- T04
- T05
- T06
- T07
- T08
- T09
- T11
- T12
- T13
- T14
- T15
- T16
- T18
- T19
- T20
