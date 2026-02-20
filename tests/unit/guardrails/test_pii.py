"""Unit tests for PII Detector (Phase 53.1)."""

import pytest

from src.pdf_framework.guardrails.pii_detector import PIIDetector, PIIType


class TestPIIDetection:
    """Test PII pattern detection for all types."""

    def test_detect_email(self):
        detector = PIIDetector(mode="detect")
        result = detector.scan("Напишите на user@example.com для связи")
        assert result.has_pii
        assert any(m.pii_type == PIIType.EMAIL for m in result.matches)

    def test_detect_phone_russian(self):
        detector = PIIDetector(mode="detect")
        result = detector.scan("Телефон: +7 (495) 123-45-67")
        assert result.has_pii
        assert any(m.pii_type == PIIType.PHONE for m in result.matches)

    def test_detect_phone_eight(self):
        detector = PIIDetector(mode="detect")
        result = detector.scan("Звоните: 8-495-123-45-67")
        assert result.has_pii
        assert any(m.pii_type == PIIType.PHONE for m in result.matches)

    def test_detect_snils(self):
        detector = PIIDetector(mode="detect")
        result = detector.scan("СНИЛС: 123-456-789 00")
        assert result.has_pii
        assert any(m.pii_type == PIIType.SNILS for m in result.matches)

    def test_detect_ssn(self):
        detector = PIIDetector(mode="detect")
        result = detector.scan("SSN: 123-45-6789")
        assert result.has_pii
        assert any(m.pii_type == PIIType.SSN for m in result.matches)

    def test_detect_credit_card_valid_luhn(self):
        detector = PIIDetector(mode="detect")
        # 4111111111111111 passes Luhn check (Visa test number)
        result = detector.scan("Карта: 4111 1111 1111 1111")
        assert result.has_pii
        assert any(m.pii_type == PIIType.CREDIT_CARD for m in result.matches)

    def test_no_false_positive_invalid_cc(self):
        detector = PIIDetector(mode="detect")
        # Random 16-digit number that fails Luhn
        result = detector.scan("Номер: 1234 5678 9012 3456")
        cc_matches = [m for m in result.matches if m.pii_type == PIIType.CREDIT_CARD]
        assert len(cc_matches) == 0

    def test_no_pii_in_clean_text(self):
        detector = PIIDetector(mode="detect")
        result = detector.scan("Справочник 'Номенклатура' содержит список товаров и услуг.")
        assert not result.has_pii

    def test_multiple_pii_types(self):
        detector = PIIDetector(mode="detect")
        text = "Email: test@mail.ru, Телефон: +7 495 123 45 67, СНИЛС: 111-222-333 44"
        result = detector.scan(text)
        assert result.has_pii
        pii_types = {m.pii_type for m in result.matches}
        assert PIIType.EMAIL in pii_types
        assert PIIType.PHONE in pii_types


class TestPIIRedaction:
    """Test PII redaction mode."""

    def test_redact_email(self):
        detector = PIIDetector(mode="redact")
        result = detector.scan("Напишите на user@example.com")
        assert "[PII:EMAIL]" in result.redacted_text
        assert "user@example.com" not in result.redacted_text

    def test_redact_phone(self):
        detector = PIIDetector(mode="redact")
        result = detector.scan("Звоните: +7 (495) 123-45-67")
        assert "[PII:PHONE]" in result.redacted_text

    def test_redact_preserves_non_pii(self):
        detector = PIIDetector(mode="redact")
        result = detector.scan("Контакт: user@mail.ru, компания ООО 'Ромашка'")
        assert "ООО 'Ромашка'" in result.redacted_text
        assert "[PII:EMAIL]" in result.redacted_text


class TestPIIBlock:
    """Test PII block mode."""

    def test_block_mode_blocks(self):
        detector = PIIDetector(mode="block")
        result = detector.scan("Email: admin@corp.ru")
        assert result.blocked
        assert result.has_pii

    def test_block_mode_allows_clean(self):
        detector = PIIDetector(mode="block")
        result = detector.scan("Чистый текст без персональных данных")
        assert not result.blocked
        assert not result.has_pii
