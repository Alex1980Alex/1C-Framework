#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EDT XML Parser - Гибридный парсер для XML файлов конфигураций 1С:Предприятие

Версия: 1.0.0
Дата: 2026-01-02

Возможности:
- Полная поддержка namespaces 1C v8
- Парсинг Form.xml, Rights.xml, Subsystems, Metadata
- Безопасное редактирование XML с сохранением структуры
- Извлечение структурированных данных для RAG индексации
- Интеграция с mdclasses (Java) для сложных операций
"""

import sys
import re
import json
import hashlib
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# Используем lxml для robust XML parsing
try:
    from lxml import etree
    LXML_AVAILABLE = True
except ImportError:
    import xml.etree.ElementTree as etree
    LXML_AVAILABLE = False
    print("[WARNING] lxml not available, using xml.etree (limited namespace support)", file=sys.stderr)


def log_stderr(*args, **kwargs):
    """Логирование в stderr для MCP совместимости"""
    print(*args, file=sys.stderr, **kwargs)


# =============================================================================
# NAMESPACES REGISTRY - Все известные namespaces 1C v8
# =============================================================================

V8_NAMESPACES = {
    # Основные
    "mdclass": "http://v8.1c.ru/8.3/MDClasses",
    "form": "http://v8.1c.ru/8.3/xcf/logform",
    "readable": "http://v8.1c.ru/8.3/xcf/readable",
    "extrnprops": "http://v8.1c.ru/8.3/xcf/extrnprops",
    "predef": "http://v8.1c.ru/8.3/xcf/predef",
    "enums": "http://v8.1c.ru/8.3/xcf/enums",

    # Данные и ядро
    "v8": "http://v8.1c.ru/8.1/data/core",
    "v8ui": "http://v8.1c.ru/8.1/data/ui",
    "ent": "http://v8.1c.ru/8.1/data/enterprise",
    "cfg": "http://v8.1c.ru/8.1/data/enterprise/current-config",

    # UI и стили
    "style": "http://v8.1c.ru/8.1/data/ui/style",
    "sys": "http://v8.1c.ru/8.1/data/ui/fonts/system",
    "web": "http://v8.1c.ru/8.1/data/ui/colors/web",
    "win": "http://v8.1c.ru/8.1/data/ui/colors/windows",

    # Приложение
    "app": "http://v8.1c.ru/8.2/managed-application/core",
    "cmi": "http://v8.1c.ru/8.2/managed-application/cmi",
    "lf": "http://v8.1c.ru/8.2/managed-application/logform",

    # СКД
    "dcscor": "http://v8.1c.ru/8.1/data-composition-system/core",
    "dcssch": "http://v8.1c.ru/8.1/data-composition-system/schema",
    "dcsset": "http://v8.1c.ru/8.1/data-composition-system/settings",

    # Роли
    "roles": "http://v8.1c.ru/8.2/roles",

    # XML Schema
    "xs": "http://www.w3.org/2001/XMLSchema",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}

# Обратный маппинг URI -> prefix
V8_NAMESPACES_REVERSE = {v: k for k, v in V8_NAMESPACES.items()}


# =============================================================================
# DATA CLASSES
# =============================================================================

class XMLDocType(Enum):
    """Типы XML документов 1C EDT"""
    FORM = "form"
    RIGHTS = "rights"
    SUBSYSTEM = "subsystem"
    METADATA = "metadata"
    COMMAND_INTERFACE = "command_interface"
    HELP = "help"
    LANGUAGE = "language"
    UNKNOWN = "unknown"


@dataclass
class FormElement:
    """Элемент формы"""
    name: str
    element_type: str  # InputField, Button, UsualGroup, etc.
    id: int
    data_path: Optional[str] = None
    title: Optional[str] = None
    events: List[str] = field(default_factory=list)
    children: List['FormElement'] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "type": self.element_type,
            "id": self.id,
            "data_path": self.data_path,
            "title": self.title,
            "events": self.events,
            "children_count": len(self.children)
        }


@dataclass
class FormAttribute:
    """Реквизит формы"""
    name: str
    value_type: str
    title: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "value_type": self.value_type,
            "title": self.title
        }


@dataclass
class FormCommand:
    """Команда формы"""
    name: str
    action: str
    title: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "action": self.action,
            "title": self.title
        }


@dataclass
class ParsedForm:
    """Распарсенная форма"""
    path: str
    form_name: str
    version: str
    elements: List[FormElement] = field(default_factory=list)
    attributes: List[FormAttribute] = field(default_factory=list)
    commands: List[FormCommand] = field(default_factory=list)
    events: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "path": self.path,
            "form_name": self.form_name,
            "version": self.version,
            "elements_count": len(self.elements),
            "elements": [e.to_dict() for e in self.elements],
            "attributes": [a.to_dict() for a in self.attributes],
            "commands": [c.to_dict() for c in self.commands],
            "events": self.events
        }

    def get_summary(self) -> str:
        """Генерация summary для RAG индексации"""
        lines = [
            f"Форма: {self.form_name}",
            f"Элементов: {len(self.elements)}",
            f"Реквизитов: {len(self.attributes)}",
            f"Команд: {len(self.commands)}",
        ]

        if self.events:
            lines.append(f"Обработчики: {', '.join(self.events.keys())}")

        # Топ элементы
        if self.elements:
            top_elements = [e.name for e in self.elements[:10]]
            lines.append(f"Элементы: {', '.join(top_elements)}")

        return "\n".join(lines)


@dataclass
class RightObject:
    """Право на объект"""
    object_name: str
    rights: Dict[str, bool] = field(default_factory=dict)


@dataclass
class ParsedRights:
    """Распарсенные права роли"""
    role_name: str
    path: str
    objects: List[RightObject] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "role_name": self.role_name,
            "path": self.path,
            "objects_count": len(self.objects),
            "objects": [
                {"name": o.object_name, "rights": o.rights}
                for o in self.objects
            ]
        }


@dataclass
class SubsystemInfo:
    """Информация о подсистеме"""
    name: str
    synonym: Optional[str] = None
    include_in_command_interface: bool = True
    content: List[str] = field(default_factory=list)
    subsystems: List['SubsystemInfo'] = field(default_factory=list)


# =============================================================================
# MAIN PARSER CLASS
# =============================================================================

class EDTXMLParser:
    """
    Гибридный парсер XML для 1C EDT

    Использует lxml для robust parsing с полной поддержкой namespaces.
    Fallback на xml.etree.ElementTree если lxml недоступен.
    """

    def __init__(self, project_path: Optional[str] = None):
        """
        Args:
            project_path: Путь к проекту 1C EDT (директория с src/)
        """
        self.project_path = Path(project_path) if project_path else None
        self.ns = V8_NAMESPACES
        self._parser = etree.XMLParser(
            remove_blank_text=False,
            recover=True  # Восстановление после ошибок
        ) if LXML_AVAILABLE else None

    def detect_document_type(self, xml_path: Union[str, Path]) -> XMLDocType:
        """Определение типа XML документа по пути и содержимому"""
        path = Path(xml_path)
        name_lower = path.name.lower()
        parent_lower = path.parent.name.lower()

        if name_lower == "form.xml":
            return XMLDocType.FORM
        elif name_lower == "rights.xml":
            return XMLDocType.RIGHTS
        elif name_lower == "commandinterface.xml":
            return XMLDocType.COMMAND_INTERFACE
        elif name_lower == "help.xml":
            return XMLDocType.HELP
        elif parent_lower == "subsystems" or "subsystem" in name_lower:
            return XMLDocType.SUBSYSTEM
        elif parent_lower == "languages":
            return XMLDocType.LANGUAGE
        elif path.suffix.lower() == ".xml":
            return XMLDocType.METADATA

        return XMLDocType.UNKNOWN

    def parse_xml(self, xml_path: Union[str, Path]) -> Optional[etree._Element]:
        """
        Безопасный парсинг XML файла

        Args:
            xml_path: Путь к XML файлу

        Returns:
            Root element или None при ошибке
        """
        path = Path(xml_path)
        if not path.exists():
            log_stderr(f"[ERROR] File not found: {path}")
            return None

        try:
            if LXML_AVAILABLE:
                tree = etree.parse(str(path), self._parser)
                return tree.getroot()
            else:
                tree = etree.parse(str(path))
                return tree.getroot()
        except Exception as e:
            log_stderr(f"[ERROR] Failed to parse {path}: {e}")
            return None

    def _get_text(self, element: Optional[Any], xpath: str, default: str = "") -> str:
        """Безопасное извлечение текста по XPath"""
        if element is None:
            return default

        try:
            if LXML_AVAILABLE:
                result = element.xpath(xpath, namespaces=self.ns)
                if result:
                    if isinstance(result[0], str):
                        return result[0]
                    return result[0].text or default
            else:
                # Fallback для ElementTree
                for prefix, uri in self.ns.items():
                    xpath = xpath.replace(f"{prefix}:", f"{{{uri}}}")
                found = element.find(xpath)
                if found is not None and found.text:
                    return found.text
        except Exception:
            pass

        return default

    def _find_all(self, element: Any, xpath: str) -> List:
        """Безопасный поиск всех элементов по XPath"""
        if element is None:
            return []

        try:
            if LXML_AVAILABLE:
                return element.xpath(xpath, namespaces=self.ns)
            else:
                # Конвертация XPath для ElementTree
                for prefix, uri in self.ns.items():
                    xpath = xpath.replace(f"{prefix}:", f"{{{uri}}}")
                return element.findall(xpath)
        except Exception as e:
            log_stderr(f"[WARNING] XPath error: {e}")
            return []

    # =========================================================================
    # FORM PARSING
    # =========================================================================

    def parse_form(self, form_path: Union[str, Path]) -> Optional[ParsedForm]:
        """
        Парсинг Form.xml

        Args:
            form_path: Путь к Form.xml

        Returns:
            ParsedForm или None
        """
        root = self.parse_xml(form_path)
        if root is None:
            return None

        path = Path(form_path)
        form_name = path.parent.parent.name  # .../FormName/Ext/Form.xml

        # Версия формы
        version = root.get("version", "unknown")

        parsed = ParsedForm(
            path=str(path),
            form_name=form_name,
            version=version
        )

        # События формы
        events_elem = root.find(".//{%s}Events" % self.ns.get("form", ""))
        if events_elem is None:
            # Попробуем без namespace
            events_elem = root.find(".//Events")

        if events_elem is not None:
            for event in events_elem:
                event_name = event.get("name") or event.tag.split("}")[-1]
                if event.text:
                    parsed.events[event_name] = event.text

        # Элементы формы
        parsed.elements = self._parse_form_elements(root)

        # Реквизиты
        parsed.attributes = self._parse_form_attributes(root)

        # Команды
        parsed.commands = self._parse_form_commands(root)

        return parsed

    def _parse_form_elements(self, root: Any, parent: Any = None) -> List[FormElement]:
        """Рекурсивный парсинг элементов формы"""
        elements = []

        # Ищем ChildItems
        search_root = parent if parent is not None else root
        child_items = None

        for tag in ["ChildItems", "{%s}ChildItems" % self.ns.get("form", "")]:
            child_items = search_root.find(f".//{tag}") if parent is None else search_root.find(tag)
            if child_items is not None:
                break

        if child_items is None:
            return elements

        for elem in child_items:
            tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            elem_name = elem.get("name", "")
            elem_id = int(elem.get("id", 0))

            # DataPath
            data_path = None
            dp = elem.find("DataPath") or elem.find("{%s}DataPath" % self.ns.get("form", ""))
            if dp is not None and dp.text:
                data_path = dp.text

            # Title (ищем в v8:item)
            title = None
            title_elem = elem.find(".//Title")
            if title_elem is not None:
                content_elems = self._find_all(title_elem, ".//v8:content")
                if content_elems and content_elems[0].text:
                    title = content_elems[0].text

            # События элемента
            events = []
            events_elem = elem.find("Events") or elem.find("{%s}Events" % self.ns.get("form", ""))
            if events_elem is not None:
                for event in events_elem:
                    event_name = event.get("name", "")
                    if event_name and event.text:
                        events.append(f"{event_name}={event.text}")

            form_elem = FormElement(
                name=elem_name,
                element_type=tag_name,
                id=elem_id,
                data_path=data_path,
                title=title,
                events=events
            )

            # Рекурсия для вложенных элементов
            form_elem.children = self._parse_form_elements(root, elem)

            elements.append(form_elem)

        return elements

    def _parse_form_attributes(self, root: Any) -> List[FormAttribute]:
        """Парсинг реквизитов формы"""
        attributes = []

        # Ищем Attributes элементы
        attr_elems = self._find_all(root, ".//Attributes")
        if not attr_elems:
            # Пробуем с namespace
            attr_elems = self._find_all(root, ".//form:Attributes")

        for attr in attr_elems:
            for item in attr:
                name = item.get("name", "")
                if not name:
                    continue

                # ValueType
                value_type = ""
                vt = item.find("ValueType") or item.find("{%s}ValueType" % self.ns.get("form", ""))
                if vt is not None:
                    # Получаем типы из Type элементов
                    types = []
                    # Сначала ищем с namespace
                    type_elems = self._find_all(vt, ".//v8:Type")
                    if not type_elems:
                        # Fallback без namespace
                        type_elems = vt.findall(".//Type")
                    for t in type_elems:
                        if t.text:
                            types.append(t.text)
                    value_type = ", ".join(types) if types else ""

                attributes.append(FormAttribute(
                    name=name,
                    value_type=value_type
                ))

        return attributes

    def _parse_form_commands(self, root: Any) -> List[FormCommand]:
        """Парсинг команд формы"""
        commands = []

        # Ищем команды формы
        cmd_sections = self._find_all(root, ".//Commands")
        if not cmd_sections:
            cmd_sections = root.findall(".//Commands")

        for cmd_section in cmd_sections:
            for cmd in cmd_section:
                name = cmd.get("name", "")
                if not name:
                    continue

                action = ""
                action_elem = cmd.find("Action") or cmd.find("{%s}Action" % self.ns.get("form", ""))
                if action_elem is not None and action_elem.text:
                    action = action_elem.text

                commands.append(FormCommand(
                    name=name,
                    action=action
                ))

        return commands

    # =========================================================================
    # RIGHTS PARSING
    # =========================================================================

    def parse_rights(self, rights_path: Union[str, Path]) -> Optional[ParsedRights]:
        """
        Парсинг Rights.xml роли

        Args:
            rights_path: Путь к Rights.xml

        Returns:
            ParsedRights или None
        """
        root = self.parse_xml(rights_path)
        if root is None:
            return None

        path = Path(rights_path)
        role_name = path.parent.parent.name  # .../RoleName/Ext/Rights.xml

        parsed = ParsedRights(
            role_name=role_name,
            path=str(path)
        )

        # Namespace для ролей
        roles_ns = {"roles": self.ns.get("roles", "http://v8.1c.ru/8.2/roles")}

        # Ищем все объекты
        obj_elems = self._find_all(root, ".//roles:object")
        if not obj_elems:
            obj_elems = root.findall(".//object")

        for obj in obj_elems:
            obj_name_elems = self._find_all(obj, ".//roles:name")
            if not obj_name_elems:
                obj_name_elem = obj.find("name")
            else:
                obj_name_elem = obj_name_elems[0]

            if obj_name_elem is None or not obj_name_elem.text:
                continue

            right_obj = RightObject(object_name=obj_name_elem.text)

            # Права
            right_elems = self._find_all(obj, ".//roles:right")
            if not right_elems:
                right_elems = obj.findall("right")

            for right in right_elems:
                right_name_elems = self._find_all(right, ".//roles:name")
                right_name_elem = right_name_elems[0] if right_name_elems else right.find("name")

                right_value_elems = self._find_all(right, ".//roles:value")
                right_value_elem = right_value_elems[0] if right_value_elems else right.find("value")

                if right_name_elem is not None and right_value_elem is not None:
                    right_name = right_name_elem.text or ""
                    right_value = right_value_elem.text == "true"
                    right_obj.rights[right_name] = right_value

            if right_obj.rights:
                parsed.objects.append(right_obj)

        return parsed

    # =========================================================================
    # METADATA PARSING
    # =========================================================================

    def parse_metadata_xml(self, xml_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Универсальный парсинг метаданных из XML

        Args:
            xml_path: Путь к XML файлу метаданных

        Returns:
            Словарь с извлечёнными данными
        """
        root = self.parse_xml(xml_path)
        if root is None:
            return {"error": "Failed to parse XML"}

        path = Path(xml_path)
        result = {
            "path": str(path),
            "type": self.detect_document_type(path).value,
            "root_tag": root.tag.split("}")[-1] if "}" in root.tag else root.tag,
        }

        # Properties
        props_elems = self._find_all(root, ".//mdclass:Properties")
        if not props_elems:
            props = root.find(".//Properties")
        else:
            props = props_elems[0]
        if props is not None:
            result["properties"] = {}
            for prop in props:
                tag = prop.tag.split("}")[-1] if "}" in prop.tag else prop.tag
                if prop.text:
                    result["properties"][tag] = prop.text
                elif len(prop) > 0:
                    # Составное свойство (например Synonym)
                    content_elems = self._find_all(prop, ".//v8:content")
                    if content_elems and content_elems[0].text:
                        result["properties"][tag] = content_elems[0].text

        # UUID
        for child in root:
            uuid = child.get("uuid")
            if uuid:
                result["uuid"] = uuid
                break

        return result

    # =========================================================================
    # SUBSYSTEM PARSING
    # =========================================================================

    def parse_subsystem(self, xml_path: Union[str, Path]) -> Optional[SubsystemInfo]:
        """Парсинг подсистемы"""
        root = self.parse_xml(xml_path)
        if root is None:
            return None

        path = Path(xml_path)

        # Имя подсистемы
        name = path.stem
        if name.endswith(".xml"):
            name = name[:-4]

        subsystem = SubsystemInfo(name=name)

        # Синоним
        synonym_elems = self._find_all(root, ".//v8:content")
        if synonym_elems and synonym_elems[0].text:
            subsystem.synonym = synonym_elems[0].text

        # Содержимое (объекты метаданных)
        content_elems = self._find_all(root, ".//mdclass:Content")
        if not content_elems:
            # Fallback без namespace
            content_elems = root.findall(".//Content")
        if content_elems:
            for item in content_elems[0]:
                if item.text:
                    subsystem.content.append(item.text)

        return subsystem

    # =========================================================================
    # PROJECT-LEVEL OPERATIONS
    # =========================================================================

    def get_all_forms(self, base_path: Optional[Union[str, Path]] = None) -> List[Path]:
        """Получение списка всех Form.xml в проекте"""
        search_path = Path(base_path) if base_path else self.project_path
        if not search_path:
            return []

        return list(search_path.rglob("**/Forms/**/Ext/Form.xml"))

    def get_all_rights(self, base_path: Optional[Union[str, Path]] = None) -> List[Path]:
        """Получение списка всех Rights.xml в проекте"""
        search_path = Path(base_path) if base_path else self.project_path
        if not search_path:
            return []

        return list(search_path.rglob("**/Roles/**/Ext/Rights.xml"))

    def extract_for_rag(self, xml_path: Union[str, Path]) -> Dict[str, Any]:
        """
        Извлечение данных из XML для RAG индексации

        Args:
            xml_path: Путь к XML файлу

        Returns:
            Словарь с данными для индексации
        """
        path = Path(xml_path)
        doc_type = self.detect_document_type(path)

        result = {
            "path": str(path),
            "doc_type": f"xml-{doc_type.value}",
            "tags": [doc_type.value, "xml", "1c-edt"],
        }

        if doc_type == XMLDocType.FORM:
            parsed = self.parse_form(path)
            if parsed:
                result["title"] = f"Форма: {parsed.form_name}"
                result["content"] = parsed.get_summary()
                result["metadata"] = parsed.to_dict()
                result["tags"].extend(["form", "ui"])

        elif doc_type == XMLDocType.RIGHTS:
            parsed = self.parse_rights(path)
            if parsed:
                result["title"] = f"Права: {parsed.role_name}"
                result["content"] = f"Роль {parsed.role_name}, объектов: {len(parsed.objects)}"
                result["metadata"] = parsed.to_dict()
                result["tags"].extend(["rights", "security", "role"])

        elif doc_type == XMLDocType.SUBSYSTEM:
            parsed = self.parse_subsystem(path)
            if parsed:
                result["title"] = f"Подсистема: {parsed.name}"
                result["content"] = f"{parsed.synonym or parsed.name}, объектов: {len(parsed.content)}"
                result["tags"].extend(["subsystem", "navigation"])

        else:
            # Универсальный парсинг
            parsed = self.parse_metadata_xml(path)
            result["title"] = f"Метаданные: {path.stem}"
            result["content"] = json.dumps(parsed.get("properties", {}), ensure_ascii=False)
            result["metadata"] = parsed

        return result


