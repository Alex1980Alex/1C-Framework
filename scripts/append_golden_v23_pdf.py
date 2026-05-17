"""One-shot: append 20 PDF-domain items (gv1-094..113) to golden_v1.json for v2.3.

Targets pdf_documents (Глава 5 1С Документация — объекты конфигурации) for
§4.1.8 PDF Matryoshka bench. Run ground_golden_v1.py after to populate
expected_chunk_ids.

Topics align with chapter sections: справочники, документы, регистры,
перечисления, общие модули, формы, бизнес-процессы.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PATH = REPO / "data" / "eval" / "golden_v1.json"


def main() -> None:
    data = json.loads(PATH.read_text(encoding="utf-8"))

    new_items = [
        # === Easy: definitions (8) ===
        {
            "id": "gv1-094",
            "query": "Что такое справочник в 1С Предприятие?",
            "difficulty": "easy",
            "category": "factual",
            "domain": "1c",
            "expected_keywords": ["Справочник", "элемент", "наименование", "код"],
        },
        {
            "id": "gv1-095",
            "query": "Какие виды документов бывают в 1С и как они проводятся?",
            "difficulty": "easy",
            "category": "factual",
            "domain": "1c",
            "expected_keywords": ["Документ", "проведение", "регистратор", "Дата"],
        },
        {
            "id": "gv1-096",
            "query": "Чем регистр сведений отличается от регистра накопления?",
            "difficulty": "easy",
            "category": "comparative",
            "domain": "1c",
            "expected_keywords": ["РегистрСведений", "РегистрНакопления", "Период", "Оборот"],
        },
        {
            "id": "gv1-097",
            "query": "Для чего используются перечисления (Enumerations) в 1С?",
            "difficulty": "easy",
            "category": "factual",
            "domain": "1c",
            "expected_keywords": ["Перечисление", "значение", "статус"],
        },
        {
            "id": "gv1-098",
            "query": "Что такое обработка (Data Processor) в 1С?",
            "difficulty": "easy",
            "category": "factual",
            "domain": "1c",
            "expected_keywords": ["Обработка", "форма", "функция"],
        },
        {
            "id": "gv1-099",
            "query": "Что такое отчёт в 1С и как он строится?",
            "difficulty": "easy",
            "category": "factual",
            "domain": "1c",
            "expected_keywords": ["Отчёт", "СхемаКомпоновкиДанных", "ВыводОтчета"],
        },
        {
            "id": "gv1-100",
            "query": "Что такое общий модуль и для чего он нужен?",
            "difficulty": "easy",
            "category": "factual",
            "domain": "1c",
            "expected_keywords": ["ОбщийМодуль", "Экспорт", "ВызовСервера"],
        },
        {
            "id": "gv1-101",
            "query": "Какие виды форм существуют в 1С 8.3?",
            "difficulty": "easy",
            "category": "factual",
            "domain": "1c",
            "expected_keywords": ["Форма", "УправляемаяФорма", "ФормаЭлемента", "ФормаСписка"],
        },
        # === Medium: properties / variants (8) ===
        {
            "id": "gv1-102",
            "query": "Как работают периодические регистры сведений?",
            "difficulty": "medium",
            "category": "conceptual",
            "domain": "1c",
            "expected_keywords": ["Периодический", "Период", "СрезПоследних", "СрезПервых"],
        },
        {
            "id": "gv1-103",
            "query": "Что такое подчинённый справочник и какие у него ограничения?",
            "difficulty": "medium",
            "category": "conceptual",
            "domain": "1c",
            "expected_keywords": ["Подчинённый", "Владелец", "иерархия"],
        },
        {
            "id": "gv1-104",
            "query": "Чем план счетов отличается от плана видов характеристик?",
            "difficulty": "medium",
            "category": "comparative",
            "domain": "1c",
            "expected_keywords": ["ПланСчетов", "ПланВидовХарактеристик", "Субконто"],
        },
        {
            "id": "gv1-105",
            "query": "Как используются бизнес-процессы и задачи в 1С?",
            "difficulty": "medium",
            "category": "conceptual",
            "domain": "1c",
            "expected_keywords": ["БизнесПроцесс", "Задача", "ТочкаМаршрута", "адресация"],
        },
        {
            "id": "gv1-106",
            "query": "Что такое регламентное задание и как настроить расписание?",
            "difficulty": "medium",
            "category": "procedural",
            "domain": "1c",
            "expected_keywords": ["РегламентноеЗадание", "Расписание", "ОбщийМодуль"],
        },
        {
            "id": "gv1-107",
            "query": "Как работают команды на управляемой форме?",
            "difficulty": "medium",
            "category": "procedural",
            "domain": "1c",
            "expected_keywords": ["Команда", "форма", "обработчик"],
        },
        {
            "id": "gv1-108",
            "query": "Какие свойства имеет реквизит документа?",
            "difficulty": "medium",
            "category": "factual",
            "domain": "1c",
            "expected_keywords": ["Реквизит", "ТипЗначения", "Длина", "Точность"],
        },
        {
            "id": "gv1-109",
            "query": "Что такое подписка на событие и когда её использовать?",
            "difficulty": "medium",
            "category": "conceptual",
            "domain": "1c",
            "expected_keywords": ["ПодпискаНаСобытие", "Источник", "Обработчик"],
        },
        # === Hard: cross-concept (4) ===
        {
            "id": "gv1-110",
            "query": "В чём принципиальная разница между регистром бухгалтерии и регистром расчёта?",
            "difficulty": "hard",
            "category": "comparative",
            "domain": "1c",
            "expected_keywords": ["РегистрБухгалтерии", "РегистрРасчёта", "проводка", "вытеснение"],
        },
        {
            "id": "gv1-111",
            "query": "Когда нужен план видов расчёта и как он связан с регистром расчёта?",
            "difficulty": "hard",
            "category": "analytical",
            "domain": "1c",
            "expected_keywords": [
                "ПланВидовРасчёта",
                "ВытесняющиеВидыРасчёта",
                "БазовыеВидыРасчёта",
            ],
        },
        {
            "id": "gv1-112",
            "query": "Какие табличные части могут быть у справочника и зачем?",
            "difficulty": "hard",
            "category": "conceptual",
            "domain": "1c",
            "expected_keywords": ["ТабличнаяЧасть", "Справочник", "Реквизит"],
        },
        {
            "id": "gv1-113",
            "query": "Как реализуется иерархия групп и элементов у справочника?",
            "difficulty": "hard",
            "category": "procedural",
            "domain": "1c",
            "expected_keywords": ["Иерархия", "ЭтоГруппа", "Родитель", "ИерархияГруппИЭлементов"],
        },
    ]

    for item in new_items:
        item.setdefault("target_collection", "pdf_documents")
        item.setdefault("expected_chunk_ids", [])
        item.setdefault("expected_answer_summary", "")

    existing_ids = {it["id"] for it in data["items"]}
    added = 0
    for item in new_items:
        if item["id"] in existing_ids:
            continue
        data["items"].append(item)
        added += 1

    data["version"] = "v2.3"
    data["updated"] = "2026-05-17"
    data["source"] = (
        data.get("source", "") + " v2.3 — +20 PDF-domain queries for §4.1.8 (2026-05-17)."
    )

    PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Appended {added}/{len(new_items)} new items; total now {len(data['items'])}")


if __name__ == "__main__":
    main()
