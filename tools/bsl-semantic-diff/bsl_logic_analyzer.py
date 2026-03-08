#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BSL Logic Analyzer - анализ логического потока BSL кода
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
import re
from enum import Enum


class NodeType(Enum):
    """Типы узлов в графе потока"""
    START = "start"
    END = "end"
    STATEMENT = "statement"
    CONDITION = "condition"
    LOOP = "loop"
    TRY = "try"
    RETURN = "return"
    RAISE = "raise"
    CALL = "call"


@dataclass
class FlowNode:
    """Узел графа потока управления"""
    id: int
    node_type: NodeType
    line_number: int
    code: str = ""
    label: str = ""
    outgoing: List[int] = field(default_factory=list)
    incoming: List[int] = field(default_factory=list)


@dataclass
class ControlFlowGraph:
    """Граф потока управления"""
    function_name: str
    nodes: Dict[int, FlowNode] = field(default_factory=dict)
    start_node: int = 0
    end_nodes: List[int] = field(default_factory=list)


@dataclass
class LogicPath:
    """Путь выполнения в графе"""
    path_id: int
    nodes: List[int]
    conditions: List[str]
    is_exception_path: bool = False


@dataclass
class LogicAnalysisResult:
    """Результат анализа логического потока"""
    function_name: str
    cfg: ControlFlowGraph = None
    paths: List[LogicPath] = field(default_factory=list)
    unreachable_lines: List[int] = field(default_factory=list)
    infinite_loops: List[int] = field(default_factory=list)
    complexity_paths: int = 0
    warnings: List[str] = field(default_factory=list)


