# Design — «xfail для инструментов»: known-issues слой в tool-health

## Цель
Убрать whack-a-mole (broken-тул с внешним корнем плодит mandatory-задачу каждые 72ч),
НЕ ослепнув. Best-practice форма (кеш `tool-alert-suppression-known-issues-2026.md`):
reason+audit-trail + review-by expiry + xpass-детект + fail-closed к видимости.

## Компоненты

### 1. Config `data/reports/tools/known_issues.json`
```json
{ "mcp__codepilot1c__qa_run": {
    "reason": "EDT-runtime getThickClientInfo апстрим-баг + infra_error при успехе (истина junit)",
    "ref": "W13 (roadmap 260718) / ADR-055 / reference-codepilot1c-qa-run-binary-path",
    "review_by": "2026-08-31" } }
```
gitignored `data/` → добавить `-f` при коммите (как отчёты? нет — конфиг курируемый, force-add).

### 2. `scripts/analyze_tool_health.py`
- Новый вердикт `known-issue` в `_VERDICT_ORDER` (позиция 2, сдвиг ineffective/unused/healthy) + `_VERDICT_MARK["known-issue"]="🔕"`.
- `_load_known_issues()` (fail-soft → {}), `_review_expired(review_by, now)` (missing/непарсимая дата → **expired=True**, fail-closed к видимости — запрещает вечное подавление без даты).
- `_apply_known_issues(tools, now)` — overlay ПОСЛЕ `apply_infra_to_tools` в `run()`:
  - `expired` → оставить реальный вердикт (ре-эскалация) + пометка `known_issue.expired`.
  - `healthy` → `recovered_known_issue=True` (xpass: «возможно решено»).
  - `broken/degraded/ineffective` → verdict=`known-issue`, stash `underlying_verdict`, reason = «причина [ref; review by дата]».
- Sidecar (`_latest.json`): +`known_issues[]` (tool/reason/ref/review_by/underlying) +`recovered_known_issues[]`. `alerts` фильтр остаётся `(broken,degraded)` → known-issue туда НЕ попадает.

### 3. `.claude/hooks/tool-health-banner-on-start.py`
- Escalation-цикл БЕЗ изменений (known-issue не в `broken` → mandatory-задача не заводится).
- +чтение `sidecar.known_issues` → тихая строка баннера «🔕 N подавлено (known-issue): tool — reason [ref]» (видно, не эскалируем).
- +чтение `sidecar.recovered_known_issues` → строка «✅ tool возможно починен (known-issue), сними suppression» + **ломает «тихо»** (actionable).
- `known_issues` сам по себе НЕ ломает silence (подавлено), но добавляется если баннер уже показывается.

### 4. Регистрация
qa_run + qa_generate в known_issues.json, ref W13, review_by 2026-08-31 (~6 нед).

### 5. Upstream issue-кандидаты
Секция в roadmap 260718: (a) getThickClientInfo отсутствует в EDT 2025.2.6; (b) infra_error при exit0-успехе (истина junit). Это «настоящий» фикс — внешний.

## Инварианты
- Отсутствие/пустой config → поведение побитово прежнее (fail-soft).
- Missing review_by → НЕ подавляет (fail-closed).
- Не трогаю логику broken/degraded/escalation для НЕ-known тулов.
- Текущие 2 задачи закрываю с дисп. на W13.

## Проверка
Юнит `tests/unit/test_tool_health_known_issues.py`: overlay 4 ветки (broken→known-issue / healthy→recovered / expired→broken / missing-date→broken), sidecar-списки, config-absent=noop. + прогон analyze_tool_health на живых данных (qa_run → known-issue, задача не заводится) + code-verify.
