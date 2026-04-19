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
| full-1 | 2026-04-19 | HEAD | multilspy,ast-grep | 22/40 | 40 | first real multilspy run; ast-grep 95% (19/20), multilspy 15% (3/20); workspace_root=REPO_ROOT |
| full-1b | 2026-04-19 | HEAD | multilspy,ast-grep | 22/40 | 40 | verify with workspace_root=src/bsl (Configuration.xml present) — same 15% multilspy → confirms BSL LS per-doc indexing limitation, not workspace-root issue; motivates R6.2 |
| full-1c | 2026-04-19 | HEAD | multilspy,ast-grep | 20/40 | 40 | investigation: tasks.json manually 0-based'd → multilspy 80%, ast-grep 20% (regressed) → exposed convention mismatch between backends |
| full-1d | 2026-04-19 | HEAD | multilspy,ast-grep | **36/40** | 40 | **root cause fixed**: tasks.json is 1-based (EDT-MCP conv), MultilspyBackend now converts to LSP 0-based internally. multilspy **85%** (17/20), ast-grep **95%** (19/20); CAT-2/3/4 both 100%, only CAT-5 edge cases fail |
| full-1e | 2026-04-19 | HEAD | multilspy,ast-grep | 37/40 | 40 | T04 fix + success=`edits_match_expected`; CLI still shows old `applied` metric (37/40) |
| full-1f | 2026-04-19 | HEAD | multilspy,ast-grep | 37/40 | 40 | URI normalization fix (URL-decode Cyrillic, strip `file:///` before wt_prefix); reports now use strict metric correctly |
| full-1g | 2026-04-19 | HEAD | multilspy,ast-grep | **14/40** | 40 | **final, strict metric** — multilspy **55%** (11/20) vs ast-grep **15%** (3/20). Multilspy CAT-1/2 at 100%, ast-grep under-performs due to text-based over-matching (false-positive edits in other files). CAT-3/4 low numbers reflect tasks.json `expected_files` ground-truth incompleteness for cross-file scenarios, not backend bug |
| option-a-on | 2026-04-19 | HEAD | ast-grep | 4/20 | 20 | ast-grep only |
| option-a-off | 2026-04-19 | HEAD | ast-grep | 3/20 | 20 | ast-grep only |
