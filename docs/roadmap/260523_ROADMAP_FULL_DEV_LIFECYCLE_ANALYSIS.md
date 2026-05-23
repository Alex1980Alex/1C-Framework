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

### Stage 5 — Tool result → Claude continues OR stops

Claude интерпретирует tool result, продолжает работу (loop Stage 3-4) ИЛИ завершает ответ. Если завершает → Stage 6.

### Stage 6 — Stop event (14 hooks, last-mile validation)

Перед exit Claude триггерит Stop. 14 хуков выполняются **последовательно** в порядке:

| Order | Hook | Blocks? | Purpose |
|---|---|---|---|
| 1 | `ralph_wiggum_stop.py` | Да | Контроль autonomous loop iteration |
| 2 | `slash-command-tracker.py` | Нет | Finalize slash-command metrics |
| 3 | `implement-1c-task-smoke-stop-alert.py` | Нет | Alert if 1C task incomplete |
| 4 | `post-indexing-analyzer.py` | Нет | Auto-report после indexing run |
| 5 | `opsx-apply-postvalidate.py` | Нет | OpenSpec apply post-validation reminder |
| 6 | `openspec-task-progress.py` | Нет | Update OpenSpec progress |
| 7 | `git-commit-enforcer.py` | **Да (exit 2)** | Uncommitted changes? Block stop |
| 8 | `docs-change-enforcer.py` | **Да (exit 2)** | Code changed без docs? Block (см. §8.3) |
| 9 | `code-verify-reminder.py` (fallback) | Нет | **Stop fallback** для PostToolUse #6305 — закрыть verify task если transcript содержит `[CODE-VERIFY-PASS]` |
| 10 | `task-enforcer.py` | **Да (exit 2)** | Mandatory hook tasks pending? Block + hint |
| 11 | `memory-sync.py` | Нет | Persist session memory → cache |
| 12 | `session-memory-save.py` | Нет | **Save session → SQLite** + L5 wiki promote |
| 13 | `auto-git-save.py` | Нет | Final git push if pending |
| 14 | `delegation-outcome-stop.py` | Нет | Delegation cost summary |

**Blocking gates (если любой exit 2):** Claude получает feedback, retry Stop.

### Stage 7 — Auto-git-save (если threshold reached)

3-layer redundancy для #6305 mitigation:

- **Layer 1 PostToolUse:** `auto-git-save.py` matcher Write|Edit|Bash → sync commit при threshold (default 1 file)
- **Layer 2 PostToolUse:** `posttooluse-auto-git-save.py` — debounced 5s fallback
- **Layer 3 UserPromptSubmit:** `auto-git-save-prompt.py` — fires at NEXT prompt если PostToolUse не сработал
- **Layer 4 Stop:** `auto-git-save.py` (Stop entry) — final push

**Commit message format:** `chore: auto-save a.py, b.py, c.py +N more` (DRY helper `shared/auto_save_core.py`)

### Stage 8 — PR automation (если AUTO_PR_ENABLED + TaskUpdate completed)

`post-task-push-pr.py` оркестрирует P0-P3 batch (см. §8.2). 11-stage pipeline:

1. P2.1 (in_progress): record start_sha
2. P0.1 label gating  
3. P2.1 scope check (`AUTO_PR_MIN_COMMITS`)
4. P0.4 pre-push pre-commit run
5. P1.3 stale base check + auto-rebase
6. P3.2 cherry-pick branch model
7. P0.2 push
8. P0.3 idempotency (reuse existing PR)
9. P2.3 reviewers via CODEOWNERS
10. P2.5 blockedBy labels
11. P1.2 wait-for-checks + merge (squash / merge-queue)

### Stage 9 — Post-merge

`scripts/pr_check_post_merge.py` (P3.4, oncall) — polls merged PR's CI:
- Если post-merge CI fail → auto-revert commit + reopen PR с failure context

### Stage 10 — Cleanup + next cycle

После merge:
- `gh pr merge --delete-branch` удаляет head branch
- session-memory-save L5 promote sees prior session patterns → adjusts future memory injection
- При следующем session start (Stage 0) circle closes

---

## §3 Pattern Catalog (cross-reference)

Все паттерны реализованные во фреймворке, сгруппированные по категориям. Каждый имеет ссылку на implementation.

### 3.1 Hook patterns