class BslLogicAnalyzer:
    """Анализатор логического потока BSL кода"""

    # Паттерны для анализа
    IF_START = re.compile(r'^\s*(Если|If)\s+(.+)\s+(Тогда|Then)', re.IGNORECASE)
    ELSEIF = re.compile(r'^\s*(ИначеЕсли|ElsIf)\s+(.+)\s+(Тогда|Then)', re.IGNORECASE)
    ELSE = re.compile(r'^\s*(Иначе|Else)\s*$', re.IGNORECASE)
    ENDIF = re.compile(r'^\s*(КонецЕсли|EndIf)', re.IGNORECASE)

    FOR_START = re.compile(r'^\s*(Для|For)\s+(.+)\s+(По|To|Каждого|Each)', re.IGNORECASE)
    WHILE_START = re.compile(r'^\s*(Пока|While)\s+(.+)\s+(Цикл|Do)', re.IGNORECASE)
    LOOP_END = re.compile(r'^\s*(КонецЦикла|EndDo)', re.IGNORECASE)
    CONTINUE = re.compile(r'^\s*(Продолжить|Continue)', re.IGNORECASE)
    BREAK = re.compile(r'^\s*(Прервать|Break)', re.IGNORECASE)

    TRY_START = re.compile(r'^\s*(Попытка|Try)', re.IGNORECASE)
    EXCEPT = re.compile(r'^\s*(Исключение|Except)', re.IGNORECASE)
    TRY_END = re.compile(r'^\s*(КонецПопытки|EndTry)', re.IGNORECASE)
    RAISE = re.compile(r'^\s*(ВызватьИсключение|Raise)', re.IGNORECASE)

    RETURN = re.compile(r'^\s*(Возврат|Return)', re.IGNORECASE)

    FUNCTION_START = re.compile(
        r'^\s*(Функция|Function|Процедура|Procedure)\s+(\w+)\s*\(',
        re.IGNORECASE
    )
    FUNCTION_END = re.compile(
        r'^\s*(КонецФункции|EndFunction|КонецПроцедуры|EndProcedure)',
        re.IGNORECASE
    )

    FUNCTION_CALL = re.compile(r'(\w+)\s*\(', re.IGNORECASE)

    def analyze_function_logic(self, content: str, function_name: str = None) -> LogicAnalysisResult:
        """
        Анализ логического потока функции

        Args:
            content: BSL код
            function_name: Имя функции для анализа (None = первая найденная)

        Returns:
            LogicAnalysisResult с графом потока и путями
        """
        lines = content.split('\n')

        # Находим границы функции
        start_line, end_line, func_name = self._find_function_bounds(lines, function_name)

        if start_line is None:
            return LogicAnalysisResult(
                function_name=function_name or "unknown",
                warnings=["Функция не найдена"]
            )

        # Строим граф потока управления
        cfg = self._build_cfg(lines[start_line:end_line], func_name, start_line)

        # Находим все пути выполнения
        paths = self._find_all_paths(cfg)

        # Анализируем проблемы
        unreachable = self._find_unreachable_code(cfg, lines, start_line)
        infinite_loops = self._find_infinite_loops(cfg, lines, start_line)

        # Генерируем предупреждения
        warnings = self._generate_logic_warnings(cfg, paths, unreachable, infinite_loops)

        return LogicAnalysisResult(
            function_name=func_name,
            cfg=cfg,
            paths=paths,
            unreachable_lines=unreachable,
            infinite_loops=infinite_loops,
            complexity_paths=len(paths),
            warnings=warnings
        )

    def _find_function_bounds(
        self, lines: List[str], function_name: str = None
    ) -> Tuple[Optional[int], Optional[int], str]:
        """Поиск границ функции в коде"""
        start_line = None
        func_name = None

        for i, line in enumerate(lines):
            match = self.FUNCTION_START.search(line)
            if match:
                name = match.group(2)
                if function_name is None or name.lower() == function_name.lower():
                    start_line = i
                    func_name = name
                    break

        if start_line is None:
            return None, None, ""

        # Ищем конец функции
        nesting = 1
        for i in range(start_line + 1, len(lines)):
            if self.FUNCTION_START.search(lines[i]):
                nesting += 1
            elif self.FUNCTION_END.search(lines[i]):
                nesting -= 1
                if nesting == 0:
                    return start_line, i + 1, func_name

        return start_line, len(lines), func_name

    def _build_cfg(self, lines: List[str], function_name: str, offset: int) -> ControlFlowGraph:
        """Построение графа потока управления"""
        cfg = ControlFlowGraph(function_name=function_name)
        node_id = 0

        # Стартовый узел
        start_node = FlowNode(
            id=node_id,
            node_type=NodeType.START,
            line_number=offset,
            label="START"
        )
        cfg.nodes[node_id] = start_node
        cfg.start_node = node_id
        node_id += 1

        # Стек для отслеживания структур
        stack = []  # (type, node_id, condition)
        prev_node = 0

        for i, line in enumerate(lines):
            actual_line = offset + i + 1
            stripped = line.strip()

            if not stripped or stripped.startswith('//'):
                continue

            # Пропускаем заголовок и конец функции
            if self.FUNCTION_START.search(line) or self.FUNCTION_END.search(line):
                continue

            node = None

            # Условные операторы
            if self.IF_START.search(line):
                match = self.IF_START.search(line)
                condition = match.group(2) if match else ""
                node = FlowNode(
                    id=node_id,
                    node_type=NodeType.CONDITION,
                    line_number=actual_line,
                    code=stripped,
                    label=f"IF: {condition[:30]}"
                )
                stack.append(('if', node_id, []))

            elif self.ELSEIF.search(line):
                match = self.ELSEIF.search(line)
                condition = match.group(2) if match else ""
                node = FlowNode(
                    id=node_id,
                    node_type=NodeType.CONDITION,
                    line_number=actual_line,
                    code=stripped,
                    label=f"ELSEIF: {condition[:30]}"
                )
                if stack and stack[-1][0] == 'if':
                    stack[-1][2].append(prev_node)

            elif self.ELSE.search(line):
                node = FlowNode(
                    id=node_id,
                    node_type=NodeType.STATEMENT,
                    line_number=actual_line,
                    code=stripped,
                    label="ELSE"
                )
                if stack and stack[-1][0] == 'if':
                    stack[-1][2].append(prev_node)

            elif self.ENDIF.search(line):
                # Соединяем все ветки
                if stack and stack[-1][0] == 'if':
                    _, start_id, branches = stack.pop()
                    branches.append(prev_node)
                    # Создаём узел-соединитель
                    node = FlowNode(
                        id=node_id,
                        node_type=NodeType.STATEMENT,
                        line_number=actual_line,
                        code=stripped,
                        label="ENDIF"
                    )
                    for branch_id in branches:
                        if branch_id in cfg.nodes:
                            cfg.nodes[branch_id].outgoing.append(node_id)
                            node.incoming.append(branch_id)

            # Циклы
            elif self.FOR_START.search(line) or self.WHILE_START.search(line):
                is_while = self.WHILE_START.search(line)
                match = self.WHILE_START.search(line) if is_while else self.FOR_START.search(line)
                condition = match.group(2) if match else ""
                node = FlowNode(
                    id=node_id,
                    node_type=NodeType.LOOP,
                    line_number=actual_line,
                    code=stripped,
                    label=f"{'WHILE' if is_while else 'FOR'}: {condition[:30]}"
                )
                stack.append(('loop', node_id, []))

            elif self.LOOP_END.search(line):
                if stack and stack[-1][0] == 'loop':
                    _, loop_start, breaks = stack.pop()
                    # Цикл возвращается к началу
                    if loop_start in cfg.nodes:
                        cfg.nodes[prev_node].outgoing.append(loop_start)
                        cfg.nodes[loop_start].incoming.append(prev_node)
                    # Создаём узел выхода из цикла
                    node = FlowNode(
                        id=node_id,
                        node_type=NodeType.STATEMENT,
                        line_number=actual_line,
                        code=stripped,
                        label="ENDLOOP"
                    )
                    # Соединяем break'и
                    for break_id in breaks:
                        if break_id in cfg.nodes:
                            cfg.nodes[break_id].outgoing.append(node_id)
                            node.incoming.append(break_id)

            elif self.BREAK.search(line):
                node = FlowNode(
                    id=node_id,
                    node_type=NodeType.STATEMENT,
                    line_number=actual_line,
                    code=stripped,
                    label="BREAK"
                )
                if stack:
                    for s in reversed(stack):
                        if s[0] == 'loop':
                            s[2].append(node_id)
                            break

            elif self.CONTINUE.search(line):
                node = FlowNode(
                    id=node_id,
                    node_type=NodeType.STATEMENT,
                    line_number=actual_line,
                    code=stripped,
                    label="CONTINUE"
                )
                # Continue возвращается к началу цикла
                if stack:
                    for s in reversed(stack):
                        if s[0] == 'loop':
                            node.outgoing.append(s[1])
                            break

            # Try-Except
            elif self.TRY_START.search(line):
                node = FlowNode(
                    id=node_id,
                    node_type=NodeType.TRY,
                    line_number=actual_line,
                    code=stripped,
                    label="TRY"
                )
                stack.append(('try', node_id, []))

            elif self.EXCEPT.search(line):
                node = FlowNode(
                    id=node_id,
                    node_type=NodeType.STATEMENT,
                    line_number=actual_line,
                    code=stripped,
                    label="EXCEPT"
                )
                if stack and stack[-1][0] == 'try':
                    stack[-1][2].append(prev_node)

            elif self.TRY_END.search(line):
                if stack and stack[-1][0] == 'try':
                    _, try_start, branches = stack.pop()
                    branches.append(prev_node)
                    node = FlowNode(
                        id=node_id,
                        node_type=NodeType.STATEMENT,
                        line_number=actual_line,
                        code=stripped,
                        label="ENDTRY"
                    )

            elif self.RAISE.search(line):
                node = FlowNode(
                    id=node_id,
                    node_type=NodeType.RAISE,
                    line_number=actual_line,
                    code=stripped,
                    label="RAISE"
                )

            elif self.RETURN.search(line):
                node = FlowNode(
                    id=node_id,
                    node_type=NodeType.RETURN,
                    line_number=actual_line,
                    code=stripped,
                    label="RETURN"
                )
                cfg.end_nodes.append(node_id)

            else:
                # Обычный оператор
                node = FlowNode(
                    id=node_id,
                    node_type=NodeType.STATEMENT,
                    line_number=actual_line,
                    code=stripped,
                    label=stripped[:40]
                )

            if node:
                cfg.nodes[node_id] = node

                # Связываем с предыдущим узлом
                if prev_node in cfg.nodes and node.node_type not in (NodeType.RETURN, NodeType.RAISE):
                    if node_id not in cfg.nodes[prev_node].outgoing:
                        cfg.nodes[prev_node].outgoing.append(node_id)
                    if prev_node not in node.incoming:
                        node.incoming.append(prev_node)

                prev_node = node_id
                node_id += 1

        # Конечный узел
        end_node = FlowNode(
            id=node_id,
            node_type=NodeType.END,
            line_number=offset + len(lines),
            label="END"
        )
        cfg.nodes[node_id] = end_node

        # Связываем последний узел с END
        if prev_node in cfg.nodes:
            cfg.nodes[prev_node].outgoing.append(node_id)
            end_node.incoming.append(prev_node)

        cfg.end_nodes.append(node_id)

        return cfg

    def _find_all_paths(self, cfg: ControlFlowGraph, max_paths: int = 100) -> List[LogicPath]:
        """Поиск всех путей выполнения в графе"""
        paths = []
        path_id = 0

        def dfs(node_id: int, current_path: List[int], conditions: List[str], visited: Set[int]):
            nonlocal path_id

            if path_id >= max_paths:
                return

            if node_id in visited:
                # Обнаружен цикл
                return

            current_path.append(node_id)
            node = cfg.nodes.get(node_id)

            if not node:
                return

            # Собираем условия
            if node.node_type == NodeType.CONDITION:
                conditions.append(node.label)

            # Достигли конца
            if node.node_type in (NodeType.END, NodeType.RETURN) or not node.outgoing:
                paths.append(LogicPath(
                    path_id=path_id,
                    nodes=current_path.copy(),
                    conditions=conditions.copy(),
                    is_exception_path=NodeType.RAISE.value in [
                        cfg.nodes[n].node_type.value for n in current_path if n in cfg.nodes
                    ]
                ))
                path_id += 1
                return

            visited.add(node_id)

            for next_id in node.outgoing:
                dfs(next_id, current_path.copy(), conditions.copy(), visited.copy())

        dfs(cfg.start_node, [], [], set())
        return paths

    def _find_unreachable_code(
        self, cfg: ControlFlowGraph, lines: List[str], offset: int
    ) -> List[int]:
        """Поиск недостижимого кода"""
        reachable = set()

        def mark_reachable(node_id: int, visited: Set[int]):
            if node_id in visited or node_id not in cfg.nodes:
                return
            visited.add(node_id)
            reachable.add(cfg.nodes[node_id].line_number)
            for next_id in cfg.nodes[node_id].outgoing:
                mark_reachable(next_id, visited)

        mark_reachable(cfg.start_node, set())

        # Находим строки с кодом, которые не достижимы
        unreachable = []
        for node in cfg.nodes.values():
            if node.line_number not in reachable and node.node_type != NodeType.START:
                unreachable.append(node.line_number)

        return sorted(set(unreachable))

    def _find_infinite_loops(
        self, cfg: ControlFlowGraph, lines: List[str], offset: int
    ) -> List[int]:
        """Поиск потенциально бесконечных циклов"""
        infinite = []

        for node_id, node in cfg.nodes.items():
            if node.node_type == NodeType.LOOP:
                # Проверяем, есть ли выход из цикла
                has_exit = False

                def check_exit(n_id: int, visited: Set[int]) -> bool:
                    if n_id in visited:
                        return False
                    visited.add(n_id)

                    n = cfg.nodes.get(n_id)
                    if not n:
                        return False

                    # Нашли выход
                    if n.node_type in (NodeType.RETURN, NodeType.RAISE, NodeType.END):
                        return True

                    # Нашли break
                    if 'BREAK' in n.label:
                        return True

                    for next_id in n.outgoing:
                        if next_id != node_id and check_exit(next_id, visited):
                            return True

                    return False

                has_exit = check_exit(node_id, set())

                # Проверяем условие цикла While
                if 'WHILE' in node.label:
                    # Упрощённая проверка - если условие содержит Истина/True
                    if re.search(r'\b(Истина|True)\b', node.code, re.IGNORECASE):
                        if not has_exit:
                            infinite.append(node.line_number)

        return infinite

    def _generate_logic_warnings(
        self,
        cfg: ControlFlowGraph,
        paths: List[LogicPath],
        unreachable: List[int],
        infinite_loops: List[int]
    ) -> List[str]:
        """Генерация предупреждений о логических проблемах"""
        warnings = []

        if unreachable:
            warnings.append(f"Недостижимый код на строках: {unreachable[:5]}")

        if infinite_loops:
            warnings.append(f"Потенциально бесконечные циклы на строках: {infinite_loops}")

        if len(paths) > 50:
            warnings.append(f"Высокая сложность: {len(paths)} путей выполнения")

        # Проверяем пути с исключениями
        exception_paths = [p for p in paths if p.is_exception_path]
        if len(exception_paths) > len(paths) // 2:
            warnings.append("Много путей завершаются исключением")

        # Проверяем глубину условий
        max_conditions = max((len(p.conditions) for p in paths), default=0)
        if max_conditions > 5:
            warnings.append(f"Глубокая вложенность условий: {max_conditions} уровней")

        return warnings

    def get_function_complexity(self, content: str, function_name: str = None) -> Dict:
        """Получение метрик сложности логического потока"""
        result = self.analyze_function_logic(content, function_name)

        return {
            'function': result.function_name,
            'path_complexity': result.complexity_paths,
            'unreachable_lines': len(result.unreachable_lines),
            'infinite_loops': len(result.infinite_loops),
            'warnings_count': len(result.warnings),
            'cfg_nodes': len(result.cfg.nodes) if result.cfg else 0
        }

    def analyze_file(self, file_path: Path) -> Dict[str, LogicAnalysisResult]:
        """Анализ всех функций в файле"""
        content = file_path.read_text(encoding='utf-8')
        results = {}

        # Находим все функции
        for match in self.FUNCTION_START.finditer(content):
            func_name = match.group(2)
            results[func_name] = self.analyze_function_logic(content, func_name)

        return results
