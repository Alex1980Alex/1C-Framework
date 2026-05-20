---
unified_id: 019f8a3b-5c7d-7e2a-9f1b-4d6e8a0c2b50
status: active
tags: [meta, chronology, log]
related:
  - '[[_index]]'
  - '[[SCHEMA]]'
created_at: 2026-04-20T10:00:00Z
updated_at: 2026-04-20T10:00:00Z
confidence: 1.0
---

<!-- markdownlint-disable MD013 MD012 MD040 -->

# Wiki Log

Chronology of knowledge promotions (L2→L3), wiki page lifecycle events, and significant session summaries. Auto-appended by `session-memory-save` hook on Stop.

**Limit:** 500 lines. Older entries archived to `docs/wiki/archive/log-YYYY-MM.md`.

---

## 2026-05-15 — Hermes Phase 5 + 6 Sprint Complete

**Event:** Hermes Ф5 (Sandbox) и Ф6 (OAuth) closed in two sprints

### Ф5 (Sandbox) — все 4 deliverables

- F1 `LangSmithBackend` (Firecracker microVM via `langsmith[sandbox]`, GA May 2026)
- F2 `E2BBackend` (stateful Jupyter Kernel, vendor-neutral)
- F3 skill `sandbox-execution` + log entry (this one)
- DryRun zero-dep fallback retained as CI/no-key default
- 38 unit tests (13 DryRun + 13 LangSmith + 12 E2B), `select_backend()` env-driven helper

### Ф6 (OAuth) — Sprint 1 + 2

- F4 audit doc [`docs/wiki/auth/oauth2-service.md`](auth/oauth2-service.md)
- F5.1 BSL wrapper `src/bsl/mcp_server/auth/oauth2.py` 214→78 LoC thin async adapter
- F5.2 reusable FastAPI router `src/shared/mcp_oauth/fastapi/` (build_oauth_router + require_oauth)
- F5.3 regression 47/47 OAuth-domain tests pass, zero new fails
- F5.4 audit logging `AuditedOAuth2Service` + `OAuthAuditEvent` (5 event types)
- F5.5 `.mcp.json` env vars + [`oauth-setup.md`](auth/oauth-setup.md) (PKCE flow + httpx client + troubleshooting)

**Status:** Hermes-llm-wiki Phase 5 + Phase 6 ready for `/opsx:archive hermes-llm-wiki`.

**Architecture finding:** pdf-vector-graph MCP — stdio-only, OAuth not applicable to local transport. F5.2 retargeted as reusable FastAPI router in `src.shared.mcp_oauth.fastapi` for any future HTTP MCP server (one-line `app.include_router()` to enable).

---

## 2026-04-20 — Initial Bootstrap

**Event:** Wiki schema and log created (Hermes Phase 2)

- Created `SCHEMA.md` — naming rules, frontmatter schema, promotion thresholds, archival policy
- Created `log.md` — this file
- DSPy Signatures module created (`src/pdf_framework/prompts/signatures.py`): GraderSignature, HallucinationCheckSignature, RewriterSignature
- Migrated 3 RAG agent nodes to DSPy: `grader.py`, `rewriter.py`, `hallucination_checker.py`

**Status:** Phase 2 DSPy Deepening in progress. Wiki schema established.

---

## 2026-05-14 — Auto-promoted: Architecture Decision: use SQLite adjacency list i

**Event:** L2 pattern promoted to wiki draft

- Pattern: `Architecture Decision: use SQLite adjacency list i` (confidence: 0.85)
- Draft: `docs/wiki/drafts/architecture-decision-use-sqlite-adjacency-list-i.md`

**Status:** Pending review

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


## 2026-05-08 — Session Summary

**Event:** Auto-saved session

- Skills: git-commit-message, analyze-1c-task-v2, z-ai-delegation, 1c-doc-research, create-hook
- Files changed: 4
- Summary: Session 2026-05-08. Skills: git-commit-message, analyze-1c-task-v2, z-ai-delegation, 1c-doc-research, create-hook, code-verify, implement-1c-task, audit-docs. Changed 4 files in configuration/260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС, configuration/260416_GKSTCPLK-2368 Восстановить предопределенные элементы справочников, external/1c_mcp, ИБTransportManagementDevelop/docs. Commit: chore: auto-save SKILL.md. Commit: chore: auto-save SKILL.md. Commit: chore: auto-save SKILL.md


## 2026-05-09 — Session Summary

**Event:** Auto-saved session

- Skills: tech-research, code-verify, bsl-development, implement-1c-task, create-hook
- Files changed: 7
- Summary: Session 2026-05-09. Skills: tech-research, code-verify, bsl-development, implement-1c-task, create-hook, evaluation-benchmark, learn:pytest-framework. Changed 7 files in .claude/settings.local.json, claude/settings.local.json, configuration/260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС, configuration/260416_GKSTCPLK-2368 Восстановить предопределенные элементы справочников, external/1c_mcp. Commit: chore: auto-save 260430_ROADMAP_DOC_AND_CODE_AUDIT.md. Commit: chore: auto-save 260430_ROADMAP_DOC_AND_CODE_AUDIT.md. Commit: chore: auto-save 260430_ROADMAP_DOC_AND_CODE_AUDIT.md


