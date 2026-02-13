# Phase 21: RAGAS Integration & Continuous Evaluation

**Приоритет:** СРЕДНИЙ | **Квартал:** Q3 2026 | **Версия:** v0.12.0
**Источники:** RAGAS, FlashRAG, Cognita
**Статус: РЕАЛИЗОВАНО**

---

## Проблема

Текущая система оценки (Phase 4) использует собственный LLM-as-a-Judge (`RAGEvaluator`) с тремя метриками. Это работает, но:

1. **Нет стандартизации** — наши метрики несовместимы с отраслевыми бенчмарками
2. **Нет synthetic test generation** — все тестовые вопросы созданы вручную
3. **Нет regression testing** — изменение кода может незаметно ухудшить качество
4. **Нет трекинга качества во времени** — невозможно увидеть тренд улучшения/ухудшения
5. **Нет детализации по типам ошибок** — "что именно не так" остаётся неизвестным

## Текущее состояние

### Что уже есть
- **RAGEvaluator** (`src/pdf_framework/evaluation/rag_evaluator.py`): Context Relevance, Groundedness, Answer Relevance (LLM-as-a-Judge)
- **EvalRunner** (`src/pdf_framework/evaluation/runner.py`): ranking metrics (Precision@k, Recall@k, MRR, NDCG@10, MAP)
- **EvalDataset** (`src/pdf_framework/evaluation/dataset.py`): test cases с relevant_chunk_ids
- **EvalReport** с детализацией по каждому query

### Чего не хватает
- Интеграция с RAGAS library (стандартные метрики)
- Synthetic test generation из документов
- CI/CD regression testing
- Quality dashboard с историческими графиками
- Анализ типов ошибок (retrieval failure vs generation failure)

---

## Архитектура решения

```
RAGAS Integration
  ├─ Adapter: наш SearchResponse → RAGAS Dataset format
  ├─ Метрики RAGAS:
  │   ├─ Context Precision (точнее нашего Context Relevance)
  │   ├─ Context Recall (с ground truth)
  │   ├─ Faithfulness (аналог нашего Groundedness, но строже)
  │   ├─ Answer Relevancy (с обратной генерацией вопросов)
  │   ├─ Answer Similarity (семантическое сходство с эталоном)
  │   └─ Answer Correctness (факт-чекинг)
  └─ Наш RAGEvaluator сохраняется как fallback (без зависимости от RAGAS)

Synthetic Generation
  ├─ Input: проиндексированные чанки
  ├─ Генерация: вопрос + эталонный ответ + контекст
  ├─ Категории: simple, reasoning, multi-context
  └─ Output: EvalDataset для RAGAS + EvalRunner

Regression Testing
  ├─ Git hook: pre-commit → quick eval (10 questions)
  ├─ CI: on PR → full eval (50 questions)
  ├─ Результат: pass/fail + delta vs baseline
  └─ Baseline хранится в data/eval/baseline.json

Quality Dashboard (Gradio)
  ├─ Historical chart: метрики по версиям/дням
  ├─ Error analysis: типы ошибок (retrieval vs generation)
  ├─ Per-question breakdown: какие вопросы проблемные
  └─ Comparison: текущая конфигурация vs предыдущая
```

---

## Пошаговый план

### 21.1. RAGAS Adapter

**Новый файл:** `src/pdf_framework/evaluation/ragas_adapter.py`

```python
from ragas import evaluate
from ragas.metrics import (
    context_precision,
    context_recall,
    faithfulness,
    answer_relevancy,
    answer_similarity,
    answer_correctness,
)
from datasets import Dataset

class RAGASAdapter:
    """Adapter between our evaluation system and RAGAS library."""

    def __init__(
        self,
        llm: ChatAnthropic | None = None,
        embeddings: BaseEmbeddingEngine | None = None,
    ):
        self._llm = llm
        self._embeddings = embeddings

    def to_ragas_dataset(
        self,
        questions: list[str],
        answers: list[str],
        contexts: list[list[str]],
        ground_truths: list[str] | None = None,
    ) -> Dataset:
        """Convert our evaluation data to RAGAS Dataset format.

        RAGAS expects:
          question: str
          answer: str
          contexts: list[str]
          ground_truth: str (optional)
        """
        data = {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
        }
        if ground_truths:
            data["ground_truth"] = ground_truths
        return Dataset.from_dict(data)

    async def evaluate(
        self,
        dataset: Dataset,
        metrics: list[str] | None = None,
    ) -> dict[str, float]:
        """Run RAGAS evaluation.

        Args:
            dataset: RAGAS-formatted dataset
            metrics: List of metric names or None for all

        Returns:
            {metric_name: score} dict
        """
        available_metrics = {
            "context_precision": context_precision,
            "context_recall": context_recall,
            "faithfulness": faithfulness,
            "answer_relevancy": answer_relevancy,
            "answer_similarity": answer_similarity,
            "answer_correctness": answer_correctness,
        }
        selected = [available_metrics[m] for m in (metrics or available_metrics)]

        result = evaluate(
            dataset=dataset,
            metrics=selected,
            llm=self._get_ragas_llm(),
            embeddings=self._get_ragas_embeddings(),
        )
        return dict(result)

    def _get_ragas_llm(self):
        """Wrap our LLM for RAGAS compatibility."""
        from ragas.llms import LangchainLLMWrapper
        return LangchainLLMWrapper(self._llm)

    def _get_ragas_embeddings(self):
        """Wrap our embeddings for RAGAS compatibility."""
        from ragas.embeddings import LangchainEmbeddingsWrapper
        # Adapter from our BaseEmbeddingEngine to LangChain Embeddings
        ...
```

