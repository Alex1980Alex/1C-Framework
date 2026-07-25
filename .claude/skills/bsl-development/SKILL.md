---
name: bsl-development
description: "BSL Development — разработка на 1С:Предприятие. ИСПОЛЬЗУЙ когда пишешь BSL код, модули 1С, процедуры/функции, обработки проведения, формы. Триггеры: 'BSL', '1С код', 'модуль 1С', 'процедура BSL', 'конфигурация 1С', 'справочник', 'документ 1С', 'регистр', 'модуль объекта', 'модуль формы', 'общий модуль', 'обработка проведения', 'ПередЗаписью'. НЕ для запросов к данным (→ 1c-mcp-crud), НЕ для документации 1С (→ 1c-doc-research)."
---

# BSL Development — разработка на 1С:Предприятие

## Обзор

Скилл для работы с кодом на языке BSL (Built-in Scripting Language)
платформы 1С:Предприятие 8.3.27.

**Источник миграции:** `D:\1C-Enterprise_Framework` → `D:\1С-Framework`
**Фаза:** 44 (Infrastructure)

## Триггеры

- 'BSL', '1С код', 'модуль 1С', 'процедура BSL'
- 'конфигурация 1С', 'справочник', 'документ 1С', 'регистр'
- 'модуль объекта', 'модуль формы', 'общий модуль'
- 'отладка BSL', 'debug 1С', 'semantic search BSL'

## Доступные MCP-инструменты

| Инструмент | MCP сервер | Назначение |
|-----------|-----------|-----------|
| **Reasoning (ОБЯЗАТЕЛЬНЫЙ)** | `mcp-reasoner` | 3 BSL-стратегии: архитектура, документы, подсистемы |
| Семантический поиск | `bsl-semantic-search` | Поиск похожего кода (3,908+ модулей) |
| Автодокументация | `auto-documenter` | generate_documentation, autoreview, autotestplan |
| Отладка (OneScript, статика) | `bsl-debugger` | breakpoints, step, variables, evaluate — без live 1С |
| Live отладка (RDBG, Scenario B) | `1c-debug` | post-BP-fire handshake против running 1С: debug_set_breakpoint, debug_variables, debug_evaluate, debug_step (см. [16.7](../../../docs/framework%20documentation/3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.7_Autonomous_Debug_Workflow.md)) |
| API платформы | `bsl-platform-context` | Типы, методы, свойства 1С:8.3.27 |
| AST-анализ | `ast-grep-mcp` | Tree-sitter парсинг BSL |
| LSP | `serena` | Symbol extraction, рефакторинг |

## Workflow

### 0. Архитектурный анализ (ОБЯЗАТЕЛЬНЫЙ для 1С кода)

Перед написанием/рефакторингом BSL кода — выбрать стратегию анализа:

| Контекст задачи | Стратегия | Глубина |
|----------------|-----------|---------|
| Архитектура модулей, SOLID, God Object | `bsl_architecture` | 8 уровней |
| Проведение, движения, регистры, производительность | `bsl_document_patterns` | 10 уровней |
| Подсистемы, RBAC, RLS, интеграция, зависимости | `bsl_subsystem_analysis` | 12 уровней |

```
mcp__reasoner__processThought(
  thought="Анализ архитектуры модуля ОбработкаДокументов",
  thoughtNumber=1,
  totalThoughts=5,
  nextThoughtNeeded=true,
  strategyType="bsl_architecture"
)
```


### 1. Анализ кода
```
mcp__ast-grep-mcp__ast_grep(pattern="Процедура $NAME($$$PARAMS)", language="bsl")
```
или
```
mcp__serena__find_symbol(name_path="...", relative_path="...")
```

### 2. Поиск похожего кода
```
mcp__bsl-semantic-search__search(query="обработка проведения документа", limit=5)
```

### 3. Контекст платформы 1С
```
mcp__bsl-platform-context__get_method_info(method_name="СправочникМенеджер.НайтиПоКоду")
```

### 4. Документация
```
mcp__auto-documenter__generate_documentation(file_path="...")
```

