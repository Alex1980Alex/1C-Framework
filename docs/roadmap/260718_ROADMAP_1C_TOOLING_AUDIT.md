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

## §5 Acceptance

1. Presence промоутнутых практик ≥50% на **применимых** задачах (валидатор T-P0.5, знаменатель applicable) + false-block-rate ≈0.
2. Outcome-сигнал (T-P0.6): Sonar-дельта/возвраты у задач с impact-чеком не хуже, чем без (ожидаемо лучше).
3. BSL-диагностика доступна в ходе правки (LSP) — живой пример пойманной до Sonar ошибки.
4. edt-mcp step-efficiency ≤15% (сейчас 29%).
5. Test-post шаблон применён минимум в 1 живой задаче проведения.
6. Method-level Sonar-замечания видимы advisory-блоком на пересечении с правкой.

## §18 Progress Log

### 2026-07-18 — Аудит проведён, роадмап создан (+адверсариальное ревью полноты)

- Инвентаризация: 16 MCP-серверов + CLI/скрипты + enforcement-слой (§1).
- Live-данные: rollup/verdicts/probe/toolgate-финал (331 задача) + память болячек → W1-W8 (§2).
- GitHub: 4 скана `--days 1095` → 8 находок + канон; кеш `1c-tooling-github-2026` (§3).
- Ключевой вывод: **главная слабость — не отсутствие инструментов, а их неиспользование**
  (impact 1.8% / BP-trace 6.3% / эталоны 0.6%); топ-ADOPT — claude-code-bsl-lsp.
- План прошёл ревью sonnet (llm_complete): 5 пропусков → T-P0.2/0.3/0.5/0.6 + T-P5.2
  (fail-open, бюджет, валидатор applicable-знаменателя, outcome-метрика, ретирмент).
- Реализация не начата (roadmap-only).
