# Классификатор сложности + маршрутизация — Тестирование (DoD пройден)

| Проверка | DoD | Результат |
|---|---|---|
| unit | pytest | **28 passed** (20 прежних + 8 новых) |
| collision-immune | full `-m unit -k "pipeline or tool_usage"` | **61 passed, 1 skipped, 0 collision** |
| ruff / compile | clean | All passed / OK (bridge, onec-task-input, enforcer) |
| route — 5 потоков (чисто UTF-8, in-process) | корректность | complex/7→**gated**; medium/4→**ask_flow**; weak/1→**ask_1c**; simple/2→**auto**; non-1С→**none** |
| enforcer `_is_test_file` | exempt | tests/→True, src/.claude→False (синтетика) |
| хук `onec-task-input` | live (UTF-8 stdin) | инъектит маршрут+оценку для 1С, молчит на не-1С |

**Live-smoke поймал реальный баг эвристики** (зачем и нужна живая проверка): «Комментарий» (имя реквизита)
матчил `light`-сигнал и занижал medium→simple. Исправлено (light = downgrade-only) + регресс-тест.
Первый прогон smoke также показал: **Bash-tool корёжит кириллицу в inline-аргументах** (mojibake) — верный
способ проверки хука = UTF-8-файл payload + python subprocess (bytes), НЕ `printf` с кириллицей.

**Вердикт: DONE.** Классификатор трудозатрат (simple/medium/complex) + маршрутизация (AUTO/ask/гейт) собраны и
проведены в `onec-task-input`. Развилка пользователя соблюдена.

**Граница (честно):** оценка трудозатрат — ЭВРИСТИКА (keyword-сигналы + config-веса, тюнятся); это рекомендация,
финальное решение и ASK — за Claude (правило пользователя «сомнение → спросить» поверх эвристики). Калибровка
весов/порогов — по мере накопления реальных задач (config `_EFFORT_CFG`).
