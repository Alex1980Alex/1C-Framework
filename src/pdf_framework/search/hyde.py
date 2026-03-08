"""HyDE (Hypothetical Document Embeddings) generator (Phase 13.3).

Generates hypothetical document answers for improved search recall.

Author: Claude Code
Version: 1.4.0 - Phase 13.3: HyDE Implementation
"""

import logging
from typing import Literal

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class HyDEConfig(BaseModel):
    """HyDE configuration."""

    model: str = "claude-haiku-4-5-20251001"
    temperature: float = 0.3
    max_tokens: int = 512
    prompt_template: str = (
        "Write a short passage (2-3 sentences) that would answer "
        "this question, as if quoting from a reference document:\n\n"
        "Question: {query}\n\n"
        "Passage:"
    )


class HyDEGenerator:
    """
    Generates hypothetical documents for queries.

    HyDE improves recall for abstract/conceptual queries by using
    the embedding of a hypothetical answer instead of the query itself.
    """

    def __init__(
        self,
        api_key: str = "",
        config: HyDEConfig | None = None,
        base_url: str = "",
    ):
        """
        Initialize HyDE generator.

        Args:
            api_key: Anthropic API key
            config: HyDE configuration
            base_url: Custom API endpoint (for Z.AI or other proxies)
        """
        self._api_key = api_key
        self._config = config or HyDEConfig()
        self._base_url = base_url

    async def generate_hypothetical(
        self,
        query: str,
    ) -> str:
        """
        Generate a hypothetical document that would answer the query.

        Args:
            query: User question

        Returns:
            Hypothetical answer passage
        """
        from src.shared.llm_rotation.adapter import cheap_llm_call, is_cheap_llm_enabled

        # Cheap LLM path
        if is_cheap_llm_enabled("hyde"):
            try:
                prompt = self._config.prompt_template.format(query=query)
                result = await cheap_llm_call(
                    prompt=prompt,
                    system_prompt="You are a knowledgeable assistant writing reference document passages.",
                    component="hyde",
                )
                if result and len(result.strip()) >= 30:
                    logger.info(f"[HyDE] Generated hypothetical (cheap, {len(result.strip())} chars)")
                    return result.strip()
            except Exception as e:
                logger.warning("[HyDE] Cheap LLM failed, falling back: %s", e)

        try:
            from langchain_anthropic import ChatAnthropic
            from langchain_core.messages import HumanMessage

            llm_kwargs = dict(
                model=self._config.model,
                temperature=self._config.temperature,
                max_tokens=self._config.max_tokens,
                api_key=self._api_key or None,
            )
            if self._base_url:
                llm_kwargs["base_url"] = self._base_url
            llm = ChatAnthropic(**llm_kwargs)

            prompt = self._config.prompt_template.format(query=query)

            # Ralph Wiggum: self-correcting retry
            rw_feedback = ""
            for rw_attempt in range(1, 3):  # max 2 attempts
                try:
                    full_prompt = prompt
                    if rw_feedback:
                        full_prompt += f"\n\n\u26a0\ufe0f {rw_feedback}"

                    response = await llm.ainvoke([HumanMessage(content=full_prompt)])

                    content = response.content
                    if isinstance(content, list):
                        hypothetical = " ".join(
                            getattr(block, "text", str(block)) for block in content
                        ).strip()
                    else:
                        hypothetical = content.strip()

                    if len(hypothetical) < 30:
                        rw_feedback = "Write 2-3 sentences answering the question. Do not refuse."
                        logger.warning(f"[HyDE] Attempt {rw_attempt}: too short ({len(hypothetical)} chars)")
                        continue

                    logger.info(f"[HyDE] Generated hypothetical ({len(hypothetical)} chars)")
                    return hypothetical

                except Exception as e:
                    logger.error(f"[HyDE] Attempt {rw_attempt} failed: {e}")
                    rw_feedback = f"Previous call failed: {e}."

            return ""

        except Exception as e:
            logger.error(f"[HyDE] Initialization failed: {e}")
            return ""

    async def embed_hypothetical(
        self,
        query: str,
        embedding_engine,
    ) -> list[float]:
        """
        Generate embedding for hypothetical document.

        Args:
            query: User question
            embedding_engine: Embedding engine to use

        Returns:
            Embedding vector
        """
        # Generate hypothetical document
        hypothetical = await self.generate_hypothetical(query)

        if not hypothetical:
            # Fallback to query embedding
            logger.warning("[HyDE] Hypothetical generation failed, using query embedding")
            return await embedding_engine.embed_text(query)

        # Embed hypothetical document
        return await embedding_engine.embed_text(hypothetical)

    async def expand_query(
        self,
        query: str,
        embedding_engine,
        llm_cache=None,
    ) -> tuple[str, list[float]]:
        """
        Expand query using HyDE (for QueryExpander integration).

        Args:
            query: Original query
            embedding_engine: Embedding engine
            llm_cache: Optional LLM cache for hypotheticals

        Returns:
            (expanded_query, embedding)
        """
        # Check cache first
        if llm_cache:
            cache_key = f"hyde:{query}"
            cached = await llm_cache.get(cache_key)
            if cached:
                logger.debug(f"[HyDE] Cache hit for query '{query[:50]}...'")
                return cached, await embedding_engine.embed_text(cached)

        # Generate hypothetical
        hypothetical = await self.generate_hypothetical(query)

        if not hypothetical:
            return query, await embedding_engine.embed_text(query)

        # Cache result
        if llm_cache:
            cache_key = f"hyde:{query}"
            await llm_cache.set(cache_key, hypothetical)

        # Get embedding
        embedding = await embedding_engine.embed_text(hypothetical)

        return hypothetical, embedding


class QueryExpander:
    """
    Expands queries using various methods (Phase 13.3 extension).

    Methods:
    - llm: LLM-based expansion (existing)
    - hyde: Hypothetical document embeddings (new)
    - synonyms: Synonym-based expansion (existing)
    """

    async def expand(
        self,
        query: str,
        method: Literal["llm", "hyde", "synonyms"] = "hyde",
        embedding_engine=None,
        **kwargs,
    ) -> tuple[str, list[float] | None]:
        """
        Expand query using specified method.

        Args:
            query: Original query
            method: Expansion method
            embedding_engine: Required for HyDE
            **kwargs: Additional parameters

        Returns:
            (expanded_text, embedding) or (None, None)
        """
        if method == "hyde":
            if embedding_engine is None:
                raise ValueError("embedding_engine required for HyDE expansion")

            hyde_gen = HyDEGenerator(
                api_key=kwargs.get("api_key", ""),
                base_url=kwargs.get("base_url", ""),
            )
            return await hyde_gen.expand_query(
                query=query,
                embedding_engine=embedding_engine,
                llm_cache=kwargs.get("llm_cache"),
            )

        # TODO: Implement other methods
        logger.warning(f"[QueryExpander] Method '{method}' not yet implemented")
        return None, None


# Global HyDE generator instance
_hyde_generator: HyDEGenerator | None = None


def get_hyde_generator(**kwargs) -> HyDEGenerator:
    """Get or create global HyDE generator instance."""
    global _hyde_generator
    if _hyde_generator is None:
        _hyde_generator = HyDEGenerator(**kwargs)
    return _hyde_generator
