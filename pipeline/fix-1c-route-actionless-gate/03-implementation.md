# 03 · Кодирование

## Изменения (3 точечные правки)

### 1. `.claude/hooks/shared/pipeline_1c_bridge.py` — гейт `actionless`
В `route_1c_task`, confident-ветка, перед simple→auto:
```
actionless = comp == "simple" and not _TASK_VERB.search(prompt) and not eff.get("signals")
out["actionless"] = actionless
if actionless: flow = "ask_flow" + reason "1С-контекст без названного действия…"
```
Ключ `actionless` добавлен во ВСЕ возвраты (none / ask_1c / confident) — наблюдаемость по образцу
`non_1c_context`.

### 2. `.claude/hooks/shared/pipeline_1c_bridge.py` — расширение `_TASK_VERB`
Добавлены частые глаголы со start-`\b`: `замен|помен|переписа|перепиш|передела|обнов|переимен|поправ`.

### 3. `.claude/hooks/onec-task-input.py` — сообщение потребителя
В ветке `flow=="ask_flow"` подветка `r.get("actionless")` → «действие не названо → спроси, что сделать»
(порядок elif: actionless проверяется раньше общего ask_flow).

## Известное ограничение (тех-долг, не блокер)
Стем-матч `_TASK_VERB` (общесловарное свойство, не только новых основ) ловит отглагольные
существительные: `\bобнов`→«обновление», `\bзамен`→«заменитель», `\bпоправ`→«поправка». Хвостовая
`\b` неприменима (отрезала бы и сами глаголы: `замени`/`заменить`); чистое решение — negative-lookahead
по суффиксам или POS-слой — вне scope. Blast-radius мал: глагол засчитывается в детект лишь с 1С-сигналом
(не ломает is_1c), а эффект на гейт — крайне редкий `confident+simple+отглагольное-сущ → flow=auto`
(тот же безопасный класс, что был, на узком триггере). Кандидат на отдельную Находку при появлении
реального FP.

## Compile/import
`py_compile` обоих файлов — OK; AST-parse `onec-task-input.py` — OK.
