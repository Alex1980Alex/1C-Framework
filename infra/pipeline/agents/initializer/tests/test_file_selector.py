"""Tests for FileSelector."""

import pytest
from datetime import datetime
from pathlib import Path

from ..file_selector import (
    FileSelector,
    RelevanceKeyword,
    select_relevant_files,
    rank_files_by_relevance,
    get_high_relevance_files,
    get_files_by_type,
)
from models import (
    ObjectType,
    FileType,
    FileInfo,
    ModuleInfo,
    ProjectStructure,
    ProjectType,
    RelevantFile,
    InitializerConfig,
)


def create_test_module(
    name: str,
    object_type: ObjectType,
    exports_count: int = 0,
) -> ModuleInfo:
    """Helper to create test module."""
    return ModuleInfo(
        name=name,
        object_type=object_type,
        path=Path(f"{object_type.value}/{name}"),
        files=[
            FileInfo(
                path=Path(f"{object_type.value}/{name}/Ext/Module.bsl"),
                name="Module.bsl",
                file_type=FileType.BSL,
                line_count=100,
            )
        ],
        exports_count=exports_count,
    )


def create_test_structure(modules: list[ModuleInfo]) -> ProjectStructure:
    """Helper to create test structure."""
    return ProjectStructure(
        root_path=Path("/test/project"),
        project_type=ProjectType.CONFIGURATION,
        name="TestProject",
        modules=modules,
        scanned_at=datetime.now(),
    )


class TestFileSelector:
    """Tests for FileSelector class."""

    def test_init_default_config(self):
        """Test initialization with default config."""
        selector = FileSelector()
        assert selector.config is not None
        assert selector.config.max_files == 10000

    def test_init_custom_config(self):
        """Test initialization with custom config."""
        config = InitializerConfig(max_relevant_files=10)
        selector = FileSelector(config)
        assert selector.config.max_relevant_files == 10

    def test_select_empty_structure(self):
        """Test selection on empty structure."""
        selector = FileSelector()
        structure = create_test_structure([])

        result = selector.select(structure, "добавить документ")

        assert result == []

    def test_select_matches_document_keyword(self):
        """Test that 'документ' keyword matches document modules."""
        selector = FileSelector()
        modules = [
            create_test_module("ПоступлениеТоваров", ObjectType.DOCUMENT),
            create_test_module("Товары", ObjectType.CATALOG),
        ]
        structure = create_test_structure(modules)

        result = selector.select(structure, "создать документ")

        assert len(result) == 1
        assert result[0].module_name == "ПоступлениеТоваров"

    def test_select_matches_catalog_keyword(self):
        """Test that 'справочник' keyword matches catalog modules."""
        selector = FileSelector()
        modules = [
            create_test_module("ПоступлениеТоваров", ObjectType.DOCUMENT),
            create_test_module("Товары", ObjectType.CATALOG),
        ]
        structure = create_test_structure(modules)

        result = selector.select(structure, "изменить справочник")

        assert len(result) == 1
        assert result[0].module_name == "Товары"

    def test_select_matches_register_keyword(self):
        """Test that 'регистр' keyword matches register modules."""
        selector = FileSelector()
        modules = [
            create_test_module("ОстаткиТоваров", ObjectType.ACCUMULATION_REGISTER),
            create_test_module("СведенияОТоварах", ObjectType.INFORMATION_REGISTER),
            create_test_module("Товары", ObjectType.CATALOG),
        ]
        structure = create_test_structure(modules)

        result = selector.select(structure, "добавить регистр")

        assert len(result) == 2
        module_names = [r.module_name for r in result]
        assert "ОстаткиТоваров" in module_names
        assert "СведенияОТоварах" in module_names

    def test_select_matches_module_name(self):
        """Test that keywords match module names."""
        selector = FileSelector()
        modules = [
            create_test_module("РаботаСТоварами", ObjectType.COMMON_MODULE),
            create_test_module("ОбщиеФункции", ObjectType.COMMON_MODULE),
        ]
        structure = create_test_structure(modules)

        result = selector.select(structure, "исправить товар")

        # Should match РаботаСТоварами due to "товар" in name
        assert len(result) >= 1
        assert any(r.module_name == "РаботаСТоварами" for r in result)

    def test_select_respects_limit(self):
        """Test that selection respects limit parameter."""
        selector = FileSelector()
        modules = [
            create_test_module(f"Документ{i}", ObjectType.DOCUMENT)
            for i in range(10)
        ]
        structure = create_test_structure(modules)

        result = selector.select(structure, "документ", limit=5)

        assert len(result) <= 5

    def test_select_sorts_by_score(self):
        """Test that results are sorted by relevance score."""
        selector = FileSelector()
        modules = [
            create_test_module("Товары", ObjectType.CATALOG, exports_count=15),
            create_test_module("ПриходТоваров", ObjectType.DOCUMENT),
        ]
        structure = create_test_structure(modules)

        result = selector.select(structure, "товар справочник")

        # Catalog should score higher due to keyword match
        assert len(result) >= 1
        if len(result) > 1:
            assert result[0].relevance_score >= result[1].relevance_score


