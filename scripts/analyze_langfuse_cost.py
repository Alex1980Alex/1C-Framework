"""Langfuse cost baseline extractor (roadmap 260515 §5c.7).

Generates a 5-section cost baseline report by querying Langfuse Cloud
production data. Output: Markdown (default) or JSON. Default window:
last 7 closed days (today-7 .. today-1) to avoid ingestion lag.

Sections:
  1. Top-N expensive observations  — where the money goes.
  2. Avg / P50 / P95 tokens per RAG call — capacity planning.
  3. Cost by strategy (search.manager.search input.strategy).
  4. Cost by model — Opus / Sonnet / Haiku ratio.
  5. Daily run-rate USD/day — financial forecast.

Reuses singleton client from observability/langfuse_setup.py.

Usage:
    python scripts/analyze_langfuse_cost.py                       # last 7 days, md
    python scripts/analyze_langfuse_cost.py --output json         # JSON for CI
    python scripts/analyze_langfuse_cost.py --dry-run             # no file write
    python scripts/analyze_langfuse_cost.py \\
        --from-date 2026-05-01 --to-date 2026-05-07 --top-n 20

Roadmap: docs/roadmap/260515_ROADMAP_LANGFUSE_COST_BASELINE.md
Tech cache: .claude/skills/tech-research/cache/langfuse-cost-api-2026.md
"""

from __future__ import annotations

import json
import logging
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import typer

# Force UTF-8 on Windows console for any non-ASCII content (e.g. md headers).
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass

# Add src to path for project imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pdf_framework.observability.langfuse_setup import _get_langfuse_client  # noqa: E402
from src.pdf_framework.utils.retry import create_retry  # noqa: E402

logger = logging.getLogger(__name__)
app = typer.Typer(help="Langfuse cost baseline extractor (roadmap 260515)")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BASELINE_OUT = PROJECT_ROOT / "docs" / "architecture" / "cost-baselines.md"

# Retry: 429 / network / timeout. Fail-fast on 401/403 handled in callers.
retry_api = create_retry(
    max_attempts=5,
    max_delay=60.0,
    initial_wait=1.0,
    max_wait=16.0,
    jitter=2.0,
)


# ─── Data containers ────────────────────────────────────────────────────────


@dataclass
class TopNRow:
    name: str
    count: int
    total_cost: float
    avg_cost: float
    total_tokens: int


@dataclass
class StrategyRow:
    strategy: str
    count: int
    total_cost: float
    avg_cost: float


@dataclass
class ModelRow:
    model: str
    total_cost: float
    share_pct: float


@dataclass
class DailyRow:
    date: str  # YYYY-MM-DD
    cost: float


@dataclass
class CostBaselineReport:
    """Pydantic-shaped JSON-serializable baseline report."""

    generated_at: str
    from_date: str
    to_date: str
    n_days: int
    n_observations: int
    total_cost: float
    cost_per_day_mean: float
    cost_per_day_p95: float
    avg_tokens: float | None
    p50_tokens: float | None
    p95_tokens: float | None
    top_n: list[TopNRow] = field(default_factory=list)
    by_strategy: list[StrategyRow] = field(default_factory=list)
    by_model: list[ModelRow] = field(default_factory=list)
    daily: list[DailyRow] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = self.__dict__.copy()
        d["top_n"] = [r.__dict__ for r in self.top_n]
        d["by_strategy"] = [r.__dict__ for r in self.by_strategy]
        d["by_model"] = [r.__dict__ for r in self.by_model]
        d["daily"] = [r.__dict__ for r in self.daily]
        return d


# ─── Langfuse API wrappers (retry on transient errors) ──────────────────────


@retry_api
def _fetch_observations_page(
    client: Any,
    from_dt: datetime,
    to_dt: datetime,
    cursor: str | None,
    name: str | None = None,
) -> Any:
    """Fetch one page of GENERATION observations.

    fields="core,basic,usage" reduces payload — we don't need full
    input/output content for cost aggregation.
    """
    return client.api.observations.get_many(
        type="GENERATION",
        from_start_time=from_dt,
        to_start_time=to_dt,
        cursor=cursor,
        limit=100,
        name=name,
        fields="core,basic,usage",
    )


@retry_api
def _metrics_query(client: Any, query: dict[str, Any]) -> Any:
    """Server-side aggregated metrics."""
    return client.api.metrics.metrics(query=json.dumps(query))


