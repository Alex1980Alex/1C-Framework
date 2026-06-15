# B′ хвост — Тестирование (DoD пройден)

| Пункт | DoD | Результат |
|---|---|---|
| общий | unit | **17 passed** (+регрессия **47 passed** -k pipeline/tool_usage) |
| общий | ruff / compile / settings.json | All passed / OK / onec-task-input зарегистрирован |
| **F-1.6** | live | `.run-state` partial→этап4 **pending**; all-passed→этап4 **done** (+systemMessage) |
| **W** | live | `--session <sid>` → реальный отчёт (Edit 977 / Bash 648 / Write 646 / Skill 77, 0 ошибок); `--rollup` OK; `data/` gitignored |
| **input** | live | «исправь ошибку гкс_… проведении» → **T2 + протокол V.6** (ASK/folder/сжато); non-1С → пусто |

**Вердикт: 3 пункта DONE.** F-1.6 закрывает этап 4 по зелёным тестам; W даёт per-task отчёт + cross-task агрегацию
эффективности (на реальном логе); input-ingestion инъектит V.6-дизамбигуацию при 1С-задаче из чата. Каждый обратим независимо.

**Граница (честно):** input-ingestion — инъекция протокола (ASK/folder/prior-load выполняет Claude по подсказке), авто-создание
папки/мультимодальный Read — операторская дисциплина (память `project-1c-task-input-taxonomy`); W-quality (✓/⚠/✗) авто из
error% + слот `_заметка_` для ручной оценки.
