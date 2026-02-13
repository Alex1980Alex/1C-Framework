"""RAGAS Integration for RAG Evaluation (Phase 21).

Implements standard RAG evaluation metrics:
- Context Precision: How relevant is the retrieved context?
- Faithfulness: How well does the answer adhere to the context?
- Answer Relevancy: How relevant is the answer to the question?

Based on RAGAS evaluation framework.

Author: Claude Code
Version: 1.0.0 - Phase 21: RAGAS Evaluation
"""

import logging
from typing import Any

from anthropic import Anthropic
from pydantic import BaseModel, Field

from src.pdf_framework.config import Settings, get_settings
from src.pdf_framework.schemas.documents import SearchResult

logger = logging.getLogger(__name__)


class RAGASEvaluation(BaseModel):
    """Result of RAGAS evaluation."""

    context_precision: float = 0.0
    faithfulness: float = 0.0
    answer_relevancy: float = 0.0
    average_score: float = 0.0

    # Detailed breakdown
    context_precision_details: str = ""
    faithfulness_details: str = ""
    answer_relevancy_details: str = ""

    # Metadata
    model_used: str = ""
    evaluation_time_ms: float = 0.0


class RAGASEvaluator:
    """Evaluates RAG outputs using RAGAS metrics.

    Uses LLM-as-a-judge to assess:
    1. Context Precision: Is retrieved context relevant to question?
    2. Faithfulness: Does answer follow from context?
    3. Answer Relevancy: Is answer relevant to question?
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-sonnet-4-5-20250929",
        settings: Settings | None = None,
    ):
        """Initialize the RAGAS evaluator.

        Args:
            api_key: Anthropic API key (empty = use env)
            model: Claude model for evaluation
            settings: Application settings
        """
        self._client = Anthropic(api_key=api_key or None)
        self._model = model
        self._settings = settings or get_settings()

    def evaluate(
        self,
        question: str,
        retrieved_context: list[str],
        answer: str,
        ground_truth: str | None = None,
    ) -> RAGASEvaluation:
        """Evaluate a RAG output.

        Args:
            question: User question
            retrieved_context: Retrieved context chunks
            answer: Generated answer
            ground_truth: Expected answer (optional, for reference)

        Returns:
            RAGASEvaluation with all metrics
        """
        import time

        t0 = time.time()

        # Evaluate each metric
        context_precision = self._evaluate_context_precision(
            question, retrieved_context
        )

        faithfulness = self._evaluate_faithfulness(
            question, retrieved_context, answer
        )

        answer_relevancy = self._evaluate_answer_relevancy(
            question, answer
        )

        # Calculate average
        scores = [context_precision, faithfulness, answer_relevancy]
        average = sum(scores) / len(scores) if scores else 0.0

        elapsed_ms = (time.time() - t0) * 1000

        evaluation = RAGASEvaluation(
            context_precision=context_precision,
            faithfulness=faithfulness,
            answer_relevancy=answer_relevancy,
            average_score=average,
            model_used=self._model,
            evaluation_time_ms=elapsed_ms,
        )

        logger.info(
            f"[RAGAS] Evaluated: Context={context_precision:.2f}, "
            f"Faithfulness={faithfulness:.2f}, Relevancy={answer_relevancy:.2f}"
        )

        return evaluation

    def _evaluate_context_precision(
        self,
        question: str,
        retrieved_context: list[str],
    ) -> float:
        """Evaluate if retrieved context is relevant to question.

        Args:
            question: User question
            retrieved_context: Retrieved chunks

        Returns:
            Score 0-1
        """
        if not retrieved_context:
            return 0.0

        prompt = f"""Evaluate the relevance of retrieved context to a question.

**Question:**
{question}

**Retrieved Context:**
{self._format_context(retrieved_context)}

**Task:**
Rate how relevant the retrieved context is to answering the question.

Consider:
1. Does the context contain information needed to answer the question?
2. Is the context directly related or tangential?
3. Is there irrelevant or distracting information?

**Output Format:**
Return a JSON object:
{{
    "score": 0.85,
    "reasoning": "Brief explanation of the score"
}}

**Scoring Guidelines:**
- 1.0: Perfectly relevant, contains all needed information
- 0.7-0.9: Highly relevant with minor irrelevant parts
- 0.4-0.6: Somewhat relevant, significant tangential info
- 0.1-0.3: Mostly irrelevant
- 0.0: Completely irrelevant
"""

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            result = self._parse_score(response.content[0].text)
            return result

        except Exception as e:
            logger.warning(f"[RAGAS] Context precision evaluation failed: {e}")
            return 0.5  # Neutral score

    def _evaluate_faithfulness(
        self,
        question: str,
        retrieved_context: list[str],
        answer: str,
    ) -> float:
        """Evaluate if answer is faithful to context (no hallucinations).

        Args:
            question: User question
            retrieved_context: Source context
            answer: Generated answer

        Returns:
            Score 0-1
        """
        prompt = f"""Evaluate if an answer is faithful to the provided context.

