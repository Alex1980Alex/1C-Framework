# Roadmap: Vibe Graphing — Visual Workflow Builder

**Дата:** 2026-03-27 | **Статус:** PLANNED | **Версия:** 1.0.0

**Цель:** Реализовать методологию **Vibe Graphing** (MASFactory, arXiv 2603.06007): преобразование описания задачи на естественном языке в визуально редактируемый граф workflow с компиляцией в исполняемый LangGraph pipeline. Два домена: задачи 1С (60+ MCP tools) и универсальные RAG/Research задачи (14 MCP tools).

**Код:** `src/pdf_framework/vibe_graph/`

---

## Текущая архитектура

```
┌───────────────────────────────────────────────────────────────────┐
│                  PDF Vector & Graph Framework                      │
├───────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│  │ Streamlit UI│  │ FastAPI API │  │ MCP Server  │  │LangGraph│ │
│  │             │  │             │  │ (14 tools)  │  │ Agents  │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └────┬────┘ │
│         └────────────────┴────────────────┴───────────────┘      │
│                                │                                   │
│           ┌────────────────────┼────────────────────┐             │
│    ┌──────┴──────┐      ┌──────┴──────┐      ┌──────┴──────┐    │
│    │  1С MCP     │      │  RAG Tools  │      │ Graph Store │    │
│    │ (60+ tools) │      │ (14 tools)  │      │ Neo4j + NX  │    │
│    └─────────────┘      └─────────────┘      └─────────────┘    │
│                                                                    │
│  Agents: Self-RAG (7 nodes) | Plan-Execute (4 nodes)              │
│          Research v2 | Analytical | Multi-Agent Orchestrator       │
│                                                                    │
│  Skills: analyze-1c-task-v2 (5 фаз) | implement-1c-task (8 этапов)│
└───────────────────────────────────────────────────────────────────┘
```

---

## Gap Analysis

| Компонент | Текущее | Требуется | Gap |
|-----------|---------|-----------|-----|
| Workflow Schema | Нет | WorkflowSpec, WorkflowNode, WorkflowEdge (Pydantic) | **Критический** |
| Node Registry | Нет | Типизированный реестр 60+ node-типов | **Критический** |
| Tool Adapters | MCP tools без типизации | Pydantic-адаптеры с input/output schema | **Высокий** |
| Workflow Compiler | Нет | WorkflowSpec → LangGraph StateGraph | **Критический** |
| Intent Compiler | plan_execute (частично) | NL → WorkflowSpec с валидацией | **Высокий** |
| Templates | SKILL.md (текстовые) | Библиотека параметризованных YAML-шаблонов | **Средний** |
| Visual Editor | Нет | Streamlit graph canvas с drag & drop | **Высокий** |
| Execution Engine | LangGraph runtime | Executor + events + tracing + checkpointing | **Высокий** |
| Adaptive Execution | plan_execute/replanner | Runtime-адаптация + quality gates | **Средний** |
| External API | MCP server (14 tools) | +4 vibe_* MCP tools + REST endpoints | **Средний** |

---

## Диаграмма зависимостей

```
Iter 1 (Schema) ─────┬──→ Iter 3 (Compiler) ──→ Iter 8 (Executor) ──→ Iter 9 (Adaptive)
                      │         │                                              │
Iter 2 (Adapters) ────┘         │                                              └──→ Iter 10 (MCP/API)
                                │
Iter 4 (Intent) ────────────────┤
                                │
                                ├──→ Iter 5 (1C Templates) ──┐
                                │                              ├──→ Iter 7 (UI)
                                └──→ Iter 6 (Universal) ──────┘
```

**Критический путь:** 1 → 2 → 3 → 8 → 9 → 10

---

## Итерации

### Iteration 1: WorkflowSpec Schema & Node Registry

**Цель:** Pydantic-модели для декларативного описания workflow-графов и реестр всех доступных node-типов.

**Зависимости:** Нет

| Task | Deliverable | Effort |
|------|-------------|--------|
| T1.1 | `WorkflowSpec` Pydantic модель: name, description, params, nodes, edges, metadata | 2h |
| T1.2 | `WorkflowNode` модель: id, name, type (enum), tool_name, agent_type, args, input/output schema, on_error | 2h |
| T1.3 | `WorkflowEdge` модель: source, target, condition, data_mapping | 1h |
| T1.4 | `RetryPolicy` модель: max_retries, strategy (fix_and_retry/skip/notify_user), fallback_node | 1h |
| T1.5 | `NodeType` enum: tool, llm_generate, parallel_group, sequential_chain, mandatory_chain, human_action, subgraph | 0.5h |
| T1.6 | `NodeRegistry` класс: register(), get(), list_by_category(), list_by_domain() | 2h |
| T1.7 | Unit tests для schemas и registry | 1.5h |

**Архитектура:**

