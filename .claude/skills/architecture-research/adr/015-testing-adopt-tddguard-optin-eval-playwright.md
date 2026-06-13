# ADR-015: Тестирование — tdd-guard opt-in; Playwright/ToB EVAL; Sentry/Code-Review-plugin SKIP

**Дата:** 2026-06-13
**Статус:** proposed
**Исследование:** ../cache/claude-code-ecosystem-tools-2026.md
**Шаг SDLC:** 4. Тестирование (решение фиксируется в Дизайне)

## Контекст
Ресёрч для шага тестирования: tdd-guard (red-first enforcement), Playwright MCP
(web/visual), Trail of Bits Security Skills (CodeQL/Semgrep локально), Sentry MCP
(prod errors), Code Review plugin. Условие: не сломать рабочий
code-verify/CI/VA-BDD flow.

## Решение
- **ADOPT tdd-guard** как **opt-in** hook (env-флаг default **OFF**, неделя валидации перед default-ON) для Python `src/**` (roadmap Этап 4.1-4.3). [own] у нас post-hoc code-verify, но нет red-first гейта.
- **Playwright MCP — EVAL** через lazy-mcp: web/visual-тесты Streamlit/Gradio UI + FastAPI smoke; web вторичен к нашему фокусу (1C VA BDD).
- **Trail of Bits Security — EVAL**: возможный дубль CI CodeQL/Semgrep.
- **SKIP Sentry MCP** (нет SaaS-деплоя), **SKIP Code Review plugin** (есть adversarial code-verify субагент + built-in `/code-review`).

## Последствия
**Положительные:** red-first дисциплина для Python; opt-in default-OFF → существующий flow не ломается.
**Отрицательные:** риск ложных блокировок tdd-guard (mitigated: default-OFF + валидация-окно).

## Альтернативы
- **Code Review plugin** — отклонён: дубль нашего code-verify + `/code-review`.
- **Sentry MCP** — отклонён: нет production SaaS с Sentry.
- **tdd-guard default-ON сразу** — отклонён: риск ложных блокировок без валидации.

## Связанные файлы
`.claude/settings.json` (Stop/PreToolUse chain — opt-in hook), `code-verify` skill, `.github/workflows/ci.yml`, `va-bdd-testing`.
