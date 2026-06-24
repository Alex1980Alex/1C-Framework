#!/usr/bin/env python3
"""1С/RU web-search (ADR-040 Фаза 1+2+3) — SearXNG -> RAG-Fusion(RRF) -> TEI cross-encoder rerank.

Заменяет сломанный DuckDuckGo надёжным self-host бэкендом для поиска RU-интернета по 1С-темам
(+ Infostart через --site). Фаза 3: multi-query expansion (expand_queries, БЕЗ LLM) -> N SearXNG-
запросов -> RRF-слияние (k=60) -> rerank bge-reranker-v2-m3 через TEI для максимальной релевантности.
Free/self-host (docker/docker-compose.search.yml), БЕЗ ключей/платных API.

Запуск:
  python scripts/onec_search.py "направление на разгрузку заблокированных ТС" --top 10
  python scripts/onec_search.py "печать ТТН снятие с хранения" --site infostart.ru --json
  python scripts/onec_search.py "тема" --no-fusion          # одиночный запрос (без RAG-Fusion)

Сеть изолирована (search_searxng/rerank_tei), graceful: SearXNG down -> []; TEI down -> порядок
SearXNG (relevance-only fallback); expand_queries недоступен -> одиночный запрос. Конфиг через env:
SEARXNG_URL (default http://localhost:8888), TEI_RERANK_URL (default http://localhost:8082).
Ядро (_rrf_fuse / rerank-слияние / markdown) тестируемо без сети.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# Phase 3 (RAG-Fusion): переиспользуем детерминированный multi-query из hook-local shared (без LLM).
sys.path.append(str(Path(__file__).resolve().parent.parent / ".claude" / "hooks"))
try:
    from shared.engagement_rank import expand_queries

    _HAS_EXPAND = True
except Exception:  # graceful: одиночный запрос
    _HAS_EXPAND = False

SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://localhost:8888")
TEI_RERANK_URL = os.environ.get("TEI_RERANK_URL", "http://localhost:8082")
UA = "onec-search/1.0 (+pdf-vector-graph framework; ADR-040)"


def _http(url: str, *, data: bytes | None = None, headers: dict | None = None, timeout: float = 15.0):
    """GET (data=None) или POST (data=bytes) -> распарсенный JSON, иначе None (graceful)."""
    try:
        req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except Exception:
        return None


def search_searxng(query: str, *, lang: str = "ru-RU", limit: int = 20, site: str | None = None) -> list[dict]:
    """SearXNG JSON API -> [{title,url,content,engine}]. site -> ограничение домена (site:)."""
    q = f"site:{site} {query}" if site else query
    url = f"{SEARXNG_URL}/search?q={urllib.parse.quote(q)}&format=json&language={lang}"
    data = _http(url)
    out: list[dict] = []
    for r in (data or {}).get("results", []) or []:
        title = (r.get("title") or "").strip()
        if not title:
            continue
        out.append(
            {
                "title": title,
                "url": r.get("url") or "",
                "content": (r.get("content") or "").strip(),
                "engine": r.get("engine") or "?",
            }
        )
        if len(out) >= limit:
            break
    return out


def _rrf_fuse(result_lists: list[list[dict]], *, k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion по url-ключу (Фаза 3). score = Σ 1/(k + rank); дедуп, сорт по убыв.

    Документ, встреченный в нескольких variant-списках/высоко по рангу, поднимается. Чистая функция.
    """
    scores: dict[str, float] = {}
    best: dict[str, dict] = {}
    for lst in result_lists:
        for rank, it in enumerate(lst):
            key = it.get("url") or it.get("title")
            if not key:
                continue
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            if key not in best:
                best[key] = it
    fused = [dict(best[key], rrf_score=round(scores[key], 5)) for key in scores]
    fused.sort(key=lambda x: x["rrf_score"], reverse=True)
    return fused


def rerank_tei(query: str, items: list[dict], *, top: int = 10) -> list[dict]:
    """Переранжировать через TEI /rerank (bge-reranker-v2-m3). TEI down -> исходный порядок (fallback)."""
    if not items:
        return []
    texts = [f"{it.get('title', '')} {it.get('content', '')}".strip() for it in items]
    body = json.dumps({"query": query, "texts": texts, "return_text": False}).encode("utf-8")
    res = _http(f"{TEI_RERANK_URL}/rerank", data=body, headers={"Content-Type": "application/json"})
    if not isinstance(res, list):
        # graceful: TEI недоступен -> relevance-only порядок входа
        return [dict(it, rerank_score=None) for it in items][:top]
    ranked: list[dict] = []
    for entry in res:
        idx = entry.get("index") if isinstance(entry, dict) else None
        if isinstance(idx, int) and 0 <= idx < len(items):
            ranked.append(dict(items[idx], rerank_score=round(float(entry.get("score") or 0), 4)))
    ranked.sort(key=lambda x: x.get("rerank_score") or 0.0, reverse=True)
    return ranked[:top]


def search(
    query: str, *, top: int = 10, lang: str = "ru-RU", site: str | None = None, fusion: bool = True
) -> list[dict]:
    """Пайплайн: [RAG-Fusion: expand_queries -> N SearXNG -> RRF] -> TEI rerank -> top.

    fusion=False или нет expand_queries -> одиночный запрос (Фаза 1+2). rerank всегда по ОРИГ. запросу.
    """
    limit = max(top * 2, 20)
    variants = expand_queries(query) if (fusion and _HAS_EXPAND) else [query]
    if len(variants) <= 1:
        hits = search_searxng(query, lang=lang, limit=limit, site=site)
    else:
        lists = [search_searxng(v, lang=lang, limit=limit, site=site) for v in variants]
        hits = _rrf_fuse(lists)[: max(top * 3, 30)]
    return rerank_tei(query, hits, top=top)


def to_markdown(query: str, ranked: list[dict]) -> str:
    """Markdown-бриф (чистая функция)."""
    lines = [f"# Поиск 1С/RU: «{query}» (SearXNG + RAG-Fusion + bge-reranker)", ""]
    if not ranked:
        lines.append("_Ничего не найдено (или SearXNG недоступен)._")
        return "\n".join(lines)
    for i, it in enumerate(ranked, 1):
        sc = it.get("rerank_score")
        sc_s = f"score={sc}" if sc is not None else "(rerank off)"
        lines.append(
            f"{i}. **[{it.get('engine', '?')}]** {it.get('title', '?')}  {sc_s}\n   {it.get('url', '')}"
        )
    return "\n".join(lines)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    ap = argparse.ArgumentParser(description="1С/RU web-search (ADR-040) — SearXNG + RAG-Fusion + TEI reranker")
    ap.add_argument("query", help="тема поиска")
    ap.add_argument("--top", type=int, default=10, help="сколько результатов (default 10)")
    ap.add_argument("--lang", default="ru-RU", help="язык SearXNG (default ru-RU)")
    ap.add_argument("--site", default=None, help="ограничить домен, напр. infostart.ru")
    ap.add_argument("--no-fusion", action="store_true", help="отключить RAG-Fusion (одиночный запрос)")
    ap.add_argument("--json", action="store_true", help="машинный JSON вместо Markdown")
    args = ap.parse_args()

    ranked = search(args.query, top=args.top, lang=args.lang, site=args.site, fusion=not args.no_fusion)
    if args.json:
        print(json.dumps({"query": args.query, "items": ranked}, ensure_ascii=False))
        return 0
    print(to_markdown(args.query, ranked))
    return 0


if __name__ == "__main__":
    sys.exit(main())
