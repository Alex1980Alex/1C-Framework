# Тестирование (DoD пройден)

| Проверка | Результат |
|---|---|
| unit | **9 passed** (_iter_tool_uses, _memory_signals none/both/md-write/route_and_save, _onec_task detected/non-1c/lookalike/stale) |
| ruff / compile | All passed / OK |
| settings.json | валидный JSON; memory-protocol-stop после pipeline-protocol-stop |
| **E2E block** | temp «1С-задача (run-1c-task)» pipeline + transcript БЕЗ памяти → **exit 2** + `[MEMORY-PROTOCOL]` |
| **E2E allow** | transcript С unified_search+capture_pattern → **exit 0** |
| **live exempt** | текущая (не-1С) сессия → **exit 0** (lookalike «1С-задача из чата» исключён) |
| code-verify | **PASS** (6/6 риск-зон: deadlock/false-block/no-enforcement/robustness/время/ресурсы) |

**Вердикт: DONE.** Обязательный memory-цикл (recall→capture) для 1С-задач теперь hard-enforced хуком —
как pipeline-protocol. Ложного блока на не-1С/framework-сессиях нет (paren-anchored 1C-сигнал). Реверс — 2 действия.

**Граница (честно):** enforcer проверяет recall (unified_search/search_patterns) + capture (capture_pattern/
route_and_save/.md-write) по транскрипту; «apply» (apply_pattern) не форсится отдельно (по релевантности находок).
MCP-down → повтор-блок до ручного opt-out (эскейп задокументирован в reason).
