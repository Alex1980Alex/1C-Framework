# Phase 22: Self-Learning Feedback Loop

**Приоритет:** СРЕДНИЙ | **Квартал:** Q3 2026 | **Версия:** v0.13.0
**Источники:** Vanna AI, Quivr, Pathway
**Статус: РЕАЛИЗОВАНО**

---

## Проблема

Система не учится на своих ответах. Пользователи видят ответы, но не могут указать, какие хорошие, а какие плохие. Нет механизма для:

1. **Сбора обратной связи** — пользователь не может оценить ответ
2. **Обучения на успехах** — хорошие пары (вопрос → ответ) не используются повторно
3. **Адаптации параметров** — веса стратегий не меняются на основе реального опыта
4. **Приоритизации контента** — популярные темы не получают приоритета в поиске

## Текущее состояние

### Что уже есть
- **Conversation Memory** (Phase 9): `ConversationMemory` в SQLite — хранит историю диалогов
- **Chat UI** (`src/ui/pages/chat.py`): Gradio chatbot с историей, но без кнопок фидбека
- **RAG Agent** с грейдингом и Self-RAG — но грейдинг автоматический, не учитывает мнение пользователя
- **Semantic Cache** (Phase 17): кэш поисковых результатов — можно приоритизировать на основе фидбека
- **SearchManager** с регистрацией стратегий и настраиваемыми весами

### Чего не хватает
- Кнопки 👍/👎 в UI
- Хранилище фидбека (SQLite)
- Few-shot prompting из успешных пар
- Автокоррекция весов стратегий
- Приоритизация контента на основе популярности

---

## Архитектура решения

```
User asks question → RAG answers → User gives feedback (👍/👎 + optional comment)
  ↓
FeedbackStore (SQLite)
  ├─ question, answer, strategy, score, timestamp
  ├─ search_results (chunk_ids + scores)
  └─ user_comment (optional)
  ↓
FeedbackAnalyzer (periodic)
  ├─ Strategy Performance:
  │   ├─ hybrid: 85% positive
  │   ├─ vector: 70% positive
  │   └─ bm25: 90% positive for terminological
  │
  ├─ Successful Pairs (few-shot):
  │   └─ Top positive (question, answer) → system prompt
  │
  ├─ Weight Tuning:
  │   ├─ hybrid_vector_weight: 0.5 → 0.45
  │   └─ hybrid_bm25_weight: 0.3 → 0.35
  │
  └─ Content Priority:
      └─ Popular chunk_ids → boost in search score
```

---

## Пошаговый план

### 22.1. Feedback Storage

**Новый файл:** `src/pdf_framework/feedback/store.py`

```python
class FeedbackEntry(BaseModel):
    """Single feedback entry."""
    feedback_id: str                     # UUID
    question: str
    answer: str
    score: Literal[-1, 0, 1]            # 👎 = -1, neutral = 0, 👍 = 1
    comment: str = ""                    # Optional user comment
    strategy: str                        # Strategy used for search
    search_k: int
    chunk_ids: list[str]                 # Retrieved chunk IDs
    chunk_scores: list[float]            # Retrieval scores
    session_id: str = ""                 # Conversation session
    timestamp: float                     # Unix timestamp
    metadata: dict = {}                  # Additional context

class FeedbackStore:
    """SQLite-backed feedback storage."""

    def __init__(self, db_path: Path = PROJECT_ROOT / "data" / "feedback.db"):
        ...

    async def initialize(self) -> None:
        """Create SQLite tables.

        CREATE TABLE feedback (
            feedback_id TEXT PRIMARY KEY,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            score INTEGER NOT NULL,
            comment TEXT DEFAULT '',
            strategy TEXT NOT NULL,
            search_k INTEGER DEFAULT 5,
            chunk_ids_json TEXT NOT NULL,
            chunk_scores_json TEXT NOT NULL,
            session_id TEXT DEFAULT '',
            timestamp REAL NOT NULL,
            metadata_json TEXT DEFAULT '{}'
        );

        CREATE INDEX idx_feedback_score ON feedback(score);
        CREATE INDEX idx_feedback_strategy ON feedback(strategy);
        CREATE INDEX idx_feedback_timestamp ON feedback(timestamp);
        """

    async def add(self, entry: FeedbackEntry) -> None:
        """Store feedback entry."""

    async def get_positive(
        self,
        limit: int = 100,
        strategy: str | None = None,
    ) -> list[FeedbackEntry]:
        """Get top positive feedback entries."""

    async def get_negative(
        self,
        limit: int = 50,
    ) -> list[FeedbackEntry]:
        """Get negative feedback for analysis."""

    async def get_stats(self) -> dict:
        """Get feedback statistics.

        Returns: {
            total: int,
            positive: int,
            negative: int,
            neutral: int,
            positive_rate: float,
            by_strategy: {strategy: {positive: int, total: int, rate: float}},
            popular_chunks: [{chunk_id: str, count: int, avg_score: float}],
        }
        """

    async def get_by_strategy(self, strategy: str) -> list[FeedbackEntry]:
        """Get all feedback for a specific strategy."""
```

