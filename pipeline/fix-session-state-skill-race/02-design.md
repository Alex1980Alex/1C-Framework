# 02 — Дизайн фикса

## 1. `shared/session_state.py` — корневой фикс

- **`_save_state` → ретрай `os.replace`**: до 6 попыток с паузой 20 мс на `PermissionError` (окно коллизии с читателем — микросекунды; бюджет ~120 мс при hook-timeout 3 с). Исчерпание — прежний `raise` (вызыватели деградируют как раньше).
- **`_mutate(fn)` — единая точка мутаций**: межпроцессный lock-файл `session-skills.lock` рядом со state (Windows `msvcrt.locking(LK_NBLCK)` / POSIX `fcntl.flock(LOCK_EX|LOCK_NB)` в retry-цикле ≤1 с; не взяли — работаем без лока, fail-open, не дедлочим хук) + **свежее чтение с диска** (мимо `_state_cache`) + `fn(state)` + save + обновление кэша.
- Все мутаторы переводятся на `_mutate`; читатели не меняются (atomic replace даёт консистентный снапшот).

## 2. `code-skill-enforcer.py` — defense-in-depth (self-heal)

Перед блоком Levels A/B/C: если state говорит «не активирован», сканировать **хвост транскрипта** (≤2 МБ) на `tool_use` `Skill` с требуемым именем скилла. Найден → дописать в state (`add_activated_skill`, self-heal) и пропустить. Ложных пропусков нет: пропускаем ровно при фактическом вызове `Skill('<требуемый>')` в сессии — тот самый контракт «activate then retry». Любой будущий сбой записи перестаёт быть ложным блоком.

## 3. Тесты (детерминированные, без таймингов)

`tests/unit/test_session_state_race.py`:
- retry: monkeypatch `os.replace` → 2 падения `PermissionError`, затем успех → `add_activated_skill` персистится (на старом коде — исключение, потеря).
- lost-update: прогреть кэш → внешним процессом (прямая запись файла) добавить скилл X → мутатором добавить Y → на диске оба (на старом коде X затёрт).
`tests/unit/test_code_skill_enforcer_transcript_fallback.py`:
- fake transcript c `tool_use Skill{skill: 1c-doc-research}` + пустой state → enforcer НЕ блокирует и дописывает state; без записи в транскрипте → блок (сабботаж-инвариант).

## Объём

2 модуля + 2 теста. Публичные API не меняются. Approve: прямой мандат пользователя «сделай анализ ошибок хука и исправь».
