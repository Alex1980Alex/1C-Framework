"""Docs invariants — chapter 01_ОБЗОР vs Phase 8 production stack (§3.5.2)."""

from pathlib import Path

import pytest

DOCS_ROOT = Path(__file__).resolve().parent.parent / "docs" / "framework documentation"
CHAPTER_DIR = DOCS_ROOT / "01_ОБЗОР"
LEGACY_PATTERNS = ["multilingual-e5-large", "Qdrant 1.15", "qdrant/qdrant:v1.15"]
BROAD_LEGACY_PATTERNS = LEGACY_PATTERNS + ["nomic-embed-text", "all-MiniLM-L6-v2", "bsl_code_v2", "bsl_code_v3"]
LEGACY_MARKERS = ["legacy", "до Phase 8", "до Phase 9", "не выбрано", "Legacy", "Deprecated", "deprecated", "Dropped", "dropped", "удалена", "superseded", "boundary detector", "(НЕ retrieval)", "Phase 8 note", "Phase 8 default", "Migration note", "Phase 9.1"]
FILE_LEVEL_BANNERS = ["Migration note", "Legacy pipeline note", "Phase 8 note", "Phase 8 default", "Phase 8 + 9.1", "Phase 8 production reference", "DROPPED"]
ALLOWLIST_DIRS = {"31_QWEN3_RETRIEVAL_PRODUCTION"}


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


def _all_doc_files() -> list[Path]:
    if not DOCS_ROOT.exists():
        pytest.skip(f"Docs root missing: {DOCS_ROOT}")
    out: list[Path] = []
    for path in DOCS_ROOT.rglob("*.md"):
        rel = path.relative_to(DOCS_ROOT).parts
        if rel and rel[0] in ALLOWLIST_DIRS:
            continue
        out.append(path)
    return sorted(out)


@pytest.mark.unit
class TestAllChaptersNoStaleProductionStack:
    def test_broad_legacy_mentions_are_marked(self):
        offenders: list[str] = []
        for path in _all_doc_files():
            text = path.read_text(encoding="utf-8")
            head = "\n".join(text.splitlines()[:30])
            file_exempt = any(b in head for b in FILE_LEVEL_BANNERS)
            if file_exempt:
                continue
            for line_no, line in enumerate(text.splitlines(), start=1):
                for pattern in BROAD_LEGACY_PATTERNS:
                    if pattern in line and not any(m in line for m in LEGACY_MARKERS):
                        rel = path.relative_to(DOCS_ROOT)
                        offenders.append(f"{rel}:{line_no} '{pattern}'")
        assert not offenders, "Legacy без маркера:\n" + "\n".join(offenders[:50])