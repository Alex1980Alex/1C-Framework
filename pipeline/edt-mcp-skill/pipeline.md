# Пайплайн: Скилл `edt-mcp` — справочник 70 инструментов EDT-MCP

Задача (от пользователя): глубокий анализ документации инструментов EDT-MCP
(`github.com/DitriXNew/EDT-MCP/tree/master/docs/tools`) и формирование скилла, чтобы
знать всю документацию, инструменты и как ими пользоваться.

## 1. План
- Источник: 70 файлов `docs/tools/*.md` + индекс `docs/tools/README.md` (тулсет-таксономия).
- Достать через sparse-clone репозитория (только `docs/`), не WebFetch по одному.
- Делегировать извлечение 60 тулов 4 параллельным read-only агентам (компактный дайджест: purpose/params/returns/gotchas); сложные create/adopt/debug_launch прочитать самому.
- Метод оформления — skill `doc-to-skill`: SKILL.md ≤500 строк + полнота в `references/`.

## 2. Дизайн
- Структура: `SKILL.md` (концепции + проектное подключение + таксономия + канонические workflow + диагностика/антипаттерны) + `references/tools.md` (все 70 тулов детально).
- Регистрация в `skill-router-config.json` bundle `edt-mcp` с УНИКАЛЬНЫМИ keywords (избегать `get_metadata` — занят `1c-mcp-data`); NOT-redirects на 1c-mcp-crud / 1c-debug-hmr / bsl-development / bsl-symbol-editing.
- Проектная специфика: порт 8765, mcp-remote, EDT 2025.2, `/mcp reconnect`, JVM-флаг форм, confirm-гейт, contentHash round-trip.

## 3. Реализация
- Sparse-clone `C:\Temp\edtmcp-repo` (docs/), конкатенация в `edtmcp-all-tools.md` (3371 строк).
- Прочитан индекс (11 тулсетов) + сложные тулы; 4 агента вернули дайджесты по 12/12/14/21 файлов (= 59 тулов).
- Созданы: `.claude/skills/edt-mcp/SKILL.md` (245 строк), `.claude/skills/edt-mcp/references/tools.md` (472 строки).
- Зарегистрирован bundle `edt-mcp` в `skill-router-config.json`.

## 4. Тест / верификация
- JSON валиден; bundle count 46; `edt-mcp` present; keywords без коллизий с другими bundle (проверено скриптом). ✅
- SKILL.md 245 строк (< лимит 500 из doc-to-skill). ✅
- Скилл подхвачен каталогом (system-reminder: skill `edt-mcp` доступен). ✅
- Покрытие: все 70 тулов из `docs/tools/README.md` присутствуют в `references/tools.md` (по тулсетам). ✅
- Faithfulness: содержимое сверено с официальными `docs/tools/*.md` (дайджесты агентов + прямые чтения), не выдумано.
