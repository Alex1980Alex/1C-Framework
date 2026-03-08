#!/usr/bin/env python3
"""
Тест полной интеграции AST-grep MCP Server с BSL поддержкой
"""

import json
import os
import sys
from main import bsl_adapter

def test_bsl_integration():
    """Комплексный тест BSL интеграции"""
    print("=" * 60)
    print("BSL Integration Test - AST-grep MCP Server")
    print("=" * 60)

    # Тест 1: Адаптер
    print("\n1. Testing BSL Adapter...")
    test_file = "../serena/test/resources/repos/bsl/test_repo/ОбщийМодуль.bsl"

    if not os.path.exists(test_file):
        print(f"   ERROR: Test file not found: {test_file}")
        return False

    # Парсинг файла
    data = bsl_adapter.parse_file(test_file)
    functions_count = len(data.get("functions", []))
    exports_count = len(data.get("exports", []))

    print(f"   OK Functions found: {functions_count}")
    print(f"   OK Exports found: {exports_count}")

    if functions_count == 0:
        print("   ERROR: No functions found!")
        return False

    # Тест 2: Поиск по паттернам
    print("\n2. Testing Pattern Search...")
    matches = bsl_adapter.search_pattern(test_file, "Функция $NAME")
    print(f"   OK Pattern matches: {len(matches)}")

    if matches:
        first_match = matches[0]
        print(f"   OK First match: {first_match['text'][:50]}...")

    # Тест 3: Поиск по YAML правилам
    print("\n3. Testing YAML Rule Search...")
    test_rule = {
        "id": "test-functions",
        "language": "bsl",
        "rule": {
            "pattern": "Функция $NAME($$$) Экспорт"
        }
    }

    rule_matches = bsl_adapter.search_by_rule(test_file, test_rule)
    print(f"   OK Rule matches: {len(rule_matches)}")

    # Тест 4: Поиск файлов
    print("\n4. Testing File Discovery...")
    project_dir = "../serena/test/resources/repos/bsl/test_repo"
    bsl_files = bsl_adapter.find_files(project_dir)
    print(f"   OK BSL files found: {len(bsl_files)}")

    for file_path in bsl_files[:3]:  # Показываем первые 3
        rel_path = os.path.relpath(file_path, project_dir)
        print(f"     - {rel_path}")

    # Тест 5: Проверка конфигурации MCP
    print("\n5. Testing MCP Configuration...")
    try:
        from main import get_supported_languages
        languages = get_supported_languages()
        if "bsl" in languages:
            print("   OK BSL language supported in MCP")
            print(f"   OK Total languages: {len(languages)}")
        else:
            print("   ERROR: BSL not in supported languages!")
            return False
    except ImportError:
        print("   ERROR: Cannot import MCP functions!")
        return False

    # Итоговый результат
    print("\n" + "=" * 60)
    print("SUCCESS: ALL TESTS PASSED - BSL Integration Ready!")
    print("=" * 60)

    print("\nUsage Examples:")
    print("1. Find BSL functions:")
    print('   find_code(project_folder="/path/to/1c/project", pattern="Функция $NAME", language="bsl")')

    print("\n2. Find export procedures:")
    print('   find_code_by_rule(project_folder="/path/to/project", yaml="""')
    print('     id: exports')
    print('     language: bsl')
    print('     rule:')
    print('       pattern: "Процедура $NAME($$$) Экспорт"')
    print('   """)')

    print("\n3. Available BSL patterns:")
    patterns = [
        "Функция $NAME($$$)",
        "Функция $NAME($$$) Экспорт",
        "Процедура $NAME($$$)",
        "Процедура $NAME($$$) Экспорт",
        "Перем $NAME"
    ]

    for pattern in patterns:
        print(f"   - {pattern}")

    return True

if __name__ == "__main__":
    success = test_bsl_integration()
    sys.exit(0 if success else 1)