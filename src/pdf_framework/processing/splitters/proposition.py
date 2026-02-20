"""Proposition-based Text Splitter (Phase 58).

Splits text into atomic propositions using LLM.
Each proposition is a single factual statement, improving retrieval precision.

Author: Claude Code
Version: 1.0.0 - Phase 58: Proposition Chunking
"""

import logging
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain.text_splitter import TextSplitter

from src.pdf_framework.schemas.documents import DocumentChunk

logger = logging.getLogger(__name__)

PROPOSITION_PROMPT = """Break down the following text into 3-10 atomic propositions.

Rules:
- Each proposition should be a single, complete factual statement
- Preserve all important information
- Avoid redundancy
- Keep propositions concise but complete

Text: {text}

Return your response as a numbered list:
1. First proposition
2. Second proposition
3. ...

Provide ONLY the numbered list, no additional text:"""


class PropositionSplitter(TextSplitter):
    """Split text into atomic propositions using LLM.

    Benefits:
    - More granular retrieval (smaller units)
    - Better precision (exact facts)
    - Improved recall (more match opportunities)

    Example:
        >>> splitter = PropositionSplitter(llm=ChatAnthropic(model="claude-3-haiku-20240307"))
        >>> propositions = splitter.split_text("The Eiffel Tower is 324m tall and located in Paris.")
        >>> # ["The Eiffel Tower is 324m tall.", "The Eiffel Tower is located in Paris."]
    """

    def __init__(
        self,
        llm: ChatAnthropic | None = None,
        model: str = "claude-3-haiku-20240307",
        min_propositions: int = 3,
        max_propositions: int = 10,
        batch_size: int = 5,
    ):
        """Initialize proposition splitter.

        Args:
            llm: LLM for proposition extraction (created if None)
            model: Model name for LLM
            min_propositions: Minimum propositions per chunk
            max_propositions: Maximum propositions per chunk
            batch_size: Batch size for processing
        """
        self._model = model
        self._min_propositions = min_propositions
        self._max_propositions = max_propositions
        self._batch_size = batch_size

        if llm is None:
            self._llm = ChatAnthropic(model=model, temperature=0.0)
        else:
            self._llm = llm

        logger.info(
            f"[PROPOSITION] Initialized with model={model}, "
            f"min={min_propositions}, max={max_propositions}"
        )

    def split_text(self, text: str) -> list[str]:
        """Split text into atomic propositions.

        Args:
            text: Input text to split

        Returns:
            List of proposition strings
        """
        if len(text) < 50:
            # Too short for propositions, return as-is
            return [text]

        propositions = self._extract_propositions(text)

        if len(propositions) < self._min_propositions:
            # Ralph Wiggum retry: got too few propositions
            logger.debug(
                f"[PROPOSITION] Too few propositions ({len(propositions)}), retrying"
            )
            propositions = self._extract_with_retry(text)

        return propositions

    def _extract_propositions(self, text: str) -> list[str]:
        """Extract propositions from text using LLM.

        Args:
            text: Input text

        Returns:
            List of propositions
        """
        try:
            response = self._llm.invoke([
                {"role": "user", "content": PROPOSITION_PROMPT.format(text=text)}
            ])

            content = response.content.strip()

            # Parse numbered list
            propositions = self._parse_numbered_list(content)

            logger.debug(f"[PROPOSITION] Extracted {len(propositions)} propositions")

            return propositions

        except Exception as e:
            logger.error(f"[PROPOSITION] Extraction failed: {e}")
            return [text]

    def _extract_with_retry(self, text: str) -> list[str]:
        """Retry extraction with different prompt.

        Args:
            text: Input text

        Returns:
            List of propositions
        """
        retry_prompt = """Extract ALL individual facts from this text. Each fact on a new line.

Text: {text}

Extract facts:"""

        try:
            response = self._llm.invoke([
                {"role": "user", "content": retry_prompt.format(text=text)}
            ])

            content = response.content.strip()
            lines = [line.strip() for line in content.split("\n") if line.strip()]

            return lines[:self._max_propositions]

        except Exception as e:
            logger.warning(f"[PROPOSITION] Retry failed: {e}")
            return [text]

    def _parse_numbered_list(self, text: str) -> list[str]:
        """Parse numbered list from LLM response.

        Args:
            text: LLM response text

        Returns:
            List of proposition strings
        """
        import re

        # Match patterns like "1. proposition" or "1) proposition"
        pattern = r"^\d+[\.\)]\s+(.+)$"
        propositions = []

        for line in text.split("\n"):
            match = re.match(pattern, line.strip())
            if match:
                propositions.append(match.group(1))

        return propositions

    def split_documents(self, documents: list[Any]) -> list[DocumentChunk]:
        """Split documents into proposition chunks.

        Args:
            documents: List of document chunks or dicts

        Returns:
            List of DocumentChunk with propositions
        """
        all_propositions = []

        for doc in documents:
            # Get text content
            if isinstance(doc, DocumentChunk):
                text = doc.content
                metadata = doc.metadata
            else:
                text = doc.get("content", "")
                metadata = doc.get("metadata", {})

            # Extract propositions
            propositions = self.split_text(text)

            # Create chunks for each proposition
            for i, prop in enumerate(propositions):
                chunk = DocumentChunk(
                    id=f"{doc.id if hasattr(doc, 'id') else doc.get('id', 'unk')}_prop_{i}",
                    content=prop,
                    document_id=doc.document_id if hasattr(doc, 'document_id') else doc.get('document_id', ''),
                    page_number=doc.page_number if hasattr(doc, 'page_number') else doc.get('page_number'),
                    section="proposition",
                    chunk_index=i,
                    metadata={
                        **metadata,
                        "chunk_type": "proposition",
                        "original_chunk_id": doc.id if hasattr(doc, 'id') else doc.get('id', ''),
                        "proposition_index": i,
                        "total_propositions": len(propositions),
                    },
                )
                all_propositions.append(chunk)

        logger.info(
            f"[PROPOSITION] Split {len(documents)} documents into "
            f"{len(all_propositions)} proposition chunks"
        )

        return all_propositions

    async def split_documents_async(self, documents: list[Any]) -> list[DocumentChunk]:
        """Split documents asynchronously in batches.

        Args:
            documents: List of document chunks

        Returns:
            List of proposition chunks
        """
        import asyncio

        results = []

        for i in range(0, len(documents), self._batch_size):
            batch = documents[i:i + self._batch_size]

            # Process batch in parallel
            tasks = [
                asyncio.to_thread(self.split_text, doc.content if hasattr(doc, 'content') else doc.get('content', ''))
                for doc in batch
            ]

            proposition_lists = await asyncio.gather(*tasks)

            # Create chunks
            for doc, propositions in zip(batch, proposition_lists):
                for j, prop in enumerate(propositions):
                    chunk = DocumentChunk(
                        id=f"{doc.id if hasattr(doc, 'id') else doc.get('id', 'unk')}_prop_{j}",
                        content=prop,
                        document_id=doc.document_id if hasattr(doc, 'document_id') else doc.get('document_id', ''),
                        page_number=doc.page_number if hasattr(doc, 'page_number') else doc.get('page_number'),
                        section="proposition",
                        chunk_index=j,
                        metadata={
                            **(doc.metadata if hasattr(doc, 'metadata') else doc.get('metadata', {})),
                            "chunk_type": "proposition",
                            "proposition_index": j,
                            "total_propositions": len(propositions),
                        },
                    )
                    results.append(chunk)

        return results


def create_proposition_splitter(
    model: str = "claude-3-haiku-20240307",
    min_propositions: int = 3,
    max_propositions: int = 10,
) -> PropositionSplitter:
    """Factory function to create proposition splitter.

    Args:
        model: LLM model name
        min_propositions: Minimum propositions
        max_propositions: Maximum propositions

    Returns:
        Configured PropositionSplitter
    """
    return PropositionSplitter(
        model=model,
        min_propositions=min_propositions,
        max_propositions=max_propositions,
    )
