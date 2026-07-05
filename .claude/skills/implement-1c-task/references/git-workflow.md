# Этап 8: Git commit — полный workflow

## Структура репозиториев

Layout — **трёхуровневый**, при этом level 2 это **обычная директория** main repo (не git-репо, не submodule). Подтверждено 2026-05-07 через `git ls-files --stage` и инспекцию `.git/` в каждой папке цепочки.

```
Level 1 — MAIN repo (.git здесь)
C:\1С-Framework\
│
├── configuration/                                 ← Level 2: обычная подпапка main, БЕЗ своего .git/
│   ├── 260304_GKSTCPLK-2182…/                     ← Level 3: SUBMODULE (gitlink in main)
│   │   ├── .git                                   ← gitlink-файл (содержимое = "gitdir: ...")
│   │   └── docs/<task>/IMPLEMENTATION-PROGRESS.md
│   └── 260416_GKSTCPLK-2368…/                     ← Level 3: SUBMODULE (gitlink in main)
│
├── ИБTransportManagementDevelop/                  ← Level 2: обычная подпапка main, БЕЗ своего .git/
│   └── Конфигурация/                              ← Level 3: SUBMODULE (gitlink in main)
│       ├── .git                                   ← gitlink-файл
│       └── src/.../*.bsl                          ← BSL-исходники (правит EDT-MCP)
│
├── external/1c_mcp/                               ← обычно untracked в main
└── …
```

**Ключевые факты:**
- **Level 1 (main repo):** единственный репозиторий с настоящим каталогом `.git/` в корне. Все gitlink'и хранятся в индексе main.
- **Level 2 (`configuration/`, `ИБTransportManagementDevelop/`):** просто директории — `git rev-parse --is-inside-work-tree` внутри них всё ещё показывает main, своего `.git/` НЕТ. Сюда нельзя `cd` и сделать локальный коммит — это будет коммит в main.
- **Level 3 (`configuration/<TaskFolder>/`, `ИБTransportManagementDevelop/Конфигурация/`):** submodule'ы — отдельные git-репозитории со своим `.git`-указателем (gitfile), своей историей и своим `HEAD`.
- В индексе main путь submodule хранится **цельным** (со слешем): `"configuration/<TaskFolder>"` и `"ИБTransportManagementDevelop/Конфигурация"`. Это и есть аргумент для `git add` при bump'е gitlink'а.
- `git add ИБTransportManagementDevelop` (без `/Конфигурация`) — **другая** операция: индексирует level-2 директорию как контент main, что обычно нежелательно (см. Diagnostic ниже).
- Промежуточного git-репо между level 1 и level 3 нет (в отличие от ошибочного описания v2.5.0). Поэтому шага «commit gitlink в middle repo» в этом pipeline не существует.

## Шаги

1. **Submodule с BSL-кодом** (`ИБTransportManagementDevelop/Конфигурация`):
   ```bash
   git -C "ИБTransportManagementDevelop/Конфигурация" add <specific_file_path>
   git -C "ИБTransportManagementDevelop/Конфигурация" commit -m "feat(НОМЕР-ЗАДАЧИ): краткое описание"
   ```
   ⚠ **НЕ использовать `git add -A`** — submodule может содержать чужой dirty state.
   ⚠ **НЕ использовать `git add <submodule-dir>`** в родителе — git попытается проиндексировать **untracked файлы внутри** (включая длинные пути Windows → fatal: filename too long).

2. **Submodule с документацией** (`configuration/<TaskFolder>`) — закоммитить IMPLEMENTATION-PROGRESS.md:
   ```bash
   git -C "configuration/<TaskFolder>" add "docs/<task>/IMPLEMENTATION-PROGRESS.md"
   git -C "configuration/<TaskFolder>" commit -m "docs(НОМЕР-ЗАДАЧИ): add implementation progress"
   ```

