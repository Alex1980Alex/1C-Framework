---
name: analyze-1c-research
description: >
  Запуск трёхагентного анализа задачи 1С (Executor + Reviewer + Comparator).
  Итеративный цикл с автоскорингом до достижения целевого балла.
version: 1.0.0
updated: 2026-03-21
tags: [1c, analysis, autoresearch, three-agent]
commands:
  - /analyze-1c-research
---

# Analyze-1C-Research — трёхагентный анализ задачи 1С

## Запуск

При вызове `/analyze-1c-research <path-to-task.md>`:

1. **Определи путь к файлу задачи**:
   - Аргумент команды = путь к `.md` файлу с описанием задачи
   - Если путь не указан — спроси у пользователя
   - Проверь что файл существует (Read)

2. **Запусти скрипт** через Bash (run_in_background=true, timeout=600000):
   ```
   powershell -File "./scripts/analyze-1c-research.ps1" -TaskFile "<path>"
   ```

3. **Мониторь прогресс** — проверяй TaskOutput каждые 30-60 секунд (block=false):
   - Показывай пользователю новые строки вывода
   - Особенно: номер итерации, агент (EXECUTOR/REVIEWER/COMPARATOR), score, verdict

4. **По завершении** сообщи:
   - Финальный score и количество итераций
   - Путь к отчёту: `data/analyze-1c-research/<task-id>/analysis-report.md`
   - Путь к логам: `data/analyze-1c-research/<task-id>/logs/`

## Параметры (опциональные, через пробел после пути)

- `-TargetScore 90` — целевой балл (по умолчанию 85)
- `-MaxIterations 10` — макс итераций (по умолчанию 7)
- `-AgentTimeoutMin 20` — hard timeout на агента в минутах (по умолчанию 15)
- `-IdleTimeoutMin 5` — kill если нет файловой активности N минут (по умолчанию 5)
- `-AgentMaxTurns 50` — макс tool calls на агента (по умолчанию 50)
- `-SessionDir path` — возобновить из существующей сессии (вместо -TaskFile)
