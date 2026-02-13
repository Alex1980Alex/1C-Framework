"""Enterprise Analytics API endpoints (Phase 40).

Provides JSON endpoints for:
- Query analytics (stats, recent queries, popular queries)
- Cost tracking (per-model token usage and cost estimates)
- Audit log (compliance trail, per-user activity)
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from src.api.dependencies.components import Components, get_components

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ---------- Response Models ----------


class QueryStatsResponse(BaseModel):
    total_queries: int = 0
    avg_latency_ms: float = 0.0
    total_tokens_input: int = 0
    total_tokens_output: int = 0
    avg_quality: float = 0.0
    avg_results: float = 0.0
    top_strategies: list[dict[str, Any]] = Field(default_factory=list)
    top_agents: list[dict[str, Any]] = Field(default_factory=list)
    popular_queries: list[dict[str, Any]] = Field(default_factory=list)


class CostStatsResponse(BaseModel):
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    by_model: dict[str, Any] = Field(default_factory=dict)


class AuditStatsResponse(BaseModel):
    total_events: int = 0
    unique_users: int = 0
    by_event_type: dict[str, int] = Field(default_factory=dict)
    by_agent: dict[str, int] = Field(default_factory=dict)


class AnalyticsSummaryResponse(BaseModel):
    queries: QueryStatsResponse = Field(default_factory=QueryStatsResponse)
    costs: CostStatsResponse = Field(default_factory=CostStatsResponse)
    audit: AuditStatsResponse = Field(default_factory=AuditStatsResponse)


# ---------- Endpoints ----------


@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def get_analytics_summary(
    components: Components = Depends(get_components),
):
    """Get combined analytics summary: queries + costs + audit."""
    query_stats = {}
    cost_stats = {}
    audit_stats = {}

    tracker = getattr(components, "query_tracker", None)
    if tracker is not None:
        query_stats = tracker.get_stats()

    cost_tracker = getattr(components, "cost_tracker", None)
    if cost_tracker is not None:
        cost_stats = cost_tracker.get_stats()

    audit_logger = getattr(components, "audit_logger", None)
    if audit_logger is not None:
        audit_stats = audit_logger.get_stats()

    return AnalyticsSummaryResponse(
        queries=QueryStatsResponse(**query_stats) if query_stats else QueryStatsResponse(),
        costs=CostStatsResponse(**cost_stats) if cost_stats else CostStatsResponse(),
        audit=AuditStatsResponse(**audit_stats) if audit_stats else AuditStatsResponse(),
    )


@router.get("/queries", response_model=QueryStatsResponse)
async def get_query_stats(
    components: Components = Depends(get_components),
):
    """Get query analytics: total, latency, strategies, popular queries."""
    tracker = getattr(components, "query_tracker", None)
    if tracker is None:
        return QueryStatsResponse()
    stats = tracker.get_stats()
    return QueryStatsResponse(**stats)


@router.get("/queries/recent")
async def get_recent_queries(
    limit: int = Query(default=50, ge=1, le=500),
    components: Components = Depends(get_components),
):
    """Get recent tracked queries."""
    tracker = getattr(components, "query_tracker", None)
    if tracker is None:
        return []
    return tracker.get_recent(limit=limit)


@router.get("/costs", response_model=CostStatsResponse)
async def get_cost_stats(
    components: Components = Depends(get_components),
):
    """Get cost tracking: tokens and estimated USD by model."""
    cost_tracker = getattr(components, "cost_tracker", None)
    if cost_tracker is None:
        return CostStatsResponse()
    stats = cost_tracker.get_stats()
    return CostStatsResponse(**stats)


@router.get("/audit")
async def get_audit_log(
    limit: int = Query(default=100, ge=1, le=1000),
    components: Components = Depends(get_components),
):
    """Get recent audit log entries."""
    audit_logger = getattr(components, "audit_logger", None)
    if audit_logger is None:
        return []
    return audit_logger.get_recent(limit=limit)


@router.get("/audit/stats", response_model=AuditStatsResponse)
async def get_audit_stats(
    components: Components = Depends(get_components),
):
    """Get audit statistics: event types, agents, unique users."""
    audit_logger = getattr(components, "audit_logger", None)
    if audit_logger is None:
        return AuditStatsResponse()
    stats = audit_logger.get_stats()
    return AuditStatsResponse(**stats)


@router.get("/audit/user/{user_id}")
async def get_user_audit(
    user_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    components: Components = Depends(get_components),
):
    """Get audit log entries for a specific user."""
    audit_logger = getattr(components, "audit_logger", None)
    if audit_logger is None:
        return []
    return audit_logger.get_by_user(user_id=user_id, limit=limit)
