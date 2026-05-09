"""Docs invariants — chapter 01_ОБЗОР vs Phase 8 production stack (§3.5.2)."""

from pathlib import Path

import pytest

CHAPTER_DIR = Path(__file__).resolve().parent.parent / "docs" / "framework documentation" / "01_ОБЗОР"
LEGACY_PATTERNS = ["multilingual-e5-large", "Qdrant 1.15", "qdrant/qdrant:v1.15"]
LEGACY_MARKERS = ["legacy", "до Phase 8", "fallback", "не выбрано", "Legacy"]


def _all_chapter_files() -> list[Path]:
    if not CHAPTER_DIR.exists():
        pytest.skip(f"Chapter dir missing: {CHAPTER_DIR}")
    return sorted(CHAPTER_DIR.glob("*.md"))


@pytest.mark.unit
class TestChapter01NoStaleProductionStack:
    def test_legacy_mentions_are_marked(self):
        offenders: list[str] = []
        for path in _all_chapter_files():
            text = path.read_text(encoding="utf-8")
            for line_no, line in enumerate(text.splitlines(), start=1):
                for pattern in LEGACY_PATTERNS:
                    if pattern in line and not any(m in line for m in LEGACY_MARKERS):
                        offenders.append(f"{path.name}:{line_no} '{pattern}': {line.strip()[:100]}")
        assert not offenders, "Legacy mentions без маркера:\n" + "\n".join(offenders)

    def test_qwen3_present_in_each_overview_file(self):
        missing: list[str] = []
        for path in _all_chapter_files():
            text = path.read_text(encoding="utf-8")
            if "Qwen3" not in text and "Qwen/Qwen3" not in text:
                missing.append(path.name)
        assert not missing, f"Qwen3 не упомянут в: {missing}"
