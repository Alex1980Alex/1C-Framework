# Phase 20: Automatic RAG Optimization (AutoRAG)

**Приоритет:** СРЕДНИЙ | **Квартал:** Q2 2026 | **Версия:** v0.11.0
**Источники:** AutoRAG, DSPy, FlashRAG
**Статус: РЕАЛИЗОВАНО**

---

## Проблема

Текущие параметры RAG-системы (chunk_size, overlap, стратегия поиска, k, модель реранкера, веса hybrid) подобраны вручную. Нет гарантии, что это оптимальная конфигурация. Изменение одного параметра (например, модели эмбеддингов) может потребовать пересмотра всех остальных.

**Текущие жёстко заданные значения:**
- `chunk_size`: 512 (config.py)
- `chunk_overlap`: 50 (config.py)
- `hybrid_vector_weight`: 0.5
- `hybrid_graph_weight`: 0.2
- `bm25_weight`: 0.3
- `search k`: 5
- `mmr_diversity_lambda`: 0.5
- `score_prefilter_threshold`: 0.1
- Reranker: CrossEncoder vs FlashRank vs None

## Текущее состояние

### Что уже есть
- **EvalRunner** (`src/pdf_framework/evaluation/runner.py`): прогоняет dataset через strategy, считает precision/recall/MRR/NDCG/MAP
- **EvalDataset** (`src/pdf_framework/evaluation/dataset.py`): набор test cases с relevant_chunk_ids
- **RAGEvaluator** (`src/pdf_framework/evaluation/rag_evaluator.py`): LLM-as-a-Judge для RAG Triad
- **SearchManager** с регистрацией стратегий — легко перебирать
- **Настраиваемые веса** в `SearchSettings` через env

### Чего не хватает
- Нет benchmark dataset по документации 1С
- Нет parameter grid search
- Нет автоматического сравнения конфигураций
- Нет экспорта оптимальной конфигурации
- Нет A/B тестирования

---

## Архитектура решения

```
BenchmarkDataset (50+ вопросов-ответов по 1С)
  ↓
ParameterGrid
  ├─ chunk_size: [256, 512, 1024]
  ├─ chunk_overlap: [0, 50, 100]
  ├─ strategy: [vector, hybrid, two_stage, bm25]
  ├─ k: [3, 5, 10]
  ├─ reranker: [none, cross_encoder, flashrank]
  ├─ hybrid_weights: [(0.7,0.2,0.1), (0.5,0.3,0.2), (0.4,0.3,0.3)]
  └─ score_prefilter: [0.0, 0.1, 0.2]
  ↓
AutoRAGRunner (iterates grid)
  For each config:
    ├─ Apply config
    ├─ (optionally re-index if chunk_size changed)
    ├─ Run EvalRunner on dataset
    ├─ Collect metrics: Precision@5, MRR, NDCG@10, latency, RAG Triad
    └─ Store result
  ↓
ResultsAnalyzer
  ├─ Rank configs by composite score
  ├─ Generate comparison table
  ├─ Identify best config per metric
  └─ Export optimal config → .env / JSON
```

---

## Пошаговый план

### 20.1. Benchmark Dataset для 1С

**Новый файл:** `src/pdf_framework/evaluation/benchmark.py`

```python
class BenchmarkQuestion(BaseModel):
    """Single benchmark question with ground truth."""
    id: str
    question: str
    category: Literal[
        "factual",        # "Что такое регистр накопления?"
        "procedural",     # "Как создать обработку?"
        "comparative",    # "Чем отличается тонкий клиент от толстого?"
        "analytical",     # "Какие ограничения управляемых форм?"
        "terminological", # "Что такое СКД?"
    ]
    expected_answer: str                     # Эталонный ответ
    relevant_chunk_ids: list[str] = []       # Релевантные чанки (если известны)
    relevant_keywords: list[str] = []        # Ключевые слова в правильном ответе
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    source_pdf: str = ""                     # Из какого PDF

class BenchmarkDataset:
    """Manage benchmark datasets for AutoRAG."""

    def __init__(self, path: Path):
        ...

    def load(self) -> list[BenchmarkQuestion]:
        """Load questions from JSON file."""

    def save(self, questions: list[BenchmarkQuestion]) -> None:
        """Save questions to JSON file."""

    @staticmethod
    def generate_from_chunks(
        chunks: list[DocumentChunk],
        llm: ChatAnthropic,
        count: int = 50,
    ) -> list[BenchmarkQuestion]:
        """Auto-generate benchmark questions from indexed chunks.

        For each chunk, LLM generates a question that this chunk answers.
        """
```

**Файл данных:** `data/benchmarks/1c_benchmark_v1.json`

```json
[
  {
    "id": "q001",
    "question": "Что такое регистр накопления?",
    "category": "factual",
    "expected_answer": "Регистр накопления — прикладной объект конфигурации...",
    "relevant_keywords": ["регистр накопления", "остатки", "обороты", "измерения", "ресурсы"],
    "difficulty": "easy"
  },
  {
    "id": "q002",
    "question": "Чем отличается тонкий клиент от толстого клиента?",
    "category": "comparative",
    "expected_answer": "Тонкий клиент работает в управляемом режиме...",
    "relevant_keywords": ["тонкий клиент", "толстый клиент", "управляемый режим"],
    "difficulty": "medium"
  }
]
```