def _iter_observations(
    client: Any, from_dt: datetime, to_dt: datetime, name: str | None = None
) -> Any:
    """Yield observations across all pages."""
    cursor: str | None = None
    while True:
        page = _fetch_observations_page(client, from_dt, to_dt, cursor, name=name)
        yield from page.data
        cursor = getattr(page.meta, "cursor", None)
        if not cursor:
            return


# ─── Sections ───────────────────────────────────────────────────────────────


def section_top_n(
    client: Any, from_dt: datetime, to_dt: datetime, top_n: int
) -> tuple[list[TopNRow], int, float, dict[str, float]]:
    """Top-N expensive observations + total counts + per-day cost map."""
    by_name: dict[str, dict[str, float]] = defaultdict(
        lambda: {"count": 0.0, "total_cost": 0.0, "total_tokens": 0.0}
    )
    per_day_cost: dict[str, float] = defaultdict(float)
    n_obs = 0
    total_cost = 0.0

    for obs in _iter_observations(client, from_dt, to_dt):
        n_obs += 1
        cost_details = obs.cost_details or {}
        usage_details = obs.usage_details or {}
        cost = _safe_float(cost_details.get("total"))
        tokens = _safe_int(usage_details.get("total"))
        by_name[obs.name]["count"] += 1
        by_name[obs.name]["total_cost"] += cost
        by_name[obs.name]["total_tokens"] += tokens
        total_cost += cost
        day = obs.start_time.strftime("%Y-%m-%d") if obs.start_time else ""
        if day:
            per_day_cost[day] += cost

    rows = [
        TopNRow(
            name=name,
            count=int(v["count"]),
            total_cost=v["total_cost"],
            avg_cost=v["total_cost"] / v["count"] if v["count"] else 0.0,
            total_tokens=int(v["total_tokens"]),
        )
        for name, v in by_name.items()
    ]
    rows.sort(key=lambda r: r.total_cost, reverse=True)
    return rows[:top_n], n_obs, total_cost, dict(per_day_cost)


def section_tokens_per_rag(
    client: Any, from_dt: datetime, to_dt: datetime
) -> tuple[float | None, float | None, float | None]:
    """avg / p50 / p95 tokens per RAG call via server-side metrics."""
    try:
        query = {
            "view": "observations",
            "metrics": [
                {"measure": "totalTokens", "aggregation": "avg"},
                {"measure": "totalTokens", "aggregation": "p50"},
                {"measure": "totalTokens", "aggregation": "p95"},
            ],
            "filters": [{"column": "name", "operator": "contains", "value": "rag"}],
            "fromTimestamp": from_dt.isoformat(),
            "toTimestamp": to_dt.isoformat(),
        }
        res = _metrics_query(client, query)
        rows = res.data or []
        if not rows:
            return None, None, None
        first = rows[0] if isinstance(rows, list) else rows
        avg = _safe_float(first.get("avg_totalTokens"))
        p50 = _safe_float(first.get("p50_totalTokens"))
        p95 = _safe_float(first.get("p95_totalTokens"))
        return avg, p50, p95
    except Exception:
        logger.debug("tokens-per-rag section failed", exc_info=True)
        return None, None, None


def section_by_strategy(client: Any, from_dt: datetime, to_dt: datetime) -> list[StrategyRow]:
    """Aggregate cost of search.manager.search spans by input.strategy."""
    by_strategy: dict[str, dict[str, float]] = defaultdict(
        lambda: {"count": 0.0, "total_cost": 0.0}
    )

    try:
        for obs in _iter_observations(client, from_dt, to_dt, name="search.manager.search"):
            inp = obs.input or {}
            if isinstance(inp, dict):
                strategy = str(inp.get("strategy", "unknown"))
            else:
                strategy = "unknown"
            cost = _safe_float((obs.cost_details or {}).get("total"))
            by_strategy[strategy]["count"] += 1
            by_strategy[strategy]["total_cost"] += cost
    except Exception:
        logger.debug("by-strategy section failed", exc_info=True)
        return []

    rows = [
        StrategyRow(
            strategy=s,
            count=int(v["count"]),
            total_cost=v["total_cost"],
            avg_cost=v["total_cost"] / v["count"] if v["count"] else 0.0,
        )
        for s, v in by_strategy.items()
    ]
    rows.sort(key=lambda r: r.total_cost, reverse=True)
    return rows


