# Дизайн фиксов (genuine-улучшения, без false-block)

| # | Файл | Изменение |
|---|---|---|
| **N4** | `pipeline_1c_bridge.py` | +`_1C_TITLE_PREFIX="1С-задача ("` + `is_1c_task_title(title)`; заменить 4 guard-сайта (`startswith("1С-задача")` → предикат, заодно чинит рассинхрон скобки) |
| **N4** | `memory-protocol-stop.py`, `research-protocol-stop.py` | импорт `is_1c_task_title` (graceful fallback на локальный литерал); использовать в `_onec_task_this_session` |
| **N3** | оба protocol-хука | `TRANSCRIPT_TAIL_BYTES=8 МБ`; `_read_tail(path, n)` параметризован; транскрипт читается 8 МБ, лог — 2 МБ |
| **N6** | `memory-protocol-stop.py` | `.md`-capture: + условие `"/.claude/" in fp` (только курируемая память, не src/memory/) |
| **N5** | `pipeline_state.py` (`approve`) + `run-1c-task/SKILL.md` | `approve` принимает actor (default "human"); AUTO зовёт `approve <slug> --by auto` → audit-след «дизайн не ревьюился человеком» |
| **N1** | `pipeline-protocol-stop.py` | превью в block-сообщении: «после Stop проверятся также память + внешний анализ» |
| **N11** | `run-1c-task/SKILL.md` | явные under-steps: Этап 1 = `unified_search`+`WebSearch` (recall+research); Этап 4 после PASS = `capture_pattern` |
| **N10** | memory/research-хуки | opt-out → `timer.log(outcome="allow-optout")` (audit-видимость blanket-bypass) |

**By-design (оставляю + честное обоснование в 43.5):** N7 research-relevance (фикс=false-block: 1С-запрос
находит Infostart без слова), N9 G4-в-AUTO (смысл режима + хард-правило + N5-audit), N12 advance-по-имени
(F-1.5 best-effort), apply_pattern (нельзя enforce «apply»), N2/N8 (graceful/edge).

**Тесты:** регресс is_1c_task_title (paren + lookalike); существующие bridge/memory/research-тесты не должны
сломаться. code-verify на изменённых хуках. **Статус: approved (оператор).**
