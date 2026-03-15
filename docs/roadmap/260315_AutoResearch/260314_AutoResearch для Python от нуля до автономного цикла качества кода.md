# AutoResearch для Python: от нуля до автономного цикла качества кода

**Автономный цикл «изменил → проверил → сохранил или откатил» теперь доступен для Python-проектов без GPU.** Концепция Андрея Карпати, реализованная 7 марта 2026 года для ML-экспериментов, уже обобщена в Claude Code–скилл, работающий с любой измеримой метрикой — включая lint-ошибки, типизацию и цикломатическую сложность. Ниже — полная дорожная карта внедрения на Windows с конкретными командами, таймлайном и оценкой затрат.

---

## Фаза 0: подготовка среды на Windows (день 1)

### Установка Claude Code

Claude Code получил **нативную поддержку Windows в августе 2025 года** — WSL больше не требуется. Инструмент работает через Git Bash, встроенный в Git for Windows.

**Шаг 1 — Git for Windows** (если ещё не установлен):
```
winget install Git.Git
```

**Шаг 2 — Claude Code** (один из способов):
```powershell
# PowerShell (рекомендуется):
irm https://claude.ai/install.ps1 | iex

# Или через WinGet:
winget install Anthropic.ClaudeCode
```

Бинарник ставится в `%USERPROFILE%\.local\bin`. Если после установки команда `claude` не распознаётся, добавьте путь вручную:
```powershell
[Environment]::SetEnvironmentVariable("PATH", "$env:PATH;$env:USERPROFILE\.local\bin", [EnvironmentVariableTarget]::User)
```

**Шаг 3 — проверка:**
```
claude doctor   # диагностика установки
claude          # запуск (откроется браузер для авторизации)
```

**Node.js не нужен** — нативный установщик самодостаточен. Старый способ через `npm install -g @anthropic-ai/claude-code` официально deprecated.

**Системные требования**: Windows 10+, **4 ГБ RAM** (8 ГБ рекомендуется), любой CPU (Intel/AMD), GPU не нужен — вся ИИ-инференция происходит в облаке Anthropic. Нужен стабильный интернет.

### Аутентификация

Два варианта:

| Метод | Для кого | Настройка |
|-------|----------|-----------|
| **OAuth** (рекомендуется) | Подписчики Pro/Max/Team | При первом запуске `claude` открывается браузер для входа |
| **API-ключ** (pay-per-use) | Пользователи API | Создать ключ на console.anthropic.com → `setx ANTHROPIC_API_KEY "sk-ant-..."` |

Минимальная подписка для Claude Code — **Claude Pro ($20/мес)**. Бесплатный план Claude Code не включает.

### Python-инструменты

```powershell
pip install ruff mypy pylint radon pytest-cov coverage
```

Или через uv (быстрый менеджер от Astral):
```powershell
pip install uv
uv pip install ruff mypy pylint radon pytest-cov
```

---

## Фаза 1: установка AutoResearch–скилла (день 1–2)

### Две реализации AutoResearch

Существуют два репозитория. Для задачи качества кода нужен именно второй:

| | Karpathy `karpathy/autoresearch` | Goenka `uditgoenka/autoresearch` |
|---|---|---|
| **Домен** | Только ML-обучение (нужна GPU) | Любая задача с числовой метрикой |
| **Формат** | `program.md` (неформальные инструкции) | Формальный `SKILL.md` для Claude Code |
| **Метрика** | `val_bpb` (loss модели) | Определяется пользователем |
| **Звёзды** | ~32 600 | 6 (новый, выпущен 13 марта 2026) |

### Установка скилла Goenka

```powershell
cd ваш-проект
git clone https://github.com/uditgoenka/autoresearch.git temp-autoresearch
xcopy /E /I temp-autoresearch\skills\autoresearch .claude\skills\autoresearch
rmdir /S /Q temp-autoresearch
```

Структура после установки:
```
ваш-проект/
├── .claude/
│   └── skills/
│       └── autoresearch/
│           ├── SKILL.md                       ← главный скилл
│           └── references/
│               ├── autonomous-loop-protocol.md
│               ├── core-principles.md
│               └── results-logging.md
├── src/
│   └── ... ваш код ...
└── pyproject.toml
```

