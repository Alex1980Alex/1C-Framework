#!/usr/bin/env python3
"""Engagement-aware ranking helpers (приём заимствован у last30days-skill, ADR-039).

Stdlib-only, чистые функции → юнит-тестируемы без сети/зависимостей. Три примитива:
  - expand_queries   — multi-query expansion (расширить recall),
  - blended_score / rank_items — слияние relevance × engagement (популярность),
  - dedup_by_entity  — слить элементы одной сущности из разных источников, оставить лучший.

V1 (ADR-039): используется `prework-github-bp.py` — блендит rapidfuzz-relevance с
GitHub-engagement (repos + sources) вместо relevance-only сортировки.
V2 (будущее): тот же модуль для free-источников скан (HN/Reddit/GitHub), где dedup_by_entity
схлопывает одну новость, встреченную на нескольких платформах.

Дизайн: relevance доминирует (вес 0.7), популярность — корректирующий вклад (0.3); engagement
лог-масштабируется (log1p) с насыщением, чтобы один «звёздный» элемент не вытеснял релевантные
(анти-паттерн чистого engagement-ранкинга).
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Sequence

# Маленький RU/EN стоп-лист — только для отбрасывания шумовых токенов в expand_queries.
_STOP = frozenset(
    {
        "the",
        "a",
        "an",
        "of",
        "for",
        "to",
        "in",
        "on",
        "and",
        "or",
        "how",
        "what",
        "is",
        "are",
        "with",
        "use",
        "using",
        "best",
        "practice",
        "practices",
        "как",
        "что",
        "для",
        "при",
        "это",
        "или",
        "над",
        "под",
        "из",
        "по",
    }
)

_TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9_\-]+")


def expand_queries(query: str, extra_terms: Iterable[str] = (), max_variants: int = 4) -> list[str]:
    """Детерминированное multi-query expansion (без LLM/сети) для расширения recall.

    Варианты: оригинал → lower → значимые токены (без стоп-слов) → `query + extra_term`.
    Дедуп с сохранением порядка, ограничено `max_variants`. Пустой query → [].
    """
    q = (query or "").strip()
    if not q:
        return []
    variants = [q, q.lower()]
    toks = [t for t in _TOKEN_RE.findall(q.lower()) if len(t) >= 3 and t not in _STOP]
    if toks:
        variants.append(" ".join(toks))
    for term in extra_terms:
        term = (term or "").strip()
        if term:
            variants.append(f"{q} {term}")
    seen: set[str] = set()
    out: list[str] = []
    for v in variants:
        v = v.strip()
        if v and v not in seen:
            seen.add(v)
            out.append(v)
        if len(out) >= max_variants:
            break
    return out


def _norm_engagement(value: float, cap: float) -> float:
    """log1p-масштаб engagement → [0,1], насыщение на `cap`."""
    if value <= 0 or cap <= 0:
        return 0.0
    return min(1.0, math.log1p(value) / math.log1p(cap))


def blended_score(
    relevance: float,
    engagement: float,
    *,
    w_relevance: float = 0.7,
    w_engagement: float = 0.3,
    engagement_cap: float = 50.0,
) -> float:
    """Слить relevance (0..1) с лог-масштабированным engagement-счётчиком → 0..1.

    relevance клампится в [0,1]; engagement (кол-во repos/upvotes/...) лог-нормируется.
    Дефолтные веса (0.7/0.3) сохраняют приоритет релевантности над популярностью.
    """
    rel = max(0.0, min(1.0, float(relevance)))
    eng = _norm_engagement(max(0.0, float(engagement)), engagement_cap)
    return round(w_relevance * rel + w_engagement * eng, 4)


def rank_items(
    items: Sequence[dict],
    *,
    relevance_key: str = "relevance",
    engagement_key: str = "engagement",
    score_key: str = "blended",
    w_relevance: float = 0.7,
    w_engagement: float = 0.3,
    engagement_cap: float = 50.0,
) -> list[dict]:
    """Вернуть копии items, отсортированные по blended_score убыв.; пишет балл в `score_key`."""
    out: list[dict] = []
    for it in items:
        new = dict(it)
        new[score_key] = blended_score(
            new.get(relevance_key, 0.0) or 0.0,
            new.get(engagement_key, 0.0) or 0.0,
            w_relevance=w_relevance,
            w_engagement=w_engagement,
            engagement_cap=engagement_cap,
        )
        out.append(new)
    out.sort(key=lambda x: x[score_key], reverse=True)
    return out


def dedup_by_entity(
    items: Iterable[dict], entity_key: Callable[[dict], object], *, score_key: str = "blended"
) -> list[dict]:
    """Слить элементы с одинаковым ключом сущности, оставив максимум по `score_key`.

    `entity_key(item)` → хэшируемый ключ (напр. нормализованный title/url/repo) или None
    (None → элемент уникален, не схлопывается). Результат отсортирован по score убыв.
    """
    best: dict[object, dict] = {}
    for it in items:
        try:
            k = entity_key(it)
        except Exception:
            k = None
        if k is None:
            best[("_uniq", id(it))] = it
            continue
        cur = best.get(k)
        if cur is None or float(it.get(score_key, 0) or 0) > float(cur.get(score_key, 0) or 0):
            best[k] = it
    return sorted(best.values(), key=lambda x: float(x.get(score_key, 0) or 0), reverse=True)
