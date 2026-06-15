# TOOL-PLAN — F-1 (impl-1c-bridge-f1)

> Раздел W роадмапа 260614: инструменты по этапам + слот качества (✓/⚠/✗). Лог использования — авто в
> `hook-invocations.jsonl` (run_id); итоговый вердикт — в конце (Тестирование).

| Этап | Инструменты | Назначение | Quality (по факту) |
|---|---|---|---|
| **Планирование** | architecture-research (skill), Read/Grep (pipeline_state.py, preflight-хуки), ADR-019 | подтвердить B′-подход, точки интеграции | _заполнить_ |
| **Дизайн** | architecture-research, Read (base/HookInput, slash_detect) | контракт helper + правки preflight + тесты | _заполнить_ |
| **Кодирование** | implementer (skill), Write/Edit, ruff/`py_compile` | helper `pipeline_1c_bridge.py` + 2 правки preflight + unit-тест | _заполнить_ |
| **Тестирование** | code-verify (skill), `pytest -m unit`, синтетический preflight, `pipeline-protocol-stop` синтетика | DoD 1–4: тест зелёный, G3 закрыт, без регрессий | _заполнить_ |

**Не используются (для F-1):** EDT-MCP / 1c-mcp-crud / 1c-debug-hmr / sonar / bsl_lint (это framework-Python-срез, НЕ BSL-задача).

**Качество — шкала:** ✓ хорошо (1–2 попытки) · ⚠ частично (трение/обходы — заметка) · ✗ плохо (ошибка/не помог — заметка).
Заполняется в конце Тестирования; затем → агрегация `data/tool-effectiveness.jsonl` (когда F-4/W-скрипт готов).
