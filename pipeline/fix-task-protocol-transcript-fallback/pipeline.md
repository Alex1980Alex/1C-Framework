# fix-task-protocol-transcript-fallback — протокольный гейт верит факту, а не только state

**Дата:** 2026-07-26 · **Инцидент:** `task-protocol-enforcer` блокировал Write с «TASK
PROTOCOL: Check skills before writing code / Skills not checked yet» уже ПОСЛЕ успешной
активации скилла в этой же задаче.

## 1. План

Факты из живых логов:

- `.claude/data/session-skills.json` на момент блока: `task_protocol.phase = "classified"`,
  `skill_checked_at: null`, `subtask_count: 0` — при том что имя скилла лежало в
  `activated_skills`, а `TaskProtocolObserver` фактически отработал на `PreToolUse:Skill`
  (13:25:21) и 4× на `TaskCreate` (13:25:32-43).
- UPS-цепочка (`skill-eval-enforcer-shell` → `reset_task_protocol` + `set_task_classified`)
  в этом окне **не фаерила**: фаеры 13:16:17 и 13:47:19 против блока 13:32:01. Значит
  «протокол сбросили новым промптом» — неверная гипотеза (она была записана в первой
  редакции ноты в `CLAUDE.md` и снята).
- `record_llm_delegation()` в 13:29:46 сохранилась. Механизм мутаций жив ⇒ потеряны
  конкретные записи (класс session-state v2.1, 2026-07-17: `os.replace` PermissionError под
  гонкой хуков; исключение глотает blanket-`except` наблюдателя).

Вывод: state — не единственный носитель факта; нужен независимый источник, как уже сделано
для `code-skill-enforcer`.

## 2. Дизайн

- [`shared/transcript_skills.py`](../../.claude/hooks/shared/transcript_skills.py) — общий
  скан транскрипта. Единые предикаты: **настоящий промпт пользователя** (`type="user"` ∧
  content-**строка** ∧ не `isMeta`) и **вызов Skill** (`tool_use` с `name="Skill"`). Форма
  снята с живого транскрипта: результаты инструментов приходят той же ролью, но content —
  список блоков `tool_result`; системные инъекции (feedback Stop-хуков, `local-command-caveat`)
  помечены `isMeta: true`; `role` в тест-фикстурах отсутствует — предикат принимает обе формы.
- Два вопроса к одному скану: `skill_in_transcript(path, name)` (конкретный скилл — прежний
  потребитель `code-skill-enforcer`, переведён на общий модуль) и
  `skill_checked_after_last_prompt(path)` (любой скилл **текущей** задачи — `task-protocol-enforcer`).
- **Якорь на последний промпт обязателен:** без него скилл, активированный в прошлой задаче
  сессии, навсегда открывал бы гейт — это обход, а не фолбэк.
- **Fail-closed:** нет якоря (хвост срезан) / нет транскрипта / модуль недоступен → False,
  остаётся обычный блок. Лишняя блокировка восстановима повторной активацией, тихий обход — нет.
- **Self-heal:** при срабатывании фолбэка пишем `record_skill_checked()`, чтобы остальные
  хуки цепочки увидели факт.

## 3. Реализация

`shared/transcript_skills.py` (новый) · `task-protocol-enforcer.py`
(`_skill_checked_in_transcript` + вызов после проверки фазы) · `code-skill-enforcer.py`
(`_skill_in_transcript` делегирует общему модулю, поведение прежнее).

## 4. Тест

[`tests/unit/test_task_protocol_transcript_fallback.py`](../../tests/unit/test_task_protocol_transcript_fallback.py)
— 13 тестов: Skill после промпта → True; Skill ДО последнего промпта → False; `isMeta`-инъекция
и `tool_result` не якорь; нет якоря → fail-closed; нет файла/пустой путь → False;
`skill_in_transcript` name-specific; формы `is_user_prompt`; e2e энфорсера (allow + self-heal /
блок без доказательства / блок при скилле прошлой задачи / прежний путь state).

Прогон: 40 passed (13 новых + 4 `code-skill-enforcer` + 16 blocked-write + 7 session-state-race),
ruff clean, compile OK. **Саботаж:** отключение фолбэка краснит 1 целевой тест, отключение
якоря — 3. **Live-контракт:** на реальном транскрипте сессии
`skill_checked_after_last_prompt` = `True` — ровно там, где был ложный блок.
