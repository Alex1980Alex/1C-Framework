# Roadmap 260525 — CI Autopilot Phase 2

**Дата:** 2026-05-25 evening
**Тип:** Implementation roadmap (extends [PR #54 fix(ci): auto-catchup](https://github.com/Alex1980Alex/1C-Framework/pull/54))
**Scope:** Превратить CI monitoring из session-bound semi-manual в **полностью автономную** систему с email-side intake и daily digest.
**Status:** PROPOSED — Phase 1 (quick wins #1+#4+#5+#6) выполнен отдельно. Phase 2 items — pending user decision.

---

## §0 Context

Сейчас (после Phase 1):
- ✅ `ci_failure_cache.py` — fixed PR resolution + `--catchup` mode + timestamp normalization + step extraction
- ✅ SessionStart hook `ci-catchup-on-start.py` — auto-backfill при resume
- ✅ Monitor `bbq4k79fh` — live polling 20s, auto-cache на FAILURE
- ✅ Cache: `.claude/cache/ci-failures.jsonl` + `ci-failure-issues.json`
- ✅ Auto-issue creation на N≥3 recurrences (после timestamp fix)

**Что остаётся открытым:**

| Gap | Текущая обработка | Желаемое |
|---|---|---|
| Off-session window | catchup при следующем resume сессии | Real-time server-side trigger |
| GitHub notifications | вручную через `gh notifications` | Auto-parse via Gmail MCP, label по типу |
| Дайджест "что было ночью" | пользователь сам читает Monitor stream / cache | Markdown digest в чат + опционально email |

**Цель Phase 2:** закрыть эти 3 gap'а → пользователь **не должен** ни разу руками открывать GitHub UI или почту чтобы понять состояние CI. Полная автономия с моей стороны.

---

## §1 Item #2 — GitHub Actions `workflow_run` webhook

### 1.1 Проблема

Catchup на SessionStart решает gap «session resume», но между resume'ами CI может крашиться неограниченно долго. Если Claude session не запускалась 3 дня — auto-issue threshold не достигается (там за это время могло быть 10× одной ошибки, но при batch import всё попадает в одну минуту → reads as 10 одинаковых entries с разными timestamps — это уже фиксится Phase 1, но gap всё равно есть).

**Цель:** trigger ci_failure_cache **в момент CI completion**, без Claude session.

### 1.2 Архитектура

```
GitHub workflow_run event (any workflow conclusion=failure)
   ↓
.github/workflows/ci-failure-cache.yml triggers
   ↓
Lightweight Python job:
   1. Parse event payload (run_id, workflow, headBranch, headSha)
   2. gh run view --log-failed → extract first error
   3. Normalize via timestamp regex (Phase 1 helper)
   4. SHA256 hash
   5. Commit append к .claude/cache/ci-failures.jsonl на `automation/ci-cache` branch
   6. Если N≥3 hash recurrences:
       - gh issue create
       - gh api POST commit к cache file
```

### 1.3 Tech enablers

- **`workflow_run` trigger** — single event для всех workflows
- **GITHUB_TOKEN** permissions: `contents: write` + `issues: write`
- **`gh` CLI** — pre-installed в `ubuntu-latest`
- **Cache backend in CI:** JSONL append-only file commit'ится в **отдельную ветку `automation/ci-cache`** (не master, чтобы не засорять history). Чтение через `gh api /repos/.../contents/.claude/cache/ci-failures.jsonl?ref=automation/ci-cache`.

### 1.4 Tradeoffs

| Option | Pros | Cons |
|---|---|---|
| **A. workflow_run + commit-back to dedicated branch** (RECOMMENDED) | Server-side, no Claude session needed; всё в одном репо | Каждый failure → mini commit; branch grows fast (retention nightly cron) |
| B. workflow_run + GitHub Actions cache | Cleaner, no commits | GitHub Actions cache scope-bounded (workflow-level only), не подходит для cross-workflow accumulation |
| C. External service (Cloudflare Worker + KV) | Best architecture | Vendor lock-in, новая инфра, секреты |
| D. Email-only (workflow → SMTP → Gmail label) | No state mgmt | Lossy, нельзя programmatically read history |

### 1.5 Risks

- **Concurrent commits**: 2+ workflows complete simultaneously → race на push. Mitigation: `git pull --rebase` в retry loop + `--force-with-lease` на push.
- **Branch grows unbounded**: 100 failures/day × N days = bloat. Mitigation: nightly cron rewrite (squash older entries за >30 дней в single archive commit).
- **GITHUB_TOKEN scope**: writeback на non-main branch требует branch protection allowlist (или absence of protection on `automation/*`).
- **CI cost**: каждый workflow run → +1 cache workflow run → +1 minute billing. Acceptable for free tier.

### 1.6 Effort

- New file: `.github/workflows/ci-failure-cache.yml` (~80 lines YAML)
- Modify `scripts/ci_failure_cache.py`: add `--ci-mode` flag (no TEI/Qdrant, no local file, append via gh api)
- New file: `scripts/ci_cache_rotate.py` (nightly squash)
- Tests: `tests/integration/test_ci_failure_cache_ci_mode.py`
- Doc: `docs/framework documentation/42_MONITOR_CI/42.5_GitHub_Actions_Webhook.md`

**Estimate:** 1.5-2 дня focused work.

---

## §2 Item #3 — Gmail MCP integration

### 2.1 Проблема

GitHub posting notifications (PR opened, review requested, security alerts, CI failures) уходят в Gmail. Сейчас:
- Пользователь читает Gmail вручную → форвардит важное мне → я обрабатываю
- Никакого автоматического parsing
- Никакого filtering по приоритету

У нас доступен **`claude_ai_Gmail` MCP server** с tools:
- `search_threads` — query Gmail (e.g. "from:notifications@github.com is:unread")
- `list_drafts` / `create_draft` — для outgoing
- `label_thread` / `label_message` — для filtering taxonomy
- `get_thread` — full content
- `list_labels` / `create_label` / `update_label` / `delete_label`

### 2.2 Архитектура

```
SessionStart hook ci-catchup-on-start.py (Phase 1)
   ↓
[NEW] sub-step: query Gmail для unread GitHub notifications
   ↓
For each thread:
   1. Parse subject + body → classify type (PR-review, CI-fail, security-alert, dependabot-merge, etc.)
   2. Apply Gmail label "github/<type>"
   3. Extract metadata (PR#, run_id, severity)
   4. Cross-reference с .claude/cache/ci-failures.jsonl (avoid dupes)
   5. Generate draft reply if action needed (e.g. "I'll investigate when next session resumes")
   6. Emit systemMessage в Claude chat: "[GMAIL] 5 unread GH threads: 3 CI fails + 2 PR reviews"
```

### 2.3 Tech enablers

- **`claude_ai_Gmail` MCP** — уже подключен (deferred tools list)
- **GitHub email subject taxonomy** — well-known formats:
  - `[org/repo] PR title (#N)` — PR activity
  - `Re: [org/repo] CI run completed: workflow` — CI
  - `[org/repo] Dependabot Updates failed` — Dependabot
  - `[GitHub] New advisory ...` — security
- **Cross-reference** — `run_id`, `pr` уже в JSONL cache

### 2.4 Tradeoffs

| Option | Pros | Cons |
|---|---|---|
| **A. SessionStart catchup + sub-hook** (RECOMMENDED) | Atomic с CI catchup, единая точка trigger | Только при session start |
| B. Standalone daemon | True realtime | Новый процесс, lifecycle management |
| C. Cron + native mailto webhook | Server-side | Complex setup, не реюзает MCP |

### 2.5 Risks

- **Gmail OAuth refresh** — MCP token может expire. Mitigation: SessionStart probe + re-auth notification.
- **False positives на classification** — regex/keyword based. Mitigation: conservative labelling + log to stderr for manual triage.
- **Reply drafts могут быть premature** — draft не отправляется автоматически, только сохраняется. User confirms before send.
- **Privacy** — нельзя случайно log full email body в JSONL. Mitigation: только metadata + classification.

### 2.6 Effort

- New hook: `.claude/hooks/gh-email-intake-on-start.py` (~100 lines, registers как часть SessionStart chain)
- New helper: `.claude/hooks/shared/gmail_classifier.py` (~80 lines — regex taxonomy)
- New script: `scripts/gh_email_summary.py` (CLI для manual digest)
- Doc: `docs/framework documentation/42_MONITOR_CI/42.6_Gmail_Integration.md`

**Estimate:** 0.5-1 день.

---

## §3 Item #7 — Daily digest

### 3.1 Проблема

После полного дня CI runs / Dependabot / merges — нет single artefact показывающего «что произошло». Monitor stream разорван по событиям, cache flat JSONL, Gmail тонет в notifications.

**Цель:** markdown digest за последние 24h: PRs merged/closed, failures top-5, recurring patterns, suggested actions.

### 3.2 Архитектура

```
$ python scripts/ci_digest.py [--since 24h] [--save docs/reports/...] [--draft-email]

Sections:
1. Summary: N PRs merged, M failures, K open
2. Top recurring failures (post-Phase-1 normalization)
3. Open PRs needing attention (failed required gates)
4. New auto-issues created
5. Dependabot status (success/fail ratios)
6. Suggested actions (e.g. "rotate ANTHROPIC_API_KEY", "rebase PR #X")
```

### 3.3 Tech enablers

- **JSONL cache** уже готов
- **`gh pr list --state merged --search "merged:>YYYY-MM-DD"`** — recent merges
- **`gh issue list --label automated`** — auto-created issues
- **`claude_ai_Gmail.create_draft`** для optional email send

### 3.4 Tradeoffs

| Option | Pros | Cons |
|---|---|---|
| **A. CLI script + Gmail draft + chat output** (RECOMMENDED) | Self-contained, reusable | Manual trigger |
| B. CronCreate routine (daily 9am) | True automation | Vendor lock-in (Claude routines) |
| C. GitHub Actions scheduled workflow | Server-side | More moving parts |

### 3.5 Risks

- **Stale data** if catchup didn't run — mitigated by running catchup as first step within digest.
- **Digest fatigue** — daily emails в Gmail ignored. Mitigation: weekly summary mode + actionable bullet points only.

### 3.6 Effort

- New script: `scripts/ci_digest.py` (~200 lines)
- Optional skill: `.claude/skills/ci-digest/SKILL.md` (~50 lines)
- Doc: `docs/framework documentation/42_MONITOR_CI/42.7_Daily_Digest.md`

**Estimate:** 0.5 день.

---

## §4 Total effort + sequencing

| Phase | Items | Effort | Status |
|---|---|---|---|
| Phase 1 (Quick wins) | #1 timestamps + #4 step extraction + #5 Monitor badge + #6 retro-clean | 2h | ⏳ IN PROGRESS (this session) |
| **Phase 2 (this roadmap)** | #7 daily digest | 0.5d | ⏳ PROPOSED |
| Phase 3 | #3 Gmail integration | 0.5-1d | ⏳ PROPOSED |
| Phase 4 | #2 workflow_run webhook | 1.5-2d | ⏳ PROPOSED |
| **Total Phase 2-4** | | **2.5-3.5 days** | |

**Order rationale:**
1. **#7 first** (digest) — non-intrusive, reuses existing infra, immediate user value
2. **#3 second** (Gmail) — extends digest with email-side intake
3. **#2 last** (workflow_run webhook) — biggest infra change, lowest urgency (catchup mostly covers gap)

---

## §5 Decision points (для пользователя)

1. **Apply Phase 2-4 в этой последовательности?** Или приоритизировать иначе (например Gmail сразу, digest потом)?
2. **`automation/ci-cache` branch model** для item #2 OK? Альтернатива — external KV store.
3. **Gmail labels naming** — `github/ci-fail`, `github/pr-review`, `github/dependabot` ОК? Или другая taxonomy?
4. **Digest frequency** — daily в 9am OK? Или weekly Monday?
5. **Draft email recipient** — `alexterletskii80@gmail.com` (текущий)?

---

## §6 Связанные артефакты

- [PR #54](https://github.com/Alex1980Alex/1C-Framework/pull/54) — Phase 1 base (auto-catchup + bug fix)
- [Chapter 42 Monitor CI](../framework%20documentation/42_MONITOR_CI/42.1_Обзор.md) — текущая архитектура
- [Memory `feedback_ci_maximum_autopilot_works`](file:///C:/Users/Tech.%20Boutique/.claude/projects/C--1--Framework/memory/feedback_ci_maximum_autopilot_works.md) — Phase 0 learnings
- [Memory `feedback_post_merge_smoke_required`](file:///C:/Users/Tech.%20Boutique/.claude/projects/C--1--Framework/memory/feedback_post_merge_smoke_required.md) — post-merge protocol

---

## §7 Open questions

- Q1: GitHub Actions billing impact — нужна оценка current minute consumption.
- Q2: Gmail rate limits для `search_threads` — нужен test query budget.
- Q3: Digest delivery — chat-only vs Gmail draft vs Slack webhook? Зависит от того где user активно работает.
- Q4: Retention policy для `automation/ci-cache` branch — nightly squash >30 дней?
