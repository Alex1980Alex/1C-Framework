# ADR-014: Кодирование — ADOPT Context7 MCP (lazy-load); Pyright EVAL; language-experts SKIP

**Дата:** 2026-06-13
**Статус:** accepted (Context7 внедрён + smoke-verified 2026-06-13; Pyright — остаётся EVAL)
**Исследование:** ../cache/claude-code-ecosystem-tools-2026.md
**Шаг SDLC:** 3. Кодирование (решение фиксируется в Дизайне)

> **Реализация (260613 Этап 3.1-3.3):** Context7 добавлен в `.mcp/lazy-mcp-config.json`
> (категория `documentation`, on-demand `cmd /c npx @upstash/context7-mcp@3.2.0`, НЕ в
> `.mcp.json`). Smoke PASS: живой MCP-handshake → `serverInfo: Context7 v3.2.0` + tool
> `resolve-library-id`; основной `.mcp.json` (21 сервер) не тронут → cold-start не вырос.
> Интегрирован в `tech-research` Фаза 1 (Context7 → fallback WebSearch).

## Контекст
Ресёрч для шага кодирования: Context7 MCP (актуальные version-specific доки в
запросе), Pyright LSP (in-session типы), language-expert субагенты (Python/Django/
React). Условие: не нарастить MCP cold-start (21 сервер уже тяжёлый,
[[feedback-pdf-mcp-init-duration]]).

## Решение
- **ADOPT Context7 MCP** через **lazy-mcp** (on-demand, НЕ в основной `.mcp.json`) — read-only, анти-галлюцинация API (roadmap Этап 3.1-3.3). [web] устраняет stale-doc ошибки; [own] усиливает наш research-протокол (`tech-research` Фаза 2).
- **Pyright LSP — EVAL** (отдельный заход): overlap с mypy → решить ценность in-session типов vs дубль.
- **SKIP language-expert субагенты**: overlap с нашими skills + `llm-rotation` (5 провайдеров) + субагенты.

## Последствия
**Положительные:** live-доки в запросе (меньше галлюцинаций API); lazy-load → cold-start не растёт; reversible (убрать definition).
**Отрицательные:** ещё один внешний сервер в зависимостях (mitigated: on-demand, read-only, opt-out).

## Альтернативы
- **Context7 в основной `.mcp.json`** — отклонён: рост cold-start (N1 нарушен).
- **language-experts** — отклонены: дубль существующих skills/делегирования.
- **Pyright сейчас** — отложен в EVAL: возможный дубль mypy-стека.

## Связанные файлы
`.mcp/lazy-mcp-config.json` (новый serverDefinition `context7`), `.claude/skills/tech-research/SKILL.md` (Фаза 2 подсказка).
