# Анализ ценности src/bsl/mcp_server (MCPProxy/OneCClient) + GitHub-экосистема

**Дата:** 2026-07-24 · **Тип:** research/analysis (без правок продукт-кода)

## Задача
Пользователь: «MCPProxy/OneCClient проверь ценность этих инструментов, проанализируй GitHub, сделай глубокий анализ» (продолжение аудита docs-coverage, где эти классы всплыли как doc-gaps).

## Метод
1. Чтение кода `src/bsl/mcp_server/*` (1560 LOC) + git-история (15 коммитов, все sweep/auto).
2. Провенанс: roadmap PHASE_46 (перенос из `D:\1C-Enterprise_Framework\mcp-1c-server`).
3. Дифф с upstream `external/1c_mcp/src/py_server` (тот же lineage, upstream ушёл вперёд).
4. GitHub: gh api (upstream 466★ пуш 2026-07-17 license:null; feenlace/mcp-1c 173★ MIT пуш 2026-07-22; FSerg 161★ stale; Untru каталог 132★; MCP35 30★; lsp-bridge 63★). ecosystem_scan пуст (30-дневное окно, известный gap).
5. Зависимые: только `tests/unit/test_bsl_oauth_wrapper.py` → compat-wrapper `auth/oauth2.py` (ядро OAuth извлечено в `src/shared/mcp_oauth`, Phase 12.3). Рантайм-вызывающих нет; продакшн - лаунчер `scripts/mcp_1c_stdio_launcher.py` → сабмодуль.

## Вывод
Ценность MCPProxy/OneCClient ≈ 0: отставший vendored-родственник upstream py_server; уникальная часть (OAuth 2.1+PKCE) уже извлечена в shared. Рекомендация - ретирмент (ADR-056, proposed). `src/bsl/mcp_integration/1c_ext` (исходники расширения 1С) - ЖИВОЙ, не трогать.

## Артефакты
- ADR-056 (proposed) - `.claude/skills/architecture-research/adr/056-retire-src-bsl-mcp-server.md`
- Обновлён кеш фактов `1c-bsl-tooling-ecosystem-2026.md` (Verified 2026-07-24)
- Обновлена память `project_1c_mcp_replacement.md`
