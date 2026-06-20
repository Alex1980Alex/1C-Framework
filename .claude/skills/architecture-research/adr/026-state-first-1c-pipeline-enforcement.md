# ADR-026: State-first enforcement пайплайна 1С (вход через машинерию, не задним числом)

**Дата:** 2026-06-20
**Статус:** accepted
**Исследование:** [../cache/agentic-pipeline-workflow-enforcement-2026.md](../cache/agentic-pipeline-workflow-enforcement-2026.md)

## Контекст

Ретроспектива сессии GKSTCPLK-2521 (залоговые цены) выявила 4 отклонения от парадигмы пайплайна 1С (гл. 43.5):

1. **pipeline-state заведён задним числом** (на Stop, чтобы разблокировать завершение), не на входе — инверсия §0.9.
2. **Методики обойдены** (`implement-1c-task`) — прямой `edt-mcp`/`1c-mcp-crud`/`bsl-development`.
3. **Сквозные петли** (recall/research/capture, §5/§6) выполнены под принуждением на Stop, не по ходу.
4. **G4** (approve дизайна перед кодом) неформален (прошёл по «да» пользователя, не как гейт).

**Корень:** работа велась чат-реактивно, без ВХОДА через машинерию пайплайна (команды → preflight → state); enforcement (`pipeline-protocol-stop`, ADR-018) срабатывал ТОЛЬКО на Stop — слишком поздно, вся задача уже сделана вне состояния.

**Best-practice (GitHub 2025-2026, см. research-cache):** Spec Kit (80k★, gates+constitution), Kiro (**steering+hooks принуждают, gate-at-creation**), BMAD (48k★, role=методика), LangGraph/Burr (state machine + HITL approval + checkpoints), agentic-guardrails (input→plan→output **по ходу**). Сводно: **state-first + gate-на-создании + роль=методика + петли по ходу**.

## Решение

**(A) Алгоритм «1С-задача строго по пайплайну»** (для Claude, на каждое сообщение) — закреплён в гл. 43.5 и памяти [[feedback-1c-pipeline-state-first]]:
вход (детект + контекст: новая/существующая, **сомнение → спросить**) → **state-first** (войти через `/run-1c-task` | `/analyze-1c-task`; preflight заводит state) → **этапы = методики** → **G4 формально** → **петли по ходу** → follow-up = advance (не рестарт).

**(B) Структурное усиление — PreToolUse-хук `onec-state-first-guard`.** Переносит проверку «правка 1С без пайплайна» с **Stop** на **первую 1С-правку** (gate-at-creation, паттерн Kiro/Spec-Kit; guardrails plan-layer). При `Write|Edit|MultiEdit` файла `.bsl/.mdo/.form` под `configuration/`/`ИБTransport` БЕЗ активного 1С-pipeline-state (`title startswith "1С-задача (" ∧ current_stage < 5`) → **advisory** `system_message` «войди через `/run-1c-task` / заведи state». **Никогда не блокирует** (анти-deadlock, §0.6); opt-out `ONEC_STATE_FIRST_DISABLE=1`; graceful.

Регистрация — `settings.local.json` (локально, как `tdd-guard`; team `settings.json` НЕ тронут — cautious rollout, hard-block — только после валидации).

## Последствия

### Положительные
- «Дисциплина входа» из памяти → **enforced инвариант**: напоминание в момент правки, а не постфактум на Stop. Закрывает deviation #1 структурно.
- Симметрично `tdd-guard` (advisory PreToolUse, opt-out) — знакомый паттерн, низкий риск.
- #2/#3/#4 закрываются поведенчески (алгоритм + память [[feedback-1c-pipeline-state-first]]).

### Отрицательные / риски
- PreToolUse на каждый Write/Edit — минимизировано early-return по расширению (не-1С → мгновенно None).
- Advisory ≠ hard-block: можно проигнорировать (by design; hard-block — после недели валидации, как tdd-guard 4.3).
- «Активный pipeline» — эвристика best-effort (title-prefix + stage<5); ложное «нет активного» → лишний нудж (не блок).

## Альтернативы
- **Hard-block на первой 1С-правке** — отклонено: deadlock-риск, противоречит §0.6 «сомнение → спрашивать, не запрещать».
- **Только Stop-gate (статус-кво)** — отклонено: поздно (вся работа уже вне состояния).
- **Сразу в team `settings.json`** — отклонено: cautious rollout (сначала локально, как tdd-guard).

## Связанные файлы
- [`.claude/hooks/onec-state-first-guard.py`](../../../hooks/onec-state-first-guard.py) · [`tests/unit/test_onec_state_first_guard.py`](../../../../tests/unit/test_onec_state_first_guard.py) · `settings.local.json` (регистрация PreToolUse)
- Парадигма — [гл. 43.5 Сквозная карта](../../../../docs/framework%20documentation/43_ПАЙПЛАЙН_1С/43.5_СКВОЗНАЯ_КАРТА.md); research — [cache](../cache/agentic-pipeline-workflow-enforcement-2026.md); связанные — ADR-017/018/019.
