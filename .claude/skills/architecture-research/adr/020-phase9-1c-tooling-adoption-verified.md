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
| **sonar-bsl-plugin** 1.16.1→1.18.1 | bundled jar | офиц. | **RESOLVED** (2026-06-15) | прежний DEFER снят: SonarQube апгрейднут `lts-community`(9.9)→`community` (CB **26.6.0.123539**, ядро ≥25.4), плагин **1.18.1** установлен (декларативный bind-mount LFS-jar), verified live (`/api/plugins/installed`=communitybsl 1.18.1, bsl + 180 правил). `config_manager.py` 1.16.1→1.18.1 |
| **mcp-bsl-lsp-bridge** | MCP (Docker/Java/8GB RAM) | Apache-2.0 | **EVAL → SKIP** (пилот 2026-06-15) | живой Docker-пилот проведён (см. «Результаты пилота» ниже): 26 LSP-инструментов, persistent warm bsl-ls, diagnostics — **полный паритет** с `bsl_lint.py`; live completion/hover/complexity подтверждены. Но весь набор **дублирует существующую триаду** (`bsl_lint.py` diagnostics + `bsl-semantic-search` call_graph/impact/rename + `edt-mcp` get_content_assist/get_symbol_info/go_to_definition против РЕАЛЬНОГО 1C:EDT). Единственное не-дублируемое — always-on per-method complexity CodeLens (маргинально). Не «заметно лучше» дописывания своего → SKIP при стоимости Docker-daemon + 911 МБ + ~2-3 ГБ RAM/проект + supply-chain |
| **claude-code-bsl-lsp** | **PLUGIN** (1c-syntax) | MIT | **SKIP** | плагин-маркетплейс ⟂ нашему решению SKIP-marketplace (ADR-012..016, hook-конфликт); ценность LSP даём своей обвязкой над bundled `bsl-language-server.jar` |
| **1c-mcp-metacode** | MCP (Neo4j) | **нет (null)** | **SKIP** | license:null = юр.блокер для публичного репо; полностью дублирует наш GraphRAG (Neo4j + Qwen3 + `bsl-semantic-search`) |
| **1c-templates-mcp** | MCP (FastAPI) | **нет (null)** | **DEFER** | ниша «curated BSL-шаблоны» не покрыта, но ценность маргинальна + license:null; при реальной потребности — своё (JSON-сниппеты + skill над `bsl_similar`) |

Атрибуция: bundled-версии — [own] (инспекция MANIFEST/jar), upstream/лицензии — [web] (`gh api`/WebFetch).

## Последствия
**Положительные:** честный verified-список вместо оптимистичного «всё High»; 2 ADOPT (Coverage41C fix, bsl-ls bump) —
framework-internal, низкий риск; drift `config_manager.py` устранён; отклонены 2 беслицензионных (юр.чистота
публичного репо) и 1 плагин (консистентность с ADR-012..016).
**Отрицательные:** оба ADOPT-исполнения упёрлись в инфра-блокеры (verified 2026-06-15): **bsl-ls 0.29 → JDK 21** (доступна только EDT JDK 17 → откат к 0.22, SKIP-bump до появления JDK 21 — не оправдан ради ~14 диагностик + 190 МБ), **Coverage41C → EDT debug-плагины** (EDT Lite без `com._1c.g5.v8.dt.debug.*` → BLOCKED до self-hosted runner + полного 1C:EDT IDE, точка интеграции Этап 6 готова). EVAL **mcp-bsl-lsp-bridge проведён** (Docker оказался доступен) → **SKIP-adoption** (дубль триады). Чистый итог Phase 9: 1 реализованный foundation (`bsl_lint.py`) + 1 fix (`config_manager.py`) + 3 обоснованных SKIP/BLOCK + 1 DEFER (1c-templates-mcp) + 1 RESOLVED (sonar-plugin 1.18.1 установлен 2026-06-15) — без внешних зависимостей в проде.

