# Benchmark Report - sanity-ast-only

**Tasks:** 20 | **Results:** 20

## Per-Backend Summary

| Backend | Success | Rollback | p50 ms | p95 ms | p99 ms |
|---------|---------|----------|--------|--------|--------|
| AstGrepBackend | 95.0% | 0.0% | 1171 | 1377 | 1586 |

## Per-Category Success Rate

| Category | AstGrepBackend |
|----------|--------|
| CAT-1-local-variable | 100.0% |
| CAT-2-module-local-proc | 100.0% |
| CAT-3-cross-file-export | 100.0% |
| CAT-4-form-handler | 100.0% |
| CAT-5-edge-case | 75.0% |

## Failure Taxonomy

### AstGrepBackend
- T17
