# 02 — Дизайн

## C: валидатор `scripts/lint_1c_artifacts.py`
`lint_text(text, kind)` → {kind, score, ok, present, missing} по regex **контент-маркеров** (не голым `## N` —
те матчат любую секцию). Core-секции: ANALYSIS (Требования[REQ]/Объекты[MODIFIED]/Механизм/Точки/Риски/Тест-план/
Резюме-Маршрут/МЕТАДАННЫЕ) · IMPL (Статус/Выполненные/Отклонения/Тестирование/Коммит-МЕТАДАННЫЕ). `ok = score≥70 &
len≥200`. CLI `--json/--kind`, exit 0 (advisory). LENIENT — толерантен к вариациям (bugfix Root Cause, мелкая задача).

## D: advisory-проводка `pipeline-1c-advance._completeness_note`
На запись ANALYSIS/IMPLEMENTATION → грузит валидатор collision-immune (importlib.spec) → при `not ok` И
score≥30 («созревший, но неполный») возвращает нудж в system_message. **Никогда не блок** (PostToolUse advisory),
best-effort try/except, opt-out `ARTIFACT_LINT_DISABLE=1`.

## B: SKILL run-1c-task — шаги 2/5: «выполняй методику ЦЕЛИКОМ, не конспектируй» + чеклист обязательных секций + self-check валидатором.
## A: 2567 ANALYSIS/IMPLEMENTATION перегенерированы по §1-§11 / полному шаблону (реальное содержимое Подсолнечника).

## Инвариант (анти-deadlock): валидатор ВСЮДУ advisory. H7-гард остаётся единственным условием продвижения.
## Approved: пользователь (AskUserQuestion: A+B+C+D).
