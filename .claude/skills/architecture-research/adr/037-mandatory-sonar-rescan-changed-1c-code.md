# ADR-037: Обязательный Sonar re-scan изменённого/добавленного 1С-кода (hard Stop-гейт)

**Дата:** 2026-06-23 · **Статус:** accepted (реализован, тесты PASS)
**Связь:** усиливает ADR-033 (Sonar remediation) и ADR-034 R6 (Clean-as-You-Code); встроен в
ADR-018 (mandatory pipeline) / ADR-035/036 (1С task-completion gate).

## Контекст
Мандат пользователя (2026-06-23): «изменённый И добавленный 1С-код обязательно прогонять через
SonarQube», закрепить **хард-гейтом** + память + доки/скиллы. Общий Quality-Gate оставлен **soft**
(ADR-033/034 R6): 57k легаси-issues в вендорной БСП завалили бы любой PR. Но это не противоречит
мандату: гейт применяет **Clean-as-You-Code к СВОИМ изменениям** (дельта по затронутым `.bsl` = 0
BLOCKER/CRITICAL), а не «весь QG зелёный». Раньше re-scan был ручным/по решению (ADR-033 §«запуск
ручной, не на каждую задачу») — теперь для затронутого кода обязателен.

## Решение
Хард-проверка `sonar_rescan` в Stop-гейте [`onec-task-completion-stop`](../../../.claude/hooks/onec-task-completion-stop.py)
(там же, где recall/capture/research — единый консолидированный блок). Компоненты:
- [`shared/sonar_rescan_state.py`](../../../.claude/hooks/shared/sonar_rescan_state.py) — единый
  контракт: детект изменённых/новых `.bsl` (git, осн.репо+сабмодули, фильтр `/src/` — scratch-`.bsl`
  в docs исключены) + read/write state + `evaluate(root, session_start)`.
- [`scripts/sonar_rescan_verify.py`](../../../scripts/sonar_rescan_verify.py) — verify: reachability
  → дельта по Sonar API (component существует? 0 BLOCKER/CRITICAL? анализ свежее правок?) → пишет
  `.claude/cache/onec-sonar-rescan-state.json`. Sonar-down → `skipped`. Порядок: сначала
  `run-sonar-analysis.ps1` (скан), потом этот скрипт (verify дельты).
- Гейт: при `config_edit` (правка 1С-кода в сессии) `evaluate` → блок если state нет (`missing`) /
  устарел (`stale`/`stale-scan`) / есть нарушения (`fail`) / не покрыты файлы (`uncovered`) / правки
  после скана (`edits-after`).

**Default-ON** (по мандату, не opt-in-env как ADR-035/036). Anti-deadlock (3 уровня):
opt-out `ONEC_SONAR_GATE_DISABLE=1`; Sonar-down → verify пишет `skipped` → `evaluate` ok; graceful
(исключение/нет контракта → ok). Выход всегда достижим — прогнать `sonar_rescan_verify.py`
(он ВСЕГДА пишет state, в т.ч. `skipped` при Sonar-down).

## Последствия
### Положительные
- Свой изменённый/добавленный код гарантированно прогнан через Sonar (CaYC), без блокировки на легаси.
- Контракт детекта `.bsl` един для verify и гейта (DRY) → нет рассинхрона «гейт блокирует на непроверенном».
- Контракт находок переиспользуем (state-файл), event в `gate-decisions.jsonl` (ADR-034 R3).
### Отрицательные / риски
- Внешняя зависимость (Sonar :9000 + токен) — снята reachability-skip.
- Блок на незакоммиченных чужих WIP-`.bsl` под `/src/` (они тоже «изменённый код») — снимается
  коммитом/stash или opt-out. Документировано.
- git-вызовы (осн.+сабмодули) на Stop при `config_edit` — timeout git 5s, только при правке 1С-кода.

## Альтернативы (отклонены)
- **Advisory-only** (как ADR-035 T1-T2) — отклонено: пользователь явно выбрал хард-гейт.
- **Жёсткий общий QG-блок** — отклонено (ADR-033): легаси-БСП завалит всё; нужен scope на свой код.
- **Opt-in-env (как ADR-036)** — отклонено: мандат = default-ON.

## Связанные файлы
- Код: `shared/sonar_rescan_state.py`, `scripts/sonar_rescan_verify.py`, `onec-task-completion-stop.py`
- Тесты: `tests/unit/test_sonar_rescan_state.py` (12, все ветки evaluate + фильтр /src/)
- Док: гл. 43.7 (Sonar) · скиллы implement-1c-task / run-1c-task / fix-sonar-task / code-verify
- Память: `feedback_1c_changed_code_sonar_mandatory`
