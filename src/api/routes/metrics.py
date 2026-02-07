"""Metrics API endpoints (Phase 11.6).

Provides JSON and HTML dashboard for system metrics.

Author: Claude Code
Version: 1.2.0 - Phase 11.6: Metrics Dashboard
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.pdf_framework.observability.tracer import get_metrics_collector
from src.pdf_framework.agents.cache import get_llm_cache
from src.pdf_framework.embeddings.cache import get_embedding_cache
from src.pdf_framework.processing.cache import get_document_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/metrics", tags=["metrics"])

# HTML template for metrics dashboard
_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Framework Metrics</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
        }
        .timestamp { color: #666; font-size: 14px; margin-bottom: 30px; }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .card-title {
            font-size: 12px;
            text-transform: uppercase;
            color: #666;
            margin-bottom: 8px;
            font-weight: 600;
        }
        .card-value {
            font-size: 32px;
            font-weight: 700;
            color: #333;
        }
        .card-unit {
            font-size: 14px;
            color: #999;
            font-weight: 400;
        }
        .good { color: #22c55e; }
        .warning { color: #eab308; }
        .error { color: #ef4444; }
        .section {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .section-title {
            font-size: 18px;
            font-weight: 600;
            color: #333;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #eee;
        }
        table { width: 100%; border-collapse: collapse; }
        th, td {
            text-align: left;
            padding: 12px 8px;
            border-bottom: 1px solid #eee;
        }
        th {
            font-size: 12px;
            text-transform: uppercase;
            color: #666;
            font-weight: 600;
        }
        td { font-size: 14px; color: #333; }
        tr:last-child td { border-bottom: none; }
        .progress-bar {
            background: #eee;
            border-radius: 4px;
            height: 8px;
            overflow: hidden;
        }
        .progress-fill {
            height: 100%;
            background: #3b82f6;
            transition: width 0.3s;
        }
        .tag {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
        }
        .tag-blue { background: #dbeafe; color: #1e40af; }
        .tag-green { background: #dcfce7; color: #166534; }
        .tag-purple { background: #f3e8ff; color: #7c3aed; }
        .footer {
            text-align: center;
            color: #999;
            font-size: 12px;
            margin-top: 30px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>PDF Framework Metrics</h1>
        <div class="timestamp">Last updated: <span id="timestamp">{timestamp}</span></div>

        <!-- Key Metrics -->
        <div class="grid">
            <div class="card">
                <div class="card-title">Total Queries</div>
                <div class="card-value">{queries_total}</div>
            </div>
            <div class="card">
                <div class="card-title">Queries Today</div>
                <div class="card-value">{queries_today}</div>
            </div>
            <div class="card">
                <div class="card-title">Avg Latency</div>
                <div class="card-value">{avg_latency_ms:.1f}<span class="card-unit">ms</span></div>
            </div>
            <div class="card">
                <div class="card-title">P95 Latency</div>
                <div class="card-value">{p95_latency_ms:.1f}<span class="card-unit">ms</span></div>
            </div>
            <div class="card">
                <div class="card-title">Cache Hit Rate</div>
                <div class="card-value {cache_class}">{cache_hit_rate:.1%}</div>
            </div>
            <div class="card">
                <div class="card-title">Error Rate</div>
                <div class="card-value {error_class}">{error_rate:.1%}</div>
            </div>
        </div>

        <!-- Cache Statistics -->
        <div class="section">
            <div class="section-title">Cache Statistics</div>
            <table>
                <thead>
                    <tr>
                        <th>Cache Type</th>
                        <th>Status</th>
                        <th>Hits</th>
                        <th>Misses</th>
                        <th>Total</th>
                        <th>Hit Rate</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>Embedding Cache</strong></td>
                        <td><span class="tag tag-green">Active</span></td>
                        <td>{emb_hits}</td>
                        <td>{emb_misses}</td>
                        <td>{emb_total}</td>
                        <td>
                            <div>{emb_hit_rate:.1%}</div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: {emb_hit_rate_pct:.0f}%"></div>
                            </div>
                        </td>
                    </tr>
                    <tr>
                        <td><strong>LLM Response Cache</strong></td>
                        <td><span class="tag tag-green">Active</span></td>
                        <td>{llm_hits}</td>
                        <td>{llm_misses}</td>
                        <td>{llm_total}</td>
                        <td>
                            <div>{llm_hit_rate:.1%}</div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: {llm_hit_rate_pct:.0f}%"></div>
                            </div>
                        </td>
                    </tr>
                    <tr>
                        <td><strong>Document Cache</strong></td>
                        <td><span class="tag tag-blue">Passive</span></td>
                        <td>{doc_hits}</td>
                        <td>{doc_stale}</td>
                        <td>{doc_total}</td>
                        <td>—</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <!-- Strategy Usage -->
        <div class="section">
            <div class="section-title">Search Strategy Usage</div>
            <table>
                <thead>
                    <tr>
                        <th>Strategy</th>
                        <th>Queries</th>
                        <th>Share</th>
                    </tr>
                </thead>
                <tbody>
                    {strategy_rows}
                </tbody>
            </table>
        </div>

        <!-- Quick Actions -->
        <div class="section">
            <div class="section-title">Quick Actions</div>
            <table>
                <tr>
                    <td><strong>Refresh</strong></td>
                    <td>Auto-refresh every 30 seconds</td>
                </tr>
                <tr>
                    <td><strong>CLI Cache Commands</strong></td>
                    <td><code>pdf-framework cache stats</code> | <code>pdf-framework cache clear</code></td>
                </tr>
            </table>
        </div>

        <div class="footer">
            PDF Framework v1.2.0 • Phase 11: Observability & Caching
        </div>
    </div>

    <script>
        // Auto-refresh every 30 seconds
        let countdown = 30;
        setInterval(() => {{
            countdown--;
            if (countdown <= 0) {{
                window.location.reload();
                countdown = 30;
            }}
        }}, 1000);

        // Update timestamp
        document.getElementById('timestamp').textContent = new Date().toLocaleString();
    </script>
</body>
</html>
"""


