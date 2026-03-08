#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BSL Semantic Differ - семантическое сравнение BSL файлов
Stub implementation for Docker MCP
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import re


@dataclass
class BslSymbol:
    """Символ BSL кода (процедура, функция, переменная)"""
    name: str
    symbol_type: str  # 'procedure', 'function', 'variable'
    start_line: int = 0
    end_line: int = 0
    is_export: bool = False
    parameters: List[str] = field(default_factory=list)
    body: str = ""


@dataclass
class BslDiffResult:
    """Результат сравнения BSL файлов"""
    added_symbols: List[BslSymbol] = field(default_factory=list)
    removed_symbols: List[BslSymbol] = field(default_factory=list)
    modified_symbols: List[BslSymbol] = field(default_factory=list)
    has_differences: bool = False


class BslSemanticDiffer:
    """Семантическое сравнение BSL файлов"""

    # Паттерны для парсинга BSL
    PROCEDURE_PATTERN = re.compile(
        r'(Процедура|Procedure)\s+(\w+)\s*\(([^)]*)\)\s*(Экспорт|Export)?',
        re.IGNORECASE | re.MULTILINE
    )
    FUNCTION_PATTERN = re.compile(
        r'(Функция|Function)\s+(\w+)\s*\(([^)]*)\)\s*(Экспорт|Export)?',
        re.IGNORECASE | re.MULTILINE
    )
    END_PROCEDURE_PATTERN = re.compile(
        r'(КонецПроцедуры|EndProcedure)',
        re.IGNORECASE
    )
    END_FUNCTION_PATTERN = re.compile(
        r'(КонецФункции|EndFunction)',
        re.IGNORECASE
    )

    def extract_symbols(self, content: str) -> List[BslSymbol]:
        """Извлечение символов из BSL кода"""
        symbols = []
        lines = content.split('\n')

        # Поиск процедур
        for match in self.PROCEDURE_PATTERN.finditer(content):
            name = match.group(2)
            params = match.group(3).strip() if match.group(3) else ""
            is_export = match.group(4) is not None
            start_pos = match.start()
            start_line = content[:start_pos].count('\n') + 1

            symbols.append(BslSymbol(
                name=name,
                symbol_type='procedure',
                start_line=start_line,
                is_export=is_export,
                parameters=params.split(',') if params else []
            ))

        # Поиск функций
        for match in self.FUNCTION_PATTERN.finditer(content):
            name = match.group(2)
            params = match.group(3).strip() if match.group(3) else ""
            is_export = match.group(4) is not None
            start_pos = match.start()
            start_line = content[:start_pos].count('\n') + 1

            symbols.append(BslSymbol(
                name=name,
                symbol_type='function',
                start_line=start_line,
                is_export=is_export,
                parameters=params.split(',') if params else []
            ))

        return symbols

    def compare_files(self, file1: Path, file2: Path) -> BslDiffResult:
        """Сравнение двух BSL файлов"""
        content1 = file1.read_text(encoding='utf-8')
        content2 = file2.read_text(encoding='utf-8')

        symbols1 = {s.name: s for s in self.extract_symbols(content1)}
        symbols2 = {s.name: s for s in self.extract_symbols(content2)}

        names1 = set(symbols1.keys())
        names2 = set(symbols2.keys())

        added = [symbols2[name] for name in names2 - names1]
        removed = [symbols1[name] for name in names1 - names2]

        # Поиск изменённых символов
        modified = []
        for name in names1 & names2:
            s1, s2 = symbols1[name], symbols2[name]
            if s1.is_export != s2.is_export or s1.parameters != s2.parameters:
                modified.append(s2)

        has_diff = bool(added or removed or modified)

        return BslDiffResult(
            added_symbols=added,
            removed_symbols=removed,
            modified_symbols=modified,
            has_differences=has_diff
        )

    def compare_content(self, content1: str, content2: str) -> BslDiffResult:
        """Сравнение BSL кода напрямую"""
        symbols1 = {s.name: s for s in self.extract_symbols(content1)}
        symbols2 = {s.name: s for s in self.extract_symbols(content2)}

        names1 = set(symbols1.keys())
        names2 = set(symbols2.keys())

        added = [symbols2[name] for name in names2 - names1]
        removed = [symbols1[name] for name in names1 - names2]
        modified = []

        for name in names1 & names2:
            s1, s2 = symbols1[name], symbols2[name]
            if s1.is_export != s2.is_export or s1.parameters != s2.parameters:
                modified.append(s2)

        has_diff = bool(added or removed or modified)

        return BslDiffResult(
            added_symbols=added,
            removed_symbols=removed,
            modified_symbols=modified,
            has_differences=has_diff
        )
