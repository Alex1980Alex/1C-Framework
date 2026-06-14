# Пайплайн · Этап 4 — Тестирование

Запусти **Этап 4** (финальный) пайплайна (ADR-017): проверка реализации.
Вход: `03-implementation.md` + изменённый код. Выход: `pipeline/<slug>/04-testing.md`.

## Уточнение от пользователя (опц.):
$ARGUMENTS

---

## Шаги

1. **Вход.** Прочитай `pipeline/<CURRENT>/03-implementation.md` и определи изменённый код.

2. **Тестируй:**
   - Напиши/прогони тесты: `Skill('evaluation-benchmark')` для тест-дизайна/метрик;
     `pytest tests/ -m unit` для unit-гейта (см. [[feedback-pytest-unit-marker-gate]]).
   - Запусти **`Skill('code-verify')`** на изменениях (режим `bug-fix-validation` / `quality-review`).

3. **Запиши артефакт** `pipeline/<slug>/04-testing.md`:
   - **Тест-план** — что проверялось (из тест-стратегии дизайна, Этап 2).
   - **Результаты** — прогоны, pass/fail, метрики.
   - **Вердикт code-verify** — PASS / PARTIAL / FAIL + рекомендации.

4. **Закрой этап:**
   ```
   .venv/Scripts/python.exe .claude/hooks/shared/pipeline_state.py done <slug> 4 04-testing.md
   ```

5. **Финал.** Сообщи: «Пайплайн завершён. Артефакты: `pipeline/<slug>/01..04`. При желании закоммить
   артефакты + код.» Покажи итоговый `status` (`pipeline_state.py status`).
