# Pipeline: Фикс bsl-code-search + догон непрогнанных инструментов

**Тип:** complex (bugfix + live-tests + docs) · **Дата:** 2026-06-21

## 1. План
(а) Прогнать SonarQube/analyze_run/bsl-platform-context с реальным выводом. (fix) Починить bsl-code-search (пустой ответ).

## 2. Дизайн
Диагностика bsl-code-search по .mcp.json + index.js; live-прогон остальных на боевой конфе; фикс кода + verify свежим спавном сервера.

## 3. Реализация
- analyze_run.py --mode graph ✅, bsl-platform-context ✅.
- bsl-code-search: 2 бага (BSL_SOURCE_DIR=configuration → src; JS-regex \w не матчит кириллицу → [\wА-Яа-яЁё]). Правки .mcp.json + index.js.
- 43.7 + память обновлены; SonarQube — запуск в фоне.

## 4. Тест / результат
- Фикс проверен end-to-end: 2104 файла → 1954 индексировано / 32901 символ; search_symbols/find_callers возвращают результаты (нужен /mcp reconnect).
- analyze_run: 33880 символов / 80246 вызовов / 5353 user-dangling.