```python
class NodeType(str, Enum):
    TOOL = "tool"                        # Вызов MCP tool
    LLM_GENERATE = "llm_generate"        # LLM generation (Opus/Sonnet)
    PARALLEL_GROUP = "parallel_group"    # asyncio.gather
    SEQUENTIAL_CHAIN = "sequential_chain"  # Линейная цепочка
    MANDATORY_CHAIN = "mandatory_chain"  # Нерушимая цепочка (1С write cycle)
    HUMAN_ACTION = "human_action"        # LangGraph interrupt
    SUBGRAPH = "subgraph"                # Вложенный граф

# NodeRegistry categories
CATEGORIES = ["recon", "validation", "modification",
              "verification", "testing", "documentation", "composite"]
```

**Файлы:**
- `src/pdf_framework/vibe_graph/__init__.py` — публичный API (~20 строк)
- `src/pdf_framework/vibe_graph/schemas.py` — все Pydantic модели (~150 строк)
- `src/pdf_framework/vibe_graph/node_registry.py` — NodeRegistry + категории (~200 строк)
- `tests/vibe_graph/test_schemas.py` (~100 строк)
- `tests/vibe_graph/test_registry.py` (~80 строк)

**Effort:** 10h

---

### Iteration 2: MCP Tool Adapters (1С + Universal)

**Цель:** Типизированные обёртки для всех 60+ MCP tools, преобразующие их в узлы графа с Pydantic input/output.

**Зависимости:** Iteration 1

| Task | Deliverable | Effort |
|------|-------------|--------|
| T2.1 | `BaseToolAdapter` абстрактный класс: async callable, input/output model, error handling | 1.5h |
| T2.2 | 1С Data adapters (8): execute_query, execute_code, get_metadata, get_event_log, get_object_by_link, get_link_of_object, find_references_to_object, get_access_rights | 2h |
| T2.3 | EDT adapters (15): list_projects, list_modules, get_module_structure, read/write_method_source, validate_query, get_project_errors, find_references, get_metadata_details, search_in_code, add_metadata_attribute, rename_metadata_object, get_content_assist, update_database, get_method_call_hierarchy | 3h |
| T2.4 | BSL Search adapters (6): bsl_search, bsl_hybrid_search, bsl_call_graph, bsl_impact_analysis, bsl_object_info, bsl_coding_context | 1.5h |
| T2.5 | BSL Debug adapters (4): bsl_analyze, bsl_execute, bsl_debug compound (start+step+variables) | 1h |
| T2.6 | RAG adapters (6): search_documents, ask_question, graph_query, analyze, research, plan_execute | 1.5h |
| T2.7 | Docs adapters (3): generate_documentation, autoreview, autotestplan | 0.5h |
| T2.8 | Регистрация всех адаптеров в NodeRegistry | 1h |
| T2.9 | Unit tests для адаптеров | 2h |

**Архитектура:**

```python
class BaseToolAdapter(ABC, Generic[I, O]):
    name: str
    category: str
    domain: str  # "1c" | "rag" | "universal"
    input_model: Type[I]
    output_model: Type[O]

    @abstractmethod
    async def execute(self, input: I) -> O: ...

    async def __call__(self, **kwargs) -> O:
        validated = self.input_model(**kwargs)
        return await self.execute(validated)

# Пример:
class ExecuteQueryAdapter(BaseToolAdapter[ExecuteQueryInput, ExecuteQueryOutput]):
    name = "execute_query"
    category = "modification"
    domain = "1c"
```

**Файлы:**
- `src/pdf_framework/vibe_graph/adapters/__init__.py` — экспорт (~30 строк)
- `src/pdf_framework/vibe_graph/adapters/base.py` — BaseToolAdapter (~80 строк)
- `src/pdf_framework/vibe_graph/adapters/onec_data.py` — 8 adapters (~200 строк)
- `src/pdf_framework/vibe_graph/adapters/edt.py` — 15 adapters (~400 строк)
- `src/pdf_framework/vibe_graph/adapters/bsl_search.py` — 6 adapters (~180 строк)
- `src/pdf_framework/vibe_graph/adapters/bsl_debug.py` — 4 adapters (~120 строк)
- `src/pdf_framework/vibe_graph/adapters/rag.py` — 6 adapters (~180 строк)
- `src/pdf_framework/vibe_graph/adapters/docs.py` — 3 adapters (~80 строк)
- `tests/vibe_graph/test_adapters.py` (~250 строк)

**Effort:** 14h

---

### Iteration 3: Workflow Compiler (WorkflowSpec → LangGraph StateGraph)

**Цель:** Компилятор, преобразующий декларативный WorkflowSpec в исполняемый LangGraph StateGraph с поддержкой всех NodeType.

**Зависимости:** Iteration 1, Iteration 2