### 5. Code Review
```
mcp__auto-documenter__autoreview(file_path="...")
```

### 6. Отладка (при необходимости)
```
mcp__bsl-debugger__set_breakpoint(file="...", line=...)
mcp__bsl-debugger__step_over()
mcp__bsl-debugger__get_variables()
```

## Стандарты кода 1С

При написании BSL кода следовать стандартам:
- Имена процедур/функций: CamelCase
- Имена переменных: camelCase
- Отступы: табуляция
- Максимальная длина строки: 120 символов

## Стоячие правила пользователя (ОБЯЗАТЕЛЬНЫЙ чеклист перед записью BSL)

Свод повторявшихся код-ревью замечаний заказчика. Прогоняй по списку КАЖДУЮ правку ДО записи.
Помеченные 🤖 дополнительно ловит хук `bsl-user-rules-check` (advisory в тот же ход) - но хук
проверяет только машинно-выражимое, чеклист первичен. Новое замечание заказчика → СРАЗУ строка
сюда + детект в [`shared/bsl_user_rules.py`](../../hooks/shared/bsl_user_rules.py) + тест
([`test_bsl_user_rules.py`](../../../tests/unit/test_bsl_user_rules.py)) - память вторична.

**Чтение данных и API:**
1. Реквизит/ТЧ по ссылке - через БСП `ОбщегоНазначения.ЗначениеРеквизитаОбъекта / ЗначенияРеквизитовОбъекта`
   (ТЧ: `...("ИмяТЧ").Выгрузить()`), НЕ `Ссылка.Реквизит` (грузит весь объект), НЕ самописный запрос за
   данными одного объекта - сперва поискать идиому в том же модуле [[feedback-1c-read-attribute-bsp]]
2. 🤖 Устаревшие глобальные → БСП: `СообщитьПользователю`→`ОбщегоНазначения.СообщитьПользователю`;
   `Подробное/КраткоеПредставлениеОшибки`→`ОбработкаОшибок.*` [[feedback-1c-bsp-deprecated-globals]]
