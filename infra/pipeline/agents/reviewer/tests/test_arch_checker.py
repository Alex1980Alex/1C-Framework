"""
Tests for REVIEWER ArchChecker.
"""

import pytest
from pathlib import Path

from agents.reviewer.arch_checker import (
    ComponentSpec,
    ArchCheckResult,
    ArchChecker,
    check_architecture,
    parse_design_spec,
)
from agents.reviewer.models import IssueSeverity, IssueCategory


# Sample design.md content for testing
SIMPLE_DESIGN = """
# Техническое проектирование

## Компонент: МодульОбработки
Общий модуль для обработки данных.

### Интерфейс:
- ПолучитьДанные() - получает данные
- ОбработатьДанные() - обрабатывает данные

## Компонент: МодульФормы
Модуль формы для отображения данных.
"""

TABLE_DESIGN = """
# Архитектура

| Компонент | Тип | Описание |
|-----------|-----|----------|
| ОсновнойМодуль | CommonModule | Основная логика |
| ДокументПриход | Documents | Документ прихода |
| СправочникТовары | Catalogs | Справочник товаров |
"""

DESIGN_WITH_INTERFACE = """
## Компонент: АПИМодуль

Экспортируемые функции:
```bsl
Функция ПолучитьКонтрагента(ИдКонтрагента) Экспорт
    // Получает контрагента по идентификатору
КонецФункции

Функция СоздатьДокумент(ДанныеДокумента) Экспорт
    // Создаёт новый документ
КонецФункции
```
"""

# Sample BSL code for testing
SERVER_MODULE_CODE = """
&НаСервере
Процедура ОбработатьДанные() Экспорт
    Запрос = Новый Запрос;
    Запрос.Текст = "ВЫБРАТЬ * ИЗ Справочник.Товары";
    Результат = Запрос.Выполнить();
КонецПроцедуры
"""

SERVER_WITH_CLIENT_CALLS = """
&НаСервере
Процедура ОбработатьДанные() Экспорт
    Предупреждение("Нельзя так делать!");
    ОткрытьФорму("Обработка.МояОбработка.Форма");
КонецПроцедуры
"""

COMMON_MODULE_NO_CONTEXT = """
Функция ПолучитьДанные() Экспорт
    Возврат "Данные";
КонецФункции
"""

COMMON_MODULE_WITH_CONTEXT = """
&НаСервереБезКонтекста
Функция ПолучитьДанные() Экспорт
    Возврат "Данные";
КонецФункции
"""

FORM_WITH_BUSINESS_LOGIC = """
&НаКлиенте
Процедура СохранитьДанные()
    Запрос = Новый Запрос;
    НачатьТранзакцию();
    Объект.Записать();
КонецПроцедуры
"""

FORM_WITHOUT_BUSINESS_LOGIC = """
&НаКлиенте
Процедура ОткрытьФорму()
    ОткрытьФорму("Справочник.Товары.Форма.ФормаЭлемента");
КонецПроцедуры
"""

MODULE_A_CODE = """
Функция ВызватьМодульБ() Экспорт
    Результат = МодульБ.ПолучитьДанные();
    Возврат Результат;
КонецФункции
"""

MODULE_B_CODE = """
Функция ПолучитьДанные() Экспорт
    Результат = МодульА.ВызватьМодульБ();  // Циклическая зависимость!
    Возврат Результат;
КонецФункции
"""

CODE_WITH_INTERFACE = """
Функция ПолучитьКонтрагента(ИдКонтрагента) Экспорт
    Возврат Справочники.Контрагенты.ПолучитьСсылку(ИдКонтрагента);
КонецФункции

// СоздатьДокумент отсутствует!
"""


class TestComponentSpec:
    """Tests for ComponentSpec dataclass."""

    def test_creation(self):
        """Test spec creation."""
        spec = ComponentSpec(
            name="МойМодуль",
            type="CommonModule",
            required=True
        )
        assert spec.name == "МойМодуль"
        assert spec.type == "CommonModule"
        assert spec.required is True

    def test_with_interface(self):
        """Test spec with interface."""
        spec = ComponentSpec(
            name="АПИ",
            type="CommonModule",
            interface=["ПолучитьДанные", "СохранитьДанные"]
        )
        assert spec.interface is not None
        assert len(spec.interface) == 2

    def test_with_dependencies(self):
        """Test spec with dependencies."""
        spec = ComponentSpec(
            name="Модуль",
            type="CommonModule",
            dependencies=["ОбщегоНазначения", "СтроковыеФункции"]
        )
        assert spec.dependencies is not None
        assert "ОбщегоНазначения" in spec.dependencies

    def test_to_dict(self):
        """Test serialization."""
        spec = ComponentSpec(
            name="Тест",
            type="Report",
            required=False,
            interface=["Сформировать"]
        )
        d = spec.to_dict()
        assert d["name"] == "Тест"
        assert d["type"] == "Report"
        assert d["required"] is False
        assert d["interface"] == ["Сформировать"]


