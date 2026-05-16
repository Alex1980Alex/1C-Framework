"""DSPy Signatures for RAG agent nodes (Hermes Phase 2).

Typed contracts for LLM calls in grader, rewriter, and hallucination_checker.
Replaces f-string prompts with DSPy Signatures for optimization and consistency.

Existing signatures in optimization/dspy_modules.py are used by GEPA optimizer
(DSPy ≥3.0, migrated from MIPROv2 per roadmap 260509 §3.4).
These refined signatures add 3-level grading and typed hallucination checking.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    import dspy

    _DSPY_AVAILABLE = True
except ImportError:
    _DSPY_AVAILABLE = False
    logger.debug("dspy-ai not installed. Signature-based prompts unavailable.")


def is_dspy_available() -> bool:
    return _DSPY_AVAILABLE


if _DSPY_AVAILABLE:

    class GraderSignature(dspy.Signature):
        """Grade document relevance with 3-level scoring."""

        question: str = dspy.InputField(desc="The user question to evaluate against")
        document: str = dspy.InputField(desc="The document text to grade for relevance")
        relevance_score: str = dspy.OutputField(desc="One of: 'relevant', 'partial', 'irrelevant'")

    class HallucinationCheckSignature(dspy.Signature):
        """Check if answer is grounded in provided context."""

        answer: str = dspy.InputField(desc="The generated answer to verify")
        context: str = dspy.InputField(desc="The source context the answer should be grounded in")
        grounded: bool = dspy.OutputField(
            desc="Whether the answer is fully grounded in the context"
        )
        reasoning: str = dspy.OutputField(desc="Explanation of the grounding assessment")

    class RewriterSignature(dspy.Signature):
        """Rewrite query for better retrieval results."""

        query: str = dspy.InputField(desc="The original query to rewrite")
        history: str = dspy.InputField(desc="Summary of previously retrieved irrelevant documents")
        rewritten_query: str = dspy.OutputField(
            desc="An improved query designed to retrieve more relevant results"
        )

    async def async_predict(signature_class: type, **kwargs: Any) -> dict[str, Any]:
        """Run dspy.Predict asynchronously via thread pool."""
        if not _DSPY_AVAILABLE:
            raise ImportError("dspy-ai is required but not installed")

        predictor = dspy.Predict(signature_class)
        result = await asyncio.to_thread(predictor, **kwargs)
        return {name: getattr(result, name) for name in signature_class.output_fields}

    async def async_chain_of_thought(signature_class: type, **kwargs: Any) -> dict[str, Any]:
        """Run dspy.ChainOfThought asynchronously via thread pool."""
        if not _DSPY_AVAILABLE:
            raise ImportError("dspy-ai is required but not installed")

        cot = dspy.ChainOfThought(signature_class)
        result = await asyncio.to_thread(cot, **kwargs)
        return {name: getattr(result, name) for name in signature_class.output_fields}

else:

    class GraderSignature:  # type: ignore[no-redef]
        pass

    class HallucinationCheckSignature:  # type: ignore[no-redef]
        pass

    class RewriterSignature:  # type: ignore[no-redef]
        pass

    async def async_predict(signature_class: type, **kwargs: Any) -> dict[str, Any]:
        raise ImportError("dspy-ai is required but not installed")

    async def async_chain_of_thought(signature_class: type, **kwargs: Any) -> dict[str, Any]:
        raise ImportError("dspy-ai is required but not installed")
