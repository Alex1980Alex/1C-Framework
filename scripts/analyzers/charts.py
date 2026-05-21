"""Pure-stdlib ASCII charts for report visualization.

No external dependencies. Output is monospace-readable on terminal and
renders cleanly in Markdown code blocks.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any


def histogram(
    values: Iterable[float],
    bins: int = 10,
    width: int = 40,
    label: str = "",
) -> str:
    vals = [float(v) for v in values if v is not None and not math.isnan(float(v))]
    if not vals:
        return "_(empty)_"
    vmin, vmax = min(vals), max(vals)
    if vmin == vmax:
        return f"```\n{label}\nAll {len(vals)} values = {vmin:.4f}\n```"
    step = (vmax - vmin) / bins
    counts = [0] * bins
    for v in vals:
        idx = min(int((v - vmin) / step), bins - 1)
        counts[idx] += 1
    cmax = max(counts) or 1
    lines = ["```"]
    if label:
        lines.append(label)
    for i, c in enumerate(counts):
        lo = vmin + i * step
        hi = lo + step
        bar = "#" * int(c / cmax * width)
        lines.append(f"  [{lo:9.3f}, {hi:9.3f}]  {bar:<{width}} {c}")
    lines.append(f"  total={len(vals)}, min={vmin:.3f}, max={vmax:.3f}")
    lines.append("```")
    return "\n".join(lines)


def boxplot(values: Iterable[float], label: str = "") -> str:
    vals = sorted(float(v) for v in values if v is not None and not math.isnan(float(v)))
    if not vals:
        return "_(empty)_"
    n = len(vals)
    if n < 4:
        return f"```\n{label} min={vals[0]:.3f} max={vals[-1]:.3f} n={n}\n```"
    q1 = vals[n // 4]
    med = vals[n // 2]
    q3 = vals[3 * n // 4]
    mn, mx = vals[0], vals[-1]
    width = 60
    rng = mx - mn or 1

    def pos(v: float) -> int:
        return max(0, min(width - 1, int((v - mn) / rng * (width - 1))))

    line = list(" " * width)
    line[pos(mn)] = "|"
    line[pos(mx)] = "|"
    for p in range(pos(q1), pos(q3) + 1):
        if 0 <= p < width and line[p] == " ":
            line[p] = "-"
    line[pos(q1)] = "["
    line[pos(q3)] = "]"
    line[pos(med)] = "#"
    bar = "".join(line)
    return (
        f"```\n{label}\n  {bar}\n"
        f"  min={mn:.3f}  q1={q1:.3f}  median={med:.3f}  "
        f"q3={q3:.3f}  max={mx:.3f}  n={n}\n```"
    )


def waterfall(stages: list[tuple[str, float]], width: int = 40) -> str:
    if not stages:
        return "_(no stages)_"
    total = sum(d for _, d in stages) or 1.0
    lines = ["```", f"Total: {total:.2f}s"]
    cum = 0.0
    for name, dur in stages:
        bar_len = max(1, int(dur / total * width))
        offset = int(cum / total * width)
        line = " " * offset + "#" * bar_len
        line = line[:width]
        lines.append(f"  {line:<{width}}  {dur:7.2f}s  {name}")
        cum += dur
    lines.append("```")
    return "\n".join(lines)


def distribution_table(dist: dict[str, int], top: int = 20) -> str:
    if not dist:
        return "_(empty)_"
    items = sorted(dist.items(), key=lambda kv: kv[1], reverse=True)[:top]
    total = sum(dist.values()) or 1
    cmax = items[0][1] or 1
    width = 30
    lines = ["```"]
    for name, n in items:
        pct = n / total * 100
        bar = "#" * int(n / cmax * width)
        name_display = str(name)[:30]
        lines.append(f"  {name_display:<30} {bar:<{width}} {n:>7,} ({pct:5.1f}%)")
    lines.append("```")
    return "\n".join(lines)


def degree_distribution_loglog(degrees: list[int], bins: int = 10) -> dict[str, Any]:
    """Log-log degree distribution + naive power-law exponent estimate.

    Returns {gamma, bins: [(low, high, count)], r_squared}.
    γ ∈ [2,3] typical for scale-free networks (software call graphs included).
    """
    if not degrees:
        return {"gamma": None, "bins": [], "r_squared": None}
    deg_filtered = [d for d in degrees if d > 0]
    if len(deg_filtered) < 10:
        return {"gamma": None, "bins": [], "r_squared": None, "note": "too few nodes"}

    dmin, dmax = min(deg_filtered), max(deg_filtered)
    if dmin == dmax:
        return {"gamma": None, "bins": [], "r_squared": None, "note": "no variance"}

    log_lo, log_hi = math.log(dmin), math.log(dmax + 1)
    step = (log_hi - log_lo) / bins
    edges = [math.exp(log_lo + i * step) for i in range(bins + 1)]
    counts = [0] * bins
    for d in deg_filtered:
        idx = min(int((math.log(d) - log_lo) / step), bins - 1) if step > 0 else 0
        counts[idx] += 1

    xs, ys = [], []
    for i, c in enumerate(counts):
        if c <= 0:
            continue
        center = math.sqrt(edges[i] * edges[i + 1])
        xs.append(math.log(center))
        ys.append(math.log(c))
    if len(xs) < 3:
        return {
            "gamma": None,
            "bins": [
                {"low": round(edges[i], 1), "high": round(edges[i + 1], 1), "count": c}
                for i, c in enumerate(counts)
            ],
            "r_squared": None,
        }

    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den_x = sum((x - mean_x) ** 2 for x in xs) or 1e-9
    slope = num / den_x
    gamma = -slope
    intercept = mean_y - slope * mean_x
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - mean_y) ** 2 for y in ys) or 1e-9
    r_sq = 1 - (ss_res / ss_tot)

    return {
        "gamma": round(gamma, 3),
        "r_squared": round(r_sq, 3),
        "bins": [
            {"low": round(edges[i], 1), "high": round(edges[i + 1], 1), "count": c}
            for i, c in enumerate(counts)
        ],
    }
