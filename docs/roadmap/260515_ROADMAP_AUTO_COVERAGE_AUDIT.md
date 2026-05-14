# 260515 — Auto-coverage Audit: auto-commit + auto-docs

**Status:** Phase A done (2026-05-15); Phase B/C open
**Discovered:** 2026-05-15 during framework process coverage analysis
**Context:** User flagged 126 uncommitted files (внутри submodules) + asked to ensure all framework processes covered by auto-commit/auto-docs patterns

## Current inventory (как было до Phase A)

### Auto-commit chain (3 hooks)

| Hook | Event | Strategy | Notes |
|---|---|---|---|
| [`auto-git-save.py`](../../.claude/hooks/auto-git-save.py) | PostToolUse: Write\|Edit\|Bash | Threshold=1 → sync commit; tracks files в metadata task; supports `auto-git-save.paused` sentinel | Полный controlled flow |
| [`posttooluse-auto-git-save.py`](../../.claude/hooks/posttooluse-auto-git-save.py) | PostToolUse: Write\|Edit | 5s debounce, `git commit --no-verify` | Workaround for Claude Code #6305 на Windows |
| [`auto-git-save-prompt.py`](../../.claude/hooks/auto-git-save-prompt.py) | UserPromptSubmit | UPS fallback layer | Triple redundancy при partial firing |

### Auto-docs chain (3 hooks + 1 skill)

| Component | Event | Action |
|---|---|---|
| [`docs-change-tracker.py`](../../.claude/hooks/docs-change-tracker.py) | PostToolUse: Write\|Edit | Pending mandatory task с mapping → chapter+skill |
| [`posttooluse-docs-tracker.py`](../../.claude/hooks/posttooluse-docs-tracker.py) | PostToolUse: Write\|Edit | Instant reminder (Phase 1.3) |
| [`docs-change-enforcer.py`](../../.claude/hooks/docs-change-enforcer.py) | Stop | BLOCK если код changed без docs update |
| [`audit-docs`](../../.claude/skills/audit-docs/SKILL.md) skill | Manual / on demand | `scripts/audit_docs_skills.py` — 6 категорий: REST API, MCP, Search, CLI, Config, Agent |

## Gaps identified

### Gap 1: Submodule coverage missing (CRITICAL)

100+ файлов внутри `ИБTransportManagementDevelop/Конфигурация` и `configuration/<JIRA>/` показываются в parent git status **только как `m` flag** (pointer drift). Auto-git-save hooks работают на parent-repo level — внутрь submodules не лезут. Результат: BSL/XML changes (10-100 файлов на task) накапливаются без auto-commit.

**Risk:** Parallel session работающая над 1С task может потерять changes если IDE/process крашится.

**Phase B fix:** новый hook `submodule-auto-commit.py` (PostToolUse Bash на `update_database` MCP call OR explicit `git submodule foreach` periodic check).

### Gap 2: Mapping fidelity (FIXED in Phase A)

Pre-2026-05-15 `docs-change-enforcer.py`:
- `src/memory/` → `01_ОБЗОР` (skill `pdf-knowledge`) — semantically wrong; Memory subsystem ≠ Overview
- `src/memory/librarian/wiki_*` имели тот же мэппинг → docs-change-tracker создавал tasks неверно адресованные

**Phase A fix applied:** добавлены specific overrides:

```python
# In order before general src/memory/ prefix:
("src/memory/librarian/wiki_promoter.py", "32_WIKI_KNOWLEDGE_LAYER", "wiki-pipeline"),
("src/memory/librarian/wiki_decay.py",    "32_WIKI_KNOWLEDGE_LAYER", "wiki-pipeline"),
("src/memory/librarian/",                  "32_WIKI_KNOWLEDGE_LAYER", "wiki-pipeline"),
("src/pdf_framework/indexing/wiki_exporter.py", "32_WIKI_KNOWLEDGE_LAYER", "wiki-pipeline"),
("src/memory/orchestrator/",            "27_UNIFIED_MEMORY",     "memory-unified"),
("src/memory/ai_memory/",               "27_UNIFIED_MEMORY",     "memory-unified"),
("src/memory/vector_memory/",           "27_UNIFIED_MEMORY",     "memory-unified"),
("src/memory/skill_learning/",          "29_XSKILL_CONTINUOUS_LEARNING", "memory-unified"),
("src/memory/infrastructure/",          "27_UNIFIED_MEMORY",     "memory-unified"),
("src/memory/",                        "27_UNIFIED_MEMORY",     "memory-unified"),
```

