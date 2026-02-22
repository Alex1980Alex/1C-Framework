---
name: git-porcelain-parsing
description: "Парсинг git status --porcelain в Python: формат XY, правильное извлечение путей, обработка staged/unstaged, кавычек, юникода, core.quotepath=false для кириллицы. Триггеры: 'git status parsing', 'porcelain', 'парсинг git status', 'line[3:]', 'git status python', 'извлечь путь из git status', 'staged files python', 'кириллица git', 'quotepath', 'core.quotepath'. НЕ для git команд — используй CLI. НЕ для коммитов — используй auto-git-save."
---

# Git Porcelain Parsing — парсинг git status --porcelain

## Обзор

Правильный парсинг вывода `git status --porcelain` в Python. Два исторических бага в проекте:

1. **Баг `line[3:]`** — потеря ведущей точки в `.claude/` путях (4 файла)
2. **Баг кириллических путей** — octal escapes `\320\236` ломаются через `.replace("\\", "/")` → `/320/236` (6 файлов, 9 вхождений)

---

## КРИТИЧНО: core.quotepath=false

### Проблема

Git по умолчанию экранирует не-ASCII символы (кириллица, CJK, эмодзи) в octal escapes:

```bash
# git status --porcelain (default core.quotepath=true)
 M "docs/\320\236\320\261\320\267\320\276\321\200.md"
?? "docs/LSP-\320\260\320\275\320\260\320\273\320\270\320\267.md"
```

Python-хук делает `.replace("\\", "/")` для нормализации Windows-путей, но это **уничтожает octal escapes**:

```python
# В Python строка содержит ЛИТЕРАЛЬНЫЕ символы \ 3 2 0
path = line[2:].lstrip().strip('"')
# path = 'docs/\320\236\320\261\320\267\320\276\321\200.md'

path = path.replace("\\", "/")
# path = 'docs//320/236/320/261/320/267/320/276/321/200.md'  ← МУСОР!

# git add с таким путём МОЛЧА ПАДАЕТ (returncode != 0)
```

### Инцидент (2026-02-22)

3 файла LSP-документации с кириллическими именами (`Обзор.md`, `Протокол языкового сервера.md`, `LSP-анализ-для-PDF-Framework.md`) не были автокоммичены. Причина:
- PostToolUse хук (auto-git-save.py) не сработал — баг #6305
- UserPromptSubmit хук (auto-git-save-prompt.py) сработал, но `_get_uncommitted_tracked_files()` вернул пустой список — пути были сломаны octal escaping
- Stop хук (git-commit-enforcer.py) не был достигнут — сессия завершилась по лимиту контекста

### Решение

Добавлять `-c core.quotepath=false` к КАЖДОМУ вызову `git status`:

```python
# ПРАВИЛЬНО — per-command флаг, не меняет глобальную конфигурацию
result = subprocess.run(
    ["git", "-c", "core.quotepath=false", "status", "--porcelain"],
    capture_output=True, text=True, timeout=5,
    cwd=str(PROJECT_ROOT),
)
```

С `core.quotepath=false` git выдаёт сырые UTF-8 пути:

```bash
# git -c core.quotepath=false status --porcelain
 M docs/Обзор.md
?? docs/LSP-анализ-для-PDF-Framework.md
```

Теперь `.replace("\\", "/")` безвреден — в путях нет backslash-последовательностей.

### Почему `-c` а не `git config`

| Подход | Плюсы | Минусы |
|--------|-------|--------|
| `git -c core.quotepath=false` | Безопасно, per-command, не требует настройки | Нужно в каждом вызове |
| `git config core.quotepath false` | Один раз | Меняет настройки репо/пользователя, влияет на другие инструменты |

**Правило**: всегда `-c` в хуках — они не должны менять конфигурацию пользователя.

---

## Формат git status --porcelain

```
XY PATH
││ │
││ └─ Путь к файлу (начинается с позиции 3, но пробел на позиции 2)
│└── Статус рабочего дерева (working tree), позиция 1
└─── Статус индекса (staged), позиция 0
```

### Примеры вывода