| Pattern | Файл | Назначение |
|---|---|---|
| **3-Level Hook Architecture** | UPS/PostToolUse/Stop | Defense-in-depth — критичное дублируется на 3 уровнях |
| **Enforcer (Stop, blocking)** | task-enforcer, docs-change-enforcer, git-commit-enforcer | exit 2 блокирует Stop пока условие не выполнено |
| **Reminder (PostToolUse, non-blocking)** | code-verify-reminder, knowledge-cache-reminder | Создаёт mandatory task, не блокирует |
| **Guard (PreToolUse, blocking)** | root-clutter-guard, bulk-action-guard, z-ai-write-guard | Cancel tool call перед execution |
| **Router (UPS, advisory)** | skill-router, bsl-tool-router, decision-to-triad | Inject context/hints в systemMessage или stdout |
| **Observer (PostToolUse, recording)** | task-protocol-observer, mcp-invocation-logger | Just records, никогда не блокирует |
| **Workaround #6305 (UPS fallback)** | auto-git-save-prompt | Fires на следующем prompt если PostToolUse не сработал |
| **Stop fallback (transcript scan)** | code-verify-reminder Stop entry | Читает transcript JSONL, scans markers |
| **Canary log** | auto-git-save-prompt-canary.log | Diagnose hook invocation independently of logic |
| **Cooldown** | memory-first-hook (30s), docs-enforcer (30m), auto-git-save (adaptive 2-6m) | Prevent spam/loop |

### 3.2 Skills system patterns

| Pattern | Файл | Назначение |
|---|---|---|
| **4-Layer skill matching** | skill-router.py | Phrase (exact) → Fuzzy (typo) → TF-IDF (semantic) → Qdrant fallback |
| **Bundle classification** | skill-router-config.json | 50+ domain groups (research-1c, bsl-dev, langchain-core) |
| **Affinity injection** | skill-router-config.json | Cross-bundle deps (langchain-streaming → langgraph-core) |
| **Workflow detection** | skill-router.py | research/brainstorm/hybrid mode hints |
| **Min-score threshold** | skill-router-config.json | 2 base, 6 для informational intent (precision lever) |
| **Session dedup** | SessionState.get_already_recommended() | Avoid re-showing same skills |
| **Task Protocol phase machine** | task_master.py + protocol-enforcer + observer | idle→classified→decomposed→skill_checked→ALLOW |
| **Auto-classification** | skill-eval-enforcer-shell.py | trivial/medium/complex по word count + multi-file markers |
| **Code-verify 3-Level** | code-verify SKILL.md | Structural → Subagent → Decision |
| **Code-verify 4-Mode** | code-verify SKILL.md | knowledge-compliance / behavior-preservation / bug-fix-validation / quality-review |
| **PASS/FAIL marker** | code-verify subagent | `[CODE-VERIFY-PASS]` / `[CODE-VERIFY-FAIL]` regex closure |
| **Ralph Wiggum Loop** | code-verify FAIL handler | Max 3 iterations, then escalate manual |

### 3.3 Memory patterns

| Pattern | Файл | Назначение |
|---|---|---|
| **4-Layer Federated Recall** | memory-first-hook.py | SQLite (200ms) + Qdrant TEI (2s) + .md (500ms) + wiki (stub) |
| **RRF merge** | memory-first-hook.py | Reciprocal Rank Fusion по content hash, top-K injection |
| **Russian stemming** | memory-first-hook.py:75-127 | 29 suffixes for Cyrillic morphology |
| **TEI Qwen3-Embedding-8B** | Phase 9.1 alignment | 4096d embeddings, 3 collections (skill_library, experience, conversation) |
| **Token overlap fallback** | memory-first-hook.py | If TEI unavailable → query learned_patterns |
| **MEMORY.md index** | ~/.claude/projects/.../MEMORY.md | 45 entries, one-line pointers to detail files |
| **Frontmatter parsing** | memory-first-hook.py:130-157 | YAML frontmatter (name, description, type, body) |
| **L5 wiki promote** | session-memory-save.py + scripts/export_graph_to_wiki | Promote patterns after session save |
| **NTFS recovery awareness** | MEMORY.md note | Original 18 entries lost 2026-04-26, recovered via index pointers |

### 3.4 Delegation patterns

