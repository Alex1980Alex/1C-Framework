# Roadmap 260522 — Миграция PR-automation стека на `dev-master`

> **Статус:** **SUPERSEDED 2026-05-23** — миграция выполнена через **PR #4 merged 2026-05-23 03:13 UTC** (merge commit `25ab2de39`). Этот roadmap сохранён как historical reference для discovery+inventory методологии. Generalized pattern → [260523 §4 Pattern B](260523_ROADMAP_UNIFIED_BRANCH_TOPOLOGY.md). Lessons из round-6/7 cleanup arc → [260523 §5 Anti-patterns](260523_ROADMAP_UNIFIED_BRANCH_TOPOLOGY.md).
> **Дата discovery:** 2026-05-22 evening.
> **Дата implementation:** 2026-05-22 night → 2026-05-23 morning (rounds 2-7).
> **Источник:** артефакт сессии task#1 (P3.2 gap-close).

## 0. TL;DR

PR-automation подсистема (18 P-items из 40.4) живёт **только** на `feat/serena-audit-hybrid-refactor`. На `dev-master` её нет вообще — даже `.claude/hooks/post-task-push-pr.py` отсутствует. Cherry-pick отдельных коммитов на `dev-master` ломается о «patch файла которого нет» (см. [PR #3](https://github.com/Alex1980Alex/1C-Framework/pull/3) demo).

Чтобы доставить P3.2 (и весь стек) чистой PR-кой, нужна **explicit миграция**: 4 semantic commit'а + порт docs + регистрация в settings.json. **Скрытый риск:** `base/protocol.py` на feat-branch новее (hook_event_name detection, transcript_path fallback, modern type hints) — без миграции protocol.py PR-automation хук **молча misclassify-ит события** и никогда не сработает.

Трудозатраты: **1.5–4 часа** одной сессии. Узкое место — conflict resolution в `.claude/settings.json` (+5 KB hook chain'ов) и `CLAUDE.md`.

## 1. Topology

| Метрика | Значение |
|---|---|
| `merge-base origin/dev-master HEAD` | `b9cba8cb1e2…` (2026-04-18) |
| `feat` ahead of merge-base | **2 231 commits** |
| `origin/dev-master` ahead | 0 commits |
| Следствие | `dev-master ≡ merge-base`, целевая ветка не двигалась |

## 2. Inventory

### 2.1 Source code (10 файлов, все MISSING на dev-master)

| Файл | Размер | Назначение |
|---|---|---|
| `.claude/hooks/post-task-push-pr.py` | 20 599 B | Главный хук PostToolUse:TaskUpdate, оркестратор P0-P3 |
| `.claude/hooks/shared/pr_helpers.py` | 18 324 B | git/gh primitives + `cherry_pick_range_to_branch` (P3.2) |
| `.claude/hooks/shared/pr_notifier.py` | 4 341 B | SMTP уведомления |
| `.claude/hooks/shared/slash_detect.py` | ~ | Детектор `/cmd` |
| `.claude/hooks/shared/run_context.py` | ~ | Per-run UUID storage |
| `scripts/pr_check_post_merge.py` | 10 816 B | P3.4 post-merge CI + auto-revert |
| `scripts/pr_automation_dashboard.py` | 7 796 B | P1.5 дашборд |
| `scripts/cleanup_orphan_branches.py` | 4 436 B | P2.4 orphan cleanup |
| `src/api/routes/github_webhooks.py` | 7 002 B | P3.1 webhook receiver (FastAPI) |
| `.mergify.yml` | 2 316 B | P3.3 Mergify template |

**Итого**: ~76 KB кода + 2 KB config.

### 2.2 Документация (5 файлов MISSING)

`docs/framework documentation/40_PR_AUTOMATION/{40.1_Обзор, 40.2_Детальная_реализация, 40.3_Best_practices, 40.4_Дорожная_карта, 40.5_Pipeline_Workflow}.md`

### 2.3 Файлы dev-master с правками

| Файл | Дельта | Что добавить |
|---|---|---|
| `.claude/settings.json` | +5 KB (11 893 → 16 843) | Регистрация `post-task-push-pr.py` PostToolUse:TaskUpdate `timeout: 1320` + env `AUTO_PR_*` |
| `.claude/hooks/base/protocol.py` | **DIVERGENT** (§3.1) | Modern API (hook_event_name detection, transcript_path fallback) |
| `CLAUDE.md` | +1 раздел | Секция `post-task-push-pr.py P0-P3 batch` + ссылка на 40.4 |

### 2.4 Что УЖЕ есть на dev-master

`.claude/hooks/shared/` содержит 15 модулей: `core_paths`, `invocation_logger`, `hook_lock`, `db_writer`, `circuit_breaker`, `fuzzy_match`, `latency_tracker`, `otel_exporter`, `ralph_state`, `semantic_search`, `session_state`, `task_master`, `tfidf_scorer`, `trust_scorer` + `code-skill-patterns.json`. PR-automation от них **не зависит**.

`base/` пакет экспортирует `BaseHook, HookInput, HookOutput` — структурно совместим. НО `protocol.py` divergent (см. §3.1).

`src/api/` существует — `routes/github_webhooks.py` добавляется без создания пакета.

## 3. Hidden risks

### 3.1 `base/protocol.py` divergence ⚠️ КРИТИЧНО

Diff `origin/dev-master..HEAD`:

```diff
- from typing import Any, Dict, Optional
+ from typing import Any

  class HookInput:
-     def __init__(self, raw: Dict[str, Any]):
+     def __init__(self, raw: dict[str, Any]):
-     self.transcript = raw.get("transcript", "")
+     self.transcript = raw.get("transcript_path", raw.get("transcript", ""))

  @property
  def detected_event(self) -> str:
+     # Authoritative: hook_event_name from payload (Claude Code 2.x).
```

**Без миграции protocol.py:** `post-task-push-pr.py:193` делает `if inp.detected_event != "PostToolUse": return None`. На dev-master старый detected_event возвращает `"Unknown"` для современных событий → хук всегда no-op'ит, ошибки в логах нет.

**Решение:** портировать `protocol.py` (и при необходимости `base.py` — blob `36103e6` feat vs `2e579b5` dev).

### 3.2 settings.json conflict resolution

dev-master `.claude/settings.json` = 11 893 B, feat = 16 843 B. Разница не только в `post-task-push-pr` — за 2 231 коммит туда добавили: `opsx-apply-postvalidate`, `openspec-change-coverage`, `analyze-1c-task-preflight`, `implement-1c-task-preflight`, `implement-1c-task-smoke-stop-alert`, `mcp-invocation-logger`, `slash-command-tracker`, `session-mypy-banner` и т.д.

**Решение:** НЕ копировать settings.json целиком (затянет 50+ хуков). Surgical patch: добавить ТОЛЬКО PostToolUse:TaskUpdate matcher + env-блок `AUTO_PR_*`.

### 3.3 `slash-command-tracker.py` co-dependency

`post-task-push-pr.py` напрямую не зависит от `slash-command-tracker`, но PR-automation метрики (`run_id` в state, корреляция Pre/Post tool calls) питаются из `data/.current-runs.json` которое наполняет `slash-command-tracker`. Без него `run_id` пустой — не блокирующий, но diagnostics беднее.

**Решение:** opt-in, можно отложить.

### 3.4 `code-skill-patterns.json` ругань

На feat patterns.json ссылается на skills которых нет на dev-master (например `openspec-explore`). Если протащить — phantom-блокировка.

**Решение:** НЕ трогать `code-skill-patterns.json` при миграции.

### 3.5 Pre-commit baseline

На feat 101 pre-existing ruff/json lint errors. На dev-master ситуация неизвестна. Запуск `pre-commit run --all-files` обязателен ПЕРЕД любым commit'ом — иначе `AUTO_PR_NO_TESTS=1` bypass придётся таскать дальше.

## 4. Commit archaeology

Semantic commits на feat-branch (4 шт):

| SHA | Date | Subject |
|---|---|---|
| `50dcd87ad` | 2026-05-22 19:49 | `fix(pr-automation): force UTF-8 + replace-errors for pre-push subprocess` |
| `f0be1a354` | 2026-05-22 19:43 | `feat(pr-automation): implement cherry_pick_range_to_branch for P3.2` |
| `7b50ab65e` | 2026-05-22 | `feat(pr-automation): P3 batch final integration` |
| `8c6538fc3` | 2026-05-22 | `feat(pr-automation): land P0+P1+P2 batch — dashboard, cleanup, doc` |

Остальные 16 коммитов — `chore: auto-save *.py` (auto-git-save hook) + `chore: rollup auto-formatter drift` (ruff).

**Решение:** squash 4 semantic коммита в один `feat(pr-automation): land P0-P3 batch on dev-master` — чище, чем тащить 20 коммитов с грязной историей.

## 5. План миграции

### Phase A — Подготовка (~15 мин)

1. `git fetch origin --prune`
2. `git switch -c migrate/pr-automation-stack origin/dev-master`
3. `pre-commit run --all-files` на чистом dev-master — зафиксировать baseline
4. Smoke существующих PostToolUse-хуков (synthetic payload)

### Phase B — Protocol modernize (~20 мин)

5. `git checkout feat/serena-audit-hybrid-refactor -- .claude/hooks/base/protocol.py`
6. Smoke existing хуков dev-master чтобы не сломались
7. Если `base.py` тоже divergent (blob `36103e6` vs `2e579b5`) — портировать аналогично

### Phase C — Source code (~30 мин)

8. Скопировать 10 файлов из §2.1 с feat-ветки:
   ```bash
   git checkout feat/serena-audit-hybrid-refactor -- \
     .claude/hooks/post-task-push-pr.py \
     .claude/hooks/shared/pr_helpers.py \
     .claude/hooks/shared/pr_notifier.py \
     .claude/hooks/shared/slash_detect.py \
     .claude/hooks/shared/run_context.py \
     scripts/pr_check_post_merge.py \
     scripts/pr_automation_dashboard.py \
     scripts/cleanup_orphan_branches.py \
     src/api/routes/github_webhooks.py \
     .mergify.yml
   ```
9. Verify imports: `python -c "import sys; sys.path.insert(0,'.claude/hooks'); from shared import pr_helpers as pr; print('ok')"`

### Phase D — settings.json surgical patch (~20 мин)

10. **НЕ копировать settings.json целиком.**
11. Открыть dev-master `.claude/settings.json`, найти `"PostToolUse"`.
12. Добавить matcher:
    ```json
    {
      "matcher": "TaskUpdate",
      "hooks": [{
        "type": "command",
        "command": "C:/1С-Framework/.venv/Scripts/python.exe C:/1С-Framework/.claude/hooks/post-task-push-pr.py",
        "timeout": 1320
      }]
    }
    ```
13. Добавить env-блок (default-off):
    ```json
    "env": {
      "AUTO_PR_ENABLED": "0",
      "AUTO_PR_BASE": "dev-master",
      "AUTO_PR_MIN_COMMITS": "3"
    }
    ```
14. Validate: `python -c "import json; json.load(open('.claude/settings.json',encoding='utf-8'))"` → OK

### Phase E — Docs (~20 мин)

15. `git checkout feat/serena-audit-hybrid-refactor -- "docs/framework documentation/40_PR_AUTOMATION/"`
16. В `CLAUDE.md` добавить раздел про hook (~3-5 строк по образцу feat-ветки)
17. Опционально: stub-ы для dead-link'ов из 40.4 если они есть

### Phase F — Smoke + commit (~30 мин)

18. Smoke:
    ```bash
    python -m py_compile .claude/hooks/post-task-push-pr.py .claude/hooks/shared/pr_helpers.py
    echo '{"hook_event_name":"PostToolUse","tool_name":"TaskUpdate","tool_input":{"taskId":"99","status":"in_progress"}}' | python .claude/hooks/post-task-push-pr.py
    ```
19. Squash commit:
    ```bash
    git add -A
    git commit -m "feat(pr-automation): land P0-P3 batch on dev-master"
    ```
20. `gh pr create --base dev-master --head migrate/pr-automation-stack`

### Phase G — Live validation (~30 мин)

21. Включить `AUTO_PR_ENABLED=1 AUTO_PR_CHERRY_PICK=1 AUTO_PR_MIN_COMMITS=1 AUTO_PR_BASE=dev-master AUTO_PR_DRY_RUN=1` в settings.local.json
22. На новой ветке создать task → trivial change + commit → TaskUpdate(completed)
23. Verify: hook output `mode=cherry-pick`, `1 commit(s) onto origin/dev-master`
24. Если зелёный — снимаем DRY_RUN, делаем реальную PR-ку

## 6. Альтернативы (rejected)

| Подход | Почему отклонено |
|---|---|
| Merge feat-branch целиком | Тащит 2 231 commit, 13.8K файлов — не review-able |
| Cherry-pick семантических коммитов | Конфликтует (файлы не существуют на dev-master) — продемонстрировано PR #3 |
| Подождать основной PR feat-ветки | Срок неопределён, P3.2 gap-close сидит «в ящике» |
| Cherry-pick на отдельную ветку из feat + merge | Не решает protocol.py divergence + тащит auto-save шум |

## 7. Open questions для оператора

- [ ] Нужен ли `slash-command-tracker.py` co-port (Phase C8)? Если да — расширяет scope до ~12 файлов.
- [ ] `base.py` тоже divergent — нужен ли port? Зависит от того что в нём поменялось.
- [ ] `AUTO_PR_BASE` после миграции — `dev-master` или `master`? Memory `project_disjoint_master_topology` намекает на `dev-master`.
- [ ] Pre-commit baseline на dev-master — green или 101+ errors как на feat? Если красный — миграция блокирована до cleanup.

## 8. Definition of Done

- [ ] PR против `origin/dev-master` с заголовком `feat(pr-automation): land P0-P3 batch on dev-master`
- [ ] CI зелёный (или явный waiver на pre-existing baseline)
- [ ] Synthetic smoke на `migrate/pr-automation-stack` показал `mode=cherry-pick` + `1 commit(s) onto origin/dev-master`
- [ ] `40.4_Дорожная_карта.md` обновлён — раздел «Миграция на dev-master» DONE
- [ ] PR замержен; `feat/serena-audit-hybrid-refactor` rebased на новый dev-master

## Атрибуция discovery

| Источник | Данные |
|---|---|
| `git ls-tree origin/dev-master` | inventory dev-master |
| `git merge-base origin/dev-master HEAD` | topology |
| `git log --reverse --oneline -- <files>` | commit archaeology |
| `git ls-tree` blob hashes | protocol.py divergence detection |
| Session task#1 PR #3 outcome | head-ref fallback evidence |
| [40.4 §«Доделки 2026-05-22 evening v3»](../framework%20documentation/40_PR_AUTOMATION/40.4_Дорожная_карта.md) | live-test transcript |
