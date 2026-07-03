# 260703 — Аудит главы 43 «Пайплайн 1С» + дорожная карта исправлений и улучшений

**Дата:** 2026-07-03 · **Статус:** активный · **Владелец:** framework
**Метод:** 4 параллельных аудит-агента (27 файлов главы ↔ реальный код хуков/скиллов/команд, все находки верифицированы `file:line`, ключевые — живыми прогонами) + GitHub-исследование через `scripts/ecosystem_scan.py` (ADR-039, 7 запросов) + deep-fetch 4 свежих реализаций + 6 кеш-исследований `architecture-research/cache/`.
**Связанные документы:** [260614_ROADMAP_1C_COMMANDS_4STAGE_ALIGNMENT](260614_ROADMAP_1C_COMMANDS_4STAGE_ALIGNMENT.md) (B′-проводка, закрыт), ADR-034/035/036/037/041, [гл. 43](../framework%20documentation/43_ПАЙПЛАЙН_1С/43.1_ОБЗОР_И_ПАРАДИГМА.md), кеш [agentic-quality-gate-workflow-templates-2026](../../.claude/skills/architecture-research/cache/agentic-quality-gate-workflow-templates-2026.md).

---

## §1 Контекст и сводный вердикт

Глава 43 (27 файлов) описывает 4-этапный 1С-пайплайн: детектор/маршрутизация чат-входа →
slash-команды → хуки-гейты → справочник инструментов. Аудит показал: **ядро документации
качественное** (~95% имён инструментов/флагов/порогов сходятся с кодом; числовые трассы
маршрутизатора подтверждены живыми прогонами), но глава **систематически отстаёт от кода
на 1–2 недели** (ADR-035/036/037/041, C1–C4, changed-lines от 2026-07-03 не отражены), а
главное — аудит вскрыл **боевой runtime-инцидент вне документации**: оркестратор гейтов
включён с ~2026-06-21 с политиками, замороженными на снимке того же дня, из-за чего три
более поздних механизма enforcement'а фактически мертвы (см. G-1).

Итог по классам: **10 ошибок док≠код** (2 high) · **12 внутренних противоречий** ·
**~25 пробелов покрытия** · **8 хрупких мест архитектуры** · **1 боевой инцидент** ·
**2 живьём подтверждённых бага кода** (JIRA-regex FP, run_id-разрыв W-цикла).

---

## §2 Находки аудита

### 2.A Runtime-инциденты и баги кода (не доки!)

| ID | Находка | Доказательство | Серьёзность |
|---|---|---|---|
| **G-1** | **Оркестратор гейтов боевой, политики заморожены на 2026-06-21.** `GATE_ORCHESTRATOR_ENABLE=1` в `settings.local.json`; в [`gate-decisions.jsonl`](../../data/gate-decisions.jsonl) с 06-21 23:03 — 1008 записей с reason-строками политик, записей живого хука нет. `onec_completion_policy` в [`gate_policies.py:95-112`](../../.claude/hooks/shared/gate_policies.py) проверяет только recall/capture/research — **Sonar-hard ADR-037 (приземлён 06-23, ПОСЛЕ включения) в Stop-энфорсменте никогда не работал**; event-log ADR-035 пуст (1 синтетическая запись → окно валидации 06-22→07-06 потеряно); LOOPS.md не пишется; флаги ADR-036 мертвы. Корень: block-условия продублированы в хуке и политике **без parity-теста и контракта синхронизации**; side-effects вшиты в `main()` хука, композиция их теряет by-design. | `settings.local.json:env`, `gate_policies.py:95-112`, `onec-task-completion-stop.py:443-477`, `gate-decisions.jsonl` (1053 строки) | **CRITICAL** |
| **G-2** | Event-log [`onec-toolgate-events.jsonl`](../../.claude/cache/) мёртв — следствие G-1; измерительный контур Фазы 2 ADR-035 не собрал данных, валидатор выдаст `insufficient-data`. | `onec-task-completion-stop.py:359-391` (код есть, не достигается) | HIGH |
| **Д-1** | **JIRA-regex ловит технические акронимы → veto-иммунный ложный auto-маршрут.** `_JIRA = [A-Z]{2,}-\d+` матчит `UTF-8`, `SHA-256`, `GPT-4`, `ISO-8601` → confidence 1.0 (иммунитет к veto C4). Живой прогон: «поправь кодировку UTF-8 в отчёте» → **`flow=auto`** (рекомендация запустить `/run-1c-task` на не-1С задаче). | [`pipeline_1c_bridge.py:26`](../../.claude/hooks/shared/pipeline_1c_bridge.py) + живой прогон | HIGH |
| **К-1** | **Research-петля гейта конфликтует с энфорсером GitHub-поиска.** `_RESEARCH_TOOLS = {WebSearch, WebFetch}`, при этом `github-search-via-ecosystem-scan.py` блокирует GitHub-WebSearch в пользу Bash `ecosystem_scan.py`, а 1С-поиск канонично идёт `onec_search.py` — **оба не засчитываются** research-сигналом: следование одному энфорсеру мешает удовлетворить другой. | `onec-task-completion-stop.py:86` vs `github-search-via-ecosystem-scan.py` | HIGH |
| **К-2** | **W-цикл слеп per-run к нативным тулам.** `BaseHook.run()` логирует Read/Write/Edit/Bash без `run_id` (`correlationid = session`), поэтому `tool_usage_report.py --run-id` их не видит; 43.3 подаёт цикл W как полный per-run учёт. | [`base/protocol.py:205-213`](../../.claude/hooks/base/protocol.py), `invocation_logger.py:150`, `mcp-invocation-logger.py:131-133` | MED |
| **К-3** | **Гонка на едином указателе `pipeline/CURRENT`.** `advance_for_artifact` продвигает и релоцирует пайплайн из `resolve_current()`, проверяя лишь «какой-то 1С-пайплайн»: две параллельные задачи → запись ANALYSIS-REPORT задачи B продвигает/перетаскивает state задачи A. | `pipeline_1c_bridge.py:166-178` | MED |
| **К-4** | **G4 fail-open при неоднозначности**: `resolve_active_1c_slug` без JIRA опирается на CURRENT; чужой/пустой CURRENT → гейт молча no-op, без advisory. | `pipeline_1c_bridge.py:205-208` (`gate_1c_implement`) | MED |
| **К-5** | `advance_test_done` не срабатывает, если `.run-state.json` пишет раннер через Bash (хук слушает только Write\|Edit); ветка `MultiEdit` в хуке мертва (матчер settings.json её не покрывает). | [`pipeline-1c-advance.py:58`](../../.claude/hooks/pipeline-1c-advance.py) + settings.json | MED |
| **Д-2** | **Рассинхрон порога SetFit**: мост берёт `_SETFIT_THRESHOLD` (env, дефолт 0.5), игнорируя калиброванный порог из `meta.json` модели, который умеет читать `onec_setfit_gate.threshold()`. Калибровка обучения до route не доезжает. | `pipeline_1c_bridge.py:723` vs [`onec_setfit_gate.py:56-69`](../../.claude/hooks/shared/onec_setfit_gate.py) | MED |
| **G-3** | Реликты бага относительного пути лога: `docs/framework documentation/47_SCENE_DETECT_MCP/data/gate-decisions.jsonl` и `.claude/skills/architecture-research/cache/data/gate-decisions.jsonl` не убраны после фикса якоря 2026-07-03. | mtime 06-28/06-29 | LOW |