@router.get("")
async def get_metrics():
    """Get system metrics as JSON."""
    metrics_collector = get_metrics_collector()
    llm_cache = get_llm_cache()
    emb_cache = get_embedding_cache()
    doc_cache = get_document_cache()

    # Get base metrics
    metrics = metrics_collector.get_metrics()

    # Get cache stats
    llm_cache_stats = llm_cache.get_stats()
    emb_cache_stats = emb_cache.get_stats()
    doc_cache_stats = doc_cache.get_stats()

    # Calculate combined hit rate
    total_requests = llm_cache_stats["hits"] + llm_cache_stats["misses"] + emb_cache_stats.hits + emb_cache_stats.misses
    total_hits = llm_cache_stats["hits"] + emb_cache_stats.hits
    combined_hit_rate = total_hits / total_requests if total_requests > 0 else 0.0

    return {
        **metrics,
        "embedding_cache": {
            "hits": emb_cache_stats.hits,
            "misses": emb_cache_stats.misses,
            "total": emb_cache_stats.total,
            "hit_rate": emb_cache_stats.hit_rate,
        },
        "llm_cache": llm_cache_stats,
        "document_cache": {
            "hits": doc_cache_stats.get("hits", 0),
            "misses": doc_cache_stats.get("misses", 0),
            "stale": doc_cache_stats.get("stale", 0),
        },
        "combined_hit_rate": combined_hit_rate,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/html", response_class=HTMLResponse)
async def get_metrics_html():
    """Get metrics dashboard as HTML page."""
    metrics_data = await get_metrics()

    # Format strategy rows
    strategy_rows = []
    strategies = metrics_data.get("strategies_usage", {})
    total_queries = sum(strategies.values()) if strategies else 1

    for strategy, count in sorted(strategies.items(), key=lambda x: x[1], reverse=True):
        share = count / total_queries * 100 if total_queries > 0 else 0
        tag_color = "blue" if strategy == "vector" else "green" if strategy == "hybrid" else "purple"
        strategy_rows.append(f"""
            <tr>
                <td><span class="tag tag-{tag_color}">{strategy}</span></td>
                <td>{count}</td>
                <td>{share:.1f}%</td>
            </tr>
        """)

    if not strategy_rows:
        strategy_rows = '<tr><td colspan="3" style="text-align:center;color:#999;">No data yet</td></tr>'

    # Determine color classes
    cache_rate = metrics_data.get("cache_hit_rate", 0)
    cache_class = "good" if cache_rate > 0.5 else "warning" if cache_rate > 0.2 else ""

    error_rate = metrics_data.get("error_rate", 0)
    error_class = "" if error_rate < 0.01 else "warning" if error_rate < 0.05 else "error"

    # Fill template
    html = _DASHBOARD_HTML.format(
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        queries_total=metrics_data.get("queries_total", 0),
        queries_today=metrics_data.get("queries_today", 0),
        avg_latency_ms=metrics_data.get("avg_latency_ms", 0),
        p95_latency_ms=metrics_data.get("p95_latency_ms", 0),
        cache_hit_rate=cache_rate,
        cache_class=cache_class,
        error_rate=error_rate,
        error_class=error_class,
        emb_hits=metrics_data["embedding_cache"]["hits"],
        emb_misses=metrics_data["embedding_cache"]["misses"],
        emb_total=metrics_data["embedding_cache"]["total"],
        emb_hit_rate=metrics_data["embedding_cache"]["hit_rate"],
        emb_hit_rate_pct=metrics_data["embedding_cache"]["hit_rate"] * 100,
        llm_hits=metrics_data["llm_cache"]["hits"],
        llm_misses=metrics_data["llm_cache"]["misses"],
        llm_total=metrics_data["llm_cache"]["total"],
        llm_hit_rate=metrics_data["llm_cache"]["hit_rate"],
        llm_hit_rate_pct=metrics_data["llm_cache"]["hit_rate"] * 100,
        doc_hits=metrics_data["document_cache"]["hits"],
        doc_stale=metrics_data["document_cache"]["stale"],
        doc_total=metrics_data["document_cache"]["hits"] + metrics_data["document_cache"]["stale"],
        strategy_rows="".join(strategy_rows),
    )

    return html


@router.post("/reset")
async def reset_metrics():
    """Reset daily metrics counter."""
    from datetime import datetime, timezone

    metrics_collector = get_metrics_collector()
    metrics_collector._queries_today = 0
    metrics_collector._last_reset = datetime.now(timezone.utc)

    return {"status": "ok", "message": "Daily metrics reset"}
