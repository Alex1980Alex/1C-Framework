# Кодирование (7 фиксов)

| # | Файл | Что сделано |
|---|---|---|
| N4 | `pipeline_1c_bridge.py` | `_1C_TITLE_PREFIX` + `is_1c_task_title()`; 3 guard'а переведены на предикат (заодно чинит рассинхрон скобки) |
| N4 | `memory-protocol-stop.py`, `research-protocol-stop.py` | import `is_1c_task_title` (graceful fallback); `_onec_task_this_session` через предикат |
| N3 | оба хука | `_read_tail(path, n)` параметризован; `TRANSCRIPT_TAIL_BYTES=8 МБ` для транскрипта (лог 2 МБ) |
| N6 | `memory-protocol-stop.py` | capture-`.md` += условие `/.claude/` (только курируемая память) |
| N5 | `run-1c-task/SKILL.md` | `approve <slug> --by auto` (метка `approved_by=auto`) |
| N1 | `pipeline-protocol-stop.py` | превью в block: «после Stop проверятся также память + внешний анализ» |
| N11 | `run-1c-task/SKILL.md` | under-steps: recall+WebSearch в начале (1.5), capture после PASS (8.5) |
| N10 | оба хука | opt-out → `outcome="allow-optout"` (audit) |

**By-design (не трогал, фикс=false-block/суть режима):** N7 research-relevance, N9 G4-в-AUTO, N12, apply_pattern, N2/N8.
**Тесты:** +`is_1c_task_title` (paren/lookalike) + N6 src/memory-exclusion; обновлён md-capture тест под N6.
