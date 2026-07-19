# Implementation - scripts/roadmap_place.py

Делает воспроизводимой эвристику «куда привязать отложенную задачу» (была только в голове).

- **`scripts/roadmap_place.py`** (stdlib-only, генерация делегирована sonnet): греп `docs/roadmap/*.md` по терминам → `rank` (сортировка `n_matched > hits > date`, 0-матчи исключены) → `suggest` (attach / attach_or_create / create) + `best_sections` (где в файле совпало). CLI `"<термины>" [--top N] [--json]`.
- Чистые функции (`rank`/`suggest`/`best_sections`/`_date_key`) не читают ФС → тестируемы; ФС только в `main`.
- Правило зашито в вывод: привязка по СУБЪЕКТУ (не по инструменту-обходу); малый follow-up → подсекция, крупная тема → новый файл.

## Live-валидация решения
`qa_run codepilot getThickClientInfo` → **ATTACH к 260718_1C_TOOLING_AUDIT** (3/3, 51 hits) - ровно куда я привязал вручную. Нет-темы → CREATE. Тул воспроизводит суждение.
