"""
1C Enterprise Metadata Extractor — Phase 62

Extracts object metadata from EDT folder structure.
No XML parsing — folder-based discovery only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ObjectInfo:
    """Information about a 1C Enterprise metadata object."""

    name: str
    object_type: str
    path: str
    modules: list[str] = field(default_factory=list)
    has_forms: bool = False
    form_names: list[str] = field(default_factory=list)


# EDT folder name -> 1C object type
FOLDER_TYPE_MAP: dict[str, str] = {
    # English
    "Catalogs": "Catalog",
    "Documents": "Document",
    "InformationRegisters": "InformationRegister",
    "AccumulationRegisters": "AccumulationRegister",
    "DataProcessors": "DataProcessor",
    "Reports": "Report",
    "CommonModules": "CommonModule",
    "Enums": "Enum",
    "Constants": "Constant",
    "ChartsOfCharacteristicTypes": "ChartOfCharacteristicTypes",
    "ChartsOfAccounts": "ChartOfAccounts",
    "ExchangePlans": "ExchangePlan",
    "CommonForms": "CommonForm",
    "Subsystems": "Subsystem",
    # Russian
    "Справочники": "Catalog",
    "Документы": "Document",
    "РегистрыСведений": "InformationRegister",
    "РегистрыНакопления": "AccumulationRegister",
    "Обработки": "DataProcessor",
    "Отчеты": "Report",
    "ОбщиеМодули": "CommonModule",
    "Перечисления": "Enum",
    "Константы": "Constant",
    "ПланыВидовХарактеристик": "ChartOfCharacteristicTypes",
    "ПланыСчетов": "ChartOfAccounts",
    "ПланыОбмена": "ExchangePlan",
    "ОбщиеФормы": "CommonForm",
    "Подсистемы": "Subsystem",
}


class MetadataExtractor:
    """Extract 1C Enterprise object metadata from EDT folder structure."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root)
        self._cache: list[ObjectInfo] | None = None

    def extract_objects(self) -> list[ObjectInfo]:
        """Scan folder structure and return all 1C metadata objects."""
        if self._cache is not None:
            return self._cache

        objects: list[ObjectInfo] = []
        src_path = self.project_root / "src"
        if not src_path.exists():
            self._cache = objects
            return objects

        for folder in sorted(src_path.iterdir()):
            if not folder.is_dir():
                continue
            obj_type = FOLDER_TYPE_MAP.get(folder.name)
            if obj_type is None:
                continue
            for obj_folder in sorted(folder.iterdir()):
                if not obj_folder.is_dir():
                    continue
                obj = self._build_object_info(obj_folder, obj_type, src_path)
                objects.append(obj)

        self._cache = objects
        return objects

    def _build_object_info(
        self, obj_folder: Path, obj_type: str, src_path: Path
    ) -> ObjectInfo:
        rel_path = str(obj_folder.relative_to(src_path)).replace("\\", "/")
        modules = [
            str(f.relative_to(obj_folder)).replace("\\", "/")
            for f in obj_folder.rglob("*.bsl")
        ]
        forms_dir = obj_folder / "Forms"
        form_names = (
            sorted(d.name for d in forms_dir.iterdir() if d.is_dir())
            if forms_dir.is_dir()
            else []
        )
        return ObjectInfo(
            name=obj_folder.name,
            object_type=obj_type,
            path=rel_path,
            modules=modules,
            has_forms=bool(form_names),
            form_names=form_names,
        )

    def get_object_modules(self, object_name: str) -> list[str]:
        """Full paths to BSL modules for an object."""
        src = self.project_root / "src"
        for obj in self.extract_objects():
            if obj.name == object_name:
                base = src / obj.path
                return [str(base / m) for m in obj.modules]
        return []

    def get_objects_by_type(self, object_type: str) -> list[ObjectInfo]:
        return [o for o in self.extract_objects() if o.object_type == object_type]

    def get_object_by_name(self, name: str) -> ObjectInfo | None:
        for o in self.extract_objects():
            if o.name == name:
                return o
        return None

    def stats(self) -> dict:
        objects = self.extract_objects()
        by_type: dict[str, int] = {}
        for o in objects:
            by_type[o.object_type] = by_type.get(o.object_type, 0) + 1
        return {"total": len(objects), "by_type": by_type}

    def clear_cache(self) -> None:
        self._cache = None
