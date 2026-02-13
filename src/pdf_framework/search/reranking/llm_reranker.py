"""LLM-based reranker using Claude for high-quality relevance scoring.

Sends query + candidate chunks to Claude, asks to score each by relevance.
Significantly faster than CrossEncoder on CPU (1-3s vs 60-120s) with
superior context understanding, especially for Russian text.

Author: Claude Code
Version: 0.1.0 — Phase 25: LLM Reranking
"""

import json
import logging
import re

from src.pdf_framework.schemas.documents import SearchResult

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "Ты — эксперт по оценке релевантности документов. "
    "Тебе дан поисковый запрос и список текстовых фрагментов. "
    "Оцени каждый фрагмент по релевантности к запросу от 0.0 до 1.0.\n\n"
    "Верни ТОЛЬКО JSON-массив объектов в формате:\n"
    '[{"index": 0, "score": 0.95}, {"index": 1, "score": 0.3}, ...]\n\n'
    "Правила:\n"
    "- index — порядковый номер фрагмента (начиная с 0)\n"
    "- score — float от 0.0 (не релевантен) до 1.0 (идеально релевантен)\n"
    "- Оценивай по смысловому соответствию, а не по совпадению слов\n"
    "- Верни JSON и НИЧЕГО больше"
)

# Maximum characters per chunk to send (avoid hitting token limits)
_MAX_CHUNK_CHARS = 800


class LLMReranker:
    """Rerank search results using Claude LLM for relevance scoring."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "",
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ):
        self._api_key = api_key
        self._base_url = base_url or None
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._client = None

    def _get_client(self):
        """Lazy-init Anthropic async client."""
        if self._client is not None:
            return self._client

        from anthropic import AsyncAnthropic

        if self._base_url:
            self._client = AsyncAnthropic(
                api_key=self._api_key,
                base_url=self._base_url,
            )
        else:
            self._client = AsyncAnthropic(api_key=self._api_key)

        logger.info(
            "[LLM-RERANK] Initialized: model=%s, base_url=%s",
            self._model,
            self._base_url or "default",
        )
        return self._client

    def _build_prompt(self, query: str, results: list[SearchResult]) -> str:
        """Build the user prompt with query and numbered chunks."""
        parts = [f"Запрос: {query}\n\nФрагменты:\n"]
        for i, r in enumerate(results):
            text = r.chunk.content[:_MAX_CHUNK_CHARS]
            if len(r.chunk.content) > _MAX_CHUNK_CHARS:
                text += "…"
            parts.append(f"[{i}] {text}\n")
        return "\n".join(parts)

    def _parse_scores(
        self, text: str, n_results: int,
    ) -> list[tuple[int, float]]:
        """Parse JSON array of {index, score} from LLM response.

        Returns list of (index, score) tuples. Falls back to original
        order on parse failure.
        """
        # Extract JSON array from response (may have markdown fences)
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            logger.warning("[LLM-RERANK] No JSON array in response, keeping original order")
            return [(i, 1.0 - i * 0.01) for i in range(n_results)]

        try:
            items = json.loads(match.group())
        except json.JSONDecodeError as e:
            logger.warning("[LLM-RERANK] JSON parse error: %s", e)
            return [(i, 1.0 - i * 0.01) for i in range(n_results)]

        scores: list[tuple[int, float]] = []
        seen: set[int] = set()
        for item in items:
            idx = int(item.get("index", -1))
            score = float(item.get("score", 0.0))
            if 0 <= idx < n_results and idx not in seen:
                scores.append((idx, score))
                seen.add(idx)

        # Add any missing indices with score 0
        for i in range(n_results):
            if i not in seen:
                scores.append((i, 0.0))

        return scores

    async def rerank(
        self, query: str, results: list[SearchResult], top_k: int = 5,
    ) -> list[SearchResult]:
        """Rerank results using Claude LLM relevance scoring."""
        if not results:
            return []

        client = self._get_client()
        prompt = self._build_prompt(query, results)

        try:
            response = await client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )

            # Extract text from response
            text = ""
            for block in response.content:
                block_text = getattr(block, "text", None)
                if block_text:
                    text += block_text

            scores = self._parse_scores(text, len(results))

            # Sort by score descending
            scores.sort(key=lambda x: x[1], reverse=True)

            # Build reranked results
            reranked: list[SearchResult] = []
            for idx, score in scores[:top_k]:
                original = results[idx]
                reranked.append(
                    SearchResult(
                        chunk=original.chunk,
                        score=score,
                        source=original.source,
                        highlights=original.highlights,
                    )
                )

            logger.info(
                "[LLM-RERANK] Reranked %d→%d results (model=%s, tokens=%d/%d)",
                len(results),
                len(reranked),
                self._model,
                response.usage.input_tokens,
                response.usage.output_tokens,
            )
            return reranked

        except Exception as e:
            logger.error("[LLM-RERANK] Failed: %s — keeping original order", e)
            # Fallback: return top_k results in original order
            return results[:top_k]