### 8-фазный цикл скилла

Каждая итерация проходит через **8 фаз**:

1. **REVIEW** — прочитать текущий код, git log, лог результатов
2. **IDEATE** — выбрать следующее изменение на основе паттернов и пробелов
3. **MODIFY** — сделать одно атомарное изменение
4. **COMMIT** — `git commit` до проверки (для чистого rollback)
5. **VERIFY** — запустить механическую проверку метрики
6. **DECIDE** — улучшилось → keep | ухудшилось → revert | crash → fix
7. **LOG** — записать в `autoresearch-results.tsv`
8. **REPEAT** — перейти к фазе 1. **Никогда не останавливаться.**

Остановка — через `Ctrl+C` или закрытие терминала.

---

## Фаза 2: настройка метрик — «функция потерь» для кода (день 2–3)

### Ruff — центральный инструмент 2025–2026

**Ruff заменил Flake8 + Black + isort** в одном инструменте. Написан на Rust, работает **в 10–100 раз быстрее** Flake8. Его используют FastAPI, pandas, Pydantic, Apache Airflow. Для автономного цикла критична скорость — Ruff выполняет проверку **за 0.2 секунды** на 120K строк кода (Flake8 — 3 сек, Pylint — 20+ сек).

### Команды для числовых метрик на Windows

Каждая метрика должна давать **одно число** — это требование скилла AutoResearch.

**1. Lint-ошибки (Ruff)** — основная метрика, цель: 0
```powershell
# PowerShell — точный подсчёт через JSON:
(ruff check . --output-format json | ConvertFrom-Json).Count

# Или текстовый вывод:
ruff check . 2>&1 | Select-String "Found"
# Вывод: "Found 42 errors." или "All checks passed!"
```

**2. Ошибки типизации (mypy)** — цель: 0
```powershell
(mypy src/ 2>&1 | Select-String ": error:").Count
```

**3. Оценка Pylint** — цель: 10.00/10
```powershell
pylint src/ 2>&1 | Select-String "rated at"
# Вывод: "Your code has been rated at 7.52/10"
```

**4. Цикломатическая сложность (Radon)** — цель: ≤ 5.0 (grade A)
```powershell
radon cc src/ --total-average | Select-Object -Last 1
# Вывод: "Average complexity: A (2.345)"
```

**5. Maintainability Index (Radon MI)** — цель: ≥ 65
```powershell
radon mi src/ -j | python -c "import sys,json;d=json.load(sys.stdin);v=[x['mi'] for x in d.values()];print(f'{sum(v)/len(v):.1f}')"
```

**6. Покрытие тестами** — цель: ≥ 80%
```powershell
pytest --cov=src tests/ 2>&1 | Select-String "^TOTAL"
```

### Рекомендуемая начальная метрика

Для первого автономного запуска возьмите **самую простую и быструю метрику — количество Ruff-ошибок**. Она удовлетворяет всем критериям скилла:

- Выполняется менее чем за 10 секунд ✓
- Выдаёт одно число ✓
- Детерминирована ✓
- Направление оптимизации — вниз (меньше = лучше) ✓

### Композитная «функция потерь»

Для продвинутого этапа — формула, нормализующая все метрики к шкале 0–100:

```python
def quality_score(ruff_errors, mypy_errors, pylint_score, avg_complexity, loc):
    lint = max(0, 100 - (ruff_errors / max(loc, 1)) * 5000)
    types = max(0, 100 - (mypy_errors / max(loc, 1)) * 10000)
    pylint_n = max(0, pylint_score * 10)
    complexity = max(0, min(100, 100 - (avg_complexity - 1) * 5))
    return round(lint * 0.25 + types * 0.30 + pylint_n * 0.20 + complexity * 0.25, 1)
```

| Метрика | Инструмент | «Хорошо» | «Отлично» |
|---------|-----------|-----------|-----------|
| Lint-ошибки | Ruff | < 10 | 0 |
| Type-ошибки | mypy | < 20 | 0 |
| Pylint score | Pylint | ≥ 8.0 | ≥ 9.5 |
| Средняя сложность | Radon CC | ≤ 5 (A) | ≤ 3 |
| Maintainability Index | Radon MI | ≥ 65 | ≥ 80 |
| Покрытие тестами | pytest-cov | ≥ 80% | ≥ 90% |

