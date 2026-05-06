---
unified_id: 019f8a3b-5c7d-7e2a-9f1b-4d6e8a0c2b50
status: active
tags: [meta, chronology, log]
related: [[_index]], [[SCHEMA]]
created_at: 2026-04-20T10:00:00Z
updated_at: 2026-04-20T10:00:00Z
confidence: 1.0
---

# Wiki Log

Chronology of knowledge promotions (L2→L3), wiki page lifecycle events, and significant session summaries. Auto-appended by `session-memory-save` hook on Stop.

**Limit:** 500 lines. Older entries archived to `docs/wiki/archive/log-YYYY-MM.md`.

---

## 2026-04-20 — Initial Bootstrap

**Event:** Wiki schema and log created (Hermes Phase 2)

- Created `SCHEMA.md` — naming rules, frontmatter schema, promotion thresholds, archival policy
- Created `log.md` — this file
- DSPy Signatures module created (`src/pdf_framework/prompts/signatures.py`): GraderSignature, HallucinationCheckSignature, RewriterSignature
- Migrated 3 RAG agent nodes to DSPy: `grader.py`, `rewriter.py`, `hallucination_checker.py`

**Status:** Phase 2 DSPy Deepening in progress. Wiki schema established.

---

## Format Template

```
## YYYY-MM-DD — [Title]

**Event:** [Brief description]

- [Change 1]
- [Change 2]

**Status:** [Current state or next step]
```

## 2026-04-21 — Session Summary

**Event:** Auto-saved session

- Skills: evaluation-benchmark, learn:pytest-framework, learning-loop, code-verify, task-protocol
- Files changed: 2
- Summary: Session 2026-04-21. Skills: evaluation-benchmark, learn:pytest-framework, learning-loop, code-verify, task-protocol, z-ai-delegation, 1c-doc-research, learn:fastapi-framework. Changed 2 files in .pre-commit-config.yaml, mcp-server.log. Commit: chore: auto-save tasks.md, 260413_Hermes Agent и LLM Wiki Карпати персистентные системы знаний.md, spec.md +1 more. Commit: chore: auto-commit 2 file(s) changed. Commit: docs(hermes): sync tasks.md Phase 0-4 status + fix link_registry.db path


## 2026-04-22 — Session Summary

**Event:** Auto-saved session

- Skills: wiki-pipeline, evaluation-benchmark, delegation-classifier, create-hook, code-verify
- Files changed: 2
- Summary: Session 2026-04-22. Skills: wiki-pipeline, evaluation-benchmark, delegation-classifier, create-hook, code-verify. Changed 2 files in docs/framework documentation, mcp-server.log. Commit: chore: auto-commit 1 file(s) changed. Commit: chore: auto-save SKILL.md. Commit: chore: auto-save SKILL.md


## 2026-04-23 — Session Summary

**Event:** Auto-saved session

- Skills: bsl-development, 1c-doc-research, git-commit-message, code-verify
- Files changed: 2
- Summary: Session 2026-04-23. Skills: bsl-development, 1c-doc-research, git-commit-message, code-verify. Changed 2 files in mcp-server.log, src/projects. Commit: chore: auto-commit 4 file(s) changed. Commit: chore: update submodule ref (GKSTCPLK-composite-promezh — fix alias-конфликт в ВТ_ЕдиничныеПробы). Commit: chore: auto-commit 1 file(s) changed


## 2026-04-26 — Session Summary

**Event:** Auto-saved session

- Skills: none
- Files changed: 8
- Summary: Session 2026-04-26. Changed 8 files in .claude/settings.local.json, .tmp/, 2, C, data/analyze-1c-research. Commit: chore: migrate hook paths from D:/1С-Framework to C:/1С-Framework


## 2026-04-27 — Session Summary

**Event:** Auto-saved session

- Skills: z-ai-delegation, code-verify, qdrant-operations, embedding-models, learn:1c-metadata-objects
- Files changed: 2
- Summary: Session 2026-04-27. Skills: z-ai-delegation, code-verify, qdrant-operations, embedding-models, learn:1c-metadata-objects, indexing-pipeline. Changed 2 files in .claude/settings.local.json, tmp/phase8


## 2026-04-28 — Session Summary

**Event:** Auto-saved session

- Skills: z-ai-delegation, code-verify, qdrant-operations, embedding-models, learn:1c-metadata-objects
- Files changed: 3
- Summary: Session 2026-04-28. Skills: z-ai-delegation, code-verify, qdrant-operations, embedding-models, learn:1c-metadata-objects, indexing-pipeline, tech-research, tenacity-retry. Changed 3 files in .claude/settings.local.json, scripts/reindex_bsl_qwen3.py, tmp/phase8. Commit: feat(phase8.10): length-bucketed dynamic batching for Qwen3-ST. Commit: chore(wiki): auto-log session summary 2026-04-27


## 2026-04-29 — Session Summary

**Event:** Auto-saved session

- Skills: z-ai-delegation, code-verify, qdrant-operations, embedding-models, learn:1c-metadata-objects
- Files changed: 0
- Summary: Session 2026-04-29. Skills: z-ai-delegation, code-verify, qdrant-operations, embedding-models, learn:1c-metadata-objects, indexing-pipeline, tech-research, tenacity-retry. Commit: fix(phase8.12): TEI DTYPE bfloat16→float16 (8.12.6). Commit: docs(phase8.12): document TEI backend in Docker doc + deployment skill. Commit: feat(phase8.12): A3 TEI Docker backend for Qwen3 reindex (8.12.6)


