#!/usr/bin/env python3
"""Ecosystem scan (ADR-039 V2+V3) — on-demand «что в экосистеме за N дней» по free-источникам.

Опрашивает Hacker News (Algolia), StackOverflow (StackExchange), GitHub (search), Lobsters и Dev.to
(тег-based, через query->tag) — БЕЗ cookies, платных API и скрапинга (в отличие от full last30days;
ADR-039 SKIP). Ранжирует по engagement через переиспользуемый shared/engagement_rank
(relevance x популярность, веса query-adaptive), схлопывает кросс-источниковые дубли и печатает
Markdown-бриф. Ускоритель Фазы 2 architecture-research / tech-research + discovery для tooling-adoption.

Reddit убран 2026 (public .json -> 403 с 2026-05-30, OAuth закрыт) -> заменён StackOverflow.

V3 (2026-06-24):
  - query-adaptive веса: discovery-запрос (best/trending/2026) -> популярность важнее (0.5/0.5);
    precision-запрос (версия/ошибка/fix) -> релевантность важнее (0.85/0.15); иначе 0.7/0.3.
  - Lobsters/Dev.to через query->tag-маппинг (закрытый набор тегов; нет тега -> источник пропущен).
  - кеш сканов в data/reports/ecosystem/ (TTL, --no-cache).

Запуск:
  python scripts/ecosystem_scan.py "RAG embeddings reranking 2026" --days 30 --top 10
  python scripts/ecosystem_scan.py "claude code mcp" --out data/reports/ecosystem/mcp.md
  python scripts/ecosystem_scan.py "langgraph" --json --no-cache

Сеть изолирована (fetch_*), graceful per-source. Ядро (build_ranked / to_markdown / _query_weights /
_map_query_to_tags / кеш) — чистое/тестируемое. GitHub: GITHUB_TOKEN из env (опц., выше rate-limit).
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
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
LOBSTERS_TAG_URL = "https://lobste.rs/t/{tag}.json"
DEVTO_API = "https://dev.to/api/articles"
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "reports" / "ecosystem"

# query-adaptive веса (#3): тип запроса -> (w_relevance, w_engagement).
_DISCOVERY_RE = re.compile(
    r"\b(best|top|trending|popular|awesome|alternativ\w*|compare|2025|2026"
    r"|лучш\w*|тренд\w*|популярн\w*|сравн\w*|обзор)\b",
    re.I | re.U,
)
_PRECISION_RE = re.compile(
    r"(\d+\.\d+|\berror\b|\bexception\b|\bfix\b|\bbug\b|traceback|\w*error\b|ошибк\w*)",
    re.I | re.U,
)

# query->tag (#1): закрытый набор тегов Lobsters/Dev.to (тег-based, не free-text).
_TAG_SYNONYMS = {
    "python": "python", "rust": "rust", "go": "go", "golang": "go",
    "javascript": "javascript", "js": "javascript", "typescript": "javascript",
    "java": "java", "ruby": "ruby", "php": "php",
    "ai": "ai", "ml": "ai", "llm": "ai", "llms": "ai", "rag": "ai", "agent": "ai",
    "agents": "ai", "embedding": "ai", "embeddings": "ai", "langchain": "ai",
    "langgraph": "ai", "gpt": "ai", "neural": "ai", "nlp": "ai",
    "security": "security", "infosec": "security",
    "database": "databases", "databases": "databases", "sql": "databases",
    "postgres": "databases", "postgresql": "databases",
    "web": "web", "frontend": "web", "react": "web",
    "devops": "devops", "kubernetes": "devops", "k8s": "devops", "docker": "devops",
    "linux": "linux", "android": "android", "ios": "ios",
}


def _http_json(url: str, headers: dict | None = None, timeout: float = 8.0):
    """GET + parse JSON (dict ИЛИ list). Любая ошибка -> None (graceful)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except Exception:
        return None


def _norm_token(s: str) -> str:
    return " ".join((s or "").lower().split())


def _query_weights(query: str) -> tuple[float, float]:
    """query-adaptive веса (#3): (w_relevance, w_engagement) по типу запроса.

    precision (версия/ошибка/fix) -> релевантность важнее; discovery (best/trending/2026) ->
    популярность важнее; иначе дефолт 0.7/0.3. precision проверяется первым (диагностический интент).
    """
    q = query or ""
    if _PRECISION_RE.search(q):
        return (0.85, 0.15)
    if _DISCOVERY_RE.search(q):
        return (0.5, 0.5)
    return (0.7, 0.3)


def _map_query_to_tags(query: str, limit: int = 2) -> list[str]:
    """Сопоставить токены запроса закрытому набору тегов (Lobsters/Dev.to тег-based). Нет совпадений -> []."""
    out: list[str] = []
    for tok in re.findall(r"[a-z0-9]+", (query or "").lower()):
        tag = _TAG_SYNONYMS.get(tok)
        if tag and tag not in out:
            out.append(tag)
        if len(out) >= limit:
            break
    return out


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


def fetch_lobsters(query: str, limit: int = 25) -> list[dict]:
    """Lobsters story-feed по тегам (#1; тег-based -> query->tag). engagement = score + comments.

    Закрытый набор тегов: берём до 2 тегов из запроса, далее общий relevance-фильтр в build_ranked.
    Нет совпадения тега -> [] (не зашумляем generic-лентой). Отдаёт JSON-массив.
    """
    out: list[dict] = []
    for tag in _map_query_to_tags(query):
        data = _http_json(LOBSTERS_TAG_URL.format(tag=tag))
        for s in (data if isinstance(data, list) else [])[:limit]:
            title = (s.get("title") or "").strip()
            if not title:
                continue
            eng = int(s.get("score") or 0) + int(s.get("comment_count") or 0)
            out.append(
                {
                    "source": f"Lobsters/{tag}",
                    "title": title,
                    "url": s.get("short_id_url") or s.get("url") or "",
                    "engagement": eng,
                }
            )
    return out


