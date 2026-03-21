# CLAUDE.md — PDF Vector & Graph Framework

## Project Overview

Framework for PDF document processing: semantic search (RAG), knowledge graphs, hybrid retrieval. Production-ready with REST API, CLI, MCP server, Streamlit UI.

## Tech Stack

- **Python 3.11+**, async-first
- **LangChain / LangGraph** — agents, tools, chains, orchestration
- **Qdrant / ChromaDB / FAISS** — vector stores
- **Neo4j / NetworkX** — graph stores
- **FastAPI** — REST API
- **MCP** — Model Context Protocol server
- **Typer** — CLI

## Project Structure

```
src/
  pdf_framework/        # Core library
    loaders/            # PDF loading (pymupdf, pdfplumber)
    processing/         # Splitting, cleaning, metadata
    embeddings/         # Embedding providers
    vector_store/       # Vector DB (base + providers)
    graph_store/        # Graph DB (base + providers)
    search/             # Hybrid search, strategies, reranking
    agents/             # LangGraph agents (RAG, analytical, research)
    indexing/           # Indexing pipelines, hybrid loader
    tools/              # LangChain tools
    chains/             # LangChain chains
    schemas/            # Pydantic data models
    config/             # Settings modules
    evaluation/         # RAGAS, benchmarks
    guardrails/         # Input/output validation
    observability/      # Logging, tracing
    analytics/          # Cost tracking, audits
    feedback/           # User feedback
    multitenancy/       # Multi-tenant support
    optimization/       # Performance tuning
    knowledge_base/     # Knowledge base management
    callbacks/          # Event callbacks
    utils/              # Utilities
  api/                  # REST API (FastAPI)
  cli/                  # CLI (Typer)
  mcp_server/           # MCP server for Claude Code
  ui/                   # Streamlit web UI
  workers/              # Background task workers
```

## Development Rules

- Store implementations extend abstract base classes in `*/base.py`
- Pydantic models from `schemas/` as data contracts
- Async-first: all I/O operations are `async`
- Configuration via `pydantic-settings` (`.env` file)
- Provider pattern: swap Vector/Graph/Embedding providers without changing logic

## Task Protocol (MANDATORY)

Every task: classify → (decompose) → **Skill() check** → execute → verify.
Enforcement: `task-protocol-enforcer` blocks Write/Edit until `Skill()` is called.
Full algorithm: `Skill('task-protocol')`.

- **ALL tasks** (including trivial) require `Skill()` before Write/Edit
- **trivial** (< 1 file, < 30 words): Skill() → Write/Edit
- **medium** (1-3 files): TaskCreate → Skill() → Write/Edit
- **complex** (4+ files): TaskCreate (full decomposition) → Skill() → Write/Edit
- Phase machine: `idle → classified → [decomposed] → skill_checked → ALLOW Write/Edit`
- Exempt: `.claude/`, `docs/`, `data/`, config files (.json, .toml, .yml, .env)

## Token Economy: Z.AI Delegation Protocol (MANDATORY — NEVER SKIP)

**RULE: Before generating ANY content > 15 lines, ALWAYS ask: "Can Z.AI generate this?"**
**If YES → MUST delegate. If NO → explain why (architecture/security/debug only).**
**Violation: generating 50+ lines of docs/tests/boilerplate yourself = wasted Opus tokens.**

Minimize Opus token usage by delegating content generation to Z.AI via LLM Rotation.

### Delegation Levels
- **Soft** (no review): bulk ops (10+ items), translations, formatting
- **Medium** (Opus review mandatory): docs, decomposition, tests, boilerplate, checklists, templates
- **Hard** (Opus thorough review mandatory): code writing, refactoring, analysis
- **Never delegate**: architecture decisions, security, debugging, tasks < 30 lines output

### Orchestrator Mode (MUST use for 3+ output files)
1. **DECOMPOSE** — Opus разбивает задачу на подзадачи, классифицирует каждую (Soft/Medium/Hard/Never)
2. **PREPARE** — Opus строит промпт для каждой делегируемой подзадачи (задача+контекст+формат+ограничения)
3. **DELEGATE** — `mcp__llm-rotation__llm_complete()` для каждой подзадачи (параллельно если независимы)
4. **REVIEW** — Opus ревьюит каждый результат (Medium: accuracy; Hard: +logic+security)
5. **ASSEMBLE** — Opus собирает финальный результат, Write() файлы
6. **FALLBACK** — Если Z.AI недоступен (all providers failed) → Opus пишет сам, НЕ останавливается

### Single Task Mode (1-2 files, output > 15 lines)
1. Classify -> delegation level
2. `mcp__llm-rotation__llm_complete(prompt=..., max_tokens=4096)`
3. Review (Medium/Hard) -> fix inline
4. Write final result

