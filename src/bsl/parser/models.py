"""
BSL Data Models — Phase 59

Data classes for BSL symbols, modules, and parsed structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class SymbolType(Enum):
    PROCEDURE = "Procedure"
    FUNCTION = "Function"


class CompilationDirective(Enum):
    AT_SERVER = "&AtServer"
    AT_CLIENT = "&AtClient"
    AT_SERVER_NO_CONTEXT = "&AtServerNoContext"
    AT_CLIENT_AT_SERVER_NO_CONTEXT = "&AtClientAtServerNoContext"
    AT_CLIENT_AT_SERVER = "&AtClientAtServer"
    # Russian equivalents
    NA_SERVERE = "&НаСервере"
    NA_KLIENTE = "&НаКлиенте"
    NA_SERVERE_BEZ_KONTEKSTA = "&НаСервереБезКонтекста"
    NA_KLIENTE_NA_SERVERE_BEZ_KONTEKSTA = "&НаКлиентеНаСервереБезКонтекста"
    NA_KLIENTE_NA_SERVERE = "&НаКлиентеНаСервере"
    NONE = ""

    @classmethod
    def from_string(cls, s: str) -> CompilationDirective:
        s = s.strip()
        for member in cls:
            if member.value.lower() == s.lower():
                return member
        return cls.NONE


class ModuleType(Enum):
    COMMON_MODULE = "CommonModule"
    OBJECT_MODULE = "ObjectModule"
    MANAGER_MODULE = "ManagerModule"
    FORM_MODULE = "FormModule"
    COMMAND_MODULE = "CommandModule"
    SESSION_MODULE = "SessionModule"
    EXTERNAL_CONNECTION = "ExternalConnectionModule"
    RECORDSET_MODULE = "RecordSetModule"
    VALUE_MANAGER_MODULE = "ValueManagerModule"
    UNKNOWN = "Unknown"

    @classmethod
    def from_path(cls, file_path: str) -> ModuleType:
        path_lower = file_path.lower().replace("\\", "/")
        mapping = {
            "commonmodules/": cls.COMMON_MODULE,
            "общиемодули/": cls.COMMON_MODULE,
            "/ext/objectmodule": cls.OBJECT_MODULE,
            "/ext/managermodule": cls.MANAGER_MODULE,
            "/ext/module": cls.FORM_MODULE,
            "/forms/": cls.FORM_MODULE,
            "/commands/": cls.COMMAND_MODULE,
            "sessionmodule": cls.SESSION_MODULE,
            "externalconnectionmodule": cls.EXTERNAL_CONNECTION,
            "recordsetmodule": cls.RECORDSET_MODULE,
            "valuemanagermodule": cls.VALUE_MANAGER_MODULE,
        }
        for pattern, mod_type in mapping.items():
            if pattern in path_lower:
                return mod_type
        return cls.UNKNOWN


@dataclass
class BSLParam:
    name: str
    by_val: bool = False
    default_value: Optional[str] = None


@dataclass
class BSLCall:
    caller_name: str
    callee_module: Optional[str]  # None for local calls
    callee_method: str
    line: int


@dataclass
class BSLSymbol:
    name: str
    symbol_type: SymbolType
    line_start: int
    line_end: int
    body: str
    is_export: bool = False
    params: List[BSLParam] = field(default_factory=list)
    compilation_directive: CompilationDirective = CompilationDirective.NONE
    comment: str = ""
    region: Optional[str] = None
    calls: List[BSLCall] = field(default_factory=list)

    @property
    def params_str(self) -> str:
        parts = []
        for p in self.params:
            s = f"Знач {p.name}" if p.by_val else p.name
            if p.default_value is not None:
                s += f" = {p.default_value}"
            parts.append(s)
        return ", ".join(parts)

    @property
    def signature(self) -> str:
        keyword = "Процедура" if self.symbol_type == SymbolType.PROCEDURE else "Функция"
        export = " Экспорт" if self.is_export else ""
        return f"{keyword} {self.name}({self.params_str}){export}"


@dataclass
class BSLVariable:
    name: str
    line: int
    is_export: bool = False


@dataclass
class BSLRegion:
    name: str
    line_start: int
    line_end: int


@dataclass
class BSLModule:
    file_path: str
    module_type: ModuleType
    symbols: List[BSLSymbol] = field(default_factory=list)
    variables: List[BSLVariable] = field(default_factory=list)
    regions: List[BSLRegion] = field(default_factory=list)
    raw_content: str = ""
    line_count: int = 0

    @property
    def procedures(self) -> List[BSLSymbol]:
        return [s for s in self.symbols if s.symbol_type == SymbolType.PROCEDURE]

    @property
    def functions(self) -> List[BSLSymbol]:
        return [s for s in self.symbols if s.symbol_type == SymbolType.FUNCTION]

    @property
    def exports(self) -> List[BSLSymbol]:
        return [s for s in self.symbols if s.is_export]

    @property
    def module_name(self) -> str:
        """Extract module name from file path."""
        import os
        parts = self.file_path.replace("\\", "/").split("/")
        # Try to find meaningful name from path
        for i, part in enumerate(parts):
            if part.lower() in ("commonmodules", "общиемодули") and i + 1 < len(parts):
                return parts[i + 1]
        return os.path.splitext(os.path.basename(self.file_path))[0]
