# ADR-030: Стратегия AI-правки UI/report-артефактов 1С (форма / табличный документ / СКД)

**Дата:** 2026-06-21
**Статус:** accepted
**Исследование:** [../cache/1c-form-skd-spreadsheet-tooling-2026.md](../cache/1c-form-skd-spreadsheet-tooling-2026.md) (§Deep-механики)
**Связь:** дополняет [ADR-029](029-1c-formsserver-skip-watch.md) (1c-formsserver SKIP/watch); опирается на cache `1c-doc-research/edt-mcp-form-render-flags` (фикс bounds 2026-06-21)

## Контекст

Сквозная задача треда — править layout формы (`horizontalStretch`/размер), перевёрстывать табличный документ (`.mxlx`, ширины колонок печатных форм) и работать со СКД. Нужна единая стратегия: каким слоем (EDT-модель / сырой XML / runtime-BSL) править КАЖДЫЙ из трёх артефактов и как верифицировать. Свип 2026-06-20/21 показал, что выделенного in-place AI-инструмента для этих операций по-прежнему нет, а слой A (EDT-модель) для форм-элементов неполон.

## Решение

Править **по слою, выбранному под артефакт** (не «один инструмент на всё»), с обязательным runtime-verify. Tractability-градиент **СКД > Формы > Табличный** (обоснование — cache §Deep-механики):

1. **СКД — слой XDTO + runtime [own/web].** Offline-правка через `СериализаторXDTO.ПрочитатьXML/ЗаписатьXML` (схема И настройки round-trip-ятся вне Конфигуратора), исполнение/verify — полный конвейер `КомпоновщикМакета→ПроцессорКомпоновки→ПроцессорВыводаВТабличныйДокумент` через `execute_code`. Самый AI-дружелюбный артефакт.

2. **Формы — слой EDT-модель, с откатом на XML для stretch/size [exp/own].** Большинство свойств — `modify_metadata`; но layout-свойства FormField (`horizontalStretch`, size, width) **не в assignable** (live 2026-06-21: assignable-адресация form-айтема → `Object not found`) → их правка = **`Form.form` XML Edit + `clean_project`**. Динамика per-session → runtime `Элементы.*` в `ПриСозданииНаСервере`. **Verify — `get_form_layout_snapshot` с per-element bounds** (доступно после фикса `nativeFormLayoutRender=false`, 2026-06-21): правка раскладки теперь проверяется количественно (diff bounds), а не «на глаз».

3. **Табличный документ — только runtime-BSL + GUI для структуры [web/exp].** Offline-парсера `.mxl/.mxlx` нет; `1CFilesConverter` конвертит лишь whole-artifact (CF/XML/EDT), не редактирует макеты; EDT не рекомпилит внешние `.mxlx`. Программно — `ТабличныйДокумент` в runtime; **«колонки разъезжаются» лечить `ПрисоединитьТабличныйДокумент(..., СоздатьФорматСтрок=Истина)`**, а не `<merge>` в `.mxlx`. Структурная вёрстка → GUI-редактор макета ИЛИ `.mxlx` XML + `update_database` (НЕ `clean_project`). Verify — `execute_code` → `ТабДок.Записать(PDF)` → Read.

4. **Новых MCP не вводим [own].** 1c-formsserver — SKIP/watch (ADR-029, генерит XML, не in-place); СКД-MCP и `.mxl`-парсер не существуют. Стек `edt-mcp` + `1c-mcp-crud` (`execute_code`) + прямой XML-Edit покрывает все три кейса.

## Последствия

### Положительные
- Детерминированный выбор слоя на каждый артефакт — меньше тупиковых попыток (напр. не искать assignable-свойство stretch, которого нет).
- Форм-правки стали верифицируемы количественно (bounds) — закрывает риск «поправил, а раскладка поехала».
- СКД-правки полностью автоматизируемы (offline-edit + runtime-verify).

### Отрицательные
- Табличный документ остаётся «ручным» по структуре (GUI) — AI ограничен runtime-генерацией; structural re-layout не автоматизируется.
- `clean_project` для форм отбрасывает несохранённые in-memory правки EDT — нужен порядок «сохранить → Edit XML → clean».
- Java-режим раскладки форм (для bounds) тяжелее для IDE глобально — держать `nativeFormLayoutRender=false` точечно под задачи с verify, иначе вернуть `true`.

## Альтернативы
- **Adopt 1c-formsserver под формы** — отклонено (ADR-029): незрелый, генератор, не in-place, styling-свойства не покрыты.
- **Написать собственный `.mxl`-парсер (Python/OneScript)** — отклонено: высокая стоимость реверса бинарного формата, runtime-BSL уже даёт полный object-API.
- **«Один MCP на все артефакты»** — отклонено: артефакты неоднородны по доступности (XDTO/EDT-model/binary), один слой не оптимален.

## Связанные файлы
- `.claude/skills/edt-mcp/` (форм-тулы, modify_metadata, snapshot), `.claude/skills/1c-doc-research/cache/edt-mcp-form-render-flags.md`
- `.claude/skills/architecture-research/cache/1c-form-skd-spreadsheet-tooling-2026.md`
- runtime: `1c-mcp-crud` `execute_code` (СКД-конвейер, ТабличныйДокумент, PDF-render-verify)
