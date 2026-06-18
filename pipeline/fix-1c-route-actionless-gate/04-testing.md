# 04 · Тестирование

## Unit (новые + регресс)
`.venv\Scripts\python.exe -m pytest tests\unit\test_pipeline_1c_bridge.py -q` → **80 passed** (0.16s).
Изолированно и с `CI=1` — зелено.

Новые тесты (8):
- `test_route_actionless_headline_user_example` — ГВОЗДЬ: точный вход пользователя → `is_1c`,
  `confident_1c`, `complexity=simple`, `actionless=True`, `flow="ask_flow"` (НЕ auto).
- `test_route_actionless_code_dump_no_verb` — code-dump без глагола → ask_flow.
- `test_route_actionless_false_when_verb_present` — инвариант: глагол → остаётся auto.
- `test_route_actionless_false_when_work_signal_present` — work-сигнал → не simple → не actionless.
- `test_route_actionless_key_present_all_returns` — наблюдаемость ключа.
- `test_task_verb_extension_common_verbs` / `_no_substring_fp` / `_route_replace_is_action` —
  новые глаголы + substring-негативы (взамен/переписка/переделка) + «замени» = действие.

## Code-verify (bug-fix-validation, ревьюер-субагент a607d8cd719138f8c)
**Вердикт: PASS** `[CODE-VERIFY-PASS]`. Подтверждено:
- гейт достижим только в simple-полосе (medium/complex не затронуты);
- инвариант безопасности «confident сохранён» — гейт меняет лишь flow/actionless;
- root-cause-фикс, минимален, баг-триггер покрыт точным входом;
- регресс на `flow=="auto"` (3 позитивных ассерта, все с глаголом) и `*_bsp_call_confident_route`
  (`flow != "ask_1c"`) — отсутствует.

Замечания ревьюера (неблокирующие): (1) substring-FP отглагольных сущ. — зафиксировано тех-долгом
в 03; (2) pre-existing флейк semantic-тестов (`test_route_semantic_*`, `_semantic_signal_*`) —
order-зависимый cross-file (накопление `sys.modules` от `src.pdf_framework`-тестов), **доказанно
не связан с фиксом** (изолированно файл зелёный; deselect новых тестов даёт те же 3 падения).

## Итог
Баг закрыт: `route_1c_task` на verb-less/zero-signal confident-входе больше не уходит в AUTO.