| Pattern | Файл | Назначение |
|---|---|---|
| **Classification (Soft/Medium/Hard/Never)** | z-ai-delegation skill | Per-task delegation decision |
| **Orchestrator mode** | z-ai-delegation skill | 3+ files → decompose+delegate+review+assemble |
| **LinUCB bandit** | z-ai-delegation-enforcer.py | Exploit best-known provider |
| **TrainedRouter (similarity)** | DELEGATION_ROUTER_CANARY_PCT env | Cosine vs exemplars (A/B canary) |
| **Outcome corpus** | data/delegation-outcomes.jsonl | Online bandit update |
| **Langfuse span** | delegation.routing.decision | Observability foundation |
| **Mandatory Opus review** | z-ai-delegation skill | Hard tasks: thorough review (security, edge cases, perf) |
| **Provider fallback** | src/shared/llm_rotation/ | 5 providers (Z.AI GLM-5, Gemini, OpenRouter, Ollama, Anthropic) |

### 3.5 Git/PR patterns

| Pattern | Файл | Назначение |
|---|---|---|
| **3-layer auto-git-save** | auto-git-save (PostToolUse) + posttooluse-auto-git-save + auto-git-save-prompt (UPS) | #6305 mitigation |
| **Threshold-based commit** | auto-git-save.py | N file changes → commit (default 1) |
| **Pause sentinel** | .claude/cache/auto-git-save.paused | TTL/forever skip mechanism |
| **Settings guard** | auto-git-save.py | Block if settings.json shrinks >30 lines (regression detect) |
| **Adaptive cooldown** | auto-git-save.py | 2-6m base, -1m per file (prevent rapid recreation) |
| **PR-automation P0-P3** | post-task-push-pr.py | Label gating + scope check + cherry-pick + merge-queue |
| **Cherry-pick worktree** | shared/pr_helpers.py:cherry_pick_range_to_branch | Temp worktree, abort cleanup в finally |
| **CODEOWNERS reviewer assignment** | shared/pr_helpers.py:codeowners_for_paths | Auto-assign reviewers |
| **Blocked-by labels** | post-task-push-pr.py | Cross-PR deps via labels |
| **Merge-queue alternative** | gh pr merge --merge-queue | Free Mergify replacement |
| **Post-merge auto-revert** | scripts/pr_check_post_merge.py | If CI fail post-merge → revert commit + reopen |
| **Force-with-lease** | git push --force-with-lease=ref:sha | Race condition protection |
| **Archive ref preservation** | archive/master-pre-reconciliation-2026-05-19 | Safety net перед force-push |
| **Per-task SHA tracking** | .claude/cache/post-task-push-pr-state.json | Scope = task's own commits, не full branch |
| **Pre-push pre-commit gate** | post-task-push-pr.py | Run pre-commit run --all-files перед push |

### 3.6 Observability patterns

| Pattern | Файл | Назначение |
|---|---|---|
| **Universal MCP audit** | mcp-invocation-logger.py | regex `mcp__.*` ловит все MCP calls |
| **Hook invocations JSONL** | data/hook-invocations.jsonl | Full audit trail (ts, hook, event, tool, elapsed, outcome) |
| **Slash-command run tracking** | slash-command-tracker.py | UUID run_id, correlate Pre/Post tool calls |
| **Langfuse spans** | memory-first / delegation / wiki promote | Distributed tracing |
| **Skill accuracy correlation** | data/skill-accuracy.jsonl | recommend→activate corr (RAGAS-like) |
| **Circuit breaker** | shared/circuit_breaker.py | OPEN/CLOSED/HALF_OPEN state per hook |
| **Auto-reports** | scripts/analyze_run.py + post-indexing-analyzer.py | Deep reports после indexing + graph runs |

---

## §4 Hook Chain Matrix

73 hooks по событиям с timeout и matcher. Полный inventory — см. research данные в session log + skill `multi-level-hook-architecture` SKILL.md (~/.claude/skills/multi-level-hook-architecture/SKILL.md).

| Event | Count | Critical hooks |
|---|---|---|
| SessionStart | 5 | ensure-docker-qdrant, submodule-status, session-mypy-banner |
| UserPromptSubmit | 14 | **memory-first-hook, skill-router, skill-eval-enforcer, auto-git-save-prompt** |
| UserPromptExpansion | 1 | slash-command-tracker (forward-compat fallback) |
| PreToolUse | 21 (7 matchers) | task-protocol-enforcer, code-skill-enforcer, root-clutter-guard, mcp-invocation-logger |
| PostToolUse | 18 (6 matchers) | **post-task-push-pr (TaskUpdate, 1320s timeout!), auto-git-save, code-verify-reminder** |
| Stop | 14 | **git-commit-enforcer, docs-change-enforcer, task-enforcer, session-memory-save** |
| **Total** | **73** | — |

