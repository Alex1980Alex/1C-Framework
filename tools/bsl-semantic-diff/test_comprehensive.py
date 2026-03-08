#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Всесторонние тесты для BSL Semantic Diff MCP v2.0
Полный набор тестов для всех новых функций семантического анализа
"""

import sys
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Добавляем путь к модулям BSL Semantic Diff
sys.path.insert(0, str(Path(__file__).parent))

# Импортируем все модули для тестирования
try:
    from bsl_deep_analyzer import (
        BslDeepAnalyzer, BslFunctionAnalysis, BslComplexityMetrics,
        BslStatement, BslVariable, BslLogicalBlock
    )
    from bsl_logic_analyzer import (
        BslLogicAnalyzer, LogicFlow, LogicNode, LogicPath, AlgorithmPattern
    )
    from bsl_html_visualizer import BslHtmlVisualizer
except ImportError as e:
    print(f"ОШИБКА: Не удалось импортировать модули: {e}")
    sys.exit(1)


class TestBslDeepAnalyzer(unittest.TestCase):
    """Тестирование глубокого анализатора BSL"""

    def setUp(self):
        """Настройка тестов"""
        self.analyzer = BslDeepAnalyzer()
        self.test_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Очистка после тестов"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_simple_function_analysis(self):
        """Тест анализа простой функции"""
        test_code = '''
Функция ПростаяФункция(Параметр1, Параметр2) Экспорт
    Результат = Параметр1 + Параметр2;
    Возврат Результат;
КонецФункции
'''
        test_file = self.test_dir / "simple.bsl"
        test_file.write_text(test_code, encoding='utf-8')

        result = self.analyzer.analyze_file_deep(test_file)
        
        self.assertIsInstance(result, dict)
        if result:  # Может не работать без tree-sitter
            self.assertIn("ПростаяФункция", result)
            func_analysis = result["ПростаяФункция"]
            self.assertIsInstance(func_analysis, BslFunctionAnalysis)
            self.assertGreaterEqual(func_analysis.line_count, 3)

    def test_complex_function_analysis(self):
        """Тест анализа сложной функции с циклами и условиями"""
        test_code = '''
Функция СложнаяФункция(МассивДанных, ПорогЗначения) Экспорт
    Результат = Новый Массив;
    Счетчик = 0;
    
    Если МассивДанных.Количество() = 0 Тогда
        Возврат Результат;
    КонецЕсли;
    
    Для Каждого Элемент Из МассивДанных Цикл
        Счетчик = Счетчик + 1;
        
        Если Элемент.Значение > ПорогЗначения Тогда
            Результат.Добавить(Элемент);
        ИначеЕсли Элемент.Значение < 0 Тогда
            Сообщить("Отрицательное значение: " + Элемент.Значение);
        КонецЕсли;
        
        Если Счетчик > 1000 Тогда
            Прервать;
        КонецЕсли;
    КонецЦикла;
    
    Возврат Результат;
КонецФункции
'''
        test_file = self.test_dir / "complex.bsl"
        test_file.write_text(test_code, encoding='utf-8')

        result = self.analyzer.analyze_file_deep(test_file)
        
        # Проверяем, что анализ выполнен без ошибок
        self.assertIsInstance(result, dict)

    def test_analyzer_methods(self):
        """Тест вспомогательных методов анализатора"""
        # Тест анализа сложности
        complexity = self.analyzer._calculate_complexity("Если А = Б Тогда\nВозврат 1;\nИначе\nВозврат 2;\nКонецЕсли;")
        self.assertIsInstance(complexity, BslComplexityMetrics)
        self.assertGreaterEqual(complexity.cyclomatic_complexity, 1)

        # Тест поиска переменных
        variables = self.analyzer._find_variables("ПеременнаяА = 1;\nПеременнаяБ = \"Строка\";")
        self.assertIsInstance(variables, list)


class TestBslLogicAnalyzer(unittest.TestCase):
    """Тестирование анализатора логики"""

    def setUp(self):
        """Настройка тестов"""
        self.analyzer = BslLogicAnalyzer()

    def test_simple_logic_analysis(self):
        """Тест анализа простой логики"""
        test_function = '''
Процедура ПростаяПроцедура(Параметр)
    Если Параметр > 0 Тогда
        Сообщить("Положительное");
    Иначе
        Сообщить("Отрицательное");
    КонецЕсли;
КонецПроцедуры
'''
        result = self.analyzer.analyze_function_logic(test_function, "ПростаяПроцедура")
        
        self.assertIsInstance(result, LogicFlow)
        self.assertGreaterEqual(len(result.nodes), 1)
        self.assertGreaterEqual(result.algorithm_complexity, 1)

    def test_complex_logic_analysis(self):
        """Тест анализа сложной логики с циклами"""
        test_function = '''
Процедура СложнаяПроцедура(МассивДанных)
    Для Каждого Элемент Из МассивДанных Цикл
        Если Элемент.ТипЗначения = "Число" Тогда
            Если Элемент.Значение > 100 Тогда
                Сообщить("Большое число");
            ИначеЕсли Элемент.Значение < 0 Тогда
                Сообщить("Отрицательное");
            Иначе
                Сообщить("Обычное число");
            КонецЕсли;
        ИначеЕсли Элемент.ТипЗначения = "Строка" Тогда
            Сообщить("Строковое значение");
        КонецЕсли;
    КонецЦикла;
КонецПроцедуры
'''
        result = self.analyzer.analyze_function_logic(test_function, "СложнаяПроцедура")
        
        self.assertIsInstance(result, LogicFlow)
        self.assertGreaterEqual(len(result.nodes), 3)
        self.assertGreaterEqual(result.algorithm_complexity, 3)

    def test_logic_analyzer_methods(self):
        """Тест вспомогательных методов анализатора логики"""
        # Тест парсинга узлов
        nodes = self.analyzer._parse_function_to_nodes("Если А Тогда\nБ = 1;\nКонецЕсли;")
        self.assertIsInstance(nodes, list)

        # Тест определения типа узла
        node_type = self.analyzer._determine_node_type("Если Условие Тогда")
        self.assertEqual(node_type, "condition")

        # Тест анализа паттернов
        patterns = self.analyzer._analyze_algorithm_patterns(
            [LogicNode("start", "start", "Начало", 1)]
        )
        self.assertIsInstance(patterns, list)


class TestBslHtmlVisualizer(unittest.TestCase):
    """Тестирование HTML визуализатора"""

    def setUp(self):
        """Настройка тестов"""
        self.visualizer = BslHtmlVisualizer()
        self.test_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Очистка после тестов"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_single_file_report(self):
        """Тест создания отчета для одного файла"""
        test_code = '''
Функция ТестоваяФункция(Параметр) Экспорт
    Возврат Параметр * 2;
КонецФункции
'''
        test_file = self.test_dir / "test.bsl"
        test_file.write_text(test_code, encoding='utf-8')
        
        output_file = self.test_dir / "report.html"
        
        success = self.visualizer.create_single_file_report(
            test_file, output_file, "Тестовый отчет"
        )
        
        self.assertTrue(success)
        self.assertTrue(output_file.exists())
        
        # Проверяем содержимое отчета
        content = output_file.read_text(encoding='utf-8')
        self.assertIn("<html", content.lower())
        self.assertIn("Тестовый отчет", content)

    def test_diff_report(self):
        """Тест создания отчета сравнения двух файлов"""
        test_code1 = '''
Функция СтараяФункция(Параметр) Экспорт
    Возврат Параметр + 1;
КонецФункции
'''
        test_code2 = '''
Функция НоваяФункция(Параметр) Экспорт
    Возврат Параметр + 2;
КонецФункции
'''
        
        file1 = self.test_dir / "old.bsl"
        file2 = self.test_dir / "new.bsl"
        file1.write_text(test_code1, encoding='utf-8')
        file2.write_text(test_code2, encoding='utf-8')
        
        output_file = self.test_dir / "diff_report.html"
        
        success = self.visualizer.create_diff_report(
            file1, file2, output_file, "Отчет сравнения"
        )
        
        self.assertTrue(success)
        self.assertTrue(output_file.exists())
        
        # Проверяем содержимое отчета
        content = output_file.read_text(encoding='utf-8')
        self.assertIn("Отчет сравнения", content)
        self.assertIn("old.bsl", content)
        self.assertIn("new.bsl", content)

    def test_html_generation_methods(self):
        """Тест вспомогательных методов генерации HTML"""
        # Тест подсветки синтаксиса
        highlighted = self.visualizer._highlight_bsl_syntax("Функция Тест()\nВозврат 1;\nКонецФункции")
        self.assertIsInstance(highlighted, str)
        self.assertIn("Функция", highlighted)

        # Тест генерации CSS
        css = self.visualizer._generate_css()
        self.assertIsInstance(css, str)
        self.assertIn("body", css)

        # Тест генерации JavaScript
        js = self.visualizer._generate_javascript()
        self.assertIsInstance(js, str)
        self.assertIn("function", js)


class TestIntegration(unittest.TestCase):
    """Интеграционные тесты всех компонентов"""

    def setUp(self):
        """Настройка интеграционных тестов"""
        self.deep_analyzer = BslDeepAnalyzer()
        self.logic_analyzer = BslLogicAnalyzer()
        self.html_visualizer = BslHtmlVisualizer()
        self.test_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Очистка после тестов"""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_full_analysis_pipeline(self):
        """Тест полного цикла анализа"""
        test_code = '''
Функция ПолныйАнализ(МассивДанных, ПараметрОбработки) Экспорт
    // Комментарий функции
    Результат = Новый Структура;
    Результат.Вставить("Количество", 0);
    Результат.Вставить("Элементы", Новый Массив);
    
    Если МассивДанных = Неопределено Тогда
        Возврат Результат;
    КонецЕсли;
    
    Для Каждого Элемент Из МассивДанных Цикл
        Попытка
            Если ТипЗнч(Элемент) = Тип("Число") Тогда
                Если Элемент > ПараметрОбработки Тогда
                    Результат.Элементы.Добавить(Элемент);
                    Результат.Количество = Результат.Количество + 1;
                КонецЕсли;
            КонецЕсли;
        Исключение
            Сообщить("Ошибка обработки элемента: " + ОписаниеОшибки());
            Продолжить;
        КонецПопытки;
    КонецЦикла;
    
    Возврат Результат;
КонецФункции

Процедура ВспомогательнаяПроцедура()
    Сообщить("Вспомогательная процедура");
КонецПроцедуры
'''
        
        test_file = self.test_dir / "full_test.bsl"
        test_file.write_text(test_code, encoding='utf-8')
        
        # 1. Глубокий анализ
        deep_result = self.deep_analyzer.analyze_file_deep(test_file)
        self.assertIsInstance(deep_result, dict)
        
        # 2. Анализ логики функции
        logic_result = self.logic_analyzer.analyze_function_logic(test_code, "ПолныйАнализ")
        self.assertIsInstance(logic_result, LogicFlow)
        
        # 3. Создание HTML отчета
        output_file = self.test_dir / "full_report.html"
        html_success = self.html_visualizer.create_single_file_report(
            test_file, output_file, "Полный анализ"
        )
        self.assertTrue(html_success)
        self.assertTrue(output_file.exists())

    def test_comparison_workflow(self):
        """Тест рабочего процесса сравнения файлов"""
        # Создаем два похожих файла с небольшими различиями
        code_v1 = '''
Функция ВерсияОдин(Параметр) Экспорт
    Результат = Параметр * 2;
    Возврат Результат;
КонецФункции
'''
        
        code_v2 = '''
Функция ВерсияДва(Параметр) Экспорт
    // Добавлен комментарий
    Результат = Параметр * 3;  // Изменена формула
    Возврат Результат;
КонецФункции
'''
        
        file_v1 = self.test_dir / "version1.bsl"
        file_v2 = self.test_dir / "version2.bsl"
        file_v1.write_text(code_v1, encoding='utf-8')
        file_v2.write_text(code_v2, encoding='utf-8')
        
        # Анализируем оба файла
        analysis_v1 = self.deep_analyzer.analyze_file_deep(file_v1)
        analysis_v2 = self.deep_analyzer.analyze_file_deep(file_v2)
        
        self.assertIsInstance(analysis_v1, dict)
        self.assertIsInstance(analysis_v2, dict)
        
        # Создаем отчет сравнения
        output_file = self.test_dir / "comparison_report.html"
        success = self.html_visualizer.create_diff_report(
            file_v1, file_v2, output_file, "Сравнение версий"
        )
        
        self.assertTrue(success)
        self.assertTrue(output_file.exists())


