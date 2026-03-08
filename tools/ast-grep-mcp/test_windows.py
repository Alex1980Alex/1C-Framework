#!/usr/bin/env python3
"""
Тест BSL адаптера на Windows с кириллическими путями
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bsl_adapter import BSLAdapter

def test_common_modules():
    """Тест на CommonModules"""
    test_path = r'D:\Projects\251211_GKSTCPLK-1934\src\CommonModules'

    if not os.path.exists(test_path):
        print(f"Path not found: {test_path}")
        return False

    adapter = BSLAdapter()

    # Найти ВСЕ BSL файлы
    bsl_files = adapter.find_files(test_path)

    print(f'Found {len(bsl_files)} BSL files for test')
    print('=' * 60)

    errors = 0
    success = 0

    for f in bsl_files:
        print(f'Testing: {f}')
        result = adapter.parse_file(f)

        if 'error' in result and result['error']:
            print(f'  ERROR: {result["error"][:100]}')
            errors += 1
        else:
            funcs = len(result.get('functions', []))
            procs = len(result.get('procedures', []))
            exports = len(result.get('exports', []))
            print(f'  OK: {funcs} functions, {procs} procedures, {exports} exports')
            success += 1

    print('=' * 60)
    print(f'Results: {success} success, {errors} errors')
    return errors == 0


if __name__ == '__main__':
    success = test_common_modules()
    sys.exit(0 if success else 1)
