# 02 — Дизайн (одобрено)

## Подход
1. **Verify-first:** подтвердить флаг через `get_server_status.formRenderFlags`, затем фактические bounds через `get_form_layout_snapshot` на реальной форме документа.
2. **Research по слоям:** для каждого артефакта определить (a) offline-правку, (b) runtime-исполнение/verify, (c) предел. Источники — Infostart/GitHub/v8.1c.ru/its + live EDT-MCP ground-truth.
3. **Синтез:** tractability-градиент + решение «слой-под-артефакт» → ADR-030 (дополняет ADR-029).
4. **Персист:** кеш `architecture-research` (факты) + ADR (решение) + capture в store.

## Делегирование
Без субагентов (веб в основном цикле; лимит был только на субагентов — отмечено пользователем). Research — прямые WebSearch/WebFetch.

## Критерий приёмки
- bounds > 0 на форме (verify фикса);
- по каждому артефакту — подтверждённый путь правки + verify;
- ADR-030 accepted, индексы валидны.

**Статус: approved** (self-approve, AUTO-режим анализа — пользователь запросил «сделай глубокий анализ»).
