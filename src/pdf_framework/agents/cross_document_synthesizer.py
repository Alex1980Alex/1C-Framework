"""Cross-Document Synthesizer for Deep Research (Phase 19.3).

Synthesizes answers from multiple documents with citation chains.
Combines information from different sources while handling conflicts.

Based on Dify's cross-document synthesis pattern.

Author: Claude Code
Version: 1.0.0 - Phase 19: Deep Research Agent
"""

import logging
from typing import Any

from anthropic import Anthropic
from pydantic import BaseModel, Field

from src.pdf_framework.config import Settings, get_settings
from src.pdf_framework.schemas.documents import SearchResult

logger = logging.getLogger(__name__)


class SourceCitation(BaseModel):
    """A citation for a specific source."""

    chunk_id: str
    source: str
    page_number: int | None = None
    snippet: str = ""
    relevance_score: float = 0.0


class SynthesizedAnswer(BaseModel):
    """A synthesized answer with citations."""

    answer: str
    citations: list[SourceCitation]
    confidence: float = 0.0  # 0-1
    conflicting_info: list[str] = Field(default_factory=list)
    synthesis_reasoning: str = ""


class CrossDocumentSynthesizer:
    """Synthesizes answers from multiple document sources.

    Combines information from different chunks/documents,
    provides citations, and handles conflicting information.
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-opus-4-6",
        settings: Settings | None = None,
    ):
        """Initialize the synthesizer.

        Args:
            api_key: Anthropic API key (empty = use env)
            model: Claude model for synthesis
            settings: Application settings
        """
        self._client = Anthropic(api_key=api_key or None)
        self._model = model
        self._settings = settings or get_settings()

    def synthesize(
        self,
        query: str,
        results: list[SearchResult],
        context: str = "",
    ) -> SynthesizedAnswer:
        """Synthesize answer from multiple search results.

        Args:
            query: Original user query
            results: Search results from multiple documents
            context: Additional context from multi-step retrieval

        Returns:
            Synthesized answer with citations
        """
        if not results:
            return SynthesizedAnswer(
                answer="Не найдено релевантной информации для ответа на вопрос.",
                citations=[],
                confidence=0.0,
            )

        # Build synthesis prompt
        prompt = self._build_synthesis_prompt(query, results, context)

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            result = response.content[0].text
            answer = self._parse_synthesis(result, results)

            logger.info(
                f"[SYNTHESIZER] Synthesized answer from {len(results)} sources "
                f"with {len(answer.citations)} citations (confidence: {answer.confidence:.2f})"
            )

            return answer

        except Exception as e:
            logger.error(f"[SYNTHESIZER] Failed to synthesize answer: {e}")
            # Fallback: simple concatenation
            return self._fallback_synthesis(query, results)

    def _build_synthesis_prompt(
        self,
        query: str,
        results: list[SearchResult],
        context: str,
    ) -> str:
        """Build prompt for answer synthesis.

        Args:
            query: User query
            results: Search results
            context: Additional context

        Returns:
            Prompt string
        """
        # Format results as source passages
        passages = []
        for i, result in enumerate(results):
            source = result.chunk.metadata.get("source", "Unknown")
            page = result.chunk.metadata.get("page_number")
            snippet = result.chunk.content[:500]

            passage = f"""[Источник {i + 1}]
Файл: {source}
Страница: {page if page else "не указана"}
Релевантность: {result.score:.3f}

Текст:
{snippet}
"""

            passages.append(passage)

        passages_text = "\n\n".join(passages)

        prompt = f"""Вы - исследователь, специализирующийся на анализе документации 1С:Предприятие.

**Вопрос пользователя:**
{query}

**Дополнительный контекст:**
{context if context else "(нет дополнительного контекста)"}

**Доступные источники:**
{passages_text}

**Задача:**
Проанализируйте источники и предоставьте комплексный ответ на вопрос. Требования:

1. **Точность:** Используйте только информацию из предоставленных источников
2. **Цитирование:** Указывайте номера источников [1], [2] и т.д. для каждого утверждения
3. **Противоречия:** Если источники противоречат друг другу - укажите это явно
4. **Полнота:** Объедините информацию из разных источников для полного ответа
5. **Структура:**
   - Краткий ответ (1-2 предложения)
   - Подробное объяснение с цитатами
   - Замеченные противоречия (если есть)
   - Уверенность в ответе (высокая/средняя/низкая)