class TestArchCheckResult:
    """Tests for ArchCheckResult dataclass."""

    def test_empty_result(self):
        """Test empty result."""
        result = ArchCheckResult()
        assert result.passed is True
        assert result.score == 100.0
        assert len(result.issues) == 0

    def test_with_issues(self):
        """Test result with issues."""
        from .models import ArchIssue

        result = ArchCheckResult()
        result.issues.append(ArchIssue(
            component="Модуль",
            issue_type="missing",
            description="Компонент не реализован"
        ))
        assert result.passed is False

    def test_with_missing_components(self):
        """Test result with missing components."""
        result = ArchCheckResult(
            missing_components=["Модуль1", "Модуль2"]
        )
        assert len(result.missing_components) == 2

    def test_with_circular_dependencies(self):
        """Test result with circular dependencies."""
        result = ArchCheckResult(
            circular_dependencies=[("A", "B"), ("C", "D")]
        )
        assert len(result.circular_dependencies) == 2

    def test_to_dict(self):
        """Test serialization."""
        result = ArchCheckResult(
            missing_components=["X"],
            extra_components=["Y", "Z"],
            score=80.0
        )
        d = result.to_dict()
        assert d["missing_components"] == 1
        assert d["extra_components"] == 2
        assert d["score"] == 80.0
        assert d["passed"] is True  # No issues added


