# Hard-гейт: обязательный Sonar re-scan изменённого/добавленного 1С-кода (ADR-037)

Мандат пользователя (2026-06-23): изменённый И добавленный 1С-код обязан проходить SonarQube;
закрепить хард-гейтом + память + доки/скиллы.

## 1. Планирование
Общий QG soft (ADR-033/034 — легаси-БСП). Решение: применять Clean-as-You-Code к СВОИМ правкам
(дельта по затронутым `.bsl` = 0 BLOCKER/CRITICAL), хард-гейтом в существующем `onec-task-completion-stop`.
Recall: онек-гейт, ADR-035/036 паттерн. Research: сессия (рецепт Sonar, API).

## 2. Дизайн
3 компонента: общий контракт state (`shared/sonar_rescan_state.py`, DRY детект `.bsl`), verify-скрипт
(`scripts/sonar_rescan_verify.py`), hard-проверка в гейте. Default-ON при config_edit; anti-deadlock
(opt-out / Sonar-down→skip / graceful / выход через verify). Approved (ADR-037).

## 3. Кодирование
- `shared/sonar_rescan_state.py` — changed_bsl_paths (фильтр /src/), read/write/evaluate.
- `scripts/sonar_rescan_verify.py` — reachability → дельта по Sonar API → state.
- `onec-task-completion-stop.py` — sonar_rescan в hard_keys + message + opt-out + decision-log.

## 4. Тестирование
- 12 unit (`tests/unit/test_sonar_rescan_state.py`) — все ветки evaluate + фильтр /src/.
- ruff/compile чисто; гейт runtime-smoke exit 0; verify live-smoke PASS (3 .bsl, 0 BLOCKER/CRITICAL).
- code-verify reviewer: PARTIAL→fixed (R1 session_start=None / R2 stale-scan / R3 git-timeout) → PASS.

## Закрепление
ADR-037; память `feedback_1c_changed_code_sonar_mandatory`; CLAUDE.md; гл.43.7; скиллы fix-sonar-task,
implement-1c-task.