**Формат вывода (JSON):**
{{
    "answer": "Комплексный ответ с цитатами [1], [2]...",
    "citations": [
        {{
            "chunk_id": "id_из_результатов",
            "source": "файл_источника",
            "page_number": номер_страницы,
            "snippet": "цитата_из_текста",
            "relevance_score": 0.85
        }}
    ],
    "confidence": 0.8,
    "conflicting_info": ["противоречие_1", "противоречие_2"],
    "synthesis_reasoning": "как_был_получен_ответ"
}}

**Пример:**
Вопрос: "Какие режимы блокировок существуют в 1С:Предприятие?"

{{
    "answer": "В 1С:Предприятие существует два основных режима блокировок: управляемый и автоматический [1]. Управляемый режим позволяет программисту явно указывать моменты блокировки, а автоматический режим управляется платформой [2]. При управляемом режиме блокировки устанавливаются только при начале транзакции [1], в то время как автоматический режим может блокировать записи при чтении [2].",
    "citations": [
        {{
            "chunk_id": "chunk_123",
            "source": "ManagedLockModes.pdf",
            "page_number": 15,
            "snippet": "Управляемый режим блокировок устанавливает блокировку только в момент начала транзакции",
            "relevance_score": 0.92
        }},
        {{
            "chunk_id": "chunk_456",
            "source": "ConcurrencyGuide.pdf",
            "page_number": 23,
            "snippet": "Автоматический режим может блокировать записи уже при чтении данных",
            "relevance_score": 0.88
        }}
    ],
    "confidence": 0.9,
    "conflicting_info": [],
    "synthesis_reasoning": "Информация из двух источников согласована и дополняет друг друга"
}}
"""

        return prompt

    def _parse_synthesis(
        self,
        result: str,
        search_results: list[SearchResult],
    ) -> SynthesizedAnswer:
        """Parse LLM response into SynthesizedAnswer.

        Args:
            result: LLM response text
            search_results: Original search results for citation lookup

        Returns:
            Parsed SynthesizedAnswer
        """
        import json

        try:
            # Extract JSON from response
            start = result.find("{")
            end = result.rfind("}") + 1

            if start == -1 or end == 0:
                raise ValueError("No JSON found in response")

            json_str = result[start:end]
            data = json.loads(json_str)

            # Parse citations
            citations = []
            for cit in data.get("citations", []):
                # Find matching search result
                matching_result = None
                for sr in search_results:
                    if sr.chunk.id == cit.get("chunk_id"):
                        matching_result = sr
                        break

                citation = SourceCitation(
                    chunk_id=cit.get("chunk_id", ""),
                    source=cit.get("source", ""),
                    page_number=cit.get("page_number"),
                    snippet=cit.get("snippet", ""),
                    relevance_score=cit.get("relevance_score", 0.0),
                )
                citations.append(citation)

            return SynthesizedAnswer(
                answer=data.get("answer", ""),
                citations=citations,
                confidence=data.get("confidence", 0.0),
                conflicting_info=data.get("conflicting_info", []),
                synthesis_reasoning=data.get("synthesis_reasoning", ""),
            )

        except Exception as e:
            logger.warning(f"[SYNTHESIZER] Failed to parse synthesis: {e}")
            return self._fallback_synthesis("", search_results)

    def _fallback_synthesis(
        self,
        query: str,
        results: list[SearchResult],
    ) -> SynthesizedAnswer:
        """Fallback synthesis when LLM parsing fails.

        Args:
            query: Original query
            results: Search results

        Returns:
            Basic SynthesizedAnswer
        """
        # Combine top results
        combined_text = "\n\n".join([
            f"[{i + 1}] {r.chunk.content}"
            for i, r in enumerate(results[:3])
        ])

        citations = [
            SourceCitation(
                chunk_id=r.chunk.id,
                source=r.chunk.metadata.get("source", ""),
                page_number=r.chunk.metadata.get("page_number"),
                snippet=r.chunk.content[:200],
                relevance_score=r.score,
            )
            for r in results[:5]
        ]

        return SynthesizedAnswer(
            answer=f"На основе найденных источников:\n\n{combined_text}",
            citations=citations,
            confidence=0.5,
            conflicting_info=[],
            synthesis_reasoning="Fallback: простое объединение результатов",
        )


def synthesize_cross_document(
    query: str,
    results: list[SearchResult],
    api_key: str = "",
    model: str = "claude-opus-4-6",
) -> SynthesizedAnswer:
    """Convenience function for cross-document synthesis.

    Args:
        query: User query
        results: Search results from multiple documents
        api_key: Anthropic API key
        model: Claude model to use

    Returns:
        SynthesizedAnswer with citations
    """
    synthesizer = CrossDocumentSynthesizer(api_key=api_key, model=model)
    return synthesizer.synthesize(query, results)
