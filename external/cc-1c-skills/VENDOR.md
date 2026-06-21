# Vendored: cc-1c-skills

Pinned vendored copy of an upstream AI-agent skill-set for 1C:Enterprise 8.3 XML artifact editing.

| Field | Value |
|---|---|
| Upstream | https://github.com/Nikolay-Shirokov/cc-1c-skills |
| Pinned commit | `3d36c2026916d2ae8915f0aca0836d55e1ccaabe` |
| Commit date | 2026-06-21 |
| License | MIT |
| Vendored on | 2026-06-21 |
| Decision | [ADR-031](../../.claude/skills/architecture-research/adr/031-cc-1c-skills-adopt-offline-mxl-dcs-editor.md) — ADOPT |

## Excluded from vendor copy
- `.git/` (use pin SHA above for provenance)
- `tests/` (~12 MB, not needed at runtime)
- `.github/`

## What we use (Python ports, dep: Python 3.x + lxml)
- **Spreadsheet (.mxl/.mxlx)** — `.claude/skills/mxl-decompile|mxl-compile|mxl-info|mxl-validate/scripts/*.py`
  - round-trip XML ↔ JSON DSL, in-place via DOM.
- **Data-composition (.dcs)** — `.claude/skills/skd-info|skd-edit|skd-compile|skd-decompile|skd-validate/scripts/*.py`
  - `skd-edit` = 30+ point operations in-place; `skd-info` reads datasets/fields/params/variants; validator trained on 930+ real schemas.

These read/write the SAME XML EDT stores (`SpreadsheetDocument.xml` = `.mxlx`, `DataCompositionSchema.xml` = `.dcs`).

## Verified (ADR-031, 2026-06-21, live on real project files — 3/3 PASS)
1. MXL round-trip on a real `.mxlx` — cell text-values 84/84, 0 lost.
2. DCS read on a real `.dcs` — full structure (codepilot `dcs_manage` returned 0 here).
3. DCS `add-parameter` on a copy — applied; original untouched (md5 match).

## Update procedure
```
git clone https://github.com/Nikolay-Shirokov/cc-1c-skills <tmp>
robocopy <tmp> external\cc-1c-skills /E /XD .git tests .github /XF *.pyc
# bump "Pinned commit" above to the new HEAD
```
