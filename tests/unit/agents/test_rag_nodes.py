"""Unit tests for RAG Agent nodes (F2.9).

Tests:
- F2.9.1: Test RAG agent node: grader
- F2.9.2: Test RAG agent node: rewriter
- F2.9.3: Test StreamingRAGRunner event types
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.unit
class TestRAGAgentNodes:
    """Test RAG agent node functions."""

    async def test_grader_relevance_check(self):
        """F2.9.1: Grader should check document relevance."""
        from src.pdf_framework.agents.rag.nodes.grader import grade_documents

        query = "What is 1С?"
        documents = [
            {"content": "1С is a platform", "id": "1"},
            {"content": "Python is a language", "id": "2"},
        ]

        graded = await grade_documents(query, documents)

        # Should score first doc higher
        assert graded[0]["id"] == "1"
        assert graded[0]["score"] > graded[1]["score"]

    async def test_grader_threshold_filtering(self):
        """F2.9.1: Grader should filter below threshold."""
        from src.pdf_framework.agents.rag.nodes.grader import grade_documents

        query = "What is 1С?"
        documents = [
            {"content": "1С is a platform", "id": "1"},
            {"content": "Recipe for cake", "id": "2"},
        ]

        graded = await grade_documents(query, documents, threshold=0.5)

        # Second doc should be filtered
        assert len(graded) == 1
        assert graded[0]["id"] == "1"

    async def test_grader_hallucination_check(self):
        """F2.9.1: Grader should detect hallucination."""
        from src.pdf_framework.agents.rag.nodes.grader import check_hallucination

        document = {"content": "1С was created in 2050", "id": "1"}
        context = [{"content": "1С was created in 1991"}]

        is_hallucination = await check_hallucination(document, context)

        # Should detect inconsistency
        assert is_hallucination is True

    async def test_rewriter_query_expansion(self):
        """F2.9.2: Rewriter should expand query for better retrieval."""
        from src.pdf_framework.agents.rag.nodes.rewriter import rewrite_query

        original_query = "справочники"

        rewritten = await rewrite_query(original_query)

        # Should produce a different, more specific query
        assert rewritten != original_query
        assert len(rewritten) > 0

    async def test_rewriter_preserves_intent(self):
        """F2.9.2: Rewriter should preserve original query intent."""
        from src.pdf_framework.agents.rag.nodes.rewriter import rewrite_query

        original_query = "какие есть регистры в 1С?"

        rewritten = await rewrite_query(original_query)

        # Should still be about registers in 1C
        assert "регистр" in rewritten.lower() or "register" in rewritten.lower()

    async def test_rewriter_multi_turn(self):
        """F2.9.2: Rewriter should support multi-turn refinement."""
        from src.pdf_framework.agents.rag.nodes.rewriter import rewrite_query

        query = "справочники"

        # Multiple rewrites should improve specificity
        rewrite1 = await rewrite_query(query, turn=1)
        rewrite2 = await rewrite_query(query, turn=2)

        # Later turns should be more specific
        assert len(rewrite2) >= len(rewrite1)

    def test_rewriter_max_length(self):
        """F2.9.2: Rewriter should respect max query length."""
        from src.pdf_framework.agents.rag.nodes.rewriter import rewrite_query

        # Set short max length
        with patch("src.pdf_framework.agents.rag.nodes.rewriter.MAX_QUERY_LENGTH", 50):
            import asyncio

            async def test():
                result = await rewrite_query("Very long query about many things")
                return len(result) <= 50

            assert asyncio.run(test())


@pytest.mark.unit
class TestStreamingRAGRunner:
    """Test StreamingRAGRunner event types (F2.9.3)."""

    async def test_streaming_events(self):
        """F2.9.3: Should emit streaming events."""
        from src.pdf_framework.agents.rag.streaming import StreamingRAGRunner

        runner = StreamingRAGRunner()

        events = []
        async def collect_events():
            async for event in runner.stream("test query"):
                events.append(event)

        await collect_events()

        # Should have events
        assert len(events) > 0

    async def test_event_types(self):
        """F2.9.3: Should emit correct event types."""
        from src.pdf_framework.agents.rag.streaming import StreamingRAGRunner, EventType

        runner = StreamingRAGRunner()

        event_types = []
        async def collect_types():
            async for event in runner.stream("test"):
                event_types.append(event.type)

        await collect_types()

        # Should have key event types
        assert EventType.QUERY_START in event_types
        assert EventType.QUERY_END in event_types

    async def test_event_progress(self):
        """F2.9.3: Events should track progress."""
        from src.pdf_framework.agents.rag.streaming import StreamingRAGRunner

        runner = StreamingRAGRunner()

        progress_values = []
        async def collect_progress():
            async for event in runner.stream("test"):
                if hasattr(event, "progress"):
                    progress_values.append(event.progress)

        await collect_progress()

        # Progress should increase
        assert all(progress_values[i] <= progress_values[i+1]
                   for i in range(len(progress_values) - 1))

    async def test_event_chunk_delivery(self):
        """F2.9.3: Should deliver response chunks."""
        from src.pdf_framework.agents.rag.streaming import StreamingRAGRunner

        runner = StreamingRAGRunner()

        chunks = []
        async def collect_chunks():
            async for event in runner.stream("test"):
                if event.type == "chunk":
                    chunks.append(event.content)

        await collect_chunks()

        # Should have content chunks
        assert len(chunks) > 0
        assert any(len(c) > 0 for c in chunks)

    async def test_streaming_error_handling(self):
        """F2.9.3: Should handle errors in streaming gracefully."""
        from src.pdf_framework.agents.rag.streaming import StreamingRAGRunner

        runner = StreamingRAGRunner()

        # Mock generator that raises error
        async def failing_generator():
            yield {"type": "start"}
            raise ValueError("Test error")

        with patch.object(runner, "_stream", failing_generator):
            with pytest.raises(ValueError):
                async for _ in runner.stream("test"):
                    pass
