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

---

## Механизмы

### 1. Sync Commit (порог)

При `file_count >= SYNC_COMMIT_THRESHOLD`:
1. `git add --` для каждого отслеженного файла
2. `git commit -m "chore: auto-save foo.py, bar.py, baz.py +N more"` (basenames первых 3 файлов; `+N more` если файлов > 3 — единый формат всех трёх auto-save хуков с 2026-05-14, до этого `auto-git-save.py` и `auto-git-save-prompt.py` использовали generic `N file(s)` и теряли контекст изменения)
3. `complete_task_by_hook()` — завершает pending задачу
4. systemMessage → `[AUTO-GIT-SAVE OK]`

При неудаче: создаёт mandatory задачу для ручного коммита.

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