## 2026-05-10 — Session Summary

**Event:** Auto-saved session

- Skills: bsl-development, learn:1c-metadata-objects, evaluation-benchmark, code-verify, tech-research
- Files changed: 5
- Summary: Session 2026-05-10. Skills: bsl-development, learn:1c-metadata-objects, evaluation-benchmark, code-verify, tech-research. Changed 5 files in configuration/260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС, configuration/260416_GKSTCPLK-2368 Восстановить предопределенные элементы справочников, external/1c_mcp, tools/bsl-debug-server, ИБTransportManagementDevelop/docs. Commit: chore: auto-commit 5 file(s) changed. Commit: chore: auto-commit 5 file(s) changed. Commit: chore: auto-save reference_1c_debug_mcp.md, dbgs-rdbg-debug-server.md, _index.json


## 2026-05-11 — Session Summary

**Event:** Auto-saved session

- Skills: task-protocol, evaluation-benchmark, learning-loop, 1c-mcp-crud, learn:pytest-framework
- Files changed: 5
- Summary: Session 2026-05-11. Skills: task-protocol, evaluation-benchmark, learning-loop, 1c-mcp-crud, learn:pytest-framework, audit-docs, 1c-doc-research, code-verify. Changed 5 files in configuration/260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС, configuration/260416_GKSTCPLK-2368 Восстановить предопределенные элементы справочников, external/1c_mcp, tools/bsl-debug-server, ИБTransportManagementDevelop/docs. Commit: chore: auto-commit 5 file(s) changed. Commit: chore: auto-save reference_1c_debug_hmr_skill.md, 260510_ROADMAP_DEBUG_HMR_INTEGRATION_INTO_1C_PIPELINE.md. Commit: chore: auto-save CLAUDE.md

## 2026-05-12 — Session Summary

**Event:** Auto-saved session

- Skills: code-verify, 1c-debug-hmr, evaluation-benchmark, learn:pytest-framework, implement-1c-task
- Files changed: 5
- Summary: Session 2026-05-12. Skills: code-verify, 1c-debug-hmr, evaluation-benchmark, learn:pytest-framework, implement-1c-task, bsl-development. Changed 5 files in configuration/260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС, configuration/260416_GKSTCPLK-2368 Восстановить предопределенные элементы справочников, external/1c_mcp, ИБTransportManagementDevelop/docs, ИБTransportManagementDevelop/Конфигурация. Commit: chore: auto-save Module.bsl, 260511_LIVE_VERIFICATION_P1_P2_P3_RESULTS.md. Commit: chore: auto-commit 4 file(s) changed. Commit: fix(GKSTCPLK-2292): add task docs and bump Конфигурация submodule

## 2026-05-13 — Session Summary

**Event:** Auto-saved session

- Skills: code-verify, 1c-debug-hmr, evaluation-benchmark, learn:pytest-framework, implement-1c-task
- Files changed: 4
- Summary: Session 2026-05-13. Skills: code-verify, 1c-debug-hmr, evaluation-benchmark, learn:pytest-framework, implement-1c-task, bsl-development, 1c-doc-research, analyze-1c-task-v2. Changed 4 files in configuration/260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС, configuration/260416_GKSTCPLK-2368 Восстановить предопределенные элементы справочников, external/1c_mcp, ИБTransportManagementDevelop/docs. Commit: chore(GKSTCPLK-2483): bump Конфигурация + configuration submodule refs

## 2026-05-14 — Session Summary

**Event:** Auto-saved session

- Skills: bsl-development, architecture-research, tech-research, git-commit-message, learning-loop
- Files changed: 4
- Summary: Session 2026-05-14. Skills: bsl-development, architecture-research, tech-research, git-commit-message, learning-loop, code-verify, auto-git-save, create-hook. Changed 4 files in configuration/260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС, configuration/260416_GKSTCPLK-2368 Восстановить предопределенные элементы справочников, external/1c_mcp, tmp/merge-candidates.jsonl. Commit: fix(hooks): posttooluse-auto-git-save respects pause sentinel + add merge tool. Commit: chore: auto-save feedback_auto_git_save_preempt.md, .kblintrc.yml. Commit: chore(wiki): rename leading-dash entity stem -v8i → v8i (kb-lint --fix)

## 2026-05-14 — Sandbox module (hermes Ф5 partial)

**Event:** New module `src/pdf_framework/sandbox/`

Skeleton for agent code-execution sandbox. Closes 3 of 10 Ф5 tasks
(SandboxBackend ABC, DryRunBackend zero-dep impl, 50-call quota).
LangSmith and E2B backends pending — need API keys + live testing.

- `src/pdf_framework/sandbox/base.py` — `SandboxBackend` ABC (async),
  `SandboxResult` dataclass, `SandboxQuotaExceeded`
