---
name: claude-code-terminal-ux
description: "UX-кастомизация терминала Claude Code (chrome, statusline, Shift+Enter). ТОЛЬКО при: --chrome Claude, /statusline, /vim Claude, iTerm2/Ghostty/Kitty/WezTerm/Alacritty Claude, GIF recording Claude. НЕ для CLI флагов (→ claude-code-cli-interactive), НЕ для VS Code (→ claude-code-vscode), НЕ для 1С, НЕ для LangChain."
---

# UX-кастомизация Claude Code

---

## 1. Интеграция с Chrome (бета)

### Что это

Claude Code управляет браузером Chrome через расширение Claude in Chrome + Native Messaging API. Работает с вашим реальным сеансом браузера (cookies, login state).

### Предварительные требования

| Компонент | Версия |
|-----------|--------|
| Google Chrome | latest |
| Расширение Claude in Chrome | 1.0.36+ |
| Claude Code CLI | 2.0.73+ |
| План Claude | Pro / Team / Enterprise |

> Не поддерживается: Brave, Arc, другие Chromium-браузеры, WSL.

### Настройка

```bash
# Запуск с Chrome
claude --chrome

# Проверка соединения (из сеанса)
/chrome

# Включить по умолчанию
/chrome → "Enabled by default"
```

> Включение по умолчанию увеличивает потребление контекста (инструменты браузера всегда загружены).

### Возможности

| Категория | Что Claude может |
|-----------|------------------|
| **Навигация** | Открывать URL, переходить по ссылкам, управлять вкладками |
| **Взаимодействие** | Клики, ввод текста, заполнение форм, прокрутка |
| **Чтение** | DOM, console logs, сетевые запросы, содержимое страницы |
| **Управление** | Изменение размера окон, создание/закрытие вкладок |
| **Запись** | GIF-запись взаимодействий |

### Примеры рабочих процессов

**Тестирование локального приложения:**
```
I just updated the login form validation. Can you open localhost:3000,
try submitting the form with invalid data, and check if the error
messages appear correctly?
```

**Отладка через console logs:**
```
Open the dashboard page and check the console for any errors when
the page loads.
```

**Автоматизация форм:**
```
I have a spreadsheet of contacts in contacts.csv. For each row,
go to crm.example.com, click "Add Contact", fill in name, email, phone.
```

**Google Docs (аутентифицированные приложения):**
```
Draft a project update based on our recent commits and add it to my
Google Doc at docs.google.com/document/d/abc123
```

**Извлечение данных:**
```
Go to the product listings page and extract name, price, availability
for each item. Save as CSV.
```

**Многосайтовый workflow:**
```
Check my calendar for meetings tomorrow, then for each meeting with
an external attendee, look up their company on LinkedIn and add a note.
```

**Запись GIF:**
```
Record a GIF showing how to complete the checkout flow, from adding
an item to the cart through to the confirmation page.
```

### Поведение

- Claude открывает **новые вкладки** (не захватывает существующие)
- Использует **login state** вашего браузера
- При CAPTCHA / login — пауза → вы решаете → говорите продолжить
- Видимое окно браузера обязательно (нет headless-режима)
- Разрешения сайтов наследуются от расширения Chrome

### Troubleshooting Chrome

| Проблема | Решение |
|----------|---------|
| Extension not detected | Chrome extension 1.0.36+, Claude Code 2.0.73+, Chrome запущен, `/chrome` → Reconnect |
| Браузер не отвечает | Проверить modal dialogs (alert/confirm), новая вкладка, перезагрузить расширение |
| Ошибки при первой настройке | Перезагрузить Chrome (native messaging host) |

### Лучшие практики Chrome

- **Modal dialogs** (alert/confirm/prompt) блокируют поток — закройте вручную
- **Новые вкладки** предпочтительнее переиспользования старых
- **Фильтруйте console output** — скажите Claude что искать, а не "весь вывод"
- Полный список инструментов: `/mcp` → `claude-in-chrome`

---

## 2. Строка состояния (Statusline)

### Что это

Кастомная строка внизу интерфейса Claude Code (аналог PS1 в shell). Обновляется при каждом сообщении (не чаще 300ms).

### Настройка

