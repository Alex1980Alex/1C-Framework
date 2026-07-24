# Ретирмент src/bsl/mcp_server (ADR-056)

**Дата:** 2026-07-24 · **Тип:** refactor/retirement · **Approve:** пользователь («приступай к реализации» по ADR-056)

## Сделано
1. **Удаление:** `src/bsl/mcp_server/` (10 файлов, ~1560 LOC: MCPProxy/OneCClient прокси-ядро + auth/oauth2.py compat-обёртка) + `tests/unit/test_bsl_oauth_wrapper.py` (9 тестов обёртки; generic-покрытие живёт в `test_mcp_oauth*.py` = 38 тестов).
2. **Доки (9 файлов):** 09.2 (диаграмма, секция wrapper→«ретирован», тест-счёт 47→38/65→56), 37.3/37.7/37.8 (замороженные хроники - сняты мёртвые ссылки + пометки), wiki/auth/oauth-setup + oauth2-service (баннер + migration path), Guides/OAUTH2_ACTIVATION (баннер + пути), CLAUDE.md (список src/bsl/), scripts/wiki_create_stubs.py (буллет → external/1c_mcp), src/shared/mcp_oauth/__init__.py (провенанс-докстринг).
3. **Не тронуто:** `src/bsl/mcp_integration/1c_ext/` (живые исходники расширения 1С), сабмодуль `external/1c_mcp`, продакшн-лаунчер.

## Верификация
- pytest test_mcp_oauth*.py: **38/38 PASS**; py_compile + ruff wiki_create_stubs.py: чисто.
- Повторный аудит: doc-gaps **23→21**, bsl_tool features 23→20 (MCPProxy/OneCClient ушли из гэпов).
- Греп остатков в исполняемых файлах: 0 (единственное упоминание - аннотированный провенанс-докстринг shared).
- code-verify субагент (read-only): PARTIAL → 2 находки (09.2:141 тест-счёт «47/47», 37.8:113 битая ссылка) → исправлены → PASS.

## Артефакты
ADR-056 **accepted** + _index.json; память project_1c_mcp_replacement + MEMORY.md обновлены.
