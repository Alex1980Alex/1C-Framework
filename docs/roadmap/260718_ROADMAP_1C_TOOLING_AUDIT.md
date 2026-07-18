# 260718 — Аудит 1С-инструментария: ошибки, слабые места, GitHub-кандидаты, карта улучшений

> Мандат пользователя (2026-07-18): проанализировать ВСЕ инструменты, работающие над задачами 1С;
> найти ошибки и слабые стороны; проанализировать GitHub на инструменты, улучшающие качество
> решения 1С-задач; сформировать роадмап фиксов + внедрения.
> Данные: live tool-health (`data/reports/tools/_latest.json`, окно 14д), probe (12/12 up),
> финальный вердикт ADR-035 toolgate (331 1С-задача), память (MEMORY.md болячки), сканы
> `ecosystem_scan --days 1095` → кеш [`1c-tooling-github-2026`](../../.claude/skills/architecture-research/cache/1c-tooling-github-2026.md).
> План прошёл адверсариальное ревью полноты (claude-cli-sonnet через llm_complete — целевой цикл
> делегирования): 5 пропусков приняты и вписаны (валидационный контур, fail-open, outcome-метрика,
> бюджет вызовов, ретирмент дублей).

## §1 Инвентаризация: кто работает над 1С-задачами

### MCP-серверы (16)

| Сервер | Роль | Live-статус (14д) |
|---|---|---|
| `edt-mcp` (70 tools) | метаданные/BSL/деплой/формы/тесты через 1C:EDT | 28 вызовов, err 0%, **retry 29%** ⚠, 2 degraded по latency |
| `1c-mcp-crud` (+5 инстансов: mfm/svetly/erp/trade/bat33566) | данные/метаданные/execute_code/query живых ИБ | 49 вызовов, err 0%, retry 0% ✅ |
| `codepilot1c` (100+ tools) | EDT-workspace, мутации форм (.mxlx), DCS, YAxUnit, отладка | мало вызовов, часть unused |
| `1c-debug` / `1c-debug-hmr` (47 tools) | live RDBG-отладка (BP/stack/variables/evaluate/logpoint) | **0 вызовов в окне** (unused) ⚠ |
| `bsl-semantic-search` | bsl_search/hybrid/similar/impact/call_graph по 37k чанков | горячие тулы healthy |
| `bsl-code-search` | символы/callers по SQLite call_graph (33k символов) | healthy |
| `bsl-platform-context` | API платформы 8.3.27 (поиск по свойствам/методам) | healthy |
| `bsl-debugger` | статический bsl_analyze + debug-обвязка | редко используется |
| `mcp-onec-test-runner` | YAxUnit прогоны → JUnit | работает; ⚠ дефолт `ONEC_TEST_CONN` битый (память) |
| `auto-documenter` | autoreview/autotestplan/доки по BSL | редко используется |

### CLI / скрипты

`tools/vanessa/run-bdd.ps1` (VA BDD, resume+`.run-state.json`) · Sonar-контур (`run-sonar-analysis.ps1`, `sonar_rescan_verify.py`, `sonar_issues_pull.py`, changed-lines гейт) · `scripts/onec_search.py` (RU-поиск Infostart+web) · `scripts/its_fetch.py` (ИТС deep-fetch) · `scripts/eval_1c_detector.py`/SetFit-гейт · `bsl_lint --format` (селективный формат) · reindex-конвейер (`reindex_bsl_qwen3.py`).

### Хуки/гейты 1С-пайплайна (enforcement-слой — тоже «инструмент»)

`onec-task-input` (классификатор/маршрутизация) · `pipeline-gate` (G4 дизайн-approve) · `pipeline-1c-advance` (авто-этапы) · `onec-task-completion-stop` (единый gate: recall/capture/research/sonar + advisory T1/T2) · `code-skill-enforcer` (скиллы) · `bsl-tool-router`.

## §1.5 Карта по ЛОГИКЕ ИСПОЛЬЗОВАНИЯ (v2): этап пайплайна → все инструменты → слабость

