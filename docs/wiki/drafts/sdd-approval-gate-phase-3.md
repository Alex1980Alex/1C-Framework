---
confidence: 0.8042320470818165
content_hash: b65598c696525289
content_type: wiki
created_at: '2026-06-21T05:21:39.193970'
importance: 0.5
memory_type: wiki
source: obsidian-vault
tags:
- 1c
- approval
- gate
- hooks
- project
- sdd
- skills
title: SDD Approval Gate (Phase 3)
unified_id: wiki:obsidian-vault:d57d85a9-4f1a-407d-b2a6-6b621f040055
updated_at: '2026-06-21T05:21:39.193973'
version: 1
---

## Content

SDD Approval Gate (Phase 3) | OpenSpec approval gate — hook blocks implement/apply without approved design in .openspec.yaml | SDD Phase 3 Approval Gate implemented (2026-04-01).

**Components:**
- `approval-gate.py`: PreToolUse:Skill hook, blocks `implement-1c-task`, `opsx:apply`, `openspec-apply-change` unless `.openspec.yaml` has `approval.status: approved`
- `opsx-approve` skill: review artifacts → approve/reject → updates `.openspec.yaml`
- `openspec-mcp` v0.4.2: added to `.mcp.json` (dashboard, approval workflow)

**Approval status tracking:**
```yaml
# openspec/changes/<name>/.openspec.yaml
approval:
  status: pending|approved|rejected
  reviewed_by: human
  reviewed_at: <ISO datetime>
  comment: <text or null>
```

**Workflow:** Explore → Propose → `/opsx:approve <change>` → Apply → `brownfield-validate` → Archive

**Why:** Prevents AI from implementing code changes without human review of design/specs. Critical for 1C brownfield modifications where architectural errors are expensive.

**How to apply:** When implementing 1C tasks through SDD workflow, always approve the design first. The hook auto-blocks otherwise.