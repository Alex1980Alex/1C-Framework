# debug-hmr-bp-analysis — компактный пайплайн (trivial, ADR-018)

**Задача:** проверить утверждение «в 1c-debug-hmr нет BP/чтения переменных», добиться рабочего цикла отладки (BP → останов → переменные → анализ).

## 1. Планирование
Гипотеза пользователя опровергнута по схемам tools; план — живой сквозной прогон на `гкс_АсинхронныеСервисы.СформироватьОшибку` (ИБTransportManagementDevelop).

## 2. Дизайн
Триггер через фоновое задание (execute_code + `ФоновыеЗадания.Выполнить`), BP веером по строкам функции, fallback: arm_next_rphost / break_on_next / thin client / rac turn-off.

## 3. Выполнение
- Блокер 1: строки живой конфигурации ≠ repo-src (BP на 67 молчал, реальная строка 70).
- Блокер 2: pre-existing rphost 47600 — убит через `rac process turn-off` (recycle_strategy тихо не срабатывал; Stop-Process — Access denied).
- Блокер 3: HTTP-service rphost не ловится (RC2) — триггер только JOB'ом.
- Результат: `stopByBP=true` на строке 70/71; `debug_variables` (Тема/Текст/Менеджер/Ошибка), `debug_evaluate`=51, logpoint JSONL с отрендеренными переменными.

## 4. Проверка
Живые артефакты: callStackFormed события, `data/debug_logs/3ff8427d-….jsonl`. Ограничение платформы: окно halt эфемерного JOB ~1–2 с (variables/evaluate успевают, Step — нет; для step — персистентный контекст: тонкий клиент/VA).

**Память:** `reference-1c-debug-job-bp-recipe` (+ индекс MEMORY.md). Правок продукт-кода нет — только memory-файлы и этот пайплайн-рекорд.
