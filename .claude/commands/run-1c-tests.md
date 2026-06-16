---
description: Прогон VA BDD тестов задачи 1С в секционно-цепочном режиме (resume с упавшей секции, pre-scenario TestDB check) через skill `va-bdd-testing` + run-bdd.ps1. Этап 4 пайплайна 1С.
---

# Прогон VA BDD тестов для задачи 1С (цепочная модель)

Запусти VA BDD тесты задачи 1С с **секционно-цепочным** исполнением: каждая секция — один
логический блок (`.feature`-файл), секции идут по порядку с переиспользованием созданных
объектов, при сбое — возобновление с упавшей секции без повторного прогона пройденных.
Используй **skill `va-bdd-testing`** как источник step-паттернов и методологии.

## Задача от пользователя:
$ARGUMENTS

---

## Инструкция

**Используй skill `va-bdd-testing`** — методология Stage 4a (pre-scenario TestDB check),
Stage 4 (post-verification), диагностика ошибок, откалиброванные паттерны.

### Входные данные

Из `$ARGUMENTS` извлеки:
1. **Путь к TEST-PLAN-DETAILED.md** (или папке задачи, или `features/<task-slug>/`)
2. **Параметры (опционально):**
   - `--section <NAME>` — запустить только конкретную секцию (например, `06_arm_workflow`)
   - `--from <NAME>` — начать цепочку с указанной секции (пропустив предыдущие)
   - `--fresh` — сбросить состояние цепочки, прогнать с нуля
   - `--dry-run` — только pre-check всех секций без запуска VA
   - `--timeout <SEC>` — таймаут на секцию (по умолчанию 120)
3. Код задачи (`<TASK-ID>`) — извлекается из пути, slug `project1234`

**Алгоритм резолва путей:**
- Папка `.feature`-секций → `features/<task-slug>/` (определения тестов — не меняется)
- State file (`.run-state.json`):
  - **1С-задача** (есть pipeline-state, `pipeline_state.state_dir(<slug>)` ≠ generic `pipeline/`) →
    `<task_dir>/.run-state.json` — В ПАПКЕ ЗАДАЧИ рядом с ANALYSIS-REPORT.md/IMPLEMENTATION-PROGRESS.md
    (этап 4 пайплайна; передавать `run-bdd.ps1 -OutputJson "<task_dir>/.run-state.json"`).
  - иначе (legacy/не-1С) → `features/<task-slug>/.run-state.json`.
- Reports → `build/reports/<task-slug>/` (JUnit XML)

---

## Модель цепочки

### Что такое «секция» и «цепочка»

- **Секция** = один `.feature`-файл = один логический блок из `/write-1c-tests`
  (один объект конфигурации + связанные формы и бизнес-логика)
- **Цепочка** = упорядоченная последовательность секций с **зависимостями**

### Зависимости между секциями

Извлекаются из `METADATA → Dependencies:` в шапке каждого `.feature`-файла:

```gherkin
# METADATA:
#   Task: <TASK-ID>
#   Logical block: Документ.<Имя>
#   Dependencies: 00_smoke.feature, 01_tm1_states.feature
```

Если `Dependencies` не задан — секция независима (может стартовать первой / параллельно
с другими независимыми).

**Граф зависимостей** строится из всех feature-файлов директории. Топологическая
сортировка → порядок исполнения. Если обнаружен цикл — ошибка, отчёт пользователю.

### Переиспользование созданных объектов

Каждая секция в `Тогда` может создавать объекты (документы, записи регистров, справочные
элементы). Эти объекты идентифицируются **уникальным маркером** в тестовых данных
(например, `Комментарий = 'TEST-SEC01-001'` или другой реквизит-маркер из METADATA).

**Post-check extraction** (после успешного прогона секции):

```python
# Найти созданные объекты по маркеру (реквизит-маркер определяется из METADATA секции)
mcp__1c-mcp-crud__execute_query(
    query="""ВЫБРАТЬ
        Ссылка.УникальныйИдентификатор() КАК UUID,
        Номер, Дата, Проведен
    ИЗ Документ.<ТипДокумента>
    ГДЕ <РеквизитМаркер> ПОДОБНО &Marker""",
    parameters={"Marker": "TEST-<SECTION>-%"}
)
```