| Task | Deliverable | Effort |
|------|-------------|--------|
| T3.1 | `WorkflowState` TypedDict: node_results, current_node, errors, iteration_count, human_responses | 1h |
| T3.2 | `WorkflowCompiler.compile(spec)` → CompiledStateGraph | 3h |
| T3.3 | Обработка node типов: tool, llm_generate, parallel_group, sequential_chain, mandatory_chain | 2h |
| T3.4 | Human action nodes: LangGraph interrupt + resume | 1.5h |
| T3.5 | Subgraph nodes: рекурсивная компиляция | 1h |
| T3.6 | Conditional edges: WorkflowEdge.condition → Python callable | 1.5h |
| T3.7 | Variable interpolation: `${node_name.field}` → подстановка из node_results | 1.5h |
| T3.8 | Mandatory chains enforcement: проверка целостности WRITE CYCLE и SQL CYCLE | 1.5h |
| T3.9 | Checkpointing: SqliteSaver для resume | 1h |
| T3.10 | Error handling: RetryPolicy → conditional edge на retry/fallback | 1.5h |
| T3.11 | Unit tests для компилятора | 2h |

**Архитектура:**

```python
class WorkflowState(TypedDict):
    node_results: dict[str, Any]        # Результаты по node_id
    current_node: str | None
    errors: list[dict]
    iteration_count: dict[str, int]     # Счётчик итераций для циклов
    human_responses: dict[str, Any]     # Ответы от human_action

# Mandatory chains (1С) — компилятор проверяет что не разорваны
MANDATORY_CHAINS = {
    "write_cycle": ["write_module_source", "get_project_errors", "read_method_source"],
    "sql_cycle": ["validate_query", "execute_query"]
}

class WorkflowCompiler:
    def compile(self, spec: WorkflowSpec) -> CompiledStateGraph:
        self._validate_spec(spec)           # mandatory chains + tool existence
        graph = StateGraph(WorkflowState)
        for node_id, node in spec.nodes.items():
            graph.add_node(node_id, self._create_handler(node))
        for edge in spec.edges:
            if edge.condition:
                graph.add_conditional_edges(edge.source, self._create_condition(edge))
            else:
                graph.add_edge(edge.source, edge.target)
        return graph.compile(checkpointer=SqliteSaver(...))
```

**Файлы:**
- `src/pdf_framework/vibe_graph/state.py` — WorkflowState TypedDict (~80 строк)
- `src/pdf_framework/vibe_graph/compiler.py` — WorkflowCompiler + валидация (~350 строк)
- `src/pdf_framework/vibe_graph/interpolation.py` — Variable interpolation `${node.field}` (~60 строк)
- `tests/vibe_graph/test_compiler.py` (~200 строк)

**Effort:** 17h

---

### Iteration 4: Intent Compiler (NL → WorkflowSpec)

**Цель:** LLM-компилятор: описание задачи на естественном языке → валидный WorkflowSpec.

**Зависимости:** Iteration 1, Iteration 2

| Task | Deliverable | Effort |
|------|-------------|--------|
| T4.1 | Системный промпт `intent_system.md`: каталог узлов, правила, mandatory chains | 1.5h |
| T4.2 | Примеры NL→WorkflowSpec (5-7 пар: 1С + universal) | 1h |
| T4.3 | `IntentCompiler.compile(intent) → WorkflowSpec` с structured output | 2h |
| T4.4 | Domain detection: 1С vs RAG vs universal (по ключевым словам) | 1h |
| T4.5 | Валидация: tool_name exists, mandatory chains, no infinite loops | 1.5h |
| T4.6 | Итеративное уточнение: max 3 итерации при failed валидации | 1h |
| T4.7 | Unit tests | 1.5h |

**Архитектура:**

```python
class IntentCompiler:
    def __init__(self, registry: NodeRegistry, llm: ChatAnthropic):
        self.registry = registry
        self.llm = llm

    async def compile(self, intent: str, domain: str | None = None) -> WorkflowSpec:
        detected_domain = domain or self._detect_domain(intent)
        available_nodes = self.registry.list_by_domain(detected_domain)

        for iteration in range(3):
            spec_json = await self._generate_spec(intent, available_nodes)
            errors = self._validate_spec(spec_json)
            if not errors:
                return WorkflowSpec(**spec_json)
            intent = self._add_validation_feedback(intent, errors)

        raise IntentCompilationError("Failed after 3 iterations")

    def _detect_domain(self, intent: str) -> str:
        onec_kw = ["конфигурация", "документ 1С", "регистр", "СКД",
                    "проведение", "EDT", "BSL", "реквизит", "форма 1С"]
        return "1c" if any(kw.lower() in intent.lower() for kw in onec_kw) else "universal"
```

**Файлы:**
- `src/pdf_framework/vibe_graph/intent_compiler.py` — IntentCompiler (~300 строк)
- `src/pdf_framework/vibe_graph/prompts/intent_system.md` — системный промпт (~150 строк)
- `src/pdf_framework/vibe_graph/prompts/examples/` — 5-7 JSON примеров (~50-80 строк каждый)
- `tests/vibe_graph/test_intent_compiler.py` (~150 строк)

