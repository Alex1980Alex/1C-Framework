# R0.1 multilspy quick-test Results

**Date**: 2026-04-17 (revised after GitHub source-code study)
**DoD**: **PASS** — cross-file rename returned 2 edits across 2 files, once workspace was structured as a real 1C configuration dump.

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

### Attempt 1 — minimal workspace (FAIL)

| Operation | Result |
|-----------|--------|
| Document Symbols | 6 |
| References | 0 |
| Definition (cross-file) | 0 |
| Rename (cross-file) | **1 edit** |
| Rename (local) | 2 edits |
| Workspace Symbol | 1 match |

Workspace had only `.bsl` files + rudimentary `Configuration.xml` (no `xmlns="http://v8.1c.ru/8.3/MDClasses"`), no per-module XML descriptors.

### Attempt 2 — proper 1C configuration layout (PASS)

After studying `BSLLanguageServer.initialize` + `ServerContext.populateContext` + `ReferenceIndexFiller` on GitHub, root cause was identified: BSL LS relies on `mdclasses` to parse configuration metadata, which requires:
- `Configuration.xml` with full `xmlns="http://v8.1c.ru/8.3/MDClasses"` namespace
- **Per-module `.xml` descriptor** next to each `CommonModules/<Name>/` folder (Name, Server, Global, ServerCall, etc.)
- Optional `.bsl-language-server.json` at workspace root

Once per-module XML descriptors were added:

| Operation | Result | Notes |
|-----------|--------|-------|
| Rename (cross-file) | **2 edits / 2 files** | `ТестоваяУтилита/Module.bsl:0:8-24` + `ТестовыйВызыватель/Module.bsl:1:28-44` |
| Rename (local) | 2 edits | Unchanged |
| References / Definition at encoded-position | 0 | Likely UTF-16 char offset mismatch on Cyrillic identifiers; rename works because prepare_rename returns resolved range first |

Raw LSP response: `multilspy-logs/05_rename_cross_file.json` (both files in `.changes`).

## Critical Insight

BSL LS **does** support cross-file rename in LSP mode, but only when the workspace is a **real 1C configuration dump** (XML descriptors present). Minimal synthetic workspaces silently degrade because `mdclasses` cannot resolve module metadata, and `ReferenceIndex` stays empty.

Downstream implications for §5.5 routing: Scenario 1 (multilspy) is viable for real projects. ast-grep remains useful for fast pattern-level rewrites and as fallback when `mdclasses` rejects a workspace.

## Conclusion (revised)

BSL LS **supports cross-file rename** via LSP when the workspace is a proper 1C
configuration dump. The prior "FAIL" verdict was a workspace-structure artifact,
not a BSL LS limitation.

## Path Forward (revised)
- **R0.5 Decision**: reconsider — Scenario 1 (multilspy + BSL LS) is viable for real
  projects that always ship with per-module XML descriptors.
- Hybrid approach remains strongest: multilspy for semantic cross-file rename, ast-grep for
  bulk pattern rewrites / fallback when `mdclasses` fails to parse a configuration.
- Add pre-flight check to refactor tool: validate presence of per-module XML descriptors
  before dispatching to multilspy backend; fall back to ast-grep otherwise.

## Artifacts
- `tools/bsl-ls/multilspy_recon.py` — reusable multilspy adapter for BSL LS
- `tools/bsl-ls/multilspy-logs/` — full test results