### 22.2. UI Integration (Feedback Buttons)

**Модификация:** `src/ui/pages/chat.py`

```python
def create_chat_page(api_url: str):
    with gr.Column() as page:
        # ... existing chatbot, strategy dropdown, etc. ...

        chatbot = gr.Chatbot(height=500, label="Диалог")

        with gr.Row():
            msg = gr.Textbox(...)
            submit_btn = gr.Button("Отправить", variant="primary", scale=1)

        # Feedback buttons (appear after answer)
        with gr.Row(visible=False) as feedback_row:
            thumbs_up = gr.Button("👍 Полезно", variant="secondary", scale=1)
            thumbs_down = gr.Button("👎 Не помогло", variant="secondary", scale=1)
            feedback_comment = gr.Textbox(
                placeholder="Комментарий (необязательно)...",
                show_label=False,
                scale=3,
            )
            feedback_status = gr.Markdown("")

        # State for tracking last answer context
        last_answer_state = gr.State({})

        def chat_fn(message, history, strategy):
            # ... existing logic ...
            # After getting answer, store context for feedback
            answer_context = {
                "question": message,
                "answer": answer,
                "strategy": strategy,
                "chunk_ids": data.get("chunk_ids", []),
                "chunk_scores": data.get("chunk_scores", []),
            }
            return history, "", sources_text, gr.update(visible=True), answer_context

        def send_feedback(score, comment, answer_ctx):
            requests.post(f"{api_url}/feedback", json={
                "question": answer_ctx["question"],
                "answer": answer_ctx["answer"],
                "score": score,
                "comment": comment,
                "strategy": answer_ctx["strategy"],
                "chunk_ids": answer_ctx["chunk_ids"],
            })
            return "Спасибо за отзыв!"
```

### 22.3. API Endpoints

**Новый файл:** `src/api/routes/feedback.py`

```python
router = APIRouter(prefix="/feedback", tags=["feedback"])

class FeedbackRequest(BaseModel):
    question: str
    answer: str
    score: Literal[-1, 0, 1]
    comment: str = ""
    strategy: str = ""
    chunk_ids: list[str] = []
    chunk_scores: list[float] = []
    session_id: str = ""

@router.post("/")
async def submit_feedback(
    request: FeedbackRequest,
    components: Components = Depends(get_components),
):
    """Submit user feedback for an answer."""
    entry = FeedbackEntry(
        feedback_id=str(uuid4()),
        question=request.question,
        answer=request.answer,
        score=request.score,
        comment=request.comment,
        strategy=request.strategy,
        chunk_ids=request.chunk_ids,
        chunk_scores=request.chunk_scores,
        session_id=request.session_id,
        timestamp=time.time(),
    )
    await components.feedback_store.add(entry)
    return {"status": "ok", "feedback_id": entry.feedback_id}

@router.get("/stats")
async def feedback_stats(
    components: Components = Depends(get_components),
):
    """Get feedback statistics."""
    return await components.feedback_store.get_stats()

@router.get("/positive")
async def positive_feedback(
    limit: int = 20,
    strategy: str | None = None,
    components: Components = Depends(get_components),
):
    """Get top positive feedback entries (for few-shot examples)."""
    entries = await components.feedback_store.get_positive(limit, strategy)
    return [e.model_dump() for e in entries]
```

### 22.4. Few-Shot Learning from Positive Feedback

**Новый файл:** `src/pdf_framework/feedback/few_shot.py`

