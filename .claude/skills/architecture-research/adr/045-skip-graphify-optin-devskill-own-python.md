# ADR-045: Graphify — SKIP как зависимость фреймворка; opt-in dev-skill только для собственного Python-кода

**Дата:** 2026-07-04
**Статус:** accepted
**Исследование:** [cache/graphify-codebase-knowledge-graph.md](../cache/graphify-codebase-knowledge-graph.md)
**Родственные:** ADR-012 (SKIP Spec-Kit/BMAD), ADR-014 (ADOPT Context7 opt-in), ADR-015 (ADOPT tdd-guard opt-in)

## Контекст

Вопрос: целесообразно ли внедрить **Graphify** (2026, `safishamsi/Graphify-Labs`, YC S26) — Claude Code
skill, превращающий кодовую базу в queryable knowledge graph (tree-sitter AST по 33 языкам + LLM-экстракция
+ Leiden communities + god-nodes; заявлено 71.5× экономии токенов на запросах). Факты — в cache-файле.

У фреймворка **уже есть** развитая граф- и код-подсистема:
- `src/pdf_framework/graph_store/` — `construction/builder.py` (text→entity graph), `community.py`
  (community detection), `entity_embeddings.py`, `summarizer.py`, `incremental.py`, провайдеры
  Neo4j+NetworkX; GraphRAG-агент; Qdrant `graph_embeddings` (6 694 pts). [own: инвентаризация кода]
- **BSL структурный граф**: `cache/bsl_call_graph.db` (SQLite adjacency — 33k symbols / 80k calls /
  2k modules, dangling-call detector), MCP `bsl-semantic-search` (`bsl_call_graph`, `bsl_impact_analysis`,
  `bsl_dead_code`). [own; memory «SQLite adjacency instead of Neo4j»]
- **Семантический self-index**: `framework_code_v1` (21k+ chunks Python-кода фреймворка, auto-reindex
  on commit) + `framework-search` MCP. [own]
- Token-economy уже адресуется llm-rotation + делегированием + семантическим поиском. [own]

## Решение

**SKIP** внедрение Graphify как встроенной зависимости/подсистемы фреймворка.
**CONDITIONAL opt-in**: допускается точечный dev-time эксперимент — Graphify как локальный Claude Code
skill, наведённый **только на собственный `src/**.py`** фреймворка (self-navigation / рефакторинг),
по образцу opt-in-адопций ADR-014/015 — **никогда в продуктовом пути и никогда над 1С-конфигурациями**.

### Обоснование

1. **Промах по ядру домена [own, решающий].** Продукт фреймворка — разработка на **1С/BSL**.
   Tree-sitter Graphify (33 языка: Python/TS/Go/Rust/Java/…) **не содержит грамматики 1С/BSL** → над
   1С-конфигурациями (где стоимость токенов и потребность в структуре максимальны) Graphify даёт ~ноль.
   Здесь уже есть лучшее покрытие: `bsl_call_graph.db` (структура) + `bsl-semantic-search` (семантика).
2. **Тяжёлое дублирование [own].** graph_store (construction + community + centrality-совместимый
   traversal + summarizer) + GraphRAG + `graph_embeddings` уже покрывают entity/community/граф-слой.
   Graphify = второй граф-стор с той же функцией → нарушает линию фреймворка на устранение избыточности
   (ср. дроп experience/conversation-коллекций; «SQLite adjacency вместо Neo4j»).
3. **Параллельная система, не интеграция [own].** Graphify — самостоятельный skill/CLI со своим граф-
   хранилищем; не подключается к Qdrant/памяти/хукам фреймворка. Внедрение = поддержка второй граф-системы
   и рассинхрон источников истины.
4. **Реальный, но узкий gap [own].** Единственное, чего у фреймворка нет — **структурный AST call-graph
   собственного Python-кода** (`framework_code_v1` семантичен, не структурен; graph_store — про
   документные сущности, не про AST кода). god-nodes/communities над `src/` могли бы помочь
   self-рефакторингу. Это dev-удобство, не продуктовая потребность → отсюда opt-in-условие, не адопция.
5. **Зрелость/lock-in [web/own].** Релиз апрель-2026, VC-backed, быстро меняется; семантический слой —
   LLM-экстракция (стоимость). Цифра 71.5× «реальна в контексте», независимый тест — 7–8%; выигрыш
   сценарно-зависим. Совпадает с SKIP-критериями ADR-012 (внешние тулы, конфликтующие/дублирующие
   hook+Qdrant-архитектуру).

## Последствия

### Положительные
- Ноль нового maintenance-груза и второго графа-истины; фокус остаётся на 1С-ядре.
- Дверь для дешёвого dev-эксперимента над собственным Python оставлена открытой (opt-in, обратимо).

### Отрицательные / риски
- Если у фреймворка вырастет собственная многоязычная (не-1С) кодовая база — решение стоит пересмотреть.
- Отказ от «модного» инструмента с большим сообществом; при смене стратегии — вернуться к вопросу.

## Альтернативы (рассмотрены, отклонены)
- **Полное встраивание Graphify в indexing/GraphRAG** — отклонено: дублирует graph_store, не покрывает
  1С, второй граф-стор.
- **Заменить `bsl_call_graph.db` на Graphify** — отклонено: Graphify не парсит BSL.
- **Neo4j GraphRAG Python / MsGraphRAG** — тот же класс, те же возражения (1С не покрыт, дубль graph_store).

## Связанные файлы
- Затрагивает (при пересмотре): `src/pdf_framework/graph_store/`, `scripts/build_call_graph.py`,
  `framework_code_v1` pipeline. Сейчас — правок кода НЕТ (решение = не внедрять).