### 2.B Ошибки док ≠ код (топ; полные списки — в отчётах аудита)

| ID | Файл дока | Суть | Код-факт | Sev |
|---|---|---|---|---|
| К-6 | 43.3, 43.6 | Чеклист единого гейта описан как «recall ∧ capture ∧ research; skill — info» — **hard-петля SONAR (ADR-037) не упомянута вовсе**; читатель не узнает, что правка `.bsl` без Sonar-verify блокирует завершение и как выйти | `onec-task-completion-stop.py:438-477` | HIGH |
| Д-3 | 43.5:34 | actionless → `ask_flow` (строка 46 того же файла — правильно `ask_action`; самопротиворечие) | `pipeline_1c_bridge.py:873` | MED |
| Д-4 | 43.5 §0.5, 43.3:15-22 | flow-enum из 5 значений без `ask_action` (43.6:128 уже знает 6) | `:792,:873` | MED |
| Д-5 | 43.5.4:85-100 | Оба примера-якоря семантического слоя ложны: «заблокированным ТС» ловится regex'ом (путь 4) без семантики; veto+CamelCase-пример без глагола вообще не активирует путь 4 (живые прогоны) | словари `:421,:437` | MED |
| К-7 | 43.2:35-36 | Фантомные MCP-тулы `bsl_replace_method_body`/`bsl_safe_delete_symbol` (также в `implement-1c-task/SKILL.md:148,334`) — существует только `bsl_rename_symbol`; исполнитель ищет несуществующий tool → молчаливая деградация на Edit-fallback | `src/bsl/semantic_search/mcp.py:1051`, grep пуст | MED |
| К-8 | 43.1:36-37 | Границы этапов 1/2: «Фазы 1-2 / 3-5» ≠ скилл («Фазы 1-3 / 4-5») | `analyze-1c-task-v2/SKILL.md:15-17` | MED |
| К-9 | 43.3:48-56 | Таблица `estimate_effort` без группы `develop:+2` и весов `ttype_T1/T3:+1` → неверный расчёт баллов читателем («печатная форма» теперь medium, не auto) | `_EFFORT_CFG` `:562-575` | MED |
| К-10 | 43.3:29-65 | Детектор описан «двухуровневым»: нет `_1C_CODE` (0.9 без глагола), veto C4, семантического слоя ②; «без JIRA → ask_1c» неверно для кода с BSL-фрагментом | `:444-559,:739-817` | MED |
| К-11 | 43.3:80, 43.6:165-170 | G4 без OpenSpec-плеча (`sync_approval` проецирует approve из `.openspec.yaml`) и advisory `[LINEAGE-CHECK]` (ADR-041) | `pipeline_1c_bridge.py:221-291`, `pipeline-gate.py:51-64` | MED |
| G-4 | 43.7:121, 43.9.9 | Семантика Sonar-гейта устарела: «0 BLOCKER/CRITICAL **на затронутых файлах**» — с 2026-07-03 `mode=changed-lines` (пересечение issue-строк с diff), формулировка ложно строже | [`sonar_rescan_verify.py:334-354`](../../scripts/sonar_rescan_verify.py) | MED |
| С-1 | 43.9.3 | **serena** рекомендован в таблице выбора — не подключён ни в одном профиле (vendored-only, 0 упоминаний в `.mcp*`) | конфиги `.mcp/*` | MED |
| С-2 | 43.4:144-158 | «Обязательный внешний анализ» рекомендует WebSearch для GitHub/Infostart/ИТС — GitHub-WebSearch **блокируется энфорсером** ADR-039; канон (`ecosystem_scan.py`/`onec_search.py`/`its-research`) не упомянут; 43.6:94 уже правильно | `github-search-via-ecosystem-scan.py` | MED |
| Д-6 | 43.5.x, все 7 файлов | Все `#L`-якоря на `pipeline_1c_bridge.py` смещены на ~140-190 строк после ADR-041 (18+ якорей: `classify_1c_task` #L254→444, `route_1c_task` #L595→785, …) | вставка `:239-381` | MED (суммарно) |
| К-12 | 43.2:33, 43.6:102 | 4 режима Preflight вместо 5 (нет Read-only verify / Read-only research) | `implement-1c-task/SKILL.md:195-198` | LOW |
| Д-7 | 43.5:650-653 | GT «64 примера» → фактически 248; метрики baseline поданы как текущие | `data/1c-detector-ground-truth.json` | LOW |
| G-5 | 43.7:121 | «12 тестов» → 18 (`test_sonar_rescan_state.py` вырос с changed-lines) | grep `def test_` | LOW |
| С-3 | 43.9.1 | `scan_metadata_index` приписан «codepilot1c / edt» — есть только у codepilot1c | тулсеты серверов | LOW |

### 2.C Внутренние противоречия (сжато)

1. **43.7 ⊥ 43.8 при включённом оркестраторе** — 43.7 обещает Sonar-энфорсмент Stop-гейтом, 43.8 описывает оркестратор «заменяет 2 гейта», в политиках Sonar нет; конфликт не оговорён нигде (см. G-1).
2. Докстринг `gate_policies.py:7` «реплицируют ТОЧНЫЕ block-условия живых хуков» — ложь после 06-21 (Sonar, toolgate-hard, LOOPS.md, event-log).
3. 43.3 (5 flow) ⊥ 43.6 (6 flow); 43.5:34 ⊥ 43.5:46 (actionless).
4. 43.1 ⊥ скилл analyze-v2 (границы фаз 1-2/3-5 vs 1-3/4-5).
5. Датировки шапок («Состояние на 2026-06-15/16/17/21») не бампались при более поздних правках содержимого — штампы врут о свежести всех 4+ файлов.
6. Терминологическая коллизия «T2 (ADR-035)» ≠ «Тир-2 (ADR-036)» между 43.4 и 43.9 — разные множества инструментов под одной меткой.
7. 43.5 §0.3 нумерация путей (3=`_1C_CODE`) vs трассы B/C (донумерация «путь 3 = термин+глагол»).
8. 43.6 «Результат аудита: открытых 0» при живом фантоме К-7 — ровно тот класс, который чеклист 43.6 объявляет ловить.
9. Команда `analyze-1c-task.md:74-75` нумерует секции отчёта 7/8, скилл — 12/13.
10. 43.5:83-84 — обрывки ASCII-рамки посреди blockquote; 43.5.2:54 — потерян литерал `\b`.
11. Метрики детектора в 43.5 (64-GT baseline) vs 43.5.4 (230-GT) без пометки историчности.
12. Дубль `find_callers`/`bsl_call_graph` в двух рамках внутри 43.9.

### 2.D Пробелы покрытия (код есть — в главе нет; сжато)

- **ADR-037 Sonar-гейт**: отсутствует в 43.1/43.2/43.3/43.6 полностью (в 43.7/43.9.9 — устаревшая семантика).
- **ADR-041**: `use_sdd` в route, `sync_approval` (OpenSpec→G4), `check_lineage` — нет в 43.3/43.5.x/43.6.
- **ADR-035/036 контур**: advisory-детекты (7 сигналов), Тир-2, event-log, валидатор `onec_toolgate_validation.py`, SessionStart-баннер — нет в 43.3/43.6/43.7 (частично).
- **SetFit фактически ВКЛЮЧЁН** (`ONEC_SETFIT_ENABLE=1` в `settings.local.json`, live `semantic_source=setfit`) — 43.5.4 подаёт «спит по умолчанию»; env-ручки слоя ② (`ONEC_SEM_THRESHOLD`, `ONEC_SETFIT_*` ×7) не документированы.
- **YAxUnit unit-трек** (2026-06-26): `/write-1c-unit-tests`, `/run-1c-unit-tests`, skill `yaxunit-unit-testing` — нет в 43.1/43.2/43.4/43.6/43.9.8.
- **`/fix-sonar-task`** — нет в инвентаре команд 43.1/43.2/43.6.
- **`onec-state-first-guard`** (ADR-026, зарегистрирован в settings.local.json) — нет в таблицах хуков 43.3/43.6.
- **C2/C3 `resolve_active_1c_slug`** — нет в 43.5 (§0.9 знает только `derive_slug`).
- **Справочник инструментов**: codepilot1c покрыт ~6/100 тулов (qa-контур, форменный write-путь, роли, отладка, ИБ-операции); `bsl-semantic-diff` (lazy-mcp) — нигде; 1c-debug семейства exception-BP/coverage/replay; `get_template_screenshot`; cc-1c-skills `db-*`/`cfe-*`/`epf-*`; SonarQube MCP (ADR-042); skill `1c-solution-architecture` в этапах 1-2; канал доступа `ast-grep-mcp` (lazy-mcp, не в активном профиле).
- **Метрики ADR-022** в `tool_usage_report.py` (реальная латентность, `repeats`/`abandonment`) — 43.3 описывает только calls/errors/avg.
- ~110 регресс-тестов моста/гейта не упомянуты ни в одном 43.5.x.

### 2.E Хрупкие места архитектуры (за пределами доков)

1. **Дублирование block-условий хук↔политика без контракта** (корень G-1) — тесты `test_gate_policies.py` фиксируют снимок, а не паритет.
2. **Fail-closed только на уровне политик**: `build_context` при сбое сбора возвращает safe-allow дефолты (`recall/capture/research=True`) — оркестратор глохнет в allow без лога.
3. **Асимметрия decision-log**: оркестратор логирует всё, живые хуки — deny всегда/allow частично → периоды в `gate-decisions.jsonl` несравнимы.
4. **Graceful-открытость Sonar-ветки**: исключение в `_sonar_rescan_evaluate` → `sonar_ok=True` тихо; `evaluate` не читает `baseline_degenerate`.
5. **`_incomplete_onec_pipeline` без age-bound**: давно брошенный 1С-пайплайн + любая `.bsl`-правка → гейт навешивается на чужой slug (LOOPS.md/события уходят в старую задачу).
6. **Сигналы петель грубые**: research = любой WebSearch; recall = в т.ч. `list_patterns` — presence-метрики Фазы 2 завышаются by-design.
7. **Дублирование словарей/весов в прозе доков** — уже дважды разошлись (develop, `ask_action`); конфиг тюнится «без правки кода», но и без правки дока.
8. **`#L`-якоря** — третье поколение сдвига; файл-цель растёт при каждом ADR.

---

## §3 GitHub-исследование: паттерны лидеров и вывод

**Источники:** свежий скан `ecosystem_scan.py` (2026-07-03, окна 30/180/365 дн.; узкие запросы в 30-дневном окне дают 0 — фиксируем как операционный факт) + deep-fetch 4 реализаций → кеш [agentic-quality-gate-workflow-templates-2026](../../.claude/skills/architecture-research/cache/agentic-quality-gate-workflow-templates-2026.md); база — кеши [agentic-pipeline-workflow-enforcement-2026](../../.claude/skills/architecture-research/cache/agentic-pipeline-workflow-enforcement-2026.md) (spec-kit ~80k★, BMAD ~48k★, OpenSpec, Kiro, LangGraph, Burr, semantic-router, task-master), [pattern-pipeline-orchestration-2026](../../.claude/skills/architecture-research/cache/pattern-pipeline-orchestration-2026.md) (Temporal/Dagster, OPA/Rego, SARIF, Pixee/Copilot-Autofix), [intent-detection-routing-best-practices](../../.claude/skills/architecture-research/cache/intent-detection-routing-best-practices.md).

**Что делают лидеры (сводка фактов):**

| # | Паттерн | Кто | Наш статус |
|---|---|---|---|
| 1 | **Гейт = исполняемая команда с exit-code**, вывод провала автоматически скармливается fix-шагу (`{{gate_output}}`), workflow не завершается до зелёных гейтов | koto, Graybark `verify.sh`, agentico fix-verify loop | Частично: `sonar_rescan_verify.py` исполняемый, но block-сообщения Stop-гейтов — текстовые чеклисты без вывода последнего verify |
| 2 | **Bounded iteration + типизированная эскалация человеку** (`max_iterations=10`, `max_consecutive_failures=3`; метки `needs-human-p0/p1/p2`) | agentico, Graybark | Нет: AUTO-режим `/run-1c-task` имеет правило «AUTO ≠ игнор блокеров», но без числовых лимитов и меток эскалации |
| 3 | **Параллельные специализированные критики со структурированным JSON-вердиктом** (6 критиков плана; 3 рецензента кода) | agentico, Graybark | Частично: code-verify субагент есть; критиков ANALYSIS-REPORT перед авто-approve нет |
| 4 | **Policy-as-code: fail-closed + decision-log + policy-тесты в CI** | OPA/Rego/conftest | Частично: `gate_policy` слой есть, decision-log есть; **parity-тестов нет — это корень инцидента G-1** |
| 5 | **Learning-петля как штатный финальный этап** (compound learning: причина ошибки → обновление rules/skills/checks) | Graybark, agentico KB | Есть (capture-петля гейта, LOOPS.md, harvester'ы) — подтверждение курса |
| 6 | **Адаптивная глубина процесса под сложность** («only stages that add value»; профили Medium/Large/Moonshot) | AWS AI-DLC (3.3k★), agentico | Есть (simple→auto / medium→ask / complex→gated) — подтверждение курса |
| 7 | **Спецификация-артефакт до кода + HITL-гейт план→код** | spec-kit, BMAD, OpenSpec, Kiro, LangGraph interrupt | Есть (B′, G4, OpenSpec-мост ADR-041) — подтверждение курса |
| 8 | **Интент-роутинг: калиброванные пороги + abstain-маршрут; малые fine-tuned модели > LLM на узких интентах** | semantic-router, SetFit (arxiv 2410.01627) | Есть (каскад regex→TF-IDF→SetFit, `ask_1c`-abstain), но калиброванный порог модели не доезжает до route (Д-2) |
| 9 | **SARIF как обменный формат находок** | OASIS SARIF 2.1.0, Pixee, CodeQL | Есть точечно (`sonar_issues_pull.py --format sarif`, ADR-034 R4) |

**Вывод.** Архитектура главы 43 (state-first пайплайн + адаптивная маршрутизация + гейты + learning-петля) **соответствует передовому фронту** — пп. 5-7 индустрия подтверждает, догонять по форме нечего. Реальные разрывы с лидерами — **не в наборе механизмов, а в их надёжности и замкнутости петель**: (а) у лидеров условия гейтов существуют в одном месте и проверяются policy-тестами — у нас продублированы и разошлись (G-1); (б) у лидеров вывод гейта автоматически становится входом фикса — у нас блок-сообщение перечисляет петли, но не подаёт вывод verify; (в) у лидеров авто-режимы ограничены числом итераций с типизированной эскалацией — у нас AUTO полагается на дисциплину правил. Приоритет улучшений: **сначала P0-надёжность (parity, инцидент), затем замыкание петель (gate-output, bounded AUTO, критики), и только потом расширение покрытия доков** — гонка за полнотой справочника без починки G-1 бессмысленна: энфорсмент, который описывают доки, частично не работает.

---

## §4 Дорожная карта

> Нумерация: P0 — инцидент/безопасность маршрута (сейчас); P1 — код-фиксы малой стоимости;
> P2 — синхронизация документации главы; P3 — улучшения по паттернам лидеров; P4 — стратегическое.
> Каждый пункт: находки → работы → acceptance → оценка.

### Фаза P0 — инцидент и опасные FP (≈1 день)

| ID | Работы | Acceptance | Оценка |
|---|---|---|---|
| **P0.1 Ре-синхронизация оркестратора гейтов** (G-1) | 1) В `gate_policies.py` добавить: sonar-политику (вызов `_sonar_rescan_evaluate` из хука через переиспользуемый слой), toolgate-hard (ADR-036 env-флаги), side-effects (event-log ADR-035 + LOOPS.md) — вынести их из `main()` хука в `shared/`-функции, зовущиеся обоими путями; 2) **parity-тест**: один синтетический контекст → живой хук и `evaluate_gates` дают идентичное block-решение (матрица: recall/capture/research/sonar/optout ≥ 12 кейсов), в CI; 3) до готовности 1-2 — **временно снять `GATE_ORCHESTRATOR_ENABLE=1`** из `settings.local.json` (живые хуки снова полны). | parity-тест зелёный в CI; deny-запись с `sonar_rescan` появляется в `gate-decisions.jsonl` при незакрытом Sonar; LOOPS.md пишется при block | 4-6 ч |
| **P0.2 Перезапуск окна ADR-035** (G-2) | После P0.1: объявить окно валидации 06-22→07-06 потерянным (запись в ADR-035), стартовать новое 14-дневное; проверить живой записью в `onec-toolgate-events.jsonl` на первой же 1С-задаче | ≥1 не-синтетическая запись в лог; баннер валидатора показывает новое окно | 1-2 ч |
| **P0.3 JIRA-regex denylist** (Д-1) | В `_JIRA`-детект добавить denylist акронимов (`UTF|SHA|GPT|ISO|MD|AES|RSA|TLS|CRC|HTTP|JSON|XML|HTML|CSS|SQL|API|URL|UUID|CPU|GPU|RAM|IPV…`) + опциональный allowlist проектных префиксов (`GKSTCPLK` и конфигурируемо); generic-матч не из allowlist → confidence 0.7 (veto-able), не 1.0 | Регресс: «поправь кодировку UTF-8» → `none`; `GKSTCPLK-2597` → 1.0; +6 unit | 2 ч |
| **P0.4 Research-сигнал засчитывает канонические скрипты** (К-1) | В `_collect_signals` (и в политику после P0.1) добавить детект Bash-вызовов `ecosystem_scan.py`/`onec_search.py`/`its_fetch.py` как research (парсинг `tool_use` Bash по подстроке имени скрипта) | e2e: сессия только с `ecosystem_scan.py` проходит research-петлю | 1-2 ч |
| **P0.5 Убрать реликты `gate-decisions.jsonl`** (G-3) | Удалить 2 файла из чужих деревьев (47_SCENE_DETECT_MCP/data, cache/data) | git status чист от реликтов | 15 мин |