**Question:**
{question}

**Context:**
{self._format_context(retrieved_context)}

**Answer:**
{answer}

**Task:**
Determine if the answer is faithful to the context - i.e., all claims
in the answer are supported by the context without hallucination.

Check for:
1. Factual claims not supported by context
2. Contradictions with the context
3. Unsupported details or specifications

**Output Format:**
Return a JSON object:
{{
    "score": 0.90,
    "reasoning": "Brief explanation"
}}

**Scoring Guidelines:**
- 1.0: All claims fully supported by context
- 0.7-0.9: Mostly supported, minor unsupported details
- 0.4-0.6: Some claims not supported or contradictory
- 0.1-0.3: Major hallucinations or contradictions
- 0.0: Answer completely unrelated to context
"""

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            result = self._parse_score(response.content[0].text)
            return result

        except Exception as e:
            logger.warning(f"[RAGAS] Faithfulness evaluation failed: {e}")
            return 0.5

    def _evaluate_answer_relevancy(
        self,
        question: str,
        answer: str,
    ) -> float:
        """Evaluate if answer is relevant to question.

        Args:
            question: User question
            answer: Generated answer

        Returns:
            Score 0-1
        """
        prompt = f"""Evaluate the relevance of an answer to a question.

**Question:**
{question}

**Answer:**
{answer}

**Task:**
Rate how relevant and complete the answer is to the question.

Consider:
1. Does the answer directly address the question?
2. Is the answer complete or missing key information?
3. Is the answer concise or verbose with irrelevant content?

**Output Format:**
Return a JSON object:
{{
    "score": 0.80,
    "reasoning": "Brief explanation"
}}

**Scoring Guidelines:**
- 1.0: Perfectly relevant and complete
- 0.7-0.9: Highly relevant with minor gaps
- 0.4-0.6: Somewhat relevant, incomplete
- 0.1-0.3: Mostly irrelevant
- 0.0: Completely irrelevant or refusal to answer
"""

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )

            result = self._parse_score(response.content[0].text)
            return result

        except Exception as e:
            logger.warning(f"[RAGAS] Answer relevancy evaluation failed: {e}")
            return 0.5

    def _format_context(self, context: list[str]) -> str:
        """Format context list for prompts.

        Args:
            context: List of context strings

        Returns:
            Formatted context string
        """
        if not context:
            return "(No context provided)"

        formatted = []
        for i, ctx in enumerate(context):
            formatted.append(f"[Context {i + 1}]\n{ctx[:500]}")

        return "\n\n".join(formatted)

    def _parse_score(self, response: str) -> float:
        """Parse score from LLM response.

        Args:
            response: LLM response text

        Returns:
            Parsed score 0-1
        """
        import json

        try:
            start = response.find("{")
            end = response.rfind("}") + 1

            if start == -1 or end == 0:
                # Try to extract number directly
                import re
                match = re.search(r'score["\s:]+([0-9.]+)', response)
                if match:
                    return float(match.group(1))
                return 0.5

            json_str = response[start:end]
            data = json.loads(json_str)

            score = float(data.get("score", 0.5))
            return max(0.0, min(1.0, score))  # Clamp to [0, 1]

        except Exception as e:
            logger.warning(f"[RAGAS] Failed to parse score: {e}")
            return 0.5

    def evaluate_batch(
        self,
        examples: list[dict[str, Any]],
    ) -> list[RAGASEvaluation]:
        """Evaluate multiple RAG examples.

        Args:
            examples: List of dicts with 'question', 'context', 'answer'

        Returns:
            List of RAGASEvaluation results
        """
        evaluations = []

        for example in examples:
            evaluation = self.evaluate(
                question=example.get("question", ""),
                retrieved_context=example.get("context", []),
                answer=example.get("answer", ""),
                ground_truth=example.get("ground_truth"),
            )
            evaluations.append(evaluation)

        return evaluations


def evaluate_rag(
    question: str,
    context: list[str],
    answer: str,
    api_key: str = "",
) -> RAGASEvaluation:
    """Convenience function for RAGAS evaluation.

    Args:
        question: User question
        context: Retrieved context chunks
        answer: Generated answer
        api_key: Anthropic API key

    Returns:
        RAGASEvaluation with metrics
    """
    evaluator = RAGASEvaluator(api_key=api_key)
    return evaluator.evaluate(question, context, answer)
