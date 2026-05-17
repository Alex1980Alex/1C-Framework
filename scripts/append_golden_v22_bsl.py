"""One-shot: append 20 BSL-domain items (gv1-074..093) to golden_v1.json for v2.2.

Targets bsl_code_v4_late collection to enable §4.1.7 BSL Matryoshka re-bench.
Run ground_golden_v1.py after to populate expected_chunk_ids.

Layout per user-approved §7.5 v2.2 breakdown:
  6 syntax + 6 object methods + 4 framework patterns + 4 error/edge
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PATH = REPO / "data" / "eval" / "golden_v1.json"


def main() -> None:
    data = json.loads(PATH.read_text(encoding="utf-8"))

    new_items = [
        # === BSL Syntax / Language constructs (6) ===
        {
            "id": "gv1-074",
            "query": "Что такое РегистрНакопления в 1С и как читать движения документа?",
            "difficulty": "medium",
            "category": "conceptual",
            "domain": "1c",
            "expected_keywords": ["РегистрНакопления", "Движения", "Регистратор", "Записать"],
            "expected_answer_summary": "РегистрНакопления хранит обороты/остатки; Документ.Движения.РегистрНакопления.<имя> читает/пишет движения.",
        },
        {
            "id": "gv1-075",
            "query": "Как работать со СписокЗначений в BSL — добавление, поиск, итерация?",
            "difficulty": "easy",
            "category": "procedural",
            "domain": "1c",
            "expected_keywords": ["СписокЗначений", "Добавить", "НайтиПоЗначению", "Для Каждого"],
            "expected_answer_summary": "СписокЗначений.Добавить(значение, представление); НайтиПоЗначению; обход через Для Каждого Элемент Из Список.",
        },
        {
            "id": "gv1-076",
            "query": "Когда использовать Структура vs Соответствие в BSL и в чём разница?",
            "difficulty": "medium",
            "category": "comparative",
            "domain": "1c",
            "expected_keywords": ["Структура", "Соответствие", "Вставить", "Ключ"],
            "expected_answer_summary": "Структура — ключи строковые идентификаторы; Соответствие — ключи произвольные. Обе — Вставить/Получить.",
        },
        {
            "id": "gv1-077",
            "query": "В чём отличие Процедура от Функция в 1С при разработке общих модулей?",
            "difficulty": "easy",
            "category": "comparative",
            "domain": "1c",
            "expected_keywords": ["Процедура", "Функция", "Возврат", "Экспорт"],
            "expected_answer_summary": "Процедура — без возврата; Функция — с Возврат. Обе могут быть Экспорт для серверного вызова.",
        },
        {
            "id": "gv1-078",
            "query": "Как объявить экспортную функцию модуля менеджера документа?",
            "difficulty": "medium",
            "category": "procedural",
            "domain": "1c",
            "expected_keywords": ["МодульМенеджера", "ManagerModule", "Экспорт", "Функция"],
            "expected_answer_summary": "В модуле менеджера: Функция МойМетод(Параметр) Экспорт … КонецФункции — доступна через Документы.<имя>.МойМетод.",
        },
        {
            "id": "gv1-079",
            "query": "Что такое ХранилищеЗначения и когда хранить структуру там вместо реквизита?",
            "difficulty": "medium",
            "category": "conceptual",
            "domain": "1c",
            "expected_keywords": ["ХранилищеЗначения", "Новый", "Получить", "DeflateCompression"],
            "expected_answer_summary": "ХранилищеЗначения — сериализованное хранение произвольного объекта. Полезно для неструктурированных payload, картинок, кеша.",
        },
        # === Object methods / API (6) ===
        {
            "id": "gv1-080",
            "query": "Как создать новый документ программно через менеджер документов?",
            "difficulty": "easy",
            "category": "procedural",
            "domain": "1c",
            "expected_keywords": ["Документы", "СоздатьДокумент", "Записать", "ПолучитьОбъект"],
            "expected_answer_summary": "Документы.<имя>.СоздатьДокумент(); установить реквизиты; .Записать(РежимЗаписиДокумента.Запись).",
        },
        {
            "id": "gv1-081",
            "query": "Как записать справочник с проверкой реквизитов перед записью?",
            "difficulty": "medium",
            "category": "procedural",
            "domain": "1c",
            "expected_keywords": ["Справочники", "ПередЗаписью", "ПроверкаЗаполнения", "Записать"],
            "expected_answer_summary": "В ПередЗаписью или ОбработкаПроверкиЗаполнения; СпрОбъект.Записать() триггерит проверку.",
        },
        {
            "id": "gv1-082",
            "query": "Чем отличается ПолучитьСсылку от НайтиПоНаименованию для справочников?",
            "difficulty": "medium",
            "category": "comparative",
            "domain": "1c",
            "expected_keywords": [
                "ПолучитьСсылку",
                "НайтиПоНаименованию",
                "УникальныйИдентификатор",
            ],
            "expected_answer_summary": "ПолучитьСсылку(UUID) — детерминированная ссылка по идентификатору; НайтиПоНаименованию — поиск по строке.",
        },
        {
            "id": "gv1-083",
            "query": "Как использовать общий модуль ОбщегоНазначения для серверного вызова с клиента?",
            "difficulty": "medium",
            "category": "procedural",
            "domain": "1c",
            "expected_keywords": [
                "ОбщегоНазначения",
                "ОбщегоНазначенияВызовСервера",
                "ВызовСервера",
                "&НаСервере",
            ],
            "expected_answer_summary": "Общие модули с галкой 'Вызов сервера' доступны с клиента; функции должны быть Экспорт.",
        },
        {
            "id": "gv1-084",
            "query": "Как обработать БлокировкаДанных внутри транзакции для предотвращения deadlock?",
            "difficulty": "hard",
            "category": "procedural",
            "domain": "1c",
            "expected_keywords": [
                "БлокировкаДанных",
                "Заблокировать",
                "НачатьТранзакцию",
                "Исключение",
            ],
            "expected_answer_summary": "БлокировкаДанных().Добавить(пространство); .Заблокировать() — даёт явную семантику и предотвращает race.",
        },
        {
            "id": "gv1-085",
            "query": "Как реализуется ФоновоеЗадание.Выполнить и контроль завершения?",
            "difficulty": "hard",
            "category": "procedural",
            "domain": "1c",
            "expected_keywords": [
                "ФоновоеЗадание",
                "Выполнить",
                "ОжидатьЗавершения",
                "ПолучитьСостояние",
            ],
            "expected_answer_summary": "ФоновыеЗадания.Выполнить(имяМетода, параметры); потом ОжидатьЗавершения() или периодически проверять Состояние.",
        },
        # === Framework patterns (4) ===
        {
            "id": "gv1-086",
            "query": "Как организован обмен данными через РегистрСведений в УТ?",
            "difficulty": "hard",
            "category": "conceptual",
            "domain": "1c",
            "expected_keywords": ["РегистрСведений", "Набор", "Записать", "Отбор"],
            "expected_answer_summary": "РегистрыСведений.<имя>.СоздатьНаборЗаписей(); Отбор; Прочитать/Записать; периодический — измерение Период.",
        },
        {
            "id": "gv1-087",
            "query": "Как настраивается роль с правами доступа к объектам конфигурации?",
            "difficulty": "medium",
            "category": "procedural",
            "domain": "1c",
            "expected_keywords": ["Роль", "Права", "Чтение", "Изменение", "RLS"],
            "expected_answer_summary": "Роль определяется в Дерево метаданных; права на объекты + RLS через шаблоны ограничения доступа.",
        },
        {
            "id": "gv1-088",
            "query": "Как работает подсистема УправлениеДоступом для разграничения видимости?",
            "difficulty": "hard",
            "category": "conceptual",
            "domain": "1c",
            "expected_keywords": ["УправлениеДоступом", "ГруппыДоступа", "ВидДоступа", "Профиль"],
            "expected_answer_summary": "БСП-подсистема: ГруппыДоступа → ВидыДоступа → значения; RLS использует регистры УправленияДоступом.",
        },
        {
            "id": "gv1-089",
            "query": "Как реализованы регламентные задания (РегламентноеЗадание) и их расписание?",
            "difficulty": "medium",
            "category": "procedural",
            "domain": "1c",
            "expected_keywords": ["РегламентноеЗадание", "Расписание", "Метаданные", "Выполнить"],
            "expected_answer_summary": "Объект метаданных Регламентное задание; Расписание периодов; вызывает указанный метод общего модуля.",
        },
        # === Error handling / edge cases (4) ===
        {
            "id": "gv1-090",
            "query": "Как правильно использовать Попытка-Исключение для обработки ошибок?",
            "difficulty": "easy",
            "category": "procedural",
            "domain": "1c",
            "expected_keywords": ["Попытка", "Исключение", "ОписаниеОшибки", "ВызватьИсключение"],
            "expected_answer_summary": "Попытка … Исключение Сообщение(ОписаниеОшибки()); КонецПопытки; ВызватьИсключение для перевыброса.",
        },
        {
            "id": "gv1-091",
            "query": "Как записать ошибку в журнал регистрации через ЗаписьЖурналаРегистрации?",
            "difficulty": "easy",
            "category": "procedural",
            "domain": "1c",
            "expected_keywords": [
                "ЗаписьЖурналаРегистрации",
                "УровеньЖурналаРегистрации",
                "Ошибка",
                "Метаданные",
            ],
            "expected_answer_summary": "ЗаписьЖурналаРегистрации(событие, УровеньЖурналаРегистрации.Ошибка, метаданные, данные, комментарий).",
        },
        {
            "id": "gv1-092",
            "query": "Как корректно обработать ОтменаТранзакции внутри вложенной транзакции?",
            "difficulty": "hard",
            "category": "procedural",
            "domain": "1c",
            "expected_keywords": [
                "НачатьТранзакцию",
                "ОтменитьТранзакцию",
                "ЗафиксироватьТранзакцию",
                "вложенн",
            ],
            "expected_answer_summary": "1С использует savepoint-семантику; внутренняя ОтменитьТранзакцию помечает внешнюю как отменённую — Попытка-Исключение обязательно.",
        },
        {
            "id": "gv1-093",
            "query": "Как обрабатывается отмена пользователем (Прервано) в коде клиента?",
            "difficulty": "medium",
            "category": "procedural",
            "domain": "1c",
            "expected_keywords": ["Прервано", "ОтменаПользователем", "Cancel", "Возврат"],
            "expected_answer_summary": "Параметр Отказ в обработчиках клиента; ОповеститьОВыборе с Отказ; для длительных операций — флаг отмены.",
        },
    ]

    # All target bsl_code_v4_late; empty expected_chunk_ids (filled by grounding)
    for item in new_items:
        item.setdefault("target_collection", "bsl_code_v4_late")
        item.setdefault("expected_chunk_ids", [])

    existing_ids = {it["id"] for it in data["items"]}
    added = 0
    for item in new_items:
        if item["id"] in existing_ids:
            continue
        data["items"].append(item)
        added += 1

    data["version"] = "v2.2"
    data["updated"] = "2026-05-17"
    data["source"] = (
        data.get("source", "") + " v2.2 — +20 BSL-domain queries for §4.1.7 re-bench (2026-05-17)."
    )

    PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Appended {added}/{len(new_items)} new items; total now {len(data['items'])}")


if __name__ == "__main__":
    main()
