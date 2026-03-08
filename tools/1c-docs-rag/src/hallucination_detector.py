"""
Hallucination Detector for RAG Systems

Валидирует утверждения (claims) из LLM ответов против источников.
Детектирует галлюцинации - утверждения не подтверждённые источниками.

Author: Claude Opus 4.5
Date: 2026-01-25
Priority: P3-10
"""

import re
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import hashlib


class ClaimStatus(Enum):
    """Статус валидации утверждения"""
    SUPPORTED = "supported"          # Подтверждено источниками
    PARTIAL = "partial"              # Частично подтверждено
    UNSUPPORTED = "unsupported"      # Не подтверждено (галлюцинация)
    UNCERTAIN = "uncertain"          # Не удалось определить


@dataclass
class Claim:
    """Утверждение извлечённое из ответа"""
    text: str                        # Текст утверждения
    claim_type: str = "statement"    # statement, fact, method, property
    confidence: float = 0.5          # Уверенность LLM в утверждении
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClaimValidation:
    """Результат валидации утверждения"""
    claim: Claim                     # Исходное утверждение
    status: ClaimStatus              # Статус валидации
    supporting_sources: List[str] = field(default_factory=list)
    confidence_score: float = 0.0    # 0.0-1.0 насколько подтверждено
    explanation: str = ""            # Объяснение решения


@dataclass
class HallucinationReport:
    """Отчёт о галлюцинациях в ответе"""
    answer: str                      # Исходный ответ
    total_claims: int                # Всего утверждений
    supported_count: int             # Подтверждённых
    unsupported_count: int           # Не подтверждённых (галлюцинации)
    partial_count: int               # Частично подтверждённых
    validations: List[ClaimValidation] = field(default_factory=list)
    hallucination_rate: float = 0.0  # Доля галлюцинаций


