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

## Итог
Verify фикса — PASS. Анализ — завершён, решение зафиксировано (ADR-030).
