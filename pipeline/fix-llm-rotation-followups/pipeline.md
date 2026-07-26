# Фиксы по живой верификации llm-rotation

Компактная запись (задача = ограниченный batch из трёх дефектов + чистка данных, отдельные
01-04 были бы церемонией). Вход: живая проверка реализации маршрутизации (сессия 2026-07-26),
которая подтвердила три корня закрытыми, но вскрыла три оставшихся дефекта.

## 1. Планирование

Дефекты найдены не чтением кода, а прогоном на реальном вызове:

| # | Дефект | Как обнаружен |
|---|--------|----------------|
| D1 | Хук-советчик выдавал «Z.AI response was slow (66.2s from claude-cli-sonnet). Consider switching provider» на УСПЕШНЫЙ вызов | PostToolUse-сообщение на живом `llm_complete` 66.18с |
| D2 | `primary_retries` инкрементился ДО попытки: чистый успех писался как «был ретрай» | Чтение completions-лога: три реальных вызова, все `attempt=1, primary_retries=1` |
| D3 | 34 интеграционных теста писали синтетику в продовый completions-лог | 4 записи в 14:52 (`none/none`, `mock/m`, `working/m`, `fallback/m`) |

## 2. Дизайн

- **D1** — не «поднять порог», а сделать норму зависимой от ФОРМАТА провайдера: claude-cli
  спавнит субпроцесс (25-150с штатно), HTTP отвечает за секунды. `_latency_profile(provider)`
  → `(fast_under, slow_over)`, единая точка для advisory и для штрафа в `_quality_heuristic`.
  Нераспознанный провайдер → строгий HTTP-профиль (fail-closed).
- **D2** — переименование, а не смена арифметики: значение всегда было «число попыток», врало имя.
- **D3** — изоляция синков в `tests/conftest.py` (import-time env), а НЕ фикстурой в модуле:
  пофайловый opt-in уже протёк мимо `test_backoff.py`. Форма скопирована с существующего
  memory-sink блока в том же conftest.

Ключевое уточнение по ревью: загрязнение лога — не гигиена, а дыра в enforcement.
`.claude/hooks/shared/llm_health.py` читает ЭТОТ ЖЕ файл и считает провалом записи с
`provider="none"` / `error~"down"`, поэтому тестовый мусор способен перевалить порог
`is_provider_down()` и на 30 минут разоружить `z-ai-write-guard`.

## 3. Реализация

| Файл | Изменение |
|------|-----------|
| [`posttooluse-delegation-tracker.py`](../../.claude/hooks/posttooluse-delegation-tracker.py) | `_latency_profile` + профили HTTP `(3.0, 15.0)` / CLI `(30.0, 180.0)`; `_quality_heuristic` принимает пороги (дефолты сохраняют прежнюю семантику); тексты советов без «Z.AI» и без «смени провайдера» |
| [`service.py`](../../src/shared/llm_rotation/service.py) | `primary_retries` → `primary_attempts` (6 мест) + комментарий о смысле счётчика |
| [`tests/conftest.py`](../../tests/conftest.py) | блок изоляции `LLM_ROTATION_{COMPLETIONS_LOG,ADAPTIVE_DATA_PATH,BUDGET_DATA_PATH}`, opt-out `LLM_ROTATION_TEST_ISOLATION_DISABLE=1` |
| [`test_delegation_tracker_latency.py`](../../tests/unit/test_delegation_tracker_latency.py) | новый регресс (7 тестов) на живой форме payload |
| [`test_llm_rotation_routing.py`](../../tests/unit/test_llm_rotation_routing.py) | пин изоляции repo-wide + пин семантики `primary_attempts` |
| `data/llm-rotation-completions.jsonl` | чистка 946 → 769 |

## 4. Тестирование

- 104 теста в затронутых наборах зелёные; полный unit-гейт `-m unit` — **2883 passed, 2 skipped**.
- ruff check / format чистые на всех изменённых файлах, compileall OK.
- **Саботаж D1**: возврат `_LATENCY_CLI` к `(3.0, 10.0)` краснит ровно 3 целевых теста.
- **Саботаж D3**: прогон с `LLM_ROTATION_TEST_ISOLATION_DISABLE=1` → `test_backoff.py` кладёт
  в продовый лог ровно +5 записей, пин-тест краснеет. Снапшот восстановлен.
- Замер mtime вокруг прогона: все четыре продовых синка untouched.
- Чистка: удалено 177 записей (148 по сигнатуре provider/model + 29 `none/none` в тех же
  секундах, что синтетика, при нуле коллизий с реальным трафиком). **123 неоднозначные
  `none/none`** со старым текстом `'No available providers'` оставлены намеренно — атрибутировать
  нечем; легаси реальных провайдеров (zai-glm5/gemini, 214) и улика эскалации `haiku→opus` (2) целы.

## Открытое (не делалось)

- `tests/eval/hook_prompts.json` гоняет хук субпроцессом и льёт в продовый
  `data/delegation-outcomes.jsonl` — тот же класс, что D3, но у этого пути нет env-override,
  нужна правка кода хука.
- Явный `model="opus"` по-прежнему даёт `claude-cli-haiku → claude-opus-4-8` в фоллбэке
  (по дизайну «явная модель не подменяется»); решение — скипать ли младший провайдер при
  явном верхнем тире — за пользователем.
