"""Lightweight lexical normalization shared across memory stores.

Casefold + cheap Russian suffix-stripping so Cyrillic morphoforms match in
lexical search paths (LIKE / token-overlap). Moved verbatim out of
``memory_orchestrator`` (roadmap 260612 P2.G2) so the episodic MCP server can
reuse it without importing the heavy orchestrator module — single source, the
orchestrator now aliases these.

Same idea as ``stem_token`` in memory-first-hook / the top-K salient cache-key
(260609 P1.2). Not a full stemmer — cheap and sufficient for overlap scoring.
"""

from __future__ import annotations

import re

RU_SUFFIXES = (
    # 3-char first (longest-match), then 2-, then 1-char
    "ами",
    "ями",
    "ого",
    "его",
    "ому",
    "ему",
    "ыми",
    "ими",
    "ать",
    "ять",
    "ить",
    "ует",
    "ных",
    "ной",
    "ную",
    "ном",
    "ов",
    "ев",
    "ам",
    "ям",
    "ом",
    "ем",
    "ах",
    "ях",
    "ий",
    "ый",
    "ой",
    "ие",
    "ые",
    "ы",
    "и",
    "а",
    "я",
    "е",
    "у",
    "ю",
    "о",
)


def stem_token(token: str) -> str:
    """Strip a common Russian suffix; English/short tokens pass through."""
    if len(token) < 4 or not any("Ѐ" <= c <= "ӿ" for c in token):
        return token
    for suf in RU_SUFFIXES:
        if token.endswith(suf) and len(token) - len(suf) >= 3:
            return token[: -len(suf)]
    return token


def tokenize(text: str) -> set[str]:
    """Casefold + tokenize + RU-stem → normalized token set for overlap scoring."""
    tokens = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9_\-]+", text.casefold())
    return {stem_token(t) for t in tokens if len(t) >= 2}


__all__ = ["RU_SUFFIXES", "stem_token", "tokenize"]