### 21.2. Synthetic Test Generation

**Новый файл:** `src/pdf_framework/evaluation/synthetic.py`

```python
from ragas.testset.generator import TestsetGenerator
from ragas.testset.evolutions import simple, reasoning, multi_context

class SyntheticTestGenerator:
    """Generate synthetic test questions from indexed documents."""

    def __init__(
        self,
        llm: ChatAnthropic,
        embedding_engine: BaseEmbeddingEngine,
    ):
        self._llm = llm
        self._embedding_engine = embedding_engine

    async def generate(
        self,
        chunks: list[DocumentChunk],
        count: int = 50,
        distribution: dict[str, float] | None = None,
    ) -> list[SyntheticQuestion]:
        """Generate synthetic test questions.

        Args:
            chunks: Source chunks to generate questions from
            count: Number of questions to generate
            distribution: Type distribution, default:
                {"simple": 0.4, "reasoning": 0.3, "multi_context": 0.3}

        Uses RAGAS TestsetGenerator for diverse question types:
        - simple: single-chunk factual questions
        - reasoning: questions requiring inference
        - multi_context: questions requiring info from multiple chunks
        """
        distribution = distribution or {
            "simple": 0.4,
            "reasoning": 0.3,
            "multi_context": 0.3,
        }

        # Convert chunks to LangChain Documents for RAGAS
        documents = self._chunks_to_documents(chunks)

        generator = TestsetGenerator.from_langchain(
            generator_llm=self._llm,
            critic_llm=self._llm,
            embeddings=self._get_langchain_embeddings(),
        )

        testset = generator.generate_with_langchain_docs(
            documents=documents,
            test_size=count,
            distributions={
                simple: distribution.get("simple", 0.4),
                reasoning: distribution.get("reasoning", 0.3),
                multi_context: distribution.get("multi_context", 0.3),
            },
        )

        return self._convert_testset(testset)

    async def generate_custom(
        self,
        chunks: list[DocumentChunk],
        count: int = 50,
    ) -> list[SyntheticQuestion]:
        """Generate questions without RAGAS dependency (fallback).

        Uses our own LLM prompts for question generation.
        """
        questions = []
        for chunk in chunks[:count]:
            q = await self._generate_question_from_chunk(chunk)
            if q:
                questions.append(q)
        return questions

    async def _generate_question_from_chunk(
        self, chunk: DocumentChunk,
    ) -> SyntheticQuestion | None:
        """Generate a question-answer pair from a single chunk."""
        prompt = f"""Прочитай фрагмент документации 1С:Предприятие и сгенерируй вопрос.

Фрагмент:
{chunk.content[:1500]}

Формат ответа (JSON):
{{
  "question": "вопрос на русском языке",
  "answer": "краткий точный ответ из фрагмента",
  "type": "simple|reasoning|comparative",
  "keywords": ["ключевое слово 1", "ключевое слово 2"]
}}"""
        ...

class SyntheticQuestion(BaseModel):
    question: str
    answer: str
    question_type: str
    source_chunk_ids: list[str]
    keywords: list[str]
```

### 21.3. Regression Testing Framework

**Новый файл:** `src/pdf_framework/evaluation/regression.py`

