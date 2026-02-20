"""Prompt Injection Defense (Phase 53.2).

Detects prompt injection attempts using pattern matching and scoring.
Covers direct injection, encoding tricks, and delimiter attacks.
"""

import base64
import logging
import re
from dataclasses import dataclass, field
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass
class InjectionMatch:
    pattern_name: str
    matched_text: str
    confidence: float


@dataclass
class InjectionResult:
    is_injection: bool
    score: float  # 0.0 — 1.0
    matches: list[InjectionMatch] = field(default_factory=list)
    action_taken: str = "none"  # none, logged, warned, blocked


# Injection patterns with confidence weights
_INJECTION_PATTERNS: list[tuple[str, re.Pattern, float]] = [
    # Direct instruction override
    ("ignore_previous", re.compile(
        r'(?:ignore|forget|disregard|override)\s+(?:all\s+)?(?:previous|above|prior|earlier)\s+'
        r'(?:instructions?|prompts?|rules?|context)',
        re.IGNORECASE,
    ), 0.9),
    ("system_prompt_leak", re.compile(
        r'(?:show|reveal|print|output|display|repeat)\s+(?:\w+\s+)*?(?:system\s+)?'
        r'(?:prompt|instructions?|rules?|configuration)',
        re.IGNORECASE,
    ), 0.8),
    ("new_instructions", re.compile(
        r'(?:new\s+instructions?|from\s+now\s+on|you\s+are\s+now|act\s+as|pretend\s+(?:to\s+be|you\s+are))',
        re.IGNORECASE,
    ), 0.85),
    ("role_play", re.compile(
        r'(?:you\s+are\s+(?:a\s+)?(?:DAN|evil|unfiltered|jailbroken|uncensored))',
        re.IGNORECASE,
    ), 0.95),
    ("do_anything", re.compile(
        r'(?:do\s+anything\s+now|no\s+restrictions?|without\s+(?:any\s+)?(?:restrictions?|limitations?|filters?))',
        re.IGNORECASE,
    ), 0.9),

    # Delimiter injection
    ("delimiter_xml", re.compile(
        r'</?(system|user|assistant|instruction|prompt|context)\s*/?>',
        re.IGNORECASE,
    ), 0.7),
    ("delimiter_markdown", re.compile(
        r'```(?:system|prompt|instruction)',
        re.IGNORECASE,
    ), 0.6),
    ("delimiter_separator", re.compile(
        r'(?:-{5,}|={5,}|\*{5,})\s*(?:SYSTEM|INSTRUCTION|END|BEGIN)',
        re.IGNORECASE,
    ), 0.65),

    # Encoding-based evasion
    ("unicode_homoglyph", re.compile(
        r'[\u0410-\u042f\u0430-\u044f].*(?:ignore|system|prompt)',  # Cyrillic mixed with Latin keywords
        re.IGNORECASE,
    ), 0.4),
    ("zero_width_chars", re.compile(
        r'[\u200b\u200c\u200d\u2060\ufeff]{2,}',
    ), 0.5),
]

# Base64 patterns that might contain injection
_BASE64_PATTERN = re.compile(r'[A-Za-z0-9+/]{20,}={0,2}')


class InjectionDefense:
    """Detect prompt injection attempts with confidence scoring.

    Modes:
        log   — detect and log, don't modify
        warn  — add warning to response metadata
        block — reject request if score >= threshold
    """

    def __init__(
        self,
        mode: Literal["log", "warn", "block"] = "log",
        threshold: float = 0.7,
    ):
        self.mode = mode
        self.threshold = threshold

    def scan(self, text: str) -> InjectionResult:
        """Scan text for injection patterns."""
        matches: list[InjectionMatch] = []

        # 1. Pattern matching
        for pattern_name, pattern, confidence in _INJECTION_PATTERNS:
            for m in pattern.finditer(text):
                matches.append(InjectionMatch(
                    pattern_name=pattern_name,
                    matched_text=m.group()[:100],
                    confidence=confidence,
                ))

        # 2. Base64 decoding check
        for m in _BASE64_PATTERN.finditer(text):
            try:
                decoded = base64.b64decode(m.group()).decode("utf-8", errors="ignore")
                # Check if decoded text contains injection patterns
                for pattern_name, pattern, confidence in _INJECTION_PATTERNS[:5]:
                    if pattern.search(decoded):
                        matches.append(InjectionMatch(
                            pattern_name=f"base64_{pattern_name}",
                            matched_text=f"base64({m.group()[:30]}...)",
                            confidence=confidence * 0.9,
                        ))
            except Exception:
                pass

        # 3. Compute aggregate score
        score = self._compute_score(matches)

        is_injection = score >= self.threshold

        # Determine action
        action = "none"
        if is_injection:
            if self.mode == "block":
                action = "blocked"
            elif self.mode == "warn":
                action = "warned"
            elif self.mode == "log":
                action = "logged"
                logger.warning(
                    "[INJECTION] Detected injection (score=%.2f): %s",
                    score,
                    [m.pattern_name for m in matches],
                )

        return InjectionResult(
            is_injection=is_injection,
            score=round(score, 3),
            matches=matches,
            action_taken=action,
        )

    @staticmethod
    def _compute_score(matches: list[InjectionMatch]) -> float:
        """Compute aggregate injection confidence score (0-1)."""
        if not matches:
            return 0.0

        # Use max confidence + diminishing bonus for additional matches
        sorted_conf = sorted([m.confidence for m in matches], reverse=True)
        score = sorted_conf[0]
        for i, conf in enumerate(sorted_conf[1:], 1):
            score += conf * (0.5 ** i)  # Diminishing returns
        return min(1.0, score)