> 1С-задачу обслуживает ВЕСЬ стек, не только «1С»-именованное: built-in Write/Edit/Bash (2123 вызова/14д),
> память, внешний анализ, LLM-делегирование, субагенты, git-контур, tool-obs. Матрица — по сквозной карте
> [гл. 43.5](../framework%20documentation/4_МЫШЛЕНИЕ/4.4_ПАЙПЛАЙН_1С/43.5_СКВОЗНАЯ_КАРТА.md) + live-данные.
> Черновик матрицы сгенерирован claude-cli-sonnet (llm_complete, целевой цикл), ревью+правки — оркестратор.

| Этап | Инструменты (факт) | Слабость (live-цифра) | Направление улучшения |
|---|---|---|---|
| §0 Вход/маршрутизация | regex+SetFit детектор (F1 0.97), `onec-task-input` advisory | детектор здоров; advisory by design (решение за пользователем — НЕ слабость) | — (мониторить FP через eval-харнесс) |
| §1 Планирование | 1c-mcp-crud (метаданные), edt-mcp (код), bsl-semantic-search, pdf-vector-graph RAG | edt-mcp retry **29%**, `search_in_code` p95 **12с**; эталон-поиск presence **0.6%** | T-P3 (edt-операционка) + Этап-В2 (adoption эталонов) |
| §2 Дизайн | + bsl-platform-context, **Runtime Trace 2.5** (1c-debug-hmr), гейт G4 | **W12**: Trace default-ON (ADR-050), а 1c-debug **0 вызовов/14д** — либо тихий SKIP всегда, либо задачи шли мимо analyze | Этап-В0: аудит SKIP-фиксаций Trace в ANALYSIS-REPORT'ах окна |
| §3 Кодирование | edt-mcp write+`get_project_errors`, execute_*, bsl_lint, Live BP-verify 5.x, **Write/Edit built-in** | Write err **+9%** к baseline; impact-чек presence **1.8%**; Sonar method-level дыра (W5) | T-P1 (BSL LSP до Sonar) + T-P0 (impact hard) + T-P4 |
| §4 Тестирование | VA BDD `run-bdd.ps1`, YAxUnit `mcp-onec-test-runner` | битый дефолт `ONEC_TEST_CONN` (W6); LLM-тестоген ниша на GitHub пуста (скан) | T-P5.1; методика VA остаётся своей |
| §5 Память | `unified_search` (recall) / `capture_pattern` / surfacing memory-first-hook | **W11**: memory-orchestrator **10 вызовов/14д** (+vector-memory 1) — recall-петля тонкая при hard-гейте; capture здоров (skill-learning 58) | Этап-В0: почему recall редок (гейт удовлетворяется 1 вызовом? surfacing замещает?) |
| §5 Внешний анализ | `onec_search`/`ecosystem_scan`/`its_fetch`/WebSearch | canonical-gap RU-терминов (W8) | RU-синонимы в скан + onec_search как парный источник |
| §5 Скиллы | `code-skill-enforcer`, skill-router | здоров (acceptance PASS 9/9); presence скиллов не мерился per-1С-задача | Этап-В4: skill-presence в toolgate-валидатор |
| §5 LLM-делегирование | `llm_complete` (sonnet-first) + `z-ai-write-guard` | было: гард мёртв (one-shot флаг), обрывы 50% — **починено 2026-07-18** (окно свежести+таймаут) | наблюдать 14д: delegation-rate на 1С-задачах |
| §5 Субагенты | Agent (code-verify ревьюер, implementer) | **W10**: Agent err **18%** (22 вызова) — провалы делегирования субагентам | Этап-В0: разбор непарных Agent-Pre (таймауты? промпт-класс?) |
| §6 Завершение | Stop-гейты `pipeline-protocol` + `onec-completion` (+sonar) | **W9**: gate-decisions **1329 allow / 0 deny за 14д** — гейты не кусаются ИЛИ deny-путь не логируется (блоки в сессиях живьём были!) | Этап-В0: аудит deny-логирования в `gate_policy.log_decision` |

## §2 Найденные ошибки и слабые стороны

### W1 🔴 ГЛАВНАЯ: high-leverage инструменты качества НЕ ИСПОЛЬЗУЮТСЯ

Финальный замер ADR-035 (окно 06-22→07-06, **331 1С-задача / 330 с правками**):

