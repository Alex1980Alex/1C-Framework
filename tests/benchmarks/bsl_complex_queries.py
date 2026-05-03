"""Benchmark: complex queries for BSL GraphRAG (Phase 6 roadmap 260502).

Run:
  pytest tests/benchmarks/bsl_complex_queries.py -v

Expected: ~20% baseline (Layer 1 only), ~80% with full GraphRAG stack.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.bsl.semantic_search.hybrid_router import classify_query, route

GOLDEN_QUERIES = [
    # Multi-hop callers
    {"id": "MH-1", "type": "multi_hop_callers",
     "query": "Кто вызывает гкс_АсинхронныеСервисы.ЗапуститьЗадание через 2 уровня?",
     "expected_min": 1},
    {"id": "MH-2", "type": "multi_hop_callers",
     "query": "Кто использует функцию ВыполнитьПроверкуОтклоненияБрутто?",
     "expected_min": 1},
    {"id": "MH-3", "type": "multi_hop_callers",
     "query": "Найди callers функции ОбработкаПроведения в гкс_Взвешивание",
     "expected_min": 1},
    {"id": "MH-4", "type": "multi_hop_callers",
     "query": "Кто вызывает методы из гкс_РегистрацияНаПЛК?",
     "expected_min": 1},
    {"id": "MH-5", "type": "multi_hop_callers",
     "query": "Кто использует ОбщегоНазначенияКлиентСервер.СообщитьПользователю?",
     "expected_min": 1},
    # Impact analysis
    {"id": "IA-1", "type": "impact_analysis",
     "query": "Что сломается если переименую функцию ВыполнитьПроверкуОтклоненияБрутто?",
     "expected_min": 1},
    {"id": "IA-2", "type": "impact_analysis",
     "query": "Какие модули повлияют на изменение интерфейса гкс_АсинхронныеСервисы.ЗапуститьЗадание?",
     "expected_min": 1},
    {"id": "IA-3", "type": "impact_analysis",
     "query": "Если переименую регистр гкс_РегистрацияНаПЛК — где это сломается?",
     "expected_min": 1},
    {"id": "IA-4", "type": "impact_analysis",
     "query": "Что повлияет на удаление документа гкс_НаправлениеНаРазгрузку?",
     "expected_min": 1},
    {"id": "IA-5", "type": "impact_analysis",
     "query": "Если изменю сигнатуру СформироватьДвижения — какие документы пострадают?",
     "expected_min": 1},
    # Architectural overview
    {"id": "AR-1", "type": "architectural",
     "query": "Дай overview подсистемы УправлениеТранспортом",
     "expected_min": 1},
    {"id": "AR-2", "type": "architectural",
     "query": "Опиши устройство подсистемы Заблокированные ТС",
     "expected_min": 1},
    {"id": "AR-3", "type": "architectural",
     "query": "Архитектура взаимодействия ВъездНаКПП и Взвешивание",
     "expected_min": 1},
    {"id": "AR-4", "type": "architectural",
     "query": "overview подсистемы Лаборатория композитные пробы",
     "expected_min": 1},
    {"id": "AR-5", "type": "architectural",
     "query": "Опиши АРМ оператора ПЛК и его связи",
     "expected_min": 1},
    # Dead code
    {"id": "DC-1", "type": "dead_code",
     "query": "Найди dead code в общих модулях",
     "expected_min": 0},
    {"id": "DC-2", "type": "dead_code",
     "query": "Какие экспортные функции никем не вызываются?",
     "expected_min": 0},
    {"id": "DC-3", "type": "dead_code",
     "query": "Покажи unused процедуры в гкс_АсинхронныеСервисы",
     "expected_min": 0},
    {"id": "DC-4", "type": "dead_code",
     "query": "Мертвый код в подсистеме УправлениеТранспортом",
     "expected_min": 0},
    {"id": "DC-5", "type": "dead_code",
     "query": "Найди не вызывается процедуры с префиксом гкс_",
     "expected_min": 0},
    # Cross-cutting concerns
    {"id": "CC-1", "type": "cross_cutting",
     "query": "Какие документы пишут в регистр гкс_РегистрацияНаПЛК?",
     "expected_min": 1},
    {"id": "CC-2", "type": "cross_cutting",
     "query": "Где используется функциональная опция и регистр одновременно?",
     "expected_min": 0},
    {"id": "CC-3", "type": "cross_cutting",
     "query": "Документы которые читают регистр Состояния ТС и пишут в РегистрацияНаПЛК",
     "expected_min": 0},
    {"id": "CC-4", "type": "cross_cutting",
     "query": "ФО и регистр накопления используются вместе в одном модуле?",
     "expected_min": 0},
    {"id": "CC-5", "type": "cross_cutting",
     "query": "Cross-cutting concerns между подсистемами Лаборатория и Транспорт",
     "expected_min": 0},
]

CATEGORIES = ["multi_hop_callers", "impact_analysis", "architectural", "dead_code", "cross_cutting"]


@pytest.mark.parametrize("case", GOLDEN_QUERIES, ids=lambda c: c["id"])
def test_router_classifies_correctly(case):
    """Phase 5 acceptance: router correctly classifies query type."""
    actual = classify_query(case["query"])
    assert actual == case["type"], f"Expected {case['type']}, got {actual} for: {case['query']}"


@pytest.mark.parametrize("category", CATEGORIES)
def test_category_coverage(category):
    """Each category has exactly 5 queries."""
    count = sum(1 for c in GOLDEN_QUERIES if c["type"] == category)
    assert count == 5, f"Category {category}: {count} queries (expected 5)"


def test_total_queries():
    """Total: 25 golden queries."""
    assert len(GOLDEN_QUERIES) == 25
