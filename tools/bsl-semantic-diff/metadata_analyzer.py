#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BSL Metadata Analyzer - анализ XML метаданных 1С конфигурации
Stub implementation for Docker MCP
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional
import xml.etree.ElementTree as ET


@dataclass
class MetadataAttribute:
    """Реквизит метаданных"""
    name: str
    type: str = ""
    synonym: str = ""


@dataclass
class MetadataObject:
    """Объект метаданных 1С"""
    name: str
    object_type: str
    synonym: str = ""
    attributes: List[MetadataAttribute] = field(default_factory=list)
    dimensions: List[MetadataAttribute] = field(default_factory=list)
    resources: List[MetadataAttribute] = field(default_factory=list)
    forms: List[str] = field(default_factory=list)
    commands: List[str] = field(default_factory=list)


class BslMetadataAnalyzer:
    """Анализатор метаданных 1С конфигурации"""

    # Типы метаданных и их пути
    METADATA_TYPES = {
        'Catalog': 'Catalogs',
        'Document': 'Documents',
        'InformationRegister': 'InformationRegisters',
        'AccumulationRegister': 'AccumulationRegisters',
        'Report': 'Reports',
        'DataProcessor': 'DataProcessors',
        'CommonModule': 'CommonModules',
        'Enum': 'Enums',
        'ChartOfCharacteristicTypes': 'ChartsOfCharacteristicTypes',
        'ChartOfAccounts': 'ChartsOfAccounts',
        'Task': 'Tasks',
        'BusinessProcess': 'BusinessProcesses',
    }

    def find_metadata_objects(self, config_path: Path, object_type: str) -> List[MetadataObject]:
        """Поиск объектов метаданных заданного типа"""
        objects = []

        # Определяем путь к метаданным
        type_folder = self.METADATA_TYPES.get(object_type, object_type)
        metadata_path = config_path / 'src' / type_folder

        if not metadata_path.exists():
            metadata_path = config_path / type_folder

        if not metadata_path.exists():
            return objects

        # Сканируем директорию
        for item in metadata_path.iterdir():
            if item.is_dir():
                obj = self._parse_metadata_object(item, object_type)
                if obj:
                    objects.append(obj)

        return objects

    def _parse_metadata_object(self, obj_path: Path, object_type: str) -> Optional[MetadataObject]:
        """Парсинг объекта метаданных из директории"""
        obj_name = obj_path.name

        # Ищем XML файл с описанием
        xml_file = obj_path / f'{obj_name}.xml'
        if not xml_file.exists():
            # Альтернативный путь для EDT формата
            xml_file = obj_path / f'{obj_name}.mdo'

        obj = MetadataObject(name=obj_name, object_type=object_type)

        if xml_file.exists():
            try:
                tree = ET.parse(xml_file)
                root = tree.getroot()

                # Ищем Synonym
                for elem in root.iter():
                    if elem.tag.endswith('Synonym'):
                        for v in elem.iter():
                            if v.tag.endswith('v') and v.text:
                                obj.synonym = v.text
                                break

                # Ищем реквизиты (Attributes)
                for attr in root.iter():
                    if attr.tag.endswith('Attribute'):
                        attr_name = ""
                        for child in attr:
                            if child.tag.endswith('Name') and child.text:
                                attr_name = child.text
                        if attr_name:
                            obj.attributes.append(MetadataAttribute(name=attr_name))

                # Ищем измерения (Dimensions) для регистров
                for dim in root.iter():
                    if dim.tag.endswith('Dimension'):
                        dim_name = ""
                        for child in dim:
                            if child.tag.endswith('Name') and child.text:
                                dim_name = child.text
                        if dim_name:
                            obj.dimensions.append(MetadataAttribute(name=dim_name))

                # Ищем ресурсы (Resources) для регистров
                for res in root.iter():
                    if res.tag.endswith('Resource'):
                        res_name = ""
                        for child in res:
                            if child.tag.endswith('Name') and child.text:
                                res_name = child.text
                        if res_name:
                            obj.resources.append(MetadataAttribute(name=res_name))

            except ET.ParseError:
                pass  # Не удалось распарсить XML

        return obj

    def compare_metadata(self, obj1: MetadataObject, obj2: MetadataObject) -> Dict:
        """Сравнение двух объектов метаданных"""
        changes = {
            'attributes_added': [],
            'attributes_removed': [],
            'dimensions_added': [],
            'dimensions_removed': [],
            'resources_added': [],
            'resources_removed': [],
            'has_changes': False
        }

        attrs1 = {a.name for a in obj1.attributes}
        attrs2 = {a.name for a in obj2.attributes}

        changes['attributes_added'] = list(attrs2 - attrs1)
        changes['attributes_removed'] = list(attrs1 - attrs2)

        dims1 = {d.name for d in obj1.dimensions}
        dims2 = {d.name for d in obj2.dimensions}

        changes['dimensions_added'] = list(dims2 - dims1)
        changes['dimensions_removed'] = list(dims1 - dims2)

        res1 = {r.name for r in obj1.resources}
        res2 = {r.name for r in obj2.resources}

        changes['resources_added'] = list(res2 - res1)
        changes['resources_removed'] = list(res1 - res2)

        changes['has_changes'] = any([
            changes['attributes_added'], changes['attributes_removed'],
            changes['dimensions_added'], changes['dimensions_removed'],
            changes['resources_added'], changes['resources_removed']
        ])

        return changes
