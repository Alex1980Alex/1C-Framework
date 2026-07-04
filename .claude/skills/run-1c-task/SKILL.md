---
name: run-1c-task
description: AUTO-оркестратор 1С-задачи — прогон analyze→implement→test БЕЗ паузы на ревью первого этапа. ИСПОЛЬЗУЙ для /run-1c-task. Вход — JIRA-код / описание из чата / путь к папке ТЗ. Делегирует методикам analyze-1c-task-v2 + implement-1c-task + va-bdd-testing/run-1c-tests, сам их НЕ дублирует. Гейтованный режим (с паузой на ревью ANALYSIS-REPORT) — отдельные /analyze-1c-task + /implement-1c-task.
version: 1.0.0
updated: 2026-06-15
commands:
  - /run-1c-task
---

# /run-1c-task — AUTO-прогон 1С-задачи (4 этапа без паузы)

> **AUTO-режим** (ADR-019 B′, доработка 2026-06-15): весь generic-пайплайн
> Планирование→Дизайн→Кодирование→Тестирование за один проход, БЕЗ паузы на ревью первого этапа.
> Гейтованный режим (с паузой/правками ANALYSIS-REPORT) — отдельные `/analyze-1c-task` + `/implement-1c-task`.

Эта команда **оркестрирует** существующие методики (analyze-1c-task-v2, implement-1c-task,
va-bdd-testing). Она их **не дублирует** и **не меняет** — только ведёт по этапам и сама ставит `approve`.

---

## Вход (`$ARGUMENTS`)

Определи источник через `pipeline_1c_bridge.resolve_task_input(arg)`:

```bash
.venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'.claude/hooks'); from shared.pipeline_1c_bridge import resolve_task_input; import json; print(json.dumps(resolve_task_input(r'''$ARGUMENTS''')))"
```

Возврат `{kind, slug, folder}`:
- **`folder`** — путь к готовой папке ТЗ (spec + скриншоты внутри). Собери из неё ТЗ (мультимодальный Read).
- **`jira`** — JIRA-код (напр. `GKSTCPLK-2182`). Задача из трекера; ТЗ собери по коду.
- **`chat`** — описание из чата. Если деталей мало → действуй по протоколу input-ingestion (V.6): уточни тип/папку.

---

## Оркестрация — 4 этапа БЕЗ паузы

### Этап 1-2 — Планирование + Дизайн (методика analyze-1c-task-v2)
1. `pipeline_state init <slug> --title "1С-задача (run-1c-task): <slug>"` (идемпотентно).
   **kind=folder** → добавь `--task-dir "<folder>"`: состояние (`.pipeline-state.json`), `LOOPS.md` и
   имена этапов (ANALYSIS-REPORT.md / IMPLEMENTATION-PROGRESS.md / .run-state.json) рождаются СРАЗУ в папке
   задачи рядом с её артефактами. Для kind=chat/jira папка узнаётся при записи ANALYSIS-REPORT.md →
   состояние авто-переезжает туда (relocate-on-artifact, хук `pipeline-1c-advance`).
   1.5. **ОБЯЗАТЕЛЬНО в начале** (иначе единый Stop-gate `onec-task-completion-stop` заблокирует
   завершение): **recall** — `mcp__memory-orchestrator__unified_search` (+ `search_patterns`) по теме задачи;
   **внешний анализ** — Infostart/RU через `python scripts/onec_search.py`, GitHub через
   `python scripts/ecosystem_scan.py` (голый GitHub-`WebSearch` блокирует энфорсер ADR-039; `WebFetch`
   точечных страниц — ок), с атрибуцией находок. Гейт засчитывает research и по Bash-вызовам этих скриптов (P0.4).