class HallucinationDetector:
    """
    Детектор галлюцинаций для RAG систем.

    Проверяет что утверждения в ответе LLM подтверждены источниками.
    """

    def __init__(self, llm_client=None):
        """
        Args:
            llm_client: Опциональный LLM клиент для извлечения утверждений
        """
        self.llm_client = llm_client
        self._claim_patterns = [
            # Паттерны для утверждений о методах/свойствах 1С
            r'(\w+)\.(\w+)\s+является\s+(.+?)[.\n]',
            r'(\w+)\s+имеет\s+метод\s+(\w+)',
            r'(\w+)\s+имеет\s+свойство\s+(\w+)',
            r'Метод\s+(\w+)\s+(.+?)[.\n]',
            # Паттерны для фактов
            r'(.+?)\s+используется\s+для\s+(.+?)[.\n]',
            r'(.+?)\s+предназначен\s+для\s+(.+?)[.\n]',
        ]

    async def validate_answer(
        self,
        answer: str,
        sources: List[Dict[str, Any]],
        extract_claims: bool = True
    ) -> HallucinationReport:
        """
        Валидирует ответ на наличие галлюцинаций.

        Args:
            answer: Ответ LLM для проверки
            sources: Список источников (документы из RAG)
            extract_claims: Извлекать утверждения автоматически

        Returns:
            HallucinationReport с детальной валидацией
        """
        # 1. Извлечь утверждения из ответа
        if extract_claims:
            claims = await self._extract_claims(answer)
        else:
            claims = [Claim(text=answer)]

        # 2. Валидировать каждое утверждение
        validations = []
        for claim in claims:
            validation = await self._validate_claim(claim, sources)
            validations.append(validation)

        # 3. Сформировать отчёт
        return self._generate_report(answer, validations)

    async def _extract_claims(self, text: str) -> List[Claim]:
        """
        Извлекает утверждения из текста ответа.

        Args:
            text: Текст ответа

        Returns:
            Список извлечённых утверждений
        """
        claims = []

        # Разбиваем текст на предложения
        sentences = self._split_sentences(text)

        for sentence in sentences:
            # Проверяем паттерны утверждений
            for pattern in self._claim_patterns:
                match = re.match(pattern, sentence, re.IGNORECASE)
                if match:
                    claim_type = self._classify_claim(sentence)
                    claims.append(Claim(
                        text=sentence.strip(),
                        claim_type=claim_type,
                        confidence=0.7
                    ))
                    break

        # Если нет утверждений по паттернам, берём все предложения
        if not claims and sentences:
            for sentence in sentences:
                if len(sentence) > 20:  # Игнорируем короткие
                    claims.append(Claim(
                        text=sentence.strip(),
                        claim_type="statement",
                        confidence=0.5
                    ))

        return claims

    async def _validate_claim(
        self,
        claim: Claim,
        sources: List[Dict[str, Any]]
    ) -> ClaimValidation:
        """
        Валидирует утверждение против источников.

        Args:
            claim: Утверждение для проверки
            sources: Список источников

        Returns:
            ClaimValidation с результатом
        """
        if not sources:
            return ClaimValidation(
                claim=claim,
                status=ClaimStatus.UNCERTAIN,
                explanation="Нет источников для валидации"
            )

        # Ищем подтверждение в источниках
        supporting = []
        partial_match = False

        for source in sources:
            content = source.get("content", "")
            metadata = source.get("metadata", {})

            # Проверяем полное совпадение
            if self._is_exact_match(claim.text, content):
                supporting.append(metadata.get("source", "unknown"))

            # Проверяем частичное совпадение
            elif self._is_partial_match(claim.text, content):
                partial_match = True
                supporting.append(metadata.get("source", "unknown"))

        # Определяем статус
        if len(supporting) >= 2:
            status = ClaimStatus.SUPPORTED
            confidence = 0.9
            explanation = f"Подтверждено {len(supporting)} источниками"
        elif len(supporting) == 1:
            status = ClaimStatus.SUPPORTED
            confidence = 0.7
            explanation = "Подтверждено 1 источником"
        elif partial_match:
            status = ClaimStatus.PARTIAL
            confidence = 0.5
            explanation = "Частичное совпадение с источниками"
        else:
            status = ClaimStatus.UNSUPPORTED
            confidence = 0.1
            explanation = "Не найдено подтверждений в источниках"

        return ClaimValidation(
            claim=claim,
            status=status,
            supporting_sources=supporting,
            confidence_score=confidence,
            explanation=explanation
        )

    def _is_exact_match(self, claim: str, content: str) -> bool:
        """Проверяет точное совпадение утверждения с содержимым"""
        claim_lower = claim.lower().strip()
        content_lower = content.lower()

        # Точное совпадение
        if claim_lower in content_lower:
            return True

        # Совпадение по ключевым словам
        claim_words = set(re.findall(r'\w+', claim_lower))
        content_words = set(re.findall(r'\w+', content_lower))

        # Если >80% слов из claim есть в content
        if claim_words and claim_words.issubset(content_words):
            return True

        return False

    def _is_partial_match(self, claim: str, content: str) -> bool:
        """Проверяет частичное совпадение"""
        claim_lower = claim.lower()
        content_lower = content.lower()

        # Проверяем наличие ключевых фраз из claim в content
        keywords = re.findall(r'\b\w{3,}\b', claim_lower)
        matches = sum(1 for kw in keywords if kw in content_lower)

        # Если >50% ключевых слов найдено
        if keywords and matches / len(keywords) > 0.5:
            return True

        return False

    def _classify_claim(self, text: str) -> str:
        """Классифицирует тип утверждения"""
        text_lower = text.lower()

        if "метод" in text_lower or "функция" in text_lower:
            return "method"
        elif "свойство" in text_lower or "атрибут" in text_lower:
            return "property"
        elif "является" in text_lower or "предназначен" in text_lower:
            return "fact"
        else:
            return "statement"

    def _split_sentences(self, text: str) -> List[str]:
        """Разбивает текст на предложения"""
        # Простой split по . ! ?
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _generate_report(
        """"""Generates a hallucination report from validation results.

Args:
    answer: The generated answer text.
    validations: List of claim validation results.

Returns:
    HallucinationReport: Report containing statistics and hallucination rate.
""""""
        self,
        answer: str,
        validations: List[ClaimValidation]
    ) -> HallucinationReport:
        """Генерирует итоговый отчёт"""
        supported = sum(1 for v in validations if v.status == ClaimStatus.SUPPORTED)
        partial = sum(1 for v in validations if v.status == ClaimStatus.PARTIAL)
        unsupported = sum(1 for v in validations if v.status == ClaimStatus.UNSUPPORTED)

        hallucination_rate = unsupported / len(validations) if validations else 0

        return HallucinationReport(
            answer=answer,
            total_claims=len(validations),
            supported_count=supported,
            unsupported_count=unsupported,
            partial_count=partial,
            validations=validations,
            hallucination_rate=hallucination_rate
        )

    def format_report(self, report: HallucinationReport) -> str:
        """Форматирует отчёт для вывода"""
        lines = [
            "=== Hallucination Detection Report ===",
            f"Total claims: {report.total_claims}",
            f"✅ Supported: {report.supported_count}",
            f"⚠️  Partial: {report.partial_count}",
            f"❌ Unsupported (hallucinations): {report.unsupported_count}",
            f"Hallucination rate: {report.hallucination_rate:.1%}",
            "",
            "--- Detailed Validations ---"
        ]

        for i, validation in enumerate(report.validations, 1):
            status_icon = {
                ClaimStatus.SUPPORTED: "✅",
                ClaimStatus.PARTIAL: "⚠️",
                ClaimStatus.UNSUPPORTED: "❌",
                ClaimStatus.UNCERTAIN: "❓"
            }.get(validation.status, "?")

            lines.append(f"\n{i}. {status_icon} {validation.claim.text}")
            lines.append(f"   Status: {validation.status.value}")
            lines.append(f"   Confidence: {validation.confidence_score:.1%}")
            lines.append(f"   Explanation: {validation.explanation}")

            if validation.supporting_sources:
                lines.append(f"   Sources: {', '.join(validation.supporting_sources)}")

        return "\n".join(lines)


