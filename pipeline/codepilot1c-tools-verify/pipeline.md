# Pipeline: Проверка codepilot1c MCP (формы/макеты/СКД) + диагностика 2 read-багов

**Тип:** trivial (диагностика инструментов, без правок конфигурации) · **Дата:** 2026-06-21

## 1. План
Проверить все 92 инструмента codepilot1c MCP на живом EDT-проекте `Конфигурация`, особенно: редактирование форм, табличные документы (макеты), СКД. Затем ответить на «как исправить» найденные баги.

## 2. Дизайн
Подход: discover_tools по 8 категориям → live-вызовы read-инструментов на реальных объектах (`Document.гкс_НаправлениеНаРазгрузку`, `Report.*`) → проверка шлюза мутаций (`edt_validate_request`, без исполнения мутаций) → grounding корня багов чтением реальных `.dcs`/`.mxlx` файлов → web/EDT-API research для рецепта фикса.

## 3. Реализация (выполненное)
- Прогнаны: discover_tools×8, scan_metadata_index, edt_metadata_details, inspect_form_layout, inspect_template, dcs_manage (get_summary/list_nodes), validate_query (вкл. dcsMode), edt_validate_request (форма+СКД).
- Прочитаны реальные `Template.dcs` (валидный DataCompositionSchema XML) и `Template.mxlx` (валидный spreadsheet XML) — подтверждён корень.
- Память: `reference_codepilot1c_form_template_dcs_tools.md` (+ индекс).
- Кеш arch-research `1c-form-skd-spreadsheet-tooling-2026.md` дополнен §LIVE-прогон 2026-06-21 + рецепт фикса; `_index.json` last_verified=2026-06-21.

## 4. Тест / результат
- Формы: ✅ `inspect_form_layout` полноценно; шлюз мутаций работает (токен).
- Макеты: ❌ `inspect_template` хардкодит `.mxl` → не читает `.mxlx` (0×0, «файл не найден»).
- СКД: ❌ `dcs_manage` read слеп (datasets/params=0 даже у типового отчёта; `.dcs` не парсится).
- `validate_query(dcsMode)`: ✅.
- Корень обоих read-багов: плагин читает только EMF/`.mdo`, не грузит content-ресурс. Фикс — в плагине (AGPL OSS) или обход (читать `.dcs`/`.mxlx` напрямую). Рецепт — в кеш-файле.