class TestArchChecker:
    """Tests for ArchChecker class."""

    def test_parse_simple_design(self):
        """Test parsing simple design."""
        checker = ArchChecker()
        specs = checker.parse_design(SIMPLE_DESIGN)

        assert len(specs) >= 2
        names = [s.name for s in specs]
        assert "МодульОбработки" in names
        assert "МодульФормы" in names

    def test_parse_table_design(self):
        """Test parsing table-based design."""
        checker = ArchChecker()
        specs = checker.parse_design(TABLE_DESIGN)

        assert len(specs) >= 3
        names = [s.name for s in specs]
        assert "ОсновнойМодуль" in names
        assert "ДокументПриход" in names
        assert "СправочникТовары" in names

    def test_parse_design_with_interface(self):
        """Test parsing design with interface specification."""
        checker = ArchChecker()
        specs = checker.parse_design(DESIGN_WITH_INTERFACE)

        assert len(specs) >= 1
        api_spec = next((s for s in specs if s.name == "АПИМодуль"), None)
        assert api_spec is not None
        assert api_spec.interface is not None
        assert "ПолучитьКонтрагента" in api_spec.interface

    def test_check_all_implemented(self):
        """Test check when all components are implemented."""
        checker = ArchChecker()
        spec = [
            ComponentSpec(name="МодульА", type="CommonModule"),
            ComponentSpec(name="МодульБ", type="CommonModule"),
        ]
        files = [
            "src/CommonModules/МодульА/Ext/Module.bsl",
            "src/CommonModules/МодульБ/Ext/Module.bsl",
        ]
        result = checker.check(spec, files)

        assert len(result.missing_components) == 0
        assert result.score >= 100.0

    def test_check_missing_component(self):
        """Test check with missing component."""
        checker = ArchChecker()
        spec = [
            ComponentSpec(name="СуществующийМодуль", type="CommonModule"),
            ComponentSpec(name="ОтсутствующийМодуль", type="CommonModule"),
        ]
        files = [
            "src/CommonModules/СуществующийМодуль/Ext/Module.bsl",
        ]
        result = checker.check(spec, files)

        assert "ОтсутствующийМодуль" in result.missing_components
        assert result.score < 100.0
        assert any(
            issue.issue_type == "missing"
            for issue in result.issues
        )

    def test_check_interface_violations(self):
        """Test check for interface violations."""
        checker = ArchChecker()
        spec = [
            ComponentSpec(
                name="АПИМодуль",
                type="CommonModule",
                interface=["ПолучитьКонтрагента", "СоздатьДокумент"]
            ),
        ]
        files = ["src/CommonModules/АПИМодуль/Ext/Module.bsl"]
        code = {"src/CommonModules/АПИМодуль/Ext/Module.bsl": CODE_WITH_INTERFACE}

        result = checker.check(spec, files, code)

        # СоздатьДокумент should be missing
        assert any(
            "СоздатьДокумент" in v
            for v in result.interface_violations
        )

    def test_detect_circular_dependencies(self):
        """Test circular dependency detection."""
        checker = ArchChecker()
        spec = []
        files = [
            "src/CommonModules/МодульА/Ext/Module.bsl",
            "src/CommonModules/МодульБ/Ext/Module.bsl",
        ]
        code = {
            "src/CommonModules/МодульА/Ext/Module.bsl": MODULE_A_CODE,
            "src/CommonModules/МодульБ/Ext/Module.bsl": MODULE_B_CODE,
        }

        result = checker.check(spec, files, code)

        # Should detect circular dependency
        assert len(result.circular_dependencies) > 0
        # The pair should contain both modules
        for pair in result.circular_dependencies:
            assert "МодульА" in pair or "Module" in pair[0] or "Module" in pair[1]

    def test_check_server_module_with_client_calls(self):
        """Test detection of client calls in server module."""
        checker = ArchChecker()
        spec = []
        files = ["src/CommonModules/СерверныйМодуль/Ext/Module.bsl"]
        code = {
            "src/CommonModules/СерверныйМодуль/Ext/Module.bsl": SERVER_WITH_CLIENT_CALLS
        }

        result = checker.check(spec, files, code)

        # Should detect client call in server code
        server_issues = [
            i for i in result.issues
            if "клиентские методы" in i.description.lower() or "client" in i.description.lower()
        ]
        assert len(server_issues) > 0

    def test_check_common_module_without_context(self):
        """Test detection of missing context annotation."""
        checker = ArchChecker()
        spec = []
        files = ["src/CommonModules/МойМодуль/Ext/Module.bsl"]
        code = {
            "src/CommonModules/МойМодуль/Ext/Module.bsl": COMMON_MODULE_NO_CONTEXT
        }

        result = checker.check(spec, files, code)

        context_issues = [
            i for i in result.issues
            if "контекст" in i.description.lower()
        ]
        assert len(context_issues) > 0

    def test_check_common_module_with_context(self):
        """Test that module with context passes."""
        checker = ArchChecker()
        spec = []
        files = ["src/CommonModules/МойМодуль/Ext/Module.bsl"]
        code = {
            "src/CommonModules/МойМодуль/Ext/Module.bsl": COMMON_MODULE_WITH_CONTEXT
        }

        result = checker.check(spec, files, code)

        context_issues = [
            i for i in result.issues
            if "контекст" in i.description.lower()
        ]
        assert len(context_issues) == 0

    def test_check_form_with_business_logic(self):
        """Test detection of business logic in form module."""
        checker = ArchChecker()
        spec = []
        files = ["src/DataProcessors/Обработка/Forms/Форма/Ext/Form/Module.bsl"]
        code = {
            "src/DataProcessors/Обработка/Forms/Форма/Ext/Form/Module.bsl": FORM_WITH_BUSINESS_LOGIC
        }

        result = checker.check(spec, files, code)

        form_issues = [
            i for i in result.issues
            if "бизнес-логик" in i.description.lower()
        ]
        assert len(form_issues) > 0

    def test_check_form_without_business_logic(self):
        """Test that clean form passes."""
        checker = ArchChecker()
        spec = []
        files = ["src/DataProcessors/Обработка/Forms/Форма/Ext/Form/Module.bsl"]
        code = {
            "src/DataProcessors/Обработка/Forms/Форма/Ext/Form/Module.bsl": FORM_WITHOUT_BUSINESS_LOGIC
        }

        result = checker.check(spec, files, code)

        form_issues = [
            i for i in result.issues
            if "бизнес-логик" in i.description.lower()
        ]
        assert len(form_issues) == 0

    def test_to_review_issues(self):
        """Test conversion to review issues."""
        from .models import ArchIssue

        checker = ArchChecker()
        result = ArchCheckResult()
        result.issues.append(ArchIssue(
            component="Модуль",
            issue_type="missing",
            description="Компонент не реализован",
            severity=IssueSeverity.CRITICAL,
        ))
        result.issues.append(ArchIssue(
            component="Форма",
            issue_type="wrong_structure",
            description="Неправильная структура",
            severity=IssueSeverity.WARNING,
        ))

        review_issues = checker.to_review_issues(result)

        assert len(review_issues) == 2
        assert review_issues[0].category == IssueCategory.MAINTAINABILITY
        assert "CR-" in review_issues[0].id
        assert "WRN-" in review_issues[1].id

    def test_score_calculation(self):
        """Test score calculation."""
        checker = ArchChecker()

        # Perfect score
        result1 = ArchCheckResult()
        score1 = checker._calculate_score(result1)
        assert score1 == 100.0

        # Missing components reduce score
        result2 = ArchCheckResult(missing_components=["A", "B"])
        score2 = checker._calculate_score(result2)
        assert score2 == 60.0  # 100 - 2*20

        # Circular dependencies
        result3 = ArchCheckResult(circular_dependencies=[("A", "B")])
        score3 = checker._calculate_score(result3)
        assert score3 == 85.0  # 100 - 15


