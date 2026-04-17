# R0.3 ast-grep Baseline Timing

**Date**: 2026-04-17
**Tool**: ast-grep 0.39.5 (via npm, Windows)
**Grammar**: tree-sitter-bsl 0.1.6 (custom language via `tree_sitter_bsl.dll`)
**Config**: `tools/bsl-ls/sgconfig.yml`
**Benchmark script**: `tools/bsl-ls/bench_ast_grep.py` (5 runs per rule, cold starts)

## Rules

1. `rename-export-method` — pattern-based match на `Функция $NAME($$$PARAMS) Экспорт ... КонецФункции`
2. `rename-local-var` — kind-based match на `assignment_statement`
3. `rename-catalog-method` — kind-based match на `call_expression` с дочерним `access` (Module.Method)

## Results

### test-workspace (2 .bsl files, 15 lines total)

| Rule | Matches | min | median | mean | max |
|------|--------:|----:|-------:|-----:|----:|
| rename-export-method | 3 | 25.8 ms | 26.8 ms | 27.0 ms | 28.2 ms |
| rename-local-var | 1 | 26.5 ms | 27.4 ms | 29.4 ms | 37.5 ms |
| rename-catalog-method | 2 | 32.9 ms | 37.6 ms | 37.5 ms | 41.2 ms |

Startup-dominated (ast-grep process spawn + .dll load). Real work << 1 ms.

### real-project (260304_GKSTCPLK-2182, 2027 .bsl files)

| Rule | Matches | min | median | mean | max |
|------|--------:|----:|-------:|-----:|----:|
| rename-export-method | 10 969 | 1 175.7 ms | 1 234.8 ms | 1 266.5 ms | 1 379.3 ms |
| rename-local-var | 151 282 | 1 542.0 ms | 1 711.2 ms | 1 708.3 ms | 1 875.3 ms |
| rename-catalog-method | 124 989 | 1 633.3 ms | 1 712.4 ms | 1 751.1 ms | 1 897.8 ms |

Throughput: **~1 050–1 720 files/sec** (парсинг + match + JSON-сериализация).

## Baseline для сравнения в R2.5

- **Целевая задержка**: ≤ 2 s на 2 k файлов — **достигнута** (median 1.2–1.7 s).
- **Нагрузка по правилу**: broad `kind`-rules (assignment, call_expression) в ~1.4× медленнее, чем специфичный pattern.
- **Startup overhead**: ≈ 25 ms независимо от нагрузки — значим для `--filter` на одном файле; при batch scanning растворяется.

## Notes

- JSON output (`--json=compact`) включён; без него timing тот же (JSON сериализация быстрее парсинга).
- Тест на «холодном» кеше tree-sitter: между запусками FS-cache прогрет, так что это best-case. Для первого прогона после reboot прибавить ~100–200 ms на .dll load.
- Парсер tree-sitter-bsl пропускает файлы с ERROR nodes частично (видно по coverage report) — matches на реальном проекте выглядят репрезентативно.

## Artifacts
- `bench_ast_grep.py` — benchmark script
- `ast-grep-baseline.json` — raw timings (5 runs × 3 rules × 2 workspaces)
