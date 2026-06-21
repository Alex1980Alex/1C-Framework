# 03 — Реализация (фактические артефакты)

## Verify фикса form-bounds
- `get_server_status` → `formRenderFlags.nativeFormLayoutRender=false`, `nativeFormBufferedLayoutRender=true`.
- `get_form_layout_snapshot` (Document.гкс_НаправлениеНаРазгрузку.Forms.ФормаДокумента) → `elementCount: 50`, `elementsWithBounds: 50`, `boundsSource: layoutProjection`, warnings []. (Корень — фикс из прошлого прохода: cache `1c-doc-research/edt-mcp-form-render-flags`.)

## Research (WebSearch/WebFetch + live EDT-MCP)
- Формы: `horizontalStretch`/size = design-time .form XML; «быстрое масштабирование форм» = user zoom (не путать); live — assignable form-айтема → Object not found (modify_metadata не покрывает layout FormField).
- Табличный: offline-парсера нет; 1CFilesConverter = whole-artifact CF/XML/EDT (не редактор); EDT не компилит .mxlx; runtime ТабличныйДокумент + ПрисоединитьТабличныйДокумент/СоздатьФорматСтрок.
- СКД: offline round-trip СериализаторXDTO (схема+настройки) + runtime-конвейер КомпоновщикМакета→ПроцессорКомпоновки→ПроцессорВыводаВТабличныйДокумент.

## Артефакты знаний
- `architecture-research/cache/1c-form-skd-spreadsheet-tooling-2026.md` — §«Deep-механики правки» (формы/табличный/СКД + градиент tractability).
- `architecture-research/adr/030-1c-ui-report-artifact-editing-strategy.md` (accepted) + индекс.
- `1c-doc-research/cache/edt-mcp-form-render-flags.md` (из прошлого прохода) + индекс.
- Capture: memory-ai `cf7d3714` (route_and_save).