def fetch_devto(query: str, days: int, limit: int = 30) -> list[dict]:
    """Dev.to (forem) статьи по тегу (#1; тег-based -> query->tag). engagement = public_reactions_count.

    Берёт лучший тег запроса; top=<days> = топ статей за окно. Нет тега -> []. Отдаёт JSON-массив.
    """
    tags = _map_query_to_tags(query, limit=1)
    if not tags:
        return []
    top = max(1, min(days, 365))
    url = f"{DEVTO_API}?tag={urllib.parse.quote(tags[0])}&top={top}&per_page={limit}"
    data = _http_json(url)
    out: list[dict] = []
    for a in data if isinstance(data, list) else []:
        title = (a.get("title") or "").strip()
        if not title:
            continue
        out.append(
            {
                "source": "DevTo",
                "title": title,
                "url": a.get("url") or "",
                "engagement": int(a.get("public_reactions_count") or 0),
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
    """Чистое ядро: relevance x engagement ранкинг (query-adaptive веса) + дедуп. Без сети."""
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
        w_rel, w_eng = _query_weights(query)
        ranked = rank_items(
            scored,
            engagement_key="eng_norm",
            engagement_cap=1.0,
            w_relevance=w_rel,
            w_engagement=w_eng,
        )
        ranked = dedup_by_entity(ranked, lambda it: _norm_token(it.get("title", ""))[:80] or None)
    else:
        ranked = sorted(scored, key=lambda x: x.get("relevance", 0), reverse=True)
        for it in ranked:
            it["blended"] = round(float(it.get("relevance", 0)), 4)
    return ranked[:top]


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s or "scan")[:50]


def _cache_path(query: str, days: int) -> Path:
    return CACHE_DIR / f"{_slugify(query)}_{days}d.json"


def _cache_load(path: Path, ttl_hours: float) -> list[dict] | None:
    """Прочитать кеш, если свежее ttl_hours. Иначе/ошибка -> None (graceful)."""
    try:
        if not path.exists():
            return None
        age_h = (datetime.now(UTC).timestamp() - path.stat().st_mtime) / 3600.0
        if age_h > ttl_hours:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("items") if isinstance(data, dict) else None
    except Exception:
        return None


def _cache_save(path: Path, query: str, days: int, items: list[dict]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "query": query,
            "days": days,
            "generated_at": datetime.now(UTC).isoformat(),
            "items": items,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass


def to_markdown(query: str, ranked: list[dict], days: int) -> str:
    """Markdown-бриф (чистая функция)."""
    lines = [f"# Ecosystem scan: «{query}» (последние {days} дн.)", ""]
    if not ranked:
        lines.append("_Ничего релевантного не найдено (или все источники недоступны)._")
        return "\n".join(lines)
    lines.append(f"Топ-{len(ranked)} по engagement × relevance (free HN/SO/GitHub/Lobsters/Dev.to):")
    lines.append("")
    for i, it in enumerate(ranked, 1):
        eng = int(it.get("engagement") or 0)
        score = it.get("blended", it.get("relevance", 0))
        lines.append(
            f"{i}. **[{it.get('source', '?')}]** {it.get('title', '?')}  "
            f"(engagement={eng}, score={score})\n   {it.get('url', '')}"
        )
    return "\n".join(lines)


def scan(
    query: str,
    days: int = 30,
    top: int = 10,
    use_cache: bool = True,
    cache_ttl_hours: float = 12.0,
) -> list[dict]:
    """Опросить все источники (сеть) + ранжировать. Кеш (#4): hit в пределах TTL -> без сети.

    Каждый источник graceful. Кеш ключуется (slug запроса, days); хранит top первого прогона.
    """
    cache = _cache_path(query, days)
    if use_cache:
        cached = _cache_load(cache, cache_ttl_hours)
        if cached is not None:
            return cached[:top]
    now = datetime.now(UTC)
    since_ts = int((now - timedelta(days=days)).timestamp())
    since_date = (now - timedelta(days=days)).strftime("%Y-%m-%d")
    items: list[dict] = []
    items += fetch_hn(query, since_ts)
    items += fetch_stackexchange(query, since_ts)
    items += fetch_github(query, since_date)
    items += fetch_lobsters(query)
    items += fetch_devto(query, days)
    ranked = build_ranked(query, items, top=top)
    if use_cache:
        _cache_save(cache, query, days, ranked)
    return ranked


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass
    ap = argparse.ArgumentParser(
        description="Ecosystem scan (ADR-039) — free HN/SO/GitHub/Lobsters/Dev.to"
    )
    ap.add_argument("query", help="тема для скана")
    ap.add_argument("--days", type=int, default=30, help="окно в днях (default 30)")
    ap.add_argument("--top", type=int, default=10, help="сколько результатов (default 10)")
    ap.add_argument("--out", default=None, help="сохранить Markdown в файл (иначе stdout)")
    ap.add_argument("--json", action="store_true", help="машинный JSON вместо Markdown")
    ap.add_argument("--no-cache", action="store_true", help="не использовать кеш (всегда сеть)")
    ap.add_argument("--cache-ttl", type=float, default=12.0, help="TTL кеша в часах (default 12)")
    args = ap.parse_args()

    ranked = scan(
        args.query,
        days=args.days,
        top=args.top,
        use_cache=not args.no_cache,
        cache_ttl_hours=args.cache_ttl,
    )

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