```python
class EvalBaseline(BaseModel):
    """Stored baseline for regression comparison."""
    version: str
    timestamp: float
    metrics: dict[str, float]           # metric_name → score
    dataset_hash: str                   # SHA-256 of dataset for consistency
    config_hash: str                    # SHA-256 of relevant config

class RegressionTester:
    """Run regression tests and compare with baseline."""

    def __init__(
        self,
        baseline_path: Path = PROJECT_ROOT / "data" / "eval" / "baseline.json",
        threshold: float = 0.05,         # Max allowed degradation (5%)
    ):
        ...

    async def run_quick(
        self,
        components: Components,
        dataset: EvalDataset,
    ) -> RegressionResult:
        """Quick regression test (10 questions, no RAG Triad).

        For pre-commit hooks (~30 seconds).
        """

    async def run_full(
        self,
        components: Components,
        dataset: EvalDataset,
    ) -> RegressionResult:
        """Full regression test (50+ questions, with RAG Triad).

        For CI/CD pipeline (~5-10 minutes).
        """

    def compare_with_baseline(
        self,
        current: EvalReport,
    ) -> RegressionResult:
        """Compare current metrics with stored baseline.

        Returns:
          passed: True if no metric degraded by more than threshold
          deltas: {metric: (baseline, current, delta)}
          regressions: list of metrics that degraded
        """

    def update_baseline(self, report: EvalReport) -> None:
        """Store current metrics as new baseline."""

class RegressionResult(BaseModel):
    passed: bool
    deltas: dict[str, tuple[float, float, float]]  # (baseline, current, delta)
    regressions: list[str]              # Metrics that degraded
    improvements: list[str]             # Metrics that improved
    summary: str                        # Human-readable summary
```

### 21.4. Error Analysis

**Новый файл:** `src/pdf_framework/evaluation/error_analysis.py`

```python
class ErrorType(str, Enum):
    RETRIEVAL_MISS = "retrieval_miss"       # Правильный чанк не найден
    RETRIEVAL_NOISE = "retrieval_noise"     # Слишком много нерелевантных
    GENERATION_HALLUCINATION = "hallucination"  # LLM придумал факт
    GENERATION_INCOMPLETE = "incomplete"    # Ответ неполный
    GENERATION_WRONG_FOCUS = "wrong_focus"  # Ответ о другом

class ErrorAnalyzer:
    """Analyze evaluation errors to identify improvement areas."""

    async def analyze(
        self,
        report: EvalReport,
    ) -> ErrorAnalysisReport:
        """Classify errors by type and suggest fixes.

        For each failed query:
        1. Check retrieval metrics → retrieval_miss or retrieval_noise
        2. Check RAG Triad → hallucination, incomplete, wrong_focus
        3. Suggest fix: better chunking, different strategy, prompt fix
        """

    def by_category(self) -> dict[str, list[ErrorDetail]]:
        """Group errors by question category (factual, comparative, etc.)."""

    def recommendations(self) -> list[str]:
        """Generate improvement recommendations.

        Example:
        - "30% errors are retrieval_miss for comparative questions → try graphrag_local"
        - "20% hallucinations in analytical questions → lower temperature"
        - "BM25 outperforms vector for terminological queries"
        """

class ErrorAnalysisReport(BaseModel):
    total_queries: int
    error_count: int
    error_rate: float
    by_type: dict[ErrorType, int]
    by_category: dict[str, dict[ErrorType, int]]
    worst_queries: list[ErrorDetail]     # Top-10 worst performing queries
    recommendations: list[str]
```

### 21.5. Quality Dashboard (Gradio)

**Новый файл:** `src/ui/pages/evaluation.py`

```python
def create_evaluation_page(api_url: str):
    """Create evaluation dashboard page."""

    with gr.Column() as page:
        gr.Markdown("### Оценка качества RAG-системы")

        with gr.Tabs():
            # Tab 1: Current Metrics
            with gr.Tab("Текущие метрики"):
                run_eval_btn = gr.Button("Запустить оценку")
                metrics_table = gr.DataFrame(
                    headers=["Метрика", "Значение", "Baseline", "Δ"],
                )
                status_text = gr.Markdown()

            # Tab 2: Historical Trends
            with gr.Tab("Тренды"):
                metrics_chart = gr.LinePlot(
                    x="date", y="value", color="metric",
                    title="Метрики качества во времени",
                )

            # Tab 3: Error Analysis
            with gr.Tab("Анализ ошибок"):
                error_pie = gr.Plot(label="Типы ошибок")
                error_table = gr.DataFrame(
                    headers=["Вопрос", "Тип ошибки", "Ожидание", "Результат"],
                )
                recommendations = gr.Markdown()

            # Tab 4: Per-Query Breakdown
            with gr.Tab("По вопросам"):
                query_table = gr.DataFrame(
                    headers=["Вопрос", "P@5", "MRR", "Context Rel", "Grounded", "Answer Rel"],
                )

            # Tab 5: Synthetic Test Generation
            with gr.Tab("Генерация тестов"):
                gen_count = gr.Slider(10, 100, 50, label="Количество вопросов")
                gen_btn = gr.Button("Сгенерировать")
                gen_output = gr.JSON(label="Сгенерированные вопросы")
```

### 21.6. Historical Metrics Storage

**Новый файл:** `src/pdf_framework/evaluation/history.py`

