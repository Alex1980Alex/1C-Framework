#!/usr/bin/env python3
"""1С/RU web-search (ADR-040 Фазы 1-4 + authority/recency) — SearXNG -> RAG-Fusion(RRF) ->
TEI rerank -> [engagement] -> authority×recency re-rank.

Заменяет сломанный DuckDuckGo надёжным self-host бэкендом для 1С-домена (интернет + Infostart).
Цель: МАКС релевантность + актуальность + доверенный источник.
  Ф1 SearXNG (free, Yandex+) · Ф2 TEI rerank (bge-reranker-v2-m3, GPU) · Ф3 RAG-Fusion (RRF) ·
  Ф4 engagement-blend (--engagement, Scrapling Infostart views) ·
  authority×recency: final = relevance × trust(домен) × (1 + recency_boost) — по умолчанию ВКЛ.
Trust-иерархия = 1c-doc-research (its.1c.ru/v8.1c.ru > infostart/github > форумы > прочее).
Recency: SearXNG publishedDate (decay 30/90/180/365д) либо год в тексте (2026/2025); graceful.

Запуск:
  python scripts/onec_search.py "направление на разгрузку заблокированных ТС" --top 10
  python scripts/onec_search.py "печать ТТН снятие с хранения" --site infostart.ru --engagement
  python scripts/onec_search.py "тема" --no-fusion --no-rank --json

Сеть/браузер изолированы, graceful. Ядро (_rrf_fuse/_source_trust/_recency_boost/_apply_authority_recency/
_parse_infostart_views/to_markdown) — без сети, тестируемо. Env: SEARXNG_URL, TEI_RERANK_URL.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timezone
from pathlib import Path

# Reuse (hook-local shared): multi-query (Ф3) + blend (Ф4). append (НЕ insert0) — feedback-hook-src-shared-collision.
sys.path.append(str(Path(__file__).resolve().parent.parent / ".claude" / "hooks"))
try:
    from shared.engagement_rank import blended_score, expand_queries

    _HAS_ENGAGEMENT = True
except Exception:
    _HAS_ENGAGEMENT = False

SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://localhost:8888")
TEI_RERANK_URL = os.environ.get("TEI_RERANK_URL", "http://localhost:8082")
UA = "onec-search/1.0 (+pdf-vector-graph framework; ADR-040)"

# Доверенный источник (authority) — иерархия из 1c-doc-research. Более специфичные домены — ВЫШЕ
# (forum.infostart.ru проверяется раньше infostart.ru). Не найден → 0.7 (нейтрально-сниженный).
_DOMAIN_TRUST = {
    "its.1c.ru": 1.0,
    "v8.1c.ru": 1.0,
    "forum.infostart.ru": 0.8,
    "forum.mista.ru": 0.7,
    "infostart.ru": 0.9,
    "github.com": 0.9,
}


def _http(
    url: str, *, data: bytes | None = None, headers: dict | None = None, timeout: float = 15.0
):
    """GET/POST -> JSON, иначе None (graceful)."""
    try:
        req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except Exception:
        return None


def search_searxng(
    query: str, *, lang: str = "ru-RU", limit: int = 20, site: str | None = None
) -> list[dict]:
    """SearXNG JSON API -> [{title,url,content,engine,published}]. site -> ограничение домена."""
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
                "published": r.get("publishedDate") or r.get("pubdate") or "",
            }
        )
        if len(out) >= limit:
            break
    return out


def _rrf_fuse(result_lists: list[list[dict]], *, k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion по url-ключу (Ф3). Чистая."""
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
    """TEI /rerank (bge-reranker-v2-m3). TEI down -> исходный порядок (fallback)."""
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


def _source_trust(url: str) -> float:
    """Доверенность источника по домену (authority). Не найден -> 0.7."""
    u = (url or "").lower()
    for dom, w in _DOMAIN_TRUST.items():
        if dom in u:
            return w
    return 0.7