class TestDetectComponentType:
    """Tests for component type detection."""

    def test_detect_common_module(self):
        """Test CommonModule detection."""
        checker = ArchChecker()
        comp_type = checker._detect_component_type(
            "МодульОбработки",
            "Это общий модуль для обработки данных"
        )
        assert comp_type == "CommonModule"

    def test_detect_form(self):
        """Test Form detection."""
        checker = ArchChecker()
        comp_type = checker._detect_component_type(
            "ФормаДокумента",
            "Это форма для отображения документа"
        )
        assert comp_type == "Form"

    def test_detect_dataprocessor(self):
        """Test DataProcessor detection."""
        checker = ArchChecker()
        comp_type = checker._detect_component_type(
            "МояОбработка",
            "DataProcessors context"
        )
        assert comp_type == "DataProcessors"


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_check_architecture(self):
        """Test check_architecture function."""
        result = check_architecture(
            SIMPLE_DESIGN,
            ["src/CommonModules/МодульОбработки/Ext/Module.bsl",
             "src/CommonModules/МодульФормы/Ext/Module.bsl"]
        )
        assert isinstance(result, ArchCheckResult)
        assert result.score >= 80.0

    def test_parse_design_spec(self):
        """Test parse_design_spec function."""
        specs = parse_design_spec(TABLE_DESIGN)
        assert isinstance(specs, list)
        assert len(specs) >= 3
        assert all(isinstance(s, ComponentSpec) for s in specs)


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_design(self):
        """Test parsing empty design."""
        checker = ArchChecker()
        specs = checker.parse_design("")
        assert specs == []

    def test_design_without_components(self):
        """Test parsing design without component definitions."""
        checker = ArchChecker()
        specs = checker.parse_design("# Просто заголовок\nНекоторый текст")
        assert specs == []

    def test_empty_files_list(self):
        """Test check with empty files list."""
        checker = ArchChecker()
        spec = [ComponentSpec(name="Модуль", type="CommonModule")]
        result = checker.check(spec, [])
        assert len(result.missing_components) == 1

    def test_optional_component(self):
        """Test optional component handling."""
        checker = ArchChecker()
        spec = [
            ComponentSpec(name="Обязательный", type="CommonModule", required=True),
            ComponentSpec(name="Опциональный", type="CommonModule", required=False),
        ]
        files = ["src/CommonModules/Обязательный/Ext/Module.bsl"]
        result = checker.check(spec, files)

        # Optional component should not be in missing
        assert "Опциональный" not in result.missing_components
        assert "Обязательный" not in result.missing_components

    def test_partial_name_matching(self):
        """Test partial name matching for components."""
        checker = ArchChecker()
        spec = [ComponentSpec(name="МойМодуль", type="CommonModule")]
        # File has prefix
        files = ["src/CommonModules/гкс_МойМодуль/Ext/Module.bsl"]
        result = checker.check(spec, files)

        # Should match despite prefix
        assert "МойМодуль" not in result.missing_components

    def test_unicode_in_design(self):
        """Test handling of Unicode in design."""
        design = """
        ## Компонент: СправочникКонтрагенты
        Справочник для хранения контрагентов.

        ## Компонент: ДокументРеализация
        Документ реализации товаров.
        """
        checker = ArchChecker()
        specs = checker.parse_design(design)

        assert len(specs) >= 2
        names = [s.name for s in specs]
        assert "СправочникКонтрагенты" in names
        assert "ДокументРеализация" in names

    def test_min_score_is_zero(self):
        """Test that score doesn't go below zero."""
        checker = ArchChecker()
        result = ArchCheckResult(
            missing_components=["A", "B", "C", "D", "E", "F"]  # 6 * 20 = 120 penalty
        )
        score = checker._calculate_score(result)
        assert score == 0.0