## 2026-04-30 — Session Summary

**Event:** Auto-saved session

- Skills: deployment, qdrant-operations, learn:1c-metadata-objects, learning-loop, task-protocol
- Files changed: 0
- Summary: Session 2026-04-30. Skills: deployment, qdrant-operations, learn:1c-metadata-objects, learning-loop, task-protocol, embedding-models, code-verify, evaluation-benchmark. Commit: docs(skills): sync embedding-models / qdrant-operations / framework-config with Phase 8.12 (roadmap 8.10.2). Commit: feat(phase8.12.8): wire Z.AI direct + small fixes from pilot smoke. Commit: feat(phase8.12.8): implement steps 2-4 (cluster + generate + label)


## 2026-05-01 — Session Summary

**Event:** Auto-saved session

- Skills: deployment, qdrant-operations, learn:1c-metadata-objects, learning-loop, task-protocol
- Files changed: 6
- Summary: Session 2026-05-01. Skills: deployment, qdrant-operations, learn:1c-metadata-objects, learning-loop, task-protocol, embedding-models, code-verify, evaluation-benchmark. Changed 6 files in .claude/settings.local.json, claude/settings.local.json, docs/roadmap. Commit: docs(audit): chapter 01_ОБЗОР deep cross-check vs реальная имплементация. Commit: docs(roadmap): expand 260430 audit roadmap с максимальной декомпозицией. Commit: docs(roadmap): 260430 audit findings — doc/code gaps post Phase 8+9.1


## 2026-05-02 — Session Summary

**Event:** Auto-saved session

- Skills: task-protocol, qdrant-operations, evaluation-benchmark, code-verify, claude-code-cli-interactive
- Files changed: 2
- Summary: Session 2026-05-02. Skills: task-protocol, qdrant-operations, evaluation-benchmark, code-verify, claude-code-cli-interactive, claude-code-settings, simplify, update-config. Changed 2 files in .claude/settings.local.json, claude/settings.local.json


## 2026-05-03 — Session Summary

**Event:** Auto-saved session

- Skills: z-ai-delegation, deployment, task-protocol
- Files changed: 3
- Summary: Session 2026-05-03. Skills: z-ai-delegation, deployment, task-protocol. Changed 3 files in configuration/260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС, configuration/260416_GKSTCPLK-2368 Восстановить предопределенные элементы справочников, ИБTransportManagementDevelop/docs. Commit: docs(roadmap): GraphRAG для BSL — max coverage сложных запросов. Commit: chore: auto-commit 3 file(s) changed. Commit: chore: auto-commit 197 file(s) changed


## 2026-05-04 — Session Summary

**Event:** Auto-saved session

- Skills: task-protocol, evaluation-benchmark, qdrant-operations, code-verify, bsl-development
- Files changed: 4
- Summary: Session 2026-05-04. Skills: task-protocol, evaluation-benchmark, qdrant-operations, code-verify, bsl-development, tech-research, embedding-models. Changed 4 files in configuration/260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС, configuration/260416_GKSTCPLK-2368 Восстановить предопределенные элементы справочников, src/bsl, ИБTransportManagementDevelop/docs. Commit: chore: auto-save qwen3_embedding.py. Commit: chore: auto-save qwen3_embedding.py. Commit: chore: auto-save qwen3_embedding.py


## 2026-05-05 — Session Summary

**Event:** Auto-saved session

- Skills: embedding-models, search-pipeline-debug, qdrant-operations, code-verify, bsl-development
- Files changed: 3
- Summary: Session 2026-05-05. Skills: embedding-models, search-pipeline-debug, qdrant-operations, code-verify, bsl-development, audit-docs, update-config, task-protocol. Changed 3 files in configuration/260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС, configuration/260416_GKSTCPLK-2368 Восстановить предопределенные элементы справочников, ИБTransportManagementDevelop/docs. Commit: fix: Исправлено логирование slash-команд при backtick-quoted prompts. Commit: chore: auto-save run_context.py. Commit: chore: auto-save run_context.py


## 2026-05-06 — Session Summary

**Event:** Auto-saved session

- Skills: create-hook, code-verify, claude-code-hooks-bugs, implement-1c-task, framework-troubleshooting
- Files changed: 3
- Summary: Session 2026-05-06. Skills: create-hook, code-verify, claude-code-hooks-bugs, implement-1c-task, framework-troubleshooting. Changed 3 files in configuration/260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС, configuration/260416_GKSTCPLK-2368 Восстановить предопределенные элементы справочников, ИБTransportManagementDevelop/docs. Commit: chore: auto-save edt-mcp-plugin-install.md, _index.json. Commit: chore: auto-commit 3 file(s) changed


## 2026-05-07 — Session Summary

**Event:** Auto-saved session

- Skills: create-hook, code-verify, claude-code-hooks-bugs, implement-1c-task, framework-troubleshooting
- Files changed: 3
- Summary: Session 2026-05-07. Skills: create-hook, code-verify, claude-code-hooks-bugs, implement-1c-task, framework-troubleshooting, update-config. Changed 3 files in configuration/260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС, configuration/260416_GKSTCPLK-2368 Восстановить предопределенные элементы справочников, ИБTransportManagementDevelop/docs. Commit: chore: auto-save .mcp.json. Commit: chore: auto-commit 3 file(s) changed. Commit: chore: auto-save application-testdb.yml, .mcp.json

