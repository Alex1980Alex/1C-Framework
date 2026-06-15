---
name: run-1c-task
description: AUTO-оркестратор 1С-задачи — прогон analyze→implement→test БЕЗ паузы на ревью первого этапа. ИСПОЛЬЗУЙ для /run-1c-task. Вход — JIRA-код / описание из чата / путь к папке ТЗ. Делегирует методикам analyze-1c-task-v2 + implement-1c-task + va-bdd-testing/run-1c-tests, сам их НЕ дублирует. Гейтованный режим (с паузой на ревью ANALYSIS-REPORT) — отдельные /analyze-1c-task + /implement-1c-task.
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
   1.5. **ОБЯЗАТЕЛЬНО в начале** (иначе единый Stop-gate `onec-task-completion-stop` заблокирует
   завершение): **recall** — `mcp__memory-orchestrator__unified_search` (+ `search_patterns`) по теме задачи;
   **внешний анализ** — `WebSearch`/`WebFetch` (Infostart + GitHub best-practices), с атрибуцией находок.
2. **Активируй skill `analyze-1c-task-v2`** и выполни его методику (Фазы 1-5) → **ANALYSIS-REPORT.md**.
   - kind=folder → источник ТЗ = папка (spec + скриншоты); kind=jira → по коду; kind=chat → по описанию.
   - Папка реализации: `configuration/<родительская-задача>/docs/<YYMMDD_slug>/` (провизорно; см. память
     `project-1c-task-input-taxonomy`).
3. Запись `ANALYSIS-REPORT.md` авто-продвинет этапы 1→2 (хук `pipeline-1c-advance`, F-1.5).

### Этап 2.5 — АВТО-APPROVE (ключевое отличие)
4. `pipeline_state approve <slug> --by auto` — **БЕЗ паузы на человека.** Это осознанный обход ревью
   (пользователь выбрал `/run-1c-task`). Гейт F-2 в AUTO-потоке не участвует (skill-делегирование, не slash).
   Метка `approved_by=auto` (а не `human`) — audit-след «дизайн НЕ ревьюился человеком» (N5).

> **Хард-правило (AUTO ≠ игнор блокеров):** если анализ выявил критическую неоднозначность, противоречие в ТЗ
> или высокий риск — **ОСТАНОВИСЬ и спроси пользователя** перед approve. Авто-режим экономит паузу на рутинном
> ревью, но не отменяет здравый смысл.

### Этап 3 — Кодирование (методика implement-1c-task)
5. **Активируй skill `implement-1c-task`** и выполни его методику (Этап 0 Preflight → Этапы 1-8) по
   готовому ANALYSIS-REPORT.md → BSL/XML через EDT-MCP, BP-verification, `get_project_errors=0`.
6. Запись `IMPLEMENTATION-PROGRESS.md` авто-продвинет этап 3 (F-1.5).

### Этап 4 — Тестирование (методика va-bdd-testing / run-1c-tests)
7. **Активируй skill `va-bdd-testing`** (или команду `/run-1c-tests`) → прогон BDD-сценариев до зелёных.
8. Зелёный `.run-state.json` (все `chain[].status==passed`) авто-продвинет этап 4 (F-1.6).
   8.5. **ОБЯЗАТЕЛЬНО после verify PASS** (иначе `onec-task-completion-stop` заблокирует): `mcp__skill-learning__capture_pattern`
   — зафиксировать переиспользуемый приём (+ запись в `.md`-память при новом правиле/граблях заказчика).

### W — отчёт об использовании инструментов
9. `python scripts/tool_usage_report.py --run-id <id> --task-dir <папка реализации>` →
   `TOOL-USAGE-REPORT.md` (per-task) + `data/tool-effectiveness.jsonl` (cross-task rollup).

### Финал
10. Отчёт пользователю: что сделано на каждом этапе + вердикт тестов + ссылки на артефакты.

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