**Через команду (интерактивно):**
```
/statusline                           # воспроизвести prompt терминала
/statusline show the model name in orange   # кастомная инструкция
```

**Через settings.json (напрямую):**
```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/statusline.sh",
    "padding": 0
  }
}
```

### JSON-вход (stdin)

Скрипт получает JSON через stdin:

```json
{
  "hook_event_name": "Status",
  "session_id": "abc123...",
  "transcript_path": "/path/to/transcript.json",
  "cwd": "/current/working/directory",
  "model": {
    "id": "claude-opus-4-1",
    "display_name": "Opus"
  },
  "workspace": {
    "current_dir": "/current/working/directory",
    "project_dir": "/original/project/directory"
  },
  "version": "1.0.80",
  "output_style": { "name": "default" },
  "cost": {
    "total_cost_usd": 0.01234,
    "total_duration_ms": 45000,
    "total_api_duration_ms": 2300,
    "total_lines_added": 156,
    "total_lines_removed": 23
  },
  "context_window": {
    "total_input_tokens": 15234,
    "total_output_tokens": 4521,
    "context_window_size": 200000,
    "current_usage": {
      "input_tokens": 8500,
      "output_tokens": 1200,
      "cache_creation_input_tokens": 5000,
      "cache_read_input_tokens": 2000
    }
  }
}
```

### Доступные поля

| Путь | Описание |
|------|----------|
| `model.id` / `model.display_name` | Модель |
| `workspace.current_dir` / `workspace.project_dir` | Каталоги |
| `version` | Версия Claude Code |
| `cost.total_cost_usd` | Общая стоимость сеанса |
| `cost.total_duration_ms` | Длительность сеанса |
| `cost.total_lines_added` / `total_lines_removed` | Строки +/- |
| `context_window.context_window_size` | Размер контекстного окна |
| `context_window.current_usage.*` | Текущее использование (может быть null) |

### Примеры скриптов

**Bash — простой:**
```bash
#!/bin/bash
input=$(cat)
MODEL=$(echo "$input" | jq -r '.model.display_name')
DIR=$(echo "$input" | jq -r '.workspace.current_dir')
echo "[$MODEL] ${DIR##*/}"
```

**Bash — с Git:**
```bash
#!/bin/bash
input=$(cat)
MODEL=$(echo "$input" | jq -r '.model.display_name')
DIR=$(echo "$input" | jq -r '.workspace.current_dir')
GIT_BRANCH=""
if git rev-parse --git-dir > /dev/null 2>&1; then
    BRANCH=$(git branch --show-current 2>/dev/null)
    [ -n "$BRANCH" ] && GIT_BRANCH=" | $BRANCH"
fi
echo "[$MODEL] ${DIR##*/}$GIT_BRANCH"
```

**Bash — context window %:**
```bash
#!/bin/bash
input=$(cat)
MODEL=$(echo "$input" | jq -r '.model.display_name')
CTX_SIZE=$(echo "$input" | jq -r '.context_window.context_window_size')
USAGE=$(echo "$input" | jq '.context_window.current_usage')
if [ "$USAGE" != "null" ]; then
    TOKENS=$(echo "$USAGE" | jq '.input_tokens + .cache_creation_input_tokens + .cache_read_input_tokens')
    PCT=$((TOKENS * 100 / CTX_SIZE))
    echo "[$MODEL] Context: ${PCT}%"
else
    echo "[$MODEL] Context: 0%"
fi
```

**Python:**
```python
#!/usr/bin/env python3
import json, sys, os
data = json.load(sys.stdin)
model = data['model']['display_name']
cdir = os.path.basename(data['workspace']['current_dir'])
git_branch = ""
if os.path.exists('.git'):
    try:
        with open('.git/HEAD') as f:
            ref = f.read().strip()
            if ref.startswith('ref: refs/heads/'):
                git_branch = f" | {ref.replace('ref: refs/heads/', '')}"
    except: pass
print(f"[{model}] {cdir}{git_branch}")
```

