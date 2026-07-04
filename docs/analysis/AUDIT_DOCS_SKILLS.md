# Audit: Code ↔ Documentation ↔ Skills

**Generated:** 2026-07-04 14:01

## Summary

| Category | In Code | Doc Gaps | Skill Gaps | Doc Coverage | Skill Coverage |
|----------|---------|----------|------------|-------------|----------------|
| Agent Types | 5 | **0** | **0** | 100.0% | 100.0% |
| bsl_tool | 33 | **32** | **0** | 3.0% | 100.0% |
| CLI Commands | 17 | **0** | **0** | 100.0% | 100.0% |
| Config Variables (.env) | 298 | **0** | **0** | 100.0% | 100.0% |
| REST API Endpoints | 88 | **0** | **0** | 100.0% | 100.0% |
| hook | 97 | **76** | **38** | 21.6% | 60.8% |
| MCP Tools | 15 | **0** | **0** | 100.0% | 100.0% |
| memory_subsystem | 62 | **41** | **2** | 33.9% | 96.8% |
| Search Strategies | 14 | **0** | **0** | 100.0% | 100.0% |
| wiki_component | 5 | **0** | **0** | 100.0% | 100.0% |
| **TOTAL** | **634** | **149** | **40** | | |

## Documentation Gaps (in code, NOT in docs)

### bsl_tool (32 gaps)

| Feature | Source | Should be in |
|---------|--------|-------------|
| `CallGraphStore` | `src\bsl\call_graph\store.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `BSLStyleProfile` | `src\bsl\coding_assistant\style_extractor.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `BSLStyleExtractor` | `src\bsl\coding_assistant\style_extractor.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `EvalResult` | `src\bsl\evaluation\metrics.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `ObjectInfo` | `src\bsl\knowledge_graph\metadata_extractor.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `MetadataExtractor` | `src\bsl\knowledge_graph\metadata_extractor.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `OAuth2BearerMiddleware` | `src\bsl\mcp_server\http_server.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `MCPHttpServer` | `src\bsl\mcp_server\http_server.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `MCPProxy` | `src\bsl\mcp_server\mcp_server.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `OneCClient` | `src\bsl\mcp_server\onec_client.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `BSLASTParser` | `src\bsl\parser\bsl_ast_parser.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `BSLChunk` | `src\bsl\parser\bsl_chunker.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `BSLChunker` | `src\bsl\parser\bsl_chunker.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `BSLContextEnricher` | `src\bsl\parser\context_enricher.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `SymbolType` | `src\bsl\parser\models.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `CompilationDirective` | `src\bsl\parser\models.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `ModuleType` | `src\bsl\parser\models.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `BSLParam` | `src\bsl\parser\models.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `BSLCall` | `src\bsl\parser\models.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `BSLSymbol` | `src\bsl\parser\models.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `BSLVariable` | `src\bsl\parser\models.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `BSLRegion` | `src\bsl\parser\models.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `BSLModule` | `src\bsl\parser\models.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `BSLSearchSettings` | `src\bsl\semantic_search\config.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `RouterResult` | `src\bsl\semantic_search\hybrid_router.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `SonarQubeConfig` | `src\bsl\sonar\config_manager.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `ConfigManager` | `src\bsl\sonar\config_manager.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `Issue` | `src\bsl\sonar\report_generator.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `AnalysisReport` | `src\bsl\sonar\report_generator.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `ReportGenerator` | `src\bsl\sonar\report_generator.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `BSLRule` | `src\bsl\sonar\rules_manager.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |
| `RulesManager` | `src\bsl\sonar\rules_manager.py` | `3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md, 7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md, 2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md` |

### hook (76 gaps)

| Feature | Source | Should be in |
|---------|--------|-------------|
| `analyze-1c-task-preflight` | `.claude\hooks\analyze-1c-task-preflight.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `audit-coverage-check` | `.claude\hooks\audit-coverage-check.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `bsl-tool-router` | `.claude\hooks\bsl-tool-router.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `bulk-action-guard` | `.claude\hooks\bulk-action-guard.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `ci-catchup-on-start` | `.claude\hooks\ci-catchup-on-start.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `ci-catchup-on-stop` | `.claude\hooks\ci-catchup-on-stop.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `code-review-enforcer` | `.claude\hooks\code-review-enforcer.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `delegation-outcome-stop` | `.claude\hooks\delegation-outcome-stop.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `delegation-outcome-tracker` | `.claude\hooks\delegation-outcome-tracker.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `docs-change-tracker` | `.claude\hooks\docs-change-tracker.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `gate-orchestrator-stop` | `.claude\hooks\gate-orchestrator-stop.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `gh-notif-intake-on-start` | `.claude\hooks\gh-notif-intake-on-start.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `github-search-via-ecosystem-scan` | `.claude\hooks\github-search-via-ecosystem-scan.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `implement-1c-task-preflight` | `.claude\hooks\implement-1c-task-preflight.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `implement-1c-task-smoke-stop-alert` | `.claude\hooks\implement-1c-task-smoke-stop-alert.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `lifecycle-cache` | `.claude\hooks\lifecycle-cache.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `logging-status-banner` | `.claude\hooks\logging-status-banner.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `mcp-invocation-logger` | `.claude\hooks\mcp-invocation-logger.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `memory-ai-acceptance-on-start` | `.claude\hooks\memory-ai-acceptance-on-start.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `memory-curation-candidates-on-start` | `.claude\hooks\memory-curation-candidates-on-start.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `memory-effectiveness-analyzer` | `.claude\hooks\memory-effectiveness-analyzer.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `memory-first-hook` | `.claude\hooks\memory-first-hook.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `memory-maintenance-cadence` | `.claude\hooks\memory-maintenance-cadence.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `memory-sync` | `.claude\hooks\memory-sync.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `onec-state-first-guard` | `.claude\hooks\onec-state-first-guard.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `onec-task-completion-stop` | `.claude\hooks\onec-task-completion-stop.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `onec-task-input` | `.claude\hooks\onec-task-input.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `onec-toolgate-validation-on-start` | `.claude\hooks\onec-toolgate-validation-on-start.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `openspec-change-coverage` | `.claude\hooks\openspec-change-coverage.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `openspec-task-progress` | `.claude\hooks\openspec-task-progress.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `opsx-apply-postvalidate` | `.claude\hooks\opsx-apply-postvalidate.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `pattern-reinforce-stop` | `.claude\hooks\pattern-reinforce-stop.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `patterns-harvester` | `.claude\hooks\patterns-harvester.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `pipeline-1c-advance` | `.claude\hooks\pipeline-1c-advance.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `pipeline-gate` | `.claude\hooks\pipeline-gate.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `pipeline-protocol-stop` | `.claude\hooks\pipeline-protocol-stop.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `pipeline-protocol` | `.claude\hooks\pipeline-protocol.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `post-indexing-analyzer` | `.claude\hooks\post-indexing-analyzer.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `post-merge-revert-stop` | `.claude\hooks\post-merge-revert-stop.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `post-task-push-pr` | `.claude\hooks\post-task-push-pr.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `posttooluse-auto-git-save` | `.claude\hooks\posttooluse-auto-git-save.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `posttooluse-bash-errors` | `.claude\hooks\posttooluse-bash-errors.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `posttooluse-delegation-tracker` | `.claude\hooks\posttooluse-delegation-tracker.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `posttooluse-docs-tracker` | `.claude\hooks\posttooluse-docs-tracker.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `posttooluse-quality-feedback` | `.claude\hooks\posttooluse-quality-feedback.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `posttooluse-skill-metrics` | `.claude\hooks\posttooluse-skill-metrics.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `posttooluse-stackoverflow-on-error` | `.claude\hooks\posttooluse-stackoverflow-on-error.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `posttooluse-web-cache` | `.claude\hooks\posttooluse-web-cache.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `pre-merge-review-check` | `.claude\hooks\pre-merge-review-check.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `prework-architecture` | `.claude\hooks\prework-architecture.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `prework-github-bp` | `.claude\hooks\prework-github-bp.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `prework-similar-code` | `.claude\hooks\prework-similar-code.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `prework-stackoverflow` | `.claude\hooks\prework-stackoverflow.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `process-guard` | `.claude\hooks\process-guard.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `ralph_activator` | `.claude\hooks\ralph_activator.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `roadmap-progress-enforcer` | `.claude\hooks\roadmap-progress-enforcer.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `search-optimizer` | `.claude\hooks\search-optimizer.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `session-context-enforcer` | `.claude\hooks\session-context-enforcer.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `session-memory-save` | `.claude\hooks\session-memory-save.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `session-mypy-banner` | `.claude\hooks\session-mypy-banner.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `skill-learning-acceptance-on-start` | `.claude\hooks\skill-learning-acceptance-on-start.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `skill-learning-pending-on-start` | `.claude\hooks\skill-learning-pending-on-start.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `skill-quality-monitor` | `.claude\hooks\skill-quality-monitor.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `skill-system-acceptance-on-start` | `.claude\hooks\skill-system-acceptance-on-start.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `skill-usage-metrics` | `.claude\hooks\skill-usage-metrics.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `skills-harvester` | `.claude\hooks\skills-harvester.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `slash-command-tracker` | `.claude\hooks\slash-command-tracker.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `stop-feedback-draft-aggregator` | `.claude\hooks\stop-feedback-draft-aggregator.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `submodule-status-check` | `.claude\hooks\submodule-status-check.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `tdd-guard-validation-on-start` | `.claude\hooks\tdd-guard-validation-on-start.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `tdd-guard` | `.claude\hooks\tdd-guard.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `tei-warmup-on-start` | `.claude\hooks\tei-warmup-on-start.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `todo-sync` | `.claude\hooks\todo-sync.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `userpromptsubmit-feedback-detector` | `.claude\hooks\userpromptsubmit-feedback-detector.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `z-ai-delegation-enforcer` | `.claude\hooks\z-ai-delegation-enforcer.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |
| `z-ai-write-guard` | `.claude\hooks\z-ai-write-guard.py` | `7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md, 9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md` |

### memory_subsystem (41 gaps)

| Feature | Source | Should be in |
|---------|--------|-------------|
| `StoreRecord` | `src\memory\orchestrator\cross_store_index.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `MirrorLink` | `src\memory\orchestrator\cross_store_sync.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `LinkType` | `src\memory\orchestrator\link_registry.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `EntityLink` | `src\memory\orchestrator\link_registry.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `RelatedEntity` | `src\memory\orchestrator\link_registry.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `AiMemorySearchAdapter` | `src\memory\orchestrator\memory_orchestrator.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `VectorMemorySearchAdapter` | `src\memory\orchestrator\memory_orchestrator.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `SkillLearningSearchAdapter` | `src\memory\orchestrator\memory_orchestrator.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `RoutingDecision` | `src\memory\orchestrator\memory_router.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `RoutingStats` | `src\memory\orchestrator\memory_router.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `ContentClassifier` | `src\memory\orchestrator\memory_router.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `PropagationEvent` | `src\memory\orchestrator\propagation_engine.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `PropagationResult` | `src\memory\orchestrator\propagation_engine.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `IDRegistry` | `src\memory\orchestrator\unified_id.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `LinkedEntity` | `src\memory\orchestrator\unified_search.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `SearchResultItem` | `src\memory\orchestrator\unified_search.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `UnifiedSearchResult` | `src\memory\orchestrator\unified_search.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `BaseSearchAdapter` | `src\memory\orchestrator\unified_search.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `Deduplicator` | `src\memory\orchestrator\unified_search.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `LinkEnricher` | `src\memory\orchestrator\unified_search.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `UnifiedSearchEngine` | `src\memory\orchestrator\unified_search.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `PatternType` | `src\memory\vector_memory\models.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `ConfidenceLevel` | `src\memory\vector_memory\models.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `EvidenceSource` | `src\memory\vector_memory\models.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `LearnedPattern` | `src\memory\vector_memory\models.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `PatternSearchResult` | `src\memory\vector_memory\models.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `LearningStats` | `src\memory\vector_memory\models.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `CacheEntry` | `src\memory\infrastructure\cache.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `LRUCache` | `src\memory\infrastructure\cache.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `CircuitState` | `src\memory\infrastructure\circuit_breaker.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `CircuitStats` | `src\memory\infrastructure\circuit_breaker.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `CircuitBreakerRegistry` | `src\memory\infrastructure\circuit_breaker.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `ConflictStrategy` | `src\memory\infrastructure\conflict_resolver.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `ConflictRecord` | `src\memory\infrastructure\conflict_resolver.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `ConflictResult` | `src\memory\infrastructure\conflict_resolver.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `Subscription` | `src\memory\infrastructure\event_bus.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `EventBusStats` | `src\memory\infrastructure\event_bus.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `MetricsCollector` | `src\memory\infrastructure\metrics.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `MetricsTimer` | `src\memory\infrastructure\metrics.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `ManagedSubscription` | `src\memory\infrastructure\subscription_manager.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |
| `SubscriptionManager` | `src\memory\infrastructure\subscription_manager.py` | `5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md, 5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md, 5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md` |

