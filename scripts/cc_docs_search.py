#!/usr/bin/env python3
"""cc_docs_search — семантический поиск по документации Claude Code (code.claude.com/docs).

index:  sitemap (EN) -> urllib GET -> trafilatura markdown -> chunk -> TEI embed -> Qdrant `cc_docs`.
search: query -> TEI embed (Qwen3 query-instruct) -> Qdrant search -> top chunks (url+heading+snippet).

Reuse: TEI (Qwen3-Embedding-8B, :8080), Qdrant (:6333), trafilatura. Публичные доки — без браузера.

  python scripts/cc_docs_search.py index [--limit N]
  python scripts/cc_docs_search.py search "how to create a hook" [--top 8]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request

SITEMAP = "https://code.claude.com/docs/sitemap.xml"
TEI = os.environ.get("TEI_URL", "http://localhost:8080")
QDRANT = os.environ.get("QDRANT_URL", "http://localhost:6333")
COLL = "cc_docs"
UA = {"User-Agent": "Mozilla/5.0 (cc-docs-index)"}
QWEN3_QUERY = "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: "


def _get(url: str, timeout: float = 30) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def _req(method: str, url: str, obj=None, timeout: float = 120):
    data = json.dumps(obj).encode() if obj is not None else None
    r = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **UA}, method=method)
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        body = resp.read()
    return json.loads(body) if body else {}


def tei_embed(texts: list[str]) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), 32):  # batch <=32 (TEI 413 при >32)
        out.extend(_req("POST", f"{TEI}/embed", {"inputs": texts[i : i + 32]}))
    return out


def en_urls(limit: int | None = None) -> list[str]:
    sm = _get(SITEMAP).decode("utf-8", "replace")
    urls = sorted({u for u in re.findall(r"<loc>([^<]+)</loc>", sm) if "/docs/en/" in u})
    return urls[:limit] if limit else urls


def chunk_md(md: str, max_len: int = 1500) -> list[str]:
    chunks: list[str] = []
    for part in re.split(r"\n(?=#{1,3} )", md):
        part = part.strip()
        if not part:
            continue
        if len(part) <= max_len:
            chunks.append(part)
        else:
            for i in range(0, len(part), max_len):
                chunks.append(part[i : i + max_len])
    return chunks


def _heading(chunk: str) -> str:
    m = re.match(r"#{1,3} (.+)", chunk)
    return m.group(1).strip() if m else ""


def _pid(url: str, idx: int) -> int:
    return int(hashlib.md5(f"{url}#{idx}".encode()).hexdigest()[:15], 16)


def _ensure_collection(dim: int) -> None:
    cols = [c["name"] for c in _req("GET", f"{QDRANT}/collections")["result"]["collections"]]
    if COLL not in cols:
        _req("PUT", f"{QDRANT}/collections/{COLL}", {"vectors": {"size": dim, "distance": "Cosine"}})
        sys.stderr.write(f"[cc_docs] создана коллекция {COLL} ({dim}d)\n")


def do_index(limit: int | None) -> int:
    import trafilatura

    urls = en_urls(limit)
    sys.stderr.write(f"[cc_docs] EN-страниц к индексации: {len(urls)}\n")
    points: list[dict] = []
    dim = None
    ok = 0
    for n, url in enumerate(urls, 1):
        try:
            html = _get(url).decode("utf-8", "replace")
            md = trafilatura.extract(html, output_format="markdown", include_tables=True)
            if not md or len(md.strip()) < 80:
                continue
            title_m = re.search(r"^#\s+(.+)", md, re.M)
            title = title_m.group(1).strip() if title_m else url.rsplit("/", 1)[-1]
            chunks = chunk_md(md)
            vectors = tei_embed(chunks)
            if len(vectors) != len(chunks):
                sys.stderr.write(f"[cc_docs] warn: TEI {len(vectors)}/{len(chunks)} векторов для {url}\n")
            if dim is None and vectors:
                dim = len(vectors[0])
                _ensure_collection(dim)
            for i, (ch, vec) in enumerate(zip(chunks, vectors)):
                points.append(
                    {"id": _pid(url, i), "vector": vec, "payload": {"url": url, "title": title, "heading": _heading(ch), "content": ch}}
                )
            ok += 1
            if len(points) >= 256:
                _req("PUT", f"{QDRANT}/collections/{COLL}/points", {"points": points})
                points = []
            if n % 20 == 0:
                sys.stderr.write(f"[cc_docs] {n}/{len(urls)} (ok={ok})\n")
        except Exception as e:  # одна страница не валит прогон
            sys.stderr.write(f"[cc_docs] skip {url}: {type(e).__name__}: {e}\n")
    if points:
        _req("PUT", f"{QDRANT}/collections/{COLL}/points", {"points": points})
    sys.stderr.write(f"[cc_docs] готово: проиндексировано страниц={ok}\n")
    return 0


def do_search(query: str, top: int) -> int:
    vec = tei_embed([QWEN3_QUERY + query])[0]
    res = _req(
        "POST",
        f"{QDRANT}/collections/{COLL}/points/search",
        {"vector": vec, "limit": top, "with_payload": True},
    )
    hits = res.get("result", [])
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    if not hits:
        print("(ничего не найдено; запусти index)")
        return 0
    print(f"# Поиск по докам Claude Code: «{query}»\n")
    for i, h in enumerate(hits, 1):
        p = h.get("payload", {})
        head = p.get("heading") or p.get("title", "")
        snippet = " ".join((p.get("content", "")).split())[:200]
        print(f"{i}. [{round(h.get('score', 0), 3)}] {p.get('title', '')} — {head}\n   {p.get('url', '')}\n   {snippet}\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Поиск по документации Claude Code (code.claude.com)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("index")
    pi.add_argument("--limit", type=int, default=None)
    psr = sub.add_parser("search")
    psr.add_argument("query")
    psr.add_argument("--top", type=int, default=8)
    a = ap.parse_args()
    if a.cmd == "index":
        return do_index(a.limit)
    return do_search(a.query, a.top)


if __name__ == "__main__":
    sys.exit(main())
