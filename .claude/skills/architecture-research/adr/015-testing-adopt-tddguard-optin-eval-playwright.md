# ADR-015: Тестирование — tdd-guard opt-in; Playwright/ToB EVAL; Sentry/Code-Review-plugin SKIP

**Дата:** 2026-06-13
**Статус:** accepted (tdd-guard hook создан+smoke-verified 2026-06-13; Playwright/ToB — EVAL)
**Исследование:** ../cache/claude-code-ecosystem-tools-2026.md
**Шаг SDLC:** 4. Тестирование (решение фиксируется в Дизайне)

> **Реализация (260613 Этап 4.2):** [`tdd-guard.py`](../../../../.claude/hooks/tdd-guard.py)
> создан — **advisory-only opt-in** (PreToolUse:Write|Edit). Default (env unset) =
> чистый no-op; `TDD_GUARD_ENABLE=1` + правка `src/**.py` с новым def/class без
> `tests/**/test_<mod>.py` → system_message-подсказка (`continue:true`, **НИКОГДА
> не блокирует**). MVP = test-presence guard (НЕ полный run-tracked red-first —
> будущее усиление). Smoke PASS: OFF=no-op / ON+нет-теста=advisory / ON+тест-есть=тихо
> / non-src=тихо; compile+ruff clean.
> **НЕ зарегистрирован в settings.json** (surgical/non-breaking — harness-критичный
> файл не трогаем ради dormant-хука; `simplicity-discipline`). **Включение (старт
> недели валидации 4.3):** (1) добавить PreToolUse `Write|Edit` entry с `tdd-guard.py`
> в `.claude/settings.json`; (2) `TDD_GUARD_ENABLE=1`. Реверс = снять оба.

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
