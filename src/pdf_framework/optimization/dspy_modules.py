"""DSPy module wrappers for RAG pipeline components (Phase 34).

Each module wraps one LLM call with a DSPy Signature, enabling
MIPROv2 to automatically optimize prompts and bootstrap few-shot examples.

Modules:
- GraderModule: Document relevance grading (yes/no)
- RewriterModule: Query rewriting for better retrieval
- AnalyzerModule: Analytical question answering
- PlannerModule: Analysis planning (aspects, queries)
- ComparatorModule: Building comparison tables
- ConclusionModule: Generating conclusions from evidence
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    import dspy

    _DSPY_AVAILABLE = True
except ImportError:
    _DSPY_AVAILABLE = False
    logger.info("[DSPY] dspy-ai not installed, optimization disabled")


def is_dspy_available() -> bool:
    """Check if DSPy is installed."""
    return _DSPY_AVAILABLE


if _DSPY_AVAILABLE:
    # ---- Signatures ----

    class GraderSignature(dspy.Signature):
        """Grade whether a document chunk is relevant to the question.

        Given a question and a document chunk, determine if the chunk
        contains information relevant to answering the question.
        """

        question: str = dspy.InputField(desc="The user's question")
        document: str = dspy.InputField(desc="Document chunk to evaluate")
        relevance: str = dspy.OutputField(
            desc="'yes' if relevant, 'no' if not relevant"
        )

    class RewriterSignature(dspy.Signature):
        """Rewrite a search query to improve retrieval results.

        Given the original question and context about why retrieval failed,
        produce a better search query.
        """

        question: str = dspy.InputField(desc="Original search query")
        feedback: str = dspy.InputField(
            desc="Why the previous search was insufficient"
        )
        rewritten_query: str = dspy.OutputField(
            desc="Improved search query for better retrieval"
        )

    class AnalyzerSignature(dspy.Signature):
        """Answer a question analytically using provided context.

        Analyze the context to produce a comprehensive answer with
        references to source material.
        """

        question: str = dspy.InputField(desc="User question")
        context: str = dspy.InputField(desc="Retrieved context with sources")
        answer: str = dspy.OutputField(
            desc="Comprehensive analytical answer in Russian with source references [N]"
        )

    class PlannerSignature(dspy.Signature):
        """Create an analysis plan for a complex question.

        Determine question type, aspects to investigate, and search queries.
        """

        question: str = dspy.InputField(desc="User question to analyze")
        plan_json: str = dspy.OutputField(
            desc="JSON plan: {question_type, aspects, search_queries, entities_to_compare}"
        )

    class EvidenceSignature(dspy.Signature):
        """Extract structured evidence from document chunks.

        Given chunks and a question, extract factual evidence with sources.
        """

        question: str = dspy.InputField(desc="Question being investigated")
        aspects: str = dspy.InputField(desc="Aspects to cover")
        chunks: str = dspy.InputField(desc="Retrieved document chunks")
        evidence_json: str = dspy.OutputField(
            desc="JSON array of {fact, aspect, chunk_index, relevance}"
        )

    class ComparatorSignature(dspy.Signature):
        """Build a comparison table from evidence.

        Given evidence about multiple entities, create a structured comparison.
        """

        entities: str = dspy.InputField(desc="Entities to compare")
        criteria: str = dspy.InputField(desc="Comparison criteria")
        evidence: str = dspy.InputField(desc="Collected evidence facts")
        table_json: str = dspy.OutputField(
            desc="JSON comparison table: {rows: [{criterion, values: {entity: description}}]}"
        )

    class ConclusionSignature(dspy.Signature):
        """Generate a conclusion from evidence and analysis.

        Synthesize a structured answer with summary, analysis, and sources.
        """

        question: str = dspy.InputField(desc="Original question")
        evidence: str = dspy.InputField(desc="Collected evidence")
        comparison: str = dspy.InputField(desc="Comparison table (if applicable)")
        conclusion: str = dspy.OutputField(
            desc="Structured conclusion: summary + analysis + references"
        )

    # ---- Modules (wrapped with predict/forward) ----

    class GraderModule(dspy.Module):
        """DSPy module for document grading."""

        def __init__(self):
            super().__init__()
            self.predict = dspy.Predict(GraderSignature)

        def forward(self, question: str, document: str) -> dspy.Prediction:
            return self.predict(question=question, document=document)

    class RewriterModule(dspy.Module):
        """DSPy module for query rewriting."""

        def __init__(self):
            super().__init__()
            self.predict = dspy.ChainOfThought(RewriterSignature)

        def forward(self, question: str, feedback: str = "") -> dspy.Prediction:
            return self.predict(question=question, feedback=feedback)

    class AnalyzerModule(dspy.Module):
        """DSPy module for analytical answer generation."""

        def __init__(self):
            super().__init__()
            self.predict = dspy.ChainOfThought(AnalyzerSignature)

        def forward(self, question: str, context: str) -> dspy.Prediction:
            return self.predict(question=question, context=context)

    class PlannerModule(dspy.Module):
        """DSPy module for analysis planning."""

        def __init__(self):
            super().__init__()
            self.predict = dspy.ChainOfThought(PlannerSignature)

        def forward(self, question: str) -> dspy.Prediction:
            return self.predict(question=question)

    class EvidenceModule(dspy.Module):
        """DSPy module for evidence extraction."""

        def __init__(self):
            super().__init__()
            self.predict = dspy.ChainOfThought(EvidenceSignature)

        def forward(
            self, question: str, aspects: str, chunks: str
        ) -> dspy.Prediction:
            return self.predict(question=question, aspects=aspects, chunks=chunks)

    class ComparatorModule(dspy.Module):
        """DSPy module for comparison table generation."""

        def __init__(self):
            super().__init__()
            self.predict = dspy.ChainOfThought(ComparatorSignature)

        def forward(
            self, entities: str, criteria: str, evidence: str
        ) -> dspy.Prediction:
            return self.predict(
                entities=entities, criteria=criteria, evidence=evidence
            )

    class ConclusionModule(dspy.Module):
        """DSPy module for conclusion generation."""

        def __init__(self):
            super().__init__()
            self.predict = dspy.ChainOfThought(ConclusionSignature)

        def forward(
            self, question: str, evidence: str, comparison: str = ""
        ) -> dspy.Prediction:
            return self.predict(
                question=question, evidence=evidence, comparison=comparison
            )

else:
    # Stubs when DSPy is not installed

    class GraderModule:  # type: ignore[no-redef]
        pass

    class RewriterModule:  # type: ignore[no-redef]
        pass

    class AnalyzerModule:  # type: ignore[no-redef]
        pass

    class PlannerModule:  # type: ignore[no-redef]
        pass

    class EvidenceModule:  # type: ignore[no-redef]
        pass

    class ComparatorModule:  # type: ignore[no-redef]
        pass

    class ConclusionModule:  # type: ignore[no-redef]
        pass
