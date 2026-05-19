# Roadmap 260519 — Master Branch Reconciliation

**Дата создания:** 2026-05-19
**Статус:** Phase 1 DONE, Phases 2–6 PENDING (требуется 2–5 часов сосредоточенной работы)
**Связанная память:** [project_disjoint_master_topology](file:///C:/Users/Tech.%20Boutique/.claude/projects/C--1--Framework/memory/project_disjoint_master_topology.md)
**Связанный PR:** [#2](https://github.com/Alex1980Alex/1C-Framework/pull/2) (открыт против `dev-master`; будет перенаправлен на `master` в Phase 5)

---

## §0 Проблема

В репозитории `Alex1980Alex/1C-Framework` на GitHub `origin/master` и локальный `master` — **две disjoint истории** (`git merge-base origin/master HEAD` возвращает пусто).

| Ветка | HEAD | Дата | Уникальных коммитов |
|---|---|---|---|
| `local master` | `b9cba8cb1` | 2026-04-18 | 2 677 (не в origin/master) |
| `origin/master` | `ae3a59534` | 2026-04-11 | 2 236 (не в local master) |

**Симптом:** `gh pr create --base master --head feat/...` отклоняется GitHub'ом с "no history in common". Из-за этого 2026-05-19 пришлось:
1. Push local master как `dev-master` (новая remote ветка)
2. Создать PR #2 против `dev-master` вместо `master`

**Причина:** local repo был initialized отдельно (`git init`), затем `git remote add origin` к существующему GitHub repo, который уже имел свою историю. Две независимые истории сосуществуют с момента ~2026-02-07.

**Цель reconciliation:** привести к одной canonical `master` ветке на GitHub, перенеся ценные коммиты из обоих источников. После — удалить `dev-master`, перенаправить PR #2 на `master`.

---

## §1 Стратегия: Local master побеждает

**Почему именно так** (а не merge / cherry-pick всего / force-push без аудита):

| Альтернатива | Почему отвергнута |
|---|---|
| `git merge --allow-unrelated-histories origin/master` | 12 695 файлов origin'а попадут в local tree → нарушение `.gitignore`, нечитаемый merge commit, невозможный PR review |
| Force-push local master сразу без аудита | 2236 коммитов origin/master уничтожены без backup → потеря legitimate work (vanessa-runner, GKSTCPLK-2256 тесты, 1C pipeline docs) |
| Cherry-pick всех 2236 origin/master коммитов | Недели работы; 184 из них — `chore: auto-save` шум, не имеющий ценности |
| Rebase feat-branch на origin/master | Уничтожает 2677 local master коммитов с current dev work |

**Выбранный путь:**
1. Архивировать origin/master через tag + branch (Phase 1) → нулевая потеря данных независимо от force-push
2. Аудит 2236 уникальных origin/master коммитов → отсев шума, выбор ~20–50 legitimate
3. Cherry-pick legitimate в local master
4. Force-push local master в origin/master
5. PR #2 base сменить с `dev-master` на `master`
6. Удалить `dev-master`

---

## §2 Phase 1 — Архивация origin/master ✅ DONE 2026-05-19

**Выполнено:**

```bash
# Local tag
git tag origin-master-archive-2026-05-19 origin/master

# Push tag to GitHub
git push origin origin-master-archive-2026-05-19

# Archive branch on GitHub (more visible than tag)
git push origin "origin/master:refs/heads/archive/master-pre-reconciliation-2026-05-19"
```

**Verification:**
- Tag SHA = `ae3a59534311ade93c07ba15283e280db53799c0`
- Branch `archive/master-pre-reconciliation-2026-05-19` SHA = same
- `gh api repos/.../branches` показывает 4 ветки: `archive/...`, `dev-master`, `feat/serena-audit-hybrid-refactor`, `master`

**Результат:** 2236 origin/master коммитов теперь доступны через 2 независимых ref'а на GitHub. Force-push в Phase 4 безопасен.

---

## §3 Phase 2 — Аудит unique origin/master commits

**Estimated:** 30–60 минут.

**Подготовка:**

```bash
# Экспорт всех 2236 уникальных коммитов
git log origin/master --not master --format='%H|%ai|%an|%s' > /tmp/origin-uniques.csv

# Подсчёт по типу commit message prefix
git log origin/master --not master --format='%s' | awk -F: '{print $1}' | sort | uniq -c | sort -rn > /tmp/prefix-stats.txt
```

**Категоризация (ожидаемая):**

| Категория | Эвристика | Действие |
|---|---|---|
| **Шум** | `chore: auto-save`, `chore: auto-commit` | skip — auto-git-save артефакты, содержимое уже в более новых коммитах |
| **Уже в local master** | `git log master --grep="<сходное сообщение>"` находит дубль | skip |
| **Уникальная legitimate работа** | `feat(`, `fix(`, `test(`, `docs(` без дубля в local master | **cherry-pick candidate** |

**Предварительные кандидаты** (по audit 2026-05-19, неполный список):

- `feat(vanessa-runner): add -OutputJson / -RunId params for /run-1c-tests integration`
- `test(gkstcplk2256): fix НнР Склад/ЯмаРазгрузки selection — search by name`
- `test(gkstcplk2256): improve ARM-FULL coverage — fill driver, supplier doc date`
- `test(gkstcplk2256): calibrate 06_arm_workflow — full 8-step ARM chain passes`
- `docs: add 17.5 — 1C Pipeline commands and VA BDD recent changes`
- `fix: remove duplicate .gitignore entry from SKIP_PATTERNS in docs-change-enforcer`
- `chore: formalize bsl-debug-server as submodule, point to Alex1980Alex fork`
- `chore: bump bsl-debug-server submodule (add Python MCP debug server)`
- `chore(submodule): bump bsl-debug-server`
- `fix(va-bdd):` × 2
- `docs(memory-first-hook):` × 1
- `spec(mcp-toolkit):` × 1
- `docs:` × 3

**Output Phase 2:** `/tmp/selected-hashes.txt` — отсортированный список ~20–50 hashes для cherry-pick в правильном хронологическом порядке.

---

## §4 Phase 3 — Cherry-pick selected commits

**Estimated:** 1–3 часа (зависит от конфликтов).

```bash
git checkout master
git tag pre-cherry-pick-master-2026-XX-XX HEAD  # safety тэг перед началом

for hash in $(cat /tmp/selected-hashes.txt); do
    echo "=== Cherry-picking $hash ==="
    git cherry-pick "$hash" || {
        # CONFLICT — resolve manually
        echo "CONFLICT — resolve files, then:"
        echo "  git add <resolved files>"
        echo "  git cherry-pick --continue"
        # ... continue после resolution
        break  # выйти из цикла для ручного resolve
    }
done
```

**Ожидаемые конфликты:**

| Файл | Природа конфликта | Resolution |
|---|---|---|
| `vanessa-runner` related (`tools/vanessa/run-bdd.ps1`) | local master имеет более новую версию | keep local + cherry-pick добавляет `-OutputJson`/`-RunId` параметры поверх |
| `.claude/skills/*/SKILL.md` | independent edits | manual merge: combined keywords + best of both descriptions |
| `code-skill-patterns.json` | independent regex/skill mappings | merge entries (union of both lists) |
| `docs-change-enforcer.py` SKIP_PATTERNS/CODE_TO_DOMAIN | parallel modifications | merge entries — local master уже имеет много overrides; добавить недостающие из origin |
| `CLAUDE.md` | overlapping enforcer notes | merge content chronologically |

**Тест после каждой группы:**
- `git status` — no leftover uncommitted
- `python -m py_compile <touched .py files>` — no syntax errors
- Spot-check 2-3 cherry-picked коммитов через `git show` что diff applied правильно

**Safety net:** если что-то пошло не так — `git reset --hard pre-cherry-pick-master-2026-XX-XX` возвращает к baseline.

---

## §5 Phase 4 — Force-push canonical master

**Estimated:** 5 минут.

**Pre-checks:**

```bash
# Подтвердить что archive есть на GitHub
gh api repos/Alex1980Alex/1C-Framework/branches/archive/master-pre-reconciliation-2026-05-19 --jq '.commit.sha'
# Должно вернуть ae3a59534311ade93c07ba15283e280db53799c0

# Проверить local master содержит cherry-picked commits
git log master --since=2026-04-11 --grep="vanessa-runner\|gkstcplk2256\|bsl-debug-server" --oneline

# Verify no uncommitted changes
git status --short
```

**Push:**

```bash
# --force-with-lease защищает от race condition если кто-то pushed в origin/master
# между Phase 1 и Phase 4
git push --force-with-lease=master:$(git rev-parse origin/master) origin master:master
```

**Verify on GitHub:**

```powershell
& "C:\Program Files\GitHub CLI\gh.exe" api repos/Alex1980Alex/1C-Framework/branches/master --jq ".commit.sha"
# Должно вернуть current local master HEAD (не ae3a59534)
```

**Rollback (если что-то пошло не так):**

```bash
# Вернуть origin/master к archive snapshot
git push --force origin archive/master-pre-reconciliation-2026-05-19:master
```

---

## §6 Phase 5 — Cleanup

**Estimated:** 10 минут.

```bash
# Переключить PR #2 на canonical master
gh pr edit 2 --base master

# Удалить dev-master (больше не нужен)
git push origin :dev-master

# (Опционально) удалить local dev-master ref
git branch -d dev-master  # если local есть
```

**Update mypy-baseline под новый master:**

```bash
python -m mypy_baseline sync
git add mypy-baseline.txt
git commit -m "chore(mypy): re-sync baseline after master reconciliation"
git push origin master
```

**Update memory:** edit [`project_disjoint_master_topology.md`](file:///C:/Users/Tech.%20Boutique/.claude/projects/C--1--Framework/memory/project_disjoint_master_topology.md) — пометить как RESOLVED с датой:

```markdown
**Status (2026-XX-XX): RESOLVED**

После master reconciliation per [roadmap 260519](docs/roadmap/260519_ROADMAP_MASTER_RECONCILIATION.md):
- Local master force-pushed в origin/master (Phase 4)
- Архив origin/master сохранён в tag `origin-master-archive-2026-05-19` + branch `archive/master-pre-reconciliation-2026-05-19`
- PR #2 теперь базируется на master
- dev-master удалён
```

**Update CLAUDE.md** — добавить заметку про topology cleanup в существующую секцию enforcer overrides.

---

## §7 Phase 6 — Verify CI

**Estimated:** 15–30 минут (зависит от CI run time).

```bash
# Запустить CI на новом master напрямую (если есть workflow_dispatch)
gh workflow run --ref master <workflow-name>

# Или дождаться auto-trigger от force-push
gh run watch
```

**Expected outcomes:**
- mypy ratchet gate: pass (baseline пересохранён в Phase 5)
- ruff lint/format: pass (был pass на pre-commit)
- gitleaks: pass
- Pre-commit hooks локально: должны pass на новом master HEAD

**PR #2 CI:** автоматически запустится после `gh pr edit --base master` (rebase detection).

**Если CI красный:**
1. Проверить mypy-baseline.txt — может нужно пересохранить
2. Проверить новые файлы из origin/master коммитов — могут иметь pre-existing issues
3. В крайнем случае откат к archive branch (см. §5 Rollback)

---

## §8 Risk Register

| Риск | Mitigation | Phase |
|---|---|---|
| Force-push уничтожает данные | Phase 1 archive tag + branch (DONE) | 1, 4 |
| Race condition при force-push (concurrent push) | `--force-with-lease=master:<expected-sha>` | 4 |
| Cherry-pick конфликты делают tree сломанным | `pre-cherry-pick` safety tag перед началом + ручной resolve | 3 |
| CI baseline сломается | Phase 5 `mypy-baseline sync` + commit | 5 |
| Active работа на feat-branch ломается | Делать когда нет concurrent work; PR #2 rebase'ится автоматически | 5 |
| Cherry-pick переносит файлы которые в local .gitignore | git cherry-pick уважает .gitignore receiver branch'а — проблемы быть не должно | 3 |
| После force-push кому-то нужно `git pull --rebase` для своих local branches | Один разработчик в репо (`Alex1980Alex`) — минимизирует риск | 4 |

---

## §9 Estimated Total: 2–5 часов

Распределение:
- Phase 1: 15 мин (DONE)
- Phase 2: 30–60 мин (audit)
- Phase 3: 1–3 часа (cherry-pick с конфликтами)
- Phase 4: 5 мин
- Phase 5: 10 мин
- Phase 6: 15–30 мин (CI watch)

**Когда делать:**
- Когда есть 2–5 часов **без переключений** (cherry-pick требует фокуса)
- Когда не идёт активная разработка на `feat/serena-audit-hybrid-refactor` (rebase станет painful)
- Не пятница вечером
- После любого pending PR review на dev-master чтобы избежать переезда review state

---

## §10 Когда **не** делать reconciliation

Если ни одно из ниже не верно — отложить:

- [ ] Есть 2-5 часов сосредоточенной работы
- [ ] PR #2 не в активном review (или ОК что base сменится)
- [ ] Все необходимые backups/tags подтверждены на GitHub
- [ ] mypy-baseline сохранён локально
- [ ] Не идёт concurrent работа в других сессиях Claude Code на этом репо

Без всех галочек — оставить как есть (dev-master + PR #2 work just fine).

---

## §11 Альтернативная "do nothing" стратегия

Текущее состояние (после Phase 1) **полностью функционально** для разработки:

- `feat/...` ветки → PR против `dev-master`
- `dev-master` — canonical для locally-developed feature work
- `master` — legacy snapshot, не используется для активной разработки
- `archive/master-pre-reconciliation-2026-05-19` — backup исходного origin/master

Этот режим можно держать **бесконечно**. Reconciliation — желаемая чистота, не блокер. Если другие задачи приоритетнее — Phase 2–6 могут ждать.

---

## §12 Связанные артефакты

- [PR #2](https://github.com/Alex1980Alex/1C-Framework/pull/2) — текущий PR, перейдёт на master в Phase 5
- Tag `pre-squash-backup-2026-05-19` (local) — backup feat-branch перед squash attempt
- Tag `origin-master-archive-2026-05-19` (GitHub) — archive origin/master
- Branch `archive/master-pre-reconciliation-2026-05-19` (GitHub) — same archive, более visible
- Memory: [project_disjoint_master_topology.md](file:///C:/Users/Tech.%20Boutique/.claude/projects/C--1--Framework/memory/project_disjoint_master_topology.md)
