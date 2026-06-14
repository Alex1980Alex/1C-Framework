# ADR-016: Tooling Adoption EVAL-хвост — Pyright SKIP / Playwright DEFER / ToB SKIP / Grill Me SKIP

**Дата:** 2026-06-13
**Статус:** accepted
**Исследование:** ../cache/claude-code-ecosystem-tools-2026.md
**Шаг SDLC:** охватывает 1 (Планирование), 3 (Кодирование), 4 (Тестирование); фиксация — Дизайн

## Контекст
После внедрения firm-ADOPT пунктов карты [260613 Tooling Adoption](../../../../docs/roadmap/260613_ROADMAP_TOOLING_ADOPTION.md)
(Context7 ADR-014, simplicity-discipline ADR-013, tdd-guard ADR-015) остался
EVAL-хвост — инструменты «оценить → adopt/skip»: Pyright LSP (3.4), Playwright MCP
(4.4), Trail of Bits Security (4.5), Grill Me (Этап 1, опц.). EVAL = решить на основе
перекрытия с существующими возможностями, без слепого «adopt из списка».

## Решение

| Инструмент | Вердикт | Обоснование |
|------------|---------|-------------|
| **Pyright LSP** (3.4) | **SKIP** | [exp] есть `mypy` + `mypy-baseline` (CI-гейт) + `ruff` — дубль type-checker'а (конфликтующие диагностики, доп-сопровождение); [own] N6 — не вводим Claude Code plugin-систему. Пересмотр: если понадобятся editor-time типы поверх CI. |
| **Playwright MCP** (4.4) | **DEFER** | [exp] UI-тесты покрыты `va-bdd-testing` (1C VA) — основной путь; web-UI (`src/ui/` Streamlit/Gradio + `src/api/` FastAPI) тестами не покрыт — **реальный, но низкоприоритетный gap** (фронтенд вторичен к BSL/RAG-ядру). [own] Дёшево добавить через `lazy-mcp` (on-demand) ПОЗЖЕ. Пересмотр-условие: если web-UI станет тестируемой поверхностью. |
| **Trail of Bits Security** (4.5) | **SKIP** | [exp] CodeQL + Semgrep уже в CI (`codeql.yml` + triage-скрипт) — точка enforcement'а. Локальный skill = дубль CI-гейта. Пересмотр: если нужен pre-CI локальный скан-удобство. |
| **Grill Me** (Этап 1, опц.) | **SKIP** | [exp] интеррогация плана уже есть: `analyze-1c-task-v2` (5-фаз, требования) + OpenSpec approval-gate. Дубль. Пересмотр: если нужен generic (не-1C) plan-grill. |

## Последствия
**Положительные:** ноль дублей (нет конфликтующих type-checker'ов / двойного security-скана / лишних plan-инструментов); карта внедрения закрыта осознанными вердиктами, не «забыли». Каждый SKIP/DEFER имеет условие пересмотра (решения не вечные).
**Отрицательные:** web-UI остаётся без авто-тестов (DEFER) — принимается как низкий приоритет; editor-time типы (Pyright) недоступны — mypy-CI покрывает корректность.

## Альтернативы
- ADOPT всех 4 — отклонено: дубли существующих возможностей, рост сопровождения без выигрыша (анти-overfit к «модному списку»).
- Полный pre-CI security-skill (ToB) — отклонён сейчас: CI — авторитетный гейт; локальный скан — будущее удобство, не необходимость.

## Связанные файлы
`mypy`/`ruff` (pyproject.toml), `.github/workflows/codeql.yml`, `va-bdd-testing` skill, `analyze-1c-task-v2`, OpenSpec approval-gate. **Карта 260613 Tooling Adoption — функционально закрыта** (все ADOPT внедрены, EVAL-хвост решён); открыт лишь 4.3 (валидация tdd-guard после ручного включения).
