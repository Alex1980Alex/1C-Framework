---
name: auto-git-save
description: "Автоматический git commit из хука: sync commit при пороге файлов, zombie prevention, adaptive timeout, task-enforcer блокировка. Триггеры: 'auto-git-save', 'автокоммит', 'sync commit', 'авто коммит', 'git save', 'порог коммита', 'commit threshold', 'auto commit hook', 'zombie task'. НЕ для ручного git — используй CLI. НЕ для настроек Claude Code — используй claude-code-settings."
---

# Auto Git Save — автоматический коммит из хука

## Обзор

Sync-commit система портированная из 1C-Enterprise_Framework v2.16. Хук `auto-git-save.py` отслеживает изменённые файлы, и при достижении порога (по умолчанию 1 файл = мгновенный коммит) автоматически выполняет `git add` + `git commit` прямо из хука. При неудаче коммита — создаёт mandatory pending задачу, которую `task-enforcer` проверяет при остановке.

---

## Полный цикл

```
Write/Edit файл → auto-git-save.py (PostToolUse)
                  │
                  ├─ should_track_file()? → НЕТ → выход
                  ├─ sync_pending_tasks_with_git()  ← zombie prevention
                  ├─ get_pause_status() — sentinel + порог? → ДА
                  │   └─ track + task only → [AUTO-GIT-SAVE PAUSED] Nm left
                  ├─ порог (1) достигнут? → ДА
                  │   └─ perform_sync_commit()
                  │       ├─ git add -- <файл>
                  │       ├─ git commit -m "chore: auto-save foo.py"
                  │       │   (basenames первых 3 файлов + `+N more`; см. §1)
                  │       └─ → [AUTO-GIT-SAVE OK] hash: abc1234
                  │
                  └─ commit failed?
                     └─ создать mandatory pending задачу
                        └─ task-enforcer заблокирует Stop
```

---

## Конфигурация

| Переменная | Default | Назначение |
|-----------|---------|-----------|
| `CLAUDE_COMMIT_THRESHOLD` | `1` | Файлов до автокоммита (1 = мгновенный коммит) |
| `CLAUDE_COMMIT_TIMEOUT_BASE` | `5` | Базовый timeout (сек) |
| `CLAUDE_COMMIT_TIMEOUT_PER_FILE` | `1` | Timeout за файл (сек) |
| `CLAUDE_COMMIT_COOLDOWN_BASE` | `2` | Cooldown после коммита (мин) |
| `CLAUDE_COMMIT_PAUSE_TTL` | `30` | TTL pause-sentinel'а по умолчанию (мин) |

Timeout вычисляется: `max(15, min(base + files * per_file, 120))`.

### Pause sentinel (временная пауза)

Когда нужно подготовить **структурированный коммит** (например, `fix(walker): ...`) и не хочется, чтобы auto-save опередил с `chore: auto-save X.py`:

```powershell
# Pause на 30 минут (default TTL)
New-Item -Path .claude/cache/auto-git-save.paused -ItemType File -Force

# Pause на N минут (-Encoding utf8 обязателен на PS 5.1 — без него Set-Content
# пишет UTF-16 LE BOM и хук падает в fallback на дефолтный TTL)
Set-Content .claude/cache/auto-git-save.paused -Value "60" -Encoding utf8

# Pause до ручного резюме
Set-Content .claude/cache/auto-git-save.paused -Value "forever" -Encoding utf8

# Resume вручную
Remove-Item .claude/cache/auto-git-save.paused
```

**Форматы содержимого sentinel'а:**
- пусто → TTL = `CLAUDE_COMMIT_PAUSE_TTL` минут от mtime файла (default 30)
- `<N>` (integer) → TTL = N минут от mtime
- `forever` / `manual` / `infinite` → без TTL, только ручной resume
- ISO datetime (`2026-05-13T15:30:00`) → явный момент истечения

**Поведение при паузе:**
- Файлы продолжают **трекаться** в metadata задачи
- `_ensure_task()` создаёт mandatory pending задачу — `task-enforcer` всё равно блокирует Stop, пока нет коммита
- Threshold-триггер **пропускается** → нет `chore: auto-save` коммита
- В systemMessage: `[AUTO-GIT-SAVE PAUSED] paused 30m left. Tracked: N file(s). ...`
- TTL истёк → sentinel **автоматически удаляется** при следующем вызове хука, поведение возвращается к обычному

**Два хука читают один sentinel (с 96b8f3a24):**
- `auto-git-save.py` (PostToolUse:Write|Edit|Bash, threshold-based, full TTL parsing)
- `posttooluse-auto-git-save.py` (PostToolUse:Write|Edit, 5s debounce + `--no-verify`, simple `os.path.isfile` check без TTL)

