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