---

## Фаза 3: первый ручной тест (день 3–4)

Прежде чем запускать автономный цикл, протестируйте всё вручную.

### Шаг 1 — замерьте baseline

```powershell
cd ваш-проект
ruff check . --output-format json | python -c "import sys,json;print(len(json.load(sys.stdin)))"
# Запишите число, например: 47
```

### Шаг 2 — попросите Claude Code исправить одну проблему

```powershell
claude
# В интерактивном режиме:
> Прочитай результат `ruff check . --output-format concise` и исправь 3 самые частые категории ошибок. После исправления запусти ruff check снова и покажи разницу.
```

### Шаг 3 — проверьте, что git работает

```powershell
git log --oneline -5          # убедитесь, что Claude сделал commit
git diff HEAD~1               # посмотрите изменения
git revert HEAD --no-edit     # протестируйте откат
git revert HEAD --no-edit     # вернитесь обратно (revert revert)
```

### Шаг 4 — протестируйте headless-режим

```powershell
claude -p "Запусти ruff check . и выведи количество ошибок" --output-format text --max-turns 5
```

---

## Фаза 4: первый автономный запуск (день 4–5)

### Запуск через скилл

```powershell
claude
# В интерактивном режиме введите:
> /autoresearch
> Goal: Reduce ruff lint errors to zero
> Scope: src/**/*.py
> Metric: ruff error count (lower is better)
> Verify: powershell -Command "(ruff check . --output-format json | ConvertFrom-Json).Count"
```

Скилл запустит бесконечный цикл: прочитает код → предложит исправление → закоммитит → проверит ruff → сохранит или откатит → запишет в TSV → повторит.

### Формат autoresearch-results.tsv

```
iteration	commit	metric	delta	status	description
0	a1b2c3d	47	0.0	baseline	initial state — 47 ruff errors
1	b2c3d4e	38	-9	keep	fix F841 unused variables across 5 files
2	-	41	+3	discard	refactor imports broke 3 checks
3	c3d4e5f	31	-7	keep	fix E711 comparison to None
4	d4e5f6g	28	-3	keep	fix W291 trailing whitespace
```

### Альтернативный запуск через headless + скрипт

Если скилл не подходит, можно организовать цикл вручную через PowerShell-скрипт:

```powershell
# autoresearch-loop.ps1
$iteration = 0
while ($true) {
    $iteration++
    Write-Host "=== Iteration $iteration ==="
    
    # Замер ДО
    $before = (ruff check . --output-format json | ConvertFrom-Json).Count
    
    # Агент вносит изменения
    claude -p @"
    Текущее количество ruff-ошибок: $before.
    Прочитай ruff check . --output-format concise, найди самую частую категорию ошибок 
    и исправь её во всех файлах. Сделай git commit с описанием изменения.
"@ --max-turns 15 --max-budget-usd 0.50
    
    # Замер ПОСЛЕ
    $after = (ruff check . --output-format json | ConvertFrom-Json).Count
    $delta = $after - $before
    
    if ($after -lt $before) {
        Write-Host "KEEP: $before -> $after (delta: $delta)"
    } else {
        Write-Host "REVERT: $before -> $after (delta: $delta)"
        git revert HEAD --no-edit
    }
    
    # Лог
    "$iteration`t$(git rev-parse --short HEAD)`t$after`t$delta`t$(if($after -lt $before){'keep'}else{'discard'})" >> results.tsv
    
    Start-Sleep -Seconds 5
}
```

Запуск:
```powershell
powershell -ExecutionPolicy Bypass -File autoresearch-loop.ps1
```

---

## Фаза 5: безопасность и защита кода

### Три уровня защиты

**1. Git как страховочная сеть.** Скилл делает `git commit` перед каждой проверкой. Если метрика ухудшилась — `git revert HEAD --no-edit`. Последнее успешное состояние всегда сохранено.

**2. Автоматические чекпоинты Claude Code.** С 2025 года Claude Code создаёт чекпоинты перед каждым изменением. Команда `/rewind` или двойное нажатие `Esc` откатывает к предыдущему состоянию.

