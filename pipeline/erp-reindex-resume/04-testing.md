# 04 — Тестирование / Верификация

- `py_compile` OK.
- `--help` показывает `--skip-indexed`; оба гейта несовместимости отбивают (`--recreate`, `--paths`).
- Живой diff против Qdrant `bsl_code_erp_ref`: **7877/7877 точных совпадений, 0 orphan** → формат путей идентичен; остаток = 18330.
- Ревьюер-субагент (code-verify, quality-review): **PASS**; R1 (normpath-страховка) + R2 (предупреждение) применены.
- Прогон запущен (PID воркера 57140, GPU 20GB/100%): `skip_indexed skipped=7877 remaining=18330` — совпало с расчётом.

Вердикт: PASS.