Извлечённые ссылки сохраняются в `.run-state.json` и **передаются в следующие секции**
через шаблон Контекста или параметры VA (например, через заранее проинициализированные
константы в `execute_code` pre-step).

---

## State file: `.run-state.json`

Местоположение: **1С-задача** → `<task_dir>/.run-state.json` (папка задачи, этап 4 пайплайна);
legacy/не-1С → `features/<task-slug>/.run-state.json` (см. «Алгоритм резолва путей» выше).

Формат:
```json
{
  "task": "<TASK-ID>",
  "last_run": "2026-04-11T14:30:00",
  "chain": [
    {
      "section": "00_smoke",
      "feature_file": "00_smoke.feature",
      "status": "passed",
      "started_at": "2026-04-11T14:25:00",
      "duration_s": 25,
      "dependencies": [],
      "created_objects": [],
      "pre_check": "ok",
      "post_check": "ok",
      "attempts": 1
    },
    {
      "section": "01_catalogs",
      "feature_file": "01_catalogs.feature",
      "status": "passed",
      "duration_s": 195,
      "dependencies": ["00_smoke"],
      "created_objects": [
        {"type": "Документ.<Type>", "uuid": "...", "marker": "ARM-TM1-001"}
      ],
      "attempts": 1
    },
    {
      "section": "02_documents",
      "feature_file": "02_documents.feature",
      "status": "failed",
      "error": "Pre-check FAIL: объект не найден в справочнике",
      "dependencies": ["01_catalogs"],
      "retry_required": true,
      "attempts": 2,
      "error_category": "logical",
      "last_error_step": "И в таблице \"Список\" я перехожу к первой строке",
      "attempt_log": [
        {"attempt": 1, "exit_code": 1, "error_category": "transient", "duration_s": 32, "last_step": "..."},
        {"attempt": 2, "exit_code": 1, "error_category": "logical", "duration_s": 28, "last_step": "..."}
      ]
    }
  ],
  "blockers": []
}
```

**Правила чтения state:**
- `status = passed` → секция пройдена, пропускать при resume
- `status = failed` → точка возобновления
- `status = pending` → не запускалась
- `retry_required = true` → сначала требуется исправить feature перед перезапуском

---

## Pipeline (7 этапов на КАЖДУЮ секцию)

Каждая секция проходит полный цикл **Pre-check → Run → Post-check → State update**.

### Этап 1 — Загрузка и маршрутизация

1. Прочитать `.run-state.json` (если отсутствует — создать пустое состояние)
2. Построить граф зависимостей из METADATA всех `.feature`-файлов
3. Определить список секций к прогону:
   - `--section X` → только X
   - `--from X` → X и все последующие
   - `--fresh` → все с начала, state сброшен
   - без параметров → первая секция со `status ≠ passed` и все последующие
4. Проверить, что все зависимости уже в статусе `passed` (если нет — STOP с объяснением)

### Этап 2 — Pre-check (до запуска VA)

**Источник:** Stage 4a из скилла `va-bdd-testing`.

1. **Проверка тестовых данных** (справочники, настройки, роли) — через
   `mcp__1c-mcp-crud__execute_query` по списку из METADATA секции
2. **Проверка артефактов предыдущих секций** — для каждого объекта из
   `created_objects` предыдущих секций убедиться, что он всё ещё существует в TestDB:
   ```python
   mcp__1c-mcp-crud__execute_query(
       query="ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Кол ИЗ Документ.<Type> ГДЕ Ссылка = &Ref",
       parameters={"Ref": "<uuid-from-state>"}
   )
   ```
   Если артефакт пропал — секция-источник помечается `status: invalidated`, вся
   цепочка от неё пересчитывается
3. **Проверка ролей пользователя** — `mcp__1c-mcp-crud__get_access_rights`