```python
class EvalHistoryStore:
    """Store evaluation results over time for trend analysis."""

    def __init__(self, db_path: Path = PROJECT_ROOT / "data" / "eval" / "history.db"):
        ...

    async def initialize(self) -> None:
        """Create SQLite tables.

        CREATE TABLE eval_runs (
            run_id TEXT PRIMARY KEY,
            timestamp REAL NOT NULL,
            version TEXT,
            config_hash TEXT,
            dataset_name TEXT,
            strategy TEXT,
            metrics_json TEXT NOT NULL
        );
        """

    async def store(self, report: EvalReport, version: str = "") -> str:
        """Store evaluation report."""

    async def get_history(
        self,
        metric: str,
        days: int = 30,
    ) -> list[tuple[float, float]]:
        """Get metric values over time: [(timestamp, value), ...]"""

    async def get_latest(self, n: int = 10) -> list[EvalReport]:
        """Get N most recent evaluation reports."""
```

### 21.7. CLI команды

**Модификация:** `src/cli/main.py`

```bash
# Запуск RAGAS-оценки
pdf-framework eval ragas --benchmark data/benchmarks/1c_v1.json --strategy hybrid

# Генерация синтетических тестов
pdf-framework eval generate-tests --count 50 --output data/benchmarks/synthetic_v1.json

# Regression test (quick)
pdf-framework eval regression --quick
# Output: PASSED (MRR: 0.82 → 0.83 (+0.01), P@5: 0.71 → 0.70 (-0.01))

# Regression test (full)
pdf-framework eval regression --full

# Error analysis
pdf-framework eval errors --benchmark data/benchmarks/1c_v1.json
# Output:
#   Retrieval Miss: 30% (15/50)
#   Hallucination: 10% (5/50)
#   Recommendations:
#     - Use graphrag_local for comparative questions
#     - Lower temperature for analytical questions

# Update baseline
pdf-framework eval update-baseline
```

### 21.8. API Endpoints

**Новый файл:** `src/api/routes/evaluation.py`

```python
router = APIRouter(prefix="/eval", tags=["evaluation"])

@router.post("/run")
async def run_evaluation(
    benchmark: str,
    strategy: str = "hybrid",
    metrics: list[str] | None = None,
    components: Components = Depends(get_components),
):
    """Run evaluation and return metrics."""

@router.get("/history")
async def get_eval_history(
    metric: str = "mrr",
    days: int = 30,
):
    """Get historical metric values."""

@router.get("/baseline")
async def get_baseline():
    """Get current baseline metrics."""

@router.post("/regression")
async def run_regression(quick: bool = True):
    """Run regression test."""
```

---

## Модифицируемые файлы

| Файл | Изменение |
|------|-----------|
| `src/pdf_framework/evaluation/ragas_adapter.py` | **NEW**: RAGAS integration adapter |
| `src/pdf_framework/evaluation/synthetic.py` | **NEW**: Synthetic test generation |
| `src/pdf_framework/evaluation/regression.py` | **NEW**: Regression testing framework |
| `src/pdf_framework/evaluation/error_analysis.py` | **NEW**: Error type classification |
| `src/pdf_framework/evaluation/history.py` | **NEW**: Historical metrics storage |
| `src/ui/pages/evaluation.py` | **NEW**: Quality dashboard |
| `src/api/routes/evaluation.py` | **NEW**: Evaluation API endpoints |
| `src/cli/main.py` | **MODIFY**: +`eval` commands |
| `src/ui/app.py` | **MODIFY**: +Evaluation tab |
| `src/api/app.py` | **MODIFY**: +evaluation router |
| `src/pdf_framework/config.py` | **MODIFY**: +EvaluationSettings |
| `pyproject.toml` | **MODIFY**: +`ragas`, +`datasets` dependencies |

## Настройки

```python
class EvaluationSettings(BaseSettings):
    ragas_enabled: bool = True
    history_db_path: Path = PROJECT_ROOT / "data" / "eval" / "history.db"
    baseline_path: Path = PROJECT_ROOT / "data" / "eval" / "baseline.json"
    regression_threshold: float = 0.05   # Max allowed degradation (5%)
    quick_eval_count: int = 10           # Questions for quick regression
    full_eval_count: int = 50            # Questions for full regression
    synthetic_gen_model: str = "claude-sonnet-4-5-20250929"
```

## Зависимости

```toml
[project.optional-dependencies]
eval = [
    "ragas>=0.2.0",
    "datasets>=2.16.0",
]
```

## Верификация

1. RAGAS adapter: конвертация нашего формата → RAGAS Dataset → оценка
2. Synthetic generation: 50 вопросов из чанков → проверка осмысленности
3. Regression quick: <30 секунд, корректное сравнение с baseline
4. Regression full: с RAG Triad, детальный отчёт
5. Error analysis: правильная классификация типов ошибок
6. Dashboard: графики трендов, таблица ошибок, рекомендации
7. History: метрики сохраняются между запусками, тренды видны