### Фаза P1 — код-фиксы малой стоимости (≈1-1.5 дня)

| ID | Работы | Acceptance | Оценка |
|---|---|---|---|
| **P1.1 SetFit-порог из `meta.json`** (Д-2) | `route_1c_task` берёт порог через `onec_setfit_gate.threshold()` (калиброванный), env `ONEC_SETFIT_THRESHOLD` — только override | unit: порог из meta.json применяется; env-override работает | 1 ч |
| **P1.2 `run_id` для нативных тулов** (К-2) | `BaseHook.run()` пробрасывает `get_run_id(session_id)` в лог (симметрично `mcp-invocation-logger`); фолбэк-семантика не меняется | `tool_usage_report.py --run-id` видит Edit/Bash; регресс-тест на envelope | 2 ч |
| **P1.3 G4 advisory при no-op** (К-4) | `gate_1c_implement`: не нашли активный 1С-slug → systemMessage «активный 1С-пайплайн не найден, гейт не применён — проверь CURRENT/JIRA» | live: implement-промпт без JIRA при чужом CURRENT даёт advisory | 1 ч |
| **P1.4 `advance_test_done` для раннера** (К-5) | Вариант A: PostToolUse-матчер `Bash` с детектом `run-bdd.ps1`→проверка mtime `.run-state.json`; Вариант B (проще): `onec-task-completion-stop`/`pipeline-1c-advance` при Stop перечитывает `.run-state.json` активного slug. Убрать мёртвую `MultiEdit`-ветку или расширить матчер | e2e: прогон run-bdd c passed-цепочкой продвигает этап 4 без ручного Write | 2-3 ч |
| **P1.5 Slug-привязка артефакта до CURRENT-fallback** (К-3) | `advance_for_artifact`: сперва извлечь JIRA/slug из пути артефакта (`configuration/<JIRA>/docs/<slug>/…`) → искать пайплайн по нему; CURRENT — только если путь не дал slug | unit: артефакт задачи B не двигает state задачи A | 2 ч |
| **P1.6 Симметрия decision-log** (2.E.3) | `onec-task-completion-stop` логирует и allow (как политики); флаг для сравнения периодов | в jsonl появляются allow-записи живого хука | 1 ч |
| **P1.7 Age-bound для `_incomplete_onec_pipeline`** (2.E.5) ⚠ live-подтверждено | Порог давности state (например, `updated_at` не старше 14 дн.) либо требование совпадения slug с сессионным сигналом. **Live-репро (pre-flight 2026-07-03):** синтетическая сессия с `config_edit` получила `task_slug` ЧУЖОЙ реальной задачи (gkstcplk-2182) — H5-fallback берёт первый попавшийся незавершённый; LOOPS.md/advisory ушли в чужую папку → приоритет ↑ | unit: брошенный месяц назад пайплайн не навешивает гейт; sig-слаг не мигрирует в чужую задачу | 1-2 ч |
| **P1.8 Лог деградаций fail-open** (2.E.2/2.E.4) | `build_context` при сбое сбора и `_sonar_rescan_evaluate` при исключении пишут warning-запись в `gate-decisions.jsonl` (`decision=allow, reason=degraded:<err>`); `evaluate` surface'ит `baseline_degenerate` в block-превью | искусственный сбой даёт `degraded`-запись | 1-2 ч |
| **P1.9 Уточнение `light`/`pos`** (Д-imp4) | Исключить `ttype`/`folder` из `pos` для light-условия (или задокументировать); цель — light-метка наблюдаема на T1-косметике | unit: «поправь опечатку в форме» (T1) получает light | 1 ч |

