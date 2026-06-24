# ADR-040: Стек повышения релевантности поиска 1С (Infostart + интернет)

**Дата:** 2026-06-24
**Статус:** proposed
**Исследование:** [cache/1c-search-relevance-stack-2026.md](../cache/1c-search-relevance-stack-2026.md)

## Контекст

~90% работы проекта — 1С (RU-домен: Infostart + рунет), но `ecosystem_scan` (гл.44) — англоязычный (HN/SO/GitHub/Lobsters/Dev.to), на 1С-теме даёт пусто (ADR-039, проверено live). Текущий 1С-research (`1c-doc-research` Фаза 2) = `WebSearch site:infostart.ru` — даёт title/URL, но без ранжирования по релевантности+engagement; бесплатный DuckDuckGo-скрейп **сломан** (anti-bot). Нужен максимум релевантности и полезности для RU/1С-поиска.

Имеющийся фундамент: Qwen3-Embedding-8B через **TEI**, Qdrant hybrid (dense+BM25, RRF/DBSF), Ollama LLM-реранкер, приём `engagement_rank` (relevance×engagement, query-adaptive), индексированные платформенные доки 1С (`POST /search/ask`).

## Решение (ROI-ранжированное, фазами)

Не строить «ещё один ecosystem_scan», а **усилить релевантность 1С-поиска** связкой проверенных кирпичей поверх имеющегося стека:

| Приоритет | Что | Зачем (числа [web]) | Реюз |
|---|---|---|---|
| **1 (must)** | **SearXNG** self-hosted (Docker, JSON API, движок **Yandex**) | заменяет сломанный DDG; бесплатный RU-web-поиск с метаданными [searxng] | новый backend для `1c-doc-research` Фаза 2 |
| **2 (must)** | **bge-reranker-v2-m3** cross-encoder через **TEI** | reranking — крупнейший единичный прирост; multilingual, 278M, быстрый [HF] | TEI уже развёрнут |
| **3 (high)** | **RAG-Fusion** (multi-query 3-5 + RRF) | +19% nDCG@10, +18% MRR [arxiv 2402.03367] | `engagement_rank.expand_queries` + RRF уже есть |
| **4 (high)** | **trafilatura** — извлечение текста + **engagement** (рейтинг/просмотры) с Infostart-страниц | даёт сигнал для relevance×engagement ранжирования | `engagement_rank.rank_items` |
| **5 (opt)** | **Contextual Retrieval** (Anthropic) для **индексированных** 1С-доков | −49%…−67% failed retrieval [anthropic] | слой `POST /search/ask`, не live-web |

**НЕ менять** embedding-модель (Qwen3-8B multilingual-сильна; для RU-текста релевантность вытягивает cross-encoder-реранкер, а не смена эмбеддера — смена только после RU-eval на RusBEIR).

**Целевой конвейер:** запрос (RU 1С) → SearXNG(Yandex+) + Infostart [multi-query → RRF] → trafilatura (текст+engagement) → bge-reranker-v2-m3 (relevance) → blend relevance×engagement×recency (`engagement_rank`) → top-N бриф. Встраивается в `1c-doc-research` Фаза 2 (не отдельный инструмент-дубль).

## Последствия

**Плюсы:** релевантность RU/1С-поиска растёт по измеренным рычагам (reranking + RAG-Fusion + contextual); всё free/self-host (SearXNG/TEI/trafilatura) — согласуется с cost-conscious; максимальный реюз (TEI, engagement_rank, RRF) — минимум нового кода; покрывает 90%-домен (1С), где ecosystem_scan бесполезен.

**Минусы:** SearXNG = Docker-сервис (эксплуатация, риск блокировок движков); cross-encoder реранкинг добавляет латентность (батч-rerank top-K); trafilatura-скрейп Infostart хрупок к смене вёрстки + ToS-серость (только публичное, без обхода paywall); Contextual Retrieval требует ре-индексации + LLM-проход.

## Альтернативы (отклонены)

- **Расширять ecosystem_scan на 1С** — отклонено: его источники англоязычны (домен-мисматч).
- **Сменить эмбеддер на bge-m3/USER** — отклонено без RU-eval (Qwen3-8B уже силён; риск регресса BSL-индекса).
- **Платные Firecrawl/Brave/Yandex API** — отклонено: против cost-conscious; SearXNG+trafilatura закрывают бесплатно.
- **Прямой ddgs/duckduckgo_search** — отклонено: хронический `202 Ratelimit` [github issues].

## Связанные файлы
- Усиление: `.claude/skills/1c-doc-research/SKILL.md` (Фаза 2), `shared/engagement_rank.py`, TEI-инфра.
- Соседнее: ADR-039 (ecosystem_scan, англо-домен), гл.31 (Qwen3/TEI), гл.44.