| Практика | Presence | Что теряем |
|---|---|---|
| `bsl_impact_analysis` перед правкой экспортного метода | **6/331 (1.8%)** | регрессии «кто сломается» ловятся тестами/юзером, а не до правки |
| live BP-trace (`1c-debug-hmr`) на runtime-логике | **21/331 (6.3%)** | анализ по статике вместо реальных данных (мандат ADR-050 живёт только в Фазе 2.5) |
| `bsl_search`/`similar` эталонов на планировании | **2/331 (0.6%)** | код пишется без сверки с 37k-чанковой базой эталонов |

Инструменты работают (probe 12/12 up) — **слабое место не в тулах, а в применении**. Advisory-строки в чеклисте не двигают поведение (вердикт keep-advisory формально верен, но фиксирует именно провал adoption).

### W2 🟠 edt-mcp — операционные болячки (retry-hotspot 29%)

- **step-efficiency 29%** (было 40% — топ по фреймворку): повторные идентичные вызовы = трение;
- degraded: `search_in_code` p95 **12с** (baseline 1.8с), `get_project_errors` p95 1084мс (2.7× baseline);
- болячки из памяти [exp]: **stale snapshot** (внешние правки файлов EDT не видит без resync), **не компилит .mxlx** (внешние правки макетов не подхватываются), form bounds только при `nativeFormLayoutRender=false`, rename/delete = 60с-таймаут но async-завершение (нужен trigger→poll), rename РС → `bmGetFqn`.

### W3 🟠 Отладка (1c-debug/hmr) — мощная, но простаивает

47 инструментов (W4′: function-BP/hypothesis/autotrace/root_cause; C1 set_variable), JOB-рецепты — а в окне 14д **0 вызовов** (даже ping). Причины [exp]: трение точек входа (halt-окно 1-2с, строки живой конфы ≠ repo-src, alias-валидация silent), запуск требует подготовки (warm rphosts). Прямое следствие — W1-строка BP-trace 6.3%.

### W4 🟡 1c-mcp-crud — здоров, но с известными ловушками

err 0% сейчас; ловушки задокументированы, но не автоматизированы [exp]: login-domain `-32000` (нужен `@sodru.com`), «Метод не обнаружен» = нет `Экспорт` (не устаревший деплой), `ВнешниеОбработки.Создать` из HTTP-сервиса = 500 (защита от опасных действий), инстансы-дубли тулов раздувают каталог (6×19 tools).

### W5 🟡 Sonar-контур — зрелый, но с дырой method-level

changed-lines гейт **пропускает method-level правила** (CognitiveComplexity якорится на заголовок метода — если правка не тронула строку заголовка, замечание невидимо гейту; проверка `--show-file` вручную) [exp]; кириллический component-API (обход есть); mono↔split дуализм (split включён локально).

### W6 🟡 Тестовый контур

YAxUnit: runner-конфиг ловушки (v0.5.1 Spring app.*, headless тонкий клиент БЕЗ /TESTMANAGER, безопасный режим ВЫКЛ) [exp]; `mcp-onec-test-runner` дефолт `ONEC_TEST_CONN` указывает на недоступный `KOMPUTER` → локальный override обязателен. VA BDD — стабилен (chain+resume).

### W7 🟢 Наблюдаемость 1С-контура — частичная

per-call лог (второй источник истины при падении stdio) есть у 1c-mcp-crud/memory-серверов, **нет у edt-mcp и codepilot1c** (самых тяжёлых); advisory-event контур пишется, но LOOPS/advisory-строки не конвертируются в действие (см. W1).

### W8 🟢 Поисковый ресёрч-контур

`ecosystem_scan` canonical-gap: RU-доменные термины (vanessa/yaxunit/oscript) в EN-источниках пусты даже за 3 года — канон добирается вручную/onec_search [live, этот аудит].

### W9 🔴 Наблюдательная слепота гейтов (v2)

`data/gate-decisions.jsonl` за 14д: **1329 allow / 0 deny** у обоих главных Stop-гейтов — при том, что блоки в сессиях происходят живьём (наблюдались сегодня). Либо deny-ветка не доходит до `log_decision` (блок уходит exit-2/JSON-путём раньше записи), либо гейты фактически никогда не срабатывают на 1С-задачах. В обоих случаях **метрика «сколько ловят гейты» слепа** — нельзя оценивать эффективность enforcement-слоя.

