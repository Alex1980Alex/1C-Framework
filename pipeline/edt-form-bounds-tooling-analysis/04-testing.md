# 04 — Тест / Верификация

## Проверки
- ✅ Фикс form-bounds: `elementsWithBounds 50/50`, `boundsSource: layoutProjection` (не native), warnings [].
- ✅ Флаг: `get_server_status.formRenderFlags.nativeFormLayoutRender == false`.
- ✅ Ground-truth форм: структура формы рендерится; assignable form-айтема → Object not found (подтверждает пробел слоя A для FormField layout).
- ✅ JSON-индексы: `adr/_index.json` (30 records), cache `_index.json` (52 topics), `1c-doc-research/cache/_index.json` (37) — все парсятся.
- ✅ Capture: `route_and_save` → memory-ai, `failed_targets: []`.

## Не покрыто (честно)
- СКД XDTO round-trip и runtime-конвейер НЕ исполнены вживую через execute_code (взято из источников 1code.info/FastCode + платформенного API) — live-проба отложена до реальной СКД-задачи.
- Структурная offline-правка `.mxlx` остаётся вне автоматизации (подтверждённый предел, не баг).

## Дополнение 2026-06-21: EDT-MCP фокус-свип (GitHub)
- Реальных Eclipse-plugin EDT-MCP — два: DitriXNew/EDT-MCP (используем) + ondysss/codepilot1c-edt (NEW, 131★/37rel/AGPL, агентный MCP Host :8765, watch-кандидат).
- velo/eclipse-mcp — не применим (JDT-only). Non-EDT read-only: feenlace/mcp-1c, ROCTUP/1c-mcp-metacode, artesk/1C_MCP_metadata.
- Подтверждено: ни один EDT-MCP не редактирует СКД/`.mxl(x)`; формы — inspect ок, edit только modify_metadata/XML. Новых MCP не вводим (ADR-030).
- Записано: cache §«EDT-MCP сервера... фокус-свип 2026-06-21» + capture memory-ai.

## Итог
Verify фикса — PASS. Анализ — завершён, решение зафиксировано (ADR-030).
