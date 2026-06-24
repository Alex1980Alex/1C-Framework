#!/usr/bin/env python3
"""1С/RU web-search (ADR-040 Фаза 1-4) — SearXNG -> RAG-Fusion(RRF) -> TEI rerank -> engagement-blend.

Заменяет сломанный DuckDuckGo надёжным self-host бэкендом для поиска RU-интернета по 1С-темам
(+ Infostart через --site). Этапы:
  Ф1 SearXNG (free meta-search, Yandex+) ;  Ф2 TEI cross-encoder rerank (bge-reranker-v2-m3, GPU) ;
  Ф3 RAG-Fusion: multi-query (expand_queries, БЕЗ LLM) -> N SearXNG -> RRF(k=60) ;
  Ф4 engagement-blend (--engagement): Scrapling DynamicFetcher рендерит Infostart-страницы (JS),
     извлекает Просмотры -> blend relevance(rerank) x engagement через engagement_rank.blended_score.
Free/self-host (docker/docker-compose.search.yml), БЕЗ ключей/платных API.

Запуск:
  python scripts/onec_search.py "направление на разгрузку заблокированных ТС" --top 10
  python scripts/onec_search.py "печать ТТН снятие с хранения" --site infostart.ru --engagement
  python scripts/onec_search.py "тема" --no-fusion --json

Сеть/браузер изолированы, graceful: SearXNG down -> []; TEI down -> relevance-only; expand_queries
нет -> single; Scrapling/рендер падает -> engagement пропущен. Конфиг env: SEARXNG_URL
(http://localhost:8888), TEI_RERANK_URL (http://localhost:8082). Ядро (_rrf_fuse / _parse_infostart_views
/ rerank-слияние / markdown) тестируемо без сети/браузера.
⚠ --engagement МЕДЛЕННО: Scrapling рендерит каждую Infostart-страницу (~5-15с/стр), top_k=5.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

# Reuse (hook-local shared): multi-query (Ф3) + blend (Ф4). append (НЕ insert0) — feedback-hook-src-shared-collision.
sys.path.append(str(Path(__file__).resolve().parent.parent / ".claude" / "hooks"))
try:
    from shared.engagement_rank import blended_score, expand_queries

    _HAS_ENGAGEMENT = True
except Exception:  # graceful: одиночный запрос + без blend
    _HAS_ENGAGEMENT = False

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
    """Reciprocal Rank Fusion по url-ключу (Ф3). score = Σ 1/(k + rank); дедуп, сорт по убыв. Чистая."""
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
        return [dict(it, rerank_score=None) for it in items][:top]
    ranked: list[dict] = []
    for entry in res:
        idx = entry.get("index") if isinstance(entry, dict) else None
        if isinstance(idx, int) and 0 <= idx < len(items):
            ranked.append(dict(items[idx], rerank_score=round(float(entry.get("score") or 0), 4)))
    ranked.sort(key=lambda x: x.get("rerank_score") or 0.0, reverse=True)
    return ranked[:top]


def _parse_infostart_views(html: str) -> int | None:
    """Извлечь Просмотры из отрендеренного Infostart HTML (<b>Просмотры</b> <i>N</i>). Чистая, тестируемая."""
    m = re.search(r"<b>\s*Просмотры\s*</b>\s*<i>\s*(\d+)\s*</i>", html)
    return int(m.group(1)) if m else None


def _infostart_engagement(url: str) -> int | None:
    """Ф4: рендер Infostart-страницы (Scrapling DynamicFetcher, JS) -> Просмотры. Graceful -> None.

    Lazy-import Scrapling (тяжёлый браузерный стек) — грузится только при --engagement. МЕДЛЕННО (~5-15с).
    """
    try:
        from scrapling.fetchers import DynamicFetcher

        page = DynamicFetcher.fetch(url, headless=True, network_idle=True)
        raw = page.body
        text = raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
        return _parse_infostart_views(text)
    except Exception:
        return None


def _enrich_engagement(ranked: list[dict], *, top_k: int = 5) -> list[dict]:
    """Ф4: для infostart.ru в top_k -> views -> blend relevance(rerank) x engagement (engagement_rank).

    Нет engagement_rank / ни одного views -> вернуть как есть (relevance-only). Не мутирует вход.
    """
    if not _HAS_ENGAGEMENT:
        return ranked
    out = [dict(it) for it in ranked]
    views: list[int] = []
    for it in out[:top_k]:
        if "infostart.ru" in (it.get("url") or ""):
            v = _infostart_engagement(it["url"])
            if v is not None:
                it["views"] = v
                views.append(v)
    if not views:
        return ranked
    cap = float(max(views))
    for it in out:
        rel = it.get("rerank_score")
        rel = float(rel) if rel is not None else 0.0
        it["blended"] = blended_score(rel, float(it.get("views") or 0), engagement_cap=cap)
    out.sort(key=lambda x: x.get("blended") or 0.0, reverse=True)
    return out


def search(
    query: str,
    *,
    top: int = 10,
    lang: str = "ru-RU",
    site: str | None = None,
    fusion: bool = True,
    engagement: bool = False,
) -> list[dict]:
    """Пайплайн: [Ф3 RAG-Fusion] -> Ф2 TEI rerank -> top [-> Ф4 engagement-blend]. rerank по ОРИГ. запросу."""
    limit = max(top * 2, 20)
    variants = expand_queries(query) if (fusion and _HAS_ENGAGEMENT) else [query]
    if len(variants) <= 1:
        hits = search_searxng(query, lang=lang, limit=limit, site=site)
    else:
        lists = [search_searxng(v, lang=lang, limit=limit, site=site) for v in variants]
        hits = _rrf_fuse(lists)[: max(top * 3, 30)]
    ranked = rerank_tei(query, hits, top=top)
    if engagement:
        ranked = _enrich_engagement(ranked)
    return ranked


def to_markdown(query: str, ranked: list[dict]) -> str:
    """Markdown-бриф (чистая функция)."""
    lines = [f"# Поиск 1С/RU: «{query}» (SearXNG + RAG-Fusion + bge-reranker)", ""]
    if not ranked:
        lines.append("_Ничего не найдено (или SearXNG недоступен)._")
        return "\n".join(lines)
    for i, it in enumerate(ranked, 1):
        sc = it.get("rerank_score")
        sc_s = f"score={sc}" if sc is not None else "(rerank off)"
        v = it.get("views")
        v_s = f", 👁{v}" if v is not None else ""
        lines.append(
            f"{i}. **[{it.get('engine', '?')}]** {it.get('title', '?')}  {sc_s}{v_s}\n   {it.get('url', '')}"
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
    ap.add_argument("--engagement", action="store_true", help="Ф4: blend Infostart views (МЕДЛЕННО, Scrapling-рендер)")
    ap.add_argument("--json", action="store_true", help="машинный JSON вместо Markdown")
    args = ap.parse_args()

    ranked = search(
        args.query, top=args.top, lang=args.lang, site=args.site,
        fusion=not args.no_fusion, engagement=args.engagement,
    )
    if args.json:
        print(json.dumps({"query": args.query, "items": ranked}, ensure_ascii=False))
        return 0
    print(to_markdown(args.query, ranked))
    return 0


if __name__ == "__main__":
    sys.exit(main())
