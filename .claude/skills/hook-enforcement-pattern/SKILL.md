---
name: hook-enforcement-pattern
description: "Паттерн Enforcer для Stop-хуков Claude Code: шаблон блокирующего хука, протокол stdin/stdout/exit, graceful degradation, actionable messages, ссылки на скиллы. Триггеры: 'enforcer pattern', 'паттерн принуждения', 'блокирующий хук', 'stop hook pattern', 'exit 2', 'block stop', 'шаблон enforcer', 'как заблокировать остановку'. НЕ для создания хуков — используй create-hook. НЕ для диагностики — используй hook-debugging."
---

# Hook Enforcement Pattern — паттерн Enforcer для Stop-хуков

## Обзор

Enforcer — поведенческий подпаттерн триады (Цикл принуждения). Stop-хук который блокирует завершение Claude до выполнения определённого условия. Используется для гарантии: коммит сделан, документация обновлена, задачи выполнены.

---

## Протокол Stop-хука

### stdin
Claude Code передаёт JSON на stdin (может быть пустым на Windows — #10450):
```json
{"stop_hook_active": true}
```

### stdout
Хук возвращает JSON на stdout:
```json
{"decision": "block", "reason": "Текст причины блокировки"}
```

### Exit codes
| Код | Значение |
|-----|----------|
| `0` | Разрешить остановку |
| `2` | Блокировать остановку |
| другой | Ошибка (интерпретируется как разрешение) |

---

## Шаблон Enforcer-хука

```python
#!/usr/bin/env python3
"""
Hook: my-enforcer
Event: Stop
Matcher: (none)
Purpose: Блокирует остановку если [УСЛОВИЕ].
Timeout: 10s

Exit codes:
  0 = разрешить остановку
  2 = блокировать остановку

Pattern: Enforcer (поведенческий подпаттерн триады — Цикл принуждения).
"""

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def check_condition() -> list[str]:
    """Проверить условие. Вернуть список проблем (пустой = всё ОК)."""
    problems = []
    try:
        # ... логика проверки ...
        pass
    except Exception:
        pass  # Graceful degradation
    return problems


def main():
    """Проверить условие. Блокировать если не выполнено."""
    try:
        # 1. Прочитать stdin (ОБЯЗАТЕЛЬНО по протоколу)
        try:
            sys.stdin.buffer.read()
        except Exception:
            pass

        # 2. Проверить условие
        problems = check_condition()

        if not problems:
            sys.exit(0)  # Всё ОК — разрешить

        # 3. Сформировать actionable message
        items_str = "\n".join(f"  - {p}" for p in problems[:10])

        reason = (
            f"[MY-ENFORCER] Обнаружено {len(problems)} проблем(а)!\n\n"
            f"{items_str}\n\n"
            "Действия:\n"
            "1. Используй скилл /my-skill для исправления\n"
            "2. Или исправь вручную\n"
            "3. После исправления можешь завершить."
        )

        # 4. Вывести JSON на stdout
        output = {"decision": "block", "reason": reason}
        out_bytes = json.dumps(output, ensure_ascii=False).encode("utf-8")
        sys.stdout.buffer.write(out_bytes + b"\n")
        sys.stdout.buffer.flush()
        sys.exit(2)  # Блокировать

    except Exception:
        # 5. ВСЕГДА graceful degradation
        sys.exit(0)


if __name__ == "__main__":
    main()
```

---

## Правила Enforcer-а

### 1. Graceful Degradation (обязательно)

```python
except Exception:
    sys.exit(0)  # НИКОГДА не блокировать при ошибке
```

Если enforcer сам упал — лучше разрешить остановку, чем заблокировать навсегда.

### 2. stdin.buffer.read() (обязательно)

```python
try:
    sys.stdin.buffer.read()
except Exception:
    pass
```

Протокол требует прочитать stdin. Без этого хук может зависнуть.

### 3. Actionable messages (рекомендуется)

Плохо:
```
"Есть проблемы. Исправь."
```

Хорошо:
```
"[DOCS-ENFORCER] Документация не обновлена для 2 области(ей)!

  📄 docs/framework documentation/04_ПОИСК/
     Skill: search-pipeline-debug
     Код: hybrid.py, bm25.py

Действия:
1. Используй скилл /audit-docs для автоматического обновления
2. Или вручную обнови документацию
3. После обновления можешь завершить."
```

### 4. Ссылка на скилл (рекомендуется)

Enforcer **проверяет**, скилл **исправляет**. Всегда указывай Claude какой скилл использовать:

| Enforcer | Скилл для исправления |
|----------|----------------------|
| git-commit-enforcer | (ручной git commit) |
| docs-change-enforcer | `/audit-docs` |
| task-enforcer | (выполнить pending задачи) |

### 5. Timeout (важно)

Enforcer должен быть быстрым. Timeout в settings.json:
- Простая проверка (git status): **5s**
- Проверка с несколькими git командами: **10s**
- Максимум: **15s**

### 6. Не дублировать логику

Каждый enforcer проверяет ОДНО условие:
- `git-commit-enforcer` → незакоммиченные файлы
- `docs-change-enforcer` → устаревшая документация
- `task-enforcer` → невыполненные задачи

Не делать один enforcer который проверяет всё.

---

## Регистрация в settings.json

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "D:\\path\\python.exe D:\\path\\my-enforcer.py",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

Порядок важен — хуки выполняются последовательно. Рекомендуемый порядок:
1. `ralph_wiggum_stop.py` — контроль автономного цикла
2. `git-commit-enforcer.py` — незакоммиченные файлы
3. `docs-change-enforcer.py` — устаревшая документация
4. `task-enforcer.py` — невыполненные задачи

---

## Примеры из проекта

| Файл | Проверяет | Timeout | Скилл |
|------|-----------|---------|-------|
| [git-commit-enforcer.py](.claude/hooks/git-commit-enforcer.py) | Незакоммиченные файлы в WATCHED_PATHS | 5s | — |
| [docs-change-enforcer.py](.claude/hooks/docs-change-enforcer.py) | Код изменился, доки не обновлены | 10s | audit-docs |
| [task-enforcer.py](.claude/hooks/task-enforcer.py) | Pending задачи от mandatory хуков | 10s | — |
| [ralph_wiggum_stop.py](.claude/hooks/ralph_wiggum_stop.py) | RALPH_DONE маркер в автономных циклах | 5s | — |

---

## Антипаттерны

| Антипаттерн | Проблема | Решение |
|-------------|----------|---------|
| `sys.exit(2)` в except | Блокировка при ошибке | Всегда `sys.exit(0)` в except |
| Нет stdin.read() | Зависание хука | Всегда читать stdin |
| Общее сообщение | Claude не знает что делать | Actionable message + ссылка на скилл |
| Проверка всего в одном хуке | Сложно поддерживать | Одно условие на enforcer |
| timeout > 15s | Медленная остановка | Оптимизировать проверку |
| Бесконечная блокировка | Claude не может остановиться | Максимум 3 цикла, потом exit 0 |