# =============================================================================
# SAFE XML EDITOR
# =============================================================================

class EDTXMLEditor:
    """
    Безопасный редактор XML для 1C EDT

    Сохраняет структуру, форматирование и namespaces при редактировании.
    """

    def __init__(self):
        self.parser = EDTXMLParser()
        self._backup_enabled = True

    def _create_backup(self, xml_path: Path) -> Path:
        """Создание резервной копии"""
        backup_path = xml_path.with_suffix(f".xml.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        import shutil
        shutil.copy2(xml_path, backup_path)
        return backup_path

    def update_element_property(
        self,
        xml_path: Union[str, Path],
        element_name: str,
        property_name: str,
        new_value: str
    ) -> bool:
        """
        Обновление свойства элемента

        Args:
            xml_path: Путь к XML
            element_name: Имя элемента (атрибут name)
            property_name: Имя свойства
            new_value: Новое значение

        Returns:
            True если успешно
        """
        path = Path(xml_path)

        if self._backup_enabled:
            self._create_backup(path)

        try:
            if LXML_AVAILABLE:
                tree = etree.parse(str(path))
                root = tree.getroot()

                # Ищем элемент по name
                elements = root.xpath(f"//*[@name='{element_name}']")
                if not elements:
                    log_stderr(f"[ERROR] Element '{element_name}' not found")
                    return False

                elem = elements[0]

                # Ищем или создаём свойство
                prop = elem.find(property_name)
                if prop is None:
                    prop = etree.SubElement(elem, property_name)

                prop.text = new_value

                # Сохраняем с сохранением форматирования
                tree.write(
                    str(path),
                    encoding="UTF-8",
                    xml_declaration=True,
                    pretty_print=True
                )
                return True
            else:
                log_stderr("[ERROR] lxml required for XML editing")
                return False

        except Exception as e:
            log_stderr(f"[ERROR] Failed to update XML: {e}")
            return False

    def add_form_event(
        self,
        form_path: Union[str, Path],
        event_name: str,
        handler_name: str
    ) -> bool:
        """
        Добавление обработчика события на форму

        Args:
            form_path: Путь к Form.xml
            event_name: Имя события (OnCreateAtServer, etc.)
            handler_name: Имя процедуры-обработчика

        Returns:
            True если успешно
        """
        path = Path(form_path)

        if self._backup_enabled:
            self._create_backup(path)

        try:
            if LXML_AVAILABLE:
                tree = etree.parse(str(path))
                root = tree.getroot()
                ns = V8_NAMESPACES

                # Ищем или создаём блок Events
                events = root.find("Events")
                if events is None:
                    events = root.find("{%s}Events" % ns.get("form", ""))
                if events is None:
                    events = etree.SubElement(root, "Events")

                # Добавляем событие
                event = etree.SubElement(events, "Event")
                event.set("name", event_name)
                event.text = handler_name

                tree.write(str(path), encoding="UTF-8", xml_declaration=True)
                return True
            else:
                log_stderr("[ERROR] lxml required for XML editing")
                return False

        except Exception as e:
            log_stderr(f"[ERROR] Failed to add event: {e}")
            return False


# =============================================================================
# MDCLASSES INTEGRATION (Java)
# =============================================================================

class MDClassesIntegration:
    """
    Интеграция с mdclasses (Java библиотека от 1c-syntax)

    Для сложных операций с метаданными, где Python-парсер недостаточен.
    """

    def __init__(self, mdclasses_jar: Optional[str] = None):
        """
        Args:
            mdclasses_jar: Путь к JAR файлу mdclasses
        """
        self.jar_path = mdclasses_jar
        self._java_available = self._check_java()

    def _check_java(self) -> bool:
        """Проверка доступности Java"""
        try:
            result = subprocess.run(
                ["java", "-version"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    @property
    def is_available(self) -> bool:
        return self._java_available and self.jar_path and Path(self.jar_path).exists()

    def parse_configuration(self, config_path: str) -> Optional[Dict]:
        """
        Парсинг конфигурации через mdclasses

        Args:
            config_path: Путь к директории конфигурации

        Returns:
            Структура метаданных или None
        """
        if not self.is_available:
            log_stderr("[WARNING] mdclasses not available")
            return None

        # TODO: Реализовать вызов mdclasses через subprocess
        # Требует специального CLI wrapper
        log_stderr("[INFO] mdclasses integration planned for future release")
        return None


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "EDTXMLParser",
    "EDTXMLEditor",
    "MDClassesIntegration",
    "V8_NAMESPACES",
    "XMLDocType",
    "ParsedForm",
    "ParsedRights",
    "SubsystemInfo",
    "FormElement",
    "FormAttribute",
    "FormCommand",
]


# =============================================================================
# CLI / TEST
# =============================================================================

if __name__ == "__main__":
    print("EDT XML Parser v1.0.0")
    print(f"lxml available: {LXML_AVAILABLE}")
    print(f"Namespaces registered: {len(V8_NAMESPACES)}")

    # Тест
    if len(sys.argv) > 1:
        test_path = sys.argv[1]
        parser = EDTXMLParser()

        doc_type = parser.detect_document_type(test_path)
        print(f"\nDocument type: {doc_type.value}")

        if doc_type == XMLDocType.FORM:
            result = parser.parse_form(test_path)
            if result:
                print(f"Form: {result.form_name}")
                print(f"Elements: {len(result.elements)}")
                print(f"Events: {result.events}")
        else:
            result = parser.extract_for_rag(test_path)
            print(json.dumps(result, ensure_ascii=False, indent=2))
