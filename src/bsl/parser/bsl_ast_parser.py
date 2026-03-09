"""
BSL AST Parser — Phase 59

Regex-based parser for 1C:Enterprise BSL code.
Extracts procedures, functions, variables, calls, regions, comments.

Supports both English and Russian BSL keywords.
"""

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Tuple

from .models import (
    BSLCall,
    BSLModule,
    BSLParam,
    BSLRegion,
    BSLSymbol,
    BSLVariable,
    CompilationDirective,
    ModuleType,
    SymbolType,
)

# --- Regex patterns ---

# Procedure/Function declaration (both languages)
_SYMBOL_RE = re.compile(
    r"^[ \t]*(?:(?P<directive>&\w+)\s*\n)?[ \t]*"
    r"(?P<type>Procedure|Function|Процедура|Функция)\s+"
    r"(?P<name>[а-яА-ЯёЁa-zA-Z_]\w*)\s*"
    r"\((?P<params>[^)]*)\)"
    r"(?:\s+(?P<export>Export|Экспорт))?",
    re.MULTILINE | re.IGNORECASE,
)

# End of procedure/function
_END_RE = re.compile(
    r"^[ \t]*(?:EndProcedure|EndFunction|КонецПроцедуры|КонецФункции)",
    re.MULTILINE | re.IGNORECASE,
)

# Compilation directive on separate line
_DIRECTIVE_RE = re.compile(
    r"^[ \t]*(&(?:AtServer|AtClient|AtServerNoContext|AtClientAtServerNoContext|AtClientAtServer"
    r"|НаСервере|НаКлиенте|НаСервереБезКонтекста|НаКлиентеНаСервереБезКонтекста|НаКлиентеНаСервере))\s*$",
    re.MULTILINE | re.IGNORECASE,
)

# Module-level variable
_VAR_RE = re.compile(
    r"^[ \t]*(?:Var|Перем)\s+(?P<name>[а-яА-ЯёЁa-zA-Z_]\w*)"
    r"(?:\s+(?P<export>Export|Экспорт))?",
    re.MULTILINE | re.IGNORECASE,
)

# Region markers
_REGION_START_RE = re.compile(
    r"^[ \t]*#(?:Region|Область)\s+(?P<name>.+?)$",
    re.MULTILINE | re.IGNORECASE,
)
_REGION_END_RE = re.compile(
    r"^[ \t]*#(?:EndRegion|КонецОбласти)",
    re.MULTILINE | re.IGNORECASE,
)

# Method calls: ModuleName.MethodName(
_QUALIFIED_CALL_RE = re.compile(
    r"(?P<module>[а-яА-ЯёЁa-zA-Z_]\w*)\.(?P<method>[а-яА-ЯёЁa-zA-Z_]\w*)\s*\(",
)

# Comment line
_COMMENT_RE = re.compile(r"^[ \t]*//(.*)$", re.MULTILINE)

# File encodings to try
_ENCODINGS = ["utf-8-sig", "utf-8", "cp1251", "cp866"]