class TestKeywordExtraction:
    """Tests for keyword extraction."""

    def test_extract_keywords_basic(self):
        """Test basic keyword extraction."""
        selector = FileSelector()

        keywords = selector._extract_keywords("Добавить новый документ")

        assert "добавить" in keywords
        assert "новый" in keywords
        assert "документ" in keywords

    def test_extract_keywords_removes_stopwords(self):
        """Test that stopwords are removed."""
        selector = FileSelector()

        keywords = selector._extract_keywords("Добавить в справочник и изменить")

        assert "в" not in keywords
        assert "и" not in keywords
        assert "добавить" in keywords
        assert "справочник" in keywords

    def test_extract_keywords_removes_short_words(self):
        """Test that short words are removed."""
        selector = FileSelector()

        keywords = selector._extract_keywords("Я хочу добавить документ")

        assert "я" not in keywords
        assert "добавить" in keywords

    def test_extract_keywords_handles_punctuation(self):
        """Test handling of punctuation."""
        selector = FileSelector()

        keywords = selector._extract_keywords("Добавить документ, справочник!")

        assert "добавить" in keywords
        assert "документ" in keywords
        assert "справочник" in keywords


class TestTargetTypeDetection:
    """Tests for target type detection."""

    def test_determine_target_types_document(self):
        """Test document type detection."""
        selector = FileSelector()

        types = selector._determine_target_types(["документ"])

        assert ObjectType.DOCUMENT in types

    def test_determine_target_types_catalog(self):
        """Test catalog type detection."""
        selector = FileSelector()

        types = selector._determine_target_types(["справочник"])

        assert ObjectType.CATALOG in types

    def test_determine_target_types_register(self):
        """Test register type detection."""
        selector = FileSelector()

        types = selector._determine_target_types(["регистр"])

        assert ObjectType.ACCUMULATION_REGISTER in types
        assert ObjectType.INFORMATION_REGISTER in types

    def test_determine_target_types_multiple(self):
        """Test multiple type detection."""
        selector = FileSelector()

        types = selector._determine_target_types(["документ", "справочник"])

        assert ObjectType.DOCUMENT in types
        assert ObjectType.CATALOG in types

    def test_determine_target_types_empty(self):
        """Test empty result for unknown keywords."""
        selector = FileSelector()

        types = selector._determine_target_types(["неизвестно"])

        assert len(types) == 0