**Notable timeouts:**
- `post-task-push-pr.py` — 1320s (22 минуты, нужен для wait-for-checks в PR-automation)
- `auto-git-save.py` — 30s
- Большинство — 3-5s

---

## §5 3-Level Hook Architecture (deep dive)

### 5.1 Зачем 3 уровня

Bug #6305 (PostToolUse ненадёжен на Windows) forced defense-in-depth pattern. Each critical concern duplicated на 2-3 уровнях:

| Concern | Level 1 (UPS) | Level 2 (PostToolUse) | Level 3 (Stop) |
|---|---|---|---|
| **Auto-commit** | auto-git-save-prompt | auto-git-save + posttooluse-auto-git-save | auto-git-save (Stop entry) |
| **Skill metrics** | skill-router `_detect_skill_activations` | posttooluse-skill-metrics | — |
| **Docs update** | — | docs-change-tracker (creates task) | docs-change-enforcer (blocks Stop) |
| **Task completion** | todo-sync | task-protocol-observer | task-enforcer (blocks Stop) |
| **Code-verify** | — | code-verify-reminder (PostToolUse:Skill\|Task\|Write\|Edit) | code-verify-reminder (Stop fallback, transcript scan) |

### 5.2 Bug history

| Bug | Impact | Mitigation | Status |
|---|---|---|---|
| #6305 PostToolUse не fires (Windows) | auto-commit, code-verify не работают | UPS + Stop fallback patterns | Active, всё mitigated |
| #10450 Windows stdin empty | Pytest output parse fails | text=True + encoding='utf-8', errors='replace' | Mitigated 2026-05-22 |
| Cyrillic path encoding | `git status --porcelain` octal escapes (`\320\236`) | `git -c core.quotepath=false` + `line[2:].lstrip()` | Mitigated 2026-02-22 |
| `line[3:]` baghunting | Loses leading `.` in paths | Switch to `line[2:].lstrip()` | Mitigated 2026-02-20 |
| Hook regressions from -X theirs merge | Silent NameError + ValueError | Mandatory post-merge importlib sweep | Active (memory `feedback_post_merge_smoke_required`) |

---

## §6 Skills System + Task Protocol

### 6.1 skill-router 4-layer matching

| Layer | Mechanism | Trigger |
|---|---|---|
| **A: Phrase** | Exact weighted keyword (1-6) | Always |
| **B: Fuzzy** | 78% threshold typo tolerance | Single-word miss |
| **C: TF-IDF** | Precomputed route-tfidf/ semantic | Low keyword score |
| **D: Qdrant fallback** | Semantic search (0.5s) | TF-IDF too low + enabled |

**Config:** `skill-router-config.json` v9 — 98 skills, 50+ bundles, 4500+ weighted keywords.

**Output:** `[SKILL-ROUTER] Bundles: X\nACTIVATE SKILLS [LEVEL]: Skill('y')` через stdout (100% injection rate).

**Tracking:** `data/skill-router.log` + `data/skill-accuracy.jsonl` (recommend→activate corr).

### 6.2 Task Protocol Phase Machine

`idle → classified → (decomposed) → skill_checked → ALLOW Write/Edit`

| Phase | Что произошло | Write/Edit |
|---|---|---|
| idle | Ничего | BLOCKED |
| classified | skill-eval-enforcer auto-classified trivial/medium/complex | BLOCKED |
| decomposed | TaskCreate вызван (только non-trivial) | BLOCKED |
| skill_checked | Skill() вызван | **ALLOWED** |

**State:** `~/.claude/cache/session-skills.json` (per-session).

**Exempt:** `.claude/`, `docs/`, `data/`, config files.

### 6.3 Code-verify 4 modes × 3 levels

| Mode | When | Reference input |
|---|---|---|
| **knowledge-compliance** | Learning Loop FETCH→EXECUTE | knowledge_block from FETCH |
| **behavior-preservation** | Refactoring | original + refactored code |
| **bug-fix-validation** | Bug fix | bug desc + fix + tests |
| **quality-review** | New code / general | code only |

