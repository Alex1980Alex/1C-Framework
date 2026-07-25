# Закрытие 21 doc-gap аудита (bsl_tool + memory_subsystem + hook)

**Дата:** 2026-07-25 · **Тип:** docs + мелкий code-fix · **Вход:** «продолжить закрытие остальных 21 doc-gaps, без промежуточных подтверждений»

## Результат
Аудит `scripts/audit_docs_skills.py`: **21 → 0 doc-gaps**, skill-gaps 0.

## Что сделано
1. **bsl_tool (11 гэпов).** Перед документированием проверил живость (урок ADR-056): `src/bsl/sonar/` — рабочий CLI-обёртка sonar-scanner, 0 стабов, версия плагина обновлялась вручную ⇒ документируем, не ретируем.
   - `28.1_Обзор.md` (таблица «Смежные подсистемы `src/bsl`»): расширены строки `coding_assistant` (BSLStyleExtractor/BSLStyleProfile) и `knowledge_graph` (MetadataExtractor/ObjectInfo + честная атрибуция потребителей), добавлены строки `parser/` (BSLModule, CompilationDirective, BSLSymbol/Param/Call/Variable/Region, SymbolType, ModuleType) и `sonar/`; нота о ретирменте `mcp_server/`.
   - `43.9.9_СТАТАНАЛИЗ_И_КАЧЕСТВО.md`: новая секция «Python-слой `src/bsl/sonar/`» (классы, CLI, отношение к продакшн-контуру ps1+scripts).
2. **memory_subsystem (9 гэпов).**
   - `27.2_Оркестратор.md`: RelatedEntity (+ `effective_strength`), SearchResultItem/LinkedEntity; попутно исправлен дрейф API (`create_link` полная сигнатура, `get_related_entities` вместо несуществующих `get_related`/`get_neighbors`, полный список индексов).
   - `27.4_Инфраструктура.md`: ConflictStrategy/ConflictRecord/ConflictResult + EventBusStats; **исправлен неверный пример** (`Strategy` вместо `ConflictStrategy`, несуществующий kwarg `metadata=`, ложный вывод `resolved=True`).
   - `27.9_Confidence_Lifecycle.md`: ConfidenceLevel (полосы) + LearningStats (с честной пометкой «прямых потребителей нет»).
3. **hook (1 гэп).** `09.7_Система_хуков.md` — строка про `bsl-user-rules-check.py`; `13.2_Hooks.md` — каталог перегенерирован из `settings.json` (99 → **106** регистраций, дрейф 7).
4. **Code-fix (корень, не симптом).** `scripts/gen_hooks_catalog.py` не экранировал `|` в matcher-ячейках → все multi-matcher строки рвали markdown-таблицу (прежний док чинили руками поверх генератора). Экранирование `\\` → `\|` + 2 регресс-теста; CLAUDE.md синхронизирован (99→106).

## Верификация
- audit: 0/0 · `gen_hooks_catalog --verify-doc`: OK · `lint_ch43_sync`: 1 low (пре-существующий, не наш) · `lint_skills --strict`: 1 error пре-существующий (`1c-debug-hmr` DESC1024).
- pytest `test_gen_hooks_catalog.py`: 13/13; **саботаж-проверка**: снятие экранирования → краснеют ровно 2 новых теста.
- ruff + py_compile: чисто.
- code-verify (read-only субагент) ×2: раунд 1 — FAIL, 6 фактических дефектов (доки врали о поведении кода) → исправлены; раунд 2 — PARTIAL, 1 новый факт («MetadataExtractor питает Neo4j» — неверно) + 3 уточнения → исправлены.