class TestRelevanceReason:
    """Tests for relevance reason generation."""

    def test_generate_reason_type_match(self):
        """Test reason for type match."""
        selector = FileSelector()
        module = create_test_module("Тест", ObjectType.DOCUMENT)
        target_types = {ObjectType.DOCUMENT}

        reason = selector._generate_reason(module, [], target_types)

        assert "тип объекта" in reason
        assert "Документ" in reason

    def test_generate_reason_name_match(self):
        """Test reason for name match."""
        selector = FileSelector()
        module = create_test_module("ТестТоваров", ObjectType.COMMON_MODULE)

        reason = selector._generate_reason(module, ["товар"], set())

        assert "совпадение в имени" in reason

    def test_generate_reason_exports(self):
        """Test reason includes export count."""
        selector = FileSelector()
        module = create_test_module("Тест", ObjectType.COMMON_MODULE, exports_count=10)

        reason = selector._generate_reason(module, [], set())

        assert "экспортов" in reason
        assert "10" in reason


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_select_relevant_files(self):
        """Test select_relevant_files function."""
        modules = [
            create_test_module("Товары", ObjectType.CATALOG),
        ]
        structure = create_test_structure(modules)

        result = select_relevant_files(structure, "справочник")

        assert len(result) == 1
        assert result[0].module_name == "Товары"

    def test_rank_files_by_relevance(self):
        """Test rank_files_by_relevance function."""
        file_info = FileInfo(
            path=Path("test.bsl"),
            name="test.bsl",
            file_type=FileType.BSL,
        )

        files = [
            RelevantFile(file_info=file_info, relevance_score=0.5, relevance_reason="test1"),
            RelevantFile(file_info=file_info, relevance_score=0.9, relevance_reason="test2"),
            RelevantFile(file_info=file_info, relevance_score=0.3, relevance_reason="test3"),
        ]

        result = rank_files_by_relevance(files)

        assert result[0].relevance_score == 0.9
        assert result[1].relevance_score == 0.5
        assert result[2].relevance_score == 0.3

    def test_rank_files_with_min_score(self):
        """Test rank_files_by_relevance with minimum score."""
        file_info = FileInfo(
            path=Path("test.bsl"),
            name="test.bsl",
            file_type=FileType.BSL,
        )

        files = [
            RelevantFile(file_info=file_info, relevance_score=0.5, relevance_reason="test1"),
            RelevantFile(file_info=file_info, relevance_score=0.9, relevance_reason="test2"),
            RelevantFile(file_info=file_info, relevance_score=0.3, relevance_reason="test3"),
        ]

        result = rank_files_by_relevance(files, min_score=0.4)

        assert len(result) == 2
        assert all(f.relevance_score >= 0.4 for f in result)

    def test_get_high_relevance_files(self):
        """Test get_high_relevance_files function."""
        modules = [
            create_test_module("Товары", ObjectType.CATALOG),
            create_test_module("Услуги", ObjectType.CATALOG),
        ]
        structure = create_test_structure(modules)

        # This should return files meeting the threshold
        result = get_high_relevance_files(structure, "справочник товар", threshold=0.5)

        # All returned files should have score >= 0.5
        assert all(f.relevance_score >= 0.5 for f in result)

    def test_get_files_by_type(self):
        """Test get_files_by_type function."""
        modules = [
            create_test_module("Документ1", ObjectType.DOCUMENT),
            create_test_module("Документ2", ObjectType.DOCUMENT),
            create_test_module("Справочник1", ObjectType.CATALOG),
        ]
        structure = create_test_structure(modules)

        result = get_files_by_type(structure, [ObjectType.DOCUMENT])

        assert len(result) == 2
        assert all(f.is_bsl for f in result)

    def test_get_files_by_multiple_types(self):
        """Test get_files_by_type with multiple types."""
        modules = [
            create_test_module("Документ1", ObjectType.DOCUMENT),
            create_test_module("Справочник1", ObjectType.CATALOG),
            create_test_module("Регистр1", ObjectType.ACCUMULATION_REGISTER),
        ]
        structure = create_test_structure(modules)

        result = get_files_by_type(structure, [ObjectType.DOCUMENT, ObjectType.CATALOG])

        assert len(result) == 2


class TestRelevanceKeyword:
    """Tests for RelevanceKeyword dataclass."""

    def test_relevance_keyword_defaults(self):
        """Test default values."""
        keyword = RelevanceKeyword("test")

        assert keyword.keyword == "test"
        assert keyword.weight == 1.0
        assert keyword.object_types == []

    def test_relevance_keyword_with_values(self):
        """Test with custom values."""
        keyword = RelevanceKeyword(
            keyword="ошибка",
            weight=1.5,
            object_types=[ObjectType.DOCUMENT],
        )

        assert keyword.keyword == "ошибка"
        assert keyword.weight == 1.5
        assert ObjectType.DOCUMENT in keyword.object_types