## Skill Gaps (in code, NOT in skills)

### hook (38 gaps)

| Feature | Source | Should be in |
|---------|--------|-------------|
| `ci-catchup-on-stop` | `.claude\hooks\ci-catchup-on-stop.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `gate-orchestrator-stop` | `.claude\hooks\gate-orchestrator-stop.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `github-search-via-ecosystem-scan` | `.claude\hooks\github-search-via-ecosystem-scan.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `lifecycle-cache` | `.claude\hooks\lifecycle-cache.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `memory-ai-acceptance-on-start` | `.claude\hooks\memory-ai-acceptance-on-start.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `memory-curation-candidates-on-start` | `.claude\hooks\memory-curation-candidates-on-start.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `memory-effectiveness-analyzer` | `.claude\hooks\memory-effectiveness-analyzer.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `memory-maintenance-cadence` | `.claude\hooks\memory-maintenance-cadence.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `onec-state-first-guard` | `.claude\hooks\onec-state-first-guard.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `onec-task-completion-stop` | `.claude\hooks\onec-task-completion-stop.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `onec-task-input` | `.claude\hooks\onec-task-input.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `onec-toolgate-validation-on-start` | `.claude\hooks\onec-toolgate-validation-on-start.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `openspec-change-coverage` | `.claude\hooks\openspec-change-coverage.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `openspec-task-progress` | `.claude\hooks\openspec-task-progress.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `opsx-apply-postvalidate` | `.claude\hooks\opsx-apply-postvalidate.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `patterns-harvester` | `.claude\hooks\patterns-harvester.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `pipeline-1c-advance` | `.claude\hooks\pipeline-1c-advance.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `pipeline-gate` | `.claude\hooks\pipeline-gate.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `pipeline-protocol-stop` | `.claude\hooks\pipeline-protocol-stop.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `pipeline-protocol` | `.claude\hooks\pipeline-protocol.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `post-indexing-analyzer` | `.claude\hooks\post-indexing-analyzer.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `post-merge-revert-stop` | `.claude\hooks\post-merge-revert-stop.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `post-task-push-pr` | `.claude\hooks\post-task-push-pr.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `posttooluse-stackoverflow-on-error` | `.claude\hooks\posttooluse-stackoverflow-on-error.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `prework-architecture` | `.claude\hooks\prework-architecture.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `prework-github-bp` | `.claude\hooks\prework-github-bp.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `prework-similar-code` | `.claude\hooks\prework-similar-code.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `prework-stackoverflow` | `.claude\hooks\prework-stackoverflow.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `process-guard` | `.claude\hooks\process-guard.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `roadmap-progress-enforcer` | `.claude\hooks\roadmap-progress-enforcer.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `skill-learning-acceptance-on-start` | `.claude\hooks\skill-learning-acceptance-on-start.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `skill-learning-pending-on-start` | `.claude\hooks\skill-learning-pending-on-start.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `skill-system-acceptance-on-start` | `.claude\hooks\skill-system-acceptance-on-start.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `skills-harvester` | `.claude\hooks\skills-harvester.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `stop-feedback-draft-aggregator` | `.claude\hooks\stop-feedback-draft-aggregator.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `tdd-guard-validation-on-start` | `.claude\hooks\tdd-guard-validation-on-start.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `tei-warmup-on-start` | `.claude\hooks\tei-warmup-on-start.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |
| `userpromptsubmit-feedback-detector` | `.claude\hooks\userpromptsubmit-feedback-detector.py` | `.claude/skills/hooks-skills-mcp-triad/SKILL.md, .claude/skills/create-hook/SKILL.md` |

### memory_subsystem (2 gaps)

| Feature | Source | Should be in |
|---------|--------|-------------|
| `StoreRecord` | `src\memory\orchestrator\cross_store_index.py` | `.claude/skills/memory-unified/SKILL.md, .claude/skills/wiki-pipeline/SKILL.md` |
| `MirrorLink` | `src\memory\orchestrator\cross_store_sync.py` | `.claude/skills/memory-unified/SKILL.md, .claude/skills/wiki-pipeline/SKILL.md` |

## Action Items

### Documentation updates needed:

**`2_КОНТЕКСТ/2.6_BSL_SEMANTIC_SEARCH/28.1_Обзор.md`** — 32 missing features:
  - [ ] Add `CallGraphStore` (from `src\bsl\call_graph\store.py`)
  - [ ] Add `BSLStyleProfile` (from `src\bsl\coding_assistant\style_extractor.py`)
  - [ ] Add `BSLStyleExtractor` (from `src\bsl\coding_assistant\style_extractor.py`)
  - [ ] Add `EvalResult` (from `src\bsl\evaluation\metrics.py`)
  - [ ] Add `ObjectInfo` (from `src\bsl\knowledge_graph\metadata_extractor.py`)
  - [ ] Add `MetadataExtractor` (from `src\bsl\knowledge_graph\metadata_extractor.py`)
  - [ ] Add `OAuth2BearerMiddleware` (from `src\bsl\mcp_server\http_server.py`)
  - [ ] Add `MCPHttpServer` (from `src\bsl\mcp_server\http_server.py`)
  - [ ] Add `MCPProxy` (from `src\bsl\mcp_server\mcp_server.py`)
  - [ ] Add `OneCClient` (from `src\bsl\mcp_server\onec_client.py`)
  - [ ] Add `BSLASTParser` (from `src\bsl\parser\bsl_ast_parser.py`)
  - [ ] Add `BSLChunk` (from `src\bsl\parser\bsl_chunker.py`)
  - [ ] Add `BSLChunker` (from `src\bsl\parser\bsl_chunker.py`)
  - [ ] Add `BSLContextEnricher` (from `src\bsl\parser\context_enricher.py`)
  - [ ] Add `SymbolType` (from `src\bsl\parser\models.py`)
  - [ ] Add `CompilationDirective` (from `src\bsl\parser\models.py`)
  - [ ] Add `ModuleType` (from `src\bsl\parser\models.py`)
  - [ ] Add `BSLParam` (from `src\bsl\parser\models.py`)
  - [ ] Add `BSLCall` (from `src\bsl\parser\models.py`)
  - [ ] Add `BSLSymbol` (from `src\bsl\parser\models.py`)
  - ... and 12 more

**`3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md`** — 32 missing features:
  - [ ] Add `CallGraphStore` (from `src\bsl\call_graph\store.py`)
  - [ ] Add `BSLStyleProfile` (from `src\bsl\coding_assistant\style_extractor.py`)
  - [ ] Add `BSLStyleExtractor` (from `src\bsl\coding_assistant\style_extractor.py`)
  - [ ] Add `EvalResult` (from `src\bsl\evaluation\metrics.py`)
  - [ ] Add `ObjectInfo` (from `src\bsl\knowledge_graph\metadata_extractor.py`)
  - [ ] Add `MetadataExtractor` (from `src\bsl\knowledge_graph\metadata_extractor.py`)
  - [ ] Add `OAuth2BearerMiddleware` (from `src\bsl\mcp_server\http_server.py`)
  - [ ] Add `MCPHttpServer` (from `src\bsl\mcp_server\http_server.py`)
  - [ ] Add `MCPProxy` (from `src\bsl\mcp_server\mcp_server.py`)
  - [ ] Add `OneCClient` (from `src\bsl\mcp_server\onec_client.py`)
  - [ ] Add `BSLASTParser` (from `src\bsl\parser\bsl_ast_parser.py`)
  - [ ] Add `BSLChunk` (from `src\bsl\parser\bsl_chunker.py`)
  - [ ] Add `BSLChunker` (from `src\bsl\parser\bsl_chunker.py`)
  - [ ] Add `BSLContextEnricher` (from `src\bsl\parser\context_enricher.py`)
  - [ ] Add `SymbolType` (from `src\bsl\parser\models.py`)
  - [ ] Add `CompilationDirective` (from `src\bsl\parser\models.py`)
  - [ ] Add `ModuleType` (from `src\bsl\parser\models.py`)
  - [ ] Add `BSLParam` (from `src\bsl\parser\models.py`)
  - [ ] Add `BSLCall` (from `src\bsl\parser\models.py`)
  - [ ] Add `BSLSymbol` (from `src\bsl\parser\models.py`)
  - ... and 12 more

**`5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.1_Обзор.md`** — 41 missing features:
  - [ ] Add `StoreRecord` (from `src\memory\orchestrator\cross_store_index.py`)
  - [ ] Add `MirrorLink` (from `src\memory\orchestrator\cross_store_sync.py`)
  - [ ] Add `LinkType` (from `src\memory\orchestrator\link_registry.py`)
  - [ ] Add `EntityLink` (from `src\memory\orchestrator\link_registry.py`)
  - [ ] Add `RelatedEntity` (from `src\memory\orchestrator\link_registry.py`)
  - [ ] Add `AiMemorySearchAdapter` (from `src\memory\orchestrator\memory_orchestrator.py`)
  - [ ] Add `VectorMemorySearchAdapter` (from `src\memory\orchestrator\memory_orchestrator.py`)
  - [ ] Add `SkillLearningSearchAdapter` (from `src\memory\orchestrator\memory_orchestrator.py`)
  - [ ] Add `RoutingDecision` (from `src\memory\orchestrator\memory_router.py`)
  - [ ] Add `RoutingStats` (from `src\memory\orchestrator\memory_router.py`)
  - [ ] Add `ContentClassifier` (from `src\memory\orchestrator\memory_router.py`)
  - [ ] Add `PropagationEvent` (from `src\memory\orchestrator\propagation_engine.py`)
  - [ ] Add `PropagationResult` (from `src\memory\orchestrator\propagation_engine.py`)
  - [ ] Add `IDRegistry` (from `src\memory\orchestrator\unified_id.py`)
  - [ ] Add `LinkedEntity` (from `src\memory\orchestrator\unified_search.py`)
  - [ ] Add `SearchResultItem` (from `src\memory\orchestrator\unified_search.py`)
  - [ ] Add `UnifiedSearchResult` (from `src\memory\orchestrator\unified_search.py`)
  - [ ] Add `BaseSearchAdapter` (from `src\memory\orchestrator\unified_search.py`)
  - [ ] Add `Deduplicator` (from `src\memory\orchestrator\unified_search.py`)
  - [ ] Add `LinkEnricher` (from `src\memory\orchestrator\unified_search.py`)
  - ... and 21 more

**`5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.2_Оркестратор.md`** — 41 missing features:
  - [ ] Add `StoreRecord` (from `src\memory\orchestrator\cross_store_index.py`)
  - [ ] Add `MirrorLink` (from `src\memory\orchestrator\cross_store_sync.py`)
  - [ ] Add `LinkType` (from `src\memory\orchestrator\link_registry.py`)
  - [ ] Add `EntityLink` (from `src\memory\orchestrator\link_registry.py`)
  - [ ] Add `RelatedEntity` (from `src\memory\orchestrator\link_registry.py`)
  - [ ] Add `AiMemorySearchAdapter` (from `src\memory\orchestrator\memory_orchestrator.py`)
  - [ ] Add `VectorMemorySearchAdapter` (from `src\memory\orchestrator\memory_orchestrator.py`)
  - [ ] Add `SkillLearningSearchAdapter` (from `src\memory\orchestrator\memory_orchestrator.py`)
  - [ ] Add `RoutingDecision` (from `src\memory\orchestrator\memory_router.py`)
  - [ ] Add `RoutingStats` (from `src\memory\orchestrator\memory_router.py`)
  - [ ] Add `ContentClassifier` (from `src\memory\orchestrator\memory_router.py`)
  - [ ] Add `PropagationEvent` (from `src\memory\orchestrator\propagation_engine.py`)
  - [ ] Add `PropagationResult` (from `src\memory\orchestrator\propagation_engine.py`)
  - [ ] Add `IDRegistry` (from `src\memory\orchestrator\unified_id.py`)
  - [ ] Add `LinkedEntity` (from `src\memory\orchestrator\unified_search.py`)
  - [ ] Add `SearchResultItem` (from `src\memory\orchestrator\unified_search.py`)
  - [ ] Add `UnifiedSearchResult` (from `src\memory\orchestrator\unified_search.py`)
  - [ ] Add `BaseSearchAdapter` (from `src\memory\orchestrator\unified_search.py`)
  - [ ] Add `Deduplicator` (from `src\memory\orchestrator\unified_search.py`)
  - [ ] Add `LinkEnricher` (from `src\memory\orchestrator\unified_search.py`)
  - ... and 21 more

**`5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.5_Поиск_и_сервисы.md`** — 41 missing features:
  - [ ] Add `StoreRecord` (from `src\memory\orchestrator\cross_store_index.py`)
  - [ ] Add `MirrorLink` (from `src\memory\orchestrator\cross_store_sync.py`)
  - [ ] Add `LinkType` (from `src\memory\orchestrator\link_registry.py`)
  - [ ] Add `EntityLink` (from `src\memory\orchestrator\link_registry.py`)
  - [ ] Add `RelatedEntity` (from `src\memory\orchestrator\link_registry.py`)
  - [ ] Add `AiMemorySearchAdapter` (from `src\memory\orchestrator\memory_orchestrator.py`)
  - [ ] Add `VectorMemorySearchAdapter` (from `src\memory\orchestrator\memory_orchestrator.py`)
  - [ ] Add `SkillLearningSearchAdapter` (from `src\memory\orchestrator\memory_orchestrator.py`)
  - [ ] Add `RoutingDecision` (from `src\memory\orchestrator\memory_router.py`)
  - [ ] Add `RoutingStats` (from `src\memory\orchestrator\memory_router.py`)
  - [ ] Add `ContentClassifier` (from `src\memory\orchestrator\memory_router.py`)
  - [ ] Add `PropagationEvent` (from `src\memory\orchestrator\propagation_engine.py`)
  - [ ] Add `PropagationResult` (from `src\memory\orchestrator\propagation_engine.py`)
  - [ ] Add `IDRegistry` (from `src\memory\orchestrator\unified_id.py`)
  - [ ] Add `LinkedEntity` (from `src\memory\orchestrator\unified_search.py`)
  - [ ] Add `SearchResultItem` (from `src\memory\orchestrator\unified_search.py`)
  - [ ] Add `UnifiedSearchResult` (from `src\memory\orchestrator\unified_search.py`)
  - [ ] Add `BaseSearchAdapter` (from `src\memory\orchestrator\unified_search.py`)
  - [ ] Add `Deduplicator` (from `src\memory\orchestrator\unified_search.py`)
  - [ ] Add `LinkEnricher` (from `src\memory\orchestrator\unified_search.py`)
  - ... and 21 more

**`5_ПАМЯТЬ/5.2_WIKI_KNOWLEDGE_LAYER/32.6_L2_L5_Promotion.md`** — 41 missing features:
  - [ ] Add `StoreRecord` (from `src\memory\orchestrator\cross_store_index.py`)
  - [ ] Add `MirrorLink` (from `src\memory\orchestrator\cross_store_sync.py`)
  - [ ] Add `LinkType` (from `src\memory\orchestrator\link_registry.py`)
  - [ ] Add `EntityLink` (from `src\memory\orchestrator\link_registry.py`)
  - [ ] Add `RelatedEntity` (from `src\memory\orchestrator\link_registry.py`)
  - [ ] Add `AiMemorySearchAdapter` (from `src\memory\orchestrator\memory_orchestrator.py`)
  - [ ] Add `VectorMemorySearchAdapter` (from `src\memory\orchestrator\memory_orchestrator.py`)
  - [ ] Add `SkillLearningSearchAdapter` (from `src\memory\orchestrator\memory_orchestrator.py`)
  - [ ] Add `RoutingDecision` (from `src\memory\orchestrator\memory_router.py`)
  - [ ] Add `RoutingStats` (from `src\memory\orchestrator\memory_router.py`)
  - [ ] Add `ContentClassifier` (from `src\memory\orchestrator\memory_router.py`)
  - [ ] Add `PropagationEvent` (from `src\memory\orchestrator\propagation_engine.py`)
  - [ ] Add `PropagationResult` (from `src\memory\orchestrator\propagation_engine.py`)
  - [ ] Add `IDRegistry` (from `src\memory\orchestrator\unified_id.py`)
  - [ ] Add `LinkedEntity` (from `src\memory\orchestrator\unified_search.py`)
  - [ ] Add `SearchResultItem` (from `src\memory\orchestrator\unified_search.py`)
  - [ ] Add `UnifiedSearchResult` (from `src\memory\orchestrator\unified_search.py`)
  - [ ] Add `BaseSearchAdapter` (from `src\memory\orchestrator\unified_search.py`)
  - [ ] Add `Deduplicator` (from `src\memory\orchestrator\unified_search.py`)
  - [ ] Add `LinkEnricher` (from `src\memory\orchestrator\unified_search.py`)
  - ... and 21 more

**`7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md`** — 76 missing features:
  - [ ] Add `analyze-1c-task-preflight` (from `.claude\hooks\analyze-1c-task-preflight.py`)
  - [ ] Add `audit-coverage-check` (from `.claude\hooks\audit-coverage-check.py`)
  - [ ] Add `bsl-tool-router` (from `.claude\hooks\bsl-tool-router.py`)
  - [ ] Add `bulk-action-guard` (from `.claude\hooks\bulk-action-guard.py`)
  - [ ] Add `ci-catchup-on-start` (from `.claude\hooks\ci-catchup-on-start.py`)
  - [ ] Add `ci-catchup-on-stop` (from `.claude\hooks\ci-catchup-on-stop.py`)
  - [ ] Add `code-review-enforcer` (from `.claude\hooks\code-review-enforcer.py`)
  - [ ] Add `delegation-outcome-stop` (from `.claude\hooks\delegation-outcome-stop.py`)
  - [ ] Add `delegation-outcome-tracker` (from `.claude\hooks\delegation-outcome-tracker.py`)
  - [ ] Add `docs-change-tracker` (from `.claude\hooks\docs-change-tracker.py`)
  - [ ] Add `gate-orchestrator-stop` (from `.claude\hooks\gate-orchestrator-stop.py`)
  - [ ] Add `gh-notif-intake-on-start` (from `.claude\hooks\gh-notif-intake-on-start.py`)
  - [ ] Add `github-search-via-ecosystem-scan` (from `.claude\hooks\github-search-via-ecosystem-scan.py`)
  - [ ] Add `implement-1c-task-preflight` (from `.claude\hooks\implement-1c-task-preflight.py`)
  - [ ] Add `implement-1c-task-smoke-stop-alert` (from `.claude\hooks\implement-1c-task-smoke-stop-alert.py`)
  - [ ] Add `lifecycle-cache` (from `.claude\hooks\lifecycle-cache.py`)
  - [ ] Add `logging-status-banner` (from `.claude\hooks\logging-status-banner.py`)
  - [ ] Add `mcp-invocation-logger` (from `.claude\hooks\mcp-invocation-logger.py`)
  - [ ] Add `memory-ai-acceptance-on-start` (from `.claude\hooks\memory-ai-acceptance-on-start.py`)
  - [ ] Add `memory-curation-candidates-on-start` (from `.claude\hooks\memory-curation-candidates-on-start.py`)
  - ... and 56 more

**`7_ПРОВЕРКА/7.4_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md`** — 32 missing features:
  - [ ] Add `CallGraphStore` (from `src\bsl\call_graph\store.py`)
  - [ ] Add `BSLStyleProfile` (from `src\bsl\coding_assistant\style_extractor.py`)
  - [ ] Add `BSLStyleExtractor` (from `src\bsl\coding_assistant\style_extractor.py`)
  - [ ] Add `EvalResult` (from `src\bsl\evaluation\metrics.py`)
  - [ ] Add `ObjectInfo` (from `src\bsl\knowledge_graph\metadata_extractor.py`)
  - [ ] Add `MetadataExtractor` (from `src\bsl\knowledge_graph\metadata_extractor.py`)
  - [ ] Add `OAuth2BearerMiddleware` (from `src\bsl\mcp_server\http_server.py`)
  - [ ] Add `MCPHttpServer` (from `src\bsl\mcp_server\http_server.py`)
  - [ ] Add `MCPProxy` (from `src\bsl\mcp_server\mcp_server.py`)
  - [ ] Add `OneCClient` (from `src\bsl\mcp_server\onec_client.py`)
  - [ ] Add `BSLASTParser` (from `src\bsl\parser\bsl_ast_parser.py`)
  - [ ] Add `BSLChunk` (from `src\bsl\parser\bsl_chunker.py`)
  - [ ] Add `BSLChunker` (from `src\bsl\parser\bsl_chunker.py`)
  - [ ] Add `BSLContextEnricher` (from `src\bsl\parser\context_enricher.py`)
  - [ ] Add `SymbolType` (from `src\bsl\parser\models.py`)
  - [ ] Add `CompilationDirective` (from `src\bsl\parser\models.py`)
  - [ ] Add `ModuleType` (from `src\bsl\parser\models.py`)
  - [ ] Add `BSLParam` (from `src\bsl\parser\models.py`)
  - [ ] Add `BSLCall` (from `src\bsl\parser\models.py`)
  - [ ] Add `BSLSymbol` (from `src\bsl\parser\models.py`)
  - ... and 12 more

**`9_НАВЫКИ/9.2_ТРИАДА_HOOK_SKILL_MCP/13.2_Hooks.md`** — 76 missing features:
  - [ ] Add `analyze-1c-task-preflight` (from `.claude\hooks\analyze-1c-task-preflight.py`)
  - [ ] Add `audit-coverage-check` (from `.claude\hooks\audit-coverage-check.py`)
  - [ ] Add `bsl-tool-router` (from `.claude\hooks\bsl-tool-router.py`)
  - [ ] Add `bulk-action-guard` (from `.claude\hooks\bulk-action-guard.py`)
  - [ ] Add `ci-catchup-on-start` (from `.claude\hooks\ci-catchup-on-start.py`)
  - [ ] Add `ci-catchup-on-stop` (from `.claude\hooks\ci-catchup-on-stop.py`)
  - [ ] Add `code-review-enforcer` (from `.claude\hooks\code-review-enforcer.py`)
  - [ ] Add `delegation-outcome-stop` (from `.claude\hooks\delegation-outcome-stop.py`)
  - [ ] Add `delegation-outcome-tracker` (from `.claude\hooks\delegation-outcome-tracker.py`)
  - [ ] Add `docs-change-tracker` (from `.claude\hooks\docs-change-tracker.py`)
  - [ ] Add `gate-orchestrator-stop` (from `.claude\hooks\gate-orchestrator-stop.py`)
  - [ ] Add `gh-notif-intake-on-start` (from `.claude\hooks\gh-notif-intake-on-start.py`)
  - [ ] Add `github-search-via-ecosystem-scan` (from `.claude\hooks\github-search-via-ecosystem-scan.py`)
  - [ ] Add `implement-1c-task-preflight` (from `.claude\hooks\implement-1c-task-preflight.py`)
  - [ ] Add `implement-1c-task-smoke-stop-alert` (from `.claude\hooks\implement-1c-task-smoke-stop-alert.py`)
  - [ ] Add `lifecycle-cache` (from `.claude\hooks\lifecycle-cache.py`)
  - [ ] Add `logging-status-banner` (from `.claude\hooks\logging-status-banner.py`)
  - [ ] Add `mcp-invocation-logger` (from `.claude\hooks\mcp-invocation-logger.py`)
  - [ ] Add `memory-ai-acceptance-on-start` (from `.claude\hooks\memory-ai-acceptance-on-start.py`)
  - [ ] Add `memory-curation-candidates-on-start` (from `.claude\hooks\memory-curation-candidates-on-start.py`)
  - ... and 56 more

### Skill updates needed:

**`.claude/skills/create-hook/SKILL.md`** — 38 missing features:
  - [ ] Add `ci-catchup-on-stop` (from `.claude\hooks\ci-catchup-on-stop.py`)
  - [ ] Add `gate-orchestrator-stop` (from `.claude\hooks\gate-orchestrator-stop.py`)
  - [ ] Add `github-search-via-ecosystem-scan` (from `.claude\hooks\github-search-via-ecosystem-scan.py`)
  - [ ] Add `lifecycle-cache` (from `.claude\hooks\lifecycle-cache.py`)
  - [ ] Add `memory-ai-acceptance-on-start` (from `.claude\hooks\memory-ai-acceptance-on-start.py`)
  - [ ] Add `memory-curation-candidates-on-start` (from `.claude\hooks\memory-curation-candidates-on-start.py`)
  - [ ] Add `memory-effectiveness-analyzer` (from `.claude\hooks\memory-effectiveness-analyzer.py`)
  - [ ] Add `memory-maintenance-cadence` (from `.claude\hooks\memory-maintenance-cadence.py`)
  - [ ] Add `onec-state-first-guard` (from `.claude\hooks\onec-state-first-guard.py`)
  - [ ] Add `onec-task-completion-stop` (from `.claude\hooks\onec-task-completion-stop.py`)
  - [ ] Add `onec-task-input` (from `.claude\hooks\onec-task-input.py`)
  - [ ] Add `onec-toolgate-validation-on-start` (from `.claude\hooks\onec-toolgate-validation-on-start.py`)
  - [ ] Add `openspec-change-coverage` (from `.claude\hooks\openspec-change-coverage.py`)
  - [ ] Add `openspec-task-progress` (from `.claude\hooks\openspec-task-progress.py`)
  - [ ] Add `opsx-apply-postvalidate` (from `.claude\hooks\opsx-apply-postvalidate.py`)
  - [ ] Add `patterns-harvester` (from `.claude\hooks\patterns-harvester.py`)
  - [ ] Add `pipeline-1c-advance` (from `.claude\hooks\pipeline-1c-advance.py`)
  - [ ] Add `pipeline-gate` (from `.claude\hooks\pipeline-gate.py`)
  - [ ] Add `pipeline-protocol-stop` (from `.claude\hooks\pipeline-protocol-stop.py`)
  - [ ] Add `pipeline-protocol` (from `.claude\hooks\pipeline-protocol.py`)
  - ... and 18 more

**`.claude/skills/hooks-skills-mcp-triad/SKILL.md`** — 38 missing features:
  - [ ] Add `ci-catchup-on-stop` (from `.claude\hooks\ci-catchup-on-stop.py`)
  - [ ] Add `gate-orchestrator-stop` (from `.claude\hooks\gate-orchestrator-stop.py`)
  - [ ] Add `github-search-via-ecosystem-scan` (from `.claude\hooks\github-search-via-ecosystem-scan.py`)
  - [ ] Add `lifecycle-cache` (from `.claude\hooks\lifecycle-cache.py`)
  - [ ] Add `memory-ai-acceptance-on-start` (from `.claude\hooks\memory-ai-acceptance-on-start.py`)
  - [ ] Add `memory-curation-candidates-on-start` (from `.claude\hooks\memory-curation-candidates-on-start.py`)
  - [ ] Add `memory-effectiveness-analyzer` (from `.claude\hooks\memory-effectiveness-analyzer.py`)
  - [ ] Add `memory-maintenance-cadence` (from `.claude\hooks\memory-maintenance-cadence.py`)
  - [ ] Add `onec-state-first-guard` (from `.claude\hooks\onec-state-first-guard.py`)
  - [ ] Add `onec-task-completion-stop` (from `.claude\hooks\onec-task-completion-stop.py`)
  - [ ] Add `onec-task-input` (from `.claude\hooks\onec-task-input.py`)
  - [ ] Add `onec-toolgate-validation-on-start` (from `.claude\hooks\onec-toolgate-validation-on-start.py`)
  - [ ] Add `openspec-change-coverage` (from `.claude\hooks\openspec-change-coverage.py`)
  - [ ] Add `openspec-task-progress` (from `.claude\hooks\openspec-task-progress.py`)
  - [ ] Add `opsx-apply-postvalidate` (from `.claude\hooks\opsx-apply-postvalidate.py`)
  - [ ] Add `patterns-harvester` (from `.claude\hooks\patterns-harvester.py`)
  - [ ] Add `pipeline-1c-advance` (from `.claude\hooks\pipeline-1c-advance.py`)
  - [ ] Add `pipeline-gate` (from `.claude\hooks\pipeline-gate.py`)
  - [ ] Add `pipeline-protocol-stop` (from `.claude\hooks\pipeline-protocol-stop.py`)
  - [ ] Add `pipeline-protocol` (from `.claude\hooks\pipeline-protocol.py`)
  - ... and 18 more

**`.claude/skills/memory-unified/SKILL.md`** — 2 missing features:
  - [ ] Add `StoreRecord` (from `src\memory\orchestrator\cross_store_index.py`)
  - [ ] Add `MirrorLink` (from `src\memory\orchestrator\cross_store_sync.py`)

**`.claude/skills/wiki-pipeline/SKILL.md`** — 2 missing features:
  - [ ] Add `StoreRecord` (from `src\memory\orchestrator\cross_store_index.py`)
  - [ ] Add `MirrorLink` (from `src\memory\orchestrator\cross_store_sync.py`)

## All Extracted Features (reference)

### Agent Types (5)

- `analytical` — `src\pdf_framework\agents\analytical\agent.py`
- `plan_execute` — `src\pdf_framework\agents\plan_execute\agent.py`
- `rag` — `src\pdf_framework\agents\rag\agent.py`
- `research_v2` — `src\pdf_framework\agents\research_v2\agent.py`
- `multi` — `src\pdf_framework\agents\multi\orchestrator.py`

### bsl_tool (33)

- `CallGraphStore` — `src\bsl\call_graph\store.py`
- `BSLStyleProfile` — `src\bsl\coding_assistant\style_extractor.py`
- `BSLStyleExtractor` — `src\bsl\coding_assistant\style_extractor.py`
- `EvalResult` — `src\bsl\evaluation\metrics.py`
- `ObjectInfo` — `src\bsl\knowledge_graph\metadata_extractor.py`
- `MetadataExtractor` — `src\bsl\knowledge_graph\metadata_extractor.py`
- `Config` — `src\bsl\mcp_server\config.py`
- `OAuth2BearerMiddleware` — `src\bsl\mcp_server\http_server.py`
- `MCPHttpServer` — `src\bsl\mcp_server\http_server.py`
- `MCPProxy` — `src\bsl\mcp_server\mcp_server.py`
- `OneCClient` — `src\bsl\mcp_server\onec_client.py`
- `BSLASTParser` — `src\bsl\parser\bsl_ast_parser.py`
- `BSLChunk` — `src\bsl\parser\bsl_chunker.py`
- `BSLChunker` — `src\bsl\parser\bsl_chunker.py`
- `BSLContextEnricher` — `src\bsl\parser\context_enricher.py`
- `SymbolType` — `src\bsl\parser\models.py`
- `CompilationDirective` — `src\bsl\parser\models.py`
- `ModuleType` — `src\bsl\parser\models.py`
- `BSLParam` — `src\bsl\parser\models.py`
- `BSLCall` — `src\bsl\parser\models.py`
- `BSLSymbol` — `src\bsl\parser\models.py`
- `BSLVariable` — `src\bsl\parser\models.py`
- `BSLRegion` — `src\bsl\parser\models.py`
- `BSLModule` — `src\bsl\parser\models.py`
- `BSLSearchSettings` — `src\bsl\semantic_search\config.py`
- `RouterResult` — `src\bsl\semantic_search\hybrid_router.py`
- `SonarQubeConfig` — `src\bsl\sonar\config_manager.py`
- `ConfigManager` — `src\bsl\sonar\config_manager.py`
- `Issue` — `src\bsl\sonar\report_generator.py`
- `AnalysisReport` — `src\bsl\sonar\report_generator.py`
- `ReportGenerator` — `src\bsl\sonar\report_generator.py`
- `BSLRule` — `src\bsl\sonar\rules_manager.py`
- `RulesManager` — `src\bsl\sonar\rules_manager.py`

### CLI Commands (17)

- `index` — `src/cli/main.py`
- `search` — `src/cli/main.py`
- `ask` — `src/cli/main.py`
- `chat` — `src/cli/main.py`
- `stats` — `src/cli/main.py`
- `server` — `src/cli/main.py`
- `restart` — `src/cli/main.py`
- `dashboard` — `src/cli/main.py`
- `cache` — `src/cli/main.py`
- `tenant` — `src/cli/main.py`
- `auth` — `src/cli/main.py`
- `eval` — `src/cli/main.py`
- `ui` — `src/cli/main.py`
- `suggest` — `src/cli/main.py`
- `research` — `src/cli/main.py`
- `autorag` — `src/cli/main.py`
- `feedback` — `src/cli/main.py`

### Config Variables (.env) (298)

- `AGENT__MODEL` — `src\pdf_framework\config\agent.py`
- `AGENT__TEMPERATURE` — `src\pdf_framework\config\agent.py`
- `AGENT__MAX_TOKENS` — `src\pdf_framework\config\agent.py`
- `AGENT__SEARCH_K` — `src\pdf_framework\config\agent.py`
- `AGENT__RERANKER_ENABLED` — `src\pdf_framework\config\agent.py`
- `AGENT__RERANKER_TYPE` — `src\pdf_framework\config\agent.py`
- `AGENT__RERANKER_MODEL` — `src\pdf_framework\config\agent.py`
- `AGENT__COLBERT_MODEL` — `src\pdf_framework\config\agent.py`
- `AGENT__RERANKER_LLM_MODEL` — `src\pdf_framework\config\agent.py`
- `AGENT__RERANKER_TOP_K` — `src\pdf_framework\config\agent.py`
- `AGENT__CHECKPOINTER` — `src\pdf_framework\config\agent.py`
- `AGENT__BASE_URL` — `src\pdf_framework\config\agent.py`
- `AGENT__GRAPH_CONCURRENCY` — `src\pdf_framework\config\agent.py`
- `AGENT__COST_BUDGET_PER_QUERY` — `src\pdf_framework\config\agent.py`
- `AGENT__COST_BUDGET_DAILY` — `src\pdf_framework\config\agent.py`
- `SELF_RAG__ENABLED` — `src\pdf_framework\config\agent.py`
- `SELF_RAG__GRADING_MODEL` — `src\pdf_framework\config\agent.py`
- `SELF_RAG__RELEVANCE_THRESHOLD` — `src\pdf_framework\config\agent.py`
- `SELF_RAG__SCORE_PREFILTER_THRESHOLD` — `src\pdf_framework\config\agent.py`
- `SELF_RAG__MAX_RETRIES` — `src\pdf_framework\config\agent.py`
- `SELF_RAG__HALLUCINATION_CHECK_ENABLED` — `src\pdf_framework\config\agent.py`
- `SELF_RAG__MAX_GENERATION_ATTEMPTS` — `src\pdf_framework\config\agent.py`
- `SELF_RAG__MAX_CONTEXT_CHARS` — `src\pdf_framework\config\agent.py`
- `SELF_RAG__STRATEGY_ESCALATION_ENABLED` — `src\pdf_framework\config\agent.py`
- `SELF_RAG__ENRICHMENT_ENABLED` — `src\pdf_framework\config\agent.py`
- `SELF_RAG__ENRICHMENT_MAX_ROUNDS` — `src\pdf_framework\config\agent.py`
- `SELF_RAG__ENRICHMENT_SUB_QUERIES` — `src\pdf_framework\config\agent.py`
- `SELF_RAG__ENRICHMENT_K` — `src\pdf_framework\config\agent.py`
- `DEEP_RESEARCH__ENABLED` — `src\pdf_framework\config\agent.py`
- `DEEP_RESEARCH__MAX_SUB_QUESTIONS` — `src\pdf_framework\config\agent.py`
- `DEEP_RESEARCH__MAX_RETRIEVAL_STEPS` — `src\pdf_framework\config\agent.py`
- `EMBEDDING__PROVIDER` — `src\pdf_framework\config\embedding.py`
- `EMBEDDING__MODEL` — `src\pdf_framework\config\embedding.py`
- `EMBEDDING__DIMENSIONS` — `src\pdf_framework\config\embedding.py`
- `EMBEDDING__BATCH_SIZE` — `src\pdf_framework\config\embedding.py`
- `EMBEDDING__TEI_BASE_URL` — `src\pdf_framework\config\embedding.py`
- `EMBEDDING__TEI_CLIENT_BATCH` — `src\pdf_framework\config\embedding.py`
- `EMBEDDING__CACHE_ENABLED` — `src\pdf_framework\config\embedding.py`
- `EMBEDDING__CACHE_DIR` — `src\pdf_framework\config\embedding.py`
- `EMBEDDING__DEVICE` — `src\pdf_framework\config\embedding.py`
- `EMBEDDING__BACKEND` — `src\pdf_framework\config\embedding.py`
- `EMBEDDING__JINA_API_KEY` — `src\pdf_framework\config\embedding.py`
- `EMBEDDING__JINA_TASK` — `src\pdf_framework\config\embedding.py`
- `EMBEDDING__JINA_TRUNCATE_DIM` — `src\pdf_framework\config\embedding.py`
- `EMBEDDING__LATE_CHUNKING` — `src\pdf_framework\config\embedding.py`
- `EMBEDDING__LATE_CHUNKING_MAX_TOKENS` — `src\pdf_framework\config\embedding.py`
- `EXTERNAL__WEB_SEARCH_ENABLED` — `src\pdf_framework\config\external.py`
- `EXTERNAL__TAVILY_API_KEY` — `src\pdf_framework\config\external.py`
- `EXTERNAL__SERPAPI_KEY` — `src\pdf_framework\config\external.py`
- `EXTERNAL__CONFIDENCE_THRESHOLD` — `src\pdf_framework\config\external.py`
- `EXTERNAL__WEB_TRUST_SCORE` — `src\pdf_framework\config\external.py`
- `OPTIMIZATION__ENABLED` — `src\pdf_framework\config\external.py`
- `OPTIMIZATION__DATASET_PATH` — `src\pdf_framework\config\external.py`
- `OPTIMIZATION__OPTIMIZED_DIR` — `src\pdf_framework\config\external.py`
- `OPTIMIZATION__MODEL` — `src\pdf_framework\config\external.py`
- `OPTIMIZATION__MAX_TRIALS` — `src\pdf_framework\config\external.py`
- `PARENT_CHILD__ENABLED` — `src\pdf_framework\config\features.py`
- `PARENT_CHILD__PARENT_CHUNK_SIZE` — `src\pdf_framework\config\features.py`
- `PARENT_CHILD__PARENT_CHUNK_OVERLAP` — `src\pdf_framework\config\features.py`
- `PARENT_CHILD__CHILD_CHUNK_SIZE` — `src\pdf_framework\config\features.py`
- `PARENT_CHILD__CHILD_CHUNK_OVERLAP` — `src\pdf_framework\config\features.py`
- `PARENT_CHILD__MERGE_THRESHOLD` — `src\pdf_framework\config\features.py`
- `PARENT_CHILD__FETCH_MULTIPLIER` — `src\pdf_framework\config\features.py`
- `PARENT_CHILD__PARENT_STORE_PATH` — `src\pdf_framework\config\features.py`
- `ADAPTIVE__CLASSIFIER_MODEL` — `src\pdf_framework\config\features.py`
- `ADAPTIVE__CLASSIFIER_CACHE_ENABLED` — `src\pdf_framework\config\features.py`
- `ADAPTIVE__ROUTING_ENABLED` — `src\pdf_framework\config\features.py`
- `ADAPTIVE__DECOMPOSITION_ENABLED` — `src\pdf_framework\config\features.py`
- `ADAPTIVE__MAX_SUB_QUESTIONS` — `src\pdf_framework\config\features.py`
- `ADAPTIVE__ROUTE_SIMPLE_STRATEGY` — `src\pdf_framework\config\features.py`
- `ADAPTIVE__ROUTE_MODERATE_STRATEGY` — `src\pdf_framework\config\features.py`
- `ADAPTIVE__ROUTE_COMPLEX_STRATEGY` — `src\pdf_framework\config\features.py`
- `ADAPTIVE__ROUTE_THEMATIC_STRATEGY` — `src\pdf_framework\config\features.py`
- `ADAPTIVE__FAST_CLASSIFY_ENABLED` — `src\pdf_framework\config\features.py`
- `ADAPTIVE__BM25_EARLY_TERMINATION` — `src\pdf_framework\config\features.py`
- `ADAPTIVE__BM25_EARLY_THRESHOLD` — `src\pdf_framework\config\features.py`
- `ADAPTIVE__PARALLEL_DECOMPOSITION` — `src\pdf_framework\config\features.py`
- `ADAPTIVE__PARALLEL_EXPANSION` — `src\pdf_framework\config\features.py`
- `CONVERSATION__MEMORY_BACKEND` — `src\pdf_framework\config\features.py`
- `CONVERSATION__MAX_HISTORY` — `src\pdf_framework\config\features.py`
- `CONVERSATION__AUTO_CLEANUP_DAYS` — `src\pdf_framework\config\features.py`
- `CONVERSATION__DB_PATH` — `src\pdf_framework\config\features.py`
- `CONVERSATION__REFORMULATION_ENABLED` — `src\pdf_framework\config\features.py`
- `CONVERSATION__REFORMULATION_MODEL` — `src\pdf_framework\config\features.py`
- `LAYOUT__LAYOUT_DETECTION_ENABLED` — `src\pdf_framework\config\features.py`
- `LAYOUT__LAYOUT_PROVIDER` — `src\pdf_framework\config\features.py`
- `LAYOUT__LAYOUT_STRATEGY` — `src\pdf_framework\config\features.py`
- `LAYOUT__INFER_TABLE_STRUCTURE` — `src\pdf_framework\config\features.py`
- `LAYOUT__EXTRACT_TABLES` — `src\pdf_framework\config\features.py`
- `LAYOUT__MIN_TABLE_ROWS` — `src\pdf_framework\config\features.py`
- `LAYOUT__MIN_TABLE_COLS` — `src\pdf_framework\config\features.py`
- `LAYOUT__EXTRACT_IMAGES` — `src\pdf_framework\config\features.py`
- `LAYOUT__IMAGE_DESCRIPTION_MODEL` — `src\pdf_framework\config\features.py`
- `LAYOUT__MIN_IMAGE_SIZE` — `src\pdf_framework\config\features.py`
- `LAYOUT__PARSE_TEMPLATE` — `src\pdf_framework\config\features.py`
- `LAYOUT__STRUCTURE_AWARE_CHUNK_SIZE` — `src\pdf_framework\config\features.py`
- `LAYOUT__STRUCTURE_AWARE_OVERLAP` — `src\pdf_framework\config\features.py`
- `RAPTOR__ENABLED` — `src\pdf_framework\config\features.py`
- `RAPTOR__MAX_LEVELS` — `src\pdf_framework\config\features.py`
- `RAPTOR__SEARCH_MODE` — `src\pdf_framework\config\features.py`
- `RAPTOR__CLUSTER_METHOD` — `src\pdf_framework\config\features.py`
- `RAPTOR__SUMMARIZATION_MODEL` — `src\pdf_framework\config\features.py`
- `SUMMARY_INDEX__ENABLED` — `src\pdf_framework\config\features.py`
- `SUMMARY_INDEX__COLLECTION_NAME` — `src\pdf_framework\config\features.py`
- `SUMMARY_INDEX__SUMMARIZATION_MODEL` — `src\pdf_framework\config\features.py`
- `SUMMARY_INDEX__MIN_CHUNKS_FOR_SUMMARY` — `src\pdf_framework\config\features.py`
- `SUGGESTIONS__ENABLED` — `src\pdf_framework\config\features.py`
- `SUGGESTIONS__METHOD` — `src\pdf_framework\config\features.py`
- `SUGGESTIONS__CACHE_TTL` — `src\pdf_framework\config\features.py`
- `SUGGESTIONS__MAX_SUGGESTIONS` — `src\pdf_framework\config\features.py`
- `SUGGESTIONS__LLM_MODEL` — `src\pdf_framework\config\features.py`
- `GUARDRAILS__PII_MODE` — `src\pdf_framework\config\features.py`
- `GUARDRAILS__INJECTION_MODE` — `src\pdf_framework\config\features.py`
- `GUARDRAILS__INJECTION_THRESHOLD` — `src\pdf_framework\config\features.py`
- `GUARDRAILS__MAX_QUERY_LENGTH` — `src\pdf_framework\config\features.py`
- `GUARDRAILS__MAX_FILE_SIZE_BYTES` — `src\pdf_framework\config\features.py`
- `HIERARCHICAL__SECTION_FIRST_ENABLED` — `src\pdf_framework\config\features.py`
- `HIERARCHICAL__SUMMARY_ENABLED` — `src\pdf_framework\config\features.py`
- `HIERARCHICAL__SUMMARY_MODEL` — `src\pdf_framework\config\features.py`
- `HIERARCHICAL__SUMMARY_DB_PATH` — `src\pdf_framework\config\features.py`
- `HIERARCHICAL__CONTEXT_BREADCRUMB` — `src\pdf_framework\config\features.py`
- `VISUAL_SEARCH__ENABLED` — `src\pdf_framework\config\features.py`
- `VISUAL_SEARCH__COLLECTION_NAME` — `src\pdf_framework\config\features.py`
- `VISUAL_SEARCH__RENDER_DPI` — `src\pdf_framework\config\features.py`
- `VISUAL_SEARCH__HYBRID_WEIGHT_VISUAL` — `src\pdf_framework\config\features.py`
- `VISUAL_SEARCH__HYBRID_WEIGHT_TEXT` — `src\pdf_framework\config\features.py`
- `VISUAL_SEARCH__AUTO_DETECT_ENABLED` — `src\pdf_framework\config\features.py`
- `VISUAL_SEARCH__VISUAL_KEYWORDS` — `src\pdf_framework\config\features.py`
- `GRAPH_RAG__COMMUNITY_DETECTION_ENABLED` — `src\pdf_framework\config\graphrag.py`
- `GRAPH_RAG__LEIDEN_RESOLUTION` — `src\pdf_framework\config\graphrag.py`
- `GRAPH_RAG__COMMUNITY_LEVELS` — `src\pdf_framework\config\graphrag.py`
- `GRAPH_RAG__SUMMARY_MODEL` — `src\pdf_framework\config\graphrag.py`
- `GRAPH_RAG__SUMMARY_CACHE_ENABLED` — `src\pdf_framework\config\graphrag.py`
- `GRAPH_RAG__LOCAL_SEARCH_DEPTH` — `src\pdf_framework\config\graphrag.py`
- `GRAPH_RAG__LOCAL_SEARCH_INCLUDE_SUMMARY` — `src\pdf_framework\config\graphrag.py`
- `GRAPH_RAG__GLOBAL_SEARCH_MAX_COMMUNITIES` — `src\pdf_framework\config\graphrag.py`
- `GRAPH_RAG__GLOBAL_SEARCH_RANK_BY_SIMILARITY` — `src\pdf_framework\config\graphrag.py`
- `GRAPH_RAG__GLOBAL_SEARCH_MAP_MODEL` — `src\pdf_framework\config\graphrag.py`
- `GRAPH_RAG__GLOBAL_SEARCH_REDUCE_MODEL` — `src\pdf_framework\config\graphrag.py`
- `GRAPH_RAG__INCREMENTAL_UPDATES_ENABLED` — `src\pdf_framework\config\graphrag.py`
- `GRAPH_RAG__AUTO_UPDATE_ENABLED` — `src\pdf_framework\config\graphrag.py`
- `GRAPH_RAG__AUTO_UPDATE_ON_REINDEX` — `src\pdf_framework\config\graphrag.py`
- `LIGHT_RAG__ENABLED` — `src\pdf_framework\config\graphrag.py`
- `LIGHT_RAG__COLLECTION_NAME` — `src\pdf_framework\config\graphrag.py`
- `LIGHT_RAG__ENTITY_TOP_K` — `src\pdf_framework\config\graphrag.py`
- `LIGHT_RAG__RELATION_TOP_K` — `src\pdf_framework\config\graphrag.py`
- `LIGHT_RAG__NEIGHBOR_DEPTH` — `src\pdf_framework\config\graphrag.py`
- `LIGHT_RAG__MAX_CHUNKS` — `src\pdf_framework\config\graphrag.py`
- `LIGHT_RAG__AUTO_SELECT_ENABLED` — `src\pdf_framework\config\graphrag.py`
- `LIGHT_RAG__LIGHT_COMPLEXITIES` — `src\pdf_framework\config\graphrag.py`
- `LIGHT_RAG__FULL_COMPLEXITIES` — `src\pdf_framework\config\graphrag.py`
- `GRAPH_STORE__PROVIDER` — `src\pdf_framework\config\infrastructure.py`
- `GRAPH_STORE__PERSIST_DIR` — `src\pdf_framework\config\infrastructure.py`
- `GRAPH_STORE__NEO4J_URI` — `src\pdf_framework\config\infrastructure.py`
- `GRAPH_STORE__NEO4J_USER` — `src\pdf_framework\config\infrastructure.py`
- `GRAPH_STORE__NEO4J_PASSWORD` — `src\pdf_framework\config\infrastructure.py`
- `MCP_SERVER__NAME` — `src\pdf_framework\config\infrastructure.py`
- `MCP_SERVER__VERSION` — `src\pdf_framework\config\infrastructure.py`
- `MCP_SERVER__TRANSPORT` — `src\pdf_framework\config\infrastructure.py`
- `API__HOST` — `src\pdf_framework\config\infrastructure.py`
- `API__PORT` — `src\pdf_framework\config\infrastructure.py`
- `API__CORS_ORIGINS` — `src\pdf_framework\config\infrastructure.py`
- `AUTH__ENABLED` — `src\pdf_framework\config\infrastructure.py`
- `AUTH__JWT_SECRET` — `src\pdf_framework\config\infrastructure.py`
- `AUTH__JWT_ALGORITHM` — `src\pdf_framework\config\infrastructure.py`
- `AUTH__TOKEN_EXPIRE_HOURS` — `src\pdf_framework\config\infrastructure.py`
- `AUTH__DEFAULT_TENANT` — `src\pdf_framework\config\infrastructure.py`
- `UI__ENABLED` — `src\pdf_framework\config\infrastructure.py`
- `UI__HOST` — `src\pdf_framework\config\infrastructure.py`
- `UI__PORT` — `src\pdf_framework\config\infrastructure.py`
- `UI__SHARE` — `src\pdf_framework\config\infrastructure.py`
- `UI__THEME` — `src\pdf_framework\config\infrastructure.py`
- `UI__API_BACKEND_URL` — `src\pdf_framework\config\infrastructure.py`
- `OPENAI_COMPAT__ENABLED` — `src\pdf_framework\config\infrastructure.py`
- `QUEUE__ENABLED` — `src\pdf_framework\config\infrastructure.py`
- `QUEUE__REDIS_URL` — `src\pdf_framework\config\infrastructure.py`
- `QUEUE__MAX_JOBS` — `src\pdf_framework\config\infrastructure.py`
- `QUEUE__JOB_TIMEOUT` — `src\pdf_framework\config\infrastructure.py`
- `QUEUE__RETRY_ATTEMPTS` — `src\pdf_framework\config\infrastructure.py`
- `QUEUE__RETRY_DELAY_SECONDS` — `src\pdf_framework\config\infrastructure.py`
- `QUEUE__QUEUE_NAME` — `src\pdf_framework\config\infrastructure.py`
- `QUEUE__HEALTH_CHECK_INTERVAL` — `src\pdf_framework\config\infrastructure.py`
- `OBSERVABILITY__TRACER` — `src\pdf_framework\config\observability.py`
- `OBSERVABILITY__TRACE_DIR` — `src\pdf_framework\config\observability.py`
- `OBSERVABILITY__LANGSMITH_ENABLED` — `src\pdf_framework\config\observability.py`
- `OBSERVABILITY__LANGFUSE_ENABLED` — `src\pdf_framework\config\observability.py`
- `OBSERVABILITY__LANGFUSE_PUBLIC_KEY` — `src\pdf_framework\config\observability.py`
- `OBSERVABILITY__LANGFUSE_SECRET_KEY` — `src\pdf_framework\config\observability.py`
- `OBSERVABILITY__LANGFUSE_HOST` — `src\pdf_framework\config\observability.py`
- `OBSERVABILITY__LANGFUSE_PROJECT_NAME` — `src\pdf_framework\config\observability.py`
- `CACHE__EMBEDDING_ENABLED` — `src\pdf_framework\config\observability.py`
- `CACHE__EMBEDDING_TTL_DAYS` — `src\pdf_framework\config\observability.py`
- `CACHE__EMBEDDING_DB_PATH` — `src\pdf_framework\config\observability.py`
- `CACHE__LLM_ENABLED` — `src\pdf_framework\config\observability.py`
- `CACHE__LLM_TTL_SECONDS` — `src\pdf_framework\config\observability.py`
- `CACHE__LLM_DB_PATH` — `src\pdf_framework\config\observability.py`
- `CACHE__DOCUMENT_ENABLED` — `src\pdf_framework\config\observability.py`
- `CACHE__DOCUMENT_CACHE_DIR` — `src\pdf_framework\config\observability.py`
- `CACHE__PROMPT_CACHING_ENABLED` — `src\pdf_framework\config\observability.py`
- `CACHE__SEMANTIC_ENABLED` — `src\pdf_framework\config\observability.py`
- `CACHE__SEMANTIC_THRESHOLD` — `src\pdf_framework\config\observability.py`
- `CACHE__SEMANTIC_TTL_SECONDS` — `src\pdf_framework\config\observability.py`
- `CACHE__SEMANTIC_MAX_ENTRIES` — `src\pdf_framework\config\observability.py`
- `CACHE__SEMANTIC_DB_PATH` — `src\pdf_framework\config\observability.py`
- `FEEDBACK__ENABLED` — `src\pdf_framework\config\observability.py`
- `FEEDBACK__DB_PATH` — `src\pdf_framework\config\observability.py`
- `FEEDBACK__ASYNC_DB_PATH` — `src\pdf_framework\config\observability.py`
- `FEEDBACK__FEW_SHOT_MAX_EXAMPLES` — `src\pdf_framework\config\observability.py`
- `FEEDBACK__FEW_SHOT_SIMILARITY_THRESHOLD` — `src\pdf_framework\config\observability.py`
- `FEEDBACK__BOOST_MAX` — `src\pdf_framework\config\observability.py`
- `FEEDBACK__BOOST_MIN_COUNT` — `src\pdf_framework\config\observability.py`
- `RAGAS_EVAL__ENABLED` — `src\pdf_framework\config\observability.py`
- `RAGAS_EVAL__EVAL_HISTORY_DB_PATH` — `src\pdf_framework\config\observability.py`
- `RAGAS_EVAL__REGRESSION_THRESHOLD` — `src\pdf_framework\config\observability.py`
- `RAGAS_EVAL__BASELINE_PATH` — `src\pdf_framework\config\observability.py`
- `AUTORAG__ENABLED` — `src\pdf_framework\config\observability.py`
- `AUTORAG__MAX_EXPERIMENTS` — `src\pdf_framework\config\observability.py`
- `AUTORAG__OUTPUT_DIR` — `src\pdf_framework\config\observability.py`
- `PDF__CHUNK_SIZE` — `src\pdf_framework\config\pdf.py`
- `PDF__CHUNK_OVERLAP` — `src\pdf_framework\config\pdf.py`
- `PDF__EXTRACT_TABLES` — `src\pdf_framework\config\pdf.py`
- `PDF__EXTRACT_IMAGES` — `src\pdf_framework\config\pdf.py`
- `PDF__SEMANTIC_THRESHOLD` — `src\pdf_framework\config\pdf.py`
- `PDF__MIN_CHUNK_SIZE` — `src\pdf_framework\config\pdf.py`
- `PDF__MAX_CHUNK_SIZE` — `src\pdf_framework\config\pdf.py`
- `DOCLING__OCR_ENABLED` — `src\pdf_framework\config\pdf.py`
- `DOCLING__OCR_ENGINE` — `src\pdf_framework\config\pdf.py`
- `DOCLING__OCR_LANGUAGES` — `src\pdf_framework\config\pdf.py`
- `DOCLING__FORCE_FULL_PAGE_OCR` — `src\pdf_framework\config\pdf.py`
- `DOCLING__TABLE_STRUCTURE_ENABLED` — `src\pdf_framework\config\pdf.py`
- `DOCLING__TABLE_MODE` — `src\pdf_framework\config\pdf.py`
- `DOCLING__EXTRACT_IMAGES` — `src\pdf_framework\config\pdf.py`
- `DOCLING__GENERATE_PICTURE_IMAGES` — `src\pdf_framework\config\pdf.py`
- `DOCLING__DOCUMENT_TIMEOUT` — `src\pdf_framework\config\pdf.py`
- `DOCLING__LAYOUT_BATCH_SIZE` — `src\pdf_framework\config\pdf.py`
- `DOCLING__OCR_BATCH_SIZE` — `src\pdf_framework\config\pdf.py`
- `DOCLING__TABLE_BATCH_SIZE` — `src\pdf_framework\config\pdf.py`
- `DOCLING__USE_ONNX` — `src\pdf_framework\config\pdf.py`
- `SMART_ROUTER__MIN_TEXT_CHARS_PER_PAGE` — `src\pdf_framework\config\pdf.py`
- `SMART_ROUTER__COMPLEX_LAYOUT_THRESHOLD` — `src\pdf_framework\config\pdf.py`
- `SMART_ROUTER__TABLE_HEAVY_THRESHOLD` — `src\pdf_framework\config\pdf.py`
- `SMART_ROUTER__FAST_LOADER` — `src\pdf_framework\config\pdf.py`
- `SMART_ROUTER__FULL_LOADER` — `src\pdf_framework\config\pdf.py`
- `HYBRID_LOADER__ENABLE_FITZ_TABLES` — `src\pdf_framework\config\pdf.py`
- `HYBRID_LOADER__ENABLE_DOCLING_TABLES` — `src\pdf_framework\config\pdf.py`
- `HYBRID_LOADER__ENABLE_VISION_OCR` — `src\pdf_framework\config\pdf.py`
- `HYBRID_LOADER__VERIFY_COVERAGE` — `src\pdf_framework\config\pdf.py`
- `HYBRID_LOADER__COVERAGE_THRESHOLD` — `src\pdf_framework\config\pdf.py`
- `HYBRID_LOADER__TABLE_DEDUP_ENABLED` — `src\pdf_framework\config\pdf.py`
- `HYBRID_LOADER__TABLE_DEDUP_THRESHOLD` — `src\pdf_framework\config\pdf.py`
- `HYBRID_LOADER__DOCLING_MAX_RETRIES` — `src\pdf_framework\config\pdf.py`
- `HYBRID_LOADER__DOCLING_TABLE_MODE` — `src\pdf_framework\config\pdf.py`
- `HYBRID_LOADER__VISION_MODEL` — `src\pdf_framework\config\pdf.py`
- `HYBRID_LOADER__VISION_MAX_RETRIES` — `src\pdf_framework\config\pdf.py`
- `HYBRID_LOADER__VISION_DPI` — `src\pdf_framework\config\pdf.py`
- `HYBRID_LOADER__VISION_MIN_TEXT_CHARS` — `src\pdf_framework\config\pdf.py`
- `SEARCH__HYBRID_VECTOR_WEIGHT` — `src\pdf_framework\config\search.py`
- `SEARCH__HYBRID_GRAPH_WEIGHT` — `src\pdf_framework\config\search.py`
- `SEARCH__HYBRID_RRF_K` — `src\pdf_framework\config\search.py`
- `SEARCH__BM25_ENABLED` — `src\pdf_framework\config\search.py`
- `SEARCH__BM25_WEIGHT` — `src\pdf_framework\config\search.py`
- `SEARCH__BM25_DB_PATH` — `src\pdf_framework\config\search.py`
- `SEARCH__BM25_BACKEND` — `src\pdf_framework\config\search.py`
- `SEARCH__BM25_TWO_PASS` — `src\pdf_framework\config\search.py`
- `SEARCH__DYNAMIC_WEIGHTING_ENABLED` — `src\pdf_framework\config\search.py`
- `SEARCH__MMR_DIVERSITY_LAMBDA` — `src\pdf_framework\config\search.py`
- `SEARCH__MMR_FETCH_K` — `src\pdf_framework\config\search.py`
- `SEARCH__QUERY_EXPANSION_ENABLED` — `src\pdf_framework\config\search.py`
- `SEARCH__QUERY_EXPANSION_METHOD` — `src\pdf_framework\config\search.py`
- `SEARCH__FLASHRANK_ENABLED` — `src\pdf_framework\config\search.py`
- `SEARCH__FLASHRANK_TOKEN_BUDGET` — `src\pdf_framework\config\search.py`
- `CONTEXTUAL_RETRIEVAL__ENABLED` — `src\pdf_framework\config\search.py`
- `CONTEXTUAL_RETRIEVAL__MAX_CONTEXT_TOKENS` — `src\pdf_framework\config\search.py`
- `CONTEXTUAL_RETRIEVAL__MODEL` — `src\pdf_framework\config\search.py`
- `CONTEXTUAL_RETRIEVAL__BATCH_CONCURRENCY` — `src\pdf_framework\config\search.py`
- `CONTEXTUAL_RETRIEVAL__MIN_CHUNK_TOKENS` — `src\pdf_framework\config\search.py`
- `CONTEXTUAL_RETRIEVAL__CACHE_ENABLED` — `src\pdf_framework\config\search.py`
- `CONTEXTUAL_RETRIEVAL__CACHE_DB_PATH` — `src\pdf_framework\config\search.py`
- `TWO_STAGE__ENABLED` — `src\pdf_framework\config\search.py`
- `TWO_STAGE__STAGE1_K` — `src\pdf_framework\config\search.py`
- `TWO_STAGE__STAGE1_STRATEGY` — `src\pdf_framework\config\search.py`
- `TWO_STAGE__STAGE2_RERANK_K` — `src\pdf_framework\config\search.py`
- `TWO_STAGE__STAGE2_USE_MMR` — `src\pdf_framework\config\search.py`
- `TWO_STAGE__STAGE2_MMR_LAMBDA` — `src\pdf_framework\config\search.py`
- `TWO_STAGE__STAGE2_USE_FLASHRANK` — `src\pdf_framework\config\search.py`
- `VECTOR_STORE__PROVIDER` — `src\pdf_framework\config\vector_store.py`
- `VECTOR_STORE__DIMENSIONS` — `src\pdf_framework\config\vector_store.py`
- `VECTOR_STORE__QDRANT_URL` — `src\pdf_framework\config\vector_store.py`
- `VECTOR_STORE__QDRANT_API_KEY` — `src\pdf_framework\config\vector_store.py`
- `VECTOR_STORE__PGVECTOR_DSN` — `src\pdf_framework\config\vector_store.py`
- `VECTOR_STORE__PGVECTOR_TABLE_NAME` — `src\pdf_framework\config\vector_store.py`
- `VECTOR_STORE__PERSIST_DIR` — `src\pdf_framework\config\vector_store.py`
- `VECTOR_STORE__COLLECTION_NAME` — `src\pdf_framework\config\vector_store.py`
- `VECTOR_STORE__DISTANCE_METRIC` — `src\pdf_framework\config\vector_store.py`
- `VECTOR_STORE__QDRANT_BM25_ENABLED` — `src\pdf_framework\config\vector_store.py`
- `VECTOR_STORE__QDRANT_BM25_LANGUAGE` — `src\pdf_framework\config\vector_store.py`
- `VECTOR_STORE__QDRANT_BM25_K` — `src\pdf_framework\config\vector_store.py`
- `VECTOR_STORE__QDRANT_BM25_B` — `src\pdf_framework\config\vector_store.py`

### REST API Endpoints (88)

- `GET /analytics/summary` — `src\api\routes\analytics.py`
- `GET /analytics/queries` — `src\api\routes\analytics.py`
- `GET /analytics/queries/recent` — `src\api\routes\analytics.py`
- `GET /analytics/costs` — `src\api\routes\analytics.py`
- `GET /analytics/audit` — `src\api\routes\analytics.py`
- `GET /analytics/audit/stats` — `src\api\routes\analytics.py`
- `GET /analytics/audit/user/{user_id}` — `src\api\routes\analytics.py`
- `POST /auth/token` — `src\api\routes\auth.py`
- `POST /auth/validate` — `src\api\routes\auth.py`
- `GET /cache/stats` — `src\api\routes\cache.py`
- `POST /cache/clear` — `src\api\routes\cache.py`
- `POST /chat/message` — `src\api\routes\chat.py`
- `GET /chat/history/{thread_id}` — `src\api\routes\chat.py`
- `DELETE /chat/history/{thread_id}` — `src\api\routes\chat.py`
- `GET /chat/threads` — `src\api\routes\chat.py`
- `GET /chat/stats/{thread_id}` — `src\api\routes\chat.py`
- `POST /collections/` — `src\api\routes\collections.py`
- `GET /collections/` — `src\api\routes\collections.py`
- `GET /collections/{collection_id}` — `src\api\routes\collections.py`
- `PATCH /collections/{collection_id}` — `src\api\routes\collections.py`
- `DELETE /collections/{collection_id}` — `src\api\routes\collections.py`
- `POST /collections/{collection_id}/documents` — `src\api\routes\collections.py`
- `DELETE /collections/{collection_id}/documents/{document_id}` — `src\api\routes\collections.py`
- `GET /collections/{collection_id}/documents` — `src\api\routes\collections.py`
- `POST /documents/upload` — `src\api\routes\documents.py`
- `POST /documents/index` — `src\api\routes\documents.py`
- `POST /documents/index/stream` — `src\api\routes\documents.py`
- `POST /documents/index/batch/stream` — `src\api\routes\documents.py`
- `GET /documents/files` — `src\api\routes\documents.py`
- `GET /documents/registry` — `src\api\routes\documents.py`
- `PATCH /documents/registry/{document_id}` — `src\api\routes\documents.py`
- `GET /documents/` — `src\api\routes\documents.py`
- `GET /documents/stats` — `src\api\routes\documents.py`
- `DELETE /documents/clear` — `src\api\routes\documents.py`
- `POST /documents/rebuild-sparse` — `src\api\routes\documents.py`
- `POST /documents/rebuild-bm25` — `src\api\routes\documents.py`
- `DELETE /documents/{document_id}` — `src\api\routes\documents.py`
- `POST /documents/index/delta` — `src\api\routes\documents.py`
- `GET /documents/index/delta/stats` — `src\api\routes\documents.py`
- `POST /documents/index/delta/clear` — `src\api\routes\documents.py`
- `POST /documents/index-async` — `src\api\routes\documents.py`
- `POST /feedback/submit` — `src\api\routes\feedback.py`
- `GET /feedback/stats` — `src\api\routes\feedback.py`
- `GET /feedback/examples/positive` — `src\api\routes\feedback.py`
- `POST /feedback/tune` — `src\api\routes\feedback.py`
- `POST /feedback/clear` — `src\api\routes\feedback.py`
- `GET /graph/stats` — `src\api\routes\graph.py`
- `GET /graph/entities` — `src\api\routes\graph.py`
- `DELETE /graph/clear` — `src\api\routes\graph.py`
- `POST /graph/build-communities` — `src\api\routes\graph.py`
- `POST /graph/build-entity-embeddings` — `src\api\routes\graph.py`
- `GET /graph/entity-embeddings/stats` — `src\api\routes\graph.py`
- `GET /graph/neighbors/{entity_id}` — `src\api\routes\graph.py`
- `POST /graph/incremental-update` — `src\api\routes\graph.py`
- `GET /graph/incremental/detect-changes` — `src\api\routes\graph.py`
- `GET /health/ready` — `src\api\routes\health.py`
- `GET /health/live` — `src\api\routes\health.py`
- `POST /jobs/enqueue` — `src\api\routes\jobs.py`
- `GET /jobs/{job_id}` — `src\api\routes\jobs.py`
- `DELETE /jobs/{job_id}` — `src\api\routes\jobs.py`
- `GET /jobs/{job_id}/stream` — `src\api\routes\jobs.py`
- `GET /metrics/html` — `src\api\routes\metrics.py`
- `POST /metrics/reset` — `src\api\routes\metrics.py`
- `GET /metrics/prometheus` — `src\api\routes\metrics.py`
- `POST /openai_compat/chat/completions` — `src\api\routes\openai_compat.py`
- `POST /openai_compat/embeddings` — `src\api\routes\openai_compat.py`
- `GET /openai_compat/models` — `src\api\routes\openai_compat.py`
- `GET /optimization/stats` — `src\api\routes\optimization.py`
- `POST /optimization/optimize` — `src\api\routes\optimization.py`
- `GET /optimization/dataset` — `src\api\routes\optimization.py`
- `POST /optimization/dataset/add` — `src\api\routes\optimization.py`
- `GET /optimization/last-result` — `src\api\routes\optimization.py`
- `POST /search/` — `src\api\routes\search.py`
- `POST /search/ask` — `src\api\routes\search.py`
- `POST /search/analyze` — `src\api\routes\search.py`
- `POST /search/research` — `src\api\routes\search.py`
- `POST /search/multi-agent` — `src\api\routes\search.py`
- `POST /search/visual` — `src\api\routes\search.py`
- `POST /search/plan-execute` — `src\api\routes\search.py`
- `GET /tenants/{tenant_id}` — `src\api\routes\tenants.py`
- `GET /tenants/{tenant_id}/stats` — `src\api\routes\tenants.py`
- `GET /tenants/{tenant_id}/usage` — `src\api\routes\tenants.py`
- `PUT /tenants/{tenant_id}` — `src\api\routes\tenants.py`
- `DELETE /tenants/{tenant_id}` — `src\api\routes\tenants.py`
- `GET /toc/{document_id}` — `src\api\routes\toc.py`
- `GET /toc/{document_id}/section/{section_number:path}` — `src\api\routes\toc.py`
- `POST /toc/{document_id}/generate-summaries` — `src\api\routes\toc.py`
- `WEBSOCKET /websocket/ws/search` — `src\api\routes\websocket.py`

### hook (97)

- `analyze-1c-task-preflight` — `.claude\hooks\analyze-1c-task-preflight.py`
- `approval-gate` — `.claude\hooks\approval-gate.py`
- `audit-coverage-check` — `.claude\hooks\audit-coverage-check.py`
- `auto-git-save-prompt` — `.claude\hooks\auto-git-save-prompt.py`
- `auto-git-save` — `.claude\hooks\auto-git-save.py`
- `bsl-tool-router` — `.claude\hooks\bsl-tool-router.py`
- `bulk-action-guard` — `.claude\hooks\bulk-action-guard.py`
- `ci-catchup-on-start` — `.claude\hooks\ci-catchup-on-start.py`
- `ci-catchup-on-stop` — `.claude\hooks\ci-catchup-on-stop.py`
- `code-review-enforcer` — `.claude\hooks\code-review-enforcer.py`
- `code-skill-enforcer` — `.claude\hooks\code-skill-enforcer.py`
- `code-verify-reminder` — `.claude\hooks\code-verify-reminder.py`
- `decision-to-triad` — `.claude\hooks\decision-to-triad.py`
- `delegation-outcome-stop` — `.claude\hooks\delegation-outcome-stop.py`
- `delegation-outcome-tracker` — `.claude\hooks\delegation-outcome-tracker.py`
- `docs-change-enforcer` — `.claude\hooks\docs-change-enforcer.py`
- `docs-change-tracker` — `.claude\hooks\docs-change-tracker.py`
- `document-persistence` — `.claude\hooks\document-persistence.py`
- `ensure-docker-qdrant` — `.claude\hooks\ensure-docker-qdrant.py`
- `factory-enforcer` — `.claude\hooks\factory-enforcer.py`
- `gate-orchestrator-stop` — `.claude\hooks\gate-orchestrator-stop.py`
- `gh-notif-intake-on-start` — `.claude\hooks\gh-notif-intake-on-start.py`
- `git-commit-enforcer` — `.claude\hooks\git-commit-enforcer.py`
- `github-search-via-ecosystem-scan` — `.claude\hooks\github-search-via-ecosystem-scan.py`
- `implement-1c-task-preflight` — `.claude\hooks\implement-1c-task-preflight.py`
- `implement-1c-task-smoke-stop-alert` — `.claude\hooks\implement-1c-task-smoke-stop-alert.py`
- `knowledge-cache-reminder` — `.claude\hooks\knowledge-cache-reminder.py`
- `lifecycle-cache` — `.claude\hooks\lifecycle-cache.py`
- `logging-status-banner` — `.claude\hooks\logging-status-banner.py`
- `mcp-invocation-logger` — `.claude\hooks\mcp-invocation-logger.py`
- `memory-ai-acceptance-on-start` — `.claude\hooks\memory-ai-acceptance-on-start.py`
- `memory-curation-candidates-on-start` — `.claude\hooks\memory-curation-candidates-on-start.py`
- `memory-effectiveness-analyzer` — `.claude\hooks\memory-effectiveness-analyzer.py`
- `memory-first-hook` — `.claude\hooks\memory-first-hook.py`
- `memory-maintenance-cadence` — `.claude\hooks\memory-maintenance-cadence.py`
- `memory-sync` — `.claude\hooks\memory-sync.py`
- `onec-state-first-guard` — `.claude\hooks\onec-state-first-guard.py`
- `onec-task-completion-stop` — `.claude\hooks\onec-task-completion-stop.py`
- `onec-task-input` — `.claude\hooks\onec-task-input.py`
- `onec-toolgate-validation-on-start` — `.claude\hooks\onec-toolgate-validation-on-start.py`
- `openspec-change-coverage` — `.claude\hooks\openspec-change-coverage.py`
- `openspec-task-progress` — `.claude\hooks\openspec-task-progress.py`
- `opsx-apply-postvalidate` — `.claude\hooks\opsx-apply-postvalidate.py`
- `pattern-reinforce-stop` — `.claude\hooks\pattern-reinforce-stop.py`
- `patterns-harvester` — `.claude\hooks\patterns-harvester.py`
- `pipeline-1c-advance` — `.claude\hooks\pipeline-1c-advance.py`
- `pipeline-gate` — `.claude\hooks\pipeline-gate.py`
- `pipeline-protocol-stop` — `.claude\hooks\pipeline-protocol-stop.py`
- `pipeline-protocol` — `.claude\hooks\pipeline-protocol.py`
- `post-indexing-analyzer` — `.claude\hooks\post-indexing-analyzer.py`
- `post-merge-revert-stop` — `.claude\hooks\post-merge-revert-stop.py`
- `post-task-push-pr` — `.claude\hooks\post-task-push-pr.py`
- `posttooluse-auto-git-save` — `.claude\hooks\posttooluse-auto-git-save.py`
- `posttooluse-bash-errors` — `.claude\hooks\posttooluse-bash-errors.py`
- `posttooluse-delegation-tracker` — `.claude\hooks\posttooluse-delegation-tracker.py`
- `posttooluse-docs-tracker` — `.claude\hooks\posttooluse-docs-tracker.py`
- `posttooluse-quality-feedback` — `.claude\hooks\posttooluse-quality-feedback.py`
- `posttooluse-skill-metrics` — `.claude\hooks\posttooluse-skill-metrics.py`
- `posttooluse-stackoverflow-on-error` — `.claude\hooks\posttooluse-stackoverflow-on-error.py`
- `posttooluse-web-cache` — `.claude\hooks\posttooluse-web-cache.py`
- `pre-merge-review-check` — `.claude\hooks\pre-merge-review-check.py`
- `prework-architecture` — `.claude\hooks\prework-architecture.py`
- `prework-github-bp` — `.claude\hooks\prework-github-bp.py`
- `prework-similar-code` — `.claude\hooks\prework-similar-code.py`
- `prework-stackoverflow` — `.claude\hooks\prework-stackoverflow.py`
- `process-guard` — `.claude\hooks\process-guard.py`
- `ralph_activator` — `.claude\hooks\ralph_activator.py`
- `ralph_wiggum_stop` — `.claude\hooks\ralph_wiggum_stop.py`
- `research-task-detector` — `.claude\hooks\research-task-detector.py`
- `roadmap-progress-enforcer` — `.claude\hooks\roadmap-progress-enforcer.py`
- `root-clutter-guard` — `.claude\hooks\root-clutter-guard.py`
- `search-optimizer` — `.claude\hooks\search-optimizer.py`
- `session-context-enforcer` — `.claude\hooks\session-context-enforcer.py`
- `session-memory-save` — `.claude\hooks\session-memory-save.py`
- `session-mypy-banner` — `.claude\hooks\session-mypy-banner.py`
- `skill-eval-enforcer-shell` — `.claude\hooks\skill-eval-enforcer-shell.py`
- `skill-eval-enforcer` — `.claude\hooks\skill-eval-enforcer.py`
- `skill-learning-acceptance-on-start` — `.claude\hooks\skill-learning-acceptance-on-start.py`
- `skill-learning-pending-on-start` — `.claude\hooks\skill-learning-pending-on-start.py`
- `skill-quality-monitor` — `.claude\hooks\skill-quality-monitor.py`
- `skill-router` — `.claude\hooks\skill-router.py`
- `skill-system-acceptance-on-start` — `.claude\hooks\skill-system-acceptance-on-start.py`
- `skill-usage-metrics` — `.claude\hooks\skill-usage-metrics.py`
- `skills-harvester` — `.claude\hooks\skills-harvester.py`
- `slash-command-tracker` — `.claude\hooks\slash-command-tracker.py`
- `stop-feedback-draft-aggregator` — `.claude\hooks\stop-feedback-draft-aggregator.py`
- `submodule-status-check` — `.claude\hooks\submodule-status-check.py`
- `task-enforcer` — `.claude\hooks\task-enforcer.py`
- `task-protocol-enforcer` — `.claude\hooks\task-protocol-enforcer.py`
- `task-protocol-observer` — `.claude\hooks\task-protocol-observer.py`
- `tdd-guard-validation-on-start` — `.claude\hooks\tdd-guard-validation-on-start.py`
- `tdd-guard` — `.claude\hooks\tdd-guard.py`
- `tei-warmup-on-start` — `.claude\hooks\tei-warmup-on-start.py`
- `todo-sync` — `.claude\hooks\todo-sync.py`
- `userpromptsubmit-feedback-detector` — `.claude\hooks\userpromptsubmit-feedback-detector.py`
- `z-ai-delegation-enforcer` — `.claude\hooks\z-ai-delegation-enforcer.py`
- `z-ai-write-guard` — `.claude\hooks\z-ai-write-guard.py`

### MCP Tools (15)

- `index_pdf` — `src/mcp_server/server.py`
- `search_documents` — `src/mcp_server/server.py`
- `ask_question` — `src/mcp_server/server.py`
- `graph_query` — `src/mcp_server/server.py`
- `analyze` — `src/mcp_server/server.py`
- `research` — `src/mcp_server/server.py`
- `web_search` — `src/mcp_server/server.py`
- `search_with_fallback` — `src/mcp_server/server.py`
- `list_collections` — `src/mcp_server/server.py`
- `list_documents` — `src/mcp_server/server.py`
- `get_toc` — `src/mcp_server/server.py`
- `get_stats` — `src/mcp_server/server.py`
- `visual_search` — `src/mcp_server/server.py`
- `visual_hybrid_search` — `src/mcp_server/server.py`
- `plan_execute` — `src/mcp_server/server.py`

### memory_subsystem (62)

- `StoreRecord` — `src\memory\orchestrator\cross_store_index.py`
- `MirrorLink` — `src\memory\orchestrator\cross_store_sync.py`
- `LinkType` — `src\memory\orchestrator\link_registry.py`
- `EntityLink` — `src\memory\orchestrator\link_registry.py`
- `RelatedEntity` — `src\memory\orchestrator\link_registry.py`
- `LinkRegistry` — `src\memory\orchestrator\link_registry.py`
- `ContentType` — `src\memory\orchestrator\memcube.py`
- `MemoryCube` — `src\memory\orchestrator\memcube.py`
- `AiMemorySearchAdapter` — `src\memory\orchestrator\memory_orchestrator.py`
- `VectorMemorySearchAdapter` — `src\memory\orchestrator\memory_orchestrator.py`
- `SkillLearningSearchAdapter` — `src\memory\orchestrator\memory_orchestrator.py`
- `MemoryOrchestrator` — `src\memory\orchestrator\memory_orchestrator.py`
- `RoutingDecision` — `src\memory\orchestrator\memory_router.py`
- `RoutingStats` — `src\memory\orchestrator\memory_router.py`
- `ClassificationResult` — `src\memory\orchestrator\memory_router.py`
- `ContentClassifier` — `src\memory\orchestrator\memory_router.py`
- `MemoryRouter` — `src\memory\orchestrator\memory_router.py`
- `PropagationEvent` — `src\memory\orchestrator\propagation_engine.py`
- `PropagationResult` — `src\memory\orchestrator\propagation_engine.py`
- `PropagationEngine` — `src\memory\orchestrator\propagation_engine.py`
- `MemoryType` — `src\memory\orchestrator\unified_id.py`
- `SourceServer` — `src\memory\orchestrator\unified_id.py`
- `UnifiedID` — `src\memory\orchestrator\unified_id.py`
- `IDRegistry` — `src\memory\orchestrator\unified_id.py`
- `SearchOptions` — `src\memory\orchestrator\unified_search.py`
- `LinkedEntity` — `src\memory\orchestrator\unified_search.py`
- `SearchResultItem` — `src\memory\orchestrator\unified_search.py`
- `UnifiedSearchResult` — `src\memory\orchestrator\unified_search.py`
- `BaseSearchAdapter` — `src\memory\orchestrator\unified_search.py`
- `ScoreNormalizer` — `src\memory\orchestrator\unified_search.py`
- `RRFMerger` — `src\memory\orchestrator\unified_search.py`
- `Deduplicator` — `src\memory\orchestrator\unified_search.py`
- `Reranker` — `src\memory\orchestrator\unified_search.py`
- `LinkEnricher` — `src\memory\orchestrator\unified_search.py`
- `UnifiedSearchEngine` — `src\memory\orchestrator\unified_search.py`
- `PatternType` — `src\memory\vector_memory\models.py`
- `ConfidenceLevel` — `src\memory\vector_memory\models.py`
- `EvidenceSource` — `src\memory\vector_memory\models.py`
- `LearnedPattern` — `src\memory\vector_memory\models.py`
- `PatternSearchResult` — `src\memory\vector_memory\models.py`
- `LearningStats` — `src\memory\vector_memory\models.py`
- `WikiDecayService` — `src\memory\librarian\wiki_decay.py`
- `WikiPromoter` — `src\memory\librarian\wiki_promoter.py`
- `CacheEntry` — `src\memory\infrastructure\cache.py`
- `LRUCache` — `src\memory\infrastructure\cache.py`
- `CircuitState` — `src\memory\infrastructure\circuit_breaker.py`
- `CircuitStats` — `src\memory\infrastructure\circuit_breaker.py`
- `CircuitBreaker` — `src\memory\infrastructure\circuit_breaker.py`
- `CircuitBreakerRegistry` — `src\memory\infrastructure\circuit_breaker.py`
- `ConflictStrategy` — `src\memory\infrastructure\conflict_resolver.py`
- `ConflictRecord` — `src\memory\infrastructure\conflict_resolver.py`
- `ConflictResult` — `src\memory\infrastructure\conflict_resolver.py`
- `ConflictResolver` — `src\memory\infrastructure\conflict_resolver.py`
- `Event` — `src\memory\infrastructure\event_bus.py`
- `Subscription` — `src\memory\infrastructure\event_bus.py`
- `EventBusStats` — `src\memory\infrastructure\event_bus.py`
- `EventBus` — `src\memory\infrastructure\event_bus.py`
- `EventStore` — `src\memory\infrastructure\event_store.py`
- `MetricsCollector` — `src\memory\infrastructure\metrics.py`
- `MetricsTimer` — `src\memory\infrastructure\metrics.py`
- `ManagedSubscription` — `src\memory\infrastructure\subscription_manager.py`
- `SubscriptionManager` — `src\memory\infrastructure\subscription_manager.py`

### Search Strategies (14)

- `adaptive` — `src\pdf_framework\search\strategies\adaptive.py`
- `auto_merge` — `src\pdf_framework\search\strategies\auto_merge.py`
- `b_m25` — `src\pdf_framework\search\strategies\bm25_search.py`
- `graph` — `src\pdf_framework\search\strategies\graph_search.py`
- `graph_r_a_g_auto` — `src\pdf_framework\search\strategies\graphrag_auto.py`
- `graph_r_a_g_global` — `src\pdf_framework\search\strategies\graphrag_global.py`
- `light_r_a_g` — `src\pdf_framework\search\strategies\graphrag_light.py`
- `graph_r_a_g_local` — `src\pdf_framework\search\strategies\graphrag_local.py`
- `hybrid` — `src\pdf_framework\search\strategies\hybrid_search.py`
- `m_m_r` — `src\pdf_framework\search\strategies\mmr_search.py`
- `r_a_p_t_o_r` — `src\pdf_framework\search\strategies\raptor_search.py`
- `vector` — `src\pdf_framework\search\strategies\vector_search.py`
- `visual` — `src\pdf_framework\search\strategies\visual.py`
- `web` — `src\pdf_framework\search\strategies\web_search.py`

### wiki_component (5)

- `WikiExporter` — `src\pdf_framework\indexing\wiki_exporter.py`
- `ForwardSyncService` — `src\pdf_framework\indexing\wiki_exporter.py`
- `IncrementalWikiSync` — `src\pdf_framework\indexing\wiki_exporter.py`
- `ReverseSyncService` — `src\pdf_framework\indexing\wiki_exporter.py`
- `WikiSearchIndexer` — `src\pdf_framework\indexing\wiki_exporter.py`
