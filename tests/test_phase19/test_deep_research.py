"""Phase 19: Deep Research Agent — tests.

Tests for:
  - ResearchPlanner: classify complexity, generate sub-questions
  - CrossDocumentSynthesizer: merge sub-results into comprehensive answer
  - ResearchQualityChecker: coverage and groundedness checks
"""

import pytest


class TestResearchPlanner:
    @pytest.mark.asyncio
    async def test_simple_question_not_deep(self):
        from src.pdf_framework.agents.deep.planner import ResearchPlanner

        planner = ResearchPlanner(llm=None)
        should = await planner.should_use_deep_research("Что такое регистр накопления?")
        assert should is False

    @pytest.mark.asyncio
    async def test_complex_question_triggers_deep(self):
        from src.pdf_framework.agents.deep.planner import ResearchPlanner

        planner = ResearchPlanner(llm=None)
        should = await planner.should_use_deep_research(
            "Сравните механизм событий форм в тонком клиенте и в веб-клиенте"
        )
        assert should is True

    @pytest.mark.asyncio
    async def test_create_plan_returns_sub_questions(self):
        from src.pdf_framework.agents.deep.planner import ResearchPlanner

        planner = ResearchPlanner(llm=None)
        plan = await planner.create_plan(
            "Опишите цикл жизни документа от создания до записи в регистры"
        )
        assert len(plan.sub_questions) >= 2
        assert len(plan.sub_questions) <= 4
        assert plan.complexity in ("moderate", "complex")

    @pytest.mark.asyncio
    async def test_plan_sub_questions_have_strategies(self):
        from src.pdf_framework.agents.deep.planner import ResearchPlanner

        planner = ResearchPlanner(llm=None)
        plan = await planner.create_plan("Сравните регистр накопления и регистр сведений")
        for sq in plan.sub_questions:
            assert sq.strategy in ("vector", "hybrid", "graphrag_local", "bm25", "adaptive")


class TestCrossDocumentSynthesizer:
    @pytest.mark.asyncio
    async def test_synthesize_multiple_results(self):
        from src.pdf_framework.agents.deep.synthesizer import (
            CrossDocumentSynthesizer,
            SubResult,
        )

        synthesizer = CrossDocumentSynthesizer(llm=None)
        sub_results = [
            SubResult(
                sub_question="Что такое регистр накопления?",
                answer="Регистр накопления хранит остатки и обороты.",
                sources=["doc1.pdf"],
                key_findings=["хранит остатки"],
                entities_found=["регистр накопления"],
                confidence=0.9,
            ),
            SubResult(
                sub_question="Что такое регистр сведений?",
                answer="Регистр сведений хранит произвольные данные.",
                sources=["doc2.pdf"],
                key_findings=["произвольные данные"],
                entities_found=["регистр сведений"],
                confidence=0.85,
            ),
        ]
        answer, citations = await synthesizer.synthesize(
            "Сравните регистры", sub_results, ""
        )
        assert len(answer) > 0
        assert len(citations) > 0

    @pytest.mark.asyncio
    async def test_build_citation_chain(self):
        from src.pdf_framework.agents.deep.synthesizer import CrossDocumentSynthesizer

        synthesizer = CrossDocumentSynthesizer(llm=None)
        citations = await synthesizer.build_citation_chain(
            "Регистр [1] хранит данные [2].",
            [],
        )
        assert isinstance(citations, list)


class TestResearchQualityChecker:
    @pytest.mark.asyncio
    async def test_quality_check_complete_answer(self):
        from src.pdf_framework.agents.deep.quality import ResearchQualityChecker

        checker = ResearchQualityChecker(llm=None)
        result = await checker.check(
            question="Что такое регистр?",
            plan=None,
            answer="Регистр — прикладной объект, хранящий данные.",
            sub_results=[],
        )
        assert result.coverage_score >= 0.0
        assert result.coverage_score <= 1.0
        assert isinstance(result.needs_followup, bool)

    @pytest.mark.asyncio
    async def test_quality_check_detects_gaps(self):
        from src.pdf_framework.agents.deep.quality import ResearchQualityChecker

        checker = ResearchQualityChecker(llm=None)
        result = await checker.check(
            question="Сравните все типы регистров с примерами",
            plan=None,
            answer="Регистр накопления хранит остатки.",  # incomplete
            sub_results=[],
        )
        assert len(result.gaps) > 0 or result.needs_followup is True