def _recency_boost(item: dict) -> float:
    """Свежесть -> boost [0..0.3]. publishedDate (decay 30/90/180/365д) либо год в тексте; graceful."""
    pd = item.get("published") or ""
    if pd:
        try:
            dt = datetime.fromisoformat(str(pd).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            age = (datetime.now(UTC) - dt).days
            if age < 30:
                return 0.30
            if age < 90:
                return 0.20
            if age < 180:
                return 0.10
            if age < 365:
                return 0.05
            return 0.0
        except Exception:
            pass
    text = f"{item.get('title', '')} {item.get('content', '')}"
    if "2026" in text:
        return 0.10
    if "2025" in text:
        return 0.05
    return 0.0


def _apply_authority_recency(ranked: list[dict]) -> list[dict]:
    """final = relevance × trust(домен) × (1 + recency_boost). Пересортировка. Не мутирует вход.

    relevance = blended (engagement-режим) либо rerank_score. По умолчанию ВКЛ (цель: max
    релевантность + актуальность + доверенный источник).
    """
    out: list[dict] = []
    for it in ranked:
        base = it.get("blended")
        if base is None:
            base = it.get("rerank_score")
        base = float(base) if base is not None else 0.0
        trust = _source_trust(it.get("url", ""))
        rec = _recency_boost(it)
        out.append(
            dict(
                it,
                trust=round(trust, 2),
                recency=round(rec, 2),
                final=round(base * trust * (1 + rec), 4),
            )
        )
    out.sort(key=lambda x: x.get("final") or 0.0, reverse=True)
    return out


def search(
    query: str,
    *,
    top: int = 10,
    lang: str = "ru-RU",
    site: str | None = None,
    fusion: bool = True,
    engagement: bool = False,
    rank: bool = True,
) -> list[dict]:
    """[Ф3 RAG-Fusion] -> Ф2 rerank -> [Ф4 engagement] -> [authority×recency]. rerank по ОРИГ. запросу."""
    limit = max(top * 2, 20)
    variants = expand_queries(query) if (fusion and _HAS_ENGAGEMENT) else [query]
    if len(variants) <= 1:
        hits = search_searxng(query, lang=lang, limit=limit, site=site)
    else:
        lists = [search_searxng(v, lang=lang, limit=limit, site=site) for v in variants]
        hits = _rrf_fuse(lists)[: max(top * 3, 30)]
    ranked = rerank_tei(query, hits, top=(top * 2) if rank else top)
    if engagement:
        ranked = _enrich_engagement(ranked)
    if rank:
        ranked = _apply_authority_recency(ranked)
    return ranked[:top]


def _parse_infostart_views(html: str) -> int | None:
    """Извлечь Просмотры из отрендеренного Infostart HTML. Чистая."""
    m = re.search(r"<b>\s*Просмотры\s*</b>\s*<i>\s*(\d+)\s*</i>", html)
    return int(m.group(1)) if m else None


def _infostart_engagement(url: str) -> int | None:
    """Ф4: рендер Infostart (Scrapling DynamicFetcher, JS) -> Просмотры. Graceful -> None. lazy-import. МЕДЛЕННО."""
    try:
        from scrapling.fetchers import DynamicFetcher

        page = DynamicFetcher.fetch(url, headless=True, network_idle=True)
        raw = page.body
        text = raw.decode("utf-8", "replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
        return _parse_infostart_views(text)
    except Exception:
        return None


def _enrich_engagement(ranked: list[dict], *, top_k: int = 5) -> list[dict]:
    """Ф4: infostart.ru в top_k -> views -> blend relevance(rerank) x engagement (engagement_rank)."""
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


def to_markdown(query: str, ranked: list[dict]) -> str:
    """Markdown-бриф (чистая функция)."""
    lines = [f"# Поиск 1С/RU: «{query}» (SearXNG + RAG-Fusion + reranker + authority×recency)", ""]
    if not ranked:
        lines.append("_Ничего не найдено (или SearXNG недоступен)._")
        return "\n".join(lines)
    for i, it in enumerate(ranked, 1):
        sc = it.get("final")
        if sc is None:
            sc = it.get("rerank_score")
        sc_s = f"score={sc}" if sc is not None else "(rerank off)"
        extra = ""
        if it.get("trust") is not None:
            extra += f", trust={it.get('trust')}"
        if it.get("recency"):
            extra += f", fresh={it.get('recency')}"
        if it.get("views") is not None:
            extra += f", 👁{it.get('views')}"
        lines.append(
            f"{i}. **[{it.get('engine', '?')}]** {it.get('title', '?')}  {sc_s}{extra}\n   {it.get('url', '')}"
        )
    return "\n".join(lines)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    ap = argparse.ArgumentParser(
        description="1С/RU web-search (ADR-040) — SearXNG + RAG-Fusion + reranker + authority×recency"
    )
    ap.add_argument("query", help="тема поиска")
    ap.add_argument("--top", type=int, default=10, help="сколько результатов (default 10)")
    ap.add_argument("--lang", default="ru-RU", help="язык SearXNG (default ru-RU)")
    ap.add_argument("--site", default=None, help="ограничить домен, напр. infostart.ru")
    ap.add_argument(
        "--no-fusion", action="store_true", help="отключить RAG-Fusion (одиночный запрос)"
    )
    ap.add_argument(
        "--no-rank", action="store_true", help="отключить authority×recency пересортировку"
    )
    ap.add_argument(
        "--engagement", action="store_true", help="Ф4: blend Infostart views (МЕДЛЕННО, Scrapling)"
    )
    ap.add_argument("--json", action="store_true", help="машинный JSON вместо Markdown")
    args = ap.parse_args()

    ranked = search(
        args.query,
        top=args.top,
        lang=args.lang,
        site=args.site,
        fusion=not args.no_fusion,
        engagement=args.engagement,
        rank=not args.no_rank,
    )
    if args.json:
        print(json.dumps({"query": args.query, "items": ranked}, ensure_ascii=False))
        return 0
    print(to_markdown(args.query, ranked))
    return 0


if __name__ == "__main__":
    sys.exit(main())