If >50% rewrite needed -> reclassify as Never, do it yourself.

### Mandatory Opus Review (ALWAYS — NEVER SKIP)
After writing ANY code (.py, .js, .ts, .bsl, etc.) — self-review is MANDATORY:
- **Code (any complexity)**: re-read written code, check logic, edge cases, naming
- **Hard tasks**: thorough review — logic + security + patterns + edge cases + error handling
- **After Z.AI draft**: verify names, imports, API calls exist (Z.AI hallucinates project details)
- Format: brief inline review after Write/Edit, before moving to next task
- **NEVER skip** even for "trivial" code changes — bugs hide in small fixes
- Hook `code-review-enforcer.py` fires on every Write|Edit of code files

### Self-Check Questions (ask before EVERY generative task)
1. Output > 15 lines? → MUST delegate to Z.AI
2. 3+ output files? → MUST use Orchestrator Mode
3. Code file changed? → MUST self-review (THOROUGH if src/tools/infra/scripts)
4. Z.AI down? → Opus writes, but note "Z.AI unavailable, writing directly"

Full protocol: `Skill('z-ai-delegation')`. Hooks: `z-ai-delegation-enforcer.py` (UserPromptSubmit), `z-ai-write-guard.py` (PreToolUse:Write — blocks >15 lines without llm_complete), `code-review-enforcer.py` (PreToolUse Write|Edit).

## Output Rules

- File references in responses must be clickable markdown: `[file.py](.claude/hooks/file.py)` or `[file.py:42](.claude/hooks/file.py#L42)`

## Триада: Hook + Skill + MCP

Каждое решение, принятое в разговоре, должно стать артефактом. Иначе — потеряно.

- **Hook** (.py) — автоматизация на событие (`.claude/hooks/`)
- **Skill** (.md) — процедурное знание (`.claude/skills/`)
- **MCP Tool** — внешний инструмент (`src/mcp_server/`)
- **Cache** — накопленные знания (`skills/<domain>/cache/`)

Создание компонентов: skill `triad-factory` (алгоритм) + `create-hook` (хуки) + `doc-to-skill` (скиллы).

### Hooks Infrastructure

```
.claude/hooks/
  base/protocol.py          # BaseHook — abstract base, stdin/stdout JSON, auto-logging (USE THIS)
  base/base.py              # Alt dataclass-based HookInput with auto-detect event
  shared/
    invocation_logger.py    # JSONL logger (data/hook-invocations.jsonl)
    session_state.py        # Session: activated/recommended skills dedup, prompt_id, pending_learn, task_protocol, llm_delegation
    ralph_state.py          # Ralph Wiggum state management
    otel_exporter.py        # OpenTelemetry OTLP exporter
    task_master.py          # Task management from hooks (session_start_cleanup: git + code-verify)
    code-skill-patterns.json # Pattern->Skill mappings (7 sections, 43 rules)
    trust_scorer.py         # Trust scoring for sources (Context7/GitHub/SO/Infostart)
  skill-router.py           # UserPromptSubmit: skill recommendations
  skill-eval-enforcer-shell.py  # UserPromptSubmit: task protocol + activation enforcement
  task-protocol-observer.py # PreToolUse:Skill|TaskCreate|llm_complete: records decomposition, skill activation, Z.AI delegation (migrated from PostToolUse)
  task-protocol-enforcer.py # PreToolUse:Write|Edit: blocks if protocol phase is idle
  code-skill-enforcer.py    # PreToolUse:Write|Edit|Bash: skill-first enforcement (6 levels A-F + A.1 research_protocol, protocol.py base)
  code-verify-reminder.py   # PreToolUse:Write|Edit: mandatory code verification task creation (migrated from PostToolUse)
  code-review-enforcer.py   # PreToolUse:Write|Edit: mandatory code review reminder (migrated from PostToolUse)
  docs-change-tracker.py    # PreToolUse:Write|Edit: maps code changes to docs (migrated from PostToolUse)
  factory-enforcer.py       # PreToolUse:Write: factory steps enforcement for .claude/ files (migrated from PostToolUse)
  bulk-action-guard.py      # PreToolUse:Bash: detects destructive commands BEFORE execution (migrated from PostToolUse, now proactive)
  skill-usage-metrics.py    # PreToolUse:Skill: logs skill invocations (migrated from PostToolUse)
  auto-git-save.py          # Stop: auto-commit on threshold
  auto-git-save-prompt.py   # UserPromptSubmit: commit reminders
  git-commit-enforcer.py    # Stop: uncommitted changes check
  docs-change-enforcer.py   # Stop: documentation coverage check (skips infra/, tools/, docker/, *.log, src/projects/, src/bsl/). Cooldown: blocks once, then allows for 30 min (prevents infinite loop)
  task-enforcer.py          # Stop: task list completion check (v2.2: auto-clean stale code-verify tasks)
  ralph_wiggum_stop.py      # Stop: Ralph iteration enforcement
  memory-sync.py            # Stop: memory system change advisory
  z-ai-write-guard.py      # PreToolUse:Write: blocks >15 lines code without Z.AI delegation
  delegation-outcome-tracker.py # PreToolUse:Write: records Write >15 lines to delegation-outcomes.jsonl
  delegation-outcome-stop.py # Stop: appends session delegation summary to JSONL
  skill-quality-monitor.py  # UserPromptSubmit: passive quality metrics logging (data/skill-quality-metrics.jsonl)
  bsl-tool-router.py        # UserPromptSubmit: routes BSL/1C queries to bsl-development skill
```