**На FAIL pre-check:**
- Сохранить `pre_check: "fail"` + причину в state
- **НЕ запускать VA**
- Отчёт пользователю: блокер + рекомендация (создать данные / назначить роль / исправить
  предыдущую секцию)

### Этап 3 — Подготовка рабочего окружения (если нужно)

Если в предыдущих секциях созданы объекты, которые нужно использовать как контекст для
текущей — выполнить `mcp__1c-mcp-crud__execute_code` для инициализации:

```bsl
// Установить константы / параметры сеанса с UUID документов из предыдущих секций
ПараметрыСеанса.ТестовыйКонтекстДокумент = СсылкаИзState;
```

Альтернатива: сгенерировать блок `Контекст:` в VA feature-файле через временный override.

### Этап 4 — Запуск VA для одной секции

```powershell
powershell -File tools\vanessa\run-bdd.ps1 -Feature "<slug>/<section>.feature" -TimeoutSec <N> -MaxRetries <R>
```

**ВАЖНО:** запуск пофайловый (не batch). VA зависает при batch-прогоне с ошибками —
это известная проблема (зафиксировано в `TEST-PLAN-DETAILED.md` E.0.1).

Измеряется `duration_s`, фиксируется PID процесса для защиты от зомби-процессов.

**Auto-retry транзиентных ошибок:** `run-bdd.ps1` автоматически классифицирует ошибки
и повторяет запуск при транзиентных сбоях (таймаут, окно не найдено, TestClient не отвечает)
с экспоненциальным backoff и jitter. Логические ошибки (неправильный синтаксис VA, несуществующая
кнопка) **не** ретраятся — сразу FAIL. Параметр `--retries <N>` задаёт макс. попыток (по умолчанию 3).

| Тип ошибки | Retry? | Примеры |
|---|---|---|
| Транзиентная | Да | `Не найдено окно`, `TestClient не отвечает`, `Таймаут ожидания`, crash без VA log |
| Логическая | Нет | `Не найдена процедура для шага`, `Кнопка не найдена`, `Неверный тип навигационной ссылки` |

### Этап 5 — Post-check (после прогона VA)

1. **Чтение JUnit XML** — `build/reports/<task-slug>/junit_<timestamp>.xml`
2. **Парсинг результата:** сценариев прошло / упало / пропущено
3. **Verification queries** — выполнение верификационных SQL из Stage 4 скилла:
   - Созданы ли документы?
   - Записаны ли движения регистров?
   - Корректны ли состояния?
4. **Извлечение созданных объектов** — по маркерам из METADATA → сохранение UUID + тип
   в `state.chain[current].created_objects`

**Критерии прохождения секции:**
- JUnit XML: `failures=0 errors=0`
- Все verification queries: ожидаемые результаты
- Все маркированные объекты созданы

Если хотя бы один критерий не выполнен → `status: failed`.

### Этап 6 — Обработка FAIL секции

На падении секции **STOP-цепочка** — НЕ прогоняем следующие секции.

Диагностика:
1. Прочитать VA лог (`D:\va-test\va-out.txt`), найти последний выполненный шаг
2. Прочитать JUnit XML, извлечь сообщение об ошибке
3. Сверить с таблицей «Common Error Messages» из скилла `va-bdd-testing`:
   - `Неверный тип навигационной ссылки` → `e1cib/app/` vs `e1cib/form/`
   - `Кнопка не найдена` → имя элемента / видимость / роль
   - `Не найдена процедура для шага` → синтаксис VA
   - `Строка не найдена в таблице` → DynamicList, использовать `первой строке`
4. Предложить пользователю конкретный fix для feature-файла
5. Зафиксировать в state: `status: failed`, `retry_required: true`, `last_error_step`

### Этап 6.5 — Auto-fix типовых ошибок (NEW)

**Каталог ошибок:** `tools/vanessa/error-catalog.yaml` — 6 типов ошибок с алгоритмами fix.
Режим задаётся параметром `--fix-mode`:

| Режим | Поведение | Когда использовать |
|---|---|---|
| `--fix-mode suggest` (default) | Показать fix, не применять | Интерактивная работа |
| `--fix-mode auto` | Применить fix + retry автоматически | CI/CD, ночные прогоны |
| `--fix-mode off` | Только диагностика (как раньше) | Отладка |