### Фаза P2 — синхронизация документации главы 43 (≈1.5-2 дня; после P0/P1, чтобы описывать уже исправленное)

| ID | Файлы | Содержимое правки | Оценка |
|---|---|---|---|
| **P2.1** | 43.5 | actionless→`ask_action` (строка 34), таблица §0.5 → 6 flow, нумерация путей в трассах B/C, метрики → 248-GT (baseline пометить историческим), убрать ASCII-артефакт (:83-84), `\b`-литерал, дата-штамп, добавить: C2/C3 `resolve_active_1c_slug`, ADR-041 (use_sdd/sync_approval/lineage), ссылки на ~110 тестов, ключ `confidence` в возврате classify | 2-3 ч |
| **P2.2** | 43.5.4 | Пересобрать оба примера-якоря по живым прогонам из 248-GT (подобрать реальный hard-кейс, где семантика промоутит, и veto-кейс с глаголом); отразить фактический статус SetFit=ON в этом репо + все env-ручки слоя ② (7 переменных); порог после P1.1 | 1-2 ч |
| **P2.3** | 43.3, 43.6 | flow-enum 6 значений; **секция SONAR-петли** (ADR-037, changed-lines, `sonar_rescan_verify.py`, выход из блока); G4 + OpenSpec-плечо + lineage; таблица effort += `develop`, `ttype`; детектор → фактические уровни (JIRA→definitive→code→signal+verb→semantика→veto); preflight 5 режимов; «3 hard-точки» → фактический список; ADR-035/036 контур + event-log + валидатор; `onec-state-first-guard` в таблицы хуков; честная формулировка correlationid (native=session до P1.2); имплемент-скилл мапится на этапы 3+4 | 3-4 ч |
| **P2.4** | 43.1, 43.2 | Границы фаз 1-3/4-5 (по скиллу); фантомные 3R-тулы → «через обёртки `bsl-symbol-editing` (read_method_source→write_module_source)»; YAxUnit unit-трек в этап 4; `/fix-sonar-task` в инвентарь команд; нумерация секций отчёта в команде = скиллу (12/13) | 2 ч |
| **P2.5** | 43.7, 43.8 | changed-lines семантика + `baseline_degenerate` + tz-фикс parse_dt; 18 тестов; ADR-036 механика; **секция «Оркестратор и живые хуки: контракт синхронизации»** (описание parity-теста из P0.1, судьба инцидента G-1); фикс якоря лога (абс. путь + `GATE_DECISIONS_LOG`); оговорка про safe-allow дефолты `build_context`; дата-штампы | 2-3 ч |
| **P2.6** | 43.4, 43.9.x | «Внешний анализ» → канон `ecosystem_scan.py`/`onec_search.py`/`its-research` (+ шаблон TOOL-PLAN); T2 vs Тир-2 переименовать (напр. «ADR-035-эталон» / «ADR-036-Тир-2»); serena удалить/пометить vendored-only; `ast-grep-mcp` — указать канал (lazy-mcp/профиль); ревизия codepilot1c (qa-контур → 43.9.8, форменный write-путь → 43.9.6 с оговоркой против cc-1c-skills, роли → 43.9.5 с уточнением «только файлами»); добавить `bsl-semantic-diff`, `get_template_screenshot`, 1c-debug exception-BP/coverage/replay, cc-1c-skills `db-*`/`cfe-*`, SonarQube MCP (ADR-042), skill `1c-solution-architecture` в этапы 1-2; `sonar_issues_pull.py --format sarif`; убрать дубль find_callers; фикс `scan_metadata_index` | 3-4 ч |
| **P2.7** | вся глава | **Якорная политика**: `#L`-якоря на живой код заменить на `функция @ файл` (без номера строки) ИЛИ добавить в `scripts/` регенератор якорей (grep def-строк → подстановка); зафиксировать в правилах главы | 1-2 ч |
| **P2.8** | вся глава | Процедурное правило: в чеклист «Аудит консистентности слоёв» (43.6) добавить пункты «бампни „Состояние на"» и «прогони по главе grep новых ADR» — исполнять при каждом ADR, задевающем пайплайн | 30 мин |

