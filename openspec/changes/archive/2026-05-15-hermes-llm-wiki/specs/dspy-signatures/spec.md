# Spec: dspy-signatures

**Change:** hermes-llm-wiki
**Phase:** 2
**Profile:** python-framework

## Контекст

Текущие LangGraph агенты `src/pdf_framework/agents/grader.py`, `rewriter.py`, `hallucination_check.py` используют f-string промпты с парсингом строковых ответов ("relevant"/"irrelevant", "grounded"/"not_grounded"). Это хрупко:
- Парсинг уязвим к вариациям вывода LLM ("Yes, it's relevant" vs "relevant")
- Нет type safety — grader может вернуть невалидный literal
- Ralph Wiggum self-correction реализован вручную в каждом агенте
- Нет eval-friendly контрактов (нельзя прогнать через DSPy Optimizer / MIPROv2)

`DSPy` (stanfordnlp/dspy, 33.7k⭐, MIT) — существующий skill `prompt-engineering` в проекте, но **не используется** в production коде (`grep -r "import dspy" src/pdf_framework/agents/` = 0 matches). DSPy предоставляет:
- `Signature` — типизированные input/output контракты
- `Predict` / `ChainOfThought` / `ProgramOfThought` — готовые модули
- `Suggest` / `Assert` — self-correction на уровне модуля (замена ручного Ralph Wiggum)
- Optimizers (MIPROv2, BootstrapFewShot) — автоматическая оптимизация промптов

Фаза 2 мигрирует 3 критических агента на DSPy Signatures **без изменения публичного API** (wrapper functions остаются). Ralph Wiggum логика переносится из custom кода в DSPy `Suggest` hooks.

Альтернативные `context_generator.py`, `entity_extractor.py`, `query_expansion.py`, `hyde.py`, `summarizer.py`, `enrichment.py` **НЕ трогаются** — они работают и eval их сложнее.

---

## ## ADDED REQ-1: GraderSignature

**Файл:** `src/pdf_framework/prompts/signatures.py` (новый)

DSPy Signature для document relevance grading.

### API

```python
# src/pdf_framework/prompts/signatures.py
from typing import Literal
import dspy

class GraderSignature(dspy.Signature):
    """Grade document relevance to user query.

    Determines whether a retrieved document is relevant to the user's query.
    Used in Self-RAG loop for filtering irrelevant retrievals before generation.
    """

    query: str = dspy.InputField(
        desc="User's question or search query"
    )
    document: str = dspy.InputField(
        desc="Retrieved document chunk (text content)"
    )
    relevance: Literal["relevant", "partial", "irrelevant"] = dspy.OutputField(
        desc=(
            "Document relevance: "
            "'relevant' if directly answers query, "
            "'partial' if contains related information, "
            "'irrelevant' if unrelated"
        )
    )
    reasoning: str = dspy.OutputField(
        desc="Brief explanation (1-2 sentences) of the relevance decision"
    )
```

### Usage в `grader.py`

```python
# src/pdf_framework/agents/grader.py (миграция)
import dspy
from src.pdf_framework.prompts.signatures import GraderSignature

_grader = dspy.Predict(GraderSignature)

def grade_document(query: str, document: str) -> GradeResult:
    """Public API — unchanged signature."""
    result = _grader(query=query, document=document)
    return GradeResult(
        relevance=result.relevance,  # type-safe Literal
        reasoning=result.reasoning,
    )
```

### Сценарий 1: Valid grade

**Given** query `"What is Qdrant?"` и document `"Qdrant is an open-source vector database..."`
**When** `grade_document(query, document)` вызывается
**Then** DSPy возвращает `{relevance: "relevant", reasoning: "Document directly defines Qdrant"}`
**And** `GradeResult.relevance` имеет тип `Literal["relevant","partial","irrelevant"]` — type-safe

### Сценарий 2: Ralph Wiggum self-correction через Suggest