**Effort:** 10h

---

### Iteration 5: 1С Task Templates

**Цель:** Библиотека параметризованных YAML-шаблонов для типовых задач 1С-разработки.

**Зависимости:** Iteration 3, Iteration 4

| Task | Deliverable | Effort |
|------|-------------|--------|
| T5.1 | `new_attribute.yaml` — добавление реквизита: get_metadata → add_metadata_attribute → write_module_source → get_project_errors → update_database | 1h |
| T5.2 | `posting_control.yaml` — контроль при проведении: get_metadata → bsl_hybrid_search → bsl_coding_context → LLM:SQL → validate → execute → LLM:BSL → write_cycle → verify → test | 1.5h |
| T5.3 | `new_report.yaml` — новый отчёт (СКД): get_metadata → LLM:SQL → validate_query → execute_query → write_module_source → get_project_errors | 1h |
| T5.4 | `data_migration.yaml` — миграция данных: execute_query(source) → LLM:transform → execute_code(write) → execute_query(verify) | 1h |
| T5.5 | `refactoring.yaml` — рефакторинг: bsl_call_graph → bsl_impact_analysis → read_method → LLM:refactor → write_cycle → find_references → test | 1h |
| T5.6 | `full_task.yaml` — полный цикл analyze (5 фаз) + implement (8 этапов) как единый параметризованный граф | 1.5h |
| T5.7 | `bug_fix.yaml` — исправление бага: bsl_hybrid_search → read_method → bsl_call_graph → LLM:fix → write_cycle → test | 1h |
| T5.8 | `TemplateLoader`: загрузка YAML + параметризация `${var}` + валидация | 1.5h |
| T5.9 | Unit tests | 1.5h |

**Архитектура (пример шаблона):**

```yaml
# posting_control.yaml
name: posting_control
description: Контроль при проведении документа
domain: 1c
params:
  document:
    type: string
    description: Имя документа (напр. РеализацияТоваровУслуг)
    required: true
  register:
    type: string
    description: Регистр для проверки остатков
    required: true
  task_number:
    type: string
    description: Номер задачи (напр. GKSTCPLK-2300)
    required: true

nodes:
  recon:
    type: parallel_group
    nodes:
      meta: {tool: get_metadata}
      info: {tool: bsl_object_info, args: {object_name: "${document}"}}
      search: {tool: bsl_hybrid_search, args: {query: "контроль проведение ${document}"}}
      context: {tool: bsl_coding_context, args: {object_name: "${document}"}}

  build_sql:
    type: llm_generate
    prompt: "SQL запрос остатков из ${register}. Аналоги: ${recon.search.results}"

  validate_sql:
    type: mandatory_chain  # SQL CYCLE — нельзя разорвать
    nodes:
      syntax: {tool: validate_query, args: {queryText: "${build_sql.output}"}}
      test: {tool: execute_query, args: {query: "${build_sql.output}", limit: 5}}
    on_error: {goto: build_sql, max_retries: 3}

  generate_code:
    type: llm_generate
    prompt: "BSL процедура. Стиль: ${recon.context.style_prompt}. SQL: ${build_sql.output}"

  write_cycle:
    type: mandatory_chain  # WRITE CYCLE — нельзя разорвать
    nodes:
      write: {tool: write_module_source, args: {source: "${generate_code.output}"}}
      check: {tool: get_project_errors, args: {severity: "ERROR"}}
      verify: {tool: read_method_source}
    on_error: {goto: generate_code, max_retries: 3}

  verify:
    type: parallel_group
    nodes:
      refs: {tool: find_references, args: {objectFqn: "Document.${document}"}}
      impact: {tool: bsl_impact_analysis, args: {symbol_name: "ОбработкаПроведения"}}
      errors: {tool: get_project_errors}

  test:
    type: sequential_chain
    nodes:
      find_data: {tool: execute_query, args: {query: "ВЫБРАТЬ ПЕРВЫЕ 1 ..."}}
      setup: {tool: execute_code, args: {code: "..."}}
      human: {type: human_action, message: "Проведите документ в 1С, скажите 'готово'"}
      check: {tool: execute_query, args: {query: "..."}}
      cleanup: {tool: execute_code}

edges:
  - recon → build_sql
  - build_sql → validate_sql
  - validate_sql → generate_code
  - recon → generate_code
  - generate_code → write_cycle
  - write_cycle → verify
  - verify → test
```

**Файлы:**
- `src/pdf_framework/vibe_graph/templates/onec/new_attribute.yaml` (~60 строк)
- `src/pdf_framework/vibe_graph/templates/onec/posting_control.yaml` (~100 строк)
- `src/pdf_framework/vibe_graph/templates/onec/new_report.yaml` (~70 строк)
- `src/pdf_framework/vibe_graph/templates/onec/data_migration.yaml` (~80 строк)
- `src/pdf_framework/vibe_graph/templates/onec/refactoring.yaml` (~90 строк)
- `src/pdf_framework/vibe_graph/templates/onec/full_task.yaml` (~150 строк)
- `src/pdf_framework/vibe_graph/templates/onec/bug_fix.yaml` (~80 строк)
- `src/pdf_framework/vibe_graph/templates/loader.py` — TemplateLoader (~120 строк)
- `tests/vibe_graph/test_templates_1c.py` (~150 строк)

