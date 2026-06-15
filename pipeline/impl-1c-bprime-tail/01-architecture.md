# B′ хвост — Планирование (F-1.6 + W + input-ingestion)

3 независимых пункта, завершающих B′. Каждый — отдельный обратимый кусок.

## F-1.6 — этап-4 advance
**Цель:** закрыть этап 4 (Тестирование) по факту прохождения тестов. **Сигнал (verified):**
`features/<task>/.run-state.json` `{task,last_run,chain[],blockers}`, «всё прошло» = непустой `chain` И все
`chain[].status=="passed"`. **Подход:** +`advance_test_done(path)` в bridge → дёргается из существующего
PostToolUse `pipeline-1c-advance` (тот же guard по title-метке). Откат = revert функции + 1 вызов.

## W — TOOL-USAGE отчёт + глоб-агрегация
**Цель:** per-task отчёт эффективности + cross-task накопление. **Подход:** `scripts/tool_usage_report.py`
(stdlib, читает `data/hook-invocations.jsonl` по `correlationid==run_id` → per-tool calls/errors/avg-latency →
`TOOL-USAGE-REPORT.md` + append в `data/tool-effectiveness.jsonl`; `--rollup` = cross-task агрегат). Переиспользуем
существующий лог (НЕ duckdb-зависимость — прямой разбор jsonl). Откат = удалить скрипт + jsonl.

## input-ingestion — V.6 дизамбигуация (G20–G23)
**Цель:** при 1С-задаче из чата — классифицировать тип (T1/T2/T3) + инъектить протокол V.6 (ASK при неоднозначности,
folder-rules, prior-load для T3). **Подход:** UPS-хук `onec-task-input.py` — детект 1С-задачи (JIRA ИЛИ 1С-сигнал+таск-глагол),
классификация по ключам, `system_message` с протоколом; +`classify_1c_task(prompt)` в bridge (тестируемо). НЕ блокирует;
не на слэш-командах (их ведёт preflight). Откат = settings-запись + хук + функция.

**Общие инварианты:** best-effort, не ломать; 1С-guard где трогаем pipeline; тесты collision-immune + live.
