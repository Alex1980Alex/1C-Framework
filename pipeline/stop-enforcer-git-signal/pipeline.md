# Pipeline: stop-enforcer-git-signal

> Компактный артефакт (ADR-018) — medium-задача в один файл-хук + unit-тест.
> Задача чётко специфицирована пользователем («сделай git-detection второй сигнал»).

## 1. Планирование (архитектура)

**Проблема.** Stop-хук [`pipeline-protocol-stop.py`](../../.claude/hooks/pipeline-protocol-stop.py)
детектит «была правка» только по PreToolUse-событиям `Write|Edit` из `data/hook-invocations.jsonl`.
`MultiEdit`/`NotebookEdit` не имеют PreToolUse-матчера в `settings.json` → их правки не логируются →
enforcer их не видит (документированный fail-safe недо-блок).

**Решение пользователя (выбрано).** Добавить в Stop-enforcer **второй сигнал** «была правка» через
`git status` + mtime, независимый от инструмента. НЕ трогать `settings.json` (чтобы на
MultiEdit/NotebookEdit не навешивались побочно другие PreToolUse-хуки: task-protocol-enforcer,
z-ai-write-guard и т.д.).

**Отвергнутая альтернатива.** Добавить `MultiEdit|NotebookEdit` в существующий PreToolUse-матчер —
побочка: эти инструменты начнут триггерить весь PreToolUse-chain. Цена > выгоды.

## 2. Дизайн реализации

Новая функция `_git_session_edit(start) -> bool` — ИЛИ-сигнал к существующему `had_write`:

- `start is None` → `False` (нет привязки → fail-safe, без deadlock).
- `git -c core.quotepath=false status --porcelain --ignore-submodules=all` (cwd=PROJECT_ROOT, timeout=5).
  - `core.quotepath=false` → кириллические пути литералом (UTF-8), не escape (память проекта).
  - `--ignore-submodules=all` → сабмодульный pointer-drift (configuration/…, ИБ…/Конфигурация) не шумит + быстрее.
- Для каждой записи: парс пути (`line[3:]`, для rename `old -> new` берём `new`).
- **Denylist** `_GIT_SKIP = {"docs/wiki/log.md"}` — авто-пишется `session-memory-save` (Stop, ПОСЛЕ нас);
  иначе на повторном Stop-проходе git-сигнал ложно сработал бы в чистом вопросе.
- Только **обычный файл** (`is_file()`); сабмодуль/каталог → пропуск.
- Считаем правкой, если `st_mtime >= start.timestamp()` → правка случилась **за** сессию.
  - Корректность времени: лог-`ts` = `datetime.now().isoformat()` (naive-local), `st_mtime` = epoch;
    `naive.timestamp()` трактует как local → одна шкала. Pre-session dirty (mtime < start) отсекается.
- Любая ошибка git/stat → `False` (graceful degradation, никогда не блок ложно).

**Почему mtime-bound обязателен:** «голый» git-dirty ловил бы и pre-session грязь (незавершённая
прошлая сессия) → ложный блок чистого вопроса = deadlock. Привязка к `start` это закрывает.

**Wiring** (`execute`): `if not had_write: had_write = _git_session_edit(start)` — ПЕРЕД `if not
had_write: return None`. `_pipeline_used_since` короткозамыкает раньше блока, так что dirty
pipeline-артефакты этой сессии ложного блока не дают.

## 3. Кодирование

- `.claude/hooks/pipeline-protocol-stop.py`: `import subprocess`; `_GIT_SKIP`; `_git_session_edit`;
  wire-in; обновлён docstring + комментарий про MultiEdit/NotebookEdit gap (теперь закрыт).

## 4. Тестирование

- `tests/unit/test_pipeline_protocol_git_signal.py` (`@pytest.mark.unit`, importlib-load хука,
  monkeypatch `subprocess.run`+`PROJECT_ROOT`, реальные tmp-файлы с управляемым mtime) — **9 PASS**:
  modified-in-session→True; pre-session→False; denylist→False; start=None→False (git не зван);
  git rc!=0→False; submodule/dir→False; rename→dest path; untracked collapsed dir свежий→True;
  untracked collapsed dir pre-session→False.
- CI-parity: `ruff check` + `compileall` на изменённом хуке (clean); `pytest -m unit` (9/9).
- Live smoke против реального репо: start=1ч назад→True, start=будущее→False, None→False.
- Verify: `Skill('code-verify')` → reviewer-субагент **PASS** (bug-fix + quality-review).
  Находка F-1 (collapsed untracked dir, fail-safe FN) — **закрыта** доп. веткой `path.endswith("/")`.