**3. Ограничение области видимости агента.** Создайте файл `.claudeignore` в корне проекта:

```
# Файлы, которые агент НЕ должен трогать
*.env
*.secret
config/production.py
migrations/
alembic/
docker-compose.yml
Dockerfile
.github/
```

### Дополнительные меры безопасности

- **Рабочая ветка**: всегда запускайте агента в отдельной ветке:
```powershell
git checkout -b autoresearch/lint-cleanup
```

- **Ограничение инструментов** через флаги Claude Code:
```powershell
claude -p "..." --allowedTools "Read,Write,Edit,Bash(ruff:*),Bash(git:*),Bash(mypy:*)"
```

- **Лимит бюджета на сессию**:
```powershell
claude -p "..." --max-budget-usd 2.00 --max-turns 30
```

- **Защита критических файлов через pre-commit hook**:
```bash
# .git/hooks/pre-commit
#!/bin/sh
PROTECTED="config/production.py migrations/ .env"
for file in $PROTECTED; do
    if git diff --cached --name-only | grep -q "$file"; then
        echo "BLOCKED: $file is protected from agent changes"
        exit 1
    fi
done
```

---

## Стоимость и бюджет: сколько стоит автономный цикл

### Актуальные цены Anthropic API (март 2026)

| Модель | Input / 1M токенов | Output / 1M токенов | Для каких задач |
|--------|-------------------|---------------------|-----------------|
| **Sonnet 4.6** | **$3.00** | **$15.00** | Основная рабочая лошадка |
| Opus 4.6 | $5.00 | $25.00 | Сложные рефакторинги |
| Haiku 4.5 | $1.00 | $5.00 | Простые lint-фиксы |

### Стоимость одной итерации

Одна итерация цикла (прочитать 500 строк → найти проблему → исправить → проверить) потребляет **~10 000–15 000 токенов**. При использовании Sonnet 4.6:

| Компонент | Токены | Стоимость |
|-----------|--------|-----------|
| Input (код + контекст) | ~10 000 | $0.03 |
| Output (анализ + правки) | ~3 000 | $0.045 |
| **Итого за 1 итерацию** | **~13 000** | **$0.05–$0.10** |
| С prompt caching (95% hit) | ~13 000 | **$0.01–$0.03** |

### Бюджет на 100 итераций

| Сценарий | Sonnet 4.6 | Haiku 4.5 |
|----------|-----------|-----------|
| Без оптимизации | $5–$20 | $2–$8 |
| С кэшированием + compaction | **$2–$8** | **$0.50–$3** |
| Через Batch API (−50%) | $1–$4 | $0.25–$1.50 |

**Предупреждение о росте контекста**: каждая итерация в одной сессии накапливает историю. К 10-й итерации input может вырасти до **100K+ токенов**. Используйте `/compact` каждые 5–10 итераций или организуйте цикл через отдельные headless-вызовы (`claude -p "..."`) — тогда каждая итерация стартует с чистого контекста.

### Рекомендуемые планы

| Профиль использования | API-стоимость/мес | Рекомендуемый план |
|----------------------|-------------------|-------------------|
| **Хобби** (< 1 ч/день) | $30–$60 | **Pro $20/мес** — дешевле API |
| **Активная разработка** (2–4 ч/день) | $100–$200 | **Max 5x $100/мес** — окупается |
| **Полный рабочий день** | $300–$1 000+ | **Max 20x $200/мес** — экономия до 93% |

По данным Anthropic, **средний разработчик тратит ~$6/день** через Claude Code, 90% пользователей — менее $12/день.

### Контроль расходов

- **`/cost`** в Claude Code — показывает стоимость текущей сессии в реальном времени
- **`--max-budget-usd 2.00`** — жёсткий лимит на headless-сессию
- **Console → Usage → Spending Limits** — месячный потолок расходов
- **Переменная окружения** `DISABLE_NON_ESSENTIAL_MODEL_CALLS=1` — отключает фоновые обращения к API

---

## Полная конфигурация проекта

### pyproject.toml