def section_by_model(client: Any, from_dt: datetime, to_dt: datetime) -> list[ModelRow]:
    """Cost-by-model via server-side metrics with providedModelName dimension."""
    try:
        query = {
            "view": "observations",
            "metrics": [{"measure": "totalCost", "aggregation": "sum"}],
            "dimensions": [{"field": "providedModelName"}],
            "fromTimestamp": from_dt.isoformat(),
            "toTimestamp": to_dt.isoformat(),
        }
        res = _metrics_query(client, query)
        rows_raw = res.data or []
        if not isinstance(rows_raw, list):
            return []
        total = sum(_safe_float(r.get("sum_totalCost")) for r in rows_raw) or 1.0
        rows = [
            ModelRow(
                model=str(r.get("providedModelName") or "(null)"),
                total_cost=_safe_float(r.get("sum_totalCost")),
                share_pct=100.0 * _safe_float(r.get("sum_totalCost")) / total,
            )
            for r in rows_raw
        ]
        rows.sort(key=lambda x: x.total_cost, reverse=True)
        return rows
    except Exception:
        logger.debug("by-model section failed", exc_info=True)
        return []


def _daily_run_rate(per_day_cost: dict[str, float]) -> tuple[list[DailyRow], float, float]:
    """Mean + P95 USD/day + sorted daily list."""
    if not per_day_cost:
        return [], 0.0, 0.0
    rows = [DailyRow(date=d, cost=c) for d, c in sorted(per_day_cost.items())]
    costs = [r.cost for r in rows]
    mean = statistics.fmean(costs) if costs else 0.0
    p95 = _percentile(costs, 95) if len(costs) >= 2 else (costs[0] if costs else 0.0)
    return rows, mean, p95


# ─── Output formatters ──────────────────────────────────────────────────────


def render_md(report: CostBaselineReport) -> str:
    """Markdown report — overwrite-mode, last run = current baseline."""
    lines: list[str] = []
    add = lines.append
    add("# Cost Baseline (auto-generated)")
    add("")
    add(f"> Generated: {report.generated_at}")
    add(f"> Period: {report.from_date} -> {report.to_date} ({report.n_days} days)")
    add("> Source: Langfuse Cloud (cloud.langfuse.com)")
    add("> Script: `scripts/analyze_langfuse_cost.py` (roadmap 260515 §5c.7)")
    add("")
    add("## Summary")
    add(f"- Total observations: {report.n_observations}")
    add(f"- Total cost: ${report.total_cost:.4f} USD")
    add(
        f"- Run-rate: ${report.cost_per_day_mean:.4f} USD/day (mean) / "
        f"${report.cost_per_day_p95:.4f} (P95)"
    )
    add("")

    if report.n_observations == 0:
        add("> ⚠️ No observations in this period. Baseline not meaningful yet —")
        add("> wait for ≥7 days of production traffic (roadmap §7).")
        add("")
        return "\n".join(lines) + "\n"

    add(f"## Top-{len(report.top_n)} expensive observations")
    add("| Rank | Name | Count | Total $ | Avg $ | Tokens |")
    add("|---|---|---|---|---|---|")
    for i, r in enumerate(report.top_n, 1):
        add(
            f"| {i} | `{r.name}` | {r.count} | "
            f"${r.total_cost:.4f} | ${r.avg_cost:.6f} | {r.total_tokens:,} |"
        )
    add("")

    add("## Tokens per RAG call")
    if report.avg_tokens is None:
        add("> No RAG observations matched in period.")
    else:
        add("| Metric | Value |")
        add("|---|---|")
        add(f"| Average | {report.avg_tokens:.1f} |")
        add(f"| P50     | {report.p50_tokens:.1f} |")
        add(f"| P95     | {report.p95_tokens:.1f} |")
    add("")

    add("## Cost by strategy (`search.manager.search`)")
    if not report.by_strategy:
        add("> No search.manager.search spans in period.")
    else:
        add("| Strategy | Count | Total $ | Avg $ |")
        add("|---|---|---|---|")
        for r in report.by_strategy:
            add(f"| `{r.strategy}` | {r.count} | " f"${r.total_cost:.4f} | ${r.avg_cost:.6f} |")
    add("")

    add("## Cost by model")
    if not report.by_model:
        add("> No model-tagged observations.")
    else:
        add("| Model | Total $ | Share % |")
        add("|---|---|---|")
        for r in report.by_model:
            add(f"| `{r.model}` | ${r.total_cost:.4f} | {r.share_pct:.1f} |")
    add("")

    add("## Daily run-rate")
    if not report.daily:
        add("> No daily samples.")
    else:
        max_cost = max((r.cost for r in report.daily), default=0.0) or 1.0
        bars = " ▁▂▃▄▅▆▇█"
        add("```")
        for r in report.daily:
            idx = min(len(bars) - 1, int(r.cost / max_cost * (len(bars) - 1)))
            add(f"{r.date}   {bars[idx]}  ${r.cost:.4f}")
        add("```")
    add("")
    return "\n".join(lines) + "\n"