### Фаза P3 — улучшения по паттернам лидеров (по мере ценности; каждое — свой pipeline/ADR)

| ID | Улучшение | Обоснование [источник] | Работы | Оценка |
|---|---|---|---|---|
| **P3.1 Gate-output → fix-петля** | Паттерн №1: вывод гейта автоматически становится входом фикса [web: koto `{{gate_output}}`, Graybark verify.sh, agentico] | Block-сообщение `onec-task-completion-stop`/оркестратора при незакрытом Sonar включает хвост последнего `sonar_rescan_verify`-вывода (уже пишется в state) + точную команду перезапуска; аналогично для research/recall — конкретные команды | 2-3 ч |
| **P3.2 Bounded AUTO + эскалация** | Паттерн №2 [web: agentico max_iterations=10/failures=3; Graybark 4 итерации + needs-human-p0/p1/p2] | В `run-1c-task` SKILL + state: `max_fix_iterations` на этап 4 (default 4); превышение → STOP c типизированной меткой в state (`needs-human: p0 архитектура / p1 непонятный путь / p2 быстрый фикс`) и понятным резюме; счётчик в `.pipeline-state.json` | 3-4 ч |
| **P3.3 Критики ANALYSIS-REPORT перед авто-approve** | Паттерн №3 [web: agentico 6 параллельных критиков плана; Graybark 3 рецензента с JSON-вердиктами] | В AUTO-режиме перед авто-approve — 2-3 параллельных субагента-критика (полнота ТЗ / объекты-метаданные / риски-регрессы) со структурированным вердиктом; любой `blocker` → пауза (деградация в гейтованный поток). Расширяет существующий преflight 2.4 | 4-6 ч |
| **P3.4 Parity-harness как постоянный CI-guard** | Паттерн №4 [web: OPA policy-тесты в CI; conftest] | Развитие P0.1: генератор синтетических Stop-контекстов (матрица сигналов) + прогон обоих путей; падение паритета валит CI. Инвариант: «правишь block-условие хука → parity-тест заставит обновить политику» | 2-3 ч (поверх P0.1) |
| **P3.5 Doc-drift линтер главы 43** | Паттерн-обобщение №4/№7 + собственный опыт двух расхождений подряд [own; web: mkdocstrings code-anchored docs — кеш hierarchical-code-anchored-docs-2026] | Скрипт `scripts/lint_ch43_sync.py`: сверяет доки с кодом по 4 инвариантам (flow-enum == коду; таблица весов == `_EFFORT_CFG`; словари-«исчерпывающие» == коду; упомянутые MCP-тулы существуют в тулсетах) → CI-job advisory; расширяемый реестр инвариантов | 4-6 ч |
| **P3.6 Compound-learning усиление** | Паттерн №5 [web: Graybark docs/solutions → обновление rules/skills/checks] | При `needs-human`-эскалации (P3.2) и FAIL-итерациях: авто-заготовка `capture_pattern` с причиной провала + предложение обновить конкретный SKILL/правило (сейчас петля фиксирует успехи охотнее, чем провалы) | 2-3 ч |

