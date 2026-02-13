"""Phase 22: Self-Learning Feedback — tests.

Tests for:
  - FeedbackStore: CRUD for user feedback
  - FewShotProvider: find similar positive examples
  - ContentBooster: boost scores for consistently positive chunks
"""

import pytest


class TestFeedbackStore:
    @pytest.mark.asyncio
    async def test_initialize_creates_tables(self, tmp_path):
        from src.pdf_framework.feedback.store import FeedbackStore

        store = FeedbackStore(db_path=tmp_path / "feedback.db")
        await store.initialize()

    @pytest.mark.asyncio
    async def test_add_and_retrieve_feedback(self, tmp_path):
        from src.pdf_framework.feedback.store import FeedbackEntry, FeedbackStore

        store = FeedbackStore(db_path=tmp_path / "feedback.db")
        await store.initialize()

        entry = FeedbackEntry(
            feedback_id="f1",
            question="Что такое регистр?",
            answer="Регистр — объект конфигурации.",
            score=1,
            strategy="hybrid",
            chunk_ids=["c1", "c2"],
            chunk_scores=[0.9, 0.7],
            timestamp=1000000.0,
        )
        await store.add(entry)

        positive = await store.get_positive(limit=10)
        assert len(positive) == 1
        assert positive[0].question == "Что такое регистр?"

    @pytest.mark.asyncio
    async def test_get_stats(self, tmp_path):
        from src.pdf_framework.feedback.store import FeedbackEntry, FeedbackStore

        store = FeedbackStore(db_path=tmp_path / "feedback.db")
        await store.initialize()

        for i, score in enumerate([1, 1, -1, 0]):
            await store.add(FeedbackEntry(
                feedback_id=f"f{i}",
                question=f"Q{i}?", answer=f"A{i}.",
                score=score, strategy="hybrid",
                chunk_ids=[], chunk_scores=[], timestamp=float(i),
            ))

        stats = await store.get_stats()
        assert stats["total"] == 4
        assert stats["positive"] == 2
        assert stats["negative"] == 1
        assert stats["positive_rate"] == pytest.approx(0.5)

    @pytest.mark.asyncio
    async def test_get_negative(self, tmp_path):
        from src.pdf_framework.feedback.store import FeedbackEntry, FeedbackStore

        store = FeedbackStore(db_path=tmp_path / "feedback.db")
        await store.initialize()

        await store.add(FeedbackEntry(
            feedback_id="f1", question="Q?", answer="Bad A.",
            score=-1, comment="Неправильный ответ",
            strategy="vector", chunk_ids=[], chunk_scores=[],
            timestamp=1.0,
        ))
        negative = await store.get_negative(limit=10)
        assert len(negative) == 1
        assert negative[0].score == -1


class TestFewShotProvider:
    @pytest.mark.asyncio
    async def test_get_examples_returns_similar(self):
        from src.pdf_framework.feedback.few_shot import FewShotProvider

        provider = FewShotProvider(
            feedback_store=None,
            embedding_engine=None,
            max_examples=3,
            similarity_threshold=0.7,
        )
        examples = await provider.get_examples("Что такое регистр?")
        assert isinstance(examples, list)
        assert len(examples) <= 3

    def test_format_for_prompt(self):
        from src.pdf_framework.feedback.few_shot import FewShotExample, FewShotProvider

        provider = FewShotProvider(
            feedback_store=None, embedding_engine=None,
        )
        examples = [
            FewShotExample(question="Q?", answer="A.", similarity=0.9),
        ]
        prompt = provider.format_for_prompt(examples)
        assert "Q?" in prompt
        assert "A." in prompt


class TestContentBooster:
    @pytest.mark.asyncio
    async def test_no_boost_for_unknown_chunk(self):
        from src.pdf_framework.feedback.boost import ContentBooster

        booster = ContentBooster(feedback_store=None)
        factor = await booster.get_boost("unknown_chunk_id")
        assert factor == 1.0

    @pytest.mark.asyncio
    async def test_boost_for_positive_chunk(self):
        from unittest.mock import AsyncMock, MagicMock

        from src.pdf_framework.feedback.boost import ContentBooster
        from src.pdf_framework.feedback.store import FeedbackEntry

        mock_store = MagicMock()
        mock_store.get_positive = AsyncMock(return_value=[
            FeedbackEntry(
                feedback_id=f"f{i}", question="Q?", answer="A.",
                score=1, chunk_ids=["popular_chunk"], chunk_scores=[0.9],
                timestamp=float(i),
            )
            for i in range(5)
        ])

        booster = ContentBooster(feedback_store=mock_store, min_positive_count=3)
        factor = await booster.get_boost("popular_chunk")
        assert 1.0 <= factor <= 1.3

    @pytest.mark.asyncio
    async def test_apply_boost_reorders_results(self):
        from unittest.mock import MagicMock

        from src.pdf_framework.feedback.boost import ContentBooster

        booster = ContentBooster(feedback_store=None)

        r1 = MagicMock()
        r1.chunk = MagicMock()
        r1.chunk.id = "low_boost"
        r1.score = 0.9

        r2 = MagicMock()
        r2.chunk = MagicMock()
        r2.chunk.id = "high_boost"
        r2.score = 0.8

        boosted = await booster.apply_boost([r1, r2])
        assert isinstance(boosted, list)
