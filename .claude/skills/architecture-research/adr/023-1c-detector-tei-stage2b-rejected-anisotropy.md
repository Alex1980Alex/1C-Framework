# ADR-023: TEI-эскалация (stage-2b) детектора 1С-задач — ОТКЛОНЕНО (анизотропия эмбеддингов)

**Дата:** 2026-06-17
**Статус:** rejected
**Исследование:** [../cache/intent-detection-routing-best-practices.md](../cache/intent-detection-routing-best-practices.md)
**Связано:** ADR-017/018 (пайплайн), #3 stage-2a (TF-IDF semantic fallback, ПРИНЯТО)

## Контекст
Детектор 1С-задачи (`classify_1c_task`/`route_1c_task`) — каскад best-practice (hybrid cascade,
[web: arxiv 2410.01627]): regex (stage-1) → TF-IDF (stage-2a, ПРИНЯТО) → **TEI-эмбеддинги (stage-2b)**.
Гипотеза stage-2b: bag-of-words TF-IDF не различает near-domain РУ-текст по СМЫСЛУ («обмен данными 1С»
vs «обмен микросервисами kafka» лексически совпадают), а эмбеддинги Qwen3 различат → закроют потолок
precision TF-IDF (1 FP «загрузка данных в хранилище» + разговорный FN «лабанализ»). [own]

## Решение
**stage-2b НЕ включён в `route_1c_task`.** Реализация (TEI `/embed` через urllib, MRL-1024+renorm,
in-memory cosine по 40 utterance-эмбеддингам) написана и доступна через CLI (`build-emb`/`emb`
в `onec_semantic_fallback.py`), но в production-путь НЕ заведена. Финальный семантический слой —
TF-IDF stage-2a. [own]

## Обоснование (замер на golden-set, TEI Qwen3-Embedding-8B live)
Эмбеддинги **анизотропны** на коротком РУ 1С-тексте — не разделяют негативы и позитивы: [exp]
- raw cosine: негативы «qdrant sparse vectors» **0.889**, near-domain **0.899**, «лабораторный анализ»
  **0.844** — НАРАВНЕ с истинными позитивами (0.85–0.94). Нет порога без массового overlap.
- centering (вычитание corpus-mean, стандартный фикс анизотропии): overlap сохраняется (негатив
  «лабораторный анализ» 0.677 > многих позитивов; один явный FN «почему не печатается» упал 0.873→0.450).
- Контраст: **TF-IDF stage-2a** на тех же кейсах разделяет ЧИСТО (FN-парафразы 0.87–0.92, негативы ≤0.43).

Согласуется с задокументированным [[feedback-bsl-embedding-collapse]] (Qwen3 на кириллице/повторяющемся
синтаксисе: eff_rank ~6%, anisotropy ~0.59, recall ceiling). [exp]

## Последствия
**Положительные:** не тащим в UPS-хук (5с) сетевой вызов TEI + зависимость от сервиса ради нулевого
выигрыша; precision/recall детектора держит TF-IDF (F1 0.976). Знание сохранено — не будет наивного
ре-эксперимента. [own]
**Отрицательные:** потолок TF-IDF остаётся (1 FP near-domain + 1 colloquial FN). Приемлемо: промоут =
`ask_1c` (вопрос, не прогон); blast-radius безопасен ([[feedback-1c-detection-judgment-mine]]). [own]

## Альтернативы (для будущего пересмотра)
1. **Reranker** (cross-encoder, напр. Ollama qwen2.5-coder — дал +5–10pp на BSL, [[feedback-ollama-reranker-pattern]])
   вместо bi-encoder cosine — может различить near-domain. Тяжелее, отдельный сервис. [own]
2. **Whitening/ABTT** (более агрессивная декорреляция, чем centering). Не пробовано. [own]
3. **Domain-tuned эмбеддер** на 1С-корпусе. Дорого. [own]
Условие пересмотра: появится reranker в hot-path-бюджете ИЛИ замер покажет, что near-domain FP в проде
заметны (сейчас — нет, golden-set 1 FP).
