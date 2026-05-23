# Roadmap 260523 — Full Dev Lifecycle Analysis

**Дата создания:** 2026-05-23
**Тип:** Analytical roadmap (snapshot of framework patterns and lifecycle)
**Scope:** End-to-end dev lifecycle от user prompt до cleanup post-merge
**Источники:** 73 hooks, 24 shared modules, 12 cache state files, 98+ skills, 45 memory entries, 70+ CODE_TO_DOMAIN mappings

---

## §0 TL;DR

Фреймворк PDF Vector & Graph реализует **end-to-end automated dev lifecycle** через 3-уровневую hook-архитектуру (UserPromptSubmit / PreToolUse + PostToolUse / Stop), enforced **Task Protocol** (idle→classified→skill_checked→ALLOW), **4-layer Memory injection** (SQLite + Qdrant TEI Qwen3 + .md + wiki stub), **token-economy delegation** (Z.AI/Gemini via LinUCB bandit) и **PR-automation P0-P3 batch** (label-driven, cherry-pick, merge-queue).

**Сильные стороны:** defense-in-depth (критичные проверки на 3 уровнях), graceful degradation (хуки не блокируют exit), observability (`data/hook-invocations.jsonl` audit log + Langfuse spans).

**Слабые места:** Windows-bug #6305 (PostToolUse unreliable) → требует UserPromptSubmit/Stop fallback patterns; bug #10450 (Windows stdin empty); Cyrillic path encoding (mitigated через `encoding="utf-8"`); большой surface area (73 hooks) с риском cascading regression (см. недавний PR #2 -X theirs merge → 4 silent hook breakages).

**Цель этого документа:** zero-prior-knowledge reader должен понять как промпт пользователя проходит через ~15 стадий до cleanup, какие паттерны на каждой стадии срабатывают, где state хранится, и где failure modes.

---

## §1 Scope

**Включено в анализ:**
- Hook lifecycle: SessionStart → UserPromptSubmit → PreToolUse → tool execution → PostToolUse → Stop
- Skills system: skill-router 4-layer matching + Task Protocol phase machine + code-verify 3-level/4-mode
- Memory & Context: P5.2 Federated Recall (4 layers), Qdrant TEI Qwen3-Embedding-8B
- Delegation: Z.AI/LLM Rotation, LinUCB bandit, TrainedRouter canary, outcome corpus
- Git/CI: auto-git-save 3-layer redundancy, docs-change-enforcer, factory-enforcer
- PR automation: post-task-push-pr P0-P3 batch (18 features), cherry-pick worktree, merge-queue
- Observability: hook-invocations.jsonl, Langfuse spans, RAGAS skill accuracy

**НЕ включено:**
- 1С-specific pipelines (`/analyze-1c-task`, `/implement-1c-task`, VA BDD tests) — отдельный документ
- BSL indexing, semantic search backend, embeddings details — chapter 31 Qwen3
- OpenSpec workflow — chapter 24
- Sandbox execution — Ф5 hermes-llm-wiki

---

## §2 Full Lifecycle Map (Stage-by-Stage)

Каждая стадия от user prompt до cleanup. На каждой стадии: trigger, что происходит, какие хуки/паттерны срабатывают, какие state-файлы touched.
