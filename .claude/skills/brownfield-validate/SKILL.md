---
name: brownfield-validate
description: Validate implemented code against OpenSpec artifacts (specs, design, tasks). Three validators — Gap, Design, Impl — check completeness, architecture, and coding standards for 1C brownfield changes.
license: MIT
metadata:
  author: 1c-framework
  version: "1.0"
---

Brownfield Validation Suite for SDD workflow. Run after `/opsx:apply` to validate implementation against approved specs.

**Input**: `$ARGUMENTS` — change name (optional), validator filter (`--gap`, `--design`, `--impl`, or all by default)

## When to Use

- After `/opsx:apply` completes implementation tasks
- Before `/opsx:archive` to ensure completeness
- As pre-merge validation for 1C code changes
- Complements `code-verify` (quality) with spec-compliance checks

## Three Validators

| Validator | Checks | Reference | MCP Tools |
|-----------|--------|-----------|-----------|
| **Gap** | Every MUST/SHALL in specs is implemented | `specs/*.md` | `bsl_search`, `bsl_hybrid_search` |
| **Design** | Code follows architecture from design.md | `design.md` | `bsl_search`, `get_metadata` |
| **Impl** | Coding standards, syntax, test coverage | BSL standards | `check_syntax_designer_modules`, `run_all_tests` |

## Steps

### 1. Select the change

Parse `$ARGUMENTS` for change name and validator filter flags.

If no name:
- Run `openspec list --json` to get active changes
- Auto-select if only one; ask if multiple

Read all artifacts:
- `openspec/changes/<name>/specs/` — all spec files
- `openspec/changes/<name>/design.md`
- `openspec/changes/<name>/tasks.md`

### 2. Identify changed files

From `tasks.md`, extract the list of files that were modified/created during implementation.
Read each file to have the current code for validation.

### 3. Gap Validator (specs vs code)

**Goal:** Every requirement marked MUST/SHALL in specs is implemented in code.

**Process:**
1. Parse specs files — extract all requirements with RFC 2119 keywords:
   - `MUST` / `SHALL` — mandatory, must be in code
   - `SHOULD` — recommended, warn if missing
   - `MAY` — optional, skip
2. For each MUST/SHALL requirement:
   - Search the changed code for evidence of implementation
   - For query changes: verify SQL patterns match spec (JOIN conditions, WHERE clauses)
   - For new objects: verify object exists via `get_metadata` if available
   - For behavior: check Given/When/Then scenarios are covered
3. For each MODIFIED requirement: verify the "Became" (Стало) behavior is in code, not the "Was" (Было)

**Output per requirement:**
```
| # | Requirement | Status | Evidence |
|---|-------------|--------|----------|
| 1 | LEFT JOIN с РегистрацияНаПЛК (MUST) | PASS | line 45: LEFT JOIN |
| 2 | Проверка Проведен = ИСТИНА (MUST) | PASS | line 48: WHERE clause |
| 3 | Сценарий: другая точка маршрута (SHOULD) | WARN | No explicit test |
```

**Verdict:**
- `PASS` — all MUST/SHALL requirements found in code
- `PARTIAL` — some SHOULD requirements missing (list them)
- `FAIL` — MUST/SHALL requirements missing (list them)

### 4. Design Validator (design.md vs code)

**Goal:** Code follows the architectural decisions from design.md.

**Process:**
1. Parse design.md — extract:
   - Modules to be changed (module names, procedure signatures)
   - SQL query structure (tables, joins, conditions)
   - Dependencies between modules
   - Patterns to use (existing functions to call, not duplicate)
2. For each architectural decision:
   - **Module check:** correct module was modified (not a different one)
   - **Signature check:** procedure/function signatures match design
   - **Pattern check:** uses referenced existing functions, doesn't duplicate
   - **SQL check:** query structure matches design (same tables, join type, conditions)
   - **No scope creep:** code doesn't touch files outside design scope
3. Use MCP for verification where applicable:
   ```
   mcp__bsl-semantic-search__bsl_search(query="<function name from design>")
   ```

**Output:**
```
| # | Design Decision | Status | Details |
|---|----------------|--------|---------|
| 1 | Modify МодульМенеджера.ПолучитьДанные | PASS | Procedure found, signature matches |
| 2 | Use LEFT JOIN pattern | PASS | Correct join type |
| 3 | No new metadata objects | PASS | No ADDED objects detected |
| 4 | Reference existing ПроверитьПроведение() | FAIL | Duplicated logic instead |
```

**Verdict:**
- `PASS` — all design decisions followed
- `PARTIAL` — minor deviations (naming, formatting)
- `FAIL` — wrong module, wrong pattern, scope creep, duplicated logic

### 5. Impl Validator (coding standards + tests)

**Goal:** Code meets 1C BSL coding standards and has test coverage.

**Process:**
1. **Syntax check** (if METR/test-runner available):
   ```
   mcp__mcp-onec-test-runner__check_syntax_designer_modules()
   ```
   or
   ```
   mcp__mcp-onec-test-runner__check_syntax_edt()
   ```

2. **Coding standards** (manual check):
   - Naming: CamelCase for procedures, camelCase for variables
   - Prefix: `гкс_` for custom objects
   - Comments: task number present (`// GKSTCPLK-XXXX`)
   - No hardcoded values (magic numbers, hardcoded refs)
   - Query text: parameterized, no string concatenation

3. **Test coverage** (if tests exist):
   ```
   mcp__mcp-onec-test-runner__run_all_tests()
   ```
   Check that changed functionality has corresponding test scenarios.

4. **Static analysis** (if available):
   ```
   mcp__bsl-semantic-search__bsl_search(query="<changed function>")
   ```
   Compare coding style with similar functions in the codebase.

**Output:**
```
| # | Check | Status | Details |
|---|-------|--------|---------|
| 1 | Syntax | PASS | No errors |
| 2 | Naming conventions | PASS | CamelCase OK |
| 3 | Task number comment | PASS | // GKSTCPLK-2256 found |
| 4 | No hardcoded values | WARN | Line 12: hardcoded "Склад-1" |
| 5 | Tests | SKIP | MCP test runner unavailable |
```

**Verdict:** PASS / PARTIAL / FAIL

### 6. Consolidated Report

Combine all 3 validators into a final report:

```
## Brownfield Validation Report: <change-name>

### Summary
| Validator | Result | Issues |
|-----------|--------|--------|
| Gap       | PASS   | 0      |
| Design    | PASS   | 0      |
| Impl      | PARTIAL| 1 warn |

### Overall: PASS (1 warning)

### Details
[... per-validator tables ...]

### Recommendations
[... if any ...]
```

**Overall verdict:**
- `PASS` — all 3 validators pass
- `PARTIAL` — warnings only, no FAIL validators
- `FAIL` — at least one validator failed

If FAIL: suggest specific fixes before archiving.
If PASS: suggest `/opsx:archive <name>`.

## Graceful Degradation

- **MCP unavailable:** Skip MCP-dependent checks, mark as `SKIP` (not FAIL)
- **No tests:** Skip test coverage check, note in report
- **Specs incomplete:** Validate what exists, warn about missing specs sections
- **No design.md:** Skip Design Validator entirely, warn

## Guardrails

- ALWAYS read all spec files before starting validation
- NEVER modify code during validation — only report findings
- If a validator cannot run (missing artifacts/MCP), mark as SKIP, not FAIL
- Report is informational — blocking is handled by approval-gate hook
- Use MCP tools for verification where possible, fall back to grep/read
