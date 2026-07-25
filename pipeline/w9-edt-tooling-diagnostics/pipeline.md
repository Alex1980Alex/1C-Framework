# W9 - диагностика EDT/codepilot-инструментов (ретро 260725)

Компактный пайплайн: разбор, а не изменение кода. Правки - только артефакты (роадмап, кеш-тема, 2 скилла, память).

## 1. Планирование

Вход: ретро [260725](../../docs/roadmap/260725_ROADMAP_SESSION_RETRO.md) §4 W9 - три незакрытые диагностики (а: form-семейство codepilot1c, б: edt-mcp мутации, в: `update_database`) + 2 висящие задачи tool-health-banner. Требование ретро: у каждой диагностики должен быть **исход**, а не «сняли алерт».

## 2. Дизайн (метод)

Три независимых источника вместо догадок:

1. **hook-invocations** (`data/hook-invocations*.jsonl`, 8 файлов) - парность Pre/Post по `tool_call_id` → точные таймстемпы 37 непарных вызовов.
2. **Транскрипты сессий** (`~/.claude/projects/C--1--Framework/<session>.jsonl`) - `tool_use.input` + `tool_result.is_error`: **текст ошибки есть там, где PostToolUse не пришёл**. Это закрыло главный пробел прежнего разбора («текста ошибки нет ни в OTel, ни в hook-логе»).
3. **Журнал EDT** (`<workspace>/.metadata/.log` + `.bak_N.log`) - пара `Processing tools/call` → `Completed tools/call: … in Nms, outcome=`. Единственный источник, различающий «упало» и «клиент не дождался».

Плюс: схемы тулов (`get_tool_guide`, ToolSearch), prefs воркспейсов, байткод бандла плагина, release notes апстрима.

## 3. Кодирование (что сделано)

Кода не менялось. Артефакты:

- `docs/roadmap/260725_ROADMAP_SESSION_RETRO.md` - W9а/б/в закрыты с фактами; §4 W9 переписан (снял два неверных допущения); 3 новых пункта (consent-гейт, 60с-потолок, классификатор).
- `.claude/skills/1c-doc-research/cache/update-database-restructuring-confirmation.md` + `_index.json` - §2.1 «ПРОВЕРЕНО: этот диалог не причина», 3 поправки, практика.
- `.claude/skills/edt-mcp/SKILL.md` - исправлена неверная строка про `fullUpdate`; +3 строки диагностики; практика №7 «исход - в журнале EDT».
- `.claude/skills/codepilot1c/SKILL.md` - +6 строк диагностики form-семейства.
- Память: `reference-edt-mcp-timeout-60s-means-success`, `reference-edt-mcp-consent-gate-preference`.
- Закрыты 2 задачи `tool-health-banner` с нотой о корне.

## 4. Тестирование (проверка выводов)

Каждый вывод опирается на цитату из журнала/транскрипта, не на пересказ:

| Вывод | Доказательство |
|---|---|
| Таймаут ≠ провал | `Completed tools/call: create_project in 60 253ms, outcome=ok` (клиент оборвал за 253мс до конца) |
| 52 минуты = ожидание человека | `Ошибка исключительной блокировки информационной базы … Отмена/Повторить/Обновить динамически` 13:10:57 → `Completed … in 3 147 392ms, outcome=ok` |
| Гейт плагина держал 119с/215с | `Destructive-consent gate: user allowed 'update_database' for the rest of this EDT session` 13:00:30/13:00:31 |
| Диалог реструктуризации не при чём | `get_tool_guide('update_database')`: «auto-presses that dialog's default Accept button» |
| `modify_metadata` broken - артефакт | из 6 вызовов 1 - собственный пробник «объект заведомо не существует» (07-25 09:34) |
| Уровни consent-гейта | `PreferenceConstants`/`ConsentSettingsService$Level` в `com.ditrix.edt.mcp.server_2.6.1.jar`: `ask_always|allow_all|per_tool` |

Незакрытое (честно): у 2 из 5 таймаутов `update_database` (07-22 08:13 и 12:41) нет покрытия журналом EDT - соответствующие логи ротировались. Вывод по ним - по аналогии с тремя подтверждёнными, не по прямому доказательству.
