# ADR-020: Phase 9 — adoption внешних 1С-инструментов (verified)

**Дата:** 2026-06-14
**Статус:** accepted (решения приняты; часть adopt-исполнения отложена до инфры/go-ahead)
**Исследование:** ../cache/1c-bsl-tooling-ecosystem-2026.md
**Roadmap:** ../../../docs/roadmap/260614_ROADMAP_1C_COMMANDS_4STAGE_ALIGNMENT.md (Phase 9)
**Паттерн:** как ADR-012..016 (tooling-adoption: ADOPT/EVAL/DEFER/SKIP)
**Шаг SDLC:** Кодирование/Тестирование (инструменты)

## Контекст
Roadmap 260614 Phase 9 пометил 5 внешних кандидатов как «High» по web-research (агенты), с оговоркой
«сверить перед внедрением». Перед adopt/skip — **верификация** (`gh api`/WebFetch upstream + инспекция bundled-версий).
Верификация существенно скорректировала картину. Адопшн внешних MCP/плагинов = **supply-chain-решение**
(исполнение стороннего кода против наших BSL-исходников) → дефолт осторожный (EVAL/SKIP вместо слепого ADOPT),
консистентно с ADR-012..016 и решением **SKIP plugin-маркетплейс**.

## Решение (per-candidate, verified)

| Кандидат | Тип | Лицензия | Verdict | Обоснование (verified) |
|---|---|---|---|---|
| **Coverage41C** 2.7.3 | jar/CLI (1c-syntax) | офиц. | **ADOPT** (fix packaging) | покрытие BSL через dbgs:1550 (инфра уже есть, 1c-debug); аналога нет; дистрибутив `tools/coverage41c/Coverage41C-2.7.3/` присутствует — сломан только верхний 9-байтовый stub-jar. Framework-internal |
| **bsl-language-server** 0.22.0→0.29.0 | bundled jar | MIT | **ADOPT** (version bump) | отстаём 7 minor (~2.5 года), +~14 диагностик; self-contained `java -jar`, замена 2 jar + пин. Дёшево/полезно |
| **sonar-bsl-plugin** 1.16.1→1.18.1 | bundled jar | офиц. | **DEFER** | 1.18.x требует SonarQube ≥2025.4 (наш собран под 9.9) → апгрейд сервера сперва. Сопутно: **FIX** drift `config_manager.py` placeholder 1.0.0→1.16.1 (сделано) |
| **mcp-bsl-lsp-bridge** | MCP (Docker/Java/8GB RAM) | Apache-2.0 | **EVAL** | единственный архитектурно-совместимый (MCP, не плагин), свежий (v1.1.0 2026-06-12, ★56, Go+tests); но сильно дублирует `bsl-semantic-search` (call_graph/impact/rename/diagnostics). Реальный gap = live completion/hover/signature_help. EVAL: измерить, дешевле ли взять, чем дописать своё |
| **claude-code-bsl-lsp** | **PLUGIN** (1c-syntax) | MIT | **SKIP** | плагин-маркетплейс ⟂ нашему решению SKIP-marketplace (ADR-012..016, hook-конфликт); ценность LSP даём своей обвязкой над bundled `bsl-language-server.jar` |
| **1c-mcp-metacode** | MCP (Neo4j) | **нет (null)** | **SKIP** | license:null = юр.блокер для публичного репо; полностью дублирует наш GraphRAG (Neo4j + Qwen3 + `bsl-semantic-search`) |
| **1c-templates-mcp** | MCP (FastAPI) | **нет (null)** | **DEFER** | ниша «curated BSL-шаблоны» не покрыта, но ценность маргинальна + license:null; при реальной потребности — своё (JSON-сниппеты + skill над `bsl_similar`) |

Атрибуция: bundled-версии — [own] (инспекция MANIFEST/jar), upstream/лицензии — [web] (`gh api`/WebFetch).

## Последствия
**Положительные:** честный verified-список вместо оптимистичного «всё High»; 2 ADOPT (Coverage41C fix, bsl-ls bump) —
framework-internal, низкий риск; drift `config_manager.py` устранён; отклонены 2 беслицензионных (юр.чистота
публичного репо) и 1 плагин (консистентность с ADR-012..016).
**Отрицательные:** ADOPT-исполнение (Coverage41C wiring, bsl-ls 94MB bump) требует инфры (CI-runner, dbgs, network)
→ отложено до go-ahead; EVAL mcp-bsl-lsp-bridge требует Docker+8GB (пилот в изоляции).

## Реализованные / отложенные действия
- [x] FIX `src/bsl/sonar/config_manager.py` placeholder `1.0.0`→`1.16.1` (drift с реальным bundled jar).
- [ ] **Coverage41C**: переключить CI/launcher с 9-байтового `tools/coverage41c/coverage41c.jar` на `Coverage41C-2.7.3/bin/Coverage41C.bat` (полный classpath); выровнять CLI-флаги (`-u/-o/-P/-i`); проброс `genericCoverage.xml` в sonar (`-Dsonar.coverageReportPaths=`); опц. coverage-wrap в `/run-1c-tests`. Верификация — на CI-runner + dbgs:1550.
- [ ] **bsl-ls 0.22.0→0.29.0**: заменить `tools/bsl-ls/bsl-language-server.jar` + fork-static (`tools/multilspy-fork/.../0.22.0/`) + пин `runtime_dependencies.json`; ~94 МБ download → go-ahead.
- [ ] **sonar-plugin 1.18.1**: после апгрейда SonarQube ≥2025.4.
- [ ] **EVAL mcp-bsl-lsp-bridge**: пилот в изоляции; сравнить с дописыванием completion/hover к собственной bsl-ls-обвязке.

## Альтернативы
- **ADOPT всех 5** (оптимистично, как в roadmap) — отклонён верификацией (2 без лицензии, 1 плагин-конфликт, дубли GraphRAG/LSP).
- **Своя LSP-обвязка над bundled bsl-ls** вместо claude-code-bsl-lsp/lsp-bridge — предпочтительный путь к «inline BSL LSP» без внешнего плагина/Docker; кандидат на отдельную проработку (потенциальный ADR-021/Phase 0.5).

## Связанные файлы
`src/bsl/sonar/config_manager.py`, `tools/bsl-ls/bsl-language-server.jar`, `tools/coverage41c/`,
`.github/workflows/ci-1c.yml`, `docs/roadmap/260614_ROADMAP_1C_COMMANDS_4STAGE_ALIGNMENT.md`,
`.claude/skills/architecture-research/cache/1c-bsl-tooling-ecosystem-2026.md`.
