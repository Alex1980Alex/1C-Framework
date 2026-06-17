# 02 — Дизайн: #3 каскад semantic fallback (TF-IDF → TEI) + #4 лемматизация

## Принцип (best practice: hybrid cascade)
Regex (stage-1) — высокая precision, низкий recall на парафразах. Каскад добавляет stage-2
**только на НЕуверенных входах** (`confidence < 0.7` после #2): regex дал `none`/`ask` → пробуем
семантику. Семантика = **МЯГКИЙ сигнал**: повышает recall (промоут `is_1c`), но НЕ делает `confident`
(остаётся `ask_1c`) — инвариант безопасности сохраняется (семантический матч ≠ твёрдый маркер).

## Stage-2a — TF-IDF (in-process, offline, этот инкремент)
- **Route-определения:** [`data/1c-utterances.json`](../../data/1c-utterances.json) — ~40 курируемых
  1С-фраз, **ОТДЕЛЬНЫ от GT** (иначе утечка в eval).
- **Модуль** [`shared/onec_semantic_fallback.py`](../../.claude/hooks/shared/onec_semantic_fallback.py):
  - токены = слова + **char 3-граммы** (морфология русского без лемматизации — «проведении»/«проведение»
    делят n-граммы);
  - `build_index` (offline CLI) → TF-IDF idf + per-utterance векторы → `data/1c-semantic-index.json`;
  - `semantic_sim(text)` (runtime) = **max cosine** к route-фразам; чистый stdlib (math/Counter), без
    sklearn в hot-path; кэш индекса на процесс; graceful (нет индекса → 0.0).
- **Интеграция** `route_1c_task`: `if confidence<0.7: sem=semantic_sim(prompt); if sem≥THRESHOLD →
  is_1c=True, flow=ask_1c` (промоут FN из `none`). Порог тюнится по харнессу #1 (баланс recall↑ vs FP).
- **Латентность:** ~мс (40 фраз), только на non-confident; graceful-degrade.

## Stage-2b — TEI Qwen3 + Qdrant (следующий инкремент)
На СРЕДНЕЙ TF-IDF-близости (mid-band) — эскалация на реальные эмбеддинги через существующий
`prework-similar-code`/TEI. Только на uncertain + кэш + graceful (TEI down → остаёмся на TF-IDF-вердикте).

## #4 — Лемматизация (pymorphy3, следующий инкремент)
Заменить стем-подстроки в `_TASK_VERB`/`_1C_SIGNAL` лемма-матчингом (чище морфология, ↓FP/↓FN —
напр. «перепроведении» → лемма «перепровести»). Зависимость + ~мс; lazy + graceful fallback на regex.

## Тест-план (этот инкремент)
- harness baseline (R=0.927, 3 FN) → после TF-IDF: ожидаем recall↑ (промоут FN из `none`→`ask`)
  БЕЗ роста FP на негативах; tune THRESHOLD.
- unit: semantic_sim высок на парафразе ТЗ, низок на не-1С; промоут FN; негативы остаются `none`;
  confident-путь не тронут (sem не вызывается).
- 54+ unit зелёные, ruff/compile, code-verify, eval --split test (held-out, utterances≠GT).
