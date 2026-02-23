"""Metrics API endpoints (Phase 11.6).

Provides JSON and HTML dashboard for system metrics.

Author: Claude Code
Version: 1.2.0 - Phase 11.6: Metrics Dashboard
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from src.pdf_framework.observability.tracer import get_metrics_collector
from src.pdf_framework.observability.hook_metrics_db import HookMetricsDB
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
        <div class="timestamp">Last updated: <span id="timestamp">$timestamp</span></div>

        <!-- Key Metrics -->
        <div class="grid">
            <div class="card">
                <div class="card-title">Total Queries</div>
                <div class="card-value">$queries_total</div>
            </div>
            <div class="card">
                <div class="card-title">Queries Today</div>
                <div class="card-value">$queries_today</div>
            </div>
            <div class="card">
                <div class="card-title">Avg Latency</div>
                <div class="card-value">$avg_latency_ms<span class="card-unit">ms</span></div>
            </div>
            <div class="card">
                <div class="card-title">P95 Latency</div>
                <div class="card-value">$p95_latency_ms<span class="card-unit">ms</span></div>
            </div>
            <div class="card">
                <div class="card-title">Cache Hit Rate</div>
                <div class="card-value $cache_class">$cache_hit_rate</div>
            </div>
            <div class="card">
                <div class="card-title">Error Rate</div>
                <div class="card-value $error_class">$error_rate</div>
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
                        <td>$emb_hits</td>
                        <td>$emb_misses</td>
                        <td>$emb_total</td>
                        <td>
                            <div>$emb_hit_rate</div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${emb_hit_rate_pct}%"></div>
                            </div>
                        </td>
                    </tr>
                    <tr>
                        <td><strong>LLM Response Cache</strong></td>
                        <td><span class="tag tag-green">Active</span></td>
                        <td>$llm_hits</td>
                        <td>$llm_misses</td>
                        <td>$llm_total</td>
                        <td>
                            <div>$llm_hit_rate</div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${llm_hit_rate_pct}%"></div>
                            </div>
                        </td>
                    </tr>
                    <tr>
                        <td><strong>Document Cache</strong></td>
                        <td><span class="tag tag-blue">Passive</span></td>
                        <td>$doc_hits</td>
                        <td>$doc_stale</td>
                        <td>$doc_total</td>
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
                    $strategy_rows
                </tbody>
            </table>
        </div>

        <!-- Hook Invocations -->
        <div class="section">
            <div class="section-title">Hook Invocations (24h)</div>
            <table>
                <thead>
                    <tr>
                        <th>Hook</th>
                        <th>Count</th>
                        <th>Avg (ms)</th>
                        <th>P95 (ms)</th>
                        <th>Blocks</th>
                        <th>Errors</th>
                    </tr>
                </thead>
                <tbody>
                    $hook_rows
                </tbody>
            </table>
        </div>

        <!-- Skill Activations -->
        <div class="section">
            <div class="section-title">Skill Activations (24h)</div>
            <div class="grid" style="margin-bottom: 15px;">
                <div class="card">
                    <div class="card-title">Activation Rate</div>
                    <div class="card-value $activation_rate_class">$activation_rate</div>
                </div>
                <div class="card">
                    <div class="card-title">Recommended</div>
                    <div class="card-value">$total_recommended</div>
                </div>
                <div class="card">
                    <div class="card-title">Activated</div>
                    <div class="card-value">$total_activated</div>
                </div>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Skill</th>
                        <th>Recommended</th>
                        <th>Activated</th>
                        <th>Rate</th>
                    </tr>
                </thead>
                <tbody>
                    $skill_rows
                </tbody>
            </table>
        </div>

        <!-- Enforcement & Errors -->
        <div class="section">
            <div class="section-title">Enforcement &amp; Errors</div>
            <div class="grid" style="margin-bottom: 15px;">
                <div class="card">
                    <div class="card-title">Total Blocks</div>
                    <div class="card-value warning">$enforcement_blocks</div>
                </div>
                <div class="card">
                    <div class="card-title">Block Rate</div>
                    <div class="card-value">$enforcement_block_rate</div>
                </div>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Hook</th>
                        <th>Error</th>
                    </tr>
                </thead>
                <tbody>
                    $error_rows
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
        setInterval(() => {
            countdown--;
            if (countdown <= 0) {
                window.location.reload();
                countdown = 30;
            }
        }, 1000);

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

    # Hook/Skill metrics from HookMetricsDB
    try:
        hook_db = HookMetricsDB()
        hook_db.ingest_from_logs()
        hook_metrics = hook_db.get_hook_metrics()
        skill_metrics = hook_db.get_skill_metrics()
        accuracy = hook_db.get_accuracy_metrics()
        errors = hook_db.get_error_log(limit=20)
        enforcement = hook_db.get_enforcement_metrics()
        hook_db.close()
    except Exception:
        hook_metrics = []
        skill_metrics = {
            "total_recommended": 0,
            "total_activated": 0,
            "activation_rate": 0.0,
            "per_skill": {},
        }
        accuracy = {
            "total_prompts": 0,
            "matched_prompts": 0,
            "missed_prompts": 0,
            "match_rate": 0.0,
        }
        errors = []
        enforcement = {
            "total_blocks": 0,
            "total_allows": 0,
            "block_rate": 0.0,
            "per_hook": {},
        }

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
        "hook_metrics": hook_metrics,
        "skill_metrics": skill_metrics,
        "accuracy": accuracy,
        "errors": errors,
        "enforcement": enforcement,
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
        strategy_rows.append('<tr><td colspan="3" style="text-align:center;color:#999;">No data yet</td></tr>')

    # Build hook invocation rows
    hook_rows = []
    for h in metrics_data.get("hook_metrics", []):
        hook_name = h.get("hook", "unknown")
        # Shorten hook name (remove .py suffix, trim path)
        short_name = hook_name.rsplit("/", 1)[-1].replace(".py", "")
        blocks_class = ' class="warning"' if h.get("blocks", 0) > 0 else ""
        errors_class = ' class="error"' if h.get("errors", 0) > 0 else ""
        hook_rows.append(f"""
            <tr>
                <td><strong>{short_name}</strong></td>
                <td>{h.get('count', 0)}</td>
                <td>{h.get('avg_ms', 0):.1f}</td>
                <td>{h.get('p95_ms', 0)}</td>
                <td{blocks_class}>{h.get('blocks', 0)}</td>
                <td{errors_class}>{h.get('errors', 0)}</td>
            </tr>
        """)
    if not hook_rows:
        hook_rows.append('<tr><td colspan="6" style="text-align:center;color:#999;">No hook data yet</td></tr>')

    # Build skill activation rows
    skill_rows = []
    skill_data = metrics_data.get("skill_metrics", {})
    per_skill = skill_data.get("per_skill", {})
    for skill_name in sorted(per_skill.keys()):
        s = per_skill[skill_name]
        rate = s.get("rate", 0)
        rate_class = "good" if rate >= 70 else "warning" if rate >= 40 else ""
        skill_rows.append(f"""
            <tr>
                <td><strong>{skill_name}</strong></td>
                <td>{s.get('recommended', 0)}</td>
                <td>{s.get('activated', 0)}</td>
                <td class="{rate_class}">{rate:.1f}%</td>
            </tr>
        """)
    if not skill_rows:
        skill_rows.append('<tr><td colspan="4" style="text-align:center;color:#999;">No skill data yet</td></tr>')

    # Build error rows
    error_rows = []
    for err in metrics_data.get("errors", [])[:10]:
        ts = err.get("timestamp", "")[:19]
        hook_name = (err.get("hook") or "unknown").rsplit("/", 1)[-1].replace(".py", "")
        error_msg = (err.get("error") or "—")[:80]
        error_rows.append(f"""
            <tr>
                <td style="white-space:nowrap;">{ts}</td>
                <td>{hook_name}</td>
                <td style="color:#ef4444;">{error_msg}</td>
            </tr>
        """)
    if not error_rows:
        error_rows.append('<tr><td colspan="3" style="text-align:center;color:#999;">No errors</td></tr>')

    # Activation rate color
    act_rate = skill_data.get("activation_rate", 0)
    activation_rate_class = "good" if act_rate >= 70 else "warning" if act_rate >= 40 else ""

    # Enforcement data
    enforcement = metrics_data.get("enforcement", {})

    # Determine color classes
    cache_rate = metrics_data.get("cache_hit_rate", 0)
    cache_class = "good" if cache_rate > 0.5 else "warning" if cache_rate > 0.2 else ""

    error_rate = metrics_data.get("error_rate", 0)
    error_class = "" if error_rate < 0.01 else "warning" if error_rate < 0.05 else "error"

    # Fill template using string.Template ($var) to avoid CSS brace conflicts
    from string import Template

    emb = metrics_data["embedding_cache"]
    llm = metrics_data["llm_cache"]
    doc = metrics_data["document_cache"]

    html = Template(_DASHBOARD_HTML).safe_substitute(
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        queries_total=metrics_data.get("queries_total", 0),
        queries_today=metrics_data.get("queries_today", 0),
        avg_latency_ms=f"{metrics_data.get('avg_latency_ms', 0):.1f}",
        p95_latency_ms=f"{metrics_data.get('p95_latency_ms', 0):.1f}",
        cache_hit_rate=f"{cache_rate:.1%}",
        cache_class=cache_class,
        error_rate=f"{error_rate:.1%}",
        error_class=error_class,
        emb_hits=emb["hits"],
        emb_misses=emb["misses"],
        emb_total=emb["total"],
        emb_hit_rate=f"{emb['hit_rate']:.1%}",
        emb_hit_rate_pct=f"{emb['hit_rate'] * 100:.0f}",
        llm_hits=llm["hits"],
        llm_misses=llm["misses"],
        llm_total=llm["total"],
        llm_hit_rate=f"{llm['hit_rate']:.1%}",
        llm_hit_rate_pct=f"{llm['hit_rate'] * 100:.0f}",
        doc_hits=doc["hits"],
        doc_stale=doc["stale"],
        doc_total=doc["hits"] + doc["stale"],
        strategy_rows="".join(strategy_rows),
        hook_rows="".join(hook_rows),
        skill_rows="".join(skill_rows),
        error_rows="".join(error_rows),
        activation_rate=f"{act_rate:.1f}%",
        activation_rate_class=activation_rate_class,
        total_recommended=skill_data.get("total_recommended", 0),
        total_activated=skill_data.get("total_activated", 0),
        enforcement_blocks=enforcement.get("total_blocks", 0),
        enforcement_block_rate=f"{enforcement.get('block_rate', 0):.1f}%",
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


# =============================================================================
# Phase 46: Prometheus Metrics Endpoint
# =============================================================================

from fastapi.responses import Response

from src.pdf_framework.observability.prometheus_metrics import (
    get_content_type,
    get_metrics_text,
)


@router.get("/prometheus")
async def get_prometheus_metrics():
    """
    F3.3.3: Get metrics in Prometheus exposition format.

    Returns metrics in Prometheus text format for scraping by Prometheus server.
    Includes:
    - query_latency_seconds (histogram)
    - query_total (counter)
    - cache_hit_total, cache_miss_total (counters)
    - token_usage_total (counter)
    - error_total (counter)
    """
    metrics_text = get_metrics_text()
    content_type = get_content_type()

    return Response(content=metrics_text, media_type=content_type)
