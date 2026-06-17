# ADR-024: LLM-on-tail (stage-3) детектора 1С — РЕАЛИЗОВАНО+ПОДКЛЮЧЕНО, но ЗАБЛОКИРОВАНО (нет пригодной модели)

**Дата:** 2026-06-18
**Статус:** blocked (deferred-activation)
**Исследование:** [../cache/intent-detection-routing-best-practices.md](../cache/intent-detection-routing-best-practices.md)
**Связано:** ADR-023 (TEI rejected), #3 stage-2a (TF-IDF, ПРИНЯТО), [[feedback-no-paid-anthropic-api]]

## Контекст
После ADR-023 (frozen-эмбеддинги коллапсируют на коротком РУ 1С-тексте: cosine + centered + обученный
probe 5-fold F1 ≤0.76 < rule+TF-IDF 0.976) единственный путь различить near-domain хвост по СМЫСЛУ —
LLM-классификатор на ~few% неоднозначных кейсов (что пережили regex+TF-IDF). [own]

## Решение
LLM-on-tail **реализован и подключён**, но **НЕ активирован** — в окружении нет пригодной генеративной
instruct-модели. status=blocked. [exp]
- Код: [`onec_llm_tail.py`](../../../hooks/shared/onec_llm_tail.py) — `llm_classify(prompt)→bool|None` через
  `cheap_llm_call` (llm-rotation), structured-JSON, temp=0, один переиспользуемый event-loop, graceful→None.
  Framework-consistent: НЕ в синхронном hook-пути (хуки лёгкие, 5с); зовётся харнессом + Claude on-demand.
- Замер: [`scripts/eval_1c_detector.py --llm-tail`](../../../../scripts/eval_1c_detector.py) — на mid-band
  TF-IDF (0.40≤sem<0.85) зовёт классификатор. Готов к замеру, как только появится модель.

## Обоснование блокировки (эмпирика)
Ни один доступный провайдер llm-rotation не классифицирует 1С: [exp]
- **ollama `qwen2.5-coder:7b`** (UP, 0.2–1с): на ЛЮБОЙ вход отдаёт `{"is_1c": false}` — code-completion
  модель, не понимает RU 1С-семантику. «доработать проведение документа реализации» (учебная 1С) → false.
- **ollama `qwen3-embedding:8b`** — эмбеддер, НЕ генеративный (completion невозможен).
- **claude-cli-haiku/sonnet** (без ключа, CLI-подписка): спавнит ПОЛНЫЙ Claude-Code-агент ВНУТРИ этого
  репо → цепляет собственные хуки/Stop-gate, «Reached maximum turns (3)», 36с, мусорный текст. Непригоден.
- **anthropic-sonnet (HTTP)** — нужен `ANTHROPIC_API_KEY`, платный API запрещён ([[feedback-no-paid-anthropic-api]]).

## Последствия
**Положительные:** детектор остаётся на rule+TF-IDF (F1 0.976); LLM-проводка готова (graceful: None→TF-IDF,
прод не затронут). Знание + код сохранены — активация = одна команда + замер. [own]
**Отрицательные:** потолок precision TF-IDF (1 near-domain FP + 1 colloquial FN) пока не закрыт. Приемлемо:
промоут = `ask_1c` (вопрос), blast-radius безопасен. [own]

## Активация (условие снятия блокировки)
Любое из: [own]
1. `ollama pull qwen2.5:7b-instruct` (ИЛИ `llama3.1:8b`, `qwen2.5:3b-instruct`) — **instruct**, НЕ coder —
   и `LLM_ROTATION_PRIMARY_PROVIDER=ollama-local` → `eval_1c_detector.py --llm-tail` замерит выигрыш.
2. Починить claude-cli-провайдер (режим без спавна in-repo агента — direct API без Claude-Code-петли).
3. Разрешить платный API (сейчас запрещён).
Then: замер по харнессу #1 → если F1 растёт над 0.976 без роста FP → wire в прод как «route флагует хвост
(`llm_tail`), Claude/агент резолвит» (hook LLM не зовёт — framework design).

## Альтернативы (отклонены/отложены)
- SetFit (контрастный fine-tuning энкодера) — ~150–300 размеченных + тренировка + хостинг; масштабный путь.
- Reranker (cross-encoder) — [[feedback-ollama-reranker-pattern]]; но локально только coder-модель.