**Алгоритм:**

1. **Классификация ошибки** — сопоставить текст ошибки из VA log / JUnit XML
   с паттернами из `error-catalog.yaml`. Извлечь named groups (element, title, step).

2. **Lookup правильного значения** через MCP (зависит от типа ошибки):

   | Тип ошибки | MCP lookup | Что ищем |
   |---|---|---|
   | `button_not_found` | `get_form_structure` → buttons | Fuzzy match имени кнопки |
   | `field_not_found` | `get_form_structure` → elements | Fuzzy match + DataPath проверка |
   | `window_not_found` | Проверить nav link prefix | Добавить wildcards к заголовку |
   | `row_not_found` | `get_form_structure` → table columns | Reference column → `первой строке` |
   | `wrong_nav_link` | Определить тип объекта | Обработка→app, Документ→list |
   | `step_not_found` | WebSearch VA docs | **Только suggest**, НЕ auto-fix |

3. **Fuzzy match** (для `button_not_found`, `field_not_found`):
   - Использовать `rapidfuzz.fuzz.ratio()` (уже есть в `shared/fuzzy_match.py`)
   - Threshold из `error-catalog.yaml` (обычно 75-80%)
   - Если match < threshold → НЕ применять, только suggest

4. **Применение fix** (если `--fix-mode auto` и confidence >= threshold):
   - Прочитать `.feature`-файл
   - Найти строку с ошибочным значением
   - Заменить на найденное правильное значение
   - Записать файл

5. **Retry** (если fix применён):
   - Повторить запуск секции через `run-bdd.ps1` (используя retry loop из Этапа 4)
   - Если снова FAIL с ДРУГОЙ ошибкой → ещё один цикл auto-fix (макс 3 итерации)
   - Если снова FAIL с ТОЙ ЖЕ ошибкой → fix не помог, STOP

6. **Запись в state:**
   ```json
   "auto_fixes": [
     {
       "error_id": "button_not_found",
       "original": "ФормаПровестиИЗакрыть",
       "fixed_to": "Форма<Документ>ИЗакрытьДокумент",
       "confidence": 85,
       "applied": true,
       "retry_result": "passed"
     }
   ]
   ```

**Ограничения:**
- `step_not_found` **никогда** не auto-fix (confidence слишком низкий) — только suggest
- Макс 3 итерации auto-fix на секцию (защита от бесконечного цикла)
- Если fix применён но retry failed → **откатить fix** (восстановить оригинал)
- Для `window_not_found` wildcard-fix применяется только если исходный заголовок
  без wildcards (не ломать уже wildcarded заголовки)

### Этап 7 — Обновление state + отчёт

1. Записать `.run-state.json` с новыми статусами
2. Краткий отчёт в чате:
   ```
   Chain: <TASK-ID> (N секций)
     [OK]     00_smoke            25s  (passed, 1 attempt)
     [OK]     01_catalogs         195s (passed, 2 attempts, 1 transient retry)
     [FAIL]   02_documents        ---  (pre-check: объект не найден)
     [SKIP]   03_registers        ---  (depends on 02)
     [SKIP]   04_reports          ---  (depends on 02)
     [SKIP]   05_workflow         ---  (depends on 04)

   BLOCKER at 02_documents:
     Error: Pre-check FAIL — <описание ошибки из preflight>
     Action: создать данные через execute_code ИЛИ исправить feature
     Resume: /run-1c-tests <путь> --from 02_documents
   ```

---

## Параметры команды