**3 levels:** Structural (grep) → Subagent (Task dispatch) → Decision (PASS/PARTIAL/FAIL → Ralph Wiggum max 3 iter).

**Marker contract:** subagent ends with `[CODE-VERIFY-PASS]` / `[CODE-VERIFY-FAIL]`.

---

## §7 Memory + Delegation

### 7.1 4-Layer Federated Recall

| Layer | Source | Weight | Budget | Backend |
|---|---|---|---|---|
| 1 | SQLite important_messages | 0.30 | 200ms | Token overlap + RU stemming |
| 2 | Qdrant skill_library + experience + conversation | 0.35 | 2s | TEI Qwen3-Embedding-8B (4096d) |
| 3 | .md files (~/.claude/projects/.../memory/) | 0.15 | 500ms | Token overlap weighted |
| 4 | Wiki drafts (docs/wiki/drafts/) | 0.20 | 200ms | **STUB** (returns []) |

**RRF merge** по content hash, dedup, top-K=5 в systemMessage.

**Fallback:** TEI unavailable → token-overlap на learned_patterns.

**State:** cooldown 30s в `memory-first-cooldown.json`.

### 7.2 Delegation (Z.AI / LLM Rotation)

**Classification:** Never (architecture, debug) / Hard (code gen) / Medium (docs, tests) / Soft (3+ files, Orchestrator).

**Routing:** `DELEGATION_ROUTER_CANARY_PCT` gates TrainedRouter (cosine) vs LinUCB bandit. Deterministic A/B via sha256.

**Outcome corpus:** `data/delegation-outcomes.jsonl` (online bandit update).

**5 providers:** Z.AI GLM-5 (primary), Gemini, OpenRouter, Ollama, Anthropic (fallback).

**Guard:** `z-ai-write-guard.py` blocks >15 lines code если no `llm_delegation` в session.

---

## §8 Git/PR Automation

### 8.1 Auto-git-save 3-layer redundancy

| Layer | Hook | Event | Role |
|---|---|---|---|
| 1 | `auto-git-save.py` | PostToolUse Write\|Edit\|Bash | Threshold sync commit |
| 2 | `posttooluse-auto-git-save.py` | PostToolUse | Debounced 5s fallback |
| 3 | `auto-git-save-prompt.py` | UserPromptSubmit | #6305 workaround |
| 4 | `auto-git-save.py` | Stop | Final push |

**Threshold:** default 1, `CLAUDE_COMMIT_THRESHOLD` env.
**Pause:** `.claude/cache/auto-git-save.paused` (TTL "30m"/"forever").
**Settings guard:** blocks if `.claude/settings.json` shrinks >30 lines.

### 8.2 PR Automation P0-P3 (post-task-push-pr)

PostToolUse:TaskUpdate, **timeout 1320s** (22 минуты для wait-for-checks).

**11-stage pipeline:** P2.1 record start_sha → P0.1 label gating → scope check (AUTO_PR_MIN_COMMITS) → P0.4 pre-push pre-commit → P1.3 auto-rebase → P3.2 cherry-pick worktree → P0.2 conflict-aware push → P0.3 existing PR reuse → P2.3 CODEOWNERS reviewers → P2.5 blocked-by labels → P1.2 wait-for-checks + merge.

**Env keys:** AUTO_PR_ENABLED, AUTO_PR_BASE (default master), AUTO_PR_MIN_COMMITS=3, AUTO_PR_DRY_RUN, AUTO_PR_AUTO_MERGE, AUTO_PR_MERGE_QUEUE, AUTO_PR_CHECKS_TIMEOUT=300.

**State:** `.claude/cache/post-task-push-pr-state.json` (per-task: start_sha, branch, pr_url, blockedBy).

**Helpers:** `shared/pr_helpers.py` (cherry_pick_range_to_branch worktree-based), `shared/pr_notifier.py` (SMTP), `scripts/pr_check_post_merge.py` (P3.4 auto-revert), `scripts/pr_automation_dashboard.py` (P1.5), `.mergify.yml` (P3.3 free template).

### 8.3 Docs-change-enforcer (Stop)

**Session-bounded git window:** reads `data/hook-invocations.jsonl` tail, finds session's earliest invocation → `git log --since=`.

**Excludes auto-format commits:** `^chore: auto-save`, `^chore: rollup auto-format`.

**Mapping:** 70+ `CODE_TO_DOMAIN` entries [prefix, chapter, skill]. First-match-wins, specific ДО general.

