# TOOL-PLAN — F-1 (impl-1c-bridge-f1)

> Раздел W роадмапа 260614: инструменты по этапам + слот качества (✓/⚠/✗). Лог использования — авто в
> `hook-invocations.jsonl` (run_id); итоговый вердикт — в конце (Тестирование).

| Этап | Инструменты | Назначение | Quality (по факту) |
|---|---|---|---|
| **Планирование** | architecture-research (skill), Read/Grep (pipeline_state.py, preflight-хуки), ADR-019 | подтвердить B′-подход, точки интеграции | **✓ хорошо** — точки интеграции (idempotent init_task, preflight) найдены сразу |
| **Дизайн** | architecture-research, Read (implement-preflight execute) | контракт helper + правки preflight + тесты | **✓ хорошо** — дизайн концентричный, approve без правок |
| **Кодирование** | create-hook (skill), Write/Edit, ruff/`py_compile` | helper `pipeline_1c_bridge.py` + 2 правки preflight + unit-тест | **✓ хорошо** — helper+правки чисто (ruff/compile green с 1й) |
| **Тестирование** | evaluation-benchmark (skill, gated), `pytest -m unit`, синтетический preflight, ruff | DoD 1–4: тест зелёный, G3 закрыт, без регрессий | **⚠ частично** — тесты упали 2/5 в full-suite (src/shared collision), нашёл+переписал collision-immune (+1 итерация); skill-gate enforcer потребовал доп. Skill() |

**Не используются (для F-1):** EDT-MCP / 1c-mcp-crud / 1c-debug-hmr / sonar / bsl_lint (это framework-Python-срез, НЕ BSL-задача).

**Качество — шкала:** ✓ хорошо (1–2 попытки) · ⚠ частично (трение/обходы — заметка) · ✗ плохо (ошибка/не помог — заметка).
Заполняется в конце Тестирования; затем → агрегация `data/tool-effectiveness.jsonl` (когда F-4/W-скрипт готов).
