# Пайплайн · Этап 3 — Кодирование (gated)

Запусти **Этап 3** пайплайна (ADR-017): реализация по **одобренному** дизайну.
Вход: `02-design.md` (должен быть `done` + `approved`). Выход: код + `pipeline/<slug>/03-implementation.md`.

## Уточнение от пользователя (опц.):
$ARGUMENTS

---

## Шаги

0. **ГЕЙТ (hard).** Проверь готовность к кодированию:
   ```
   .venv/Scripts/python.exe .claude/hooks/shared/pipeline_state.py gate pl-code
   ```
   Если `ok=false` и `hard=true` — **СТОП**, выведи `reason` пользователю (нужно одобрить дизайн через
   `pipeline_state.py approve <slug>`) и не пиши код. Хук `pipeline-gate` блокирует и на уровне harness —
   это дублирующая защита (defense-in-depth).

1. **Вход.** Прочитай `pipeline/<CURRENT>/02-design.md` (+ `01-architecture.md` для контекста).

2. **Реализуй.** Делегируй кодирование субагенту `implementer` (`Agent(subagent_type="implementer")`)
   по точкам модификации из дизайна. Opus = декомпозиция задачи + ревью результата субагента
   (правило делегирования). Соблюдай существующие паттерны и стиль кодовой базы.

3. **Запиши артефакт** `pipeline/<slug>/03-implementation.md`:
   - **Что изменено** — список файлов + краткий diff-summary.
   - **Отклонения от дизайна** (если были) + причина.
   - **Открытые вопросы / что проверить на Этапе 4.**

4. **Закрой этап:**
   ```
   .venv/Scripts/python.exe .claude/hooks/shared/pipeline_state.py done <slug> 3 03-implementation.md
   ```

5. **Передай дальше.** Сообщи пользователю: «Этап 3 готов — `/pl-test`».