3. **Main repo** — обновить оба gitlink'а (по одному коммиту на submodule или одним коммитом сразу):
   ```bash
   git add "ИБTransportManagementDevelop/Конфигурация"
   git commit -m "chore(НОМЕР-ЗАДАЧИ): bump Конфигурация submodule ref"

   git add "configuration/<TaskFolder>"
   git commit -m "chore(НОМЕР-ЗАДАЧИ): bump configuration submodule ref"
   ```
   Здесь `git add <submodule_path>` — **корректно**: git распознаёт submodule entry и обновляет только gitlink, не содержимое.

**Итого:** одна задача = до 4 коммитов в 3 репозиториях (BSL submodule, docs submodule, main ×2 gitlink). Если правка только в одном из submodule — соответствующая половина пропускается.

## Git identity без `git config`

CLAUDE.md запрещает `git config` (включая локальный). Если submodule наследует identity от родителя — коммит проходит. Если в submodule пусто — коммит падает с `fatal: unable to auto-detect email address`. Решение — **per-command override**:

```bash
git -c user.name="Имя" -c user.email="email@example.com" commit -m "..."
```

Эти `-c` действуют только в рамках одной команды и **не пишутся** в `.git/config`. Identity берётся из main repo (`git config user.name` + `git config user.email`).

## Diagnostic: подтвердить 3-уровневый layout перед коммитом

Шаг 1 — убедиться что **level 3** (submodule) действительно зарегистрирован в индексе **level 1** (main):

```bash
git ls-files --stage "ИБTransportManagementDevelop/Конфигурация"
# ожидается: 160000 <hash> 0  ИБTransportManagementDevelop/Конфигурация
git ls-files --stage "configuration/<TaskFolder>"
# ожидается: 160000 <hash> 0  configuration/<TaskFolder>
```

Mode `160000` = gitlink (submodule). Если строка пуста или mode ≠ `160000` — submodule не зарегистрирован, остановиться и сверить с пользователем (вероятно сломан `.gitmodules` или рабочий tree разошёлся с индексом).

Шаг 2 — убедиться что **level 2** (`configuration/`, `ИБTransportManagementDevelop/`) — действительно простая директория, а не самозванец:

```bash
test -d "ИБTransportManagementDevelop/.git" && echo "АНОМАЛИЯ: level 2 имеет свой .git" || echo "OK: level 2 — обычная директория"
test -d "configuration/.git" && echo "АНОМАЛИЯ: level 2 имеет свой .git" || echo "OK: level 2 — обычная директория"
```

Ожидание: `OK` для обоих. Если у level-2 директории появился собственный `.git/` — это другой layout (как ошибочно описывала v2.5.0), и git-flow из шагов 1-3 надо переcмотреть отдельно.

Шаг 3 — `git status` в main: типичный `m configuration/<TaskFolder>` или `m ИБTransportManagementDevelop/Конфигурация` (lowercase `m` = submodule modified content) — **нормально**, ожидается перед bump'ом gitlink'а. А вот `M ИБTransportManagementDevelop` (uppercase, без `/Конфигурация`) — **аномалия**: значит внутри level-2 директории появились трекаемые main'ом файлы вне зарегистрированного submodule. Не bump'ить, разобраться сначала.

**⚠ Windows + Cyrillic submodule paths (`ИБTransportManagementDevelop/Конфигурация`):** по умолчанию `core.quotepath=true`, и git выводит кириллицу как octal-escape (`"\320\230\320\221..."`). Это ломает парсинг `git status --porcelain` в скриптах и затрудняет визуальную проверку. CLAUDE.md запрещает `git config` (включая локальный), поэтому решение — **per-command override**:

```bash
git -c core.quotepath=false status --short
git -c core.quotepath=false ls-files --stage "ИБTransportManagementDevelop/Конфигурация"
```

Эти `-c core.quotepath=false` действуют только в рамках одной команды и **не пишутся** в `.git/config`. Без флага кириллические пути нечитаемы. См. memory `git-porcelain-parsing` для деталей парсинга.