### 20.2. Автогенерация вопросов из чанков

**Модификация:** `src/pdf_framework/evaluation/benchmark.py`

```python
class QuestionGenerator:
    """Generate benchmark questions from document chunks."""

    def __init__(self, llm: ChatAnthropic):
        self._llm = llm

    async def generate_batch(
        self,
        chunks: list[DocumentChunk],
        questions_per_chunk: int = 1,
        categories: list[str] | None = None,
    ) -> list[BenchmarkQuestion]:
        """Generate questions from chunks using LLM.

        Prompt:
          Прочитай фрагмент документации 1С:Предприятие.
          Сгенерируй 1 вопрос, на который этот фрагмент даёт ответ.
          Формат:
            question: <вопрос>
            category: factual|procedural|comparative|analytical|terminological
            expected_answer: <краткий эталонный ответ из фрагмента>
            keywords: <ключевые слова через запятую>
        """

    async def generate_comparative(
        self,
        chunk_pairs: list[tuple[DocumentChunk, DocumentChunk]],
    ) -> list[BenchmarkQuestion]:
        """Generate comparison questions from pairs of related chunks."""
```

### 20.3. Parameter Grid Definition

**Новый файл:** `src/pdf_framework/evaluation/autorag.py`

```python
class ParameterConfig(BaseModel):
    """Single parameter configuration to evaluate."""
    config_id: str
    chunk_size: int = 512
    chunk_overlap: int = 50
    strategy: str = "hybrid"
    k: int = 5
    reranker: Literal["none", "cross_encoder", "flashrank"] = "none"
    hybrid_vector_weight: float = 0.5
    hybrid_graph_weight: float = 0.2
    hybrid_bm25_weight: float = 0.3
    mmr_lambda: float = 0.5
    score_prefilter: float = 0.1

class ParameterGrid:
    """Define parameter combinations for grid search."""

    def __init__(self, **param_ranges: list):
        """
        Example:
            grid = ParameterGrid(
                strategy=["vector", "hybrid", "two_stage"],
                k=[3, 5, 10],
                reranker=["none", "cross_encoder"],
            )
        """

    def configs(self) -> list[ParameterConfig]:
        """Generate all combinations (cartesian product)."""

    def configs_count(self) -> int:
        """Total number of combinations."""

class SmartGrid(ParameterGrid):
    """Smart grid that prunes unlikely combinations.

    Rules:
    - If reranker=flashrank, skip two_stage (redundant)
    - If strategy=bm25, skip hybrid weights
    - If strategy=vector, skip bm25_weight
    """
```

### 20.4. AutoRAG Runner

**Новый файл:** `src/pdf_framework/evaluation/autorag_runner.py`

```python
class AutoRAGResult(BaseModel):
    """Result of evaluating a single configuration."""
    config: ParameterConfig
    precision_at_5: float
    recall_at_5: float
    mrr: float
    ndcg_at_10: float
    map_score: float
    context_relevance: float | None = None
    groundedness: float | None = None
    answer_relevance: float | None = None
    avg_latency_ms: float
    p95_latency_ms: float
    composite_score: float              # Взвешенная метрика

class AutoRAGRunner:
    """Run automated RAG optimization."""

    def __init__(
        self,
        components: Components,
        benchmark: BenchmarkDataset,
        eval_rag: bool = False,         # RAG Triad (медленно)
    ):
        ...

    async def run_grid(
        self,
        grid: ParameterGrid,
        progress_callback: Callable | None = None,
    ) -> list[AutoRAGResult]:
        """Run all configurations and collect results.

        For each config:
        1. Apply search parameters (no re-indexing for search-only params)
        2. Run EvalRunner on benchmark
        3. Compute composite score
        4. Log progress

        Returns sorted results (best first).
        """

    async def _apply_config(self, config: ParameterConfig) -> None:
        """Apply configuration to SearchManager and related components.

        Modifies:
        - search_settings.hybrid_vector_weight
        - search_settings.hybrid_graph_weight
        - search_settings.bm25_weight
        - search_settings.mmr_diversity_lambda
        - self_rag_settings.score_prefilter_threshold
        - Enables/disables reranker
        """

    def _compute_composite(self, result: AutoRAGResult) -> float:
        """Weighted composite metric.

        Default weights:
          MRR: 0.3 (most important for single-answer queries)
          Precision@5: 0.2
          NDCG@10: 0.2
          Latency penalty: 0.1 (normalized, lower is better)
          RAG Triad avg: 0.2 (if evaluated)
        """
```

### 20.5. Results Analyzer & Config Export

**Новый файл:** `src/pdf_framework/evaluation/autorag_analyzer.py`

