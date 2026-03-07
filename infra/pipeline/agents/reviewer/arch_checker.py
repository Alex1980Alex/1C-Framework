"""
Architecture Checker for REVIEWER Agent.

Validates code architecture against design.md specification.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set, Tuple
import re
from pathlib import Path

from agents.reviewer.models import (
    ArchIssue,
    ReviewIssue,
    IssueSeverity,
    IssueCategory,
)


@dataclass
class ComponentSpec:
    """Expected component from design.md."""
    name: str
    type: str  # module, procedure, function, form, register, etc.
    required: bool = True
    interface: Optional[List[str]] = None  # Expected exports
    dependencies: Optional[List[str]] = None  # Expected dependencies

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "type": self.type,
            "required": self.required,
            "interface": self.interface,
            "dependencies": self.dependencies,
        }


@dataclass
class ArchCheckResult:
    """Result of architecture check."""
    issues: List[ArchIssue] = field(default_factory=list)
    missing_components: List[str] = field(default_factory=list)
    extra_components: List[str] = field(default_factory=list)
    interface_violations: List[str] = field(default_factory=list)
    circular_dependencies: List[Tuple[str, str]] = field(default_factory=list)
    score: float = 100.0  # 0-100

    @property
    def passed(self) -> bool:
        """Check if architecture is valid."""
        return len(self.issues) == 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "issues_count": len(self.issues),
            "missing_components": len(self.missing_components),
            "extra_components": len(self.extra_components),
            "interface_violations": len(self.interface_violations),
            "circular_dependencies": len(self.circular_dependencies),
            "score": round(self.score, 1),
            "passed": self.passed,
        }


class ArchChecker:
    """
    Validates implementation against architecture specification.

    Checks:
    - All required components are implemented
    - Interfaces match specification
    - No circular dependencies
    - Module structure is correct
    - BSL-specific patterns are followed

    Usage:
        checker = ArchChecker()
        spec = checker.parse_design("design.md content")
        result = checker.check(spec, implemented_files)
    """

    # BSL module types
    MODULE_TYPES = {
        "CommonModule": "Общий модуль",
        "ObjectModule": "Модуль объекта",
        "ManagerModule": "Модуль менеджера",
        "FormModule": "Модуль формы",
        "CommandModule": "Модуль команды",
        "RecordSetModule": "Модуль набора записей",
        "ValueManagerModule": "Модуль менеджера значения",
    }

    # 1C object types
    OBJECT_TYPES = {
        "Catalogs": "Справочники",
        "Documents": "Документы",
        "DataProcessors": "Обработки",
        "Reports": "Отчёты",
        "InformationRegisters": "Регистры сведений",
        "AccumulationRegisters": "Регистры накопления",
        "CommonModules": "Общие модули",
        "Constants": "Константы",
        "Enums": "Перечисления",
    }

    def __init__(self) -> None:
        """Initialize checker."""
        self._issue_counter = {
            IssueSeverity.CRITICAL: 0,
            IssueSeverity.WARNING: 0,
            IssueSeverity.RECOMMENDATION: 0,
        }

    def parse_design(self, design_content: str) -> List[ComponentSpec]:
        """
        Parse design.md to extract expected components.

        Args:
            design_content: Content of design.md file

        Returns:
            List of expected components
        """
        components = []

        # Find component definitions
        # Pattern: ## Компонент: ИмяКомпонента or ### Module: НазваниеМодуля
        component_pattern = re.compile(
            r'(?:#{2,3})\s*(?:Компонент|Component|Module|Модуль):\s*([^\n]+)',
            re.IGNORECASE
        )

        for match in component_pattern.finditer(design_content):
            name = match.group(1).strip()

            # Determine type from context
            comp_type = self._detect_component_type(name, design_content[match.start():])

            # Find interface (exported functions/procedures)
            interface = self._extract_interface(design_content[match.start():match.start() + 2000])

            components.append(ComponentSpec(
                name=name,
                type=comp_type,
                required=True,
                interface=interface,
            ))

        # Also look for explicit tables
        # | Компонент | Тип | Описание |
        table_pattern = re.compile(
            r'\|\s*([А-Яа-яA-Za-z_][А-Яа-яA-Za-z0-9_]*)\s*\|\s*([^\|]+)\s*\|',
            re.IGNORECASE
        )

        for match in table_pattern.finditer(design_content):
            name = match.group(1).strip()
            comp_type = match.group(2).strip().lower()

            # Skip header rows
            if name.lower() in ('компонент', 'component', 'модуль', 'module', '---'):
                continue

            # Avoid duplicates
            if not any(c.name == name for c in components):
                components.append(ComponentSpec(
                    name=name,
                    type=comp_type,
                    required=True,
                ))

        return components

    def _detect_component_type(self, name: str, context: str) -> str:
        """Detect component type from name and context."""
        name_lower = name.lower()
        context_lower = context.lower()

        # Check for explicit type mentions
        for eng, rus in self.OBJECT_TYPES.items():
            if eng.lower() in context_lower or rus.lower() in context_lower:
                return eng

        # Infer from naming patterns
        if 'модуль' in name_lower or 'module' in name_lower:
            return 'CommonModule'
        if 'форма' in name_lower or 'form' in name_lower:
            return 'Form'
        if 'регистр' in name_lower or 'register' in name_lower:
            return 'Register'
        if 'обработка' in name_lower or 'dataprocessor' in name_lower:
            return 'DataProcessor'
        if 'отчёт' in name_lower or 'report' in name_lower:
            return 'Report'

        return 'unknown'

    def _extract_interface(self, context: str) -> Optional[List[str]]:
        """Extract expected interface (exports) from context."""
        exports = []

        # Look for function/procedure definitions in code blocks
        func_pattern = re.compile(
            r'(?:Функция|Процедура|Function|Procedure)\s+([А-Яа-яA-Za-z_][А-Яа-яA-Za-z0-9_]*)\s*\(',
            re.IGNORECASE
        )

        for match in func_pattern.finditer(context):
            func_name = match.group(1)
            # Check if marked as export
            line_end = context.find('\n', match.end())
            if line_end > 0:
                line = context[match.start():line_end]
                if 'Экспорт' in line or 'Export' in line:
                    exports.append(func_name)

        # Also look for bullet lists
        # - ПолучитьДанные() - получает данные
        bullet_pattern = re.compile(
            r'[-*]\s*([А-Яа-яA-Za-z_][А-Яа-яA-Za-z0-9_]*)\s*\(',
            re.IGNORECASE
        )

        for match in bullet_pattern.finditer(context):
            func_name = match.group(1)
            if func_name not in exports:
                exports.append(func_name)

        return exports if exports else None

    def check(
        self,
        spec: List[ComponentSpec],
        implemented_files: List[str],
        code_content: Optional[Dict[str, str]] = None
    ) -> ArchCheckResult:
        """
        Check implementation against specification.

        Args:
            spec: Expected components from design.md
            implemented_files: List of implemented file paths
            code_content: Optional dict of file_path -> content

        Returns:
            ArchCheckResult with issues
        """
        result = ArchCheckResult()

        # Normalize file paths for matching
        impl_names = self._extract_component_names(implemented_files)

        # Check for missing components
        for component in spec:
            if component.required:
                if not self._is_component_implemented(component.name, impl_names):
                    result.missing_components.append(component.name)
                    result.issues.append(ArchIssue(
                        component=component.name,
                        issue_type="missing",
                        description=f"Компонент '{component.name}' не реализован",
                        severity=IssueSeverity.CRITICAL,
                        recommendation=f"Реализовать {component.type}: {component.name}",
                    ))

        # Check interfaces if code content provided
        if code_content:
            for component in spec:
                if component.interface:
                    file_path = self._find_component_file(component.name, implemented_files)
                    if file_path and file_path in code_content:
                        violations = self._check_interface(
                            component.interface,
                            code_content[file_path]
                        )
                        for missing_func in violations:
                            result.interface_violations.append(
                                f"{component.name}.{missing_func}"
                            )
                            result.issues.append(ArchIssue(
                                component=component.name,
                                issue_type="wrong_interface",
                                description=f"Отсутствует экспортная функция: {missing_func}",
                                severity=IssueSeverity.WARNING,
                                related_files=[file_path],
                                recommendation=f"Добавить: Функция {missing_func}(...) Экспорт",
                            ))

        # Check for circular dependencies
        if code_content:
            circular = self._detect_circular_dependencies(code_content)
            result.circular_dependencies = circular
            for dep1, dep2 in circular:
                result.issues.append(ArchIssue(
                    component=dep1,
                    issue_type="circular_dep",
                    description=f"Циклическая зависимость: {dep1} ↔ {dep2}",
                    severity=IssueSeverity.WARNING,
                    recommendation="Вынести общий код в отдельный модуль",
                ))

        # Check BSL-specific patterns
        if code_content:
            pattern_issues = self._check_bsl_patterns(code_content)
            result.issues.extend(pattern_issues)

        # Calculate score
        result.score = self._calculate_score(result)

        return result

    def _extract_component_names(self, file_paths: List[str]) -> Set[str]:
        """Extract component names from file paths."""
        names = set()
        for path in file_paths:
            # Get filename without extension
            p = Path(path)
            name = p.stem

            # Also add parent folder name for modules
            if name.lower() in ('module', 'ext'):
                parent = p.parent.name
                if parent:
                    names.add(parent)

            names.add(name)

        return names

    def _is_component_implemented(self, name: str, impl_names: Set[str]) -> bool:
        """Check if component is implemented."""
        name_lower = name.lower()

        for impl in impl_names:
            if impl.lower() == name_lower:
                return True
            # Check partial match (e.g., "гкс_МойМодуль" matches "МойМодуль")
            if name_lower in impl.lower() or impl.lower() in name_lower:
                return True

        return False

    def _find_component_file(self, name: str, file_paths: List[str]) -> Optional[str]:
        """Find file path for component."""
        name_lower = name.lower()

        for path in file_paths:
            if name_lower in path.lower():
                return path

        return None

    def _check_interface(
        self,
        expected: List[str],
        code: str
    ) -> List[str]:
        """Check if expected interface is implemented."""
        missing = []
        code_lower = code.lower()

        for func_name in expected:
            # Look for function/procedure with export
            pattern = re.compile(
                rf'(?:Функция|Процедура)\s+{re.escape(func_name)}\s*\([^)]*\)\s*Экспорт',
                re.IGNORECASE
            )
            if not pattern.search(code):
                missing.append(func_name)

        return missing

    def _detect_circular_dependencies(
        self,
        code_content: Dict[str, str]
    ) -> List[Tuple[str, str]]:
        """Detect circular dependencies between modules."""
        # Build dependency graph
        deps: Dict[str, Set[str]] = {}

        for file_path, content in code_content.items():
            module_name = Path(file_path).stem
            deps[module_name] = set()

            # Find module references
            # Common pattern: МодульИмя.Функция(
            ref_pattern = re.compile(
                r'([А-Яа-яA-Za-z_][А-Яа-яA-Za-z0-9_]*)\s*\.\s*[А-Яа-яA-Za-z_][А-Яа-яA-Za-z0-9_]*\s*\('
            )

            for match in ref_pattern.finditer(content):
                ref_module = match.group(1)
                # Skip built-in objects
                if ref_module not in ('Справочники', 'Документы', 'РегистрыСведений',
                                     'ОбщегоНазначения', 'Строка', 'Массив', 'Запрос'):
                    deps[module_name].add(ref_module)

        # Find cycles
        circular = []
        for module_a in deps:
            for module_b in deps.get(module_a, set()):
                if module_a in deps.get(module_b, set()):
                    # Avoid duplicates (A→B and B→A)
                    pair = tuple(sorted([module_a, module_b]))
                    if pair not in circular:
                        circular.append(pair)

        return circular

    def _check_bsl_patterns(self, code_content: Dict[str, str]) -> List[ArchIssue]:
        """Check BSL-specific architectural patterns."""
        issues = []

        for file_path, content in code_content.items():
            module_name = Path(file_path).stem

            # Check 1: Серверный модуль не должен вызывать клиентские методы
            if self._is_server_module(file_path, content):
                client_calls = self._find_client_calls(content)
                if client_calls:
                    issues.append(ArchIssue(
                        component=module_name,
                        issue_type="wrong_structure",
                        description=f"Серверный модуль вызывает клиентские методы: {', '.join(client_calls[:3])}",
                        severity=IssueSeverity.CRITICAL,
                        related_files=[file_path],
                        recommendation="Перенести вызовы на клиент или использовать callback",
                    ))

            # Check 2: Общий модуль должен иметь явное указание контекста
            if 'CommonModules' in file_path:
                if not self._has_context_annotation(content):
                    issues.append(ArchIssue(
                        component=module_name,
                        issue_type="wrong_structure",
                        description="Общий модуль без явного указания контекста выполнения",
                        severity=IssueSeverity.RECOMMENDATION,
                        related_files=[file_path],
                        recommendation="Добавить &НаСервере, &НаКлиенте или &НаСервереБезКонтекста",
                    ))

            # Check 3: Модуль формы не должен содержать бизнес-логику
            if 'Form' in file_path and 'Module.bsl' in file_path:
                if self._has_business_logic(content):
                    issues.append(ArchIssue(
                        component=module_name,
                        issue_type="wrong_structure",
                        description="Модуль формы содержит бизнес-логику",
                        severity=IssueSeverity.RECOMMENDATION,
                        related_files=[file_path],
                        recommendation="Вынести логику в общий модуль или модуль объекта",
                    ))

        return issues

    def _is_server_module(self, file_path: str, content: str) -> bool:
        """Check if module is server-side."""
        # Check path
        if 'CommonModules' in file_path:
            return '&НаСервере' in content or '&НаСервереБезКонтекста' in content

        # Object modules are always server
        if 'ObjectModule.bsl' in file_path or 'ManagerModule.bsl' in file_path:
            return True

        return False

    def _find_client_calls(self, content: str) -> List[str]:
        """Find client-only method calls in code."""
        client_methods = [
            'Предупреждение', 'Вопрос', 'ОткрытьФорму', 'ОткрытьФормуМодально',
            'ПоказатьВводДаты', 'ПоказатьВводЗначения', 'ПоказатьПредупреждение',
            'ПоказатьВопрос', 'ПолучитьФорму',
        ]

        found = []
        for method in client_methods:
            if re.search(rf'\b{method}\s*\(', content):
                found.append(method)

        return found

    def _has_context_annotation(self, content: str) -> bool:
        """Check if module has context annotation."""
        annotations = ['&НаСервере', '&НаКлиенте', '&НаСервереБезКонтекста', '&НаКлиентеНаСервереБезКонтекста']
        return any(ann in content for ann in annotations)

    def _has_business_logic(self, content: str) -> bool:
        """Check if form module contains business logic (heuristic)."""
        # Indicators of business logic in form
        indicators = [
            r'Запрос\s*=\s*Новый\s+Запрос',  # Query creation
            r'НачатьТранзакцию\s*\(',  # Transaction
            r'\.Записать\s*\(',  # Object write
            r'\.Провести\s*\(',  # Document posting
        ]

        indicator_count = 0
        for pattern in indicators:
            if re.search(pattern, content):
                indicator_count += 1

        # If more than 2 indicators, likely has business logic
        return indicator_count >= 2

    def _calculate_score(self, result: ArchCheckResult) -> float:
        """Calculate architecture score (0-100)."""
        score = 100.0

        # Missing components are critical
        score -= len(result.missing_components) * 20.0

        # Interface violations are important
        score -= len(result.interface_violations) * 10.0

        # Circular dependencies
        score -= len(result.circular_dependencies) * 15.0

        # Other issues
        for issue in result.issues:
            if issue.issue_type not in ('missing', 'wrong_interface', 'circular_dep'):
                if issue.severity == IssueSeverity.CRITICAL:
                    score -= 10.0
                elif issue.severity == IssueSeverity.WARNING:
                    score -= 5.0
                else:
                    score -= 1.0

        return max(0.0, score)

    def to_review_issues(self, result: ArchCheckResult) -> List[ReviewIssue]:
        """
        Convert architecture issues to review issues.

        Args:
            result: Architecture check result

        Returns:
            List of ReviewIssue
        """
        review_issues = []

        for arch_issue in result.issues:
            self._issue_counter[arch_issue.severity] += 1

            prefix = {
                IssueSeverity.CRITICAL: "CR",
                IssueSeverity.WARNING: "WRN",
                IssueSeverity.RECOMMENDATION: "REC",
            }.get(arch_issue.severity, "ISS")

            issue = ReviewIssue(
                id=f"{prefix}-{self._issue_counter[arch_issue.severity]:03d}",
                title=f"Архитектура: {arch_issue.component}",
                description=arch_issue.description,
                severity=arch_issue.severity,
                category=IssueCategory.MAINTAINABILITY,
                file_path=arch_issue.related_files[0] if arch_issue.related_files else None,
                recommendation=arch_issue.recommendation,
            )
            review_issues.append(issue)

        return review_issues


# Convenience functions
def check_architecture(
    design_content: str,
    implemented_files: List[str],
    code_content: Optional[Dict[str, str]] = None
) -> ArchCheckResult:
    """
    Check implementation against design specification.

    Args:
        design_content: Content of design.md
        implemented_files: List of implemented file paths
        code_content: Optional dict of file_path -> content

    Returns:
        ArchCheckResult
    """
    checker = ArchChecker()
    spec = checker.parse_design(design_content)
    return checker.check(spec, implemented_files, code_content)


def parse_design_spec(design_content: str) -> List[ComponentSpec]:
    """
    Parse design.md to extract component specifications.

    Args:
        design_content: Content of design.md

    Returns:
        List of ComponentSpec
    """
    checker = ArchChecker()
    return checker.parse_design(design_content)
