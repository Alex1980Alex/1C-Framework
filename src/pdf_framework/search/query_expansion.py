"""Query expansion module for improving search recall.

Phase 2.3: Three expansion methods:
1. LLM expansion — generate alternative query phrasings via LLM
2. Synonym expansion — Russian morphological forms via pymorphy3
3. HyDE — Hypothetical Document Embeddings
"""

import logging
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.pdf_framework.config import AgentSettings

logger = logging.getLogger(__name__)

_EXPANSION_PROMPT = """Generate {n} alternative phrasings for the following search query.
Each alternative should capture the same intent but use different words or structure.
Return ONLY the alternatives, one per line, without numbering or bullets.

Query: {query}"""

_HYDE_PROMPT = """Write a short passage (3-5 sentences) that would be a perfect answer
to the following question. Write in the same language as the question.
Do not include any preamble — just the answer text.

Question: {query}"""


class QueryExpander:
    """Expand search queries to improve recall.

    Supports LLM-based expansion, morphological synonyms, and HyDE.
    """

    def __init__(
        self,
        settings: AgentSettings | None = None,
        api_key: str = "",
    ):
        self._settings = settings or AgentSettings()
        llm_kwargs: dict = {
            "model": self._settings.model,
            "temperature": 0.7,
            "max_tokens": 512,
            "api_key": api_key or None,
        }
        if self._settings.base_url:
            llm_kwargs["base_url"] = self._settings.base_url
        self._llm = ChatAnthropic(**llm_kwargs)

    async def expand(
        self,
        query: str,
        method: Literal["llm", "synonyms", "hyde"] = "llm",
        n: int = 3,
    ) -> list[str]:
        """Expand a query using the specified method.

        Args:
            query: Original search query.
            method: Expansion method.
            n: Number of alternative queries (for LLM method).

        Returns:
            List of expanded queries (original query is always first).
        """
        if method == "synonyms":
            return self.expand_synonyms(query)
        if method == "hyde":
            hyde_doc = await self.expand_hyde(query)
            return [query, hyde_doc]
        # Default: LLM expansion
        return await self.expand_llm(query, n=n)

    async def expand_llm(self, query: str, n: int = 3) -> list[str]:
        """Generate N alternative query phrasings via LLM (Ralph Wiggum)."""
        base_messages = [
            SystemMessage(content="You are a search query expansion system."),
            HumanMessage(content=_EXPANSION_PROMPT.format(query=query, n=n)),
        ]
        rw_feedback = ""

        for rw_attempt in range(1, 3):  # max 2 attempts
            try:
                messages = list(base_messages)
                if rw_feedback:
                    messages.append(HumanMessage(content=f"\u26a0\ufe0f {rw_feedback}"))

                response = await self._llm.ainvoke(messages)
                content = response.content if isinstance(response.content, str) else str(response.content)

                alternatives = [
                    line.strip()
                    for line in content.strip().split("\n")
                    if line.strip() and len(line.strip()) > 3
                ][:n]

                # Validate: at least 1 alternative
                if not alternatives:
                    rw_feedback = f"Return {n} alternative phrasings, one per line. No numbering or bullets."
                    logger.warning(f"[EXPAND] Attempt {rw_attempt}: no alternatives generated")
                    continue

                return [query] + alternatives

            except Exception as e:
                logger.warning("LLM query expansion attempt %d failed: %s", rw_attempt, e)
                rw_feedback = f"Previous call failed: {e}."

        return [query]

    def expand_synonyms(self, query: str) -> list[str]:
        """Expand query with Russian morphological forms.

        Uses pymorphy3 for lemmatization and form generation.
        Falls back to original query if pymorphy3 is not installed.
        """
        try:
            import pymorphy3
        except ImportError:
            logger.info("pymorphy3 not installed, skipping synonym expansion")
            return [query]

        morph = pymorphy3.MorphAnalyzer()
        words = query.split()
        expanded_queries = [query]

        # Generate lemmatized version
        lemmas = []
        for word in words:
            parsed = morph.parse(word)
            if parsed:
                lemmas.append(parsed[0].normal_form)
            else:
                lemmas.append(word)

        lemma_query = " ".join(lemmas)
        if lemma_query != query:
            expanded_queries.append(lemma_query)

        return expanded_queries

    async def expand_hyde(self, query: str) -> str:
        """Generate a hypothetical document for HyDE embedding (Ralph Wiggum)."""
        base_messages = [
            SystemMessage(content="You are a knowledgeable assistant."),
            HumanMessage(content=_HYDE_PROMPT.format(query=query)),
        ]
        rw_feedback = ""

        for rw_attempt in range(1, 3):  # max 2 attempts
            try:
                messages = list(base_messages)
                if rw_feedback:
                    messages.append(HumanMessage(content=f"\u26a0\ufe0f {rw_feedback}"))

                response = await self._llm.ainvoke(messages)
                content = response.content if isinstance(response.content, str) else str(response.content)
                hypothetical = content.strip()

                # Validate: non-empty and substantive
                if len(hypothetical) < 30:
                    rw_feedback = "Write a passage of 3-5 sentences answering the question. Do not refuse."
                    logger.warning(f"[HyDE] Attempt {rw_attempt}: too short ({len(hypothetical)} chars)")
                    continue

                return hypothetical

            except Exception as e:
                logger.warning("HyDE attempt %d failed: %s", rw_attempt, e)
                rw_feedback = f"Previous call failed: {e}."

        return query
