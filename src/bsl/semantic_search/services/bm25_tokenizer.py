"""Canonical CamelCase tokenizer for BSL BM25 sparse vectors."""

from __future__ import annotations

import re

CAMELCASE_RE = re.compile(r"[А-ЯЁ][а-яё]*|[A-Z][a-z]*|[а-яё]+|[a-z]+|\d+")


def normalize_camelcase(text: str) -> str:
    parts = CAMELCASE_RE.findall(text)
    return " ".join(parts).lower() if parts else text.lower()
