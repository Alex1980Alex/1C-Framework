"""
Context Generator for INITIALIZER Agent.

Generates context.md report from project structure.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from agents.initializer.models import (
    ObjectType,
    ProjectStructure,
    ModuleInfo,
    RelevantFile,
    ContextReport,
    InitializerConfig,
)


class ContextGenerator:
    """
    Generates context.md report for other agents.

    Features:
    - Markdown report generation
    - Project overview
    - Module listings by type
    - Relevant files section
    - Dependency graph (Mermaid)
    """

    def __init__(self, config: Optional[InitializerConfig] = None) -> None:
        """Initialize generator with config."""
        self.config = config or InitializerConfig()

    def generate(
        self,
        project_id: str,
        structure: ProjectStructure,
        task_description: str,
        relevant_files: list[RelevantFile],
    ) -> ContextReport:
        """
        Generate context report.

        Args:
            project_id: Project identifier
            structure: Scanned project structure
            task_description: Task description for relevance
            relevant_files: List of relevant files with scores

        Returns:
            ContextReport with markdown content
        """
        # Generate markdown
        markdown = self._generate_markdown(
            project_id=project_id,
            structure=structure,
            task_description=task_description,
            relevant_files=relevant_files,
        )

        # Create report
        report = ContextReport(
            project_id=project_id,
            project_structure=structure,
            task_description=task_description,
            relevant_files=relevant_files,
            generated_at=datetime.now(),
            markdown_content=markdown,
        )

        return report

    def _generate_markdown(
        self,
        project_id: str,
        structure: ProjectStructure,
        task_description: str,
        relevant_files: list[RelevantFile],
    ) -> str:
        """Generate markdown content."""
        lines = []

        # Header
        lines.append(f"# Контекст проекта: {project_id}")
        lines.append("")

        # Overview section
        lines.extend(self._generate_overview(structure))
        lines.append("")

        # Project structure
        lines.extend(self._generate_structure_section(structure))
        lines.append("")

        # Relevant files for task
        lines.extend(self._generate_relevant_files_section(
            task_description=task_description,
            relevant_files=relevant_files,
        ))
        lines.append("")

        # Dependencies graph
        lines.extend(self._generate_dependencies_section(structure, relevant_files))
        lines.append("")

        # Patterns section
        lines.extend(self._generate_patterns_section(structure))
        lines.append("")

        # Footer
        lines.append("---")
        lines.append(f"*Сгенерировано: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

        return "\n".join(lines)

    def _generate_overview(self, structure: ProjectStructure) -> list[str]:
        """Generate overview section."""
        lines = [
            "## Обзор",
            "",
            f"- **Тип**: {structure.project_type.ru_name}",
            f"- **Всего файлов**: {structure.total_files}",
            f"- **BSL модулей**: {structure.total_bsl_files}",
            f"- **Объектов**: {structure.total_modules}",
            f"- **Последнее сканирование**: {structure.scanned_at.strftime('%Y-%m-%dT%H:%M:%S')}",
        ]
        return lines

    def _generate_structure_section(self, structure: ProjectStructure) -> list[str]:
        """Generate project structure section."""
        lines = ["## Структура проекта", ""]

        # Group modules by type
        modules_by_type: dict[ObjectType, list[ModuleInfo]] = {}
        for module in structure.modules:
            if module.object_type not in modules_by_type:
                modules_by_type[module.object_type] = []
            modules_by_type[module.object_type].append(module)

        # Order of object types for display
        type_order = [
            ObjectType.CATALOG,
            ObjectType.DOCUMENT,
            ObjectType.ACCUMULATION_REGISTER,
            ObjectType.INFORMATION_REGISTER,
            ObjectType.COMMON_MODULE,
            ObjectType.DATA_PROCESSOR,
            ObjectType.REPORT,
            ObjectType.ENUM,
            ObjectType.CONSTANT,
        ]

        for obj_type in type_order:
            modules = modules_by_type.get(obj_type, [])
            if not modules:
                continue

            lines.append(f"### {obj_type.ru_name_plural} ({len(modules)})")
            lines.append("")
            lines.append("| Модуль | Файлов | Экспорт | Строк |")
            lines.append("|--------|--------|---------|-------|")

            # Sort by name
            for module in sorted(modules, key=lambda m: m.name):
                lines.append(
                    f"| {module.name} | {len(module.files)} | "
                    f"{module.exports_count} | {module.total_lines} |"
                )

            lines.append("")

        # Other types
        other_modules = []
        for obj_type, modules in modules_by_type.items():
            if obj_type not in type_order:
                other_modules.extend(modules)

        if other_modules:
            lines.append(f"### Другие объекты ({len(other_modules)})")
            lines.append("")
            for module in sorted(other_modules, key=lambda m: m.name):
                lines.append(f"- {module.name} ({module.object_type.ru_name})")
            lines.append("")

        return lines

    def _generate_relevant_files_section(
        self,
        task_description: str,
        relevant_files: list[RelevantFile],
    ) -> list[str]:
        """Generate relevant files section."""
        lines = [
            "## Релевантные файлы для задачи",
            "",
            f"> Задача: \"{task_description}\"",
            "",
        ]

        if not relevant_files:
            lines.append("*Релевантные файлы не определены*")
            return lines

        # High relevance
        high = [f for f in relevant_files if f.relevance_score > 0.8]
        if high:
            lines.append("### Высокая релевантность (score > 0.8)")
            lines.append("")
            for i, rf in enumerate(high, 1):
                module_info = f" ({rf.module_name})" if rf.module_name else ""
                lines.append(
                    f"{i}. `{rf.file_info.path.name}`{module_info} - {rf.relevance_reason}"
                )
            lines.append("")

        # Medium relevance
        medium = [f for f in relevant_files if 0.5 <= f.relevance_score <= 0.8]
        if medium:
            lines.append("### Средняя релевантность (score 0.5-0.8)")
            lines.append("")
            for i, rf in enumerate(medium, 1):
                lines.append(f"{i}. `{rf.file_info.path.name}` - {rf.relevance_reason}")
            lines.append("")

        # Low relevance
        low = [f for f in relevant_files if f.relevance_score < 0.5]
        if low:
            lines.append("### Низкая релевантность (score < 0.5)")
            lines.append("")
            for i, rf in enumerate(low, 1):
                lines.append(f"{i}. `{rf.file_info.path.name}` - {rf.relevance_reason}")
            lines.append("")

        return lines

    def _generate_dependencies_section(
        self,
        structure: ProjectStructure,
        relevant_files: list[RelevantFile],
    ) -> list[str]:
        """Generate dependencies section with Mermaid graph."""
        lines = ["## Зависимости", ""]

        # If we have structure.dependencies, show them even if no relevant_files
        if not relevant_files and not structure.dependencies:
            lines.append("*Зависимости не определены*")
            return lines

        # Generate Mermaid graph if we have relevant_files
        if relevant_files:
            lines.append("```mermaid")
            lines.append("graph TD")

            # Generate nodes and edges based on relevant files
            high_files = [f for f in relevant_files if f.relevance_score > 0.8]

            if high_files:
                lines.append("    A[Задача] --> B[Релевантные файлы]")
                for i, rf in enumerate(high_files[:5]):  # Limit to 5
                    node_id = chr(ord('C') + i)
                    name = rf.file_info.name[:20]  # Truncate long names
                    lines.append(f"    B --> {node_id}[{name}]")

            lines.append("```")
            lines.append("")

        # Text description
        if structure.dependencies:
            lines.append("### Обнаруженные зависимости")
            lines.append("")
            for dep in structure.dependencies[:10]:  # Limit
                lines.append(f"- {dep.source} → {dep.target} ({dep.dependency_type})")
            lines.append("")

        return lines

    def _generate_patterns_section(self, structure: ProjectStructure) -> list[str]:
        """Generate patterns section."""
        lines = ["## Паттерны проекта", ""]

        if not structure.patterns:
            lines.append("*Паттерны не обнаружены*")
            return lines

        for pattern in structure.patterns:
            lines.append(f"### {pattern.name}")
            lines.append("")
            lines.append(f"{pattern.description}")
            lines.append("")
            if pattern.examples:
                lines.append("**Примеры:**")
                for example in pattern.examples[:3]:
                    lines.append(f"- `{example}`")
                lines.append("")

        return lines

    def save_to_file(self, report: ContextReport, output_path: Path) -> Path:
        """
        Save context report to file.

        Args:
            report: Context report to save
            output_path: Directory to save to

        Returns:
            Path to saved file
        """
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        file_path = output_path / "context.md"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(report.markdown_content)

        return file_path


# Convenience functions

def generate_context(
    project_id: str,
    structure: ProjectStructure,
    task_description: str,
    relevant_files: list[RelevantFile],
    config: Optional[InitializerConfig] = None,
) -> ContextReport:
    """Generate context report."""
    generator = ContextGenerator(config)
    return generator.generate(
        project_id=project_id,
        structure=structure,
        task_description=task_description,
        relevant_files=relevant_files,
    )


def generate_context_markdown(
    project_id: str,
    structure: ProjectStructure,
    task_description: str,
    relevant_files: list[RelevantFile],
) -> str:
    """Generate context markdown string."""
    report = generate_context(
        project_id=project_id,
        structure=structure,
        task_description=task_description,
        relevant_files=relevant_files,
    )
    return report.markdown_content