AutoResearch: `scripts/skill-health-analyzer.py` (health report) + `scripts/audit-skill-freshness.py` (freshness audit) + `scripts/autoresearch.ps1` (autonomous cycle). Templates: `ralph.bat --template skill-health|quality|1c-study|autoresearch`. Archive: `.claude/skills/_archived/`. Docs: [Chapter 18 (v1)](docs/framework%20documentation/18_AUTORESEARCH/), [Chapter 20 (v2)](docs/framework%20documentation/20_AUTORESEARCH_V2/). AutoResearch v2: three-agent engine (Executor+Reviewer+Comparator), `autoresearch.sh` (bash), eval: `scripts/eval-autoresearch.py`, dashboard: `scripts/autoresearch-dashboard.py`.
Evaluation: `scripts/eval-hooks.py` + `tests/eval/hook_prompts.json` (40 тестов, 16 скиллов).
Skill Router Eval: `scripts/eval-skill-router.py` (64 ground truth, F1/precision/recall) + `scripts/skill-router-dashboard.py` (CLI dashboard) + CI gate в `.github/workflows/ci.yml`.
Dashboard: `scripts/hook-dashboard.py` (CLI) + `scripts/skill-enforcement-dashboard.py` (enforcement) + `src/ui/pages/hook_dashboard.py` (Streamlit).
Monitoring: `src/pdf_framework/observability/hook_metrics_db.py` (SQLite) + `tracer.py` (OTLP) + `/metrics/html` (unified dashboard).
Migration: `scripts/skill-migration-advisor.py` (pattern coverage analysis).

## BSL Development (1C Enterprise)

- **BSL код**: `src/bsl/` (semantic_search, mcp_server, mcp_integration, sonar, finetuning)
- **Инструменты**: `tools/auto-documenter/` (Node.js), `tools/bsl-debugger/` (Node.js), `tools/ast-grep-mcp/`, `tools/bsl-semantic-diff/`
- **MCP серверы**: bsl-semantic-search, bsl-platform-context, auto-documenter, bsl-debugger, ast-grep-mcp, bsl-semantic-diff
- **Memory**: `src/memory/` (ai_memory, vector_memory, skill_learning, orchestrator)
- **LLM Rotation**: `src/shared/llm_rotation/` (5 провайдеров, fallback)
- **Профили**: `.mcp/pdf.json`, `.mcp/bsl.json`, `.mcp/full.json`, `.mcp/lazy-mcp.json`
- **Lazy MCP**: `infra/lazy-mcp/` (proxy, 11 категорий, 27 on-demand серверов)
- **Qdrant коллекции**: `bsl_code_v2` (768d nomic), `ai_memory` (768d), `learned_patterns` (768d)
- **BSL hook**: `bsl-tool-router.py` — routes BSL/1C queries to bsl-development skill

## Research

При вопросах про 1С: документация 8.3.27 — первоисточник. Внешние источники (its.1c.ru, infostart.ru) — только дополнение. Каждый факт с атрибуцией. Протокол: skill `1c-doc-research`.

При вопросах про RAG/ML/Python: протокол в skill `tech-research`.

## Ralph Wiggum — Autonomous Loop

При работе в автономном цикле (`scripts/ralph.bat` / `ralph.sh`):

- В начале итерации: `git log --oneline -5` + `git diff --stat`
- Коммиты с префиксом `[RALPH]`, по одному на логическое изменение
- После 3 неудачных попыток — объяснить почему, не зацикливаться
- Маркер завершения: `RALPH_DONE` (только когда ВСЕ критерии выполнены)
- Stop Hook блокирует преждевременную остановку
- Не изменять файлы вне scope, не удалять `data/` без инструкции
- Шаблоны: `--template reindex|test-coverage|evaluation|documentation|lint`
