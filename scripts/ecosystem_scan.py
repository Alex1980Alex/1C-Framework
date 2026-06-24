#!/usr/bin/env python3
"""Ecosystem scan (ADR-039 V2) — on-demand «что в экосистеме за N дней» по free-источникам.

Опрашивает Hacker News (Algolia), StackOverflow (StackExchange API), GitHub (search API) — БЕЗ
cookies, платных API и скрапинга (в отличие от full last30days; ADR-039 SKIP). Ранжирует по
engagement через переиспользуемый shared/engagement_rank (relevance × популярность), схлопывает
кросс-источниковые дубли и печатает Markdown-бриф. Ускоритель Фазы 2 architecture-research / tech-
research + discovery для tooling-adoption (ADR-012..015).

Reddit убран 2026 (public .json -> 403 с 2026-05-30, OAuth закрыт — data-licensing). Замена —
StackOverflow (free-text q, без ключа, engagement = score). Доп. источники (Lobsters/Dev.to —
тег-based) рассмотрены, но не free-text — отложены.

Запуск:
  python scripts/ecosystem_scan.py "RAG embeddings reranking 2026" --days 30 --top 10
  python scripts/ecosystem_scan.py "claude code mcp" --out data/reports/ecosystem/mcp.md
  python scripts/ecosystem_scan.py "langgraph" --json     # машинный вывод

Сеть изолирована (fetch_*), graceful per-source (источник упал -> пропущен, остальные работают).
Ядро (build_ranked / to_markdown) — чистое, без сети -> unit-тестируемо.
GitHub: использует GITHUB_TOKEN из env при наличии (выше rate-limit), иначе анонимно.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Переиспользуем приём из V1 (hook-local shared). Cross-tree import: scripts/ -> .claude/hooks.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".claude" / "hooks"))
try:
    from shared.engagement_rank import dedup_by_entity, expand_queries, rank_items

    HAS_ENGAGEMENT = True
except Exception:  # graceful: relevance-only fallback
    HAS_ENGAGEMENT = False

try:
    from rapidfuzz import fuzz

    HAS_RAPIDFUZZ = True
except Exception:
    HAS_RAPIDFUZZ = False

UA = "ecosystem-scan/1.0 (+pdf-vector-graph framework; ADR-039)"
HN_API = "https://hn.algolia.com/api/v1/search_by_date"
STACKEXCHANGE_API = "https://api.stackexchange.com/2.3/search/advanced"
GITHUB_API = "https://api.github.com/search/repositories"


def _http_json(url: str, headers: dict | None = None, timeout: float = 8.0) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except Exception:
        return None


def _norm_token(s: str) -> str:
    return " ".join((s or "").lower().split())


def fetch_hn(query: str, since_ts: int, limit: int = 30) -> list[dict]:
    """Hacker News stories за окно (Algolia). engagement = points + comments."""
    q = urllib.parse.quote(query)
    url = (
        f"{HN_API}?query={q}&tags=story"
        f"&numericFilters=created_at_i>{since_ts}&hitsPerPage={limit}"
    )
    data = _http_json(url)
    out: list[dict] = []
    for h in (data or {}).get("hits", []) or []:
        title = h.get("title") or h.get("story_title") or ""
        if not title:
            continue
        url_ = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        eng = int(h.get("points") or 0) + int(h.get("num_comments") or 0)
        out.append({"source": "HN", "title": title, "url": url_, "engagement": eng})
    return out


def fetch_stackexchange(query: str, since_ts: int, limit: int = 30) -> list[dict]:
    """StackOverflow вопросы за окно (StackExchange API, free, без ключа). engagement = score.

    Заменил мёртвый Reddit (2026): unauth .json -> 403, OAuth закрыт. SE отдаёт плоский JSON,
    free-text q, фильтр fromdate. title содержит HTML-entities -> html.unescape.
    """
    q = urllib.parse.quote(query)
    url = (
        f"{STACKEXCHANGE_API}?order=desc&sort=votes&q={q}&fromdate={since_ts}"
        f"&site=stackoverflow&pagesize={limit}"
    )
    data = _http_json(url)
    out: list[dict] = []
    for r in (data or {}).get("items", []) or []:
        title = html.unescape(r.get("title") or "")
        if not title:
            continue
        out.append(
            {
                "source": "StackOverflow",
                "title": title,
                "url": r.get("link") or "",
                "engagement": int(r.get("score") or 0),
            }
        )
    return out


def fetch_github(query: str, since_date: str, limit: int = 30) -> list[dict]:
    """GitHub repos, pushed за окно (search API). engagement = stars."""
    q = urllib.parse.quote(f"{query} pushed:>{since_date}")
    url = f"{GITHUB_API}?q={q}&sort=stars&order=desc&per_page={limit}"
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = _http_json(url, headers=headers)
    out: list[dict] = []
    for r in (data or {}).get("items", []) or []:
        name = r.get("full_name") or ""
        if not name:
            continue
        desc = (r.get("description") or "").strip()
        title = f"{name} — {desc}" if desc else name
        out.append(
            {
                "source": "GitHub",
                "title": title,
                "url": r.get("html_url") or "",
                "engagement": int(r.get("stargazers_count") or 0),
            }
        )
    return out


def _relevance(query_variants: list[str], title: str) -> float:
    """0..1 релевантность title к расширенному запросу (rapidfuzz token_set_ratio,
    иначе token-overlap fallback)."""
    t = _norm_token(title)
    if not t or not query_variants:
        return 0.0
    if HAS_RAPIDFUZZ:
        return max(fuzz.token_set_ratio(v.lower(), t) for v in query_variants) / 100.0
    qtok = {w for v in query_variants for w in v.lower().split() if len(w) >= 3}
    if not qtok:
        return 0.0
    ttok = set(t.split())
    return len(qtok & ttok) / len(qtok)


def _normalize_engagement_per_source(scored: list[dict]) -> None:
    """Per-source min-max нормировка engagement в [0,1] (поле eng_norm, in-place).

    Иначе GitHub-звёзды (10^4-10^5) топят HN/SO (10^0-10^2) при едином cap — топ каждого источника
    получает eng_norm=1.0, источники конкурируют честно -> разнообразие источников в выдаче.
    """
    by_source: dict[str, float] = {}
    for it in scored:
        s = str(it.get("source", "?")).split("/")[0]
        by_source[s] = max(by_source.get(s, 0.0), float(it.get("engagement") or 0))
    for it in scored:
        s = str(it.get("source", "?")).split("/")[0]
        smax = by_source.get(s, 0.0)
        it["eng_norm"] = (float(it.get("engagement") or 0) / smax) if smax > 0 else 0.0


def build_ranked(
    query: str, items: list[dict], top: int = 10, min_relevance: float = 0.5
) -> list[dict]:
    """Чистое ядро: relevance × engagement ранкинг + кросс-источниковый дедуп. Без сети."""
    variants = expand_queries(query) if HAS_ENGAGEMENT else [query]
    scored: list[dict] = []
    for it in items:
        rel = _relevance(variants, it.get("title", ""))
        if rel < min_relevance:
            continue
        scored.append({**it, "relevance": rel})
    if not scored:
        return []
    if HAS_ENGAGEMENT:
        _normalize_engagement_per_source(scored)
        ranked = rank_items(scored, engagement_key="eng_norm", engagement_cap=1.0)
        ranked = dedup_by_entity(ranked, lambda it: _norm_token(it.get("title", ""))[:80] or None)
    else:
        ranked = sorted(scored, key=lambda x: x.get("relevance", 0), reverse=True)
        for it in ranked:
            it["blended"] = round(float(it.get("relevance", 0)), 4)
    return ranked[:top]


def to_markdown(query: str, ranked: list[dict], days: int) -> str:
    """Markdown-бриф (чистая функция)."""
    lines = [f"# Ecosystem scan: «{query}» (последние {days} дн.)", ""]
    if not ranked:
        lines.append("_Ничего релевантного не найдено (или все источники недоступны)._")
        return "\n".join(lines)
    lines.append(f"Топ-{len(ranked)} по engagement × relevance (free HN/StackOverflow/GitHub):")
    lines.append("")
    for i, it in enumerate(ranked, 1):
        eng = int(it.get("engagement") or 0)
        score = it.get("blended", it.get("relevance", 0))
        lines.append(
            f"{i}. **[{it.get('source', '?')}]** {it.get('title', '?')}  "
            f"(engagement={eng}, score={score})\n   {it.get('url', '')}"
        )
    return "\n".join(lines)


def scan(query: str, days: int = 30, top: int = 10) -> list[dict]:
    """Опросить все источники (сеть) + ранжировать. Каждый источник graceful."""
    now = datetime.now(UTC)
    since_ts = int((now - timedelta(days=days)).timestamp())
    since_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    items: list[dict] = []
    items += fetch_hn(query, since_ts)
    items += fetch_stackexchange(query, since_ts)
    items += fetch_github(query, since_date)
    return build_ranked(query, items, top=top)


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    ap = argparse.ArgumentParser(description="Ecosystem scan (ADR-039 V2) — free HN/StackOverflow/GitHub")
    ap.add_argument("query", help="тема для скана")
    ap.add_argument("--days", type=int, default=30, help="окно в днях (default 30)")
    ap.add_argument("--top", type=int, default=10, help="сколько результатов (default 10)")
    ap.add_argument("--out", default=None, help="сохранить Markdown в файл (иначе stdout)")
    ap.add_argument("--json", action="store_true", help="машинный JSON вместо Markdown")
    args = ap.parse_args()

    ranked = scan(args.query, days=args.days, top=args.top)

    if args.json:
        print(
            json.dumps(
                {"query": args.query, "days": args.days, "items": ranked}, ensure_ascii=False
            )
        )
        return 0

    md = to_markdown(args.query, ranked, args.days)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"[ecosystem-scan] -> {out} ({len(ranked)} items)")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
