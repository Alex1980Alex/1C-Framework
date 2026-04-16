# R0.1 multilspy quick-test Results

**Date**: 2026-04-17
**DoD**: FAIL (cross-file rename returned 1 edit, need >=2)

## Setup
- multilspy v0.0.15, Python 3.13
- BSL Language Server (bsl-language-server.jar)
- 2-file test workspace: ТестоваяУтилита + ТестовыйВызыватель
- Bulk preload: both files opened via `didOpen` before queries

## Key Fix
- BSL LS uses `--lsp` subcommand, NOT `--stdio` flag
- multilspy `start_server()` is bare — must implement full init cycle:
  `server.start()` → `send.initialize()` → `notify.initialized()`

## Results

| Operation | Result | Notes |
|-----------|--------|-------|
| Initialize | OK (4.5s) | Capabilities returned |
| Document Symbols | 6 symbols | Works within file |
| References | **0** | BSL LS doesn't index workspace |
| Definition (cross-file) | **0** | No cross-file resolution |
| Prepare Rename | OK | Returns correct range |
| Rename (cross-file) | **1 edit** | Only in definition file |
| Rename (local) | 2 edits | Local rename works |
| Workspace Symbol | **0** | Not supported |

## Conclusion
**Scenario 2**: multilspy does NOT help BSL LS with cross-file operations.
The BSL LS doesn't implement workspace-wide symbol indexing — it only
analyzes individual files opened via `didOpen`. This is a fundamental
limitation of BSL LS, not a multilspy issue.

## Path Forward
- **R0.5 Decision**: Scenario 2 (ast-grep + tree-sitter-bsl) or Scenario 3 (full ast-grep)
- multilspy lifecycle management (subprocess, circuit breaker) still useful
- Cross-file rename must be implemented via ast-grep pattern matching

## Artifacts
- `tools/bsl-ls/multilspy_recon.py` — reusable multilspy adapter for BSL LS
- `tools/bsl-ls/multilspy-logs/` — full test results
