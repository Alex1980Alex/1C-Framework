"""Fuzzy keyword matching with lemmatization for Russian text.

Combines pymorphy3 (handles inflection) + rapidfuzz (handles typos)
for robust intent detection in hooks.

Usage:
    from shared.fuzzy_match import FuzzyMatcher

    matcher = FuzzyMatcher(keywords=["удалить", "создать", "добавить"])
    matches = matcher.match_prompt("нужно удалть эти файлы автаматически")
    # → [("удалить", 87.5)]  — caught despite typo "удалть"
"""

from __future__ import annotations

from typing import Sequence

# Lazy-loaded to keep import fast (hooks have 3s timeout)
_morph = None
_tokenize = None


def _get_morph():
    global _morph
    if _morph is None:
        from pymorphy3 import MorphAnalyzer
        _morph = MorphAnalyzer()
    return _morph


def _get_tokenize():
    global _tokenize
    if _tokenize is None:
        try:
            from razdel import tokenize as _tok
            _tokenize = _tok
        except ImportError:
            # Fallback: simple split
            _tokenize = None
    return _tokenize


def tokenize_text(text: str) -> list[str]:
    """Tokenize text, preferring razdel if available."""
    tok = _get_tokenize()
    if tok is not None:
        return [t.text.lower() for t in tok(text) if len(t.text) > 1]
    return [w for w in text.lower().split() if len(w) > 1]


def lemmatize(word: str) -> str:
    """Get normal form (lemma) of a Russian word."""
    morph = _get_morph()
    return morph.parse(word)[0].normal_form


class FuzzyMatcher:
    """Keyword matcher with lemmatization + fuzzy tolerance.

    Three-step matching per token:
    1. Exact lemma match (handles inflection: "удалим" → "удалить")
    2. Fuzzy match on original token (handles typos: "удалть" → "удалить")
    3. Fuzzy match on lemma (handles typo+inflection combo)
    """

    def __init__(
        self,
        keywords: Sequence[str],
        fuzzy_threshold: int = 78,
    ):
        self.keywords = set(keywords)
        self.fuzzy_threshold = fuzzy_threshold
        # Pre-compute lemmas of keywords for faster lookup
        self._keyword_lemmas: dict[str, str] = {}
        for kw in keywords:
            try:
                self._keyword_lemmas[lemmatize(kw)] = kw
            except Exception:
                pass

    def match_token(self, token: str) -> tuple[str, float] | None:
        """Match a single token against keywords.

        Returns (matched_keyword, score) or None.
        Score: 100.0 for exact/lemma match, <100 for fuzzy.
        """
        # Step 1: Exact match
        if token in self.keywords:
            return (token, 100.0)

        # Step 2: Lemma match (handles inflection)
        try:
            token_lemma = lemmatize(token)
        except Exception:
            token_lemma = token

        if token_lemma in self.keywords:
            return (token_lemma, 100.0)
        if token_lemma in self._keyword_lemmas:
            return (self._keyword_lemmas[token_lemma], 100.0)

        # Step 3: Fuzzy match on original token (handles typos)
        from rapidfuzz import fuzz, process
        result = process.extractOne(
            token, self.keywords, scorer=fuzz.ratio
        )
        if result and result[1] >= self.fuzzy_threshold:
            return (result[0], result[1])

        # Step 4: Fuzzy match on lemma (handles typo+inflection)
        if token_lemma != token:
            result = process.extractOne(
                token_lemma, self.keywords, scorer=fuzz.ratio
            )
            if result and result[1] >= self.fuzzy_threshold:
                return (result[0], result[1])

        return None

    def match_prompt(self, prompt: str) -> list[tuple[str, float]]:
        """Match all tokens in a prompt against keywords.

        Returns list of (keyword, score) for matched tokens.
        Deduplicates by keyword (keeps highest score).
        """
        tokens = tokenize_text(prompt)
        matches: dict[str, float] = {}
        for token in tokens:
            result = self.match_token(token)
            if result:
                kw, score = result
                if kw not in matches or score > matches[kw]:
                    matches[kw] = score
        return [(kw, score) for kw, score in matches.items()]

    def has_match(self, prompt: str) -> bool:
        """Quick check: does prompt contain any keyword?"""
        tokens = tokenize_text(prompt)
        return any(self.match_token(t) is not None for t in tokens)

    def match_count(self, prompt: str) -> int:
        """Count unique matched keywords in prompt."""
        return len(self.match_prompt(prompt))