**Effort:** 11h

---

### Iteration 6: Universal Templates (RAG/Research/Analytical)

**Цель:** Шаблонные графы для универсальных задач фреймворка (не 1С).

**Зависимости:** Iteration 3, Iteration 4

| Task | Deliverable | Effort |
|------|-------------|--------|
| T6.1 | `rag_pipeline.yaml` — RAG: search → grade → [rewrite\|generate] → hallucination_check → [regenerate\|answer] | 1.5h |
| T6.2 | `research_deep.yaml` — план → search + graph_query + web_search → analyze → verify_coverage → report | 1h |
| T6.3 | `document_analysis.yaml` — index_pdf → search → graph_query → analyze (comparative) → report | 1h |
| T6.4 | `knowledge_graph_build.yaml` — index_pdf → entity_extraction → graph_build → community_detection → summarize | 1h |
| T6.5 | `multi_doc_comparison.yaml` — [index_pdf × N] → search per doc → analytical (comparative) → table | 1h |
| T6.6 | Unit tests | 1h |

**Архитектура (пример):**

```yaml
# rag_pipeline.yaml
name: rag_pipeline
description: RAG pipeline с grading, regeneration и hallucination check
domain: universal
params:
  question: {type: string, required: true}
  collection: {type: string, default: "default"}
  strategy: {type: string, default: "hybrid"}

nodes:
  search:
    type: tool
    tool_name: search_documents
    args: {query: "${question}", collection: "${collection}", strategy: "${strategy}"}

  grade:
    type: llm_generate
    prompt: "Оцени релевантность документов. Score 0-1. Docs: ${search.results}"

  rewrite:
    type: llm_generate
    prompt: "Переформулируй вопрос для лучшего поиска: ${question}"

  generate:
    type: llm_generate
    prompt: "Ответь на вопрос на основе документов. Context: ${search.results}"

  hallucination_check:
    type: llm_generate
    prompt: "Проверь: ответ основан на документах? Hallucination: true/false"

  regenerate:
    type: llm_generate
    prompt: "Перегенерируй строго по документам. No hallucination."

edges:
  - search → grade
  - grade → rewrite          # condition: grade.score < 0.5
  - grade → generate         # condition: grade.score >= 0.5
  - rewrite → search         # loop back
  - generate → hallucination_check
  - hallucination_check → regenerate  # condition: hallucinated
  - hallucination_check → END         # condition: grounded
  - regenerate → hallucination_check  # retry loop (max 2)
```

**Файлы:**
- `src/pdf_framework/vibe_graph/templates/universal/rag_pipeline.yaml` (~80 строк)
- `src/pdf_framework/vibe_graph/templates/universal/research_deep.yaml` (~90 строк)
- `src/pdf_framework/vibe_graph/templates/universal/document_analysis.yaml` (~70 строк)
- `src/pdf_framework/vibe_graph/templates/universal/knowledge_graph_build.yaml` (~80 строк)
- `src/pdf_framework/vibe_graph/templates/universal/multi_doc_comparison.yaml` (~75 строк)
- `tests/vibe_graph/test_templates_universal.py` (~120 строк)

**Effort:** 6.5h

---

### Iteration 7: Visual Editor (Streamlit)

**Цель:** Streamlit-страница с интерактивным графом для создания и редактирования workflow.

**Зависимости:** Iteration 5, Iteration 6

| Task | Deliverable | Effort |
|------|-------------|--------|
| T7.1 | Graph canvas: streamlit-agraph / st-cytoscape для рендеринга directed graph | 2h |
| T7.2 | Node palette: боковая панель с категориями узлов (drag & drop) | 1.5h |
| T7.3 | Node inspector: панель свойств узла (tool_name, args, on_error) | 1.5h |
| T7.4 | Edge inspector: условие перехода, data_mapping | 1h |
| T7.5 | Template picker: выбор шаблона → загрузка в canvas | 1h |
| T7.6 | Parameter form: заполнение `${param}` параметров шаблона | 1h |
| T7.7 | Compile & Run: кнопка → компиляция → запуск → progress overlay | 1.5h |
| T7.8 | Import/Export: загрузка/сохранение WorkflowSpec YAML | 1h |
| T7.9 | Validation panel: ошибки (broken mandatory chains, missing tools) | 1h |
| T7.10 | Integration tests | 1.5h |

**Макет:**