3. 🤖 Ссылки на элементы справочников - предопределённые (v8std #std697), НЕ `НайтиПоКоду/Наименованию`
   с литералом; ⚠ DontAutoUpdate = связка имя↔элемент base-specific; фикс-фильтр динсписка -
   `ЗНАЧЕНИЕ()` прямо в тексте запроса [[feedback-1c-predefined-not-hardcode-codes]]
4. 🤖 `ТекущаяДатаСеанса()`, не `ТекущаяДата()` (серверный код, БСП-стандарт)
5. «Метод не обнаружен» на сервере = обычно нет `Экспорт`, а не устаревший деплой
   [[feedback-1c-method-not-found-means-no-export]]

**Строки и сообщения:**
6. 🤖 Сборка строки из 2+ частей - `СтрШаблон("%1.%2", А, Б)`, не конкатенация `+`
   (одиночный тривиальный `+` терпим) [[feedback-1c-strshablon-not-concat]]

**Запросы:**
7. 🤖 НЕ оборачивать запрос вложенным подзапросом в `ИЗ` («так никогда не делай») - временные таблицы:
   `ПОМЕСТИТЬ ВТ_X` + второй запрос пакета [[feedback-1c-no-subquery-wrap-use-temp-tables]]
8. 🤖 Строки неограниченной длины (Адрес/Комментарий/Текст) нельзя в `СГРУППИРОВАТЬ ПО` и
   `МАКСИМУМ/МИНИМУМ` - двухэтапно: группировка по ссылочным ключам в ВТ → джойн деталей
   [[feedback-1c-group-by-unlimited-string]]
9. `ВыполнитьПакет()` индексирует и `ПОМЕСТИТЬ`-запросы; rename поля не должен коллидировать
   с алиасом джойна [[feedback-1c-vypolnitpaket-indexes-placeholders]] [[feedback-1c-rename-field-collides-join-alias]]
10. В тексте запроса, склеиваемом в исходнике, помнить про `|` (маркер продолжения строки BSL -
    при склейке попадает в текст запроса и ломает разбор)

**Оформление и процесс:**
11. 🤖 Каждый блок нового/изменённого кода - маркеры `// <JIRA> Начало` / `// <JIRA> Конец`
    (однострочная вставка - `// <JIRA>` в конце строки)
12. Док-комментарий нового метода СРАЗУ (`Параметры:` / `Возвращаемое значение:`); для Структуры -
    `Структура:` с ДВОЕТОЧИЕМ + `* Поле - Тип - описание` (иначе EDT-предупреждение)
    [[feedback-1c-edt-struct-return-doctype]]
13. Правки `.bsl` - батчем ОДНИМ вызовом (гонка с автоформатом); точечная правка - минимальный дифф
    [[feedback-bsl-batch-edit-format-hook]] [[feedback-bsl-targeted-edit-minimal-diff]]
14. Правка СУЩЕСТВУЮЩЕГО экспортного метода - сначала `bsl_impact_analysis` (кто сломается)
15. Не городить избыточные защиты, которые платформа уже гарантирует (`СокрЛП(Неопределено)`="" и т.п.);
    рекомендации ревьюеров проверять live-вызовом [[reference-1c-sokrlp-undefined-returns-empty]]
16. РС, подчинённый регистратору: периодичность записей = периодичность регистратора (Month-guard)
    [[feedback-1c-recorder-subordinate-periodicity]]

**Автоформат:** `python scripts/bsl_lint.py <module.bsl> --format` (bsl-ls `--format`, in-place, идемпотентно) — приводит отступы/пробелы к стандарту перед коммитом/диагностикой.

**Расширенный свод BSL-стандартов** (канонические области модулей, зарезервированные имена свойств форм, БСП-first, анти-паттерны async/транзакций, ошибки ручного metadata-XML, стратегия логирования) — внешний community-набор `[web]`, закеширован: [`external-bsl-ai-coding-rules-comol.md`](../1c-doc-research/cache/external-bsl-ai-coding-rules-comol.md).

## Примеры использования

### Поиск процедур проведения
```bsl
// Запрос к bsl-semantic-search
"обработка проведения документа движения регистры"
```

### Генерация документации модуля
```
Использовать auto-documenter с профилем #7 (lazy-mcp)
```

## Конфигурация (Phase 8.12.8 production switchover, 2026-04-30)

- **MCP профиль:** `.mcp/bsl.json`
- **Embeddings:** Qwen3-Embedding-8B (4096d, через Ollama `qwen3-embedding`)
- **Qdrant collection:** `bsl_code_v4_late` (Qwen3 + Late Chunking pooling, +26% recall vs E5 baseline на 50q expanded pilot)
- **Query instruction:** default web-retrieval template из HF model card (BSL-specific варианты дали -100%, см. roadmap §21.10 H1 ablation)
- **SQLite fallback:** `cache/docs-mcp/hybrid_search.db` (FTS5, 12983 docs) — когда Qdrant недоступен
- **Legacy collections:** `bsl_code_v3` (E5 1024d, drop pending Phase 8.11.3), `bsl_code_v2` (nomic 768d, deprecated), `bsl_code_v4` (Qwen3+std 4096d, research-baseline only — std pooling даёт -64% recall vs Late)

## Индексация BSL — варианты и decision flowchart

> **Полная справка:** [chapter 31.6 Варианты индексации и типичные ошибки](../../../docs/framework%20documentation/2_КОНТЕКСТ/2.8_QWEN3_RETRIEVAL_PRODUCTION/31.6_Варианты_индексации_и_типичные_ошибки.md)

### Decision flowchart — какой backend выбрать

```
Что делаешь?
├── Изменил 1-N .bsl файлов в существующем проекте (commit/PR)
│   → INCREMENTAL: --paths <files> --embedder qwen3-tei --batch-size 32
│     TEI остаётся up; ~секунды; std pooling (mixed quality acceptable)
│
├── Добавил новый 1С-проект целиком (или раз в N недель re-alignment)
│   → FULL: --project <root> --embedder qwen3-st --pooling-mode late-chunking
│           --batch-size 50 --buffer-size 512 (БЕЗ --enable-fa2)
│     ОБЯЗАТЕЛЬНО `docker stop pdf-rag-tei` ПЕРЕД! ~60-90 мин на 2000+ файлов
│
└── BREAKING change (новая модель / payload schema)
    → FULL + --recreate (дропает ВСЮ коллекцию всех проектов!)
```

### Матрица backend × pooling

| Backend | Pooling | Late Chunking | GPU | Скорость | Когда |
|---|---|---|---|---|---|
| `qwen3-st` | last_token | **✓ да** | 16 GB FP16 | медленная (warmup ~30c) | **Full reindex** в `bsl_code_v4_late` |
| `qwen3-tei` | last_token (TEI) | ✗ нет | 16 GB (постоянно) | быстрая | **Incremental** + online queries |
| `e5` | mean | ✗ нет | 0 (CPU OK) | средняя | legacy, DEPRECATED |

**Ключевое:** `qwen3-st late-chunking` и `qwen3-tei` дают **разные** embedding-векторы. На BSL benchmark разница = **+64% recall@10** в пользу Late.

### Auto-reindex BSL при git commit

При активном `git config core.hooksPath scripts/git_hooks` автоматически запускается incremental reindex `bsl_code_v4_late` для изменённых `.bsl` файлов (через `qwen3-tei`, std pooling). Auto-detect project root через walk до `configuration/<X>/`. Delete-stale: удаляет chunks с тем же `module_path` но другим `chunk_id` (ловит удалённые/переименованные функции). Лог: `cache/bsl_reindex.log`.

### Типичные ошибки (помни всегда!)

1. **`qwen3-tei` для FULL reindex** → mixed-pooling коллекция, gradual recall drop. → Для `--project` ВСЕГДА `qwen3-st --pooling-mode late-chunking`.
2. **`qwen3-st` БЕЗ остановки TEI** → CUDA OOM (две копии 8B FP16 = 32 GB на 24GB GPU). → `docker stop pdf-rag-tei` ПЕРЕД, потом `start`.
3. **`--enable-fa2` на `ИБTransportManagementDevelop`** → OOM на XXL chunks. → `--batch-size 50 --buffer-size 512` БЕЗ `--enable-fa2`. Memory `feedback_bsl_reindex_fallback`.
4. **Не делать `build_call_graph.py` ПЕРЕД reindex** → пустые `calls`/`caller_count` в payload. → `python scripts/build_call_graph.py --project <root> --db cache/bsl_call_graph.db` (16 сек) ПЕРЕД.
5. **Matryoshka truncation на BSL** → -12% до -20% recall (Cyrillic identifiers не сжимаются). → SQ int8 — да, MRL — нет. Memory `feedback_mrl_content_matters`.
6. **`--recreate` для добавления проекта** → дроп всей коллекции (все конфигурации). → Без `--recreate`, новые chunks доupsert'ятся.
7. **`qwen3-st` БЕЗ `--pooling-mode late-chunking`** → std pooling (default), но запишет в `_late` коллекцию. → Для `bsl_code_v4_late` ОБЯЗАТЕЛЬНО `--pooling-mode late-chunking`.

### Pre-flight checklist (перед любым reindex)

```bash
# 1. TEI healthy (для qwen3-tei или верификация перед stop)
curl -s http://localhost:8080/info | python -m json.tool | head -3

# 2. Qdrant healthy
curl -s http://localhost:6333/collections/bsl_code_v4_late | grep points_count

# 3. GPU свободен (для qwen3-st use case)
nvidia-smi --query-gpu=memory.used,memory.free --format=csv | head -2

# 4. Call graph актуален (для context-enrichment)
ls -lh cache/bsl_call_graph.db
```

## Зависимости

- Фаза 45: BSL Semantic Search + SonarQube
- Фаза 46: MCP 1C Integration
- Фаза 47: Auto-Documenter
- Фаза 48: BSL Debugger
- Фаза 52: Serena LSP Integration
- Фаза 57: MCP Reasoner (3 BSL-стратегии)
