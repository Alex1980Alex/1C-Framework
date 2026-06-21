# Pipeline: ADR-032 выбор инструментария 1C UI/report

**Тип:** medium (research-synthesis → ADR) · **Дата:** 2026-06-21

## 1. План
Зафиксировать выбор инструментов (cc-1c-skills vs codepilot1c-edt vs EDT-MCP) для 4 способностей (DCS/табл.документ/формы) после рейтинга ≥12.

## 2. Дизайн
ADR (architecture-research Фаза 6) с матрицей способность→инструмент + сравнением 3 по осям (offline/live, read/write, формат, лицензия, verified), опора на ADR-030/031 + live-результаты сессии.

## 3. Реализация
- ADR-032 создан + зарегистрирован в adr/_index.json.
- Опирается на кеш 1c-form-skd-spreadsheet-tooling-2026.md.

## 4. Тест / результат
- Решение: 3-инструментальный стек, cc-1c-skills основной (offline, все 4), codepilot EDT-write, EDT-MCP baseline+deploy, execute_code fallback.
- Матрица способность→инструмент зафиксирована; запрет новых MCP (ADR-030) соблюдён.
- Follow-up (не сделано): live mdclasses/1c-formsserver (setup-тяжёлый).
