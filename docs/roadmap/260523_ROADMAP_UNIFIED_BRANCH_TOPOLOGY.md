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

### Phase 3 — Cherry-pick + force-push (~1-3 часа)

Идентично §4-§5 исходного 260519. Safety tag перед началом, для каждого hash — `git cherry-pick`, manual resolve. После — `git push --force-with-lease`.

**Hidden risk (new, не было в 260519):** Phase 1 fast-forward'нул local master на origin/dev-master (с PR #4 внутри). Cherry-pick'и из origin/master применяются поверх PR-automation стека, **возможны конфликты** в:
- `.claude/hooks/shared/` (PR #4 добавил pr_helpers, pr_notifier)
- `.claude/settings.json` (surgical patch на PostToolUse + AUTO_PR_* env)
- `.pre-commit-config.yaml` (excludes до 14 patterns + удалил mypy)
- `pyproject.toml` (pytest importmode + per-file-ignores)

**Mitigation:** при resolve брать union — origin/master legitimate edits + PR #4 inventory сохраняется.

### Phase 4 — Cleanup (~10 минут)

```bash
# Переключить PR #2 на canonical master
gh pr edit 2 --base master

# Закрыть PR #3 (demo)
gh pr close 3 --comment "Superseded by PR #4 + reconciliation 260523"

# Удалить dev-master
git push origin :dev-master
git branch -d dev-master
```

**Update memory:** [project_disjoint_master_topology](file:///C:/Users/Tech.%20Boutique/.claude/projects/C--1--Framework/memory/project_disjoint_master_topology.md) → пометить RESOLVED.

**Update mypy baseline:** `python -m mypy_baseline sync && git commit -am "chore(mypy): re-sync after reconciliation"`.

**Update CLAUDE.md:** убрать упоминания `dev-master` как working area, заменить на `master`.

### Phase 5 — Verify + standardize (~30-60 минут)

1. CI watch на pushed master
2. PR #2 auto-rebase trigger от `gh pr edit --base master`
3. Smoke на `.claude/hooks/post-task-push-pr.py` с `AUTO_PR_BASE=master`
4. Update `.claude/settings.json` env: `"AUTO_PR_BASE": "master"`
5. Update [40.4_Дорожная_карта.md](../framework%20documentation/40_PR_AUTOMATION/40.4_Дорожная_карта.md) — `dev-master` → `master` во всех env reference

---

## §4 Standardized Workflow Pattern (lessons из PR #4)

Пока **260519 Phase 2-5 не выполнен** (workaround dev-master остаётся), любая coherent feature delivery с feat → dev-master должна следовать паттерну выработанному в PR #4 round-6/7.

### Pattern A — Small incremental PRs (preferred)

Если фича изолирована (1-5 файлов):
1. На `feat`-ветке cherry-pick semantic коммит'ы на отдельную `feat-feature-xyz` from origin/dev-master
2. Squash в один semantic commit
3. PR против dev-master, CI должен пройти без round-2..7 cycle

### Pattern B — Coherent stack migration (PR #4 model)

Если фича обширная (>10 файлов, settings.json patches, docs section):
1. **Discovery roadmap** (по образцу 260522): inventory, hidden risks, semantic commits archaeology
2. **migrate/feature-name** worktree branch from origin/dev-master
3. **Inventory copy**: `git checkout feat -- <files>` для каждого identified file
4. **Protocol/base divergence check**: diff `base/protocol.py` + shared base — port if divergent
5. **Surgical settings.json patch**: НЕ копировать целиком, только новые hooks + env keys
6. **Squash + PR**
7. **CI cleanup rounds** (lessons из PR #4):
   - **Round 1-2**: baseline excludes (vendor: `tools/`, `infra/`, `external/`, `jre/`, `docs/documentation/`, `mcp-server.log*`, `.serena/`, `.vscode-extensions/`)
   - **Round 3-5**: dependency bumps (ruff, mypy additional_dependencies, missing test deps)
   - **Round 6**: pytest `--import-mode=importlib`; product code surgical fixes
   - **Round 7**: full pre-commit autofix bulk (~200-400 files); per-file-ignores в pyproject; mypy removed from pre-commit если 1000+ baseline errors
8. **Post-merge cleanup**: remove worktree, delete remote migration-branch, optional rebase feat

### Pattern decision matrix

| Признак фичи | Pattern |
|---|---|
| 1-5 файлов, no settings.json change | **A** |
| 6-10 файлов, minimal config | **A** with extra care |
| >10 файлов OR settings.json patches OR new docs section | **B** |
| Touches `base/`, `shared/`, `core/` (cross-cutting infra) | **B** (protocol divergence risk) |
| Builds on >5 другие WIP файлы на feat-branch | **B** (transitive dep'ы) |

---

## §5 Anti-patterns (collected from PR #4 round-6/7)

| Anti-pattern | Почему плохо | Правильный путь |
|---|---|---|
| `pre-commit run --all-files` без полных vendor excludes | Хватает 1300+ файлов JDK / LangChain docs / log dumps | ВСЕГДА проверить top-level `exclude:` ПЕРЕД autofix; minimum set в HEAD post-`a705e69c5` |
| Inventory copy всего `.claude/settings.json` с feat | Тянет 50+ unrelated hooks + phantom-блокировки через `code-skill-patterns.json` | Surgical patch: только новый matcher + env keys |
| Cherry-pick semantic коммита без проверки base/protocol.py divergence | Silent hook misclassification (DetectedEvent="Unknown"), ошибки в логах нет | Diff `base/protocol.py` + `base.py` blob hashes ПЕРЕД cherry-pick |
| mypy в pre-commit при 1000+ baseline errors без filter wrapper | Блокирует все local commits на pre-existing tech debt | Либо `mypy_baseline filter` wrapper, либо убрать mypy (CI имеет own continue-on-error job) |
| `pytest --import-mode=prepend` (default) с inconsistent `__init__.py` | Name collisions (`bsl.test_parser`↔`src/bsl/`, duplicate basename'ы) | `addopts = "--import-mode=importlib"` в `[tool.pytest.ini_options]` |
| Тащить `code-skill-patterns.json` целиком с feat → dev-master | Ссылки на несуществующие skills → phantom enforcer блокировка | НЕ переносить — оставить per-branch divergent |
| `git rebase` 2 233 commits на dev-master без merge стратегии | Часы, конфликты в каждом 10-м коммите, риск потерять работу при abort | `git merge origin/dev-master` (1 merge commit) — minutes, единая точка resolve |
| Force-push в origin/master без archive | Безвозвратная потеря 2 236 unique origin/master коммитов | Archive tag + branch (DONE 2026-05-19) ПЕРЕД любым force-push |

---

## §6 Decision matrix — когда что делать

### Сейчас (Phase 1 immediate cleanup) — **рекомендуется**

| Условие | Действие |
|---|---|
| PR #4 merged 2026-05-23 ✓ | Удалить `origin/migrate/pr-automation-stack` |
| Local master behind origin/dev-master | Fast-forward (no conflict, ff-only) |
| Tag/branch archive ещё нужны | Оставить ещё на 1-3 месяца как safety net |

**Время:** 15 минут. **Риск:** нулевой.

### Через 1-2 недели (Phase 2-3 reconciliation) — **opcional**

Если хотя бы одно верно:
- Появится reason работать с `origin/master` напрямую (внешний contributor PR)
- Tooling предполагает `master` как имя (не `dev-master`)
- Documentation/README ссылается на canonical branch для clarity
- Накопилось ≥2 будущих migration PR'ов кандидата → ROI reconciliation становится позитивным

**Время:** 2-5 часов. **Риск:** medium (cherry-pick конфликты). Mitigation: safety tag + archive ref'ы.

### Через 1-3 месяца (Phase 4-5 finalization) — **only if 2-3 done**

После reconciliation: PR #2 retarget, удалить dev-master, `AUTO_PR_BASE=master`, memory + docs sync.

**Время:** 30-60 минут. **Риск:** низкий.

### **Do-nothing валидно**

Текущее состояние (post Phase 1) полностью функционально. Reconciliation **желательная чистота, не блокер**. Можно держать workaround неопределённо долго.

---

## §7 Что заменяет / superseded