- `src/pdf_framework/sandbox/dry_run_backend.py` — fallback for CI /
  no-API-key dev; records calls, returns `[dry-run]` results
- `tests/unit/pdf_framework/sandbox/test_dry_run_backend.py` — 13 tests
- `.claude/skills/sandbox-execution/SKILL.md` — usage guide

Commits: 9b392c465 (skeleton), F3 (skill+log doc).
Spec: openspec/changes/hermes-llm-wiki/tasks.md §Фаза 5.

## 2026-05-15 — Session Summary

**Event:** Auto-saved session

- Skills: bsl-development, architecture-research, tech-research, git-commit-message, learning-loop
- Files changed: 3
- Summary: Session 2026-05-15. Skills: bsl-development, architecture-research, tech-research, git-commit-message, learning-loop, code-verify, auto-git-save, create-hook. Changed 3 files in configuration/260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС, docs/wiki, ИБTransportManagementDevelop/Конфигурация. Commit: chore(wiki): remove test-stale-example.md after archive verification. Commit: chore: auto-save 32.10_Примеры.md. Commit: chore: auto-save 32.10_Примеры.md

## 2026-05-16 — Session Summary

**Event:** Auto-saved session

- Skills: tech-research, create-hook, claude-code-github-actions, code-verify
- Files changed: 0
- Summary: Session 2026-05-16. Skills: tech-research, create-hook, claude-code-github-actions, code-verify. Commit: chore: auto-save task_master.py. Commit: chore: auto-save task_master.py. Commit: chore: auto-save CLAUDE.md

## 2026-05-17 — Session Summary

**Event:** Auto-saved session

- Skills: qdrant-operations, evaluation-benchmark
- Files changed: 6
- Summary: Session 2026-05-17. Skills: qdrant-operations, evaluation-benchmark. Changed 6 files in data/eval, scripts/_eval_common.py, scripts/ground_golden_v1.py, scripts/matryoshka_migrate.py, src/shared. Commit: feat(eval): close §4.1.5 — Matryoshka MIGRATE verdict for framework_code_v1. Commit: chore: auto-commit mcp-server.log.2026-05-10.0.gz, Конфигурация. Commit: fix(ground): Phase 3 review fixes — async retrieval + batch resilience


## 2026-05-18 — Session Summary

**Event:** Auto-saved session

- Skills: qdrant-operations, framework-search, evaluation-benchmark, code-verify
- Files changed: 2
- Summary: Session 2026-05-18. Skills: qdrant-operations, framework-search, evaluation-benchmark, code-verify. Changed 2 files in БTransportManagementDevelop/Конфигурация, ИБTransportManagementDevelop/Конфигурация. Commit: chore(framework-search): cosmetic cleanup from reviewer recommendations. Commit: refactor(framework-search): extract recreate_collection_preserving_alias helper. Commit: docs(31.4 + 03.2): note M1+M2 alias-aware ensure_collection + RAPTOR embedder cache

## 2026-05-19 — Session Summary

**Event:** Auto-saved session

- Skills: tech-research, z-ai-delegation, analyze-1c-task-v2, bsl-development, task-protocol
- Files changed: 2
- Summary: Session 2026-05-19. Skills: tech-research, z-ai-delegation, analyze-1c-task-v2, bsl-development, task-protocol, qdrant-operations, code-verify, indexing-pipeline. Changed 2 files in configuration/260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС, ИБTransportManagementDevelop/Конфигурация. Commit: chore: auto-commit 260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС, Конфигурация, mcp-server.log.2026-05-18.0.gz +1 more. Commit: chore: auto-save probe_phase12_vram.py. Commit: chore: auto-save smoke_test_phase3_grouping.py

## 2026-05-20 — Session Summary

**Event:** Auto-saved session

- Skills: indexing-pipeline, qdrant-operations, learn:pytest-framework, learning-loop, evaluation-benchmark
- Files changed: 2
- Summary: Session 2026-05-20. Skills: indexing-pipeline, qdrant-operations, learn:pytest-framework, learning-loop, evaluation-benchmark, code-verify, git-commit-message, claude-api. Changed 2 files in configuration/260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС, ИБTransportManagementDevelop/Конфигурация. Commit: chore: auto-save generate_bsl_golden_set.py. Commit: chore: auto-save generate_bsl_golden_set.py. Commit: chore: auto-save IMPLEMENTATION-PROGRESS.md, test_bsl_retrieval_quality.py

## 2026-05-21 — Session Summary

**Event:** Auto-saved session

- Skills: code-verify, git-commit-message
- Files changed: 2
- Summary: Session 2026-05-21. Skills: code-verify, git-commit-message. Changed 2 files in БTransportManagementDevelop/Конфигурация, ИБTransportManagementDevelop/Конфигурация. Commit: chore(GKSTCPLK-2507): bump docs submodule — раздел Git commits в PROGRESS. Commit: chore(GKSTCPLK-2507): bump Конфигурация submodule — fix runtime error в форме АРМ. Commit: chore(GKSTCPLK-2507): bump Конфигурация submodule — UI вкладка АРМ
