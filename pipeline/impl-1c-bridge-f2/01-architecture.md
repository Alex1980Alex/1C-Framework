# F-2 — Планирование: гейт G4 (блок /implement-1c-task до approve дизайна)

**Срез:** B′ F-2. **Цель (G4):** `/implement-1c-task` блокируется, если дизайн 1С-задачи (этап 2, ANALYSIS-REPORT)
не `approved` — хард-чекпоинт «Дизайн→Кодирование» для 1С-маршрута (как pl-code в generic).

**Подход:** расширить существующий [`pipeline-gate.py`](../../.claude/hooks/pipeline-gate.py) (UPS, уже гейтит pl-code).
Логику 1С-гейта вынести в `pipeline_1c_bridge.gate_1c_implement(prompt)` (рядом с derive_slug — один slug-резолв).

**Семантика:** slug=`derive_slug(prompt)` → `load(slug)`; если 1С-пайплайн (title-метка F-1) И этап 2 не done+approved →
**HARD block** с подсказкой approve. Нет 1С-пайплайна / не-1С → **no-op** (не блокируем — нормальный поток: analyze создаёт пайплайн). best-effort (сбой → no-op).

**Граница:** только /implement-1c-task; opt-out `PIPELINE_GATE_DISABLE=1` (уже есть). Этап 4 — отдельно.
**Инварианты:** не трогаем generic pl-* гейт; best-effort; откат = revert ветки в pipeline-gate + функция.
**DoD:** unit (no-pipeline→ok, best-effort→ok) + live (не-approved→block, approved→allow); без регрессий.