Now Memory changes route to `27_UNIFIED_MEMORY`; wiki librarian → `32_WIKI_KNOWLEDGE_LAYER`. **First-match-wins** — specific overrides ДОЛЖНЫ предшествовать general prefix.

### Gap 3: Hook duplication (Phase C — refactor)

Three auto-git-save hooks делают похожее. Триадная защита (threshold + debounce + UPS fallback) была нужна как workaround для #6305 на Windows. Современный Claude Code (post 2.1.126) более стабилен, redundancy может быть consolidated.

**Phase C fix:** Unified `auto-git-save-v2.py` с mode-flag (`--threshold | --debounce | --fallback`). Single source of truth для commit message формата (см. этой сессии fix `auto-save filename, filename +N more`).

### Gap 4: audit-docs скилл scope узкий (Phase B)

Текущий `scripts/audit_docs_skills.py` audits 6 категорий из `src/pdf_framework/` + `src/api/` + `src/cli/` + `src/mcp_server/`. **Не покрывает:**

- `src/memory/` подсистемы (wiki librarian, ai_memory, vector_memory, orchestrator, infrastructure)
- `src/bsl/` (semantic_search, mcp_server, mcp_integration, sonar, finetuning)
- `src/framework_search/` (Phase 9 self-search)
- `src/extensions/` (Phase 35)
- `.claude/hooks/` themselves (no audit against hook catalogue)
- `.claude/skills/` themselves (no audit что skills соответствуют actual functionality)

**Phase B fix:** Extend `audit_docs_skills.py` с 6 → 12+ categories. Add extractors для memory subsystem, BSL tools, hooks catalogue.

### Gap 5: Pre-commit + auto-save tension

Pre-commit hook chain validates `Markdown Lint (wiki)` + `KB Lint (wiki)` + ruff + mypy + gitleaks. Auto-save uses `--no-verify` → markdownlint warnings ship without notice. В этой сессии 152 markdownlint errors на 4 hub pages вскрылись только при `git commit` без `--no-verify`.

**Phase B fix:** Periodic `markdownlint-cli2 --fix` scheduled run (daily/weekly cron), OR `auto-git-save` без `--no-verify` once markdownlint config aligned with reality.

### Gap 6: No periodic / scheduled audit

Все hooks event-driven (Write/Edit/Bash/Stop/UserPromptSubmit). **Нет** periodic scan:
- Submodule drift detection
- Stale `docs/wiki/drafts/` cleanup
- Orphan entity detection (verify CLI exists, но не cron'ом)
- Decay run (also exists CLI, но manual cadence)

**Phase B fix:** новый `SessionStart` hook `audit-coverage.py` запускающий smoke-check на coverage gaps + warning systemMessage. ИЛИ external cron через Windows Task Scheduler.

## Plan

### Phase A (DONE 2026-05-15)

- ✅ Mapping fix in `docs-change-enforcer.py`: added 11 overrides для `src/memory/librarian/` + `src/memory/<subsystem>/` + `src/pdf_framework/indexing/wiki_exporter.py`
- ✅ This roadmap documenting full audit
- ✅ Note in CLAUDE.md hooks section about session findings

### Phase B (open, medium effort)

| Item | Effort | Priority |
|---|---|---|
| B1: Submodule auto-commit hook | 2-3h | HIGH (data loss risk in 1С workflow) |
| B2: Extend `audit-docs` to 12+ categories | 3-4h | MEDIUM (improves visibility) |
| B3: Periodic audit-coverage hook (SessionStart) | 1-2h | MEDIUM (drift detection) |
| B4: Pre-commit + auto-save alignment | 4-6h | LOW (cosmetic markdown debt) |

### Phase C (open, large refactor)

| Item | Effort | Priority |
|---|---|---|
| C1: Consolidate 3 auto-git-save hooks → 1 unified | 1 day | LOW (current redundancy works) |
| C2: Semantic mapping (use `wiki_pages_v1` Qdrant) instead of mechanical prefix table | 2 days | LOW (current table works for known paths) |

## Связано

- Skill [`auto-git-save`](../../.claude/skills/auto-git-save/SKILL.md) — current chain documentation
- [Chapter 32 Wiki Knowledge Layer](../framework%20documentation/32_WIKI_KNOWLEDGE_LAYER/32.1_Обзор.md) — primary subsystem owner для Phase A fixes
- [Chapter 09.7 Система хуков](../framework%20documentation/09_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md) — общая глава про hook chain
- Skill [`audit-docs`](../../.claude/skills/audit-docs/SKILL.md) — current 6-category audit script
