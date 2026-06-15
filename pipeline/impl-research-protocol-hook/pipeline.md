# research-protocol-stop — pipeline (medium, клон verified-хука)

**План.** Пользователь: hard-gate хук — блокировать завершение 1С-задачи, если не было внешнего анализа
(WebSearch/Infostart/GitHub), как с memory-protocol-stop.
**Дизайн.** Точный клон verified `memory-protocol-stop` (тот же каркас: _session_start / _onec_task_this_session
[title `1С-задача (`] / _iter_tool_uses / graceful / opt-out). Отличие — `_research_done` = факт ≥1
WebSearch/WebFetch (active research). Литеральную «infostart»/«github» НЕ требуем (легитимный 1С-запрос
находит Infostart без явного слова → ложный block). Источники — в block-сообщении. Opt-out RESEARCH_PROTOCOL_DISABLE=1.
**Реализация.** `.claude/hooks/research-protocol-stop.py` + регистрация в settings.json (после memory-protocol-stop)
+ `tests/unit/test_research_protocol_stop.py` (6 тестов) + ноты в 43.4/CLAUDE.md.
**Тест.** 6 unit + e2e block(exit2)/allow(exit0) + live exempt(exit0) + code-verify PASS (faithful clone,
_research_done корректна, requirement-дизайн обоснован). ruff/compile/settings-JSON clean.
