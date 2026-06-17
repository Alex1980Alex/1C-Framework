# ADR-024: LLM-on-tail (stage-3) детектора 1С — ИЗМЕРЕНО на qwen2.5:7b → net-neutral (модель слаба)

**Дата:** 2026-06-18
**Статус:** rejected (для доступной модели; проводка retained opt-in под более сильную)
**Исследование:** [../cache/intent-detection-routing-best-practices.md](../cache/intent-detection-routing-best-practices.md)
**Связано:** ADR-023 (TEI rejected), #3 stage-2a (TF-IDF, ПРИНЯТО), [[feedback-no-paid-anthropic-api]]

## Контекст
После ADR-023 (frozen-эмбеддинги коллапсируют: cosine + centered + обученный probe 5-fold F1 ≤0.76 <
rule+TF-IDF 0.976) — единственный путь различить near-domain хвост по СМЫСЛУ — LLM-классификатор на
~few% неоднозначных кейсов (что пережили regex+TF-IDF). [own]

## Решение
LLM-on-tail **реализован, подключён и ИЗМЕРЕН** на `qwen2.5:7b` (instruct, скачана 2026-06-18). Результат:
**не улучшает TF-IDF baseline 0.976** → **НЕ принят в production-путь**. Проводка сохранена opt-in
(`scripts/eval_1c_detector.py --llm-tail`) под будущую более сильную модель — активация = смена
`ONEC_TAIL_MODEL`. [exp]
- Код: [`onec_llm_tail.py`](../../../hooks/shared/onec_llm_tail.py) — `llm_classify(prompt)→bool|None`
  **прямым вызовом Ollama** (`/api/chat`, `format=json`, sync urllib), НЕ через llm-rotation: дефолтный
  primary llm-rotation = claude-cli, спавнящий Claude-агента ВНУТРИ репо (мусор + max-turns), а
  structured-output сервис не пробрасывает. `format=json` форсит валидный JSON. graceful → None.

## Обоснование (замер на golden-set, qwen2.5:7b live)
**Net-neutral + недетерминизм:** [exp]
- `eval --llm-tail` 6 идентичных прогонов (temp=0): **5× F1=0.976** (== baseline), **1× 0.988** (fluke).
  GPU-недетерминизм на пограничных логитах → модель флипает mid-band кейсы run-to-run («лабораторный
  анализ»→ask vs «ТС заблокировано»→none), но чинит НЕ больше, чем ломает → стабильный net = 0.
- Ручные 10 кейсов через `llm_classify`: **6/10**, противоречиво — zero-shot JSON был true-biased (4/8),
  сбалансированный промпт перекосил в false-bias (путает явные 1С «доработать проведение»/«печатная
  форма ТН» → false). Надёжной дискриминации near-domain нет.
- Контраст: rule+TF-IDF **детерминирован** и держит **0.976**. LLM на available-модели его не бьёт.

`qwen2.5-coder:7b` (прежний default ollama) ещё хуже — `{"is_1c": false}` на ВСЁ (code-completion).

## Последствия
**Положительные:** детектор остаётся на rule+TF-IDF (F1 0.976, детерминирован); проводка корректна и
готова (смена 1 env-переменной) под более сильную модель; харнесс `--llm-tail` измеряет любую новую. [own]
**Отрицательные:** near-domain потолок TF-IDF не закрыт. Приемлемо: промоут = `ask_1c` (вопрос), даже
ошибочный флип LLM деградирует в вопрос, не в авто-прогон — blast-radius безопасен. [own]

## Активация (условие пересмотра)
Нужна **более сильная модель** (available qwen2.5:7b измеренно недостаточна): [own]
1. Крупнее instruct локально: `ollama pull qwen2.5:32b` / `qwen2.5:72b` (нужен VRAM; сейчас 7.2 ГБ
   свободно — 32B не влезет на GPU, пойдёт в RAM-спилл, медленно) → `ONEC_TAIL_MODEL` + `--llm-tail`.
2. **SetFit** — контрастный fine-tuning энкодера на ~150–300 размеченных (адаптирует пространство под
   задачу, бьёт коллапс там, где frozen-эмбеддинги и слабый LLM не справились). Масштабный путь.
3. Платный API (Claude/GPT) — запрещён ([[feedback-no-paid-anthropic-api]]).

## Альтернативы (отклонены/отложены)
- TEI-эмбеддинги (cosine/probe) — ADR-023, коллапс.
- Reranker (cross-encoder) — [[feedback-ollama-reranker-pattern]]; локально только coder-модель.