```python
class AutoRAGAnalyzer:
    """Analyze AutoRAG results and export optimal config."""

    def __init__(self, results: list[AutoRAGResult]):
        ...

    def best_config(self) -> ParameterConfig:
        """Return config with highest composite score."""

    def best_per_metric(self) -> dict[str, ParameterConfig]:
        """Best config for each individual metric."""

    def comparison_table(self) -> str:
        """Markdown table comparing all configurations.

        | Config | Strategy | k | Reranker | MRR | P@5 | NDCG | Latency |
        |--------|----------|---|---------|-----|-----|------|---------|
        | cfg_01 | hybrid   | 5 | CE      | 0.82| 0.71| 0.78 | 1200ms  |
        | cfg_02 | vector   | 5 | none    | 0.65| 0.55| 0.60 | 200ms   |
        """

    def export_env(self, config: ParameterConfig, path: Path) -> None:
        """Export config as .env file.

        SEARCH__HYBRID_VECTOR_WEIGHT=0.5
        SEARCH__HYBRID_GRAPH_WEIGHT=0.2
        SEARCH__BM25_WEIGHT=0.3
        ...
        """

    def export_json(self, path: Path) -> None:
        """Export full results as JSON for further analysis."""

    def sensitivity_analysis(self) -> dict[str, float]:
        """Which parameters have the most impact on quality?

        Returns: {param_name: importance_score}
        Based on variance of composite score when only that param changes.
        """
```

### 20.6. CLI команды

**Модификация:** `src/cli/main.py`

```bash
# Генерация benchmark из проиндексированных чанков
pdf-framework benchmark generate --count 50 --output data/benchmarks/1c_v1.json

# Запуск AutoRAG (поиск-only, без переиндексации)
pdf-framework autorag run \
    --benchmark data/benchmarks/1c_v1.json \
    --strategies vector,hybrid,two_stage \
    --k 3,5,10 \
    --rerankers none,cross_encoder \
    --output data/autorag/results.json

# Запуск AutoRAG с RAG Triad (медленнее, точнее)
pdf-framework autorag run \
    --benchmark data/benchmarks/1c_v1.json \
    --eval-rag \
    --output data/autorag/results_with_rag.json

# Анализ результатов
pdf-framework autorag analyze --input data/autorag/results.json
# Output:
#   Best config: hybrid, k=5, cross_encoder (composite: 0.82)
#   Sensitivity: strategy (0.35), reranker (0.28), k (0.18), weights (0.12)

# Экспорт лучшей конфигурации
pdf-framework autorag export --input data/autorag/results.json --format env --output .env.optimal
```

### 20.7. UI страница AutoRAG

**Новый файл:** `src/ui/pages/autorag.py`

- Выбор benchmark dataset
- Конфигурация grid (чекбоксы стратегий, слайдеры k)
- Прогресс-бар выполнения (X/N конфигураций)
- Таблица результатов с сортировкой по метрикам
- График: Pareto front (quality vs latency)
- Кнопка "Применить лучшую конфигурацию"

---

## Модифицируемые файлы

| Файл | Изменение |
|------|-----------|
| `src/pdf_framework/evaluation/benchmark.py` | **NEW**: BenchmarkDataset + QuestionGenerator |
| `src/pdf_framework/evaluation/autorag.py` | **NEW**: ParameterGrid + ParameterConfig |
| `src/pdf_framework/evaluation/autorag_runner.py` | **NEW**: AutoRAGRunner |
| `src/pdf_framework/evaluation/autorag_analyzer.py` | **NEW**: ResultsAnalyzer + export |
| `data/benchmarks/1c_benchmark_v1.json` | **NEW**: Benchmark dataset (50+ questions) |
| `src/cli/main.py` | **MODIFY**: +`benchmark`, +`autorag` commands |
| `src/ui/pages/autorag.py` | **NEW**: AutoRAG UI page |
| `src/ui/app.py` | **MODIFY**: +AutoRAG tab |
| `src/pdf_framework/config.py` | **MODIFY**: +AutoRAGSettings |

## Настройки

```python
class AutoRAGSettings(BaseSettings):
    enabled: bool = True
    benchmark_dir: Path = PROJECT_ROOT / "data" / "benchmarks"
    results_dir: Path = PROJECT_ROOT / "data" / "autorag"
    composite_weights: dict = {
        "mrr": 0.3,
        "precision": 0.2,
        "ndcg": 0.2,
        "latency": 0.1,
        "rag_triad": 0.2,
    }
    max_configs: int = 100              # Лимит комбинаций
    parallel_eval: bool = False         # Параллельная оценка (осторожно с API rate limits)
```

## Верификация

1. `benchmark generate` → 50 вопросов из проиндексированных чанков
2. Ручная проверка: вопросы осмысленны, ответы корректны
3. `autorag run` с 3 стратегиями × 3 k → 9 конфигураций
4. Результаты показывают разницу в метриках между конфигурациями
5. `autorag analyze` → лучшая конфигурация + sensitivity анализ
6. `autorag export` → .env файл с оптимальными параметрами
7. Применение оптимальной конфигурации → улучшение метрик vs текущие