```
┌───────────────────────────────────────────────────────────────────────┐
│  Vibe Graph Editor                                    [Compile] [Run] │
├────────────────┬──────────────────────────────────────────────────────┤
│                │                                                      │
│  NODE PALETTE  │                 GRAPH CANVAS                         │
│                │                                                      │
│  ┌─ Recon ───┐ │   ┌──────────┐     ┌──────────┐     ┌──────────┐  │
│  │ get_meta  │ │   │get_meta  │────▶│validate  │────▶│write_src │  │
│  │ search    │ │   └──────────┘     └──────────┘     └──────────┘  │
│  └───────────┘ │                                           │         │
│                │                                           ▼         │
│  ┌─ Modify ──┐ │                                    ┌──────────┐    │
│  │ write_src │ │                                    │get_errors│    │
│  │ execute   │ │                                    └──────────┘    │
│  └───────────┘ │                                                      │
│                │                                                      │
│  ┌─ Template ┐ │                                                      │
│  │ 1C: 7     │ │                                                      │
│  │ RAG: 5    │ │                                                      │
│  └───────────┘ │                                                      │
├────────────────┴──────────────────────────────────────────────────────┤
│  NODE INSPECTOR                                                       │
│  Node: write_src │ Type: tool │ Tool: write_module_source             │
│  Args: {"module": "${document}.Form", "code": "${llm_code}"}         │
│  On Error: RetryPolicy(max=3, strategy=fix_and_retry)                │
├───────────────────────────────────────────────────────────────────────┤
│  VALIDATION: 0 errors, 0 warnings                              [OK]  │
└───────────────────────────────────────────────────────────────────────┘
```

**Файлы:**
- `src/ui/pages/vibe_graph.py` — главная страница (~400 строк)
- `src/ui/components/graph_editor.py` — canvas, node/edge rendering (~200 строк)
- `src/ui/components/node_palette.py` — палитра с категориями (~100 строк)
- `src/ui/components/node_inspector.py` — панель свойств (~120 строк)
- `src/ui/components/template_picker.py` — выбор шаблонов (~80 строк)
- `src/ui/components/validation_panel.py` — панель валидации (~60 строк)
- `tests/ui/test_vibe_graph_page.py` (~150 строк)

**Effort:** 13h

---

### Iteration 8: Execution Engine & Observability

**Цель:** Движок выполнения графов с real-time трассировкой, визуализацией прогресса и checkpointing.

**Зависимости:** Iteration 3

| Task | Deliverable | Effort |
|------|-------------|--------|
| T8.1 | `WorkflowExecutor`: execute(compiled_graph, params) → WorkflowResult | 2h |
| T8.2 | Event types: node_started, node_completed, node_failed, edge_traversed, human_action_required | 1h |
| T8.3 | Event bus: asyncio.Queue для real-time streaming в UI | 1h |
| T8.4 | Progress tracking: текущий узел, завершённые, ошибки | 1h |
| T8.5 | Checkpointing: SqliteSaver — resume после crash/human_action | 1.5h |
| T8.6 | Timeout per node: configurable (60s MCP, 120s LLM) | 0.5h |
| T8.7 | Cost tracking: TokenTracker per node → суммарная стоимость | 1h |
| T8.8 | Execution log: JSONL со всеми событиями | 1h |
| T8.9 | Integration с OTLP tracing, hook_metrics_db | 1h |
| T8.10 | Execution monitor UI component | 1.5h |
| T8.11 | Unit tests | 1.5h |

**Архитектура:**

```python
@dataclass
class WorkflowEvent:
    event_type: str       # node_started, node_completed, node_failed, ...
    workflow_id: str
    node_id: str | None
    timestamp: datetime
    data: dict            # node output, error, duration_ms, cost

class WorkflowExecutor:
    def __init__(self, checkpointer: SqliteSaver, event_bus: asyncio.Queue):
        self.checkpointer = checkpointer
        self.event_bus = event_bus
        self.timeouts = {"tool": 60, "llm_generate": 120, "human_action": 600}

    async def execute(self, graph: CompiledStateGraph, params: dict,
                      resume_from: str | None = None) -> WorkflowResult:
        state = await self._load_checkpoint(resume_from) if resume_from else initial_state
        async for event in graph.astream(state):
            await self.event_bus.put(WorkflowEvent(...))
            await self.checkpointer.save(workflow_id, event["state"])
        return WorkflowResult(workflow_id, final_state, events)
```

**Файлы:**
- `src/pdf_framework/vibe_graph/executor.py` — WorkflowExecutor (~300 строк)
- `src/pdf_framework/vibe_graph/events.py` — WorkflowEvent, event types (~80 строк)
- `src/pdf_framework/vibe_graph/tracing.py` — OTLP integration, TokenTracker (~100 строк)
- `src/ui/components/execution_monitor.py` — real-time progress UI (~150 строк)
- `tests/vibe_graph/test_executor.py` (~180 строк)

**Effort:** 13h

---

### Iteration 9: Adaptive Execution & Replanning

