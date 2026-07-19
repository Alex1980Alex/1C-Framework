# ADR-055: Known-issues слой в tool-health («xfail для инструментов»)

- **Статус:** Accepted
- **Дата:** 2026-07-19
- **Исследование:** [cache/tool-alert-suppression-known-issues-2026.md](../cache/tool-alert-suppression-known-issues-2026.md)

## Контекст

`tool-health-analyzer` (roadmap 260713/260718) метит инструмент `broken` по метрикам за 14д-окно и **авто-заводит mandatory-задачу диагностики** (cooldown 72ч). Для инструментов, сломанных по **ИЗВЕСТНОЙ внешней причине**, это whack-a-mole: задача регенерится вечно, а метрика не самоочистится.

Живой кейс: `mcp__codepilot1c__qa_run` (42%) / `qa_generate` (0/3). Корень разобран в **W13**: (a) EDT-runtime `getThickClientInfo` отсутствует в EDT 2025.2.6 (апстрим-баг); (b) `infra_error` при exit0-успехе (истина в junit) → успехи логируются как провалы; binary-путь **доказан рабочим**. Фикс внешний/операционный, метрика останется красной из-за ложных негативов.

В `analyze_tool_health.py` не было механизма подавления → задачи плодились.

## Решение

Known-issues слой по best-practice форме «xfail для инструментов» (см. research: Alertmanager silences/inhibition + pytest `xfail(strict=True)`→xpass):

- **Config** `data/reports/tools/known_issues.json`: `{tool: {reason, ref, review_by}}`.
- **Вердикт `known-issue`** (🔕) вместо `broken/degraded/ineffective` для зарегистрированных тулов. Виден в отчёте/баннере с причиной+ref, но **баннерный escalation-фильтр `(broken,degraded)` его не подхватывает → mandatory-задача НЕ заводится**.
- **4 свойства** (research): (1) reason+ref+audit-trail, видимость; (2) `review_by` обязателен — **missing/непарсимая дата → подавление НЕ действует** (`_review_expired` fail-closed, нет вечного молчаливого mute); (3) **xpass-детект** — `healthy` known-issue → `recovered_known_issue`, баннер «возможно починен, сними suppression»; (4) overlay после infra, per-tool.
- Баннер: known-issue тул держится в `current_active` (как degraded) → НЕ ложное «вылечено», cooldown-запись сохранена.

## Последствия

**Положительные:** whack-a-mole убран (qa_run/qa_generate `broken`→`known-issue`, задачи не заводятся); проблемы **видны, датированы, авто-всплывают** при восстановлении/истечении; корень pollution закрыт без правки апстрим-плагина. Fail-soft (нет config → поведение прежнее), fail-closed (нет даты → не подавляет).

**Отрицательные:** подавленный тул не алертит, если сломается ПО-НОВОМУ (митигация: review_by-expiry + xpass-детект). Требует ручного снятия записи после реального фикса.

## Альтернативы (отклонены)

- **Наивный вечный allowlist** — антипаттерн (research: quarantine «опасен как постоянный»); нет expiry/xpass.
- **Починить `infra_error`→junit в обёртке** — «настоящий» фикс, но часть дефекта апстримная (в плагине); отложено как отдельная задача (upstream issue-кандидаты, roadmap 260718). known-issue слой — трекинг до неё.
- **Закрывать задачи разово** — возвращаются через 72ч.

## Связанные файлы

`scripts/analyze_tool_health.py` (verdict + overlay + sidecar), `.claude/hooks/tool-health-banner-on-start.py` (surfacing), `data/reports/tools/known_issues.json`, `tests/unit/test_tool_health_known_issues.py`. Память [[reference-codepilot1c-qa-run-binary-path]], W13 (roadmap 260718).
