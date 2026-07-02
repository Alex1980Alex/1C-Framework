# 04 — Тестирование

- Unit: `tests/unit/test_sonar_rescan_state.py` (+6: parse-хедеры/якорь ^, owning-tree,
  untracked→None, tracked→диапазоны с -w, whitespace-only→[]),
  `tests/unit/test_bsl_lint_format.py` (+4: full-format при head=None с возвратом CRLF,
  легаси-строки не тронуты, вставка форматируется, только-чужие→before). Итог 26/26 PASS.
- `tests/unit/test_gate_policy.py` + `test_gate_policies.py`: 10/10 PASS после фикса _LOG_PATH.
- Ruff: чисто по всем изменённым файлам.
- Live-смоук verify: PASS, per-file запрос HTTP 200 (без усечения), baseline_degenerate=true
  корректно репортится (сервер пересчитает период при следующем анализе).
- Live-сверка дельты закоммиченного АРМ-рефактора (32713d5): 92 изменённые строки (diff -w),
  0 BLOCKER/CRITICAL хитов; 5 CRITICAL файла — легаси (L171/268/1181/1268/1325).
- Code-verify: субагент-ревьюер (read-only) — см. итог в сессии.