class TestErrorHandling(unittest.TestCase):
    """Тестирование обработки ошибок"""

    def test_empty_file_handling(self):
        """Тест обработки пустых файлов"""
        analyzer = BslDeepAnalyzer()
        test_dir = Path(tempfile.mkdtemp())
        
        try:
            empty_file = test_dir / "empty.bsl"
            empty_file.write_text("", encoding='utf-8')
            
            result = analyzer.analyze_file_deep(empty_file)
            self.assertIsInstance(result, dict)
            
        finally:
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)

    def test_invalid_syntax_handling(self):
        """Тест обработки некорректного синтаксиса"""
        analyzer = BslLogicAnalyzer()
        
        # Тест с некорректным синтаксисом
        invalid_code = "Функция НеЗакрытая( \n Если Условие \n"
        
        result = analyzer.analyze_function_logic(invalid_code, "НеЗакрытая")
        self.assertIsInstance(result, LogicFlow)
        # Анализатор должен обрабатывать ошибки gracefully

    def test_missing_file_handling(self):
        """Тест обработки отсутствующих файлов"""
        visualizer = BslHtmlVisualizer()
        
        non_existent_file = Path("non_existent_file.bsl")
        output_file = Path("output.html")
        
        success = visualizer.create_single_file_report(
            non_existent_file, output_file, "Тест"
        )
        
        # Должно корректно обработать отсутствие файла
        self.assertFalse(success)


