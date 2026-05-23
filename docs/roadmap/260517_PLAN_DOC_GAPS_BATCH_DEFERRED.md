# Doc Content Gaps Closure Plan (DEFERRED batch, 2026-05-17)

> **Статус:** 104 documentation gaps detected by `/audit-docs`. Bulk content authoring task — defer to dedicated session с LLM batch delegation.

## Current state

После `/audit-docs --update` сессии 2026-05-17:
- ✅ **0 skill gaps** (was 109 → closed via auto-update)
- ⚠️ **104 doc gaps** remain (require manual content, не list-table appends)

| Category | Missing | Target file |
|---|---|---|
| bsl_tool | 32 | `28_BSL_SEMANTIC_SEARCH/*` (по подсистемам) |
| hook | 33 | `09_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md` |
| memory_subsystem | 39 | `27_UNIFIED_MEMORY/*` |

## Why deferred

**Per-entry effort:** ~3-5 min manual (read source, write 50-100 word description, link to file)
- 104 × 4 min = ~7 hours pure manual content
- Не оправдывает single-session budget

**Best execution mode:** batch via LLM (Z.AI subscription) с Opus review

## Execution path (when scheduled)

### Phase 1: Script preparation (~30 min)

Write `scripts/generate_doc_stubs.py`:

```python
"""Batch-generate doc entries for AUDIT_DOCS_SKILLS gaps."""

from pathlib import Path
import json

def parse_audit_report(path: Path) -> dict:
    """Extract gaps from docs/analysis/AUDIT_DOCS_SKILLS.md."""
    # Parse markdown → {category: [{name, source_file, target_doc}]}

def generate_entry_via_llm(name: str, source_file: str) -> str:
    """Use mcp__llm-rotation__llm_complete to generate 50-100 word doc entry."""
    prompt = f'''Read this Python module:
    {Path(source_file).read_text()[:3000]}

    Generate a documentation entry для класса/функции `{name}`:
    - 2-3 sentences explaining purpose
    - Key methods/fields if relevant
    - Russian language, Markdown table row format

    Return ONLY: `| {name} | description | use case |`
    '''
    return llm_complete(prompt, max_tokens=200)["text"]

def append_to_target(target_doc: Path, entries: list[str]) -> None:
    """Insert entries into appropriate section of target doc."""
    # Find ## section, append table rows
```

### Phase 2: Batch generation (~2 hours wall-clock на subscription tier)

```bash
# Run on bsl_tool category first (32 entries × 15s = 8 min)
python scripts/generate_doc_stubs.py --category bsl_tool --dry-run  # preview
python scripts/generate_doc_stubs.py --category bsl_tool             # commit

# Then hook (33 × 15s = 8 min)
python scripts/generate_doc_stubs.py --category hook

# Then memory_subsystem (39 × 15s = 10 min, longer due to complexity)
python scripts/generate_doc_stubs.py --category memory_subsystem
```

Cost: ~$0 (claude-cli subscription) или ~$1-2 (paid Haiku API).

### Phase 3: Manual review (~1 hour)

- Scan generated entries для accuracy
- Fix Russian grammar где LLM ошибся
- Verify section placement правильное
- Re-run `/audit-docs --fix` → expect 0 gaps

### Phase 4: Commit + push

Single commit per category для clean history:
- `docs(audit): bsl_tool stubs (32 entries)`
- `docs(audit): hook stubs (33 entries)`
- `docs(audit): memory_subsystem stubs (39 entries)`

## Acceptance criteria

- [ ] /audit-docs reports 0 doc gaps
- [ ] Manual review checklist signed off (accuracy, language, placement)
- [ ] No regression in existing docs (existing content untouched)

## Investment

| Phase | Time | Cost |
|---|---|---|
| Script prep | 30 min eng | $0 |
| Batch gen | 2h wall-clock (background) | $0-2 LLM |
| Manual review | 1h eng | $0 |
| **Total** | **~3.5h eng** | **~$2** |

## Связанные документы

- [docs/analysis/AUDIT_DOCS_SKILLS.md](../analysis/AUDIT_DOCS_SKILLS.md) — current gap list (refreshed by /audit-docs)
- [scripts/audit_docs_skills.py](../../scripts/audit_docs_skills.py) — auditor
- Memory: [aggressive delegation protocol](../../.claude/projects/C--1--Framework/memory/feedback_delegation_aggressive.md)

## Decision

**DEFERRED** — bulk content authoring better suited для dedicated session с LLM batch delegation. Re-evaluation triggers:
1. Documentation drift becomes UX-blocking
2. New contributor onboarding бьётся об missing entries
3. /ultrareview flagged как documentation completeness issue