До commit `96b8f3a24` второй хук игнорировал sentinel и мог авто-коммитить 200+ файлов с шумным сообщением даже при `forever` паузе (инцидент `93fee7b53` 2026-05-13). Теперь оба гейтятся одинаково — пользователь переключает обе линии одним sentinel-файлом.

> **Регрессия + guard (2026-06-19):** вызов `_is_paused()` в `posttooluse-auto-git-save.py:execute()` был потерян при рефакторинге (функция осталась определена, но не вызывалась) → debounce-хук снова коммитил сквозь `forever` паузу, подхватывая чужие staged-файлы. Вызов восстановлен; защищён регресс-тестом [tests/unit/test_auto_save_pause.py](../../../tests/unit/test_auto_save_pause.py) (paused → `_git_commit` не зовётся; not-paused → зовётся, защита от over-gating). Третий хук `auto-git-save-prompt.py` гейтит через `_is_paused()` (стр. 266), `auto-git-save.py` — через `get_pause_status()` (стр. 678) — все три проверены.

---

## Механизмы

### 1. Sync Commit (порог) — split commit (2026-05-29)

При `file_count >= SYNC_COMMIT_THRESHOLD` `auto-git-save.py` делает **раздельные коммиты**, чтобы не смешивать чужой дрифт с правкой Claude под вводящим в заблуждение именем:

1. Берёт `get_uncommitted_files()` (все незакоммиченные в watched-путях; **gitlink-записи mode 160000 — submodule/embedded-repo pointer bumps — исключаются** через `get_gitlink_paths()`, чтобы автокоммит не подхватывал указатели подмодулей) и делит на два множества:
   - **tracked** = пересечение с файлами, которые хук реально отследил через Write/Edit (`modified_data["files"]`)
   - **drift** = всё остальное незакоммиченное (правки от других процессов/прошлых сессий)
2. `perform_sync_commit(tracked)` → `chore: auto-save foo.py, bar.py +N more` (basenames первых 3; `+N more` если >3 — единый формат всех auto-save хуков с 2026-05-14)
3. `perform_sync_commit(drift, prefix="chore: sweep unrelated drift")` → отдельный коммит для дрифта
4. `complete_task_by_hook()` — завершает pending задачу
5. systemMessage → `[AUTO-GIT-SAVE OK] ... N файл(ов) в M коммит(ах) [tracked:hash, drift:hash]`

**Множество коммитимых файлов не меняется** (tracked ∪ drift = все незакоммиченные) → дерево остаётся чистым, `git-commit-enforcer` доволен. Меняется только группировка: концерны разделены, сообщения честные.

`perform_sync_commit(files, timeout=None, prefix="chore: auto-save")` — `prefix` параметризован (Edit 2026-05-29). Fallback: если split не дал файлов (tracked уже закоммичен debounce-хуком, дрифта нет) — старое поведение (commit всех uncommitted).

При неудаче: создаёт mandatory задачу для ручного коммита. Частичный успех (один коммит прошёл, другой нет) → `[AUTO-GIT-SAVE OK] ... | не закоммичено: ...` + задача.

### 1.5 Amend-absorb (2026-06-12)

Все три коммит-пути (`auto-git-save.py`, `posttooluse-auto-git-save.py`,
`auto-git-save-prompt.py`) перед коммитом вызывают
`auto_save_core.get_amendable_head(project_root, prefix)`: если HEAD — **незапушенный**
auto-save коммит **того же prefix'а**, новый auto-save выполняет `git commit --amend`
с объединённым сообщением (`merge_for_message` — union файлов HEAD + новых, дедуп
по basename) вместо стопки `chore: auto-save` коммитов.

**Safety-гейты** (любой не пройден → обычный новый коммит):
1. subject HEAD начинается с того же prefix (auto-save / sweep-drift / auto-commit НЕ смешиваются — split-commit разделение концернов сохранено);
2. HEAD отсутствует на всех remote (`git branch -r --contains HEAD` пуст) — амендить запушенное нельзя, иначе divergence;
3. нет merge/rebase/cherry-pick in progress (маркеры `MERGE_HEAD`/`rebase-merge`/`rebase-apply`/`CHERRY_PICK_HEAD` в `.git/`).

