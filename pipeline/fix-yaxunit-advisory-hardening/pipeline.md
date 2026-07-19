# fix-yaxunit-advisory-hardening (2026-07-19)

Глубокий анализ реализации рек.3 (YAxUnit-смоук advisory, roadmap 260718 1C tooling audit) + хардинг.

## Найдено (живой тест + грамматика bsl-parser)
1. **БАГ (FN):** async-префикс BSL = `Асинх`/`Async` (BSLLexer.g4), а не «Асинхронная» — async-методы не матчились заголовком вовсе.
2. **БАГ (FN):** кириллица-only ключевые слова — англоязычный синтаксис (Procedure/Export/EndProcedure) невидим.
3. **БАГ (FP):** `П = "Экспорт"` в сигнатуре давал ложный экспорт (литералы не вырезались).
4. **Слабость знаменателя:** живой замер — 159 чужих WIP `.bsl` в сабмодулях → `yaxunit_applicable`/`impact_applicable` ≈ всегда True; «честный знаменатель» вырождался.
5. **Перф:** worst-case (нет экспортных правок) = 159×2 git-вызова в Stop-хуке под таймаутом.

## Фиксы
- `onec_change_scope.py`: двуязычные regex + `Асинх`, вырезание строковых литералов, `session_paths`-сужение (`_session_tail`, fallback полный скан), кап `_MAX_FILES_SCAN=50` (sorted).
- `onec-task-completion-stop.py`: сбор `sig["bsl_paths"]` из транскрипта (Write/Edit + MCP-арги на .bsl) → `_impact_applicable(session_paths)`.

## Верификация
- 5 новых unit; саботаж на pre-fix `4e7f4eb5e` — все красные; 384 passed; ruff clean.
- Живой прогон: fallback 1.1s / narrowed 1.0s; точность спанов на реальном модуле (907 методов): 12 «дельт» = легитимные многострочные сигнатуры, FP 0.
- code-verify reviewer PASS (рек.1 применена).
