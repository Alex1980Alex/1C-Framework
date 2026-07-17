# 04 — Тестирование

## Прогоны

- `tests/unit/test_session_state_race.py` — 6 тестов: retry переживает 2×PermissionError; исчерпание ретраев re-raise (контракт деградации); внешняя запись другого процесса НЕ затирается мутацией (fresh-read); stale-лок взламывается и чистится; свежий чужой лок → fail-open (мутация проходит, чужой лок не тронут); нет остатков `.tmp`/`.lock`.
- `tests/unit/test_code_skill_enforcer_fallback.py` — 4 теста: блок без активации и транскрипта (сабботаж-инвариант); fallback по транскрипту → allow + self-heal state; активация в state работает без транскрипта; ЧУЖОЙ Skill в транскрипте не открывает гейт.
- Регресс: `test_session_state_atomic.py` (3) + `test_hook_invocation_logging_p0.py` (11) — зелёные. Итог: **24 passed**, ruff clean, compileall OK.

## Сабботаж-проверка (обязательная)

Первая попытка (git stash) оказалась пустой — auto-git-save уже закоммитил фикс в HEAD, stash нечего было снимать → тесты гоняли фикшенный код. Честный прогон: файлы взяты из **pre-fix коммита** (`cb609c6ad`) → 3 ключевых теста **FAILED** (retry / lost-update / fallback), фикс-версии восстановлены из HEAD. Тесты пиннят инвариант, не реализацию.

## Read-only ревью (субагент code-verify)

**ВЕРДИКТ: PASS.** Дедлоков нет, публичный контракт сверен побайтово со старой версией, потребители всех 14 мутаторов проверены, transcript-fallback fail-safe. Замечания и их судьба:

- **№1 major (pre-existing, НЕ регрессия диффа) — ИСПРАВЛЕН:** recovery-ветка `_load_state` при ошибке ЧТЕНИЯ персистила пустой state (reader-side erase — стирала чужие activated_skills/task_protocol). Фикс: read-retry (`_READ_RETRIES=3`×20мс на транзиентный OSError; JSONDecodeError/FileNotFoundError — сразу fresh) + **никогда не персистить на read-пути** (файл лечит первая мутация). Симметрично упрочнён `_read_disk_fresh`. Пин: `test_reader_error_does_not_erase_state` (на старом коде красный — файл перезаписывался).
- **№2 minor (TOCTOU break-in stale-лока) — комментарий добавлен** (best-effort by design; Windows: живой держатель невзламываем — unlink открытого файла даёт PermissionError).
- **№7 nit — module-level `reset_session` добавлен** (+`__all__`); ImportError в `test_skill_routing.py::test_29` устранён. Побочная находка: весь класс `TestSkillRouterSessionDedup` (26/28/29/30) — **pre-existing гниль**, падает даже test_26 без всякой связи с session_state (ожидания против роутера до Honest Eval 2026-06-13; test_30 ищет state в `.claude/cache/` вместо `data/`); файл БЕЗ unit-маркера → вне CI-гейта. Долг роутер-тестов, вне скоупа.
- **№11 nit — шапка энфорсера обновлена** (v2.2.0, Updated 2026-07-17).
- **№3/№4/№5 minor — приняты как риски:** worst-case двойной мутации ~1.5с < таймаута 3с (реальные удержания — мс); потерянный `record_skill_checked` фолбэка не имеет (residual, transcript-fallback покрывает только активацию скилла); fallback засчитывает Pre-записанный tool_use — идентично state-пути (не расширение гейта). №6/№8/№9/№10 nit — зафиксированы, без правок.

Финальный прогон после пост-ревью правок: **25 passed** (моя связка) + ruff clean.
