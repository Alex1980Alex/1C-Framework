"""Cross-Document Synthesizer for Deep Research Agent (Phase 19).

Merges results from multiple sub-searches into a comprehensive answer.

Author: Claude Code
Version: 1.0.0 - Phase 19: Deep Research Agent
"""

import logging
import re
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SubResult(BaseModel):
    """Result from a single sub-question search."""

    sub_question: str
    answer: str
    sources: list[str] = Field(default_factory=list)
    key_findings: list[str] = Field(default_factory=list)
    entities_found: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class Citation(BaseModel):
    """A citation reference."""

    index: int
    source: str
    text: str = ""


class CrossDocumentSynthesizer:
    """Merge sub-results into a comprehensive answer with citations."""

    def __init__(self, llm: Any = None, api_key: str = "", base_url: str = ""):
        self._llm = llm
        self._api_key = api_key
        self._base_url = base_url

    async def synthesize(
        self,
        original_question: str,
        sub_results: list[SubResult],
        context: str = "",
    ) -> tuple[str, list[Citation]]:
        """Synthesize sub-results into one answer."""
        if self._llm is not None:
            return await self._synthesize_with_llm(original_question, sub_results, context)
        return self._synthesize_heuristic(original_question, sub_results)

    def _synthesize_heuristic(
        self, question: str, sub_results: list[SubResult],
    ) -> tuple[str, list[Citation]]:
        """Synthesize without LLM using template merging."""
        parts: list[str] = []
        citations: list[Citation] = []
        cite_idx = 1

        for sr in sub_results:
            if sr.answer:
                parts.append(f"**{sr.sub_question}**\n{sr.answer} [{cite_idx}]")
                for src in sr.sources:
                    citations.append(Citation(index=cite_idx, source=src))
                    cite_idx += 1

        answer = "\n\n".join(parts) if parts else "Недостаточно данных для ответа."
        return answer, citations

    async def _synthesize_with_llm(
        self, question: str, sub_results: list[SubResult], context: str,
    ) -> tuple[str, list[Citation]]:
        """Synthesize using LLM."""
        try:
            from langchain_core.messages import HumanMessage, SystemMessage

            context_parts = []
            for i, sr in enumerate(sub_results, 1):
                context_parts.append(f"[{i}] {sr.sub_question}: {sr.answer}")

            messages = [
                SystemMessage(content=(
                    "Synthesize the following research findings into a comprehensive answer. "
                    "Use citation numbers [1], [2], etc. to reference sources. "
                    "Answer in Russian."
                )),
                HumanMessage(content=f"Question: {question}\n\nFindings:\n" + "\n".join(context_parts)),
            ]
            response = await self._llm.ainvoke(messages)
            text = response.content if isinstance(response.content, str) else response.content[0].text
            citations = self._extract_citations(text, sub_results)
            return text, citations
        except Exception as e:
            logger.warning(f"[SYNTH] LLM synthesis failed: {e}")
            return self._synthesize_heuristic(question, sub_results)

    async def build_citation_chain(
        self, answer: str, sub_results: list[SubResult],
    ) -> list[Citation]:
        """Extract citation references from an answer."""
        return self._extract_citations(answer, sub_results)

    def _extract_citations(
        self, text: str, sub_results: list[SubResult],
    ) -> list[Citation]:
        """Parse [N] citations from text."""
        citations: list[Citation] = []
        indices = set(int(m) for m in re.findall(r"\[(\d+)\]", text))

        for idx in sorted(indices):
            if 1 <= idx <= len(sub_results):
                sr = sub_results[idx - 1]
                for src in sr.sources:
                    citations.append(Citation(index=idx, source=src))
            else:
                citations.append(Citation(index=idx, source="unknown"))

        return citations