2. **Активируй skill `analyze-1c-task-v2`** и выполни его методику (Фазы 1-5) **ЦЕЛИКОМ** → **ANALYSIS-REPORT.md**.
   - kind=folder → источник ТЗ = папка (spec + скриншоты); kind=jira → по коду; kind=chat → по описанию.
   - Папка реализации: `configuration/<родительская-задача>/docs/<YYMMDD_slug>/` (провизорно; см. память
     `project-1c-task-input-taxonomy`).
   - ⚠ **НЕ конспектируй методику.** ANALYSIS-REPORT обязан соответствовать шаблону analyze-1c-task-v2
     (§1-§11) с КОНТЕНТ-секциями (не просто номерами): **§1 Требования `[REQ-N]` · §2 объекты с
     `[MODIFIED]`/`[ADDED]` · §3 анализ+паттерны · §4 пронумерованные точки модификации (файл/строка/было→стало/
     образец) · §6 Риски/открытые вопросы · §7 Тест-план · §9 Резюме · §11 Сложность+Маршрут · МЕТАДАННЫЕ JIRA**.
     Это конвенция остальных задач (см. соседние `*/ANALYSIS-REPORT.md`); тонкий конспект — пробел.
3. Запись `ANALYSIS-REPORT.md` авто-продвинет этапы 1→2 (хук `pipeline-1c-advance`, F-1.5). Тот же хук запускает
   **advisory-валидатор** `lint_1c_artifacts.py` — при нехватке core-секций выдаёт нудж (не блок). Само-проверка:
   `python scripts/lint_1c_artifacts.py "<папка>/ANALYSIS-REPORT.md"` → score должен быть ✓ (≥70).

### Этап 2.4 — Preflight полноты ТЗ (H6: AUTO-approve идёт без человека)

Перед авто-approve (человек НЕ ревьюит дизайн) — короткий self-check полноты ТЗ. Если хотя бы один
пункт «нет» → **НЕ авто-approve: ОСТАНОВИСЬ и спроси пользователя** (или для kind=folder — выпиши
недостающее в ANALYSIS-REPORT и запроси уточнение):

- [ ] ТЗ собрано (spec+скриншоты из folder · описание из JIRA · достаточное описание из чата);
- [ ] есть критерий приёмки / ожидаемый результат («что считается готово»);
- [ ] объём понятен — затронутые объекты/модули названы (не расплывчатое «что-то доработать»);
- [ ] нет критической неоднозначности / противоречия в ТЗ (по итогам Фаз 1-5 анализа).

Это конкретизация хард-правила «AUTO ≠ игнор блокеров»: AUTO экономит паузу на рутинном ревью,
но не даёт права проскочить неполное/противоречивое ТЗ.

### Этап 2.5 — АВТО-APPROVE (ключевое отличие)
4. `pipeline_state approve <slug> --by auto` — **БЕЗ паузы на человека.** Это осознанный обход ревью
   (пользователь выбрал `/run-1c-task`). Гейт F-2 в AUTO-потоке не участвует (skill-делегирование, не slash).
   Метка `approved_by=auto` (а не `human`) — audit-след «дизайн НЕ ревьюился человеком» (N5).

> **Хард-правило (AUTO ≠ игнор блокеров):** если анализ выявил критическую неоднозначность, противоречие в ТЗ
> или высокий риск — **ОСТАНОВИСЬ и спроси пользователя** перед approve. Авто-режим экономит паузу на рутинном
> ревью, но не отменяет здравый смысл.

### Этап 3 — Кодирование (методика implement-1c-task)
5. **Активируй skill `implement-1c-task`** и выполни его методику (Этап 0 Preflight → Этапы 1-8) **ЦЕЛИКОМ** по
   готовому ANALYSIS-REPORT.md → BSL/XML через EDT-MCP, BP-verification, `get_project_errors=0`.
   - ⚠ **НЕ конспектируй.** IMPLEMENTATION-PROGRESS обязан нести: **Статус · Pipeline mode · Выполненные точки
     (с `EDT errors: 0` + образец) · `## Отклонения от ANALYSIS-REPORT` (даже «нет») · Результаты тестирования
     (render-verify/BP) · корпоративное `## Сообщение коммита` (Как было/Как стало/Изменённые объекты) +
     `МЕТАДАННЫЕ: <JIRA>`**. Это конвенция соседних задач.
6. Запись `IMPLEMENTATION-PROGRESS.md` авто-продвинет этап 3 (F-1.5). Тот же хук запускает advisory-валидатор;
   само-проверка: `python scripts/lint_1c_artifacts.py "<папка>/IMPLEMENTATION-PROGRESS.md"` → score ✓ (≥70).

### Этап 4 — Тестирование (BDD-трек + YAxUnit-трек)