```
 M src/api/app.py          ← modified в working tree (не staged)
M  .claude/hooks/hook.py   ← staged (добавлен в индекс)
MM src/config.py            ← staged + ещё изменён в working tree
A  new_file.py              ← новый файл, staged
?? untracked.txt            ← не отслеживается
D  deleted.py               ← удалён, staged
R  old.py -> new.py         ← переименован
"M  path with spaces.py"   ← путь в кавычках (пробелы/юникод)
```

---

## Баг line[3:]

### Проблема

```python
# НЕПРАВИЛЬНО — line[3:]
filepath = line[3:].strip()

# Для строки "M  .claude/hooks/hook.py":
#   line[3:] = "claude/hooks/hook.py"  ← потеряна точка!
#
# Потом: ".claude/hooks/".startswith("claude/hooks/") → False
# Файл не проходит фильтр WATCHED_PATHS
```

### Корень проблемы

Формат `XY PATH`:
- Позиция 0: статус индекса
- Позиция 1: статус working tree
- Позиция 2: пробел (разделитель)
- Позиция 3+: путь

Для staged файлов (`M  path`): `M` на позиции 0, два пробела на 1-2, путь с позиции 3 — `line[3:]` работает.

Для unstaged файлов (` M path`): пробел на позиции 0, `M` на позиции 1, пробел на 2, путь с позиции 3 — `line[3:]` тоже работает.

**НО** для staged файлов с путём начинающимся на точку (`M  .claude/`): `line[3:]` = `.claude/` — ОК, казалось бы. Проблема в том что git иногда выводит `M .claude/hooks/hook.py` (один пробел после M, не два), и тогда `line[3:]` = `laude/hooks/hook.py`.

### Правильное решение

```python
# ПРАВИЛЬНО — line[2:].lstrip()
filepath = line[2:].lstrip().strip('"').replace("\\", "/")
```

Почему это работает:
- `line[2:]` — берём всё после XY (два символа статуса)
- `.lstrip()` — убираем ведущие пробелы (1 или более)
- `.strip('"')` — убираем кавычки (для путей с пробелами/юникодом)
- `.replace("\\", "/")` — нормализуем разделители (Windows)

---

## Полный шаблон парсинга

```python
import subprocess
from pathlib import Path

def get_changed_files(cwd: str = ".") -> list[dict]:
    """Парсинг git status --porcelain с правильным извлечением путей.

    ВАЖНО: core.quotepath=false для корректной работы с кириллицей.

    Returns:
        list of {"path": str, "index": str, "work": str, "is_untracked": bool}
    """
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", "status", "--porcelain"],
        capture_output=True, text=True, timeout=5,
        cwd=cwd,
    )
    if result.returncode != 0:
        return []

    files = []
    for line in result.stdout.strip().splitlines():
        if not line or len(line) < 2:
            continue

        index_status = line[0]   # позиция 0: staged
        work_status = line[1]    # позиция 1: working tree

        # ПРАВИЛЬНЫЙ парсинг пути:
        # 1. line[2:].lstrip() — пропускаем XY + пробелы (не line[3:]!)
        # 2. .strip('"') — убираем кавычки (пути с пробелами)
        # 3. .replace("\\", "/") — безопасно с core.quotepath=false
        filepath = line[2:].lstrip().strip('"').replace("\\", "/")

        if not filepath:
            continue

        files.append({
            "path": filepath,
            "index": index_status,
            "work": work_status,
            "is_untracked": index_status == "?" and work_status == "?",
        })

    return files
```

---

## Таблица статусов

| XY | Значение | index | work |
|----|----------|-------|------|
| `M ` | Staged (изменён, добавлен в индекс) | M | пробел |
| ` M` | Modified в working tree (не staged) | пробел | M |
| `MM` | Staged + ещё изменён после staging | M | M |
| `A ` | Новый файл, staged | A | пробел |
| `D ` | Удалён, staged | D | пробел |
| ` D` | Удалён в working tree | пробел | D |
| `R ` | Переименован, staged | R | пробел |
| `??` | Не отслеживается (untracked) | ? | ? |
| `!!` | Игнорируется (.gitignore) | ! | ! |

---

## Фильтрация по путям

