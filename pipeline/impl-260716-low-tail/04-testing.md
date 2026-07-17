# 04 — Верификация

## Новые тесты — [`tests/unit/test_memory_low_tail_260716.py`](../../tests/unit/test_memory_low_tail_260716.py) (10, все green)

| Тест | Пинит |
|---|---|
| `test_null_avg_importance_returns_none_not_crash` | item 1 (round(None) crash) |
| `test_delete_succeeds_when_link_cleanup_raises` | item 2 (cleanup-фейл не маскирует delete) |
| `test_both_naive_age_is_exact` | item 3 happy-path (both-naive) |
| `test_naive_dt_aware_now_agrees_with_naive_now` | item 3 (tz-offset дрейф; skip на UTC-машине) |
| `test_aware_dt_aware_now_offset_correct` | item 3 (aware/aware offset) |
| `test_garbage_metadata_pattern_type_is_coerced_via_alias` | item 5 (alias-коэрсия) |
| `test_unknown/missing_pattern_type_defaults_to_canonical` ×2 | item 5 (дефолт) |
| `test_all_from_string_list_valid_values` | item 6 (message `Valid:`) |
| `test_from_string_still_raises_valueerror` | item 6 (тип исключения не сломан) |

## Sabotage-check (fixes committed → sabotage working tree → git checkout restore)

Откат всех 5 фиксов → **8/10 тестов покраснели**. 2 green — намеренные invariant-guards,
не чувствительные к этим саботажам: `test_both_naive_age_is_exact` (both-naive путь не тронут
саботажем aware-ветки) и `test_from_string_still_raises_valueerror` (сообщение сломано, но это
всё ещё ValueError). **Каждый фикс пинится ≥1 тестом, краснеющим на откате.**

## Регресс

Memory-touching батч (15 файлов: apply_cascade / audit_logging / content_hash / governance_wiring /
link_registry_p0 / memory_ai_chains / memory_maintenance / p1_resilience / pattern_type_contract /
propagation_honest / unified_search_honest / wiki_promoter / write_contract / session_memory_save_dup
+ новый) = **208 passed**. Импорт-смоук: без циклов.

## code-verify

См. запись в §18 роадмапа (Level 2 read-only reviewer).
