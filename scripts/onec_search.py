#!/usr/bin/env python3
"""1С/RU web-search (ADR-040 Фаза 1+2) — SearXNG (free meta-search, Yandex) -> TEI cross-encoder rerank.

Заменяет сломанный DuckDuckGo-скрейп надёжным self-host бэкендом для поиска RU-интернета по 1С-темам
(+ Infostart через --site); переранжирует результаты bge-reranker-v2-m3 через TEI для максимальной
релевантности. Free/self-host (docker/docker-compose.search.yml), БЕЗ ключей/платных API.

Запуск:
  python scripts/onec_search.py "направление на разгрузку заблокированных ТС" --top 10
  python scripts/onec_search.py "печать ТТН снятие с хранения" --site infostart.ru --json

Сеть изолирована (search_searxng/rerank_tei), graceful: SearXNG down -> []; TEI down -> порядок
SearXNG (relevance-only fallback). Конфиг через env: SEARXNG_URL (default http://localhost:8888),
TEI_RERANK_URL (default http://localhost:8082). Ядро (rerank-слияние/markdown) тестируемо без сети.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request

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


def rerank_tei(query: str, items: list[dict], *, top: int = 10) -> list[dict]:
    """Переранжировать через TEI /rerank (bge-reranker-v2-m3). TEI down -> исходный порядок (fallback)."""
    if not items:
        return []
    texts = [f"{it.get('title', '')} {it.get('content', '')}".strip() for it in items]
    body = json.dumps({"query": query, "texts": texts, "return_text": False}).encode("utf-8")
    res = _http(f"{TEI_RERANK_URL}/rerank", data=body, headers={"Content-Type": "application/json"})
    if not isinstance(res, list):
        # graceful: TEI недоступен -> relevance-only порядок SearXNG
        return [dict(it, rerank_score=None) for it in items][:top]
    ranked: list[dict] = []
    for entry in res:
        idx = entry.get("index") if isinstance(entry, dict) else None
        if isinstance(idx, int) and 0 <= idx < len(items):
            ranked.append(dict(items[idx], rerank_score=round(float(entry.get("score") or 0), 4)))
    ranked.sort(key=lambda x: x.get("rerank_score") or 0.0, reverse=True)
    return ranked[:top]


def search(query: str, *, top: int = 10, lang: str = "ru-RU", site: str | None = None) -> list[dict]:
    """SearXNG -> TEI rerank -> top. Тонкий пайплайн (сеть в search_searxng/rerank_tei)."""
    hits = search_searxng(query, lang=lang, limit=max(top * 2, 20), site=site)
    return rerank_tei(query, hits, top=top)


def to_markdown(query: str, ranked: list[dict]) -> str:
    """Markdown-бриф (чистая функция)."""
    lines = [f"# Поиск 1С/RU: «{query}» (SearXNG + bge-reranker)", ""]
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
    ap = argparse.ArgumentParser(description="1С/RU web-search (ADR-040) — SearXNG + TEI reranker")
    ap.add_argument("query", help="тема поиска")
    ap.add_argument("--top", type=int, default=10, help="сколько результатов (default 10)")
    ap.add_argument("--lang", default="ru-RU", help="язык SearXNG (default ru-RU)")
    ap.add_argument("--site", default=None, help="ограничить домен, напр. infostart.ru")
    ap.add_argument("--json", action="store_true", help="машинный JSON вместо Markdown")
    args = ap.parse_args()

    ranked = search(args.query, top=args.top, lang=args.lang, site=args.site)
    if args.json:
        print(json.dumps({"query": args.query, "items": ranked}, ensure_ascii=False))
        return 0
    print(to_markdown(args.query, ranked))
    return 0


if __name__ == "__main__":
    sys.exit(main())