```python
WATCHED_PATHS = ["src/", "docs/", ".claude/hooks/", ".claude/skills/"]

SKIP_PATTERNS = ["/cache/", "/__pycache__/", "node_modules/"]

def should_track(filepath: str) -> bool:
    """Проверка: файл в отслеживаемых путях и не в исключениях."""
    fp = filepath.replace("\\", "/").lower()

    # Пропустить исключения
    if any(skip in fp for skip in SKIP_PATTERNS):
        return False

    # Проверить отслеживаемые пути
    return any(fp.startswith(p) for p in WATCHED_PATHS)
```

---

## Чеклист: новый хук с git status

При создании любого хука, использующего `git status --porcelain`:

- [ ] Используется `["git", "-c", "core.quotepath=false", "status", "--porcelain"]`
- [ ] Путь извлекается через `line[2:].lstrip()` (НЕ `line[3:]`)
- [ ] Применяется `.strip('"')` (пути с пробелами)
- [ ] Применяется `.replace("\\", "/")` (Windows-нормализация)
- [ ] `git add` получает нормализованный путь
- [ ] Ошибки `git add` обрабатываются (returncode != 0)
- [ ] Есть timeout на subprocess.run

---

## Файлы проекта с исправлениями

### Исправление 1: line[3:] → line[2:].lstrip() (2026-02-20)

| Файл | Строка | Было | Стало |
|------|--------|------|-------|
| [auto-git-save-prompt.py](.claude/hooks/auto-git-save-prompt.py) | ~115 | `line[3:]` | `line[2:].lstrip()` |
| [auto-git-save.py](.claude/hooks/auto-git-save.py) | ~140 | `line[3:]` | `line[2:].lstrip()` |
| [auto-git-save.py](.claude/hooks/auto-git-save.py) | ~291 | `line.strip().split()` | `line[2:].lstrip()` |
| [git-commit-enforcer.py](.claude/hooks/git-commit-enforcer.py) | ~65 | `line[3:]` | `line[2:].lstrip()` |

### Исправление 2: core.quotepath=false (2026-02-22)

| Файл | Вхождений | Причина |
|------|:---------:|---------|
| [auto-git-save.py](.claude/hooks/auto-git-save.py) | 3 | `get_uncommitted_files`, `perform_sync_commit`, `sync_pending_tasks_with_git` |
| [auto-git-save-prompt.py](.claude/hooks/auto-git-save-prompt.py) | 1 | `_get_uncommitted_tracked_files` |
| [git-commit-enforcer.py](.claude/hooks/git-commit-enforcer.py) | 1 | `get_uncommitted_changes` |
| [docs-change-enforcer.py](.claude/hooks/docs-change-enforcer.py) | 1 | uncommitted files check |
| [task-enforcer.py](.claude/hooks/task-enforcer.py) | 1 | zombie task sync |
| [task_master.py](.claude/hooks/shared/task_master.py) | 1 | `sync_git_tasks` |

---

## Особые случаи

### Пути с пробелами
Git оборачивает в кавычки: `"path with spaces/file.py"` → `.strip('"')` убирает их.

### Пути с кириллицей / юникодом
**БЕЗ `core.quotepath=false`**: Git экранирует в octal: `"\320\236\320\261\320\267\320\276\321\200.md"`. Далее `.replace("\\", "/")` превращает `\320` в `/320` — путь сломан, `git add` падает молча.

**С `core.quotepath=false`**: Git выдаёт сырые UTF-8: `Обзор.md`. Путь корректен, `git add` работает.

### Переименования (R)
Формат: `R  old_name -> new_name` → парсить нужно правую часть после ` -> `.

### Пустой вывод (чистое дерево)
`result.stdout.strip()` будет пустой строкой. `.splitlines()` вернёт пустой список. Цикл не выполнится.

---

## Связанные скиллы

- [auto-git-save](.claude/skills/auto-git-save/) — автокоммит хук, использует парсинг
- [hook-debugging](.claude/skills/hook-debugging/) — отладка хуков
- [claude-code-hooks-bugs](.claude/skills/claude-code-hooks-bugs/) — баг #6305 PostToolUse
- [multi-level-hook-architecture](.claude/skills/multi-level-hook-architecture/) — трёхуровневая защита
