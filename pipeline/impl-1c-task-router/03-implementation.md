# Классификатор сложности + маршрутизация — Кодирование

Реализовано (обратимо):

1. **`pipeline_1c_bridge.py`**: `_1C_STRONG` (regex уверенного 1С-маркера), `_EFFORT_CFG` (тюнинг-config),
   `estimate_effort(prompt, ttype, is_folder, cfg)` (эвристика трудозатрат → simple/medium/complex),
   `route_1c_task(prompt, is_folder, cfg)` (объединяет classify+estimate → `flow` ∈ none/ask_1c/auto/ask_flow/gated).
2. **`onec-task-input.py`**: переключён с `classify_1c_task` на `route_1c_task`; инъектит РЕКОМЕНДАЦИЮ потока
   (простая→`/run-1c-task`, средняя→спросить, сложная→гейт) + V.6 (тип/папка/prior) + хвост «эвристика < правило: сомнение → спросить».
3. **`code-skill-enforcer.py`** (durable-фикс): `_is_test_file` → tests/ exempt от content-based уровней A/A.1.
   Корень: Level A.1 форсил learning-loop на 1С-токенах в **тест-фикстурах** (ложно). Тот же exempt, что у z-ai-write-guard.
4. **Heuristic-fix (поймал live-smoke):** `light` (косметика) теперь **downgrade-only** (применяется лишь при
   `pos==0`), НЕ counterweight — иначе имя реквизита «Комментарий»/«Заголовок» в medium-задаче ложно занижало её в simple.

**Тесты:** +8 в `test_pipeline_1c_bridge.py` (estimate_effort банды + folder-bump; route none/auto/ask_flow/gated/ask_1c;
регресс «Комментарий»). Все collision-immune (чистые функции).

**Развилка маршрута (решение пользователя 2026-06-15):** простая→AUTO, средняя→спросить, сложная→гейт.
Всегда поверх: не-1С/сомнение-в-1С → спросить; сомнение-в-потоке → спросить.
