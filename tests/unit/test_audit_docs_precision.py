"""Regression tests for audit_docs_skills.py precision fixes.

Covers the 4 root-cause bugs found in the 2026-07-19 audit-coverage analysis:
  1. endpoint router-prefix resolution (APIRouter(prefix=...) inside module)
  2. acronym-aware strategy name mangling
  3. token-based strategy doc matching + whole-tree fallback
  4. public-API (__all__) filtering of internal subsystem classes
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "audit_docs_skills.py"
_spec = importlib.util.spec_from_file_location("audit_docs_skills", _SCRIPT)
ads = importlib.util.module_from_spec(_spec)
sys.modules["audit_docs_skills"] = ads
_spec.loader.exec_module(ads)


# ── Fix 1: router prefix ────────────────────────────────────────────────
def test_router_prefix_from_apirouter_constructor():
    text = 'router = APIRouter(prefix="/v1", tags=["openai-compat"])\n@router.post("/chat/completions")'
    assert ads._extract_router_prefix(text, "openai_compat") == "/v1"


def test_router_prefix_root_mount_when_no_prefix():
    # APIRouter present but no prefix anywhere, stem absent from app.py -> root mount
    text = 'router = APIRouter(tags=["websocket"])\n@router.websocket("/ws/search")'
    assert ads._extract_router_prefix(text, "zz_nonexistent_stem") == ""


def test_router_prefix_stem_fallback_without_apirouter():
    assert (
        ads._extract_router_prefix("no router here", "zz_nonexistent_stem")
        == "/zz_nonexistent_stem"
    )


# ── Fix 2: acronym-aware strategy name ──────────────────────────────────
@pytest.mark.parametrize(
    "cls_name,expected",
    [
        ("GraphRAGAutoStrategy", "graph_rag_auto"),
        ("GraphRAGGlobalStrategy", "graph_rag_global"),
        ("GraphRAGLocalStrategy", "graph_rag_local"),
        ("LightRAGStrategy", "light_rag"),
        ("WebSearchStrategy", "web"),
        ("HybridSearchStrategy", "hybrid"),
    ],
)
def test_class_to_strategy_name_acronym_aware(cls_name, expected):
    assert ads._class_to_strategy_name(cls_name) == expected
    # regression guard: the old bug produced single-letter acronym splits
    assert "_r_a_g_" not in ads._class_to_strategy_name(cls_name)


# ── Fix 3: strategy token matching ──────────────────────────────────────
def test_strategy_documented_by_tokens():
    feat = ads.Feature(name="graph_rag_auto", category="strategy", source_file="x")
    doc = "the graphrag family supports auto, local and global modes".lower()
    assert ads._feature_documented(feat, doc) is True


def test_strategy_not_documented_when_token_missing():
    feat = ads.Feature(name="graph_rag_global", category="strategy", source_file="x")
    doc = "only hybrid and bm25 are described here".lower()
    assert ads._feature_documented(feat, doc) is False


# ── Fix 4: __all__ public-API filter ────────────────────────────────────
def test_package_exports_parses_all(tmp_path):
    init = tmp_path / "__init__.py"
    init.write_text('__all__ = [\n    "PublicOne",\n    "PublicTwo",\n]\n', encoding="utf-8")
    assert ads._package_exports(init) == {"PublicOne", "PublicTwo"}


def test_package_exports_none_without_all(tmp_path):
    init = tmp_path / "__init__.py"
    init.write_text("x = 1\n", encoding="utf-8")
    assert ads._package_exports(init) is None


def test_package_exports_missing_file(tmp_path):
    assert ads._package_exports(tmp_path / "nope.py") is None


# ── Whole-tree caches ───────────────────────────────────────────────────
def test_all_docs_text_cached():
    ads._ALL_DOCS_CACHE = None
    first = ads._all_docs_text()
    assert isinstance(first, str)
    assert first is ads._all_docs_text()  # cached, same object


def test_all_skills_text_cached():
    ads._ALL_SKILLS_CACHE = None
    first = ads._all_skills_text()
    assert isinstance(first, str)
    assert first is ads._all_skills_text()


# ── Fix 4 guard: __all__ filter is actually applied by the extractors ────
def test_memory_extractor_respects_all_exports():
    """Every extracted memory class from a package that declares __all__ must be
    exported there. Catches an inverted/removed guard (would surface internals)."""
    memory_dir = ads.PROJECT_ROOT / "src" / "memory"
    for feat in ads.extract_memory_subsystems():
        sub = Path(feat.source_file).parts[2]  # src/memory/<sub>/<file>.py
        exports = ads._package_exports(memory_dir / sub / "__init__.py")
        if exports is not None:
            assert feat.name in exports, f"{feat.name} extracted but not in {sub}/__all__"


def test_bsl_extractor_respects_all_exports():
    for feat in ads.extract_bsl_tools():
        sub = Path(feat.source_file).parts[2]  # src/bsl/<sub>/<file>.py
        exports = ads._package_exports(ads.PROJECT_ROOT / "src" / "bsl" / sub / "__init__.py")
        if exports is not None:
            assert feat.name in exports, f"{feat.name} extracted but not in {sub}/__all__"


# ── End-to-end: the fixed audit eliminates the false-positive categories ─
def test_audit_no_false_positive_categories():
    """endpoint/hook/strategy doc gaps must be zero after the fixes.

    Dual semantics: if this fails after adding a genuinely-undocumented endpoint
    or hook, that is a real coverage signal (document the feature), not a fix
    regression. It only asserts the naming/prefix/allowlist BUGS stay dead.
    """
    ads._ALL_DOCS_CACHE = None
    ads._ALL_SKILLS_CACHE = None
    report = ads.run_audit()
    fp_categories = {"endpoint", "strategy", "hook"}
    offenders = [g.feature_name for g in report.doc_gaps if g.category in fp_categories]
    assert offenders == [], f"unexpected doc gaps in fixed categories: {offenders}"


# ── Skill-gap scoping (Diátaxis): reference categories are doc-tracked only ──
_REFERENCE_CATEGORIES = {"config_var", "endpoint", "hook", "memory_subsystem", "bsl_tool"}


def test_reference_categories_never_skill_gapped():
    """Config vars/endpoints/hooks/internal classes are reference material →
    tracked on docs, never counted as skill gaps (else --update re-pollutes skills)."""
    ads._ALL_DOCS_CACHE = None
    ads._ALL_SKILLS_CACHE = None
    report = ads.run_audit()
    leaked = [g.feature_name for g in report.skill_gaps if g.category in _REFERENCE_CATEGORIES]
    assert leaked == [], f"reference categories must not be skill-gapped: {leaked}"


def test_reference_categories_have_null_skill_coverage():
    report = ads.run_audit()
    for cat, stats in report.summary["by_category"].items():
        if cat in ads.SKILL_COVERAGE_CATEGORIES:
            assert stats["coverage_skills"] is not None, f"{cat} should report skill coverage"
        else:
            assert stats["coverage_skills"] is None, f"{cat} skill coverage should be n/a"


def test_skill_coverage_categories_are_conceptual():
    # guardrail: the tracked set stays task/conceptual, not bulk-reference
    assert ads.SKILL_COVERAGE_CATEGORIES == {
        "agent",
        "strategy",
        "mcp_tool",
        "cli_command",
        "wiki_component",
    }
