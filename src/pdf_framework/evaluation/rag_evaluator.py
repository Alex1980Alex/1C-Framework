"""RAG Triad evaluator (LLM-as-a-Judge).

Phase 4: Evaluates RAG quality on three dimensions:
  - Context Relevance: are the retrieved contexts relevant to the query?
  - Groundedness: is the answer grounded in the provided contexts?
  - Answer Relevance: does the answer actually address the query?

Each metric returns a float in [0.0, 1.0].
"""

import logging

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.pdf_framework.config import AgentSettings

logger = logging.getLogger(__name__)

_SYSTEM = "You are an evaluation judge. Return ONLY a single number between 0.0 and 1.0."

_CONTEXT_RELEVANCE_PROMPT = """Rate how relevant the following contexts are to the query.
0.0 = completely irrelevant, 1.0 = perfectly relevant.

Query: {query}

Contexts:
{contexts}

Return ONLY a number between 0.0 and 1.0."""

_GROUNDEDNESS_PROMPT = """Rate how well the answer is grounded in (supported by) the contexts.
0.0 = answer contradicts or has no support, 1.0 = fully supported by contexts.

Answer: {answer}

Contexts:
{contexts}

Return ONLY a number between 0.0 and 1.0."""

_ANSWER_RELEVANCE_PROMPT = """Rate how relevant and helpful the answer is to the query.
0.0 = completely off-topic, 1.0 = directly and fully answers the query.

Query: {query}

Answer: {answer}

Return ONLY a number between 0.0 and 1.0."""


class RAGEvaluator:
    """LLM-as-a-Judge for RAG quality evaluation."""

    def __init__(
        self,
        settings: AgentSettings | None = None,
        api_key: str = "",
    ):
        self._settings = settings or AgentSettings()
        llm_kwargs: dict = {
            "model": self._settings.model,
            "temperature": 0.0,
            "max_tokens": 16,
            "api_key": api_key or None,
        }
        if self._settings.base_url:
            llm_kwargs["base_url"] = self._settings.base_url
        self._llm = ChatAnthropic(**llm_kwargs)

    async def _judge(self, prompt: str) -> float:
        """Send a judge prompt and parse the numeric response."""
        messages = [
            SystemMessage(content=_SYSTEM),
            HumanMessage(content=prompt),
        ]
        text = ""
        try:
            response = await self._llm.ainvoke(messages)
            if isinstance(response.content, str):
                text = response.content.strip()
            elif isinstance(response.content, list):
                parts = []
                for block in response.content:
                    if isinstance(block, dict):
                        parts.append(block.get("text", ""))
                    elif hasattr(block, "text"):
                        parts.append(getattr(block, "text"))
                    else:
                        parts.append(str(block))
                text = "".join(parts).strip()
            else:
                text = str(response.content).strip()

            score = float(text)
            return max(0.0, min(1.0, score))
        except (ValueError, TypeError) as e:
            logger.warning("Failed to parse judge score: %s (response: %s)", e, text)
            return 0.0
        except Exception as e:
            logger.error("RAG evaluation LLM call failed: %s", e)
            return 0.0

    async def evaluate_context_relevance(
        self, query: str, contexts: list[str],
    ) -> float:
        """Rate how relevant retrieved contexts are to the query."""
        if not contexts:
            return 0.0
        contexts_text = "\n---\n".join(
            f"[{i+1}] {c[:500]}" for i, c in enumerate(contexts)
        )
        return await self._judge(
            _CONTEXT_RELEVANCE_PROMPT.format(query=query, contexts=contexts_text),
        )

    async def evaluate_groundedness(
        self, answer: str, contexts: list[str],
    ) -> float:
        """Rate how well the answer is supported by the contexts."""
        if not answer or not contexts:
            return 0.0
        contexts_text = "\n---\n".join(
            f"[{i+1}] {c[:500]}" for i, c in enumerate(contexts)
        )
        return await self._judge(
            _GROUNDEDNESS_PROMPT.format(answer=answer, contexts=contexts_text),
        )

    async def evaluate_answer_relevance(
        self, query: str, answer: str,
    ) -> float:
        """Rate how relevant the answer is to the query."""
        if not answer:
            return 0.0
        return await self._judge(
            _ANSWER_RELEVANCE_PROMPT.format(query=query, answer=answer),
        )
