"""Section-First Search Pipeline (Phase 30).

Two-level search: (1) locate dominant section via BM25 title hits,
(2) search within that section using hybrid strategy + reranking.

Leverages document hierarchy (ToC breadcrumbs, section_number metadata)
for more focused retrieval when queries map to a specific section.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any, TYPE_CHECKING

from src.pdf_framework.schemas.documents import SearchResponse

if TYPE_CHECKING:
    from src.pdf_framework.search.bm25_store import BM25Store
    from src.pdf_framework.search.manager import SearchManager

logger = logging.getLogger(__name__)


class SectionFirstPipeline:
    """Two-level search: locate section via BM25, then search within.

    Step 1: Run BM25 two-pass search (title=10x weighted) to identify
            which document section the query targets.
    Step 2: If a dominant section is found (>60% of top hits agree),
            run hybrid search scoped to that section.
    Fallback: If no dominant section, fall back to regular hybrid search.
    """

    # Minimum agreement ratio among top BM25 hits to declare a dominant section
    DOMINANCE_THRESHOLD = 0.5

    # How many levels to keep when truncating section numbers (5.14.3.6 → 5.14.3)
    TRUNCATE_LEVELS = 3

    def __init__(
        self,
        bm25_store: BM25Store,
        search_manager: SearchManager,
    ) -> None:
        self._bm25 = bm25_store
        self._manager = search_manager

    async def search(
        self,
        query: str,
        k: int = 5,
        filter: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> SearchResponse:
        """Execute section-first search.

        1. BM25 two-pass → top hits with section metadata
        2. Extract dominant section from hits
        3. Hybrid search within that section (or fallback to full hybrid)
        """
        # Step 1: BM25 two-pass to locate relevant sections
        bm25_hits = await self._bm25.search_two_pass(query, k=10)

        # Step 2: Determine dominant section
        top_section = await self._extract_dominant_section(bm25_hits)

        if top_section:
            logger.info(
                "[SECTION-FIRST] Dominant section: '%s' — searching within",
                top_section,
            )
            response = await self._manager.search(
                query=query,
                strategy="hybrid",
                k=k,
                filter=filter,
                section_prefix=top_section,
                rerank=True,
                **kwargs,
            )
            # If section-scoped search found enough results, return them
            if len(response.results) >= max(1, k // 2):
                response.metadata["section_first"] = top_section
                return response

            # Not enough results in section — fall through to full search
            logger.info(
                "[SECTION-FIRST] Section '%s' yielded only %d results — falling back",
                top_section, len(response.results),
            )

        # Fallback: regular hybrid search (no section constraint)
        logger.info("[SECTION-FIRST] No dominant section — using full hybrid search")
        return await self._manager.search(
            query=query,
            strategy="hybrid",
            k=k,
            filter=filter,
            rerank=True,
            **kwargs,
        )

    async def _extract_dominant_section(
        self, hits: list[tuple[str, float]],
    ) -> str | None:
        """Find the most common section_number prefix among top BM25 hits.

        - Fetches section metadata from chunk_meta table
        - Truncates section numbers to TRUNCATE_LEVELS (e.g. 5.14.3.6 → 5.14.3)
        - Returns the most frequent prefix if it covers >DOMINANCE_THRESHOLD of hits
        """
        if not hits:
            return None

        # Get chunk IDs from top hits
        chunk_ids = [cid for cid, _ in hits[:10]]

        # Fetch metadata from BM25 store (has section_title which contains breadcrumb)
        chunk_metas = await self._bm25.get_chunks_by_ids(chunk_ids)

        if not chunk_metas:
            return None

        # Extract and truncate section numbers from section titles
        section_prefixes: list[str] = []
        for meta in chunk_metas:
            section_title = meta.get("section_title", "")
            if not section_title:
                continue

            # Extract leading number: "5.14.3.6. Агрегаты" → "5.14.3.6"
            # Or from breadcrumb: "5. Глава > 5.14. Регистры > 5.14.3. ..." → last number
            section_num = self._extract_section_number(section_title)
            if section_num:
                truncated = self._truncate_section(section_num, self.TRUNCATE_LEVELS)
                section_prefixes.append(truncated)

        if not section_prefixes:
            return None

        # Count prefixes and find dominant one
        counter = Counter(section_prefixes)
        most_common, count = counter.most_common(1)[0]
        ratio = count / len(section_prefixes)

        logger.debug(
            "[SECTION-FIRST] Section distribution: %s (dominant: '%s' at %.0f%%)",
            dict(counter), most_common, ratio * 100,
        )

        if ratio >= self.DOMINANCE_THRESHOLD:
            return most_common

        return None

    @staticmethod
    def _extract_section_number(text: str) -> str:
        """Extract leading section number from text.

        Examples:
            "5.14.3.6. Агрегаты" → "5.14.3.6"
            "5. Глава > 5.14. Регистры > 5.14.3.6. Агрегаты" → "5.14.3.6"
            "**5.8.Справочники**" → "5.8"
            "Справочники" → ""
        """
        import re

        # If breadcrumb format (A > B > C), take the last segment
        if " > " in text:
            text = text.rsplit(" > ", 1)[-1]

        # Strip markdown bold markers
        text = text.strip().strip("*")

        # Match leading number like "5.14.3.6" or "5.14.3.6."
        match = re.match(r"(\d+(?:\.\d+)*)", text.strip())
        return match.group(1) if match else ""

    @staticmethod
    def _truncate_section(section_num: str, max_levels: int) -> str:
        """Truncate section number to max_levels.

        Examples (max_levels=3):
            "5.14.3.6" → "5.14.3"
            "5.14" → "5.14"
            "5" → "5"
        """
        parts = section_num.split(".")
        return ".".join(parts[:max_levels])
