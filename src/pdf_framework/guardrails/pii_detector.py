"""PII Detection and Redaction (Phase 53.1).

Detects personally identifiable information in text using regex patterns.
Supports Russian (ИНН, СНИЛС, passport) and international (SSN, credit card) PII types.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class PIIType(str, Enum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    INN = "INN"          # Russian tax ID (10 or 12 digits)
    SNILS = "SNILS"      # Russian social insurance (XXX-XXX-XXX XX)
    PASSPORT = "PASSPORT" # Russian passport (XX XX XXXXXX)
    CREDIT_CARD = "CREDIT_CARD"
    SSN = "SSN"          # US Social Security Number


@dataclass
class PIIMatch:
    pii_type: PIIType
    start: int
    end: int
    value: str


@dataclass
class PIIResult:
    has_pii: bool
    matches: list[PIIMatch] = field(default_factory=list)
    redacted_text: str = ""
    blocked: bool = False


# Luhn algorithm for credit card validation
def _luhn_check(number: str) -> bool:
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


# Compiled patterns for performance
_PATTERNS: list[tuple[PIIType, re.Pattern]] = [
    (PIIType.EMAIL, re.compile(
        r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'
    )),
    (PIIType.PHONE, re.compile(
        r'(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}\b'
    )),
    (PIIType.SNILS, re.compile(
        r'\b\d{3}[\s\-]\d{3}[\s\-]\d{3}[\s\-]?\d{2}\b'
    )),
    (PIIType.PASSPORT, re.compile(
        r'\b\d{2}\s?\d{2}\s?\d{6}\b'
    )),
    (PIIType.INN, re.compile(
        r'\b\d{10}(?:\d{2})?\b'
    )),
    (PIIType.SSN, re.compile(
        r'\b\d{3}[\s\-]\d{2}[\s\-]\d{4}\b'
    )),
    (PIIType.CREDIT_CARD, re.compile(
        r'\b(?:\d{4}[\s\-]?){3}\d{4}\b'
    )),
]


class PIIDetector:
    """Detect and optionally redact PII in text.

    Modes:
        detect — return matches, don't modify text
        redact — replace PII with [PII:TYPE] placeholders
        block  — reject text entirely if PII found
    """

    def __init__(self, mode: Literal["detect", "redact", "block"] = "detect"):
        self.mode = mode

    def scan(self, text: str) -> PIIResult:
        """Scan text for PII patterns."""
        matches: list[PIIMatch] = []

        for pii_type, pattern in _PATTERNS:
            for m in pattern.finditer(text):
                value = m.group()

                # Extra validation for credit cards (Luhn check)
                if pii_type == PIIType.CREDIT_CARD:
                    digits_only = re.sub(r'\D', '', value)
                    if not _luhn_check(digits_only):
                        continue

                # Extra validation for INN — avoid matching arbitrary 10-digit numbers
                # INN must not start with 00
                if pii_type == PIIType.INN:
                    digits_only = re.sub(r'\D', '', value)
                    if digits_only.startswith("00"):
                        continue

                matches.append(PIIMatch(
                    pii_type=pii_type,
                    start=m.start(),
                    end=m.end(),
                    value=value,
                ))

        # Deduplicate overlapping matches (keep longest)
        matches = self._deduplicate(matches)

        has_pii = len(matches) > 0

        if self.mode == "block" and has_pii:
            return PIIResult(has_pii=True, matches=matches, blocked=True)

        redacted_text = text
        if self.mode == "redact" and has_pii:
            redacted_text = self._redact(text, matches)

        return PIIResult(
            has_pii=has_pii,
            matches=matches,
            redacted_text=redacted_text,
            blocked=False,
        )

    @staticmethod
    def _redact(text: str, matches: list[PIIMatch]) -> str:
        """Replace matched PII with [PII:TYPE] placeholders."""
        # Sort by position descending to replace from end to start
        sorted_matches = sorted(matches, key=lambda m: m.start, reverse=True)
        result = text
        for m in sorted_matches:
            placeholder = f"[PII:{m.pii_type.value}]"
            result = result[:m.start] + placeholder + result[m.end:]
        return result

    @staticmethod
    def _deduplicate(matches: list[PIIMatch]) -> list[PIIMatch]:
        """Remove overlapping matches, keeping the longest."""
        if not matches:
            return []
        sorted_matches = sorted(matches, key=lambda m: (m.start, -(m.end - m.start)))
        result = [sorted_matches[0]]
        for m in sorted_matches[1:]:
            prev = result[-1]
            if m.start >= prev.end:
                result.append(m)
            elif (m.end - m.start) > (prev.end - prev.start):
                result[-1] = m
        return result