### Фаза P4 — стратегическое (после P3, отдельные ADR)

- **P4.1** SARIF-агрегация BSL-линтеров: `bsl_lint.py` → SARIF-вывод, единый формат с `sonar_issues_pull.py --format sarif` (ADR-034 R4) для будущего findings-роутера [web: SARIF 2.1.0, Pixee 12+50 форматов].
- **P4.2** Оценка child-workflow оркестрации для `/fix-sonar-task` per-cluster (ADR-034 R1, Temporal-паттерн родитель→N детей) — когда объём Sonar-задач вырастет.
- **P4.3** Пере-валидация 43.5.4-примеров и порогов детектора на растущем GT (248→400) + `--cv` отчёт в CI (развитие ADR-025).

### Зависимости

```
P0.1 ─→ P0.2 ─→ (окно 14 дн.) ─→ ADR-035 Фаза 2 (решение hard-промоута)
P0.1 ─→ P3.4 (harness поверх parity-теста)
P1.1/P1.2/… ─→ P2.x (доки описывают исправленное состояние)
P3.2 ─→ P3.6 (эскалация порождает learning-вход)
```

---

## §5 Риски и границы

1. **P0.1 — самый чувствительный пункт**: правка гейтовой логики может дать ложные блоки. Митигация: pre-flight Stop-хуков синтетическим payload'ом (memory `feedback-stop-hook-preflight`), parity-тест до включения, opt-out-переменные сохраняются.
2. **P0.3 denylist** может отрезать легитимный JIRA-проект с «техническим» префиксом — allowlist проектных префиксов конфигурируемый, дефолт наполняется из `pipeline/_1c_index.json` истории.
3. **P2 — большой батч правок доков**: риск нового дрейфа при длинной раскатке. Митигация: P2 исполнять одним срезом после P0/P1; P3.5-линтер закрепляет.
4. **Оценки** — по практике roadmap'ов переоцениваются на 1.5-3× (memory `project-roadmap-audit-pattern`); суммарно P0+P1+P2 ≈ 4-6 рабочих дней с буфером.
5. Аудит покрывал главу 43 и её код-опору; смежные главы (17.x, 40.x, 45) не проверялись — переносить выводы на них нельзя.
6. **Пред-существующая тест-инфра (обнаружено при P0, НЕ регресс):** полный сбор `pytest tests/unit/` падает на семействе хук-`shared`-тестов (`test_gate_policies`/`test_gate_policy`/`test_llm_health`/`test_sonar_rescan_state` + новый `test_gate_parity`) — бареный `shared` кэшируется как `src/shared` под `--import-mode=importlib`, затеняя `.claude/hooks/shared` ([[feedback-hook-src-shared-collision]]). Воспроизведено БЕЗ моих файлов → пред-существующее (CI уже красный по этой и др. причинам с 06-28). P0-тесты верифицированы таргетными прогонами. **Кандидат-фикс (P1/P2):** conftest, эвиктящий/изолирующий `shared` для хук-тестов, ИЛИ importlib-загрузка хук-модулей по пути под уникальным именем.

