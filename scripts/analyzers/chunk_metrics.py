"""Chunk-level quality metrics on Qdrant points with payloads.

Operates on a sample (scroll with_payload=True), computes:
  - chunk length distribution (chars / approx tokens)
  - lexical diversity (unique tokens / total)
  - empty / near-empty chunk count
  - near-duplicate detection via shingled jaccard sample
  - language detection (if `langdetect` available — opt-in)
"""

from __future__ import annotations

import random
import re
import statistics
from collections.abc import Iterable
from typing import Any

try:
    from langdetect import DetectorFactory, detect  # type: ignore[import-not-found]

    DetectorFactory.seed = 42
    _LANGDETECT = True
except ImportError:
    _LANGDETECT = False


_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_TEXT_FIELDS = ("text", "content", "chunk_text", "page_content")


def extract_text(payload: dict[str, Any] | None) -> str:
    if not payload:
        return ""
    for f in _TEXT_FIELDS:
        v = payload.get(f)
        if isinstance(v, str) and v:
            return v
    return ""


def _shingles(text: str, k: int = 5) -> set[str]:
    tokens = _TOKEN_RE.findall(text.lower())
    if len(tokens) < k:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i : i + k]) for i in range(len(tokens) - k + 1)}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _percentile(vals: list[int], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    k = (p / 100) * (len(s) - 1)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return float(s[f])
    return s[f] + (s[c] - s[f]) * (k - f)


def analyze_chunks(
    payloads: Iterable[dict[str, Any] | None],
    *,
    dedup_pairs: int = 500,
    language_sample: int = 100,
) -> dict[str, Any]:
    """Returns metric dict; safe for any payload shape."""
    texts: list[str] = []
    char_lens: list[int] = []
    token_lens: list[int] = []
    diversities: list[float] = []
    empties = 0

    for p in payloads:
        t = extract_text(p)
        if len(t.strip()) < 10:
            empties += 1
            continue
        texts.append(t)
        char_lens.append(len(t))
        toks = _TOKEN_RE.findall(t)
        token_lens.append(len(toks))
        if toks:
            toks_lower = [tok.lower() for tok in toks]
            diversities.append(len(set(toks_lower)) / len(toks_lower))

    out: dict[str, Any] = {
        "total_sampled": len(texts) + empties,
        "empty_chunks": empties,
    }
    if not texts:
        return out

    out["char_length"] = {
        "mean": int(statistics.fmean(char_lens)),
        "median": int(statistics.median(char_lens)),
        "min": min(char_lens),
        "max": max(char_lens),
        "p95": int(_percentile(char_lens, 95)),
    }
    out["token_length"] = {
        "mean": int(statistics.fmean(token_lens)),
        "median": int(statistics.median(token_lens)),
        "min": min(token_lens),
        "max": max(token_lens),
        "p95": int(_percentile(token_lens, 95)),
    }
    if diversities:
        out["lexical_diversity"] = {
            "mean": round(statistics.fmean(diversities), 3),
            "min": round(min(diversities), 3),
            "max": round(max(diversities), 3),
        }
    out["char_length_distribution"] = char_lens

    pairs_to_test = min(dedup_pairs, len(texts) * (len(texts) - 1) // 2)
    if pairs_to_test > 0 and len(texts) > 1:
        rng = random.Random(42)
        shingled = [_shingles(t) for t in texts[:200]]
        idx = list(range(len(shingled)))
        sampled_pairs = []
        for _ in range(min(pairs_to_test, 1000)):
            i, j = rng.sample(idx, 2)
            sampled_pairs.append((i, j))
        high_sim = 0
        for i, j in sampled_pairs:
            j_score = _jaccard(shingled[i], shingled[j])
            if j_score >= 0.85:
                high_sim += 1
        out["near_duplicates"] = {
            "pairs_tested": len(sampled_pairs),
            "high_similarity_pairs": high_sim,
            "rate_pct": round(high_sim / len(sampled_pairs) * 100, 2),
        }

    if _LANGDETECT and texts:
        from collections import Counter

        lang_counter: Counter[str] = Counter()
        for t in texts[:language_sample]:
            try:
                lang_counter[detect(t[:500])] += 1
            except Exception:
                lang_counter["?"] += 1
        out["languages"] = dict(lang_counter.most_common(10))

    return out


def render_chunk_section(metrics: dict[str, Any]) -> str:
    if not metrics or metrics.get("total_sampled", 0) == 0:
        return "_Нет sample'а с payload.text/content — chunk-level metrics недоступны._"
    lines: list[str] = []
    lines.append(f"- **sampled chunks:** {metrics['total_sampled']:,}")
    if metrics.get("empty_chunks"):
        lines.append(f"- **empty/near-empty:** {metrics['empty_chunks']:,} !")
    cl = metrics.get("char_length", {})
    if cl:
        lines.append(
            f"- **char length:** mean=`{cl['mean']:,}`, median=`{cl['median']:,}`, "
            f"p95=`{cl['p95']:,}`, max=`{cl['max']:,}`"
        )
    tl = metrics.get("token_length", {})
    if tl:
        lines.append(
            f"- **token length (approx):** mean=`{tl['mean']:,}`, median=`{tl['median']:,}`, "
            f"p95=`{tl['p95']:,}`"
        )
    ld = metrics.get("lexical_diversity", {})
    if ld:
        lines.append(
            f"- **lexical diversity:** mean=`{ld['mean']}` "
            f"(low <0.3 = boilerplate, >0.7 = high entropy)"
        )
    nd = metrics.get("near_duplicates", {})
    if nd:
        rate = nd["rate_pct"]
        tag = " !" if rate > 5.0 else ""
        lines.append(
            f"- **near-duplicates (jaccard ≥0.85):** {nd['high_similarity_pairs']}/"
            f"{nd['pairs_tested']} pairs = {rate}%{tag}"
        )
    langs = metrics.get("languages")
    if langs:
        bits = ", ".join(f"{k}={v}" for k, v in langs.items())
        lines.append(f"- **languages (sample):** {bits}")
    return "\n".join(lines)
