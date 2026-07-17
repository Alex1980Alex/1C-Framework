# 01 — Анализ: потеря активации Skill в session-state

## Инцидент (транскрипт пользователя, 2026-07-17)

1. `Skill('1c-doc-research')` → «Successfully loaded skill».
2. Следующий `Edit` (Form.form с текстом запроса `ВЫБРАТЬ|КОЛИЧЕСТВО|...`) → `code-skill-enforcer` блокирует: «SKILL REQUIRED: '1C Query Language' (1c-doc-research)».
3. Прямое чтение `data/session-skills.json`: в `activated_skills` есть `implement-1c-task`, но **нет** `1c-doc-research` — активация не записалась.
4. Второй `Skill('1c-doc-research')` → Edit проходит.

## Механизм записи активации

- `PreToolUse:Skill` запускает **параллельно 4 hook-процесса**: `approval-gate`, `task-protocol-observer`, `skill-usage-metrics`, `tool-invocation-logger`.
- Писатель один — `task-protocol-observer.py`: `record_skill_checked()` + `add_activated_skill(skill)` (две последовательные записи файла).
- Читатели в тот же момент: `skill-usage-metrics` (`get_prompt_id()` → `open(STATE_FILE)`), потенциально `approval-gate`/логгер.
- Ошибки observer глотает: `except Exception: pass` (graceful degradation).

## Корневые причины (обе в `shared/session_state.py`)

**A (инцидент): `os.replace` без ретрая под Windows-читателем.**
`_save_state` пишет tmp и делает `os.replace(tmp, STATE_FILE)`. На Windows замена файла, который другой процесс держит открытым на чтение (CPython `open()` — без `FILE_SHARE_DELETE`), даёт `PermissionError`. Observer его глотает → активация **тихо теряется**. Одноразовость и успех повторной попытки полностью совпадают с наблюдаемым.

**B (латентный, тот же модуль): lost-update между процессами.**
Мутаторы делают read-modify-write поверх **процессного кэша** (`_state_cache`) без межпроцессного лока (`threading.Lock` не защищает от параллельных hook-процессов). При параллельных писателях (UserPromptSubmit — ~19 хуков: `skill-router` пишет prompt_id/recommendations/router_fired, классификатор — task_protocol) последний писатель затирает чужие изменения. Фикс 2026-06-30 (atomic tmp+replace) закрыл только torn-write corruption — не потерю обновлений и не ретрай replace.

## Прочее из транскрипта (не баги)

- `[1C-STATE-FIRST]` — advisory по дизайну (правка 1С-файла без pipeline-state), не блокировал.
- Блок по паттерну `ВЫБРАТЬ|...` на `.form` — корректная работа Level A (в Form.form лежит текст запроса динсписка); расширение `.form` не в exempt-списке, и это правильно.