## Реализованные / отложенные действия
- [x] FIX `src/bsl/sonar/config_manager.py` placeholder `1.0.0`→`1.16.1` (drift с реальным bundled jar).
- [x] **`scripts/bsl_lint.py`** — foundation «своей bsl-ls обвязки» (см. Альтернативы): on-demand BSL-диагностики через bundled `bsl-language-server.jar` + auto-discovery Java (JAVA_HOME → 1C:EDT Axiom JDK 17 → bundled sonar JRE → PATH); режимы `--json`/`--severity`/`--fail-on-error`; verified (нашёл реальные Error-диагностики `InvalidCharacterInFile`). **Открытие при реализации:** bundled `tools/*/jre/bin/java.exe` — Git-LFS exe, в dev-чекауте НЕ выгружен; Java берётся из 1C:EDT (`C:\Program Files\1C\1CE\components\axiom-jdk-full-17.*`). **Интегрирован в `implement-1c-task` Этап 4** (v2.8) как предпочтительный BSL-статанализ (OneScript `bsl_analyze` → fallback). Следующий слой — хук (PostToolUse) / MCP поверх `bsl_lint.py`.
- [x] **`bsl_lint.py --format` (BSL-форматер, 2026-06-15)** — добавлен режим форматирования через bundled bsl-ls `--format` (CLI подтверждён `--help`; in-place в srcDir). Для одиночного файла — temp-copy → format → **write-back ТОЛЬКО при изменении И `rc==0`** (точные байты → сохраняется BOM/кодировка 1С; не перезаписывает оригинал при сбое форматера); idempotent. Wired в `implement-1c-task` Этап 4 **шаг 0** (skill v2.8.1) ПЕРЕД диагностикой + указатель из skill `bsl-development`. code-verify PASS (quality-review, субагент) + R1/R3-hardening применены; регресс [`tests/unit/test_bsl_lint_format.py`](../../../../tests/unit/test_bsl_lint_format.py) 4/4 (write-back контракт замокан, marker `unit`).
- [⛔] **bsl-ls 0.22.0→0.29.0 — БЛОКЕР: JDK 21** (попытка 2026-06-15): `bsl-language-server-0.29.0-exec.jar` (115 МБ) скачан → `UnsupportedClassVersionError` (0.29 = class 65 / JDK 21; доступна только 1C:EDT Axiom JDK **17** / class 61) → откат к 0.22 (verified — `bsl_lint.py` работает). Разблокировка: установить JDK 21 + научить `bsl_lint.py`/CI его находить. multilspy-fork оставлен на 0.22 (чтобы не сломать refactor-backend).
- [⛔] **Coverage41C — БЛОКЕР: EDT debug-плагины + test-run** (проверка 2026-06-15): JDK-OK (Coverage41C 2.7.3 = JDK 11), dbgs:1550 **live**, но classpath требует EDT debug-jar'ов `com._1c.g5.v8.dt.debug.*` (даже `--help` → `NoClassDefFoundError: …RuntimeDebugClientException`); их нет на `C:\Program Files\1C\1CE` (там EDT components/JDK; `.bat` ищет EDT через deprecated `ring edt locations list`). Разблокировка: `EDT_LOCATION`=plugins dir полного 1C:EDT IDE + live YaXUnit/VA test-run. Fix-doc + поток: `tools/coverage41c/README.md`. Точка интеграции — implement Этап 6 / `/run-1c-tests`. (9-байтовый `coverage41c.jar` — битый stub, не использовать.) **CI-проводка СДЕЛАНА 2026-06-15:** job `coverage` в [`ci-1c.yml`](../../../../.github/workflows/ci-1c.yml) переписан с битого `coverage41c.jar` на `Coverage41C-2.7.3/bin/Coverage41C.bat` + `EDT_LOCATION`/`COVERAGE_IB_ALIAS`-gate (start/stop в `try/finally`, dbgs:1550, artifact `genericCoverage.xml`); попутно исправлен дубль ключа `if:` в jobs `coverage` и `allure-report` (затирал runner-gate → job висел QUEUED). YAML-валидность + отсутствие дублей проверены. **Запуск** активируется при self-hosted runner + `gh variable set EDT_LOCATION …`; без полного EDT IDE по-прежнему не стартует (gate отрабатывает `::warning::` + skip).
- [x] **sonar-plugin 1.18.1 — RESOLVED (установлено 2026-06-15)**: прежний DEFER (нужен апгрейд сервера ≥2025.4) закрыт. `docker/docker-compose.sonarqube.yml` → образ `sonarqube:lts-community`(9.9) → `sonarqube:community` (**CB 26.6.0.123539**) + декларативный bind-mount плагина в `extensions/plugins/`. `tools/sonar-bsl-plugin.jar` (Git LFS) 1.16.1→**1.18.1**, `config_manager.py` 1.16.1→1.18.1. Verified live: `/api/system/status`=UP, `/api/plugins/installed`=communitybsl 1.18.1, язык `bsl` + 180 правил. Коммит `2bff2c988` (feat). См. [pipeline-артефакт](../../../../pipeline/install-sonarqube-cb-bsl-1181/pipeline.md) + [роадмап 260328](../../../../docs/roadmap/260328_1C_Docker_CICD_Roadmap.md).
- [x] **comol/cursor_rules_1c (BSL coding-rules, 2026-06-15)** — не инструмент, набор AI-правил кодирования 1С (license: нет/public-domain). Выжато в кеш [`1c-doc-research/cache/external-bsl-ai-coding-rules-comol.md`](../../1c-doc-research/cache/external-bsl-ai-coding-rules-comol.md) `[web]` (канонические области модулей, зарезервированные имена свойств форм, БСП-first, анти-паттерны async, ошибки metadata-XML, логирование) + указатель из skill `bsl-development`. Без новых зависимостей.
- [x] **EVAL mcp-bsl-lsp-bridge — ПРОВЕДЁН → SKIP** (живой пилот 2026-06-15; Docker 29.4.0 оказался доступен). См. «Результаты пилота EVAL» ниже. Вердикт: дублирует существующую триаду (`bsl_lint.py` + `bsl-semantic-search` + `edt-mcp`), не «заметно лучше» → SKIP-adoption по критерию ADR. Контейнер/образ/том снесены, клон `.tmp_lspbridge` удалён.

