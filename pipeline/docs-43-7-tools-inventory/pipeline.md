# Pipeline: 43.7 — полный инвентарь инструментов анализа + реальные прогоны

**Тип:** complex (inventory + live-tests + docs) · **Дата:** 2026-06-21

## 1. План
Инвентаризировать весь 1С-аналитический инструментарий, разложить по этапам пайплайна, протестировать каждое семейство на реальном примере, внести в 43.7.

## 2. Дизайн
Live-прогоны по семействам (bsl-semantic-search, bsl-code-search, 1c-mcp-crud, codepilot1c, edt-mcp, cc-1c-skills, scripts) на боевой Конфигурации → таблица «тул → сервер → этап → что → реальный результат» + находки + маппинг этапов в 43.7.

## 3. Реализация
- Прогнано ~20 инструментов на реальных объектах (гкс_НаправлениеНаРазгрузку, ПолучитьПоРегистрации, ПФ_MXL_АктРасхожденияВеса).
- 43.7 расширена секцией «Полный инвентарь по этапам» + «Находки» + «Маппинг этапов».
- Память: feedback_bsl_code_search_empty (+ индекс).

## 4. Тест / результат
- ✅ bsl_stats(37694), bsl_search(rel1.123), bsl_impact_analysis(24), bsl_dead_code(3596), get_metadata_tree, execute_query(29873), bsl_list_methods(14), bsl_analyze_method(unused-param), execute_code(PDF), get_project_errors, update_database.
- ❌ НАХОДКА: bsl-code-search (search_symbols/find_callers) пуст даже на реальном символе → зафиксировано + альтернативы.
- ⚠ bsl_object_info резолв капризен; codepilot read СКД/.mxlx сломан (cc-1c-skills замена).
