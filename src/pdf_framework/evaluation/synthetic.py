"""Synthetic Test Generator for RAG Evaluation (Phase 21.2).

Automatically generates test questions from documents.
Creates golden datasets for evaluation.

Based on RAGAS synthetic data generation.

Author: Claude Code
Version: 1.0.0 - Phase 21: RAGAS Evaluation
"""

import logging
from typing import Any

from anthropic import Anthropic
from pydantic import BaseModel, Field

from src.pdf_framework.config import Settings, get_settings
from src.pdf_framework.schemas.documents import DocumentChunk

logger = logging.getLogger(__name__)


class SyntheticQuestion(BaseModel):
    """A synthetically generated test question."""

    question: str
    answer: str = ""  # Expected answer
    context_chunk_id: str = ""
    question_type: str = ""  # "factual", "procedural", "conceptual"
    difficulty: str = "medium"  # "easy", "medium", "hard"


class SyntheticDataset(BaseModel):
    """A synthetically generated test dataset."""

    name: str
    source_document: str = ""
    questions: list[SyntheticQuestion] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SyntheticQuestionGenerator:
    """Generates synthetic test questions from document chunks.

    Uses LLM to create diverse question types:
    - Factual: What is X?
    - Procedural: How to do X?
    - Conceptual: Why does X work?
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-sonnet-4-5-20250929",
        settings: Settings | None = None,
    ):
        """Initialize the question generator.

        Args:
            api_key: Anthropic API key (empty = use env)
            model: Claude model for generation
            settings: Application settings
        """
        self._client = Anthropic(api_key=api_key or None)
        self._model = model
        self._settings = settings or get_settings()

    def generate_from_chunk(
        self,
        chunk: DocumentChunk,
        questions_per_chunk: int = 3,
    ) -> list[SyntheticQuestion]:
        """Generate questions from a single document chunk.

        Args:
            chunk: Document chunk to generate questions from
            questions_per_chunk: Number of questions to generate

        Returns:
            List of SyntheticQuestion objects
        """
        prompt = self._build_generation_prompt(chunk.content, questions_per_chunk)

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )

            result = response.content[0].text
            questions = self._parse_questions(result, chunk.id)

            logger.info(
                f"[SYNTHETIC] Generated {len(questions)} questions from chunk {chunk.id[:8]}..."
            )

            return questions

        except Exception as e:
            logger.error(f"[SYNTHETIC] Failed to generate questions: {e}")
            return []

    def generate_from_chunks(
        self,
        chunks: list[DocumentChunk],
        questions_per_chunk: int = 2,
        max_total_questions: int | None = None,
    ) -> SyntheticDataset:
        """Generate questions from multiple chunks.

        Args:
            chunks: Document chunks to generate questions from
            questions_per_chunk: Questions per chunk
            max_total_questions: Maximum total questions

        Returns:
            SyntheticDataset with generated questions
        """
        all_questions: list[SyntheticQuestion] = []

        for chunk in chunks:
            if max_total_questions and len(all_questions) >= max_total_questions:
                break

            questions = self.generate_from_chunk(chunk, questions_per_chunk)
            all_questions.extend(questions)

        # Truncate if needed
        if max_total_questions:
            all_questions = all_questions[:max_total_questions]

        # Get source document name
        source = chunks[0].metadata.get("source", "unknown") if chunks else "unknown"

        return SyntheticDataset(
            name=f"synthetic_{source.replace('/', '_')}",
            source_document=source,
            questions=all_questions,
            metadata={
                "total_chunks": len(chunks),
                "total_questions": len(all_questions),
                "questions_per_chunk": questions_per_chunk,
                "model_used": self._model,
            },
        )

    def _build_generation_prompt(self, content: str, num_questions: int) -> str:
        """Build prompt for question generation.

        Args:
            content: Document chunk content
            num_questions: Number of questions to generate

        Returns:
            Prompt string
        """
        prompt = f"""You are an expert at creating test questions for technical documentation.

**Document Content:**
{content[:2000]}