```toml
[tool.ruff]
line-length = 88
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "B", "UP", "S", "C90", "PL"]
ignore = ["E501"]

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.ruff.format]
quote-style = "double"

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true

[tool.pylint.master]
fail-under = 7.0

[tool.pytest.ini_options]
addopts = "--cov=src --cov-report=term-missing --cov-fail-under=80"
```

### CLAUDE.md (инструкции для Claude Code в корне проекта)

```markdown
# Project Instructions

## Code Quality Rules
- All code must pass `ruff check .` with zero errors
- All code must pass `mypy src/ --strict` with zero errors  
- Formatting: always run `ruff format .` before committing
- Import sorting: handled by ruff (I rules)
- Minimum pylint score: 8.0/10
- Maximum cyclomatic complexity: 10 per function

## Verification Commands
- Lint: `ruff check . --output-format json`
- Types: `mypy src/`
- Format: `ruff format --check .`
- Score: `pylint src/`
- Complexity: `radon cc src/ --total-average`

## Safety Rules  
- NEVER modify files in: migrations/, .env, config/production.py
- ALWAYS work in a feature branch
- ALWAYS commit before running verification
- If verification fails, revert immediately
```

---

## Сводная дорожная карта

| Фаза | Действия | Срок | Стоимость |
|-------|---------|------|-----------|
| **0. Среда** | Git for Windows + Claude Code + pip install tools | День 1 | $0 (установка) |
| **1. Скилл** | Клонировать uditgoenka/autoresearch → `.claude/skills/` | День 1–2 | $0 |
| **2. Метрики** | Настроить ruff, mypy, pylint, radon; замерить baseline | День 2–3 | $0 |
| **3. Ручной тест** | Попросить Claude Code исправить 3 ошибки, проверить git revert | День 3–4 | ~$0.50 |
| **4. Первый цикл** | `/autoresearch` с метрикой ruff errors, 10–20 итераций | День 4–5 | ~$1–$2 |
| **5. Безопасность** | .claudeignore, pre-commit hook, рабочая ветка, лимиты | День 5 | $0 |
| **6. Масштабирование** | Добавить mypy → pylint → radon → композитную метрику | Неделя 2–3 | ~$5–$15 |
| **7. Автономный режим** | Ночные запуски headless с `--max-budget-usd`, Batch API | Неделя 3+ | ~$2–$8/ночь |

### Рекомендуемый порядок подключения метрик

Начинайте с самых быстрых и однозначных метрик, затем наращивайте сложность:

1. **Ruff lint errors → 0** (самая быстрая метрика, ~0.2 сек проверка)
2. **Ruff format** (автоформатирование, нулевой риск — стилевые изменения)
3. **Mypy type errors → 0** (требует больше «интеллекта» агента)
4. **Pylint score → 9.0+** (семантический анализ, медленнее)
5. **Radon CC ≤ 5** (рефакторинг сложных функций — самая трудная задача)
6. **Композитный балл** (объединение всех метрик в одно число)

---

## Что может пойти не так

**Рост контекста** — главная ловушка автономных циклов. Без `/compact` или перезапуска каждые 5–10 итераций стоимость одной итерации может вырасти в 10 раз. Решение: используйте отдельные headless-вызовы через PowerShell-скрипт — каждый вызов стартует с чистого контекста.

**Зацикливание «fix → break → revert»** — агент может бесконечно пытаться одно и то же изменение. В скилле Goenka это решается правилом «когда застрял — пробуй радикально другой подход» и логом прошлых попыток в TSV.

**Ложные улучшения** — агент может удалить код, чтобы уменьшить количество ошибок. Защита: добавьте в CLAUDE.md правило «не удалять функциональный код, только исправлять ошибки» и следите за тем, чтобы `git diff --stat` не показывал массовых удалений.

**Скилл AutoResearch от Goenka вышел 13 марта 2026** — то есть буквально вчера. Он очень новый (6 звёзд на GitHub), поэтому возможны баги. Рекомендуется иметь PowerShell-скрипт как запасной вариант для организации цикла.

Эта дорожная карта позволяет за **5 дней** перейти от нулевого опыта к работающему автономному циклу улучшения качества кода, а за **2–3 недели** — масштабировать его на все основные метрики Python-проекта при бюджете **$20–$50 в месяц** (план Pro + API для ночных запусков).