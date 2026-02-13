"""Tests for Parse Templates and document type detection (Phase 10.5).

Tests template classes, registry, and auto-detection logic.
"""

from src.pdf_framework.loaders.templates.base import (
    GenericTemplate,
    ParseTemplate,
    ResearchPaperTemplate,
    UserManualTemplate,
    TEMPLATE_REGISTRY,
    detect_document_type,
    get_template,
)


class TestGenericTemplate:
    """Test GenericTemplate."""

    def test_name(self):
        t = GenericTemplate()
        assert t.get_name() == "generic"

    def test_skip_elements(self):
        t = GenericTemplate()
        assert t.should_skip("header") is True
        assert t.should_skip("footer") is True
        assert t.should_skip("page_number") is True
        assert t.should_skip("paragraph") is False
        assert t.should_skip("table") is False

    def test_default_priorities(self):
        t = GenericTemplate()
        assert t.get_priority("title") == 10
        assert t.get_priority("table") == 8
        assert t.get_priority("paragraph") == 5
        assert t.get_priority("unknown_type") == 0

    def test_chunk_size_defaults(self):
        t = GenericTemplate()
        assert t.get_chunk_size("paragraph", 1000) == 1000
        assert t.get_chunk_size("table", 500) == 500


class TestResearchPaperTemplate:
    """Test ResearchPaperTemplate."""

    def test_name(self):
        t = ResearchPaperTemplate()
        assert t.get_name() == "research_paper"

    def test_skip_elements(self):
        t = ResearchPaperTemplate()
        assert t.should_skip("references") is True
        assert t.should_skip("acknowledgments") is True
        assert t.should_skip("bibliography") is True
        assert t.should_skip("header") is True
        assert t.should_skip("paragraph") is False

    def test_priorities(self):
        t = ResearchPaperTemplate()
        assert t.get_priority("title") == 10
        assert t.get_priority("abstract") == 10
        assert t.get_priority("section_header") == 9
        assert t.get_priority("table") == 8
        assert t.get_priority("equation") == 8

    def test_chunk_size_overrides(self):
        t = ResearchPaperTemplate()
        assert t.get_chunk_size("paragraph", 1000) == 1200
        assert t.get_chunk_size("section_header", 1000) == 1500
        # No override for table → uses default
        assert t.get_chunk_size("table", 1000) == 1000


class TestUserManualTemplate:
    """Test UserManualTemplate."""

    def test_name(self):
        t = UserManualTemplate()
        assert t.get_name() == "user_manual"

    def test_skip_elements(self):
        t = UserManualTemplate()
        assert t.should_skip("header") is True
        assert t.should_skip("footer") is True
        assert t.should_skip("paragraph") is False
        assert t.should_skip("list") is False

    def test_priorities(self):
        t = UserManualTemplate()
        assert t.get_priority("instruction") == 10
        assert t.get_priority("warning") == 9
        assert t.get_priority("code_block") == 9
        assert t.get_priority("list") == 8
        assert t.get_priority("image") == 8

    def test_chunk_size_overrides(self):
        t = UserManualTemplate()
        assert t.get_chunk_size("list", 1000) == 2000
        assert t.get_chunk_size("code_block", 1000) == 1500


class TestTemplateRegistry:
    """Test template registry and get_template."""

    def test_registry_has_all_templates(self):
        assert "generic" in TEMPLATE_REGISTRY
        assert "research_paper" in TEMPLATE_REGISTRY
        assert "user_manual" in TEMPLATE_REGISTRY

    def test_get_template_generic(self):
        t = get_template("generic")
        assert isinstance(t, GenericTemplate)
        assert t.get_name() == "generic"

    def test_get_template_research(self):
        t = get_template("research_paper")
        assert isinstance(t, ResearchPaperTemplate)

    def test_get_template_manual(self):
        t = get_template("user_manual")
        assert isinstance(t, UserManualTemplate)

    def test_get_template_unknown_returns_generic(self):
        t = get_template("nonexistent_template")
        assert isinstance(t, GenericTemplate)

    def test_all_templates_are_parse_template(self):
        for name in TEMPLATE_REGISTRY:
            t = get_template(name)
            assert isinstance(t, ParseTemplate)


class TestDocumentTypeDetection:
    """Test detect_document_type function."""

    def test_empty_elements_returns_generic(self):
        assert detect_document_type([]) == "generic"

    def test_research_paper_with_abstract(self):
        elements = [
            {"type": "title", "content": "Deep Learning for NLP"},
            {"type": "paragraph", "content": "Abstract: We present a novel approach..."},
            {"type": "paragraph", "content": "Introduction"},
            {"type": "table", "content": "Results table"},
            {"type": "paragraph", "content": "Methods section"},
        ]
        assert detect_document_type(elements) == "research_paper"

    def test_research_paper_with_references_and_tables(self):
        elements = [
            {"type": "title", "content": "Analysis"},
            {"type": "paragraph", "content": "Some text"},
            {"type": "paragraph", "content": "References listed here"},
            {"type": "table", "content": "Table 1"},
            {"type": "table", "content": "Table 2"},
            {"type": "paragraph", "content": "More text"},
            {"type": "paragraph", "content": "Conclusion"},
        ]
        # Has references + high table ratio
        result = detect_document_type(elements)
        assert result == "research_paper"

    def test_user_manual_with_high_list_ratio(self):
        elements = [
            {"type": "title", "content": "User Guide"},
            {"type": "list", "content": "1. First step"},
            {"type": "list", "content": "2. Second step"},
            {"type": "list", "content": "3. Third step"},
            {"type": "paragraph", "content": "Additional notes"},
            {"type": "paragraph", "content": "More info"},
        ]
        assert detect_document_type(elements) == "user_manual"

    def test_user_manual_with_instruction_keywords(self):
        elements = [
            {"type": "title", "content": "Installation Guide"},
            {"type": "paragraph", "content": "Follow the instructions below."},
            {"type": "paragraph", "content": "Step 1: Install dependencies"},
            {"type": "paragraph", "content": "Note: This requires admin access"},
        ]
        assert detect_document_type(elements) == "user_manual"

    def test_generic_document(self):
        elements = [
            {"type": "title", "content": "Company Report"},
            {"type": "paragraph", "content": "We are pleased to report..."},
            {"type": "paragraph", "content": "Financial overview for Q4."},
            {"type": "paragraph", "content": "Outlook for next year."},
        ]
        assert detect_document_type(elements) == "generic"

    def test_manual_with_warning_keyword(self):
        elements = [
            {"type": "title", "content": "Safety Manual"},
            {"type": "paragraph", "content": "Warning: Do not operate without training."},
            {"type": "paragraph", "content": "General safety rules."},
            {"type": "paragraph", "content": "Additional guidelines."},
        ]
        assert detect_document_type(elements) == "user_manual"