**Skip patterns:** 140 exclusions (vendor, generated, 3rd-party).

**3-phase check:** stale_domains → stale_infra → unmapped_changes (suggests /audit-docs).

**Cooldown:** 30 минут.

### 8.4 Factory-enforcer (PostToolUse:Write)

Hook/skill file created → mandatory tasks для registration + verification (Step 4 + Step 5 в settings.json + MEMORY.md + triggers test).

---

## §9 Failure Modes + Recovery

### 9.1 Known failure classes

| Class | Symptom | Detection | Recovery |
|---|---|---|---|
| **PostToolUse no-fire (#6305)** | auto-commit/code-verify не работает | hook-invocations.jsonl absence | UPS/Stop fallback patterns |
| **Hook ImportError after merge** | UserPromptSubmit/PreToolUse errors в UI | tail hook-invocations.jsonl outcome=error | importlib sweep всех hooks |
| **Hook NameError** (typing import lost) | Module loads fail | grep for `: Any/dict[str, Any]` without `from typing` | Restore import |
| **Hook UnicodeEncodeError** | print() с → arrows crashes Windows cp1251 | "charmap codec" в error trace | sys.stdout.reconfigure utf-8 errors='replace' |
| **Pre-commit вендор spillover** | autofix touches 1300+ vendor files | git status --short после autofix | Add to exclude regex (tools/, jre/, etc.) |
| **Disjoint master histories** | gh pr create rejects "no history in common" | git merge-base пусто | Force-push reconciliation with archive ref |
| **Auto-save preempt** | Auto-git-save коммитит до meaningful commit | git log shows chore: auto-save | Use git commit --amend (если parent не запушен) |
| **Submodule stale snapshot** | EDT write_module_source затирает чужие правки | git diff submodule | git checkout + Edit re-apply |
| **Cherry-pick conflict (PR-automation)** | cherry-pick fails если file отсутствует на base | post-task-push-pr fallback log | Use mode=head-ref instead of cherry-pick |
| **Z.AI write guard false-positive** | Blocks docs/markdown | guard fires на .md > 15 lines | Chunk Write/Edit ≤14 lines |
| **Skill router phantom blocking** | Recommends non-existent skill | code-skill-patterns.json validation | Audit script: `re.findall(r'"skill":\s*"([^"]+)"',text)` exists check |

### 9.2 Mandatory post-merge smoke (lesson из PR #2)

После любого `git merge -X theirs` на 20+ conflict-diff:

```bash
# 1. Import sweep всех top-level хуков
python -c "
import sys, importlib.util
from pathlib import Path
sys.path.insert(0, r'C:/1С-Framework/.claude/hooks')
fail = []
for f in Path(r'C:/1С-Framework/.claude/hooks').glob('*.py'):
    try:
        spec = importlib.util.spec_from_file_location(f.stem, str(f))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
    except Exception as e:
        fail.append((f.name, type(e).__name__, str(e)[:80]))
print(f'Pass: {59-len(fail)}/{59} | Fail: {len(fail)}')
for n,t,m in fail: print(f'  {n}: {t}: {m}')
"

# 2. Tail audit log на новые errors через 1-2 минуты после resume
tail -200 data/hook-invocations.jsonl | python -c "
import json,sys
for line in sys.stdin:
    try:
        r = json.loads(line)
        if r.get('outcome') == 'error':
            print(r.get('hook'), r.get('error',''))
    except: pass
"

# 3. Smoke critical hooks via stdin
echo '{"prompt":"test"}' | python .claude/hooks/memory-first-hook.py
echo '{"tool_name":"Bash","tool_input":{"command":"x"},"tool_response":"FAILED"}' | python .claude/hooks/posttooluse-bash-errors.py
```

См. memory [`feedback_post_merge_smoke_required`](file:///C:/Users/Tech.%20Boutique/.claude/projects/C--1--Framework/memory/feedback_post_merge_smoke_required.md).

---

## §10 Observability + State Files

### 10.1 Audit log

**File:** `data/hook-invocations.jsonl`
**Format:** `{ts, hook, event, tool, elapsed_ms, outcome, session, error, agent_id, category, run_id}`
**Categories:** `hook`, `mcp_call`, `slash_run`, `preflight`, `delegation_decision`

**Diagnostic:** `tail -500 data/hook-invocations.jsonl | jq 'select(.outcome=="error")'`