**Поглощение осмысленным коммитом** (закрывает [[feedback-auto-git-save-preempt]]):
так как незапушенные auto-save'ы схлопываются в один HEAD-коммит, подготовленный
структурированный коммит поглощает его штатно: `git add <файлы>` →
`git commit --amend -m "feat(...): ..."`. Для хвоста из НЕСКОЛЬКИХ auto-save'ов
(legacy/смешанные prefix'ы): `git reset --soft <последний-запушенный>` → один
осмысленный коммит. Регресс: [tests/unit/test_auto_save_amend.py](../../../tests/unit/test_auto_save_amend.py) (7 тестов, throwaway-репо).

### 1.6 Ruff-format перед коммитом (2026-06-19)

Все три коммит-пути перед коммитом вызывают `auto_save_core.format_staged_python(project_root, files)`:
ruff-format'ит **staged .py** под `[tool.ruff] line-length` из pyproject (затем `git add` заново).
Зачем: auto-commit идёт `--no-verify` (или через кастомный `core.hooksPath`), в обход pre-commit,
поэтому неотформатированный .py раньше попадал в `master` и красил CI-джоб **Pre-commit Hooks**
(см. [[project-ci-precommit-red-autocommit-noverify]]). Теперь auto-commit'ы CI-clean.

- **Эквивалентность CI:** `ruff format --line-length N` проверенно совпадает с pre-commit ruff-format
  (голый `ruff format <file>` line-length не подхватывает — поэтому `--line-length` передаётся явно;
  значение читается из pyproject, fallback 100). Python берётся из `.venv` (`_python_exe`).
- **Best-effort:** любой сбой (нет ruff, timeout) проглатывается — коммит НЕ блокируется.
- **Exclude:** vendored/generated деревья (`tools/`, `external/`, `infra/`, `src/bsl/` …) пропускаются —
  зеркало top-level `exclude:` в `.pre-commit-config.yaml`.

### 1.7 Stale index.lock guard (2026-07-24)

Все три коммит-пути перед первой git-командой вызывают `auto_save_core.clear_stale_index_lock(project_root)`:
осиротевший `.git/index.lock` **старше 10 минут** (`STALE_INDEX_LOCK_MAX_AGE_SEC=600`) снимается, свежий
(живой git-процесс) не трогается. Живой инцидент: 0-байтовый лок 4.5-часовой давности от упавшего
auto-save блокировал ВСЕ коммиты main-репо до ручного `rm`.

- **Fail-safe в обе стороны:** исчезновение лока в окне getmtime→remove ловится `OSError`→False;
  будущий mtime (сдвиг часов) даёт отрицательный age → трактуется как свежий → не трогаем.
- Порог 600с на порядки больше любой легитимной git-операции; git при долгой записи обновляет
  mtime самого lock-файла — двойная защита от false-positive.
- Регресс: [tests/unit/test_auto_save_stale_lock.py](../../../tests/unit/test_auto_save_stale_lock.py)
  (4 теста: снят/нетронут/нет файла/кастомный порог). Roadmap: [260724 Б-2/В-3](../../../docs/roadmap/260724_ROADMAP_1C_TOOLING_RELIABILITY.md).

### 2. Zombie Task Prevention

`sync_pending_tasks_with_git()` вызывается на **каждый** PostToolUse. Проверяет:
- Извлекает файлы из metadata задачи
- Сверяет с `git status --porcelain`
- Если ВСЕ файлы задачи уже закоммичены → задача completed + `note: "Auto-synced"`

### 3. Validate Cache

`validate_cache()` при Bash "git commit":
- Проверяет каждый cached файл через `git diff --quiet`
- Если все закоммичены → `complete_task_by_hook()` + clear cache
- Детектирует коммиты сделанные вне хука (вручную, другой инструмент)

### 4. Adaptive Timeout/Cooldown

- **Timeout**: `15s` min — `120s` max, масштабируется по количеству файлов
- **Cooldown**: `2-5 мин` — меньше файлов = дольше cooldown (anti-spam)
  - 1 файл → 5 мин, 3 файла → 3 мин, 5+ файлов → 2 мин

### 5. Task Metadata

Файлы хранятся в metadata задачи (single source of truth):
```json
{
  "content": "Закоммитить незакоммиченные изменения - file1, file2",
  "metadata": {
    "files": ["src/main.py", "docs/README.md"],
    "first_change": "2026-02-21T14:00:00",
    "last_change": "2026-02-21T14:05:00"
  }
}
```

---

## 3-уровневая защита

| Уровень | Хук | Событие | Механизм |
|---------|-----|---------|----------|
| 1. Создание | `auto-git-save.py` | PostToolUse (Write\|Edit\|Bash) | Отслеживание файлов, создание задачи или автокоммит |
| 2. Напоминание | `todo-sync.py` | UserPromptSubmit | Синхронизация pending задач → TodoWrite (видимый список) |
| 3. Блокировка | `task-enforcer.py` | Stop | `sync_git_tasks_with_status()` + block если pending |

Дополнительно: `git-commit-enforcer.py` (Stop) блокирует если есть незакоммиченные изменения в watched paths (src/, docs/, tests/, .claude/skills/, .claude/hooks/).

### Bulk-removal guard (v2.17, 2026-04-26)

`perform_sync_commit()` отказывается коммитить, если staged-diff `.claude/settings.json` показывает net удаление ≥ 30 строк (added vs removed по `git diff --cached --numstat`). Профилактика регрессий типа коммита `910a3a1f` (2026-03-20), где автокоммит молча снёс 127 строк PostToolUse-секции. При срабатывании в логе: `GUARD: settings.json shrinks by N net lines — auto-commit blocked`.

---

## Отслеживаемые файлы

**Расширения**: `.py`, `.js`, `.ts`, `.tsx`, `.jsx`, `.bsl`, `.bat`, `.sh`, `.json`, `.yaml`, `.yml`, `.toml`, `.xml`, `.md`

**Пути**: `src/`, `docs/`, `tests/`, `.claude/skills/`, `.claude/hooks/`

**Игнорируются**: `cache/`, `temp/`, `__pycache__`, `node_modules`, `.git/`, `active-todos.json`, `hook-todos.json`

### Path-prefix exempt (2026-05-29) — `docs/roadmap/`

Помимо basename-фильтра `IGNORE_PATTERNS`, **все три** хука трио исключают **path-prefix** `docs/roadmap/`:
- `auto-git-save.py` — `IGNORE_PATH_PREFIXES` + `_is_path_ignored()`, проверяется в `should_track_file()` (threshold) И `get_uncommitted_files()` (commit-путь, включая drift-set split-commit).
- `posttooluse-auto-git-save.py` — `"docs/roadmap/"` в `SKIP_PATTERNS`.
- `auto-git-save-prompt.py` — `IGNORE_PATH_PREFIXES`, проверяется в `_should_track()` (**добавлено 2026-07-25**).

⚠ **Третий хук был пропущен при внедрении 2026-05-29** и полтора месяца уносил roadmap-правки
безымянным `chore: auto-commit` (живьём: E12 ретро 260725 — файл ретро уехал в авто-коммит вместе
с чужим сабжем, потребовался `reset --soft` для пересборки). Урок: у трио **три** точки фильтрации,
а не две — правка «в оба хука» оставляет дырку в UserPromptSubmit-пути. Регресс пинит инвариант для
всех трёх сразу: [`tests/unit/test_auto_save_roadmap_exempt.py`](../../../tests/unit/test_auto_save_roadmap_exempt.py)
(+ обратная сторона: обычный код по-прежнему автосейвится).

**Зачем:** §18 Progress Log дорожных карт должен получать осознанный коммит `docs(roadmap): progress log` (протокол §19), а не `chore: auto-save` preempt. Safety net — `git-commit-enforcer` (watches `docs/`) заблокирует Stop, если §18-правка осталась uncommitted → потери нет. См. [roadmap 260523 §19.3](../../../docs/roadmap/260523_ROADMAP_FULL_DEV_LIFECYCLE_ANALYSIS.md). При добавлении новых «manual-commit» директорий — дополнять **все три** точки.

---

## task_master.py API

| Функция | Назначение |
|---------|-----------|
| `add_task(session_id="")` | Создать pending задачу (session_id для cross-session tracking) |
| `complete_task(title, created_by)` | Завершить конкретную задачу по title |
| `complete_task_by_hook(hook_id)` | Завершить ВСЕ pending задачи хука |
| `get_pending_tasks(created_by)` | Получить pending задачи (опционально по creator) |
| `get_task_with_metadata(hook_id)` | Получить задачу с metadata |
| `update_task_metadata(hook_id, data)` | Обновить metadata задачи |
| `has_recent_completion(hook_id, minutes)` | Cooldown check |
| `cleanup_old_completed(max_age_hours, max_count)` | Удалить старые completed задачи |
| `auto_validate_git_tasks()` | Sync git tasks при старте |
| `auto_validate_code_verify_tasks(current_session_id)` | Cleanup stale code-verify tasks (session + age fallback) |
| `session_start_cleanup(current_session_id)` | Cleanup old + validate git + code-verify |

---

## Файлы

| Файл | Назначение |
|------|-----------|
| `.claude/hooks/auto-git-save.py` | Основной хук (PostToolUse: Write\|Edit\|Bash) |
| `.claude/hooks/task-enforcer.py` | Stop хук с `sync_git_tasks_with_status()` |
| `.claude/hooks/todo-sync.py` | UserPromptSubmit bridge → TodoWrite |
| `.claude/hooks/git-commit-enforcer.py` | Stop хук: блокирует при незакоммиченных изменениях в watched paths |
| `.claude/hooks/shared/task_master.py` | API задач (add, complete, metadata, cleanup) |
| `.claude/cache/hook-todos.json` | Хранилище задач (отдельно от TodoWrite) |
| `.claude/settings.json` | Регистрация хуков (timeout: 15s) |