```python
class FewShotProvider:
    """Provide few-shot examples from positive feedback.

    Подбирает 2-3 самых похожих успешных пары (вопрос → ответ)
    для включения в system prompt при генерации ответа.
    """

    def __init__(
        self,
        feedback_store: FeedbackStore,
        embedding_engine: BaseEmbeddingEngine,
        max_examples: int = 3,
        similarity_threshold: float = 0.7,
    ):
        self._store = feedback_store
        self._engine = embedding_engine
        self._max_examples = max_examples
        self._threshold = similarity_threshold
        self._cache: list[tuple[list[float], FeedbackEntry]] | None = None

    async def get_examples(self, question: str) -> list[FewShotExample]:
        """Find similar positive Q&A pairs for few-shot prompting.

        1. Embed the new question
        2. Compare with embeddings of positive feedback questions
        3. Return top-k most similar pairs above threshold
        """
        if self._cache is None:
            await self._build_cache()

        query_embedding = await self._engine.embed_text(question)

        # Compute similarities
        similarities = []
        for emb, entry in self._cache:
            sim = self._cosine_similarity(query_embedding, emb)
            if sim >= self._threshold:
                similarities.append((sim, entry))

        # Sort by similarity, take top-k
        similarities.sort(key=lambda x: x[0], reverse=True)
        examples = [
            FewShotExample(
                question=entry.question,
                answer=entry.answer,
                similarity=sim,
            )
            for sim, entry in similarities[:self._max_examples]
        ]

        return examples

    async def _build_cache(self) -> None:
        """Load positive feedback and embed questions."""
        positive = await self._store.get_positive(limit=200)
        self._cache = []
        for entry in positive:
            emb = await self._engine.embed_text(entry.question)
            self._cache.append((emb, entry))

    def format_for_prompt(self, examples: list[FewShotExample]) -> str:
        """Format examples for system prompt injection.

        Примеры успешных ответов:

        Вопрос: {q1}
        Ответ: {a1}

        Вопрос: {q2}
        Ответ: {a2}
        """

class FewShotExample(BaseModel):
    question: str
    answer: str
    similarity: float
```

**Интеграция в RAG Agent:**

```python
# В generate_answer (agent.py):
few_shot_provider = components.few_shot_provider
examples = await few_shot_provider.get_examples(question)

if examples:
    examples_text = few_shot_provider.format_for_prompt(examples)
    system_prompt = (
        "Всегда отвечай на русском языке.\n\n"
        f"{examples_text}\n\n"
        "Отвечай на вопрос, используя ТОЛЬКО предоставленный контекст.\n\n"
        f"Контекст:\n{context}"
    )
```

### 22.5. Strategy Weight Tuning

**Новый файл:** `src/pdf_framework/feedback/tuner.py`

```python
class StrategyTuner:
    """Auto-tune strategy weights based on feedback.

    Анализирует фидбек по стратегиям и корректирует:
    - hybrid_vector_weight, hybrid_graph_weight, hybrid_bm25_weight
    - Рекомендации по default strategy
    """

    def __init__(self, feedback_store: FeedbackStore):
        self._store = feedback_store

    async def analyze(self) -> TuningReport:
        """Analyze feedback and suggest weight adjustments.

        Алгоритм:
        1. Собрать фидбек по стратегиям
        2. Для hybrid: проанализировать chunk_ids — какой retriever нашёл лучшие
        3. Посчитать success rate по стратегиям
        4. Предложить новые веса

        Returns:
            TuningReport with recommendations
        """

    async def auto_tune(self, settings: SearchSettings) -> SearchSettings:
        """Automatically apply weight adjustments.

        Only adjusts if:
        - Enough feedback (>50 entries)
        - Clear signal (strategy success rate differs by >15%)
        - Changes are small (max ±0.1 per weight)
        """

    async def get_strategy_performance(self) -> dict[str, StrategyStats]:
        """Get per-strategy performance stats.

        Returns: {
            "hybrid": StrategyStats(total=100, positive=85, rate=0.85),
            "vector": StrategyStats(total=50, positive=35, rate=0.70),
            ...
        }
        """

class TuningReport(BaseModel):
    current_weights: dict[str, float]
    suggested_weights: dict[str, float]
    confidence: float                    # 0-1, based on feedback volume
    strategy_stats: dict[str, StrategyStats]
    recommendations: list[str]

class StrategyStats(BaseModel):
    total: int
    positive: int
    negative: int
    rate: float                          # positive / total
```

### 22.6. Content Priority Boost

**Новый файл:** `src/pdf_framework/feedback/boost.py`

