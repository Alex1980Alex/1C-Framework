"""Research Planner for Deep Research Agent (Phase 19).

Classifies query complexity and generates sub-question plans.
Works with or without an LLM — uses heuristics when llm=None.

Author: Claude Code
Version: 1.0.0 - Phase 19: Deep Research Agent
"""

import logging
import re
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Heuristic keywords for deep research detection
_COMPLEX_KEYWORDS = {
    "сравн", "отличи", "различи", "анализ", "механизм", "цикл",
    "взаимосвяз", "архитектур", "vs", "versus", "compare", "contrast",
    "принцип работы", "жизненный цикл", "все типы", "обзор всех",
    "преимущества и недостатки", "плюсы и минусы",
}
_MULTI_STEP_PATTERNS = [
    r"от .+ до .+",  # "от создания до записи"
    r"опиши.+цикл",
    r"сравн.+(и|с) ",
    r"как.+связан.+с",
]


class SubQuestion(BaseModel):
    """A sub-question in a research plan."""

    question: str
    strategy: str = "hybrid"
    priority: int = 1


class ResearchPlan(BaseModel):
    """A plan for deep research."""

    original_question: str
    complexity: str = "simple"  # "simple", "moderate", "complex"
    sub_questions: list[SubQuestion] = Field(default_factory=list)
    estimated_steps: int = 1


class ResearchPlanner:
    """Classify complexity and generate research plans."""

    def __init__(self, llm: Any = None, api_key: str = "", base_url: str = ""):
        self._llm = llm
        self._api_key = api_key
        self._base_url = base_url

    async def should_use_deep_research(self, question: str) -> bool:
        """Determine if a question needs deep research (multiple sub-searches)."""
        q_lower = question.lower()

        # Short/simple questions → not deep
        word_count = len(question.split())
        if word_count <= 5:
            return False

        # Check for complexity keywords
        for kw in _COMPLEX_KEYWORDS:
            if kw in q_lower:
                return True

        # Check for multi-step patterns
        for pattern in _MULTI_STEP_PATTERNS:
            if re.search(pattern, q_lower):
                return True

        # Long questions with conjunctions suggest complexity
        if word_count > 12 and any(c in q_lower for c in [" и ", " или ", " а также "]):
            return True

        return False

    async def create_plan(self, question: str) -> ResearchPlan:
        """Create a research plan with sub-questions."""
        if self._llm is not None:
            return await self._create_plan_with_llm(question)
        return self._create_plan_heuristic(question)

    def _create_plan_heuristic(self, question: str) -> ResearchPlan:
        """Create plan using heuristic decomposition."""
        q_lower = question.lower()
        sub_questions: list[SubQuestion] = []

        # Detect comparison
        is_comparison = any(kw in q_lower for kw in ["сравн", "отличи", "различи"])
        is_lifecycle = any(kw in q_lower for kw in ["цикл", "от ", "этап", "шаг"])
        is_overview = any(kw in q_lower for kw in ["все типы", "обзор", "перечисл"])

        if is_comparison:
            # Extract entities being compared
            parts = re.split(r"\s+и\s+|\s+с\s+|\s+от\s+", question, maxsplit=1)
            for i, part in enumerate(parts):
                sub_questions.append(SubQuestion(
                    question=f"Что такое {part.strip('?., ')}?",
                    strategy="hybrid",
                    priority=i + 1,
                ))
            sub_questions.append(SubQuestion(
                question=question,
                strategy="graphrag_local",
                priority=len(parts) + 1,
            ))
        elif is_lifecycle:
            sub_questions = [
                SubQuestion(question=question, strategy="hybrid", priority=1),
                SubQuestion(question=f"Какие этапы включает процесс в контексте: {question}?", strategy="bm25", priority=2),
            ]
        elif is_overview:
            sub_questions = [
                SubQuestion(question=question, strategy="hybrid", priority=1),
                SubQuestion(question=question, strategy="graphrag_local", priority=2),
            ]
        else:
            # Generic decomposition
            sub_questions = [
                SubQuestion(question=question, strategy="hybrid", priority=1),
                SubQuestion(question=f"Связанные понятия: {question}", strategy="vector", priority=2),
            ]

        # Determine complexity
        if len(sub_questions) >= 3:
            complexity = "complex"
        elif len(sub_questions) >= 2:
            complexity = "moderate"
        else:
            complexity = "simple"

        # Ensure 2-4 sub-questions
        if len(sub_questions) < 2:
            sub_questions.append(SubQuestion(
                question=f"Дополнительный контекст: {question}",
                strategy="vector",
                priority=2,
            ))
        sub_questions = sub_questions[:4]

        return ResearchPlan(
            original_question=question,
            complexity=complexity,
            sub_questions=sub_questions,
            estimated_steps=len(sub_questions),
        )

    async def _create_plan_with_llm(self, question: str) -> ResearchPlan:
        """Create plan using LLM decomposition."""
        # Fallback to heuristic if LLM call fails
        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content=(
                    "Decompose the following question into 2-4 sub-questions for research. "
                    "For each sub-question suggest a strategy: vector, hybrid, bm25, graphrag_local, or adaptive. "
                    "Also classify complexity as: simple, moderate, or complex. "
                    "Reply in JSON: {\"complexity\": \"...\", \"sub_questions\": [{\"question\": \"...\", \"strategy\": \"...\"}]}"
                )),
                HumanMessage(content=question),
            ]
            response = await self._llm.ainvoke(messages)
            import json
            text = response.content if isinstance(response.content, str) else response.content[0].text
            data = json.loads(text[text.find("{"):text.rfind("}") + 1])

            subs = [
                SubQuestion(question=sq["question"], strategy=sq.get("strategy", "hybrid"), priority=i + 1)
                for i, sq in enumerate(data.get("sub_questions", []))
            ]
            return ResearchPlan(
                original_question=question,
                complexity=data.get("complexity", "moderate"),
                sub_questions=subs[:4] or [SubQuestion(question=question, strategy="hybrid")],
                estimated_steps=len(subs),
            )
        except Exception as e:
            logger.warning(f"[PLANNER] LLM plan failed, falling back to heuristic: {e}")
            return self._create_plan_heuristic(question)