class BSLASTParser:
    """Regex-based BSL parser for symbol extraction."""

    def __init__(self) -> None:
        self._cache: Dict[str, BSLModule] = {}

    def parse_file(self, file_path: str) -> BSLModule:
        """Parse a BSL file and return structured module data."""
        norm_path = os.path.normpath(file_path)

        if norm_path in self._cache:
            return self._cache[norm_path]

        content = self._read_file(norm_path)
        if content is None:
            return BSLModule(file_path=norm_path, module_type=ModuleType.UNKNOWN)

        module = self.parse_content(content, norm_path)
        self._cache[norm_path] = module
        return module

    def parse_content(self, content: str, file_path: str = "<string>") -> BSLModule:
        """Parse BSL source code string."""
        lines = content.split("\n")
        module = BSLModule(
            file_path=file_path,
            module_type=ModuleType.from_path(file_path),
            raw_content=content,
            line_count=len(lines),
        )

        module.regions = self._extract_regions(content)
        module.variables = self._extract_variables(content)
        module.symbols = self._extract_symbols(content, lines, module.regions)

        return module

    def parse_files(self, file_paths: List[str]) -> List[BSLModule]:
        """Parse multiple BSL files."""
        return [self.parse_file(fp) for fp in file_paths]

    def clear_cache(self) -> None:
        self._cache.clear()

    # --- Private methods ---

    def _read_file(self, file_path: str) -> Optional[str]:
        """Read file with encoding detection."""
        if not os.path.exists(file_path):
            return None
        for enc in _ENCODINGS:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        return None

    def _extract_regions(self, content: str) -> List[BSLRegion]:
        """Extract #Region/#EndRegion blocks."""
        regions: List[BSLRegion] = []
        stack: List[Tuple[str, int]] = []

        for m in _REGION_START_RE.finditer(content):
            line = content[:m.start()].count("\n") + 1
            stack.append((m.group("name").strip(), line))

        end_lines = []
        for m in _REGION_END_RE.finditer(content):
            end_lines.append(content[:m.start()].count("\n") + 1)

        for i, (name, start_line) in enumerate(stack):
            end_line = end_lines[i] if i < len(end_lines) else start_line
            regions.append(BSLRegion(name=name, line_start=start_line, line_end=end_line))

        return regions

    def _extract_variables(self, content: str) -> List[BSLVariable]:
        """Extract module-level Var declarations."""
        variables: List[BSLVariable] = []
        first_symbol = _SYMBOL_RE.search(content)
        search_area = content[:first_symbol.start()] if first_symbol else content

        for m in _VAR_RE.finditer(search_area):
            line = content[:m.start()].count("\n") + 1
            variables.append(BSLVariable(
                name=m.group("name"),
                line=line,
                is_export=bool(m.group("export")),
            ))
        return variables

    def _extract_symbols(
        self, content: str, lines: List[str], regions: List[BSLRegion]
    ) -> List[BSLSymbol]:
        """Extract all procedures and functions with their bodies."""
        symbols: List[BSLSymbol] = []

        # Collect directive positions for lookup
        directives: Dict[int, str] = {}
        for m in _DIRECTIVE_RE.finditer(content):
            line_num = content[:m.start()].count("\n") + 1
            directives[line_num] = m.group(1)

        for m in _SYMBOL_RE.finditer(content):
            start_pos = m.start()
            start_line = content[:start_pos].count("\n") + 1

            type_str = m.group("type").lower()
            symbol_type = (
                SymbolType.PROCEDURE
                if type_str in ("procedure", "процедура")
                else SymbolType.FUNCTION
            )

            # Find matching end
            end_line = start_line
            end_pos = start_pos
            for end_m in _END_RE.finditer(content, m.end()):
                end_pos = end_m.end()
                end_line = content[:end_pos].count("\n") + 1
                break

            body = content[start_pos:end_pos]
            params = self._parse_params(m.group("params") or "")

            # Get compilation directive
            directive_str = m.group("directive") or ""
            if not directive_str:
                directive_str = directives.get(start_line - 1, "")
            directive = CompilationDirective.from_string(directive_str)

            comment = self._extract_preceding_comment(lines, start_line - 1)
            region = self._find_region(start_line, regions)
            calls = self._extract_calls(body, m.group("name"), start_line)

            symbols.append(BSLSymbol(
                name=m.group("name"),
                symbol_type=symbol_type,
                line_start=start_line,
                line_end=end_line,
                body=body,
                is_export=bool(m.group("export")),
                params=params,
                compilation_directive=directive,
                comment=comment,
                region=region,
                calls=calls,
            ))

        return symbols

    def _parse_params(self, params_str: str) -> List[BSLParam]:
        """Parse parameter list string into BSLParam objects."""
        params: List[BSLParam] = []
        if not params_str.strip():
            return params

        for part in params_str.split(","):
            part = part.strip()
            if not part:
                continue

            by_val = False
            default_value = None

            if "=" in part:
                part, default_value = part.split("=", 1)
                part = part.strip()
                default_value = default_value.strip()

            if part.lower().startswith(("val ", "знач ")):
                by_val = True
                part = part.split(None, 1)[1] if " " in part else part

            name = part.strip()
            if name:
                params.append(BSLParam(name=name, by_val=by_val, default_value=default_value))

        return params

    def _extract_preceding_comment(self, lines: List[str], symbol_line_0based: int) -> str:
        """Extract // comment block immediately before a symbol."""
        comment_lines: List[str] = []
        i = symbol_line_0based - 1

        # Skip directive line
        while i >= 0 and lines[i].strip().startswith("&"):
            i -= 1

        while i >= 0:
            stripped = lines[i].strip()
            if stripped.startswith("//"):
                comment_lines.insert(0, stripped[2:].strip())
                i -= 1
            else:
                break

        return "\n".join(comment_lines)

    def _find_region(self, line: int, regions: List[BSLRegion]) -> Optional[str]:
        """Find which region a line belongs to."""
        for region in regions:
            if region.line_start <= line <= region.line_end:
                return region.name
        return None

    def _extract_calls(self, body: str, caller_name: str, base_line: int) -> List[BSLCall]:
        """Extract method calls from a symbol body."""
        calls: List[BSLCall] = []
        seen = set()

        for m in _QUALIFIED_CALL_RE.finditer(body):
            module = m.group("module")
            method = m.group("method")
            key = f"{module}.{method}"
            if key not in seen:
                seen.add(key)
                rel_line = body[:m.start()].count("\n")
                calls.append(BSLCall(
                    caller_name=caller_name,
                    callee_module=module,
                    callee_method=method,
                    line=base_line + rel_line,
                ))

        return calls

    @staticmethod
    def find_bsl_files(root_dir: str) -> List[str]:
        """Find all .bsl files under a directory."""
        bsl_files: List[str] = []
        for dirpath, _, filenames in os.walk(root_dir):
            for fn in filenames:
                if fn.lower().endswith(".bsl"):
                    bsl_files.append(os.path.join(dirpath, fn))
        return bsl_files