def render_json(report: CostBaselineReport) -> str:
    return json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n"


# ─── Helpers ────────────────────────────────────────────────────────────────


def _safe_float(v: Any) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _safe_int(v: Any) -> int:
    try:
        return int(v) if v is not None else 0
    except (TypeError, ValueError):
        return 0


def _percentile(values: list[float], pct: int) -> float:
    """Inclusive percentile (linear interpolation)."""
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (pct / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=UTC)


def _default_window() -> tuple[str, str]:
    today_utc = datetime.now(UTC).date()
    from_d = today_utc - timedelta(days=7)
    to_d = today_utc - timedelta(days=1)
    return from_d.isoformat(), to_d.isoformat()


# ─── CLI ────────────────────────────────────────────────────────────────────


@app.command()
def main(
    from_date: str = typer.Option("", help="ISO date YYYY-MM-DD (default: today-7)"),
    to_date: str = typer.Option("", help="ISO date YYYY-MM-DD (default: today-1)"),
    output: str = typer.Option("md", help="Output format: md | json"),
    top_n: int = typer.Option(10, help="Top-N expensive observations to report"),
    tag: str = typer.Option("", help="Optional Langfuse tag filter"),  # noqa: ARG001
    dry_run: bool = typer.Option(False, help="Parse + format but do not write file"),
) -> None:
    """Generate cost baseline report from Langfuse Cloud data."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if not from_date or not to_date:
        d_from, d_to = _default_window()
        from_date = from_date or d_from
        to_date = to_date or d_to

    try:
        from_dt = _parse_date(from_date)
        to_dt = _parse_date(to_date) + timedelta(days=1)  # inclusive end-of-day
    except ValueError as e:
        typer.secho(f"Invalid date: {e}", fg=typer.colors.RED)
        raise typer.Exit(1) from e
    n_days = (to_dt - from_dt).days

    client = _get_langfuse_client()
    if client is None:
        typer.secho(
            "Langfuse not enabled or creds missing. "
            "Check .env (OBSERVABILITY__LANGFUSE_*) or repo secrets.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    typer.secho(
        f"Fetching observations: {from_date} -> {to_date} ({n_days} days)",
        fg=typer.colors.CYAN,
    )

    # Section 1 + per-day cost map
    top_rows, n_obs, total_cost, per_day = section_top_n(client, from_dt, to_dt, top_n)

    if n_obs == 0:
        typer.secho(
            "No observations in range — baseline file not updated (use --dry-run "
            "to confirm). See roadmap §7 'когда НЕ делать'.",
            fg=typer.colors.YELLOW,
        )

    # Section 2-4
    avg_t, p50_t, p95_t = section_tokens_per_rag(client, from_dt, to_dt)
    strategy_rows = section_by_strategy(client, from_dt, to_dt)
    model_rows = section_by_model(client, from_dt, to_dt)

    # Section 5
    daily_rows, mean_day, p95_day = _daily_run_rate(per_day)

    report = CostBaselineReport(
        generated_at=datetime.now(UTC).isoformat(),
        from_date=from_date,
        to_date=to_date,
        n_days=n_days,
        n_observations=n_obs,
        total_cost=total_cost,
        cost_per_day_mean=mean_day,
        cost_per_day_p95=p95_day,
        avg_tokens=avg_t,
        p50_tokens=p50_t,
        p95_tokens=p95_t,
        top_n=top_rows,
        by_strategy=strategy_rows,
        by_model=model_rows,
        daily=daily_rows,
    )

    rendered = render_md(report) if output == "md" else render_json(report)

    if dry_run:
        typer.secho("--dry-run: skipping file write", fg=typer.colors.YELLOW)
        sys.stdout.write(rendered)
        return

    # Real run: write file. JSON to stdout, MD to canonical path.
    if output == "json":
        sys.stdout.write(rendered)
    else:
        if n_obs == 0:
            typer.secho(
                "Baseline file NOT written on empty dataset.",
                fg=typer.colors.YELLOW,
            )
            return
        BASELINE_OUT.parent.mkdir(parents=True, exist_ok=True)
        BASELINE_OUT.write_text(rendered, encoding="utf-8")
        typer.secho(f"Wrote: {BASELINE_OUT}", fg=typer.colors.GREEN)


if __name__ == "__main__":
    app()