```python
class ContentBooster:
    """Boost search scores for chunks that consistently appear in positive feedback.

    Чанки, которые часто приводят к хорошим ответам, получают boost при поиске.
    """

    def __init__(self, feedback_store: FeedbackStore):
        self._store = feedback_store
        self._boost_map: dict[str, float] | None = None

    async def get_boost(self, chunk_id: str) -> float:
        """Get boost factor for a chunk.

        Returns 1.0 (no boost) to 1.3 (30% boost) based on positive feedback frequency.
        """
        if self._boost_map is None:
            await self._build_boost_map()
        return self._boost_map.get(chunk_id, 1.0)

    async def apply_boost(
        self,
        results: list[SearchResult],
    ) -> list[SearchResult]:
        """Apply feedback-based boost to search results.

        Reorders results by score * boost_factor.
        """
        for result in results:
            boost = await self.get_boost(result.chunk.id)
            result.score *= boost
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    async def _build_boost_map(self) -> None:
        """Build chunk_id → boost_factor map from feedback.

        Algorithm:
        - Count appearances in positive vs negative feedback
        - Positive ratio > 0.8 and count > 3 → boost 1.1-1.3
        - Negative ratio > 0.5 → no boost (1.0)
        """
```

### 22.7. Feedback Dashboard (UI)

**Новый файл:** `src/ui/pages/feedback.py`

```python
def create_feedback_page(api_url: str):
    with gr.Column() as page:
        gr.Markdown("### Обратная связь и обучение")

        with gr.Tabs():
            # Tab 1: Statistics
            with gr.Tab("Статистика"):
                refresh_btn = gr.Button("Обновить")
                stats_json = gr.JSON(label="Общая статистика")
                strategy_chart = gr.BarPlot(
                    x="strategy", y="positive_rate",
                    title="Успешность по стратегиям",
                )

            # Tab 2: Recent Feedback
            with gr.Tab("Последний фидбек"):
                feedback_table = gr.DataFrame(
                    headers=["Время", "Вопрос", "Оценка", "Стратегия", "Комментарий"],
                )

            # Tab 3: Weight Tuning
            with gr.Tab("Настройка весов"):
                analyze_btn = gr.Button("Анализировать и предложить")
                current_weights = gr.JSON(label="Текущие веса")
                suggested_weights = gr.JSON(label="Предлагаемые веса")
                apply_btn = gr.Button("Применить предложенные веса", variant="primary")
                tuning_status = gr.Markdown()

            # Tab 4: Few-Shot Examples
            with gr.Tab("Примеры для обучения"):
                examples_table = gr.DataFrame(
                    headers=["Вопрос", "Ответ", "Стратегия", "Оценка"],
                )
```

---

## Модифицируемые файлы

| Файл | Изменение |
|------|-----------|
| `src/pdf_framework/feedback/store.py` | **NEW**: FeedbackStore (SQLite) |
| `src/pdf_framework/feedback/few_shot.py` | **NEW**: FewShotProvider |
| `src/pdf_framework/feedback/tuner.py` | **NEW**: StrategyTuner |
| `src/pdf_framework/feedback/boost.py` | **NEW**: ContentBooster |
| `src/pdf_framework/feedback/__init__.py` | **NEW**: Package init |
| `src/api/routes/feedback.py` | **NEW**: Feedback API endpoints |
| `src/ui/pages/feedback.py` | **NEW**: Feedback dashboard |
| `src/ui/pages/chat.py` | **MODIFY**: +👍/👎 buttons, feedback state |
| `src/ui/app.py` | **MODIFY**: +Feedback tab |
| `src/api/app.py` | **MODIFY**: +feedback router |
| `src/api/dependencies/components.py` | **MODIFY**: +FeedbackStore, +FewShotProvider DI |
| `src/pdf_framework/agents/rag/agent.py` | **MODIFY**: +few-shot examples in prompt |
| `src/pdf_framework/search/manager.py` | **MODIFY**: +content boost (optional) |
| `src/pdf_framework/config.py` | **MODIFY**: +FeedbackSettings |

## Настройки

```python
class FeedbackSettings(BaseSettings):
    enabled: bool = True
    db_path: Path = PROJECT_ROOT / "data" / "feedback.db"
    few_shot_enabled: bool = True
    few_shot_max_examples: int = 3
    few_shot_similarity_threshold: float = 0.7
    auto_tune_enabled: bool = False      # Manual approval by default
    auto_tune_min_feedback: int = 50     # Min entries before tuning
    content_boost_enabled: bool = True
    content_boost_max: float = 1.3       # Max boost factor
```

## Верификация

1. Задать вопрос → получить ответ → нажать 👍 → запись в feedback.db
2. Задать похожий вопрос → few-shot примеры включены в промпт → качество ответа выше
3. 50+ фидбеков → `analyze()` → report с рекомендациями по весам
4. Content boost: чанки с высоким позитивным рейтингом ранжируются выше
5. Dashboard: статистика, тренды, предложения по настройке
6. API: POST /feedback → 200, GET /feedback/stats → статистика
