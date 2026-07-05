# Этап 7: Документация — шаблон IMPLEMENTATION-PROGRESS.md

**Создать/обновить файл IMPLEMENTATION-PROGRESS.md** в той же папке docs/:

```markdown
# НОМЕР-ЗАДАЧИ — Прогресс реализации

## Статус: В работе / Завершено / Ожидает тестирования

Pipeline mode: Full | Full (no-BP) | Code-only | Read-only verify | Read-only research

## Выполненные точки модификации

### Точка N: Описание
- **Файл:** путь
- **Действие:** что сделано
- **Строки:** актуальные (из EDT-MCP)
- **Валидация запросов:** validate_query OK / исправлен (описание)
- **Ошибки EDT:** 0 / исправлены (описание)
- **bsl_analyze:** 0 ошибок / N предупреждений (список)
- **BP verification:** PASS (frames[0].lineNo=N) / SKIP (причина) / FAIL (детали)
- **Тест на данных:** пройден / ожидает / не требуется
- **Отклонения от ANALYSIS-REPORT:** нет / описание

## Debug session (если режим Full)

- session_id: <UUID>
- session_summary: вывод `debug_session_summary(format="markdown")` — счётчики BP fire, eval, UI+ retries
- Regression diff vs prev (если был baseline): verdict, изменения метрик

## Результаты тестирования
- Тест X.Y: PASS / FAIL / SKIP (причина)

## Открытые вопросы (если есть)

<!-- debug_session_id: <UUID последнего успешного прогона; читается следующим запуском /implement-1c-task для regression diff Этапа 5.y> -->
```

**Правила footer'а:**
- `debug_session_id` записывается ТОЛЬКО при успешном завершении всего pipeline (Этап 5.x PASS, Этап 6 PASS).
- При REGRESSION verdict в Этапе 5.y — footer НЕ перезаписывается (baseline сохраняется для следующей попытки исправления).
- Если режим не Full и BP-verification была SKIP — footer не создаётся (нет валидной session для diff).
