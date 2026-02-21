---
name: git-porcelain-parsing
description: "Парсинг git status --porcelain в Python: формат XY, правильное извлечение путей, обработка staged/unstaged, кавычек, юникода. Триггеры: 'git status parsing', 'porcelain', 'парсинг git status', 'line[3:]', 'git status python', 'извлечь путь из git status', 'staged files python'. НЕ для git команд — используй CLI. НЕ для коммитов — используй auto-git-save."
---

# Git Porcelain Parsing — парсинг git status --porcelain

## Обзор

Правильный парсинг вывода `git status --porcelain` в Python. Баг `line[3:]` был обнаружен в 4 файлах проекта и приводил к потере ведущей точки в путях `.claude/`, из-за чего файлы не матчились с WATCHED_PATHS.

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

    Returns:
        list of {"path": str, "index": str, "work": str, "is_untracked": bool}
    """
    result = subprocess.run(
        ["git", "status", "--porcelain"],
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

        # ПРАВИЛЬНЫЙ парсинг пути
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

## Файлы проекта с исправлением

| Файл | Строка | Было | Стало |
|------|--------|------|-------|
| [auto-git-save-prompt.py](.claude/hooks/auto-git-save-prompt.py) | ~129 | `line[3:]` | `line[2:].lstrip()` |
| [auto-git-save.py](.claude/hooks/auto-git-save.py) | ~157 | `line[3:]` | `line[2:].lstrip()` |
| [auto-git-save.py](.claude/hooks/auto-git-save.py) | ~308 | `line.strip().split()` | `line[2:].lstrip()` |
| [git-commit-enforcer.py](.claude/hooks/git-commit-enforcer.py) | ~63 | `line[3:]` | `line[2:].lstrip()` |
| [docs-change-enforcer.py](.claude/hooks/docs-change-enforcer.py) | ~135 | (сразу правильно) | `line[2:].lstrip()` |

---

## Особые случаи

### Пути с пробелами
Git оборачивает в кавычки: `"path with spaces/file.py"` → `.strip('"')` убирает их.

### Пути с юникодом (кириллица)
Git может экранировать: `"\320\241\320\236\320\224..." ` → octal escape. Для корректной обработки нужен `git config core.quotePath false`.

### Переименования (R)
Формат: `R  old_name -> new_name` → парсить нужно правую часть после ` -> `.
