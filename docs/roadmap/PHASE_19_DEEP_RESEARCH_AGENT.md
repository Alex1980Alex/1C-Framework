# Phase 19: Deep Research Agent

**Приоритет:** СРЕДНИЙ | **Квартал:** Q2 2026 | **Версия:** v0.10.0
**Источники:** R2R, Dify, AnythingLLM
**Статус: РЕАЛИЗОВАНО**

---

## Проблема

Текущий RAG-агент (Phase 5) работает в один шаг: вопрос → поиск → грейдинг → ответ. Для сложных вопросов, требующих синтеза информации из нескольких документов и нескольких итераций поиска, этого недостаточно.

**Примеры проблемных запросов:**
- "Сравните механизм событий форм в тонком клиенте и в веб-клиенте, учитывая различия в обработке модальных окон"
- "Опишите полный цикл жизни объекта документа: от создания формы до записи в регистры"
- "Какие ограничения платформы влияют на выбор между регистром накопления и регистром сведений?"

В этих случаях один поисковый запрос не покрывает всю тему — нужна декомпозиция и последовательный поиск с накоплением контекста.

## Текущее состояние

### Что уже есть
- **SubQuestionDecomposer** (`src/pdf_framework/search/routing/decomposer.py`): разбивает сложный вопрос на 2-4 под-вопроса, синтезирует ответы
- **RAG Agent** (`src/pdf_framework/agents/rag/agent.py`): LangGraph граф с Self-RAG (grade → rewrite → hallucination check)
- **Adaptive Strategy** (`src/pdf_framework/search/strategies/adaptive.py`): автоматический выбор стратегии
- **Conversation Memory** (Phase 9): SQLite/память для хранения истории диалога
- **Каталог agents/** с заготовками: `agents/deep/` (пустой), `agents/graph/`, `agents/hybrid/`

### Чего не хватает
- Нет multi-hop reasoning (итеративный поиск на основе предыдущих результатов)
- Нет cross-document synthesis (осознанное объединение информации из разных PDF)
- Нет citation chain (прозрачная цепочка рассуждений с конкретными ссылками)
- Нет планирования исследования (research plan generation)
- Нет промежуточных итогов (intermediate summaries)

---

## Архитектура решения

```
User Question
  ↓
ResearchPlanner (LLM)
  ├─ Classify: simple → Standard RAG (Phase 5)
  └─ Classify: complex → Deep Research Pipeline
       ↓
  Generate Research Plan
       ├─ Sub-question 1 (с указанием стратегии)
       ├─ Sub-question 2
       ├─ Sub-question 3
       └─ Sub-question 4 (optional)
       ↓
  For each sub-question (sequential):
       ├─ Execute search (strategy from plan)
       ├─ Grade results
       ├─ Generate intermediate answer
       ├─ Extract key findings & entities
       └─ Update accumulated context
       ↓
  Cross-Document Synthesizer
       ├─ Merge intermediate answers
       ├─ Resolve contradictions
       ├─ Build citation chain
       └─ Generate final comprehensive answer
       ↓
  QualityChecker
       ├─ Coverage check (все под-вопросы покрыты?)
       ├─ Groundedness (все утверждения подтверждены?)
       └─ Gap detection → optional follow-up search
```

---

## Пошаговый план

### 19.1. Research Planner

**Новый файл:** `src/pdf_framework/agents/deep/planner.py`

```python
class ResearchPlan(BaseModel):
    """Plan for deep research execution."""
    original_question: str
    complexity: Literal["simple", "moderate", "complex"]
    sub_questions: list[SubQuestion]
    expected_sources: int              # Ожидаемое кол-во документов
    estimated_steps: int               # Оценка шагов

class SubQuestion(BaseModel):
    question: str
    strategy: str = "hybrid"            # Рекомендованная стратегия
    depends_on: list[int] = []          # Индексы зависимых под-вопросов
    focus_area: str = ""                # "формы", "регистры", "модули" и т.д.

class ResearchPlanner:
    """Generate research plans for complex questions."""

    def __init__(self, llm: ChatAnthropic):
        ...

    async def create_plan(self, question: str) -> ResearchPlan:
        """Analyze question complexity and create execution plan."""

    async def should_use_deep_research(self, question: str) -> bool:
        """Quick classification: simple RAG vs deep research."""
```

**Логика классификации:**
- **simple** — один аспект, один документ (→ стандартный RAG)
- **moderate** — 2-3 аспекта, возможно несколько документов
- **complex** — сравнение, анализ, несколько тем, cross-document

**Промпт для планирования:**
```
Ты — планировщик исследований по документации 1С:Предприятие.
Разбей вопрос на 2-4 под-вопроса для последовательного поиска.
Для каждого укажи:
- Текст под-вопроса (конкретный, поисковый)
- Стратегию: vector/hybrid/graphrag_local/bm25
- Зависимости от других под-вопросов (если есть)
- Фокусную область документации
```

### 19.2. Deep Research Agent (LangGraph)

**Новый файл:** `src/pdf_framework/agents/deep/agent.py`

```python
class DeepResearchState(TypedDict):
    """State for deep research LangGraph."""
    question: str
    research_plan: ResearchPlan
    current_step: int
    sub_results: list[SubResult]        # Промежуточные результаты
    accumulated_context: str            # Накопленный контекст
    accumulated_entities: list[str]     # Найденные сущности (для graph search)
    final_answer: str
    citations: list[Citation]
    quality_score: float

class SubResult(BaseModel):
    sub_question: str
    answer: str
    sources: list[str]
    key_findings: list[str]
    entities_found: list[str]
    confidence: float

class Citation(BaseModel):
    claim: str                          # Утверждение в ответе
    source: str                         # PDF файл
    chunk_id: str                       # ID чанка
    quote: str                          # Цитата из источника

def create_deep_research_agent(
    search_manager: SearchManager,
    settings: AgentSettings,
    self_rag_settings: SelfRAGSettings,
    api_key: str,
) -> CompiledGraph:
    """Create LangGraph deep research agent.

    Graph:
      plan → [loop: search_step → grade → intermediate_answer → update_context]
           → synthesize → quality_check → (follow_up | end)
    """
```

**Ноды графа:**

1. **plan** — вызывает `ResearchPlanner.create_plan()`, инициализирует state
2. **search_step** — выполняет поиск по текущему под-вопросу
   - Использует `accumulated_entities` для graph boost
   - Учитывает `depends_on` — ждёт результатов зависимых шагов
3. **grade_step** — грейдинг результатов (reuse Phase 5 grading)
4. **intermediate_answer** — генерация промежуточного ответа для под-вопроса
5. **update_context** — обновление накопленного контекста и сущностей
6. **synthesize** — финальный синтез из всех промежуточных ответов
7. **quality_check** — проверка покрытия и обоснованности
8. **follow_up_search** — дополнительный поиск при обнаружении пробелов

### 19.3. Cross-Document Synthesizer

**Новый файл:** `src/pdf_framework/agents/deep/synthesizer.py`

```python
class CrossDocumentSynthesizer:
    """Synthesize information from multiple search iterations."""

    async def synthesize(
        self,
        original_question: str,
        sub_results: list[SubResult],
        accumulated_context: str,
    ) -> tuple[str, list[Citation]]:
        """
        Merge sub-results into comprehensive answer.

        Returns:
            (answer, citations) — ответ с цитатами
        """

    async def resolve_contradictions(
        self,
        sub_results: list[SubResult],
    ) -> list[str]:
        """Identify and resolve contradictions between sources."""

    async def build_citation_chain(
        self,
        answer: str,
        sub_results: list[SubResult],
    ) -> list[Citation]:
        """Map each claim in the answer to a source chunk."""
```

**Промпт синтезатора:**
```
Ты получил промежуточные ответы на подвопросы. Создай единый, связный ответ:
1. Объедини информацию из всех подответов
2. Убери дубликаты
3. При противоречиях — укажи оба варианта с источниками
4. Каждое утверждение должно иметь ссылку [1], [2], ...
5. Структурируй ответ логически (не по подвопросам)
```

### 19.4. Quality Checker

**Новый файл:** `src/pdf_framework/agents/deep/quality.py`

```python
class QualityCheckResult(BaseModel):
    coverage_score: float               # Все ли аспекты вопроса покрыты?
    groundedness_score: float           # Все ли утверждения подтверждены?
    gaps: list[str]                     # Непокрытые аспекты
    needs_followup: bool                # Нужен ли дополнительный поиск?
    followup_queries: list[str]         # Доп. запросы для поиска

class ResearchQualityChecker:
    """Check quality of deep research output."""

    async def check(
        self,
        question: str,
        plan: ResearchPlan,
        answer: str,
        sub_results: list[SubResult],
    ) -> QualityCheckResult:
        """Evaluate research completeness and quality."""
```

### 19.5. Streaming Support

**Модификация:** `src/pdf_framework/agents/rag/streaming.py`

Добавить поддержку стриминга промежуточных шагов:

```python
class DeepResearchStreamEvent(BaseModel):
    event_type: Literal[
        "plan_created",       # План исследования готов
        "step_started",       # Начат шаг N
        "step_search",        # Поиск по под-вопросу
        "step_answer",        # Промежуточный ответ
        "synthesis_started",  # Начат синтез
        "quality_check",      # Проверка качества
        "followup_search",    # Дополнительный поиск
        "final_answer",       # Финальный ответ
    ]
    step: int | None = None
    data: dict[str, Any] = {}
```

### 19.6. API Endpoint

**Модификация:** `src/api/routes/search.py`

```python
class DeepResearchRequest(BaseModel):
    question: str
    max_steps: int = 4
    strategy: str = "hybrid"
    stream: bool = False

class DeepResearchResponse(BaseModel):
    answer: str
    citations: list[Citation]
    research_plan: dict
    sub_results: list[dict]
    quality_score: float
    elapsed_ms: float

@router.post("/deep-research", response_model=DeepResearchResponse)
async def deep_research(
    request: DeepResearchRequest,
    components: Components = Depends(get_components),
):
    """Execute deep research with multi-step retrieval."""

@router.post("/deep-research/stream")
async def deep_research_stream(
    request: DeepResearchRequest,
    components: Components = Depends(get_components),
):
    """Stream deep research progress via SSE."""
```

### 19.7. UI Integration

**Модификация:** `src/ui/pages/chat.py`

- Добавить кнопку "Глубокое исследование" рядом с "Отправить"
- При deep research показывать прогресс: какой шаг выполняется, промежуточные результаты
- После завершения — показать развёрнутый ответ с цитатами
- Добавить accordion с планом исследования и подробностями

### 19.8. CLI команда

**Модификация:** `src/cli/main.py`

```bash
pdf-framework research "Сравните механизм событий форм в тонком и веб-клиенте"
# Output:
#   Research Plan: 3 sub-questions
#   Step 1/3: Searching for "события форм тонкий клиент"... 5 results
#   Step 2/3: Searching for "события форм веб-клиент"... 4 results
#   Step 3/3: Searching for "различия обработки модальных окон"... 3 results
#   Synthesizing answer...
#   Quality: 0.87 (coverage: 0.9, groundedness: 0.85)
#
#   [Full answer with citations]
```

---

## Модифицируемые файлы

| Файл | Изменение |
|------|-----------|
| `src/pdf_framework/agents/deep/planner.py` | **NEW**: ResearchPlanner |
| `src/pdf_framework/agents/deep/agent.py` | **NEW**: Deep Research LangGraph agent |
| `src/pdf_framework/agents/deep/synthesizer.py` | **NEW**: CrossDocumentSynthesizer |
| `src/pdf_framework/agents/deep/quality.py` | **NEW**: ResearchQualityChecker |
| `src/pdf_framework/agents/deep/__init__.py` | **NEW**: Package init + factory |
| `src/pdf_framework/agents/rag/streaming.py` | **MODIFY**: +DeepResearchStreamEvent |
| `src/api/routes/search.py` | **MODIFY**: +`/deep-research` endpoint |
| `src/api/dependencies/components.py` | **MODIFY**: +DeepResearchAgent DI |
| `src/ui/pages/chat.py` | **MODIFY**: +кнопка "Глубокое исследование" |
| `src/cli/main.py` | **MODIFY**: +`research` command |
| `src/pdf_framework/config.py` | **MODIFY**: +DeepResearchSettings |

## Настройки

```python
class DeepResearchSettings(BaseSettings):
    enabled: bool = True
    max_sub_questions: int = 4
    max_followup_searches: int = 2
    planning_model: str = "claude-sonnet-4-5-20250929"  # Быстрая модель для плана
    synthesis_model: str = "claude-opus-4-6"             # Основная модель для синтеза
    quality_threshold: float = 0.7                       # Мин. качество без follow-up
    stream_intermediate: bool = True                     # Стримить промежуточные шаги
    timeout_seconds: int = 300                           # Таймаут всего исследования
```

## Верификация

1. Простой вопрос → `should_use_deep_research()` = False → стандартный RAG
2. Сложный вопрос → план с 3 под-вопросами → последовательный поиск
3. Промежуточные ответы содержат информацию из разных PDF
4. Финальный ответ объединяет всё с цитатами [1], [2], [3]
5. Quality check находит непокрытые аспекты → follow-up search
6. SSE стриминг показывает прогресс шагов
7. CLI выводит прогресс и финальный ответ
8. UI показывает план и промежуточные результаты
