"""Docs invariants — chapter 01_ОБЗОР vs Phase 8 production stack (§3.5.2)."""

from pathlib import Path

import pytest

CHAPTER_DIR = Path(__file__).resolve().parent.parent / "docs" / "framework documentation" / "01_ОБЗОР"
LEGACY_PATTERNS = ["multilingual-e5-large", "Qdrant 1.15", "qdrant/qdrant:v1.15"]
LEGACY_MARKERS = ["legacy", "до Phase 8", "fallback", "не выбрано", "Legacy"]
