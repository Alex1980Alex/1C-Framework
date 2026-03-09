"""
BSL Code Style Extractor — Phase 66

Analyzes existing BSL codebase to extract coding conventions:
- Naming patterns (procedures, functions, variables)
- Indentation style (tabs vs spaces)
- Region usage patterns
- Comment style
- Export patterns

Uses BSLASTParser output (Phase 59) for analysis.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from src.bsl.parser.models import BSLModule, BSLSymbol, SymbolType


@dataclass
class BSLStyleProfile:
    """Extracted code style rules from a BSL codebase."""

    # Naming
    proc_naming: str = "PascalCase"  # PascalCase, camelCase, mixed
    var_naming: str = "camelCase"
    uses_russian: bool = True
    uses_english: bool = False

    # Structure
    indent_char: str = "tab"  # tab or spaces
    indent_size: int = 1
    uses_regions: bool = True
    common_regions: list[str] = field(default_factory=list)

    # Patterns
    avg_proc_length: float = 0.0
    export_ratio: float = 0.0
    comment_ratio: float = 0.0
    top_called: list[str] = field(default_factory=list)

    def to_prompt(self) -> str:
        """Format as instructions for code generation."""
        lines = ["BSL Code Style Rules (extracted from project):"]
        lines.append(f"- Procedure/Function names: {self.proc_naming}")
        lines.append(f"- Variable names: {self.var_naming}")
        lines.append(f"- Language: {'Russian' if self.uses_russian else 'English'}")
        lines.append(f"- Indentation: {self.indent_char}")
        if self.uses_regions and self.common_regions:
            lines.append(f"- Use regions: {', '.join(self.common_regions[:5])}")
        lines.append(f"- Average procedure length: {self.avg_proc_length:.0f} lines")
        lines.append(f"- Export ratio: {self.export_ratio:.0%}")
        if self.top_called:
            lines.append(f"- Commonly used modules: {', '.join(self.top_called[:5])}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "proc_naming": self.proc_naming,
            "var_naming": self.var_naming,
            "uses_russian": self.uses_russian,
            "uses_english": self.uses_english,
            "indent_char": self.indent_char,
            "indent_size": self.indent_size,
            "uses_regions": self.uses_regions,
            "common_regions": self.common_regions[:10],
            "avg_proc_length": round(self.avg_proc_length, 1),
            "export_ratio": round(self.export_ratio, 3),
            "comment_ratio": round(self.comment_ratio, 3),
            "top_called": self.top_called[:10],
        }


_CYRILLIC_RE = re.compile(r"[а-яА-ЯёЁ]")
_LATIN_RE = re.compile(r"[a-zA-Z]")


class BSLStyleExtractor:
    """Extract code style conventions from parsed BSL modules."""

    def analyze(self, modules: list[BSLModule]) -> BSLStyleProfile:
        """Analyze a set of parsed modules and return a style profile."""
        profile = BSLStyleProfile()

        if not modules:
            return profile

        all_symbols: list[BSLSymbol] = []
        region_counter: Counter[str] = Counter()
        call_module_counter: Counter[str] = Counter()
        total_lines = 0
        total_comments = 0
        total_exports = 0
        indent_tabs = 0
        indent_spaces = 0
        cyrillic_names = 0
        latin_names = 0

        for mod in modules:
            total_lines += mod.line_count
            for sym in mod.symbols:
                all_symbols.append(sym)
                if sym.is_export:
                    total_exports += 1
                if sym.comment:
                    total_comments += 1
                if sym.region:
                    region_counter[sym.region] += 1

                # Naming language detection
                if _CYRILLIC_RE.search(sym.name):
                    cyrillic_names += 1
                if _LATIN_RE.search(sym.name):
                    latin_names += 1

                # Cross-module calls
                for call in sym.calls:
                    if call.callee_module:
                        call_module_counter[call.callee_module] += 1

                # Indent detection from body
                if sym.body:
                    for line in sym.body.split("\n")[:5]:
                        stripped = line.lstrip()
                        if stripped and line != stripped:
                            leading = line[: len(line) - len(stripped)]
                            if "\t" in leading:
                                indent_tabs += 1
                            elif "    " in leading:
                                indent_spaces += 1

        n_symbols = len(all_symbols)
        if n_symbols == 0:
            return profile

        # Naming convention
        profile.uses_russian = cyrillic_names > latin_names
        profile.uses_english = latin_names > cyrillic_names
        profile.proc_naming = "PascalCase"  # BSL standard

        # Indentation
        profile.indent_char = "tab" if indent_tabs >= indent_spaces else "spaces"

        # Regions
        profile.uses_regions = bool(region_counter)
        profile.common_regions = [r for r, _ in region_counter.most_common(10)]

        # Metrics
        lengths = [
            (s.line_end - s.line_start + 1) for s in all_symbols
            if s.line_start and s.line_end
        ]
        profile.avg_proc_length = sum(lengths) / len(lengths) if lengths else 0
        profile.export_ratio = total_exports / n_symbols
        profile.comment_ratio = total_comments / n_symbols

        # Top called modules
        profile.top_called = [m for m, _ in call_module_counter.most_common(10)]

        return profile