**Цель:** Runtime-адаптация графа: error recovery, quality gates, dynamic branching, replanning.

**Зависимости:** Iteration 8

| Task | Deliverable | Effort |
|------|-------------|--------|
| T9.1 | Error recovery: RetryPolicy → fix_and_retry (LLM анализирует ошибку → исправляет → retry) / skip / notify_user | 2h |
| T9.2 | Dynamic branching: conditional edges на runtime данных (get_project_errors.count > 0 → fix_loop) | 1h |
| T9.3 | Quality gates: пороги (coverage >= 80%, errors == 0) → continue / loop back | 1.5h |
| T9.4 | Replanner node: получает результаты + intent → может добавить/удалить узлы в runtime (как plan_execute/replanner.py) | 2h |
| T9.5 | Max iterations: глобальный лимит для циклов (default 5), adaptive SQL (validate fail → get_metadata → fix → retry) | 1h |
| T9.6 | Unit tests | 2.5h |

**Архитектура:**

```python
class QualityGate:
    metric: str          # "errors", "coverage", "score"
    threshold: float     # 0.0, 0.8, 85.0
    operator: str        # "==", ">=", "<="
    on_fail: str         # "loop_back", "notify", "skip"
    max_loops: int = 5

class AdaptiveExecutor:
    """Обёртка над WorkflowExecutor с replanning."""

    async def execute_with_adaptation(self, graph, params) -> WorkflowResult:
        for iteration in range(self.max_iterations):
            result = await self.executor.execute(graph, params)
            gate_results = self._check_quality_gates(result)
            if all(g.passed for g in gate_results):
                return result
            # Replanning
            graph = await self._replan(graph, result, gate_results)
        return result  # best effort

    async def _replan(self, graph, result, gates) -> CompiledStateGraph:
        failed_gates = [g for g in gates if not g.passed]
        # LLM анализирует failures → предлагает изменения → re-compile
        ...
```

**Файлы:**
- `src/pdf_framework/vibe_graph/adaptive.py` — AdaptiveExecutor, error recovery (~200 строк)
- `src/pdf_framework/vibe_graph/quality_gates.py` — QualityGate, evaluation (~100 строк)
- `tests/vibe_graph/test_adaptive.py` (~150 строк)

**Effort:** 10h

---

### Iteration 10: MCP Tools & API Integration

**Цель:** Expose Vibe Graphing через MCP server (4 tools) и REST API (4 endpoints) для внешних клиентов.

**Зависимости:** Iteration 8, Iteration 9

| Task | Deliverable | Effort |
|------|-------------|--------|
| T10.1 | MCP tool `vibe_compile`: NL intent → WorkflowSpec (JSON preview) | 1.5h |
| T10.2 | MCP tool `vibe_execute`: WorkflowSpec или template_id + params → execution_id | 1.5h |
| T10.3 | MCP tool `vibe_templates`: список шаблонов с параметрами, фильтрация по domain | 1h |
| T10.4 | MCP tool `vibe_status`: статус по execution_id (nodes_completed, current, errors, progress_pct) | 1h |
| T10.5 | REST API: POST /vibe/compile, POST /vibe/execute, GET /vibe/status/{id} (SSE), GET /vibe/templates | 2h |
| T10.6 | Unit + integration tests | 1h |

**MCP Tools:**

```python
# В src/mcp_server/server.py — добавить 4 tool:

# vibe_compile: NL → WorkflowSpec
@server.call_tool("vibe_compile")
async def vibe_compile(description: str, domain: str | None = None) -> WorkflowSpec:
    compiler = IntentCompiler(registry, llm)
    return await compiler.compile(description, domain)

# vibe_execute: spec → run
@server.call_tool("vibe_execute")
async def vibe_execute(spec: dict | None = None, template_id: str | None = None,
                        params: dict = {}, dry_run: bool = False) -> dict:
    workflow = load_template(template_id, params) if template_id else WorkflowSpec(**spec)
    compiled = compiler.compile(workflow)
    if dry_run:
        return {"valid": True, "nodes": len(workflow.nodes), "edges": len(workflow.edges)}
    execution_id = await executor.execute(compiled, params)
    return {"execution_id": execution_id}

# vibe_templates: list templates
@server.call_tool("vibe_templates")
async def vibe_templates(domain: str | None = None) -> list[dict]:
    return loader.list_templates(domain=domain)

# vibe_status: check execution
@server.call_tool("vibe_status")
async def vibe_status(execution_id: str) -> dict:
    return executor.get_status(execution_id)
```

**REST API:**

| Endpoint | Method | Описание |
|----------|--------|----------|
| `/vibe/compile` | POST | NL → WorkflowSpec (JSON) |
| `/vibe/execute` | POST | WorkflowSpec → запуск, returns execution_id |
| `/vibe/status/{id}` | GET | SSE stream событий выполнения |
| `/vibe/templates` | GET | Список шаблонов с фильтрацией по domain |

