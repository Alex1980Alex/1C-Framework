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
- [x] **`scripts/bsl_lint.py`** — foundation «своей bsl-ls обвязки» (см. Альтернативы): on-demand BSL-диагностики через bundled `bsl-language-server.jar` + auto-discovery Java (JAVA_HOME → 1C:EDT Axiom JDK 17 → bundled sonar JRE → PATH); режимы `--json`/`--severity`/`--fail-on-error`; verified (нашёл реальные Error-диагностики `InvalidCharacterInFile`). **Открытие при реализации:** bundled `tools/*/jre/bin/java.exe` — Git-LFS exe, в dev-чекауте НЕ выгружен; Java берётся из 1C:EDT (`C:\Program Files\1C\1CE\components\axiom-jdk-full-17.*`). **Интегрирован в `implement-1c-task` Этап 4** (v2.8) как предпочтительный BSL-статанализ (OneScript `bsl_analyze` → fallback). Следующий слой — хук (PostToolUse) / MCP поверх `bsl_lint.py`.
- [⛔] **bsl-ls 0.22.0→0.29.0 — БЛОКЕР: JDK 21** (попытка 2026-06-15): `bsl-language-server-0.29.0-exec.jar` (115 МБ) скачан → `UnsupportedClassVersionError` (0.29 = class 65 / JDK 21; доступна только 1C:EDT Axiom JDK **17** / class 61) → откат к 0.22 (verified — `bsl_lint.py` работает). Разблокировка: установить JDK 21 + научить `bsl_lint.py`/CI его находить. multilspy-fork оставлен на 0.22 (чтобы не сломать refactor-backend).
- [⛔] **Coverage41C — БЛОКЕР: EDT debug-плагины + test-run** (проверка 2026-06-15): JDK-OK (Coverage41C 2.7.3 = JDK 11), dbgs:1550 **live**, но classpath требует EDT debug-jar'ов `com._1c.g5.v8.dt.debug.*` (даже `--help` → `NoClassDefFoundError: …RuntimeDebugClientException`); их нет на `C:\Program Files\1C\1CE` (там EDT components/JDK; `.bat` ищет EDT через deprecated `ring edt locations list`). Разблокировка: `EDT_LOCATION`=plugins dir полного 1C:EDT IDE + live YaXUnit/VA test-run. Fix-doc + поток: `tools/coverage41c/README.md`. Точка интеграции — implement Этап 6 / `/run-1c-tests`. (9-байтовый `coverage41c.jar` — битый stub, не использовать.)
- [ ] **sonar-plugin 1.18.1**: после апгрейда SonarQube ≥2025.4.
- [⛔] **EVAL mcp-bsl-lsp-bridge — БЛОКЕР: Docker** (в среде нет Docker+8GB). Критерии EVAL: контейнер на копии конфигурации → сравнить completion/hover/diagnostics-латентность и качество vs `bsl_lint.py` (наш bundled bsl-ls); ADOPT только если заметно лучше дописывания completion/hover к своей обвязке.

## Альтернативы
- **ADOPT всех 5** (оптимистично, как в roadmap) — отклонён верификацией (2 без лицензии, 1 плагин-конфликт, дубли GraphRAG/LSP).
- **Своя LSP-обвязка над bundled bsl-ls** вместо claude-code-bsl-lsp/lsp-bridge — предпочтительный путь к «inline BSL LSP» без внешнего плагина/Docker; кандидат на отдельную проработку (потенциальный ADR-021/Phase 0.5).

## Связанные файлы
`src/bsl/sonar/config_manager.py`, `tools/bsl-ls/bsl-language-server.jar`, `tools/coverage41c/`,
`.github/workflows/ci-1c.yml`, `docs/roadmap/260614_ROADMAP_1C_COMMANDS_4STAGE_ALIGNMENT.md`,
`.claude/skills/architecture-research/cache/1c-bsl-tooling-ecosystem-2026.md`.
