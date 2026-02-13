"""Contextual Retrieval: LLM-generated context for document chunks.

Phase 3.1: At index time, generates a short context summary for each chunk
that places it within the broader document. The contextual content is stored
in chunk metadata and used for embedding, improving retrieval accuracy by +20-30%.

Flow:
    chunk.content (original text, preserved for display)
    chunk.metadata["context"] (LLM-generated summary)
    chunk.metadata["contextual_content"] (context + content, used for embedding)
"""

import logging

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.pdf_framework.config import AgentSettings, ContextualRetrievalSettings
from src.pdf_framework.schemas.documents import DocumentChunk, ProcessedDocument

logger = logging.getLogger(__name__)

_CONTEXT_PROMPT = """Here is the document titled "{title}".

<document>
{doc_excerpt}
</document>

Here is a chunk from that document:

<chunk>
{chunk_text}
</chunk>

Give a short context (1-2 sentences) that situates this chunk within the document.
Focus on what topic/section this chunk belongs to and what it discusses.
Write in the same language as the chunk. Return ONLY the context, nothing else."""


class ContextGenerator:
    """Generate contextual summaries for document chunks via LLM."""

    def __init__(
        self,
        settings: AgentSettings | None = None,
        context_settings: ContextualRetrievalSettings | None = None,
        api_key: str = "",
    ):
        self._settings = settings or AgentSettings()
        self._context_settings = context_settings or ContextualRetrievalSettings()

        llm_kwargs: dict = {
            "model": self._settings.model,
            "temperature": 0.0,
            "max_tokens": self._context_settings.max_context_tokens,
            "api_key": api_key or None,
        }
        if self._settings.base_url:
            llm_kwargs["base_url"] = self._settings.base_url
        self._llm = ChatAnthropic(**llm_kwargs)

    async def generate_context(
        self,
        chunk: DocumentChunk,
        document: ProcessedDocument,
    ) -> str:
        """Generate a context summary for a single chunk."""
        # Use first ~2000 chars of doc as excerpt for context
        doc_excerpt = document.raw_text[:2000] if document.raw_text else ""
        title = document.metadata.title or document.source_path

        messages = [
            SystemMessage(content="You generate brief context summaries for document chunks."),
            HumanMessage(content=_CONTEXT_PROMPT.format(
                title=title,
                doc_excerpt=doc_excerpt,
                chunk_text=chunk.content[:1000],
            )),
        ]

        # Ralph Wiggum: self-correcting retry for context generation
        max_rw_retries = 2
        rw_feedback = ""

        for rw_attempt in range(1, max_rw_retries + 1):
            try:
                attempt_messages = list(messages)
                if rw_feedback:
                    attempt_messages.append(
                        HumanMessage(content=f"\u26a0\ufe0f CORRECTION: {rw_feedback}")
                    )

                response = await self._llm.ainvoke(attempt_messages)
                if isinstance(response.content, str):
                    context = response.content.strip()
                elif isinstance(response.content, list):
                    parts = []
                    for block in response.content:
                        if isinstance(block, dict):
                            parts.append(block.get("text", ""))
                        elif hasattr(block, "text"):
                            parts.append(getattr(block, "text"))
                        else:
                            parts.append(str(block))
                    context = "".join(parts).strip()
                else:
                    context = str(response.content).strip()

                # Validate: non-empty and reasonable length
                if len(context) < 15:
                    rw_feedback = (
                        "Context must be 1-2 sentences describing the chunk's topic. "
                        "Write in the same language as the chunk."
                    )
                    logger.warning(
                        f"Context too short for chunk {chunk.id} (attempt {rw_attempt}): {len(context)} chars"
                    )
                    continue

                # Validate: not a refusal
                refusal_patterns = ["i cannot", "i can't", "i'm unable", "не могу"]
                if any(p in context.lower() for p in refusal_patterns):
                    rw_feedback = (
                        "Do not refuse. Summarize the chunk topic in 1-2 sentences. "
                        "The chunk is real document text."
                    )
                    logger.warning(f"Context refusal for chunk {chunk.id} (attempt {rw_attempt})")
                    continue

                return context

            except Exception as e:
                logger.warning("Context generation attempt %d failed for chunk %s: %s", rw_attempt, chunk.id, e)
                rw_feedback = f"Previous call failed: {e}. Try again."

        return ""

    async def enrich_chunks(
        self,
        chunks: list[DocumentChunk],
        document: ProcessedDocument,
    ) -> list[DocumentChunk]:
        """Add contextual content to all chunks.

        Sets:
            chunk.metadata["context"] — the LLM-generated context
            chunk.metadata["contextual_content"] — context + original content (for embedding)
        """
        for chunk in chunks:
            context = await self.generate_context(chunk, document)
            chunk.metadata["context"] = context
            if context:
                chunk.metadata["contextual_content"] = f"{context}\n\n{chunk.content}"
            else:
                chunk.metadata["contextual_content"] = chunk.content
            logger.debug("Chunk %s context: %s", chunk.id, context[:100] if context else "(empty)")

        return chunks