**⚠ Bounded fix-петля (P3.2, паттерн agentico/Graybark — против бесконечного retry):** тесты красные →
чинишь → перепрогон. **Перед КАЖДОЙ починкой** отметь попытку:
`pipeline_state.py bump-attempt <slug> 4` → JSON `{count, max, exceeded}` (max = env
`ONEC_MAX_FIX_ITERATIONS`, дефолт 4). Если `exceeded=true` — **ОСТАНОВИ AUTO-петлю** и эскалируй:
`pipeline_state.py needs-human <slug> <p0|p1|p2> "<в чём затык>"` (p0 — архитектурное/продуктовое
решение · p1 — непонятный путь · p2 — быстрый фикс), затем дай пользователю резюме (что пробовал,
где застрял) и СТОП. Не «дотачивай» бесконечно — застревание требует человека.

**BDD-трек (UI-сценарии):**
7. **Активируй skill `va-bdd-testing`** (или команду `/run-1c-tests`) → прогон BDD-сценариев до зелёных.

**YAxUnit-трек (серверная логика):**
7.5. **Если реализация затронула серверные методы** (общие модули / модуль объекта / модуль менеджера):
   - **Активируй skill `yaxunit-unit-testing`** (или команду `/write-1c-unit-tests`) → написание тест-модулей
     в расширении `src/bsl/exts/UnitTests/` + деплой (`LoadConfigFromFiles + UpdateDBCfg`).
   - Затем `/run-1c-unit-tests <папка задачи>` → прогон через `mcp-onec-test-runner`.
   - YAxUnit-записи (`type == "yaxunit"`) добавляются в тот же `.run-state.json` в массив `chain[]`.

8. Зелёный `.run-state.json` (все `chain[].status==passed`, включая `type == "yaxunit"` записи) авто-продвинет этап 4 (F-1.6).
   8.5. **ОБЯЗАТЕЛЬНО после verify PASS** (иначе `onec-task-completion-stop` заблокирует): `mcp__skill-learning__capture_pattern`
   — зафиксировать переиспользуемый приём (+ запись в `.md`-память при новом правиле/граблях заказчика).

### W — отчёт об использовании инструментов
9. **Сначала** запиши `<папка задачи>/TOOL-RESULTS.json` — курируемые саммари **результата работы** по
   инструменту `{"<tool>": "<что дал в этой задаче>"}` (лог несёт только метрики — результат знаешь только ты).
   Затем `python scripts/tool_usage_report.py --run-id <id> --slug <slug>` →
   `TOOL-USAGE-REPORT.md` в папке задачи: чеклист обязательных петель + блок на инструмент
   (метрики + назначение + **результат** из TOOL-RESULTS.json). Путь резолвится через реестр
   `pipeline_state.state_dir(slug)` — единый источник, как `.pipeline-state.json`/`LOOPS.md`;
   `--results <json>` — явный путь, иначе авто `<папка>/TOOL-RESULTS.json`. `--task-dir <D>` — override.

### Финал
10. Отчёт пользователю: что сделано на каждом этапе + вердикт тестов + ссылки на артефакты.
    Сводка обязательных петель (recall/capture/research/skill/pipeline) авто-пишется в
    `pipeline/<slug>/LOOPS.md` хуком `onec-task-completion-stop` на Stop (H2) — сошлись на неё.

---

## Контракт

| Свойство | AUTO `/run-1c-task` | Гейтованный `/analyze` + `/implement` |
|---|---|---|
| Пауза на ревью ANALYSIS-REPORT | **нет** (авто-approve) | да (человек правит отчёт + approve) |
| Команд | 1 | 2 |
| Объём | analyze→implement→test | analyze; затем отдельно implement |
| Методики 1С | те же (analyze-1c-task-v2 / implement-1c-task) | те же |
| Когда | ТЗ доверенное/готовое, рутина | нужен контроль первого этапа |

## ВАЖНО
- Методики 1С (analyze-1c-task-v2, implement-1c-task) — **не изменяются**; run-1c-task только оркестрирует + авто-approve.
- AUTO ≠ игнор блокеров: критическая ошибка/неоднозначность → СТОП и вопрос.
- Проведение документов = пользователь (Claude без GUI) — как и в гейтованном потоке.
- Реверс: удалить команду + этот скилл + `resolve_task_input`; гейтованный поток (B′) не затронут.
