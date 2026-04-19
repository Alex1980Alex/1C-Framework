# Benchmark Trend

| Run ID | Date | Commit | Backends | Success | Total | Notes |
|--------|------|--------|----------|---------|-------|-------|
| run-20260418-195101 | 2026-04-18 | HEAD | ast-grep | BLOCKED | 20 | tree-sitter-bsl .dll missing |
| run-20260418-203328 | 2026-04-18 | HEAD | ast-grep | 0% | 20 | --inline-rules broken on Windows |
| run-20260418-203702 | 2026-04-18 | HEAD | ast-grep | 0% | 20 | shell=True breaks multiline YAML |
| run-20260418-204045 | 2026-04-18 | HEAD | ast-grep | 30% | 20 | temp file fix works; 1-based line bug |
| run-20260418-204337 | 2026-04-18 | HEAD | ast-grep | 35% | 20 | _word_at whitespace scan fix |
| run-20260418-204655 | 2026-04-18 | HEAD | ast-grep | **95%** | 20 | 1-based line fix; CAT1-4 100%, CAT5 75% |
| run-20260418-210222 | 2026-04-18 | HEAD | ast-grep | **95%** | 20 | verification run; R5.5 calibration applied: local_variable 0.70→0.95, module_local 0.85→0.95, form_handler 0.60→0.95 |
