# Roadmap 260523 — Unified Branch Topology Reconciliation

**Дата создания:** 2026-05-23
**Статус:** living document — Phase 0 DONE (PR #4 landed), Phase 1-5 PENDING
**Заменяет:** [260519](260519_ROADMAP_MASTER_RECONCILIATION.md) + [260522](260522_ROADMAP_PR_AUTOMATION_MIGRATION_TO_DEV_MASTER.md)
**Память:** [project_disjoint_master_topology](file:///C:/Users/Tech.%20Boutique/.claude/projects/C--1--Framework/memory/project_disjoint_master_topology.md), [feedback_precommit_vendor_excludes](file:///C:/Users/Tech.%20Boutique/.claude/projects/C--1--Framework/memory/feedback_precommit_vendor_excludes.md)

---

## §0 TL;DR

В репо живут две независимые ветки истории: `origin/master` (legacy, frozen Apr 2026) и `origin/dev-master` (canonical для разработки). Они без общего предка — `git merge-base` пусто. Это корневая проблема (roadmap 260519).

Следствие: любая фича разрабатываемая на длинноживущей `feat/serena-audit-hybrid-refactor` (2233+ коммитов поверх `dev-master`) не может быть merged быстро — её нужно мигрировать на `dev-master` отдельным PR'ом с inventory + protocol-port + surgical settings.json patches. **PR-automation было первым прохождением** этого паттерна (roadmap 260522 → **PR #4 MERGED 2026-05-23**). Каждая следующая фича повторит цикл.

**Unified roadmap решает три задачи:**
1. **Стандартизирует** workflow «feat → dev-master migration PR» (lessons из PR #4 round-6/7)
2. **Закрывает** structural master reconciliation (260519 Phase 2-6)
3. **Удаляет** `dev-master` как workaround, делая `master` единственной canonical branch

Трудозатраты: **3-7 часов** + одна крупная migration PR из feat-ветки.

---

## §1 Реальная картина 2026-05-23

### 1.1 Branch topology

| Ref | HEAD | Назначение | Состояние |
|---|---|---|---|
| `origin/master` | `ae3a59534` | Legacy (frozen 2026-04-11), не используется | 2 236 уникальных vs local master, **0 общих предков** |
| `origin/dev-master` | `25ab2de39` | **De-facto canonical** — все PR сюда | 12 коммитов впереди local master (вкл. PR #4 merge) |
| `local master` | `b9cba8cb1` | Backup snapshot pre-PR#4 | 2 677 уникальных vs origin/master, **0 общих предков** |
| `local dev-master` | `b9cba8cb1` | Tracking branch (behind 12) | Идентичен local master, нужен fast-forward |
| `local feat/serena-audit-hybrid-refactor` | `3ac091b49` | **Активная разработка** | 50 ahead of origin, **2 233 ahead of dev-master, 12 behind** |
| `origin/archive/master-pre-reconciliation-2026-05-19` | `ae3a59534` | Backup origin/master | Frozen safety net |
| `origin/migrate/pr-automation-stack` | `1afb5c64f` | Worktree-ветка PR #4 (merged) | **Cleanup pending** — удалить |
| tag `origin-master-archive-2026-05-19` | `ae3a59534` | То же что branch archive | Frozen safety net |

### 1.2 PR queue

| PR | State | Base ← Head | Title |
|---|---|---|---|
| **#2** | OPEN (5+ дней) | `dev-master` ← `feat/serena-audit-hybrid-refactor` | feat: Serena audit — hybrid retrieval |
| **#3** | demo open / abandoned | `dev-master` ← demo (P3.2) | используется для cherry-pick fallback тестов, удалить |
| **#4** | **MERGED 2026-05-23 03:13 UTC** | `dev-master` ← `migrate/pr-automation-stack` | feat(pr-automation): land P0-P3 batch on dev-master |

### 1.3 Что DONE vs PENDING из исходных roadmap'ов

**260519 (Master Reconciliation):**
- ✅ Phase 1: Архивация origin/master (tag + branch) — DONE 2026-05-19
- ⏳ Phase 2: Аудит 2 236 уникальных origin/master коммитов — pending
- ⏳ Phase 3: Cherry-pick legitimate коммитов в local master — pending
- ⏳ Phase 4: Force-push local master → origin/master — pending
- ⏳ Phase 5: PR #2 retarget на master + удалить dev-master + mypy-baseline sync — pending
- ⏳ Phase 6: Verify CI green — pending

**260522 (PR-automation Migration):**
- ✅ Phase A-G: вся миграция выполнена через **PR #4 (round-6/7)** — DONE 2026-05-23
- ✅ Bonus: discovered + memory-saved [feedback_precommit_vendor_excludes](file:///C:/Users/Tech.%20Boutique/.claude/projects/C--1--Framework/memory/feedback_precommit_vendor_excludes.md)
- ⏳ Cleanup: `git push origin :migrate/pr-automation-stack` — remote branch ещё жив
- ⏳ Sync feat ↔ dev-master — deferred (2 233 commits, requires merge not rebase)

---

## §2 Общий корень и cascade effects

```
ROOT: origin/master ↔ local master — disjoint histories (no common ancestor)
                          │
                          ▼
WORKAROUND #1: dev-master как de-facto canonical (every PR → dev-master)
                          │
                          ▼
SYMPTOM #1: PR #2 не может быть merged в origin/master напрямую
                          │
                          ▼
WORKAROUND #2: feat-branch накапливает 2 233 commits ahead of dev-master
                          │
                          ▼
SYMPTOM #2: фичи feat-branch не доставляются на dev-master малыми PR'ами
                          │
                          ▼
WORKAROUND #3: migration PR'ы из feat → dev-master (как PR #4)
                          │  Каждый требует:
                          │  - inventory файлов
                          │  - protocol divergence check
                          │  - surgical settings.json patch
                          │  - 4-7 round'ов CI cleanup
                          ▼
SYMPTOM #3: каждая фича = новый mini-260522 (повторяющийся cost)
```

**Ключевое наблюдение:** PR #4 closed конкретный instance, но **паттерн остаётся**. Любая следующая фича на feat-branch потребует такого же migration cycle. Этот roadmap должен либо устранить корень (260519 Phase 2-6), либо стандартизировать workaround (§4).

---

## §3 Unified Phase Plan

### Phase 0 — PR #4 (DONE 2026-05-23)

Migration PR-automation подсистемы на dev-master. Closed 260522. Lessons → §4, §5.

### Phase 1 — Immediate cleanup (~15 минут)

**Цель:** обнулить остаточные ref'ы от PR #4.

```bash
# Удалить remote migration-ветку (PR merged, ветка не нужна)
git push origin :migrate/pr-automation-stack

# Fast-forward local master + local dev-master к origin/dev-master
git checkout master
git merge --ff-only origin/dev-master
git push origin master
git checkout dev-master 2>/dev/null && git merge --ff-only origin/dev-master
```

**Verification:** `gh pr list --state open` показывает только PR #2; `git log master..origin/dev-master` пусто.

### Phase 2 — Audit unique origin/master commits (~30-60 минут)

**Цель:** идентифицировать 20-50 legitimate коммитов из 2 236 уникальных origin/master, которые нужно cherry-pick'нуть в master перед force-push.

Идентично §3 (Phase 2) исходного 260519. Эвристики, prefix-stats, категоризация по noise/duplicate/legitimate — без изменений.

**Output:** `/tmp/selected-hashes.txt` — отсортированный список hash'ей в хронологическом порядке.