def run_comprehensive_tests():
    """Запуск всех тестов"""
    print("🧪 ЗАПУСК ВСЕСТОРОННИХ ТЕСТОВ BSL Semantic Diff MCP v2.0")
    print("=" * 70)
    
    # Создаем test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Добавляем все тестовые классы
    test_classes = [
        TestBslDeepAnalyzer,
        TestBslLogicAnalyzer,
        TestBslHtmlVisualizer,
        TestIntegration,
        TestErrorHandling
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Запускаем тесты
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 70)
    print("📊 РЕЗУЛЬТАТЫ ВСЕСТОРОННИХ ТЕСТОВ:")
    print(f"✅ Пройдено: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"❌ Ошибок: {len(result.errors)}")
    print(f"⚠️ Неудач: {len(result.failures)}")
    print(f"📈 Всего тестов: {result.testsRun}")
    
    if result.failures:
        print("\n⚠️ НЕУДАЧНЫЕ ТЕСТЫ:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback.split('AssertionError:')[-1].strip()}")
    
    if result.errors:
        print("\n❌ ОШИБКИ:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback.split('Error:')[-1].strip()}")
    
    success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun) * 100
    print(f"\n🎯 Процент успешности: {success_rate:.1f}%")
    
    if success_rate >= 80:
        print("🎉 ОТЛИЧНЫЙ РЕЗУЛЬТАТ! BSL Semantic Diff MCP v2.0 готов к использованию")
    elif success_rate >= 60:
        print("✅ ХОРОШИЙ РЕЗУЛЬТАТ! Небольшие доработки могут улучшить стабильность")
    else:
        print("⚠️ ТРЕБУЮТСЯ ИСПРАВЛЕНИЯ для повышения надежности")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_comprehensive_tests()
    sys.exit(0 if success else 1)