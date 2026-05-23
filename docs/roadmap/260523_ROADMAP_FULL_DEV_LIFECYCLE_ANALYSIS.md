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

### Stage 0 — Session bootstrap (`SessionStart` event, 5 hooks)

Перед первым промптом фреймворк готовит environment:

| # | Hook | Purpose | State touched |
|---|---|---|---|
| 1 | `ensure-docker-qdrant.py` | Запустить Qdrant Docker если не running | docker ps |
| 2 | `logging-status-banner.py` | Показать MCP logging status | systemMessage |
| 3 | `submodule-status-check.py` | Verify git submodule sync | hook output |
| 4 | `session-mypy-banner.py` | Show mypy baseline compliance | `mypy-baseline.txt` |
| 5 | `audit-coverage-check.py` | Verify hook audit coverage % | systemMessage |

**Stage exit:** Claude получает initial systemMessages, инфраструктура готова.

### Stage 1 — User prompt arrives (`UserPromptSubmit`, 14 hooks)

User набирает сообщение, нажимает Enter. 14 хуков запускаются в порядке регистрации в `settings.json`:

| Order | Hook | Critical role |
|---|---|---|
| 1 | `memory-first-hook.py` | **4-layer federated recall** — top-K context injection (см. §7) |
| 2 | `session-context-enforcer.py` | Enforce active task constraints |
| 3 | `skill-router.py` | **Skill routing** через 4-layer matching (phrase/fuzzy/TF-IDF/semantic) — см. §6.1 |
| 4 | `skill-eval-enforcer-shell.py` | **Auto-classification** trivial/medium/complex + block invalid skills |
| 5 | `ralph_activator.py` | Активация Ralph Wiggum autonomous loop если detect signal |
| 6 | `decision-to-triad.py` | Convert decisions → triad artifacts |
| 7 | `document-persistence.py` | Save plans/roadmaps to session state |
| 8 | `todo-sync.py` | Sync hook-todos.json ↔ TodoWrite |
| 9 | `auto-git-save-prompt.py` | **Workaround #6305** — async git commit (см. §8.1) |
| 10 | `z-ai-delegation-enforcer.py` | **Token economy** — classify Soft/Medium/Hard/Never (см. §7.2) |
| 11 | `skill-quality-monitor.py` | RAGAS metrics check before routing |
| 12 | `slash-command-tracker.py` | Detect `/cmd`, dedup |
| 13 | `implement-1c-task-preflight.py` | Pre-validate 1С task structure |
| 14 | `analyze-1c-task-preflight.py` | Pre-validate 1С analysis task |

**Stage exit:** Claude получил obогащённый prompt (memory context + skill recommendations + delegation hint + task classification).

**State touched:** `.claude/cache/session-skills.json`, `memory-first-cooldown.json`, `data/skill-router.log`, `data/skill-accuracy.jsonl`

### Stage 2 — Skill activation (`Skill()` tool call)

Claude видит `[SKILL-ROUTER] ACTIVATE SKILLS [HIGH]: Skill('xyz')` → вызывает `Skill('xyz')`. Это:

1. Загружает skill SKILL.md в context (knowledge injection)
2. PostToolUse:Skill хуки фиксируют activation:
   - `posttooluse-skill-metrics.py` → metrics
   - `code-verify-reminder.py` → schedule verify if code change pending
3. PreToolUse:Skill хуки enforce:
   - `approval-gate.py` → require pre-approval from SKILL.yaml
   - `task-protocol-observer.py` → mark phase=`skill_checked`
   - `skill-usage-metrics.py` → frequency/latency/error rate

**Phase transition:** `idle/classified` → `skill_checked` (unblocks Write/Edit).

### Stage 3 — Tool execution (Write/Edit/Bash/Read/Grep/MCP)

Claude вызывает любой tool. PreToolUse hooks по matcher:

| Matcher | Guards | Purpose |
|---|---|---|
| `Read\|Grep\|Glob` | bsl-tool-router.py | Route BSL searches |
| `Write\|Edit` | task-protocol-enforcer, code-review-enforcer, code-verify-reminder, docs-change-tracker, root-clutter-guard, z-ai-write-guard, factory-enforcer, delegation-outcome-tracker | **Blocking layer** — phase check, skill check, root path check, delegation gating |
| `Write\|Edit\|Bash` | code-skill-enforcer | Sequence enforcement (Code → Review → Verify) |
| `Bash` | search-optimizer, bulk-action-guard | Optimize queries, warn on bulk ops |
| `Skill` | approval-gate, task-protocol-observer, skill-usage-metrics | Approval + state recording |
| `TaskCreate` | task-protocol-observer | Mark phase=`decomposed` |
| `mcp__.*` | mcp-invocation-logger | Audit all MCP calls |
| `mcp__llm-rotation__llm_complete` | task-protocol-observer | Mark delegation event |

**If blocked (exit 2):** tool call cancelled, Claude видит блокировку в output, корректирует подход.

### Stage 4 — PostToolUse (cleanup + tracking, 18 hooks across 6 matchers)

⚠️ **Windows bug #6305:** PostToolUse hooks ненадёжны на Windows. Fallback patterns documented в §5.

| Matcher | Hooks | Role |
|---|---|---|
| `TaskUpdate` | **post-task-push-pr** (timeout 1320s) | **PR automation P0-P3** — branch+push+PR+merge (см. §8.2) |
| `Skill` | posttooluse-skill-metrics, code-verify-reminder | Metrics + schedule verify |
| `Task` | code-verify-reminder | Check if Task closed verify task |
| `WebSearch\|WebFetch` | posttooluse-web-cache, knowledge-cache-reminder | Cache web results |
| `Write\|Edit` | posttooluse-docs-tracker, posttooluse-quality-feedback, **posttooluse-auto-git-save**, code-verify-reminder, openspec-change-coverage | **Auto-git-save sync commit** + docs tracking + OpenSpec coverage |
| `mcp__llm-rotation__llm_complete` | posttooluse-delegation-tracker | Delegation outcome corpus |
| `Bash` | posttooluse-bash-errors | Parse errors → suggest fixes |

**Stage exit:** State persisted, tasks scheduled, metrics logged.
