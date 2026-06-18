# 04 — Тестирование

## Результаты
- **pytest** `tests/unit/test_onec_setfit_gate.py` + `tests/unit/test_pipeline_1c_bridge.py`:
  **82 passed** (16 новых гейта + 4 новых route + все прежние bridge зелены → behavior-preservation).
- **ruff** по всем тронутым файлам: `All checks passed!`
- **dry-run** `train_onec_setfit.py --dry-run`: GT=68 (pos=41/neg=27), train 45 / test 23, форма корректна,
  предупреждение «<150 — разметить» сработало.
- **gate info**: enabled=False, setfit_installed=False, model_present=False → «гейт ВЫКЛЮЧЕН → route падает на TF-IDF».
- **eval behavior-preservation**: baseline vs `--setfit` (гейт on, модели нет → graceful TF-IDF) —
  **идентичны**: is_1c P/R/F1 = 0.976, route_class accuracy 0.971.

## Проверенные инварианты
- Выключенный гейт ⇒ поведение каскада идентично прежнему (тесты + eval).
- Graceful degradation на всех путях (нет env / нет deps / нет модели / исключение модели) → None → TF-IDF.
- Мягкий сигнал: промоут только `ask_1c`.

## Не покрыто (требует активации)
Реальный инференс/обучение SetFit — нужны `pip install setfit datasets` + разметка до ~150–300 (ADR-025 §Активация).