**Given** LLM вернул невалидный `relevance = "yes"` (не в Literal)
**When** DSPy `Suggest` hook triggered
**Then** DSPy автоматически переформулирует prompt с hint "relevance must be one of: relevant, partial, irrelevant"
**And** retry (max 2) → валидный результат
**And** existing `grader.py` retry logic **удаляется** (заменена DSPy Suggest)

### Граничные условия

- LLM возвращает unexpected literal → DSPy Suggest retry
- LLM API timeout → propagate exception (не retry внутри DSPy)
- Document длиннее context window → truncate до (window - 500 tokens buffer)
- Empty document → `relevance: "irrelevant"` (DSPy автоматически)

### Ссылки

- `src/pdf_framework/agents/grader.py` — existing implementation (~180 LoC, будет сокращён)
- `.claude/skills/prompt-engineering/SKILL.md` — DSPy skill (уже в проекте)
- [stanfordnlp/dspy](https://github.com/stanfordnlp/dspy) — upstream

---

## ## ADDED REQ-2: HallucinationCheckSignature

**Файл:** `src/pdf_framework/prompts/signatures.py`

DSPy Signature для hallucination detection с **typed `grounded: bool`** вместо парсинга `"grounded"`/`"not_grounded"` строк.

### API

```python
class HallucinationCheckSignature(dspy.Signature):
    """Check if generated answer is grounded in provided context.

    Used after RAG generation to verify that the answer doesn't contain
    hallucinations not supported by retrieved documents.
    """

    answer: str = dspy.InputField(
        desc="Generated answer from LLM"
    )
    context: str = dspy.InputField(
        desc="Retrieved documents used for generation (concatenated)"
    )
    grounded: bool = dspy.OutputField(
        desc="True if all claims in answer are supported by context, False otherwise"
    )
    unsupported_claims: list[str] = dspy.OutputField(
        desc="List of specific claims from answer not found in context (empty if grounded=True)"
    )
    reasoning: str = dspy.OutputField(
        desc="Brief explanation (1-2 sentences)"
    )
```

### Сценарий 1: Grounded answer

**Given** context `"Qdrant supports HNSW indexing with M=16, ef=100"`
**And** answer `"Qdrant uses HNSW graph with parameters M=16 and ef=100"`
**When** `check_hallucination(answer, context)` вызывается
**Then** DSPy возвращает `{grounded: True, unsupported_claims: [], reasoning: "All claims verified"}`
**And** `grounded` типизирован как `bool` — no string parsing

### Сценарий 2: Hallucinated answer

**Given** context `"Qdrant supports HNSW indexing"`
**And** answer `"Qdrant supports HNSW, IVF, and PQ indexing with GPU acceleration"`
**When** `check_hallucination(answer, context)` вызывается
**Then** DSPy возвращает `{grounded: False, unsupported_claims: ["IVF indexing", "PQ indexing", "GPU acceleration"], reasoning: "Context only mentions HNSW"}`

### Граничные условия

- Empty answer → `grounded: True`, `unsupported_claims: []` (ничего проверять)
- Empty context → `grounded: False`, `unsupported_claims: [<все claims>]`
- Very long answer (>2000 chars) → chunked check (optional optimization)
- LLM возвращает `unsupported_claims` не в list format → DSPy парсит + Suggest retry

### Ссылки

- `src/pdf_framework/agents/hallucination_check.py` — existing (~200 LoC)

---

## ## ADDED REQ-3: RewriterSignature

**Файл:** `src/pdf_framework/prompts/signatures.py`

DSPy Signature для query rewriting с учётом conversation history. Использует `dspy.ChainOfThought` для explicit reasoning.

### API

```python
class RewriterSignature(dspy.Signature):
    """Rewrite user query using conversation history context.

    Resolves references ("it", "they"), expands abbreviations,
    makes implicit context explicit for better retrieval.
    """

    query: str = dspy.InputField(
        desc="Current user query (may contain pronouns, references)"
    )
    history: str = dspy.InputField(
        desc="Previous turns formatted as 'User: ... / Assistant: ...'"
    )
    rewritten: str = dspy.OutputField(
        desc="Standalone query with all references resolved"
    )
```

### Usage

```python
# src/pdf_framework/agents/rewriter.py
from src.pdf_framework.prompts.signatures import RewriterSignature

_rewriter = dspy.ChainOfThought(RewriterSignature)

def rewrite_query(query: str, history: list[Message]) -> str:
    history_str = format_history(history)
    result = _rewriter(query=query, history=history_str)
    return result.rewritten
```

### Сценарий 1: Pronoun resolution

**Given** history `"User: What is Qdrant? / Assistant: Vector database..."`
**And** query `"How does it compare to ChromaDB?"`
**When** `rewrite_query(query, history)` вызывается
**Then** DSPy `ChainOfThought` генерирует reasoning: `"'it' refers to Qdrant from previous turn"`
**And** `rewritten = "How does Qdrant compare to ChromaDB?"`

### Сценарий 2: Empty history passthrough

**Given** `history = []`
**And** `query = "What is RAG?"`
**When** rewrite вызывается
**Then** `rewritten = "What is RAG?"` (без изменений)

### Граничные условия

- History > 4000 tokens → truncate до последних 5 turns
- Query уже standalone → ChainOfThought возвращает identity (no change)
- Ambiguous reference → сохранить original + log warning

### Ссылки

- `src/pdf_framework/agents/rewriter.py` — existing (~150 LoC)

---

## ## MODIFIED REQ-4: Миграция src/pdf_framework/agents/

**Файлы:**
- `src/pdf_framework/agents/grader.py` (мигрировать)
- `src/pdf_framework/agents/rewriter.py` (мигрировать)
- `src/pdf_framework/agents/hallucination_check.py` (мигрировать)

**Было:** f-string промпты + custom parse + manual Ralph Wiggum retry
**Стало:** thin wrapper вокруг DSPy modules с сохранённым публичным API

### Принципы миграции

1. **Public API не меняется** — функции `grade_document()`, `check_hallucination()`, `rewrite_query()` сохраняют сигнатуры
2. **Ralph Wiggum удаляется** — заменяется DSPy `Suggest` hooks (max 2 retries по умолчанию)
3. **Existing tests остаются** — migration validation через `tests/integration/test_agents.py` регрессию
4. **LLM config через DSPy** — `dspy.configure(lm=dspy.Claude(model="claude-sonnet-4-5"))` в `src/pdf_framework/config/llm.py`
5. **Существующие метрики качества должны сохраниться или улучшиться** — регрессия <5% blocker

### Сценарий 1: grader.py migration

**Given** existing `grader.py` с f-string prompt и custom `_parse_grade()` функцией
**When** migration выполнена
**Then** `grader.py` содержит только `dspy.Predict(GraderSignature)` + public wrapper
**And** `grader.py` сокращён с ~180 LoC до ~50 LoC
**And** existing `test_grader.py` (pytest) проходит без изменений
**And** accuracy на eval dataset ≥ baseline (не хуже)

### Сценарий 2: Eval regression check

**Given** eval dataset `data/eval/bsl/bsl_eval_dataset.json` (100 queries)
**When** запущен `scripts/eval_agents_dspy.py --compare-baseline`
**Then** script сравнивает pre-migration vs post-migration metrics
**And** если grader precision drop >5% → **ROLLBACK** (exit non-zero)
**And** если precision sustained или better → PASS
**And** metrics сохранены в `data/eval/dspy_migration_report.json`

### Граничные условия

- DSPy config не установлен в `dspy.configure()` → RuntimeError на первом вызове → fail-fast
- LLM provider (Anthropic) недоступен → propagate exception (не retry)
- DSPy Suggest уходит в бесконечный цикл → max 2 retries enforced
- Ralph Wiggum тесты (если есть) → обновить на DSPy Suggest mocks

### Ссылки

- `src/pdf_framework/agents/grader.py` — migration target
- `src/pdf_framework/agents/rewriter.py` — migration target
- `src/pdf_framework/agents/hallucination_check.py` — migration target
- `src/pdf_framework/config/llm.py` — добавить `dspy.configure()`
- `tests/integration/test_agents.py` — regression protection

---

## ## ADDED REQ-5: DSPy LM configuration

**Файл:** `src/pdf_framework/config/llm.py` (расширение) или `src/pdf_framework/config/dspy_config.py` (новый)

Централизованная настройка DSPy для использования существующих LLM provider (Claude через Anthropic + Z.AI fallback через llm-rotation).

### API

```python
# src/pdf_framework/config/dspy_config.py
import dspy
from src.pdf_framework.config import Settings

def configure_dspy(settings: Settings) -> None:
    """Configure DSPy with existing LLM providers.

    Uses claude-sonnet-4-5 as default, falls back to Z.AI via llm-rotation on errors.
    """
    main_lm = dspy.Claude(
        model="claude-sonnet-4-5-20250929",
        api_key=settings.anthropic.api_key,
        max_tokens=2048,
    )
    dspy.configure(lm=main_lm)
```

### Сценарий 1: DSPy initialized on app startup

**Given** `src/api/dependencies/components.py` инициализирует Components
**When** вызывается `configure_dspy(settings)` при startup
**Then** `dspy.settings.lm` установлен в `dspy.Claude(model=...)`
**And** любой DSPy module (`dspy.Predict(GraderSignature)`) работает без дополнительной конфигурации

### Сценарий 2: Fallback на Z.AI

**Given** `main_lm` (Claude) возвращает rate limit error
**When** existing `llm-rotation` service catches и делегирует
**Then** DSPy получает retry через rotation layer (прозрачно для DSPy)
**And** `result.relevance` корректный

### Граничные условия

- `settings.anthropic.api_key` не установлен → RuntimeError на startup (fail-fast)
- Z.AI fallback не настроен → использовать только Claude
- DSPy не инициализирован, но `dspy.Predict` вызван → clear error message "Call configure_dspy() first"

### Ссылки

- `src/pdf_framework/config/_base.py` — `Settings` class
- `src/shared/llm_rotation/` — existing rotation service
- `src/api/dependencies/components.py` — DI container (call site)

---

## Регрессия

Фаза 2 **НЕ ДОЛЖНА** ломать:

- [ ] `test_grader.py`, `test_rewriter.py`, `test_hallucination_check.py` — regression tests
- [ ] Existing `context_generator.py`, `entity_extractor.py`, `query_expansion.py`, `hyde.py`, `summarizer.py`, `enrichment.py` — НЕ мигрируются в этой фазе
- [ ] Existing `src/shared/llm_rotation/` — не затрагивается, используется как fallback layer под DSPy
- [ ] Eval metrics на существующем `data/eval/` — must sustain or improve
- [ ] Ralph Wiggum state в `shared/ralph_state.py` — остаётся для других агентов, не трогается

## Новые тесты

```
tests/unit/pdf_framework/prompts/
  test_signatures.py              — GraderSignature/HallucinationCheckSignature/RewriterSignature Literal validation

tests/integration/
  test_grader_dspy.py             — grader migration integration
  test_rewriter_dspy.py           — rewriter migration integration
  test_hallucination_dspy.py      — hallucination migration integration
  test_dspy_configuration.py      — configure_dspy() at startup

tests/eval/
  test_dspy_regression.py         — compare pre/post migration metrics на eval dataset
```

**Coverage target:** signatures.py ≥95%, migrated agents ≥90%. Eval regression: ≤5% drop = rollback.