### W10 🟠 Субагентное делегирование (v2)

`Agent` err **18%** (22 вызова, по unpaired-Pre) — почти каждый пятый запуск субагента (code-verify ревьюер, implementer) обрывается без результата. Для пайплайна это скрытые повторы этапа верификации.

### W11 🟡 Recall-петля памяти тонкая (v2)

`memory-orchestrator` **10 вызовов/14д** (+ vector-memory 1) при hard-требовании recall на каждой 1С-задаче: петля удовлетворяется минимальным одиночным вызовом, глубина recall не растёт. Capture при этом здоров (skill-learning 58). Гипотезы: surfacing (`memory-first-hook`) фактически замещает явный recall; или recall делается «для галочки гейта».

### W12 🟡 Runtime Trace default-ON не виден в данных (v2)

ADR-050 сделал Фазу 2.5 (live BP-trace) default-ON для задач с исполняемым кодом, но 1c-debug/hmr — **0 вызовов за 14д**. Либо все задачи окна легитимно фиксировали SKIP (нет кода/env down), либо мандат тихо не исполняется. Требуется аудит SKIP-фиксаций в ANALYSIS-REPORT'ах окна.

## §3 GitHub-кандидаты (сканы 2026-07-18, кеш `1c-tooling-github-2026`)

| Кандидат | Что даёт | Вердикт |
|---|---|---|
| **1c-syntax/claude-code-bsl-lsp** | BSL Language Server LSP **прямо в Claude Code** (diagnostics/hover для .bsl/.os без EDT-раундтрипа) | **ADOPT (T-P1)** — мгновенный lint при правке снижает зависимость от edt-mcp validate-цикла (W2) и ловит ошибки до Sonar |
| **Desko77/1c-formsserver** | 18 MCP-тулов управляемых форм: generation/validation/**conversion между 3 форматами** (logform/Managed/EDT) | **EVAL (T-P2)** — наша боль: мутации форм только через codepilot1c, EDT-MCP не умеет, .mxlx не компилится (W2) |
| **skiddgoddamn/1c-mcp** | приём «**test-post в откатываемой транзакции**» для диагноза ошибок проведения | **ADOPT-ПРИЁМ (T-P2)** — портировать идею в наш `execute_code`-шаблон Этапа 5.x (live-проверка проведения без порчи данных, усиливает ADR-050) |
| **feenlace/mcp-1c** (eng=163) | компактный MCP 1С (1 бинарь, 10 tools, «точный BSL по конфигурации») | **EVAL-LOW** — функционально дубль 1c-mcp-crud; сравнить точность/простоту на 1 ИБ, при паритете skip |
| **Jimmo910/edt-sonarq-plugin** | Sonar-issues внутри EDT (serverless через BSL LS) | **SKIP** — наш Sonar-контур в пайплайне полнее (changed-lines гейт); нота для ручной работы в EDT |
| infaton/MCP35, onec-odata-mcp, RCS-kz | ERP digital twins / OData-мост / платный SaaS | **SKIP** — ERP-специфика/дубль/платный |
| Канон: bsl-language-server, sonar-bsl-plugin-community, vanessa, yaxunit | ядро экосистемы | уже в проде (LS — косвенно через Sonar; прямое подключение = ADOPT выше) |

### §3.5 Категории сквозных систем (v2): GitHub-покрытие через кеши

Ресёрч по НЕ-1С-именованным участникам пайплайна опирается на существующие research-кеши
(Фаза 0 architecture-research; свежие сканы дали бы дубли):

| Категория (система §5) | Кеш (факты уже собраны) | Вывод для роадмапа |
|---|---|---|
| Память агента | `ai-agent-memory-systems-2026`, `agent-memory-ingestion-consolidation-2026` | архитектура наша зрелая (§26-§27); улучшение W11 — поведенческое, не инструментальное |
| Ревью/верификация | `agentic-quality-gate-workflow-templates-2026`, `universal-code-verification` | паттерны quality-gate внедрены (ADR-034); W10 — надёжность запуска субагентов, не методика |
| Оркестрация | `pattern-pipeline-orchestration-2026`, `orchestration-best-practices` | ADR-034 R1-R8 карта уже есть |
| Поиск/ретрив | `1c-search-relevance-stack-2026`, `embedding-backend-mcp-tei-vs-ollama` | стек Qwen3+hybrid production (гл. 31) |
| Observability | `tool-call-observability-effectiveness-2026`, `langfuse-llm-observability-2026` | тяжёлый путь внедрён сегодня (OTel→Langfuse) |
| LLM-тестогенерация (этап 4) | скан 2026-07-18: ниша пуста (единственный хит testforge — ADO-специфика, нерелевантен) | VA BDD-методика остаётся своей; внешнего ADOPT нет |

## §4 Дорожная карта

### T-P0 — Переворот использования (W1: инструменты есть — заставить работать) *~1 сессия*

1. **T-P0.1** Hard-промоут T1 для узких, безошибочно детектируемых условий (ADR-035 Фаза 2, «не авто-флип»):
   `bsl_impact_analysis` — **hard** ТОЛЬКО при правке существующего экспортного метода (детект по diff: `Экспорт`-сигнатура в изменённых строках, `pipeline_1c_bridge`-классификация); BP-trace — **hard** только для T3-задач с меткой «не учтено/не работает» (runtime-загадка). Остальное — advisory.
2. **T-P0.2** *(ревью-№3)* **Fail-open политика hard-гейтов**: инструмент недоступен (probe down / RDBG не поднят / индекс пуст) → гейт деградирует в advisory с фиксацией `skipped:<reason>` в отчёте — anti-deadlock паттерн ADR-037/ADR-050 (SKIP по фиксации, не блок).
3. **T-P0.3** *(ревью-№2)* **Бюджет вызовов**: hard-условия узкие по конструкции (экспортный diff / T3-метка), + кап 1 обязательный вызов/инструмент/задача; латентность BP-trace амортизируется warm rphosts. Замер длительности задач до/после — в валидаторе.
4. **T-P0.4** Методики: в `analyze-1c-task-v2` Фаза 2 — обязательный `bsl_search` эталона (≥1 запрос, вывод в ANALYSIS-REPORT §«Эталоны»); в `implement-1c-task` Этап 3 — impact-чек перед правкой экспортного.
5. **T-P0.5** *(ревью-№1)* **Валидационный контур**: расширить `onec_toolgate_validation` — окно 14д ПОСЛЕ промоута, presence на ПРИМЕНИМЫХ задачах (знаменатель = задачи, где условие сработало, не все 331 — убирает survivorship-caveat), false-block-rate (гейт сработал там, где инструмент был не нужен) + SessionStart-баннер прогресса. Решение «оставить hard» — по вердикту валидатора, реверс = снять условие.
6. **T-P0.6** *(ревью-№4)* **Outcome-метрика, не только presence**: считать по задачам с impact-чеком vs без — Sonar-дельту и число возвратов задачи (re-open/повторные правки того же метода в 7д, по git-логу конфигураций). Цель — увидеть эффект, а не активность.

### T-P1 — BSL LSP в Claude Code (ADOPT claude-code-bsl-lsp) *~0.5-1 сессия*

1. Установить plugin (lazy-профиль, НЕ в тяжёлый .mcp.json), связать с существующим `bsl-language-server` конфигом Sonar-совместимых диагностик.
2. Приёмка: правка `.bsl` в Claude Code → диагностики в ходе (до Sonar-скана); замер — падение Sonar-дельты BLOCKER/CRITICAL на задачу.
3. Гигиена: НЕ дублировать `bsl_lint --format` (формат остаётся селективным, [[feedback-bsl-batch-edit-format-hook]]).

### T-P2 — Формы + test-post приём *~1 сессия*

1. **EVAL 1c-formsserver**: поднять на 1 тестовой ИБ, прогнать conversion logform↔EDT на реальной форме из задач; если стабилен — ADR + включение в lazy-mcp (закрывает W2-.mxlx боль).
2. **Порт приёма test-post**: шаблон `execute_code` «провести в транзакции → собрать ошибки → откатить» в `implement-1c-task` Этап 5.x (усиление ADR-050 live-данных без порчи ИБ).

### T-P3 — edt-mcp операционка (W2) *~0.5 сессии*

1. Retry-29%: разбор top-повторов из лога (`args_hash`-кластеры) → починить корневые причины (вероятно stale-snapshot → перед батч-правками обязательный `resync_to_disk`; правило в edt-mcp skill).
2. `search_in_code` p95 12с → правило в скилле: поиск по коду = `bsl_search`/`bsl-code-search` (индексы), edt-search только для точечного refactor-контекста.
3. Per-call лог edt-mcp + codepilot1c (`mcp_call_log` wrap, helper готов — N-P2.2 очередь).

### T-P4 — Sonar method-level мостик (W5) *~0.5 сессии*

В `sonar_rescan_verify --show-file` добавить авто-режим: для изменённых файлов вытянуть method-level issues (CognitiveComplexity и т.п.), чьи методы ПЕРЕСЕКАЮТСЯ с changed-lines (по границам процедур из AST `bsl-code-search`), и показывать их advisory-блоком (не гейтить легаси — CaYC-инвариант цел).

### T-P5 — Гигиена + ретирмент *(фон)*

1. Битый дефолт `ONEC_TEST_CONN` → валидный локальный; canonical-gap ecosystem_scan — нота в кеше.
2. *(ревью-№5)* **Ретирмент/деэскалация дублей**: unused-инстансы 1c-mcp-crud (6×19 тулов раздувают каталог) → lazy-mcp кандидаты; `bsl-debugger` vs `1c-debug-hmr` — оставить один канонический debug-путь (второй в lazy); feenlace/mcp-1c EVAL-LOW закрыть вердиктом skip/adopt (не держать вечный eval).

**Порядок:** T-P0 (главный рычаг) → T-P1 → T-P3 → T-P2 → T-P4 → T-P5. Все внедрения — через лестницу advisory→замер→hard (ADR-035-паттерн), реверсивно; hard-гейты всегда с fail-open фиксацией.

## §4.5 Методика улучшения + этапы внедрения (v2)

> Единая программа: T-P* (что делать) разложены во **временнЫе этапы В0-В5** (когда и в каком порядке),
> каждый этап заканчивается **замером** — внедрение без подтверждённого эффекта не переходит дальше
> (лестница advisory→замер→hard, ADR-035; все шаги реверсивны).

### Методика (5 правил внедрения любого улучшения)

1. **Сначала диагноз по live-данным, не по ощущению** — каждое улучшение привязано к W-номеру с цифрой.
2. **Advisory → замер → hard**: ничего не становится обязательным без окна валидации на applicable-знаменателе + outcome-метрики (presence ≠ эффект).
3. **Fail-open с фиксацией**: недоступность инструмента деградирует гейт в advisory со `skipped:<reason>`, не в блок (анти-deadlock ADR-037/050).
4. **Один владелец политики**: детект/гейт/замер живут в одном модуле (`pipeline_1c_bridge`/`gate_policy`), потребители импортируют — без дрейфа копий (урок G-1).
5. **Реверс задокументирован до включения** (env-флаг/снятие условия), внедрение = отдельный коммит.

### Этапы внедрения

| Этап | Содержание | Выход/замер |
|---|---|---|
| **В0 · Диагностика слепых зон** *(первый — дёшево, разблокирует остальное)* | W9 аудит deny-логирования `gate_policy.log_decision` (почему 0 deny при живых блоках); W12 аудит SKIP-фиксаций Runtime Trace в ANALYSIS-REPORT'ах окна; W10 разбор 22 Agent-вызовов (кластеры unpaired-Pre); W11 трасса recall (surfacing vs явный вызов) | отчёт-страница в этом роадмапе §18; исправление логирования deny если подтвердится |
| **В1 · Quick wins** | T-P5.1 битый `ONEC_TEST_CONN`; T-P3.2 правило «поиск по коду = индексы, не edt-search»; T-P3.3 per-call лог edt-mcp/codepilot1c; RU-синонимы в ecosystem_scan (W8) | конфиг+скилл-правки; edt search p95 в отчёте ↓ |
| **В2 · Переворот использования (T-P0)** | hard-промоут impact (экспортный diff) + BP-trace (T3-runtime) c fail-open; методики: обязательный эталон-поиск в analyze Ф2, impact-чек в implement Э3; валидатор applicable-знаменателя + outcome-метрика | окно 14д: presence ≥50% applicable, false-block ≈0, outcome не хуже |
| **В3 · Новые инструменты (T-P1/T-P2)** | ADOPT `claude-code-bsl-lsp` (диагностика при правке); EVAL `1c-formsserver` на тестовой ИБ; порт приёма test-post-в-транзакции в implement Э5.x | живой пример пойманной LSP-ошибки до Sonar; вердикт EVAL (adopt/skip) |
| **В4 · Контроль эффекта** | повторный toolgate-замер; Sonar-дельта/возвраты задач с impact vs без (T-P0.6); skill-presence per-1С-задача; T-P4 method-level мостик | сравнительный отчёт «до/после» в §18 |
| **В5 · Ретирмент (T-P5.2)** | unused-инстансы crud → lazy-mcp; один канонический debug-путь; закрыть feenlace-EVAL вердиктом | каталог тулов ↓ без потери презенса |

Ритм: В0+В1 — одна сессия; В2 — сессия + 14д окно; В3 — 1-2 сессии параллельно окну В2; В4 — по закрытию окна; В5 — фон.

## §5 Acceptance

1. Presence промоутнутых практик ≥50% на **применимых** задачах (валидатор T-P0.5, знаменатель applicable) + false-block-rate ≈0.
2. Outcome-сигнал (T-P0.6): Sonar-дельта/возвраты у задач с impact-чеком не хуже, чем без (ожидаемо лучше).
3. BSL-диагностика доступна в ходе правки (LSP) — живой пример пойманной до Sonar ошибки.
4. edt-mcp step-efficiency ≤15% (сейчас 29%).
5. Test-post шаблон применён минимум в 1 живой задаче проведения.
6. Method-level Sonar-замечания видимы advisory-блоком на пересечении с правкой.

## §18 Progress Log

### 2026-07-18 — v2: расширение по логике использования (мандат «не только 1С-именованное»)

- §1.5 матрица «этап §0-§6 → ВСЕ инструменты → слабость → улучшение» (сквозная карта 43.5 + live);
  черновик матрицы — claude-cli-sonnet через llm_complete (целевой цикл), ревью-правки оркестратора
  (hard-роутинг §0 отклонён — advisory by design, решение за пользователем).
- Новые слабости v2: **W9** гейт-децизионная слепота (1329 allow / 0 deny при живых блоках),
  **W10** Agent err 18% (провалы субагентов), **W11** recall-петля тонкая (10 вызовов/14д),
  **W12** Runtime Trace default-ON не виден в данных (0 вызовов 1c-debug).
- §3.5 GitHub-категории сквозных систем: покрыты существующими research-кешами (память/ревью/
  оркестрация/поиск/obs); LLM-тестоген ниша пуста (скан) — VA-методика своя.
- §4.5 методика улучшения (5 правил) + этапы внедрения **В0-В5** (диагностика слепых зон →
  quick wins → переворот использования → новые тулы → контроль эффекта → ретирмент) с замером
  на выходе каждого этапа.

### 2026-07-18 — Аудит проведён, роадмап создан (+адверсариальное ревью полноты)

- Инвентаризация: 16 MCP-серверов + CLI/скрипты + enforcement-слой (§1).
- Live-данные: rollup/verdicts/probe/toolgate-финал (331 задача) + память болячек → W1-W8 (§2).
- GitHub: 4 скана `--days 1095` → 8 находок + канон; кеш `1c-tooling-github-2026` (§3).
- Ключевой вывод: **главная слабость — не отсутствие инструментов, а их неиспользование**
  (impact 1.8% / BP-trace 6.3% / эталоны 0.6%); топ-ADOPT — claude-code-bsl-lsp.
- План прошёл ревью sonnet (llm_complete): 5 пропусков → T-P0.2/0.3/0.5/0.6 + T-P5.2
  (fail-open, бюджет, валидатор applicable-знаменателя, outcome-метрика, ретирмент).
- Реализация не начата (roadmap-only).