## Результаты пилота EVAL mcp-bsl-lsp-bridge (2026-06-15)

**Сборка/запуск:** `docker compose build` (multi-stage golang:1.24.2 + bundled bsl-ls `1.0.0-rc.1`) → образ `mcp-lsp-bridge-bsl:latest` **911 МБ**. Контейнер: s6-supervised persistent `lsp-session-manager` (порт 9999) + bsl-ls (java, Xmx2g) — состояние держится между `docker exec`-сессиями. ASCII-mount `C:/Temp/lsp_proj` (ro) с 4 BSL-файлами (копии `гкс_ПечатьАктВозврата_Беларусь` + `гкс_ЛабораторныйАнализЛокализация_by`). MCP — stdio через `docker exec -i … mcp-lsp-bridge`.

**Проверено вживую (JSON-RPC):**
- `tools/list` → **26 LSP-инструментов** (completion, hover, signature_help, definition, document_diagnostics, quality_diagnostics, module_health, complexity, call_graph, call_hierarchy, symbol_impact, rename, inlay_hints, code_actions, project_analysis, …).
- `lsp_status` → `ready`, indexing `complete 4/4` («Наполнение контекста завершено»), оба клиента (`bsl` / `bsl-language-server`) connected.
- `document_diagnostics` (ManagerModule.bsl) → **9 issues / 3 ERRORS** = **полный паритет** с `bsl_lint.py` (те же `InvalidCharacterInFile` строки 171-173; + MissingParameterDescription/IfElseIfEndsWithElse/SetPrivilegedMode/SemicolonPresence/Typo/MissingSpace). Оба обёртывают один bsl-ls.
- `quality_diagnostics` → категоризованный `SetPrivilegedMode [SECURITY_HOTSPOT]` (security/perf/sql срез).
- `complexity` / `module_health` → per-method cyclomatic+cognitive (5 методов, 0 над порогом) + ранжированные refactor-targets (security ×10).
- `hover` → **live вывод типа** `Тип: ТабличныйДокумент` (фича, которой нет в `bsl_lint.py`); `completion` → member-discovery после точки (работает, нужна точная позиция).

**Анализ перекрытия (почему SKIP):** каждый класс возможностей уже покрыт нашим стеком:
| Возможность bridge | Уже есть у нас |
|---|---|
| document/quality diagnostics | `bsl_lint.py` (bundled bsl-ls) + `edt-mcp get_project_errors` |
| completion / hover / definition | `edt-mcp get_content_assist` / `get_symbol_info` / `go_to_definition` (против РЕАЛЬНОГО 1C:EDT, не файл-снапшота) |
| call_graph / impact / rename / symbol | `bsl-semantic-search` (`bsl_call_graph` / `bsl_impact_analysis` / `bsl_rename_symbol` / `bsl_object_info`) |
| complexity / module_health (always-on CodeLens) | **не покрыто**, но маргинально; over-threshold уже ловят diagnostics `CyclomaticComplexity`/`CognitiveComplexity` в `bsl_lint.py`. Always-on per-method потребует bsl-ls в LSP-режиме (тяжелее CLI `--analyze`) — не оправдано |

**Стоимость отказа от adopt:** Docker-daemon always-on + образ 911 МБ + ~2-3 ГБ RAM на проект + supply-chain (сторонний Go-бинарь исполняется против наших BSL-исходников). При нулевом не-дублируемом выигрыше → не берём.

**Что инструмент сделал хорошо (на будущее):** чистая архитектура (persistent warm LS, multi-project `project_add`/`project_close`, типо-осведомлённый completion через BSL LS Type System v2). Если когда-нибудь понадобится **inline IDE-completion вне 1C:EDT** — это эталон; до тех пор `edt-mcp` его перекрывает. Закрепляет предпочтительную альтернативу: «своя тонкая обвязка над bundled bsl-ls» (`bsl_lint.py`), а не внешний Docker-MCP.

## Альтернативы
- **ADOPT всех 5** (оптимистично, как в roadmap) — отклонён верификацией (2 без лицензии, 1 плагин-конфликт, дубли GraphRAG/LSP).
- **Своя LSP-обвязка над bundled bsl-ls** вместо claude-code-bsl-lsp/lsp-bridge — предпочтительный путь к «inline BSL LSP» без внешнего плагина/Docker; кандидат на отдельную проработку (потенциальный ADR-021/Phase 0.5).

## Связанные файлы
`src/bsl/sonar/config_manager.py`, `tools/bsl-ls/bsl-language-server.jar`, `tools/coverage41c/`,
`.github/workflows/ci-1c.yml`, `docs/roadmap/260614_ROADMAP_1C_COMMANDS_4STAGE_ALIGNMENT.md`,
`.claude/skills/architecture-research/cache/1c-bsl-tooling-ecosystem-2026.md`.
