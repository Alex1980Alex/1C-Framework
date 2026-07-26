# fix-blocked-write-not-edit — заблокированный гардом вызов ≠ правка кода

**Дата:** 2026-07-26 · **Инцидент:** ложный блок завершения `[GATE-ORCHESTRATOR] правки кода
без пайплайна (ADR-018)` + фантомная mandatory-задача «Запустить code-verify для изменённого
кода» в сессии, где ни один файл не записан (`git status --ignore-submodules=all` чист).

## 1. План

Корень: один `Write`, отклонённый `TaskProtocolEnforcer`, оставил в
[`data/hook-invocations.jsonl`](../../data/hook-invocations.jsonl) **12 Pre-записей** (по одной
на хук цепочки — блокирующий отдаёт `decision:"block"`, при котором цепочка доходит до
логгера). Два потребителя читали их как факт правки:

- [`pipeline-protocol-stop.py`](../../.claude/hooks/pipeline-protocol-stop.py)
  `_session_writes_and_start` — «была правка» → требование пайплайна (и через
  `gate_policies.build_context` тот же сигнал у живого `gate-orchestrator-stop`);
- [`code-verify-reminder.py`](../../.claude/hooks/code-verify-reminder.py) на `PreToolUse`
  создавал mandatory-задачу «на намерение».

Тот же класс, что `blocked` в tool-health (roadmap 260718 N-P4.3): отклонённый вызов не
исполнялся — вычитать его надо и в enforcement-слое, а не только в метриках.

## 2. Дизайн

- Предикат блокировки — **single-source** `is_guard_block` в
  [`scripts/tool_effectiveness.py`](../../scripts/tool_effectiveness.py); report-слой
  `analyze_tool_health.guard_blocks_by_tool` делегирует ему (было продублировано инлайном).
  `_take_block` → публичный `take_block` (расходуемое сопоставление 1:1 нужно обоим слоям).
- Правка = **canonical** Pre (`category="tool_call"`, пишет `tool-invocation-logger`), не
  объяснённая block-записью того же инструмента в той же сессии (±`BLOCK_MATCH_SEC=5с`).
- **Fail-closed:** нет canonical-записей / битый `ts` / нет модуля-хелпера → считаем правкой
  как раньше. Гейт не должен ослабнуть из-за пробела в телеметрии.
- `code-verify-reminder`: задача только на `PostToolUse` (Post приходит лишь у исполнившегося
  вызова). Pre-регистрация была workaround #6305 — замер 2026-07-26 по логу: Post 1460 vs
  Pre 1540 = **95% доставки**, workaround устарел.
- Паритет оркестратора — by construction: `build_context` зовёт ту же `pp._session_writes_and_start`.

## 3. Реализация

`scripts/tool_effectiveness.py` (+`is_guard_block`, `take_block`) ·
`scripts/analyze_tool_health.py` (делегирование) ·
`.claude/hooks/pipeline-protocol-stop.py` (вычет + импорт хелпера через `sys.path.append`) ·
`.claude/hooks/code-verify-reminder.py` (Post-only).

## 4. Тест

[`tests/unit/test_blocked_write_not_edit.py`](../../tests/unit/test_blocked_write_not_edit.py)
— 16 тестов: живая 12-записевая цепочка блока → не правка; правка после блока / 2 canonical на
1 блок / чужая сессия / чужой тул / вне окна → правка; fail-closed ветки (нет canonical, битый
`ts`, нет хелпера) → правка; parity `is_guard_block` ↔ `guard_blocks_by_tool`; Pre→нет задачи,
Post→задача, не-код→нет задачи.

Прогон: 16 passed · 349 gate/pipeline · 180 tool-health/obs · ruff clean.
**Саботаж:** отключение вычета краснит ровно `test_blocked_write_is_not_an_edit`; снятие
Post-гарда — ровно `test_pre_tool_use_does_not_create_task`.