| Параметр | Назначение | Пример |
|---|---|---|
| `<путь>` (обязательный) | Путь к TEST-PLAN / папке задачи / features-директории | `features/<task-slug>/` |
| `--section <NAME>` | Запустить только указанную секцию (не влияет на state других) | `--section 05_workflow` |
| `--from <NAME>` | Запустить секцию и все последующие по цепочке | `--from 02_tm3_exclude` |
| `--fresh` | Сбросить state и прогнать цепочку с начала | `--fresh` |
| `--dry-run` | Только pre-check всех секций, без запуска VA | `--dry-run` |
| `--timeout <SEC>` | Таймаут на секцию (по умолчанию 120) | `--timeout 300` |
| `--retries <N>` | Макс. попыток на секцию при транзиентных ошибках (по умолчанию 3) | `--retries 5` |
| `--no-retry` | Отключить auto-retry (эквивалент `--retries 1`) | `--no-retry` |
| `--fix-mode <MODE>` | Режим auto-fix: `suggest` (default), `auto`, `off` | `--fix-mode auto` |
| `--verbose` | Подробный вывод pre-check и post-check | `--verbose` |

### Типовые сценарии использования

**1. Первый прогон всей цепочки:**
```
/run-1c-tests features/<task-slug>/
```

**2. Возобновление после падения:**
```
# State знает, где упало — просто запускаем без параметров
/run-1c-tests features/<task-slug>/
```

**3. Прогон одной секции (для отладки):**
```
/run-1c-tests features/<task-slug>/ --section 05_workflow
```

**4. Прогон с конкретной точки:**
```
/run-1c-tests features/<task-slug>/ --from 02_tm3_exclude
```

**5. Только проверка готовности (без запуска):**
```
/run-1c-tests features/<task-slug>/ --dry-run
```

**6. Принудительный перезапуск с нуля:**
```
/run-1c-tests features/<task-slug>/ --fresh
```

---

## Цикл отладки секции

Когда секция падает, рабочий процесс:

```
/run-1c-tests → FAIL @ 02_tm3_exclude
    ↓
Анализ ошибки (скилл va-bdd-testing → Common Error Messages)
    ↓
Исправление 02_tm3_exclude.feature вручную ИЛИ через /write-1c-tests
    ↓
/run-1c-tests --from 02_tm3_exclude    # state знает, что 00/01 прошли
    ↓
Повторный прогон только 02 и далее
    ↓
Если снова FAIL → attempts++, ещё один цикл
Если PASS → цепочка продолжается автоматически
```

**После 3 неудачных попыток** на одной секции — предупреждение пользователю: «секция
требует углублённой калибровки, возможно нужен probe-прогон отдельного шага».

---

## Результат

- **Обновлённый** `.run-state.json` — история прогонов и текущее состояние цепочки
- **JUnit XML** в `build/reports/<task-slug>/junit_<timestamp>.xml`
- **Отчёт в чате:**
  - таблица секций со статусами, временем, попытками
  - для упавшей секции — детальная диагностика + конкретная рекомендация fix
  - команда для resume
- **Обновление** раздела «Статус калибровки» в `TEST-PLAN-DETAILED.md`
  (автоматически — таблица passed/failed по секциям, дата прогона)

---

## ВАЖНО

- **НЕ переписывай feature-файлы.** Эта команда только ЗАПУСКАЕТ и диагностирует.
  Для изменения `.feature` — `/write-1c-tests`.
- **Всегда уважай state** — если секция в `passed`, не перезапускать её без `--fresh`
  или `--section`. Это ключ к экономии времени.
- **Пре-чек обязателен** (Stage 4a) — лучше упасть за 5 секунд с понятной причиной,
  чем за 200 секунд на «Кнопка не найдена».
- **Артефакты предыдущих секций** хранятся по UUID — не по маркеру, потому что маркер
  может повторяться между прогонами. UUID уникален.
- **Каждая попытка** инкрементирует `attempts` в state — виден прогресс отладки.
- **Запуск пофайловый** — НЕ batch. VA зависает при batch-прогоне (зафиксировано E.0.1).
- **TestDB** предполагается стабильной во время одного прогона цепочки. Если БД
  перезапущена посреди прогона — `--fresh` обязателен (артефакты могут быть потеряны).
- **После 3 fail attempts** на секции — STOP с предложением пере-калибровать через
  `/write-1c-tests --section <NAME>` + probe-прогон.
- **Output сценарий** сохраняется в `features/<task-slug>/runs/<timestamp>/` для аудита.
