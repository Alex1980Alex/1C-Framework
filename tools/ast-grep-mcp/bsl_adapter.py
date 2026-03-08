#!/usr/bin/env python3
"""
BSL Adapter для AST-grep MCP Server
Парсер BSL кода с regex-based анализом

Версия 2.0 - Полностью Python-based:
- Не требует внешнего JS парсера
- Regex-based анализ BSL кода
- Поддержка Unicode и кириллицы
- Кеширование результатов
"""

import json
import os
import re
from typing import Any, Dict, List, Optional
import platform

# Определяем, работаем ли на Windows
IS_WINDOWS = platform.system() == "Windows"


class BSLAdapter:
    """Адаптер для работы с BSL кодом через regex-based парсинг"""

    def __init__(self, bsl_parser_path: str = None):
        """
        Инициализация адаптера.
        bsl_parser_path больше не используется, оставлен для совместимости.
        """
        # Кеш для результатов парсинга
        self._parse_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_max_size = 100

        # Простые паттерны для BSL (поддержка кириллицы)
        self.simple_patterns = {
            'procedures': re.compile(
                r'^(\s*)Процедура\s+([а-яА-ЯёЁa-zA-Z0-9_]+)\s*\(([^)]*)\)(\s+Экспорт)?\s*$',
                re.MULTILINE | re.IGNORECASE
            ),
            'functions': re.compile(
                r'^(\s*)Функция\s+([а-яА-ЯёЁa-zA-Z0-9_]+)\s*\(([^)]*)\)(\s+Экспорт)?\s*$',
                re.MULTILINE | re.IGNORECASE
            ),
            'variables': re.compile(
                r'^(\s*)Перем\s+([а-яА-ЯёЁa-zA-Z0-9_]+)(.*?);?\s*$',
                re.MULTILINE | re.IGNORECASE
            ),
            'exports': re.compile(
                r'^(\s*)(Процедура|Функция)\s+([а-яА-ЯёЁa-zA-Z0-9_]+)\s*\([^)]*\)\s+Экспорт',
                re.MULTILINE | re.IGNORECASE
            )
        }

    def _read_file_safely(self, file_path: str) -> Optional[str]:
        """Безопасное чтение файла с обработкой различных кодировок"""
        encodings = ['utf-8', 'utf-8-sig', 'cp1251', 'cp866', 'latin-1']

        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
            except Exception as e:
                return None

        return None

    def _get_line_number(self, content: str, match_start: int) -> int:
        """Получает номер строки по позиции в тексте"""
        return content[:match_start].count('\n') + 1

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """Парсит BSL файл и возвращает структурированные данные"""
        # Нормализуем путь
        norm_path = os.path.normpath(file_path)

        # Проверяем кеш
        if norm_path in self._parse_cache:
            return self._parse_cache[norm_path]

        # Проверяем существование файла
        if not os.path.exists(norm_path):
            return {
                "error": f"File not found: {norm_path}",
                "procedures": [],
                "functions": [],
                "variables": [],
                "exports": []
            }

        # Читаем файл
        content = self._read_file_safely(norm_path)
        if content is None:
            return {
                "error": f"Failed to read file: {norm_path}",
                "procedures": [],
                "functions": [],
                "variables": [],
                "exports": []
            }

        result = {
            "procedures": [],
            "functions": [],
            "variables": [],
            "exports": []
        }

        # Используем простые паттерны (более надежные)
        patterns = self.simple_patterns

        # Поиск процедур
        for match in patterns['procedures'].finditer(content):
            indent, name, params, export = match.groups()
            line = self._get_line_number(content, match.start())
            result["procedures"].append({
                "name": name,
                "params": params.strip() if params else "",
                "line": line,
                "export": bool(export)
            })

        # Поиск функций
        for match in patterns['functions'].finditer(content):
            indent, name, params, export = match.groups()
            line = self._get_line_number(content, match.start())
            result["functions"].append({
                "name": name,
                "params": params.strip() if params else "",
                "line": line,
                "export": bool(export)
            })

        # Поиск переменных
        for match in patterns['variables'].finditer(content):
            indent, name, rest = match.groups()
            line = self._get_line_number(content, match.start())
            result["variables"].append({
                "name": name,
                "line": line
            })

        # Собираем экспортные элементы
        for proc in result["procedures"]:
            if proc.get("export"):
                result["exports"].append({
                    "type": "procedure",
                    "name": proc["name"],
                    "line": proc["line"]
                })

        for func in result["functions"]:
            if func.get("export"):
                result["exports"].append({
                    "type": "function",
                    "name": func["name"],
                    "line": func["line"]
                })

        # Сохраняем в кеш
        self._add_to_cache(norm_path, result)

        return result

    def _add_to_cache(self, path: str, data: Dict[str, Any]):
        """Добавляет результат в кеш с ограничением размера"""
        if len(self._parse_cache) >= self._cache_max_size:
            # Удаляем старые записи (FIFO)
            keys_to_remove = list(self._parse_cache.keys())[:self._cache_max_size // 2]
            for key in keys_to_remove:
                del self._parse_cache[key]
        self._parse_cache[path] = data

    def clear_cache(self):
        """Очищает кеш парсинга"""
        self._parse_cache.clear()

    def parse_files_batch(self, file_paths: List[str]) -> Dict[str, Dict[str, Any]]:
        """Парсит несколько файлов пакетно"""
        results = {}
        for file_path in file_paths:
            results[file_path] = self.parse_file(file_path)
        return results

    def search_pattern(self, file_path: str, pattern: str) -> List[Dict[str, Any]]:
        """Поиск по паттерну в BSL файле"""
        data = self.parse_file(file_path)

        if "error" in data and data["error"]:
            return []

        matches = []

        # Конвертируем AST-grep паттерны в поиск по нашим данным
        pattern_lower = pattern.lower()

        if "процедура" in pattern_lower and "$name" in pattern_lower:
            for proc in data.get("procedures", []):
                matches.append(self._create_match(file_path, proc, "procedure"))

        if "функция" in pattern_lower and "$name" in pattern_lower:
            for func in data.get("functions", []):
                matches.append(self._create_match(file_path, func, "function"))

        if "перем" in pattern_lower and "$name" in pattern_lower:
            for var in data.get("variables", []):
                matches.append(self._create_match(file_path, var, "variable"))

        # Поиск экспортных элементов
        if "экспорт" in pattern_lower:
            for exp in data.get("exports", []):
                matches.append(self._create_match(file_path, exp, exp["type"]))

        return matches

    def search_by_rule(self, file_path: str, rule: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Поиск по YAML правилам"""
        data = self.parse_file(file_path)

        if "error" in data and data["error"]:
            return []

        matches = []
        rule_pattern = rule.get("rule", {})

        if isinstance(rule_pattern, dict):
            pattern_text = rule_pattern.get("pattern", "")
            if pattern_text:
                return self.search_pattern(file_path, pattern_text)

            # Обработка сложных правил (any, all)
            if "any" in rule_pattern:
                for sub_rule in rule_pattern["any"]:
                    if "pattern" in sub_rule:
                        matches.extend(self.search_pattern(file_path, sub_rule["pattern"]))

            if "all" in rule_pattern:
                for sub_rule in rule_pattern["all"]:
                    if "pattern" in sub_rule:
                        matches.extend(self.search_pattern(file_path, sub_rule["pattern"]))

        return matches

    def _create_match(self, file_path: str, item: Dict[str, Any], item_type: str) -> Dict[str, Any]:
        """Создает match объект в формате AST-grep"""
        line = item.get("line", 1)
        name = item.get("name", "")
        params = item.get("params", "")

        # Формируем текст совпадения
        if item_type == "procedure":
            text = f"Процедура {name}({params})"
            if item.get("export"):
                text += " Экспорт"
        elif item_type == "function":
            text = f"Функция {name}({params})"
            if item.get("export"):
                text += " Экспорт"
        elif item_type == "variable":
            text = f"Перем {name}"
        else:
            text = f"{item_type}: {name}"

        return {
            "file": file_path,
            "range": {
                "start": {"line": line - 1, "column": 0},
                "end": {"line": line - 1, "column": len(text)}
            },
            "text": text,
            "metaVariables": {"NAME": name}
        }

    def find_files(self, project_folder: str, extensions: List[str] = None) -> List[str]:
        """Находит все BSL файлы в проекте"""
        if extensions is None:
            extensions = ["bsl", "os"]

        bsl_files = []

        for root, dirs, files in os.walk(project_folder):
            for file in files:
                if any(file.lower().endswith(f".{ext}") for ext in extensions):
                    bsl_files.append(os.path.join(root, file))

        return bsl_files


def test_adapter():
    """Тестирование адаптера"""
    adapter = BSLAdapter()

    # Тестируем на доступном файле
    test_paths = [
        r"D:\Projects\251211_GKSTCPLK-1934\src\CommonModules",
        r"D:\1C-Enterprise_Framework\src\projects\configuration"
    ]

    test_file = None
    for path in test_paths:
        if os.path.exists(path):
            files = adapter.find_files(path)
            if files:
                test_file = files[0]
                break

    if not test_file:
        print("No BSL files found for testing")
        return

    print(f"Testing BSL adapter on: {test_file}")
    print("=" * 60)

    # Тест парсинга
    data = adapter.parse_file(test_file)

    if "error" in data and data["error"]:
        print(f"ERROR: {data['error']}")
        return

    print(f"Functions found: {len(data.get('functions', []))}")
    print(f"Procedures found: {len(data.get('procedures', []))}")
    print(f"Variables found: {len(data.get('variables', []))}")
    print(f"Exports found: {len(data.get('exports', []))}")

    # Показать первые найденные
    if data.get('functions'):
        print(f"\nFirst function: {data['functions'][0]['name']}")
    if data.get('procedures'):
        print(f"First procedure: {data['procedures'][0]['name']}")

    print("\nAdapter ready to use!")


if __name__ == "__main__":
    test_adapter()
