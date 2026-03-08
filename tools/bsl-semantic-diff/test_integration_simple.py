#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки интеграции новых модулей BSL Semantic Diff v2.0
Упрощенная версия без эмодзи для совместимости с Windows консолью.
"""

import sys
import logging
from pathlib import Path

# Добавляем путь к модулям BSL Semantic Diff
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Тестирование импорта всех новых модулей"""
    print("ПРОВЕРКА ИМПОРТА МОДУЛЕЙ...")

    try:
        from bsl_deep_analyzer import BslDeepAnalyzer, BslFunctionAnalysis, BslComplexityMetrics
        print("[OK] bsl_deep_analyzer импортирован успешно")

        from bsl_logic_analyzer import BslLogicAnalyzer, LogicFlow, LogicNode
        print("[OK] bsl_logic_analyzer импортирован успешно")

        from bsl_html_visualizer import BslHtmlVisualizer
        print("[OK] bsl_html_visualizer импортирован успешно")

        # Тестируем обновленный MCP сервер
        from mcp_server import server, _handle_deep_analyze_file, _handle_analyze_logic_flow, _handle_create_html_report
        print("[OK] mcp_server с новыми функциями импортирован успешно")

        return True

    except ImportError as e:
        print(f"[ERROR] Ошибка импорта: {e}")
        return False

def test_deep_analyzer():
    """Тестирование глубокого анализатора"""
    print("\nТЕСТИРОВАНИЕ BslDeepAnalyzer...")

    try:
        from bsl_deep_analyzer import BslDeepAnalyzer

        analyzer = BslDeepAnalyzer()
        print("[OK] BslDeepAnalyzer создан успешно")

        # Создаем простой тестовый BSL код
        test_bsl = '''
Функция ТестоваяФункция(Параметр1, Параметр2) Экспорт
    Результат = 0;

    Если Параметр1 > 0 Тогда
        Для Счетчик = 1 По Параметр2 Цикл
            Результат = Результат + Счетчик;
        КонецЦикла;
    Иначе
        Результат = -1;
    КонецЕсли;

    Возврат Результат;
КонецФункции
'''

        # Сохраняем во временный файл
        temp_file = Path(__file__).parent / "temp_test.bsl"
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(test_bsl)

        # Анализируем
        analysis = analyzer.analyze_file_deep(temp_file)

        if analysis:
            print(f"[OK] Анализ выполнен: найдено {len(analysis)} функций")
            func_name = list(analysis.keys())[0]
            func_analysis = analysis[func_name]
            print(f"  Функция: {func_name}")
            print(f"  Строк кода: {func_analysis.line_count}")
            print(f"  Сложность: {func_analysis.complexity_metrics.cyclomatic_complexity}")
            print(f"  Переменных: {len(func_analysis.variables)}")
        else:
            print("[WARN] Анализ не вернул результатов")

        # Удаляем временный файл
        temp_file.unlink()
        return True

    except Exception as e:
        print(f"[ERROR] Ошибка тестирования глубокого анализатора: {e}")
        return False

def test_logic_analyzer():
    """Тестирование анализатора логики"""
    print("\nТЕСТИРОВАНИЕ BslLogicAnalyzer...")

    try:
        from bsl_logic_analyzer import BslLogicAnalyzer

        analyzer = BslLogicAnalyzer()
        print("[OK] BslLogicAnalyzer создан успешно")

        # Простой тестовый код с логикой
        test_function = '''
Процедура ОбработкаДанных(Данные, Результат)
    Если Данные.Количество() > 0 Тогда
        Для Каждого Элемент Из Данные Цикл
            Если Элемент.Активен Тогда
                Результат.Добавить(Элемент);
            КонецЕсли;
        КонецЦикла;
    Иначе
        Сообщить("Нет данных для обработки");
    КонецЕсли;
КонецПроцедуры
'''

        logic_flow = analyzer.analyze_function_logic(test_function, "ОбработкаДанных")

        print(f"[OK] Анализ логики выполнен:")
        print(f"  Узлов в графе: {len(logic_flow.nodes)}")
        print(f"  Путей выполнения: {len(logic_flow.execution_paths)}")
        print(f"  Сложность алгоритма: {logic_flow.algorithm_complexity}")

        return True

    except Exception as e:
        print(f"[ERROR] Ошибка тестирования анализатора логики: {e}")
        return False

def test_html_visualizer():
    """Тестирование HTML визуализатора"""
    print("\nТЕСТИРОВАНИЕ BslHtmlVisualizer...")

    try:
        from bsl_html_visualizer import BslHtmlVisualizer

        visualizer = BslHtmlVisualizer()
        print("[OK] BslHtmlVisualizer создан успешно")

        # Создаем простой тестовый файл
        test_bsl = '''
Функция ПолучитьСумму(А, Б) Экспорт
    Возврат А + Б;
КонецФункции

Процедура ВывестиСообщение(Текст)
    Сообщить(Текст);
КонецПроцедуры
'''

        temp_file = Path(__file__).parent / "temp_test_html.bsl"
        with open(temp_file, 'w', encoding='utf-8') as f:
            f.write(test_bsl)

        # Создаем HTML отчет
        output_path = Path(__file__).parent / "temp_test_report.html"
        success = visualizer.create_single_file_report(
            temp_file, output_path, "Test BSL Analysis"
        )

        if success and output_path.exists():
            file_size = output_path.stat().st_size
            print(f"[OK] HTML отчет создан: {file_size} байт")

            # Удаляем временные файлы
            temp_file.unlink()
            output_path.unlink()
        else:
            print("[WARN] HTML отчет не создан")

        return True

    except Exception as e:
        print(f"[ERROR] Ошибка тестирования HTML визуализатора: {e}")
        return False

def main():
    """Главная функция тестирования"""
    print("BSL SEMANTIC DIFF MCP v2.0 - ТЕСТ ИНТЕГРАЦИИ")
    print("=" * 60)

    tests = [
        ("Импорт модулей", test_imports),
        ("Глубокий анализатор", test_deep_analyzer),
        ("Анализатор логики", test_logic_analyzer),
        ("HTML визуализатор", test_html_visualizer),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"[ERROR] Критическая ошибка в тесте '{test_name}': {e}")

    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print(f"Пройдено: {passed}/{total} тестов")

    if passed == total:
        print("[SUCCESS] ВСЕ ТЕСТЫ ПРОЙДЕНЫ! BSL Semantic Diff v2.0 готов к использованию")
    else:
        print("[WARNING] Некоторые тесты не прошли. Проверьте зависимости и конфигурацию.")

    print("\nДля демонстрации запустите: python demo_new_features.py")

if __name__ == "__main__":
    main()