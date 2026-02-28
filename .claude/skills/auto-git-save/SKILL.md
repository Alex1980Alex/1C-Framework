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
                  ├─ порог (1) достигнут? → ВСЕГДА ДА
                  │   └─ perform_sync_commit()
                  │       ├─ git add -- <файл>
                  │       ├─ git commit -m "chore: auto-commit 1 file(s)"
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

Timeout вычисляется: `max(15, min(base + files * per_file, 120))`.

---

## Механизмы

### 1. Sync Commit (порог)

При `file_count >= SYNC_COMMIT_THRESHOLD`:
1. `git add --` для каждого отслеженного файла
2. `git commit -m "chore: auto-commit N file(s) changed"`
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
