---
name: hook-debugging
description: "Диагностика хуков Claude Code: canary-метод, file-based логирование, ручной тест stdin, subprocess-обёртка, чеклист отладки. Триггеры: 'хук не работает', 'hook not firing', 'отладка хука', 'debug hook', 'хук не срабатывает', 'hook debugging', 'почему хук не запускается', 'canary test'. НЕ для создания хуков — используй create-hook. НЕ для известных багов — используй claude-code-hooks-bugs."
---

# Hook Debugging — диагностика хуков Claude Code

## Обзор

Методика диагностики хуков, выработанная при отладке `auto-git-save.py` (PostToolUse). Хук проходил ручные тесты, но не срабатывал в реальной сессии Claude Code. Причина: баг #6305 — Claude Code не запускает процессы PostToolUse хуков.

**Главный принцип:** доказать на каком этапе происходит отказ — процесс не запускается? stdin пуст? ошибка импорта? логика фильтрации?

---

## Чеклист диагностики (по порядку)

| Шаг | Проверяет | Команда | Ожидание |
|-----|-----------|---------|----------|
| 1. Синтаксис | Нет ли SyntaxError | `python -m py_compile hook.py` | `SYNTAX OK` |
| 2. Импорты | Все зависимости доступны | `python -c "import hook"` | Без ошибок |
| 3. Ручной stdin | Логика хука работает | `echo '{"tool_name":"Edit",...}' \| python hook.py` | Ожидаемый JSON |
| 4. Canary-тест | Процесс вообще запускается | Вставить canary → сделать Edit → проверить файл | Файл создан |
| 5. Лог-файл | Где именно падает | Добавить file logging → проверить лог | Записи есть |

---

## Шаг 1: Проверка синтаксиса

```bash
python -m py_compile .claude/hooks/my-hook.py && echo "SYNTAX OK"
```

Если ошибка — python покажет строку и тип ошибки.

---

## Шаг 2: Проверка импортов

```bash
python -c "
import importlib.util
spec = importlib.util.spec_from_file_location('hook', '.claude/hooks/my-hook.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print('Imports OK')
"
```

Частые проблемы:
- `ModuleNotFoundError` — `base`, `shared.task_master` не в sys.path
- Хуки с дефисом в имени не импортируются через `import` (используй `importlib`)

---

## Шаг 3: Ручной тест через stdin

### PostToolUse хук (Write/Edit):
```bash
echo '{"tool_name":"Edit","tool_input":{"file_path":"src/test.py","old_string":"a","new_string":"b"}}' | python .claude/hooks/my-hook.py
```

### UserPromptSubmit хук:
```bash
echo '{"prompt":"test message"}' | python .claude/hooks/my-hook.py
```

### Stop хук:
```bash
echo '{}' | python .claude/hooks/my-hook.py; echo "EXIT=$?"
```

### Через subprocess (точнее):
```python
import subprocess, sys
result = subprocess.run(
    [sys.executable, '.claude/hooks/my-hook.py'],
    input=b'{"tool_name":"Edit","tool_input":{"file_path":"src/test.py"}}',
    capture_output=True, timeout=15
)
print('STDOUT:', result.stdout.decode('utf-8', errors='replace'))
print('STDERR:', result.stderr.decode('utf-8', errors='replace'))
print('EXIT:', result.returncode)
```

---

## Шаг 4: Canary-тест (критический)

**Цель:** доказать запускается ли процесс хука вообще.

Вставить **в самое начало файла** (ДО любых импортов):

```python
#!/usr/bin/env python3
# === CANARY: удалить после диагностики ===
try:
    from pathlib import Path as _P
    from datetime import datetime as _DT
    _canary = _P(__file__).resolve().parent.parent / "cache" / "canary-HOOKNAME.txt"
    _canary.parent.mkdir(parents=True, exist_ok=True)
    _canary.write_text(f"CANARY {_DT.now().isoformat()}\n", encoding="utf-8")
except Exception:
    pass
# === END CANARY ===
```

Затем:
1. Выполнить действие, которое должно триггерить хук (Edit файла)
2. Проверить: `cat .claude/cache/canary-HOOKNAME.txt`
3. Файл **существует** → процесс запускается, проблема в логике хука
4. Файл **НЕ существует** → Claude Code НЕ запускает процесс (баг платформы)

**Важно:** canary стоит ДО импортов — значит даже ImportError не помешает записи. Если файла нет — гарантия что процесс не стартовал.

---

## Шаг 5: File-based логирование

Добавить в хук (stdout/stderr не видны при вызове из Claude Code):

```python
import logging
from pathlib import Path

_LOG_FILE = Path(__file__).resolve().parent.parent / "cache" / "my-hook-debug.log"

logging.basicConfig(
    filename=str(_LOG_FILE),
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("my-hook")
```

Ключевые точки логирования:
```python
log.debug(f"START tool={tool_name} file={file_path}")   # вход
log.debug(f"should_track={result}")                      # фильтрация
log.debug(f"subprocess cmd={cmd} rc={rc} err={stderr}")  # внешние вызовы
log.debug(f"EXIT result={output}")                       # выход
```

---

## Логирование ошибок в BaseHook.run()

Если хук наследует BaseHook, добавить в `base/protocol.py`:

```python
except Exception as e:
    try:
        from pathlib import Path as _P
        from datetime import datetime as _DT
        _log = _P(__file__).resolve().parent.parent / "cache" / "hook-errors.log"
        _log.parent.mkdir(parents=True, exist_ok=True)
        with open(str(_log), "a", encoding="utf-8") as _f:
            _cls = type(self).__name__
            _f.write(f"{_DT.now().isoformat()} [{_cls}] {type(e).__name__}: {e}\n")
    except Exception:
        pass
    sys.exit(0)
```

---

## Типичные причины отказа

| Симптом | Причина | Решение |
|---------|---------|---------|
| Canary не создан | Claude Code не запускает процесс | Баг #6305, используй workaround (UserPromptSubmit/Stop) |
| Canary создан, stdout пуст | Ошибка в логике хука | Добавить file logging, проверить лог |
| Ручной тест работает, хук нет | stdin пустой (Windows #10450) | Обрабатывать пустой stdin gracefully |
| ImportError в логе | Зависимость не в sys.path | Проверить sys.path.insert для base/shared |
| Timeout в settings.json | Операции не укладываются | Увеличить timeout, оптимизировать subprocess |
| `line[3:]` баг | Потеря точки `.claude/` | Использовать `line[2:].lstrip()` |

---

## Файлы проекта

| Файл | Роль |
|------|------|
| [.claude/hooks/base/protocol.py](.claude/hooks/base/protocol.py) | BaseHook с error logging |
| [.claude/cache/hook-errors.log](.claude/cache/hook-errors.log) | Лог ошибок всех BaseHook хуков |
| [.claude/cache/auto-git-save-debug.log](.claude/cache/auto-git-save-debug.log) | Пример debug лога |
