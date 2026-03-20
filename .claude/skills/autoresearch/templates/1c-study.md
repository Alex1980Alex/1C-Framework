# Template: 1C Configuration Study

name: 1c-study
scope: ".claude/skills/1c-*/cache/"
metric: "% изученных объектов"
direction: higher is better
verify: |
  python -c "
  import json, os
  idx = 'cache/_index.json'
  if os.path.exists(idx):
      data = json.load(open(idx, encoding='utf-8'))
      total = data.get('total_objects', 1)
      studied = len(data.get('studied', []))
      print(f'METRIC: {round(studied/total*100, 1)}')
  else:
      print('METRIC: 0')
  "
test: echo "Validate cache JSON structure"

## Executor

6 фаз на каждый объект:
1. МЕТАДАННЫЕ: `get_metadata`, `find_references`, `execute_query` (первые 3 записи)
2. ИСХОДНЫЙ КОД: `list_modules`, `get_symbol_info` (ОбработкаПроведения, ПередЗаписью)
3. ГИПОТЕЗА: обязательные реквизиты, движения, зависимости, бизнес-смысл
4. ПРОВЕРКА НА БАЗЕ: создать ТЕСТ_AR_*, провести, проверить движения
5. ГРАНИЧНЫЕ СЛУЧАИ: без обязательного поля, отмена проведения
6. CLEANUP + КЭШ: удалить ТЕСТ_AR_*, записать cache/

Приоритет: документы → регистры → справочники.

## Reviewer

- Cache файл создан и валиден (JSON)?
- `_index.json` обновлён?
- Тестовые данные (ТЕСТ_AR_*) удалены?
- Факты проверены на базе (не выдуманы)?