**Файлы:**
- `src/mcp_server/server.py` — +4 MCP tools (обновление, ~100 строк нового кода)
- `src/api/routes/vibe_graph.py` — REST endpoints + SSE (~200 строк)
- `tests/vibe_graph/test_mcp_tools.py` (~120 строк)
- `tests/vibe_graph/test_api.py` (~100 строк)

**Effort:** 8h

---

## Сводная таблица

| # | Iteration | Effort | Зависимости | Статус | Ключевые файлы |
|---|-----------|--------|-------------|--------|-----------------|
| 1 | WorkflowSpec Schema & Node Registry | 10h | — | PLANNED | `schemas.py`, `node_registry.py` |
| 2 | MCP Tool Adapters (1С + Universal) | 14h | Iter 1 | PLANNED | `adapters/*.py` |
| 3 | Workflow Compiler | 17h | Iter 1, 2 | PLANNED | `compiler.py`, `state.py` |
| 4 | Intent Compiler (NL → Spec) | 10h | Iter 1, 2 | PLANNED | `intent_compiler.py` |
| 5 | 1С Task Templates | 11h | Iter 3, 4 | PLANNED | `templates/onec/*.yaml` |
| 6 | Universal Templates | 6.5h | Iter 3, 4 | PLANNED | `templates/universal/*.yaml` |
| 7 | Visual Editor (Streamlit) | 13h | Iter 5, 6 | PLANNED | `ui/pages/vibe_graph.py` |
| 8 | Execution Engine & Observability | 13h | Iter 3 | PLANNED | `executor.py`, `events.py` |
| 9 | Adaptive Execution & Replanning | 10h | Iter 8 | PLANNED | `adaptive.py`, `quality_gates.py` |
| 10 | MCP Tools & API Integration | 8h | Iter 8, 9 | PLANNED | `server.py`, `routes/vibe_graph.py` |
| | **ИТОГО** | **~112h** | | | |

---

## Порядок реализации (рекомендуемый)

```
Неделя 1:  Iter 1 (Schema) + Iter 2 (Adapters)          = 24h
Неделя 2:  Iter 3 (Compiler) + Iter 4 (Intent)           = 27h
Неделя 3:  Iter 5 (1C Templates) + Iter 6 (Universal)    = 17.5h
Неделя 4:  Iter 7 (Visual Editor)                         = 13h
Неделя 5:  Iter 8 (Executor) + Iter 9 (Adaptive)         = 23h
Неделя 6:  Iter 10 (MCP/API) + интеграционные тесты       = 8h + buffer
```

---

## Риски и митигации

| Риск | Вероятность | Импакт | Митигация |
|------|-------------|--------|-----------|
| **MCP timeout** на длинных операциях (EDT write + verify) | Высокая | Средний | Async execution, SSE для статуса, configurable timeouts per node |
| **LLM hallucination** в Intent Compiler (генерирует несуществующие tool_name) | Средняя | Высокий | Strict validation + NodeRegistry whitelist + итеративное уточнение (3 попытки) |
| **Mandatory chain разрыв** при визуальном редактировании | Средняя | Критический | Validation в компиляторе + UI блокирует удаление узлов из mandatory chain |
| **UI performance** на больших графах (50+ узлов) | Низкая | Средний | Lazy loading, виртуализация, subgraph collapsing |
| **Стоимость LLM** при частых компиляциях intent | Средняя | Средний | Кэширование intent→spec, приоритет шаблонов над NL-компиляцией, Z.AI delegation |

---

## Метрики успеха (KPIs)

| Метрика | Целевое значение | Как измерять |
|---------|------------------|--------------|
| Время NL → execute ready | < 2 мин | Timestamp от intent до первого node_started |
| Успешность компиляции intent | > 80% первая попытка | Валидация без ошибок / total attempts |
| Покрытие шаблонами типовых задач 1С | > 70% | 7 шаблонов / типовые задачи из JIRA |
| Время выполнения vs ручное | < 50% | Сравнение с историей ручных analyze+implement |
| Mandatory chain integrity | 100% | Ни один write_cycle/sql_cycle не разорван в production |
| Adoption rate (использование templates vs manual) | > 60% через месяц | Логи vibe_execute / total task starts |

---

## Связанные документы

- [MASFactory paper](https://arxiv.org/abs/2603.06007) — оригинальная публикация Vibe Graphing
- [MASFactory GitHub](https://github.com/BUPT-GAMMA/MASFactory) — reference implementation
- `docs/roadmap/ROADMAP_MCP_1C_INTEGRATION.md` — MCP инструменты для 1С
- `.claude/skills/analyze-1c-task-v2/SKILL.md` — 5-фазный анализ (станет шаблоном full_task)
- `.claude/skills/implement-1c-task/SKILL.md` — 8-этапная реализация (станет частью full_task)
- `src/pdf_framework/agents/plan_execute/` — базовый Plan-Execute агент (основа Intent Compiler)
