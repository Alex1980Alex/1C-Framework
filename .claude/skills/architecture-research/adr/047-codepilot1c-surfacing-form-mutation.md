# ADR-047: Surfacing codepilot1c — форм/DCS/роль/макет-мутации в 1С-пайплайне

**Дата:** 2026-07-06
**Статус:** accepted
**Исследование:** inventory codepilot1c через `discover_tools` (forms/dcs/metadata/qa), инцидент GKSTCPLK-2640

## Контекст

На GKSTCPLK-2640 нужно было добавить флажок на форму набора констант. EDT-MCP `create_metadata` отклонил привязку поля к члену `ConstantsSet` (dotted `dataPath` он трактует как колонку динсписка). Вместо поиска профильного тула я упал в ручную XML-правку `Form.form`. Пользователь указал: есть **codepilot1c (1С Copilot)** с `mutate_form_model` — профильный form-инструмент.

**Корень surfacing-провала (по коду):** у codepilot1c **не было ни скилла, ни бандла** в `skill-router-config.json` (grep=0), поэтому роутер его НИКОГДА не подсвечивал — в отличие от edt-mcp/1c-mcp-crud/bsl-debug/va-bdd (у них есть скилл+бандл). Плюс методичка `implement-1c-task` в таблицах инструментов называла только EDT-MCP/1c-mcp-crud/bsl-debugger — codepilot1c не упоминался. Итог: два независимых пробела (упреждающий router-surfacing И mid-task методичка) оставляли инструмент невидимым.

**Ниша codepilot1c (что EDT-MCP НЕ умеет, по `discover_tools`):** мутация форм (`create_form`/`mutate_form_model`/`apply_form_recipe`), СКД (`dcs_manage`), права ролей (`inspect/mutate_role_rights`), макеты печатных форм (`render_template`/`inspect_template`), QA Vanessa/YAxUnit через модель (`qa_*`/`author_yaxunit_tests`). Метаданные/BSL/debug — тяжёлый overlap с EDT-MCP; свой гейт `edt_validate_request → validation_token` перед мутацией.

## Решение

Двухслойная автоматизация surfacing (оба пробела закрыты):

1. **Router-surfacing (упреждающий):** новый скилл [`codepilot1c`](../../codepilot1c/SKILL.md) (lean, ниша+workflow validation_token, 90 строк) + бандл `codepilot1c` в `skill-router-config.json` с **уникальными** keywords (`mutate_form_model`/`create_form`/`dcs_manage`/`mutate_role_rights`/`render_template`/«мутация формы»/«схема компоновки данных»/«права роли» — без коллизий с edt-mcp). Проверено: промпт «добавить флажок на форму» → роутер выдаёт `ACTIVATE codepilot1c`.
2. **Методичка (mid-task):** секция codepilot1c в tool-таблицах `implement-1c-task` (форма/DCS/роль/макет → codepilot1c, с пометкой «EDT-MCP форму не мутирует») + cross-ref в `edt-mcp` (секция Форм + Связанные скиллы).

**Процессный урок (в память [[feedback-form-mutation-codepilot1c]]):** на «инструмент не умеет X» — сначала `ToolSearch`/`discover_tools` за профильным тулом, только потом фолбэк. Знание воркэраунда не должно убивать поиск лучшего пути.

## Последствия

**Положительные:** форм/DCS/роль/макет-задачи теперь маршрутизируются на codepilot1c и упомянуты в пайплайне; ручной XML форм — только явный фолбэк. Скилл-lint нового скилла чист (desc 883/1024, body 90/500). Self-updating guard `gen_hooks_catalog --verify-doc` поймал дрейф счётчиков триады (66→67 bundles, 98→99 skills) — обновлены.

**Отрицательные / риски:** ещё один MCP-сервер в активном наборе → рост surface; overlap с EDT-MCP по метаданным/BSL может путать выбор (митигировано таблицей «когда какой сервер»). codepilot1c tools остаются deferred (грузятся `ToolSearch`) — скилл это документирует.

## Альтернативы

- **Только методичка (без router-бандла)** — отклонено: не закрывает упреждающий surfacing для новых форм-задач.
- **Только router-бандл на существующий edt-mcp скилл** — отклонено: codepilot1c — отдельный сервер с отдельным workflow (validation_token), заслуживает своего home; смешение с edt-mcp запутало бы.
- **Полный 70-тул скилл codepilot1c** — отклонено (over-build): скилл сфокусирован на нише (то, чего нет у EDT-MCP) + указатель на `discover_tools` для остального.

## Связанные файлы
`.claude/skills/codepilot1c/SKILL.md` · `skill-router-config.json` (бандл) · `implement-1c-task/SKILL.md` · `edt-mcp/SKILL.md` · `hooks-skills-mcp-triad/SKILL.md` (счётчики) · память `feedback_form_mutation_codepilot1c`.
