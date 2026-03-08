#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BSL Deep Analyzer - глубокий семантический анализ BSL кода
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
import re
from collections import Counter


@dataclass
class ComplexityMetrics:
    """Метрики сложности кода"""
    cyclomatic_complexity: int = 1  # Цикломатическая сложность
    cognitive_complexity: int = 0    # Когнитивная сложность
    nesting_depth: int = 0           # Максимальная глубина вложенности
    lines_of_code: int = 0           # Строки кода
    comment_lines: int = 0           # Строки комментариев
    blank_lines: int = 0             # Пустые строки


@dataclass
class VariableInfo:
    """Информация о переменной"""
    name: str
    line_declared: int = 0
    usage_count: int = 0
    is_parameter: bool = False


@dataclass
class FunctionAnalysis:
    """Результат анализа функции/процедуры"""
    name: str
    function_type: str  # 'function' or 'procedure'
    start_line: int
    end_line: int
    line_count: int
    is_export: bool
    parameters: List[str] = field(default_factory=list)
    variables: List[VariableInfo] = field(default_factory=list)
    complexity_metrics: ComplexityMetrics = field(default_factory=ComplexityMetrics)
    called_functions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class BslDeepAnalyzer:
    """Глубокий анализатор BSL кода"""

    # Паттерны для анализа
    FUNCTION_START = re.compile(
        r'^[ \t]*(Функция|Function)\s+(\w+)\s*\(([^)]*)\)\s*(Экспорт|Export)?',
        re.IGNORECASE | re.MULTILINE
    )
    PROCEDURE_START = re.compile(
        r'^[ \t]*(Процедура|Procedure)\s+(\w+)\s*\(([^)]*)\)\s*(Экспорт|Export)?',
        re.IGNORECASE | re.MULTILINE
    )
    FUNCTION_END = re.compile(r'^[ \t]*(КонецФункции|EndFunction)', re.IGNORECASE | re.MULTILINE)
    PROCEDURE_END = re.compile(r'^[ \t]*(КонецПроцедуры|EndProcedure)', re.IGNORECASE | re.MULTILINE)

    # Паттерны для сложности
    IF_PATTERN = re.compile(r'\b(Если|If)\b', re.IGNORECASE)
    ELSEIF_PATTERN = re.compile(r'\b(ИначеЕсли|ElsIf)\b', re.IGNORECASE)
    ELSE_PATTERN = re.compile(r'\b(Иначе|Else)\b', re.IGNORECASE)
    FOR_PATTERN = re.compile(r'\b(Для|For)\b', re.IGNORECASE)
    WHILE_PATTERN = re.compile(r'\b(Пока|While)\b', re.IGNORECASE)
    TRY_PATTERN = re.compile(r'\b(Попытка|Try)\b', re.IGNORECASE)
    AND_OR_PATTERN = re.compile(r'\b(И|И|And|Or|Или)\b', re.IGNORECASE)

    # Паттерны для переменных
    VAR_DECLARATION = re.compile(r'\b(Перем|Var)\s+(\w+)', re.IGNORECASE)
    ASSIGNMENT = re.compile(r'(\w+)\s*=\s*[^=]')
    FUNCTION_CALL = re.compile(r'(\w+)\s*\(')

    # Комментарии
    COMMENT_LINE = re.compile(r'^\s*//')
    COMMENT_INLINE = re.compile(r'//.*$')

    def analyze_file_deep(self, file_path: Path) -> Dict[str, FunctionAnalysis]:
        """
        Глубокий анализ BSL файла

        Returns:
            Словарь {имя_функции: FunctionAnalysis}
        """
        content = file_path.read_text(encoding='utf-8')
        return self.analyze_content(content)

    def analyze_content(self, content: str) -> Dict[str, FunctionAnalysis]:
        """Анализ содержимого BSL кода"""
        results = {}
        lines = content.split('\n')

        # Находим все функции и процедуры
        functions = self._extract_functions(content, lines)

        for func_name, func_data in functions.items():
            analysis = self._analyze_function(func_data, lines)
            results[func_name] = analysis

        return results

    def _extract_functions(self, content: str, lines: List[str]) -> Dict[str, dict]:
        """Извлечение функций и процедур из кода"""
        functions = {}

        # Поиск функций
        for match in self.FUNCTION_START.finditer(content):
            start_pos = match.start()
            start_line = content[:start_pos].count('\n') + 1
            name = match.group(2)
            params = match.group(3).strip() if match.group(3) else ""
            is_export = match.group(4) is not None

            # Найти конец функции
            end_line = self._find_function_end(lines, start_line - 1, 'function')

            functions[name] = {
                'name': name,
                'type': 'function',
                'start_line': start_line,
                'end_line': end_line,
                'params': params,
                'is_export': is_export,
                'body': '\n'.join(lines[start_line - 1:end_line])
            }

        # Поиск процедур
        for match in self.PROCEDURE_START.finditer(content):
            start_pos = match.start()
            start_line = content[:start_pos].count('\n') + 1
            name = match.group(2)
            params = match.group(3).strip() if match.group(3) else ""
            is_export = match.group(4) is not None

            end_line = self._find_function_end(lines, start_line - 1, 'procedure')

            functions[name] = {
                'name': name,
                'type': 'procedure',
                'start_line': start_line,
                'end_line': end_line,
                'params': params,
                'is_export': is_export,
                'body': '\n'.join(lines[start_line - 1:end_line])
            }

        return functions

    def _find_function_end(self, lines: List[str], start_idx: int, func_type: str) -> int:
        """Поиск конца функции/процедуры"""
        end_pattern = self.FUNCTION_END if func_type == 'function' else self.PROCEDURE_END

        for i in range(start_idx + 1, len(lines)):
            if end_pattern.search(lines[i]):
                return i + 1

        return len(lines)

    def _analyze_function(self, func_data: dict, lines: List[str]) -> FunctionAnalysis:
        """Детальный анализ функции"""
        body = func_data['body']
        body_lines = body.split('\n')

        analysis = FunctionAnalysis(
            name=func_data['name'],
            function_type=func_data['type'],
            start_line=func_data['start_line'],
            end_line=func_data['end_line'],
            line_count=func_data['end_line'] - func_data['start_line'] + 1,
            is_export=func_data['is_export'],
            parameters=self._parse_parameters(func_data['params'])
        )

        # Анализ сложности
        analysis.complexity_metrics = self._calculate_complexity(body_lines)

        # Анализ переменных
        analysis.variables = self._analyze_variables(body, analysis.parameters)

        # Поиск вызываемых функций
        analysis.called_functions = self._find_called_functions(body)

        # Генерация предупреждений
        analysis.warnings = self._generate_warnings(analysis)

        return analysis

    def _parse_parameters(self, params_str: str) -> List[str]:
        """Парсинг параметров функции"""
        if not params_str.strip():
            return []

        params = []
        for param in params_str.split(','):
            param = param.strip()
            # Убираем значение по умолчанию и ключевое слово Знач
            param = re.sub(r'\s*=\s*.*$', '', param)
            param = re.sub(r'^\s*(Знач|Val)\s+', '', param, flags=re.IGNORECASE)
            if param:
                params.append(param)

        return params

    def _calculate_complexity(self, lines: List[str]) -> ComplexityMetrics:
        """Расчёт метрик сложности"""
        metrics = ComplexityMetrics()

        current_nesting = 0
        max_nesting = 0

        for line in lines:
            stripped = line.strip()

            # Подсчёт типов строк
            if not stripped:
                metrics.blank_lines += 1
            elif self.COMMENT_LINE.match(stripped):
                metrics.comment_lines += 1
            else:
                metrics.lines_of_code += 1

            # Цикломатическая сложность
            if self.IF_PATTERN.search(line):
                metrics.cyclomatic_complexity += 1
                current_nesting += 1
            if self.ELSEIF_PATTERN.search(line):
                metrics.cyclomatic_complexity += 1
            if self.FOR_PATTERN.search(line):
                metrics.cyclomatic_complexity += 1
                current_nesting += 1
            if self.WHILE_PATTERN.search(line):
                metrics.cyclomatic_complexity += 1
                current_nesting += 1
            if self.TRY_PATTERN.search(line):
                metrics.cyclomatic_complexity += 1
                current_nesting += 1

            # Логические операторы
            and_or_count = len(self.AND_OR_PATTERN.findall(line))
            metrics.cyclomatic_complexity += and_or_count

            # Когнитивная сложность (учитывает вложенность)
            if self.IF_PATTERN.search(line) or self.FOR_PATTERN.search(line) or self.WHILE_PATTERN.search(line):
                metrics.cognitive_complexity += 1 + current_nesting

            # Отслеживание вложенности
            max_nesting = max(max_nesting, current_nesting)

            # Уменьшение вложенности на КонецЕсли/КонецЦикла/КонецПопытки
            if re.search(r'\b(КонецЕсли|EndIf|КонецЦикла|EndDo|КонецПопытки|EndTry)\b', line, re.IGNORECASE):
                current_nesting = max(0, current_nesting - 1)

        metrics.nesting_depth = max_nesting
        return metrics

    def _analyze_variables(self, body: str, parameters: List[str]) -> List[VariableInfo]:
        """Анализ переменных в функции"""
        variables = []
        var_usage = Counter()

        # Параметры как переменные
        for param in parameters:
            variables.append(VariableInfo(name=param, is_parameter=True))

        # Явные объявления
        for match in self.VAR_DECLARATION.finditer(body):
            var_name = match.group(2)
            line_num = body[:match.start()].count('\n') + 1
            variables.append(VariableInfo(name=var_name, line_declared=line_num))

        # Присваивания (неявные объявления)
        for match in self.ASSIGNMENT.finditer(body):
            var_name = match.group(1)
            # Пропускаем если это уже известная переменная или параметр
            known = {v.name.lower() for v in variables}
            if var_name.lower() not in known:
                line_num = body[:match.start()].count('\n') + 1
                variables.append(VariableInfo(name=var_name, line_declared=line_num))

        # Подсчёт использований
        words = re.findall(r'\b(\w+)\b', body)
        var_usage.update(w.lower() for w in words)

        for var in variables:
            var.usage_count = var_usage.get(var.name.lower(), 0)

        return variables

    def _find_called_functions(self, body: str) -> List[str]:
        """Поиск вызываемых функций"""
        calls = set()

        for match in self.FUNCTION_CALL.finditer(body):
            func_name = match.group(1)
            # Пропускаем ключевые слова
            keywords = {'Если', 'If', 'Пока', 'While', 'Для', 'For', 'Возврат', 'Return',
                       'Новый', 'New', 'Попытка', 'Try', 'Перем', 'Var'}
            if func_name not in keywords:
                calls.add(func_name)

        return sorted(calls)

    def _generate_warnings(self, analysis: FunctionAnalysis) -> List[str]:
        """Генерация предупреждений о качестве кода"""
        warnings = []

        # Проверка сложности
        if analysis.complexity_metrics.cyclomatic_complexity > 10:
            warnings.append(f"Высокая цикломатическая сложность: {analysis.complexity_metrics.cyclomatic_complexity} (рекомендуется < 10)")

        if analysis.complexity_metrics.cognitive_complexity > 15:
            warnings.append(f"Высокая когнитивная сложность: {analysis.complexity_metrics.cognitive_complexity}")

        if analysis.complexity_metrics.nesting_depth > 4:
            warnings.append(f"Глубокая вложенность: {analysis.complexity_metrics.nesting_depth} уровней")

        # Проверка размера
        if analysis.line_count > 100:
            warnings.append(f"Длинная функция: {analysis.line_count} строк (рекомендуется < 100)")

        # Проверка переменных
        if len(analysis.variables) > 15:
            warnings.append(f"Много переменных: {len(analysis.variables)} (рекомендуется < 15)")

        # Неиспользуемые переменные
        unused = [v.name for v in analysis.variables if v.usage_count <= 1 and not v.is_parameter]
        if unused:
            warnings.append(f"Возможно неиспользуемые переменные: {', '.join(unused[:5])}")

        # Отсутствие комментариев в сложном коде
        if analysis.complexity_metrics.cyclomatic_complexity > 5 and analysis.complexity_metrics.comment_lines == 0:
            warnings.append("Сложный код без комментариев")

        return warnings

    def get_file_summary(self, file_path: Path) -> Dict:
        """Получение краткой сводки по файлу"""
        analysis = self.analyze_file_deep(file_path)

        total_complexity = sum(f.complexity_metrics.cyclomatic_complexity for f in analysis.values())
        total_lines = sum(f.line_count for f in analysis.values())
        total_warnings = sum(len(f.warnings) for f in analysis.values())

        return {
            'file': str(file_path),
            'functions_count': len(analysis),
            'total_lines': total_lines,
            'total_complexity': total_complexity,
            'avg_complexity': total_complexity / len(analysis) if analysis else 0,
            'total_warnings': total_warnings,
            'exported_count': sum(1 for f in analysis.values() if f.is_export),
            'most_complex': max(analysis.values(), key=lambda x: x.complexity_metrics.cyclomatic_complexity).name if analysis else None
        }