**Node.js:**
```javascript
#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
let input = '';
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
    const data = JSON.parse(input);
    const model = data.model.display_name;
    const dir = path.basename(data.workspace.current_dir);
    let git = '';
    try {
        const head = fs.readFileSync('.git/HEAD', 'utf8').trim();
        if (head.startsWith('ref: refs/heads/'))
            git = ` | ${head.replace('ref: refs/heads/', '')}`;
    } catch {}
    console.log(`[${model}] ${dir}${git}`);
});
```

### Helper-функции (bash)

```bash
get_model_name()    { echo "$input" | jq -r '.model.display_name'; }
get_current_dir()   { echo "$input" | jq -r '.workspace.current_dir'; }
get_project_dir()   { echo "$input" | jq -r '.workspace.project_dir'; }
get_version()       { echo "$input" | jq -r '.version'; }
get_cost()          { echo "$input" | jq -r '.cost.total_cost_usd'; }
get_duration()      { echo "$input" | jq -r '.cost.total_duration_ms'; }
get_lines_added()   { echo "$input" | jq -r '.cost.total_lines_added'; }
get_lines_removed() { echo "$input" | jq -r '.cost.total_lines_removed'; }
get_input_tokens()  { echo "$input" | jq -r '.context_window.total_input_tokens'; }
get_output_tokens() { echo "$input" | jq -r '.context_window.total_output_tokens'; }
```

### Советы по statusline

- Краткая — одна строка
- ANSI-цвета поддерживаются
- `jq` для парсинга JSON в bash
- Тест: `echo '{"model":{"display_name":"Test"},"workspace":{"current_dir":"/test"}}' | ./statusline.sh`
- `chmod +x` обязательно, stdout (не stderr)

---

## 3. Настройка терминала

### Темы

Claude НЕ управляет темой терминала. Сопоставить тему Claude Code с терминалом: `/config`.

### Разрывы строк (многострочный ввод)

| Способ | Где работает |
|--------|-------------|
| `\` + Enter | Везде |
| `Shift+Enter` | iTerm2, WezTerm, Ghostty, Kitty — из коробки |
| `/terminal-setup` | Авто-настройка для VS Code, Alacritty, Zed, Warp |

> `/terminal-setup` видна только в терминалах, требующих ручной настройки.

**Option+Enter (Mac Terminal.app):**
Settings → Profiles → Keyboard → "Use Option as Meta Key"

**Option+Enter (iTerm2 / VS Code):**
Settings → Profiles → Keys → General → Left/Right Option key → "Esc+"

### Уведомления

**iTerm2:**
1. Preferences → Profiles → Terminal
2. "Silence bell" + Filter Alerts → "Send escape sequence-generated alerts"
3. Настроить задержку

**Кастомные хуки уведомлений:**
Создать через hooks API для собственной логики.

### Обработка больших входных данных

- Не вставлять длинный текст напрямую — записать в файл → попросить Claude прочитать
- VS Code терминал особенно подвержен усечению

### Vim mode

Включение: `/vim` или `/config`

| Категория | Привязки |
|-----------|----------|
| **Режимы** | `Esc` (NORMAL), `i`/`I`/`a`/`A`/`o`/`O` (INSERT) |
| **Навигация** | `h`/`j`/`k`/`l`, `w`/`e`/`b`, `0`/`$`/`^`, `gg`/`G`, `f`/`F`/`t`/`T` + `;`/`,` |
| **Удаление** | `x`, `dw`/`de`/`db`/`dd`/`D` |
| **Замена** | `cw`/`ce`/`cb`/`cc`/`C` |
| **Повтор** | `.` |
| **Копирование** | `yy`/`Y`, `yw`/`ye`/`yb`, `p`/`P` |
| **Текстовые объекты** | `iw`/`aw`, `iW`/`aW`, `i"`/`a"`, `i'`/`a'`, `i(`/`a(`, `i[`/`a[`, `i{`/`a{` |
| **Отступы** | `>>`/`<<` |
| **Строки** | `J` (объединение) |

---

**Источники:**
- Использование Claude Code с Chrome (бета).md (docs/documentation/Claude Code Docs/1. Начало работы/)
- Конфигурация строки состояния.md (docs/documentation/Claude Code Docs/3. Конфигурация/)
- Оптимизируйте настройку вашего терминала.md (docs/documentation/Claude Code Docs/3. Конфигурация/)