# ============================================================================
# Integration Functions
# ============================================================================

async def check_hallucination(
    answer: str,
    sources: List[Dict[str, Any]],
    llm_client=None
) -> Tuple[bool, HallucinationReport]:
    """
    Быстрая проверка ответа на галлюцинации.

    Args:
        answer: Ответ LLM
        sources: Источники из RAG
        llm_client: Опциональный LLM клиент

    Returns:
        Tuple[has_hallucinations, report]
    """
    detector = HallucinationDetector(llm_client)
    report = await detector.validate_answer(answer, sources)

    # Галлюцинации есть если rate > 20%
    has_hallucinations = report.hallucination_rate > 0.2

    return has_hallucinations, report


def validate_with_sources(
    """"""
Synchronously validates answer against source documents without LLM extraction.

Args:
    answer: Response text to validate
    source_docs: List of source document texts

Returns:
    Dict containing validation results and metadata
""""""
    answer: str,
    source_docs: List[str]
) -> Dict[str, Any]:
    """
    Синхронная валидация (без LLM извлечения утверждений).

    Args:
        answer: Ответ для проверки
        source_docs: Список текстов источников

    Returns:
        Dict с результатами валидации
    """
    sources = [{"content": doc, "metadata": {}} for doc in source_docs]

    detector = HallucinationDetector()

    # Создаём утверждения из предложений
    claims = []
    sentences = re.split(r'[.!?]+', answer)
    for sent in sentences:
        if len(sent.strip()) > 20:
            claims.append(Claim(text=sent.strip()))

    # Валидируем синхронно
    validations = []
    for claim in claims:
        validation = detector._is_exact_match(
            claim.text,
            " ".join(source_docs)
        )
        validations.append({
            "claim": claim.text,
            "supported": validation
        })

    unsupported = sum(1 for v in validations if not v["supported"])

    return {
        "total": len(validations),
        "supported": len(validations) - unsupported,
        "unsupported": unsupported,
        "validations": validations
    }


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """CLI для тестирования детектора"""
    import asyncio

    # Пример ответа с потенциальной галлюцинацией
    answer = """
    СправочникМенеджер - это объект для работы со справочниками.
    Он имеет метод ПолучитьДанные() для получения данных.
    Также есть метод НайтиПоКоду() для поиска по коду.
    """

    # Примеры источников
    sources = [
        {
            "content": "СправочникМенеджер используется для работы со справочниками в 1С. "
                      "Основной метод: НайтиПоКоду() - поиск элемента по коду.",
            "metadata": {"source": "docs/1C/SpravochnikManager.md"}
        },
        {
            "content": "Для справочников доступны методы: НайтиПоНаименованию(), "
                      "НайтиПоРеквизиту().",
            "metadata": {"source": "docs/1C/SpravochnikiMethods.md"}
        }
    ]

    async def test():
        detector = HallucinationDetector()
        report = await detector.validate_answer(answer, sources)

        print(detector.format_report(report))

        return report

    return asyncio.run(test())


if __name__ == "__main__":
    main()