## §6 Acceptance всего roadmap

- [ ] P0 полностью: parity-тест в CI зелёный; Sonar-deny виден в `gate-decisions.jsonl`; новое окно ADR-035 идёт с живыми записями; «UTF-8»-класс промптов не уходит в auto; research-петля принимает канонические скрипты.
- [ ] P1: `--run-id` видит нативные тулы; артефакты не мигрируют между задачами; `.run-state.json` от раннера продвигает этап 4.
- [ ] P2: `grep` по главе не находит `ask_flow` в actionless-контексте, «двухуровневый детектор», «0 BLOCKER/CRITICAL на затронутых файлах», WebSearch-как-канон GitHub; все дата-штампы ≥ даты последней правки файла.
- [ ] P3: как минимум P3.4 (parity-harness) и P3.5 (doc-drift линтер) в CI; решения по P3.1-P3.3/P3.6 зафиксированы (сделано или отклонено ADR'ом).

---

## §18 Progress log

| Дата | Фаза | Событие | Артефакт |
|---|---|---|---|
| 2026-07-03 | Аудит | 4-агентный аудит 27 файлов главы ↔ код (2 боевых бага подтверждены живьём: JIRA-FP, run_id-разрыв; инцидент G-1 оркестратора вскрыт по `gate-decisions.jsonl`) + GitHub-исследование (ecosystem_scan + deep-fetch agentico/AI-DLC/koto/Graybark) + этот roadmap | этот файл + кеш [agentic-quality-gate-workflow-templates-2026](../../.claude/skills/architecture-research/cache/agentic-quality-gate-workflow-templates-2026.md) |
| 2026-07-03 | **P0 runtime-verify** | **Pre-flight Stop-хуков синтетическим payload'ом (18/18 PASS):** R1 live-хук block + LOOPS.md + advisory-event + deny с `sonar_rescan` в `gate-decisions.jsonl` (acceptance P0.1 ✓); R2 оркестратор block тем же чеклистом + свои side-effects (фикс G-1 работает live); R3 взаимоисключение путей (yield, без двойной записи); R4 петли закрыты research'ем через Bash `ecosystem_scan.py` → allow (P0.4 e2e ✓); guard «advisory только наш slug». Вся синтетика вычищена из 3 логов. **Бонус:** первый прогон live-воспроизвёл 2.E.5 (H5-fallback увёл side-effects в чужую задачу gkstcplk-2182; LOOPS.md той задачи — авто-артефакт, перегенерируется) → приоритет P1.7 поднят. | `scratchpad/preflight_p0.py` (сессионный) + строка P1.7 |
| 2026-07-03 | **P0 РЕАЛИЗОВАН** | **P0.1** single-source `evaluate_completion` (sonar + LOOPS.md + advisory-event вынесены из `main()`; `build_context`/`onec_completion_policy` делегируют; оркестратор рендерит богатый reason) + parity-тест `test_gate_parity.py` (16-комбинационная матрица + инцидент-тест «Sonar теперь deny»). **P0.3** `_find_jira` denylist акронимов (UTF/SHA/GPT/…) + allowlist проектных префиксов (env `ONEC_JIRA_PREFIXES`); generic-JIRA→0.7 veto-able; живой прогон: «UTF-8»→none, GKSTCPLK→1.0. **P0.4** research-сигнал засчитывает Bash `ecosystem_scan.py`/`onec_search.py`/`its_fetch.py`. **P0.5** реликты лога удалены. **P0.2** ADR-035 окно перезапущено (06-22→07-06 потеряно → 07-03→07-17). Тесты: 173 таргетных passed (parity 20 + bridge 115 + onec 15 + gate 23), ruff+compile чисто. | `onec-task-completion-stop.py` + `shared/gate_policies.py` + `gate-orchestrator-stop.py` + `shared/pipeline_1c_bridge.py` + 3 теста + ADR-035 |

> Триггеры обновления §18 (memory `feedback-roadmap-progress-log-protocol`): закрытие фазы, ADR, снятый блокер → строка + коммит `docs(roadmap):`.