**Task:**
Generate {num_questions} diverse test questions based on this content.

Create a mix of:
1. **Factual questions**: "What is X?", "What are the components of Y?"
2. **Procedural questions**: "How to do X?", "What are the steps for Y?"
3. **Conceptual questions**: "Why does X work?", "What is the relationship between X and Y?"

**Requirements:**
- Questions must be answerable from the provided content
- Questions should vary in difficulty (easy, medium, hard)
- Include expected answers that can be verified from the content

**Output Format:**
Return a JSON object:
{{
    "questions": [
        {{
            "question": "What is the purpose of...",
            "answer": "Detailed answer based on content...",
            "type": "factual",
            "difficulty": "medium"
        }}
    ]
}}
"""

        return prompt

    def _parse_questions(self, result: str, chunk_id: str) -> list[SyntheticQuestion]:
        """Parse generated questions from LLM response.

        Args:
            result: LLM response text
            chunk_id: Source chunk ID

        Returns:
            List of SyntheticQuestion objects
        """
        import json

        try:
            start = result.find("{")
            end = result.rfind("}") + 1

            if start == -1 or end == 0:
                logger.warning("[SYNTHETIC] No JSON found in response")
                return []

            json_str = result[start:end]
            data = json.loads(json_str)

            questions = []
            for q in data.get("questions", []):
                question = SyntheticQuestion(
                    question=q["question"],
                    answer=q.get("answer", ""),
                    context_chunk_id=chunk_id,
                    question_type=q.get("type", "factual"),
                    difficulty=q.get("difficulty", "medium"),
                )
                questions.append(question)

            return questions

        except Exception as e:
            logger.warning(f"[SYNTHETIC] Failed to parse questions: {e}")
            return []


class GoldenDatasetGenerator:
    """Generates golden datasets for evaluation.

    Combines synthetic questions with human-verified examples.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-sonnet-4-5-20250929",
    ):
        """Initialize the golden dataset generator.

        Args:
            api_key: Anthropic API key
            model: Claude model for generation
        """
        self._generator = SyntheticQuestionGenerator(api_key=api_key, model=model)

    def create_golden_dataset(
        self,
        chunks: list[DocumentChunk],
        include_synthetic: bool = True,
        synthetic_ratio: float = 0.5,
        max_total: int = 100,
    ) -> SyntheticDataset:
        """Create a golden dataset with synthetic and human questions.

        Args:
            chunks: Document chunks
            include_synthetic: Include synthetic questions
            synthetic_ratio: Ratio of synthetic to human questions
            max_total: Maximum total questions

        Returns:
            SyntheticDataset
        """
        questions: list[SyntheticQuestion] = []

        # Add synthetic questions
        if include_synthetic:
            synthetic_count = int(max_total * synthetic_ratio)
            synthetic_dataset = self._generator.generate_from_chunks(
                chunks,
                questions_per_chunk=2,
                max_total_questions=synthetic_count,
            )
            questions.extend(synthetic_dataset.questions)

        # TODO: Load human questions from file

        # Create final dataset
        source = chunks[0].metadata.get("source", "unknown") if chunks else "unknown"

        return SyntheticDataset(
            name=f"golden_{source.replace('/', '_')}",
            source_document=source,
            questions=questions[:max_total],
            metadata={
                "synthetic_count": len([q for q in questions if q.answer]),
                "human_count": len([q for q in questions if not q.answer]),
                "total_questions": len(questions),
            },
        )


def generate_synthetic_questions(
    chunks: list[DocumentChunk],
    api_key: str = "",
    questions_per_chunk: int = 2,
) -> SyntheticDataset:
    """Convenience function to generate synthetic questions.

    Args:
        chunks: Document chunks
        api_key: Anthropic API key
        questions_per_chunk: Questions per chunk

    Returns:
        SyntheticDataset with generated questions
    """
    generator = SyntheticQuestionGenerator(api_key=api_key)
    return generator.generate_from_chunks(chunks, questions_per_chunk)
