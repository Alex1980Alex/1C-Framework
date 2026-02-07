"""Sub-Question Decomposer for Adaptive RAG.

Breaks complex queries into simpler sub-questions for independent retrieval.

Author: Claude Code
Version: 0.9.0 - Phase 8.3: Sub-Question Decomposer
"""

import logging
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)


class SubQuestionDecomposer:
    """
    Decomposes complex queries into simpler sub-questions.

    For complex queries (comparisons, multi-step analysis),
    breaks into 2-4 sub-questions that can be answered independently.
    """

    def __init__(
        self,
        llm: ChatAnthropic | None = None,
        model: str = "claude-haiku-4-5-20251001",
        max_sub_questions: int = 4,
    ):
        """
        Initialize sub-question decomposer.

        Args:
            llm: LLM for decomposition (default: Haiku)
            model: Model name
            max_sub_questions: Maximum number of sub-questions
        """
        self._llm = llm or ChatAnthropic(model=model, temperature=0.0, max_tokens=1024)
        self._max_sub_questions = max_sub_questions
        self._parser = StrOutputParser()

    async def decompose(self, query: str) -> list[str]:
        """
        Decompose a complex query into simpler sub-questions.

        Args:
            query: Complex user query

        Returns:
            List of sub-questions (2-4 items)
        """
        if not query.strip():
            return []

        try:
            sub_questions = await self._decompose_with_llm(query)

            logger.info(
                f"[DECOMPOSER] Decomposed query into {len(sub_questions)} sub-questions: "
                f"[{'][']['".join([q[:30] + '...' for q in sub_questions])}]"
            )

            return sub_questions

        except Exception as e:
            logger.error(f"[DECOMPOSER] Error decomposing query: {e}")
            # Fallback: return original query as single sub-question
            return [query]

    async def _decompose_with_llm(self, query: str) -> list[str]:
        """Decompose query using LLM."""
        prompt = self._get_decomposition_prompt(query)

        messages = [
            SystemMessage(content=self._get_system_prompt()),
            HumanMessage(content=prompt),
        ]

        response = await self._llm.ainvoke(messages)
        text = self._parser.invoke(response).strip()

        return self._parse_sub_questions(text)

    async def synthesize(
        self,
        original_query: str,
        sub_answers: list[str],
        search_contexts: list[Any] | None = None,
    ) -> str:
        """
        Synthesize answers from sub-questions into a comprehensive response.

        Args:
            original_query: Original complex query
            sub_answers: Answers to each sub-question
            search_contexts: Optional search contexts for reference

        Returns:
            Synthesized comprehensive answer
        """
        if not sub_answers:
            return "Unable to answer the question with the available information."

        if len(sub_answers) == 1:
            return sub_answers[0]

        try:
            synthesized = await self._synthesize_with_llm(original_query, sub_answers)

            logger.info(
                f"[DECOMPOSER] Synthesized {len(sub_answers)} sub-answers "
                f"into answer ({len(synthesized)} chars)"
            )

            return synthesized

        except Exception as e:
            logger.error(f"[DECOMPOSER] Error synthesizing: {e}")
            # Fallback: join sub-answers
            return "\n\n".join(
                f"Sub-question {i + 1}: {answer}"
                for i, answer in enumerate(sub_answers)
            )

    def _get_decomposition_prompt(self, query: str) -> str:
        """Build decomposition prompt for a query."""
        return f"""Break this complex query into {self._max_sub_questions} simpler sub-questions that can be answered independently.

Original query: {query}

Guidelines:
- Each sub-question should be self-contained and answerable
- Break down comparisons into separate questions for each side
- Break down multi-part questions into individual questions
- Keep sub-questions focused and specific
- Maximum {self._max_sub_questions} sub-questions

Return each sub-question on a new line, starting with 1., 2., etc."""

    def _get_system_prompt(self) -> str:
        """Get system prompt for decomposition."""
        return """You are an expert at breaking down complex questions into simpler, manageable sub-questions.

Your task:
1. Analyze the complex query
2. Identify the key components or aspects
3. Create 2-4 focused sub-questions
4. Each sub-question should be independently answerable
5. Return one sub-question per line, numbered 1., 2., etc.

Examples:
Query: "Compare PostgreSQL and MySQL"
1. "What are the key features of PostgreSQL?"
2. "What are the key features of MySQL?"
3. "How do PostgreSQL and MySQL differ in performance?"
4. "How do they differ in licensing?"

Query: "List all authentication methods and their pros/cons"
1. "What authentication methods are available?"
2. "What are the pros and cons of password-based authentication?"
3. "What are the pros and cons of token-based authentication?"
4. "What are the pros and cons of certificate-based authentication?"

Be precise and specific. Each sub-question should stand alone."""

    def _parse_sub_questions(self, text: str) -> list[str]:
        """Parse LLM response into list of sub-questions."""
        lines = text.strip().split("\n")

        sub_questions = []
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Remove numbering prefixes (1., 2., etc.)
            line = line.lstrip("0123456789.-) ")
            line = line.lstrip("•_- ")

            if line:
                sub_questions.append(line)

            if len(sub_questions) >= self._max_sub_questions:
                break

        return sub_questions

    def _get_synthesis_prompt(self, original_query: str, sub_answers: list[str]) -> str:
        """Build synthesis prompt."""
        answers_text = "\n\n".join(
            f"Sub-question {i + 1}: {answer}"
            for i, answer in enumerate(sub_answers)
        )

        return f"""Synthesize the sub-question answers into a comprehensive response to the original question.

Original question: {original_query}

Sub-question answers:
{answers_text}

Synthesize a comprehensive answer that:
1. Directly addresses the original question
2. Integrates information from all sub-answers
3. Is well-structured and easy to follow
4. Maintains factual accuracy

Provide the synthesized answer:"""

    async def _synthesize_with_llm(
        self,
        original_query: str,
        sub_answers: list[str],
    ) -> str:
        """Synthesize using LLM."""
        prompt = self._get_synthesis_prompt(original_query, sub_answers)

        messages = [
            SystemMessage(
                content="You are an expert at synthesizing information from multiple sources into coherent answers."
            ),
            HumanMessage(content=prompt),
        ]

        response = await self._llm.ainvoke(messages)
        return self._parser.invoke(response).strip()

    def should_decompose(self, classification) -> bool:
        """
        Determine if a query should be decomposed based on classification.

        Args:
            classification: Query classification

        Returns:
            True if decomposition is recommended
        """
        # Decompose for complex queries with high confidence
        return (
            classification.complexity == "complex"
            and classification.confidence > 0.7
        )
