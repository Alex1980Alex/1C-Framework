# 01 — Планирование

## Задача
Две связанные части:
1. **Верификация** фикса EDT-MCP form bounds (`nativeFormLayoutRender=false`) после рестарта EDT + `/mcp reconnect`.
2. **Глубокий анализ** инструментария AI-правки трёх UI/report-артефактов 1С: формы (`.form`, `horizontalStretch`/size), табличный документ (`.mxl/.mxlx`), СКД (DataCompositionSchema) — поверх GitHub-свипа пользователя.

## Контекст
Сквозной тред: правка layout формы + перевёрстка печатных форм. Прежний кеш `1c-form-skd-spreadsheet-tooling-2026` фиксировал 3 слоя доступа и инвентарь MCP, но без глубоких механик правки. Память: mxlx-not-compiled, render-verify, form-bounds-render-flag.

## Объём
- Live-verify через `edt-mcp` (get_server_status, get_form_layout_snapshot, get_metadata_details).
- Research: WebSearch/WebFetch (Infostart/GitHub/v8.1c.ru/its) по механикам правки каждого артефакта.
- Артефакты знаний: углубление кеша, ADR-030, capture в память.

## Классификация
complex (research + несколько артефактов знаний + live-verify).
