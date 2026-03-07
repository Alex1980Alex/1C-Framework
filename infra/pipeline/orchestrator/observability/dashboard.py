"""Real-time monitoring dashboard for pipeline observability.

Provides visualization and monitoring capabilities:
- Aggregated view of logs, metrics, and traces
- Status panels with health indicators
- Real-time data refresh
- Export and reporting

"""

from __future__ import annotations

import threading
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Callable

from .logger import get_logger, get_memory_handler, LogLevel, LogEntry
from .metrics import get_metrics, MetricsCollector
from .tracer import get_tracer, get_span_processor, Span, SpanStatus


class PanelType(Enum):
    """Types of dashboard panels."""

    LOGS = "logs"
    METRICS = "metrics"
    TRACES = "traces"
    STATUS = "status"
    CUSTOM = "custom"


class HealthStatus(Enum):
    """Health status indicators."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

    @property
    def symbol(self) -> str:
        """Get symbol for display."""
        symbols = {
            HealthStatus.HEALTHY: "✓",
            HealthStatus.DEGRADED: "⚠",
            HealthStatus.UNHEALTHY: "✗",
            HealthStatus.UNKNOWN: "?",
        }
        return symbols[self]

    @property
    def color(self) -> str:
        """Get color for display."""
        colors = {
            HealthStatus.HEALTHY: "green",
            HealthStatus.DEGRADED: "yellow",
            HealthStatus.UNHEALTHY: "red",
            HealthStatus.UNKNOWN: "gray",
        }
        return colors[self]


@dataclass
class DashboardConfig:
    """Configuration for the dashboard."""

    title: str = "Pipeline Dashboard"
    refresh_interval_ms: int = 5000
    max_log_entries: int = 100
    max_traces: int = 50
    show_timestamps: bool = True
    compact_mode: bool = False
    auto_refresh: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "refresh_interval_ms": self.refresh_interval_ms,
            "max_log_entries": self.max_log_entries,
            "max_traces": self.max_traces,
            "show_timestamps": self.show_timestamps,
            "compact_mode": self.compact_mode,
            "auto_refresh": self.auto_refresh,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DashboardConfig":
        """Create from dictionary."""
        return cls(
            title=data.get("title", "Pipeline Dashboard"),
            refresh_interval_ms=data.get("refresh_interval_ms", 5000),
            max_log_entries=data.get("max_log_entries", 100),
            max_traces=data.get("max_traces", 50),
            show_timestamps=data.get("show_timestamps", True),
            compact_mode=data.get("compact_mode", False),
            auto_refresh=data.get("auto_refresh", True),
        )


@dataclass
class DashboardPanel:
    """A panel in the dashboard."""

    panel_id: str
    title: str
    panel_type: PanelType
    position: int = 0
    width: int = 1  # Grid columns (1-4)
    height: int = 1  # Grid rows
    visible: bool = True
    data_source: Optional[str] = None
    options: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "panel_id": self.panel_id,
            "title": self.title,
            "panel_type": self.panel_type.value,
            "position": self.position,
            "width": self.width,
            "height": self.height,
            "visible": self.visible,
            "data_source": self.data_source,
            "options": self.options,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DashboardPanel":
        """Create from dictionary."""
        return cls(
            panel_id=data["panel_id"],
            title=data["title"],
            panel_type=PanelType(data["panel_type"]),
            position=data.get("position", 0),
            width=data.get("width", 1),
            height=data.get("height", 1),
            visible=data.get("visible", True),
            data_source=data.get("data_source"),
            options=data.get("options", {}),
        )


@dataclass
class StatusCheck:
    """Result of a health check."""

    name: str
    status: HealthStatus
    message: str = ""
    last_check: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "last_check": self.last_check.isoformat(),
            "details": self.details,
        }


class Dashboard:
    """Real-time monitoring dashboard."""

    def __init__(
        self,
        config: Optional[DashboardConfig] = None,
    ):
        self.config = config or DashboardConfig()
        self._panels: Dict[str, DashboardPanel] = {}
        self._health_checks: Dict[str, Callable[[], StatusCheck]] = {}
        self._custom_data_sources: Dict[str, Callable[[], Any]] = {}
        self._lock = threading.Lock()
        self._last_refresh: Optional[datetime] = None

        # Register default health checks
        self._register_default_health_checks()

    def _register_default_health_checks(self) -> None:
        """Register default health checks."""
        self.register_health_check("logging", self._check_logging_health)
        self.register_health_check("metrics", self._check_metrics_health)
        self.register_health_check("tracing", self._check_tracing_health)

    def _check_logging_health(self) -> StatusCheck:
        """Check logging system health."""
        handler = get_memory_handler()
        if handler is None:
            return StatusCheck(
                name="logging",
                status=HealthStatus.UNKNOWN,
                message="Memory handler not configured",
            )

        entries = handler.get_entries(limit=10)
        error_count = sum(1 for e in entries if e.level >= LogLevel.ERROR)

        if error_count > 5:
            return StatusCheck(
                name="logging",
                status=HealthStatus.UNHEALTHY,
                message=f"High error rate: {error_count} errors in last 10 entries",
                details={"error_count": error_count},
            )
        elif error_count > 0:
            return StatusCheck(
                name="logging",
                status=HealthStatus.DEGRADED,
                message=f"{error_count} errors in last 10 entries",
                details={"error_count": error_count},
            )
        else:
            return StatusCheck(
                name="logging",
                status=HealthStatus.HEALTHY,
                message="No recent errors",
            )

    def _check_metrics_health(self) -> StatusCheck:
        """Check metrics system health."""
        try:
            metrics = get_metrics()
            data = metrics.collect_all()
            metric_count = (
                len(data.get("counters", {})) +
                len(data.get("gauges", {})) +
                len(data.get("histograms", {})) +
                len(data.get("timers", {}))
            )

            return StatusCheck(
                name="metrics",
                status=HealthStatus.HEALTHY,
                message=f"Collecting {metric_count} metrics",
                details={"metric_count": metric_count},
            )
        except Exception as e:
            return StatusCheck(
                name="metrics",
                status=HealthStatus.UNHEALTHY,
                message=f"Error: {str(e)}",
            )

    def _check_tracing_health(self) -> StatusCheck:
        """Check tracing system health."""
        processor = get_span_processor()
        if processor is None:
            return StatusCheck(
                name="tracing",
                status=HealthStatus.UNKNOWN,
                message="Span processor not configured",
            )

        spans = processor.get_spans(limit=20)
        error_spans = sum(1 for s in spans if s.status == SpanStatus.ERROR)

        if not spans:
            return StatusCheck(
                name="tracing",
                status=HealthStatus.HEALTHY,
                message="No traces recorded yet",
            )
        elif error_spans > len(spans) * 0.5:
            return StatusCheck(
                name="tracing",
                status=HealthStatus.UNHEALTHY,
                message=f"High error rate: {error_spans}/{len(spans)} spans failed",
                details={"error_spans": error_spans, "total_spans": len(spans)},
            )
        elif error_spans > 0:
            return StatusCheck(
                name="tracing",
                status=HealthStatus.DEGRADED,
                message=f"{error_spans} error spans in last {len(spans)}",
                details={"error_spans": error_spans, "total_spans": len(spans)},
            )
        else:
            return StatusCheck(
                name="tracing",
                status=HealthStatus.HEALTHY,
                message=f"All {len(spans)} recent spans successful",
                details={"total_spans": len(spans)},
            )

    def add_panel(self, panel: DashboardPanel) -> None:
        """Add a panel to the dashboard."""
        with self._lock:
            self._panels[panel.panel_id] = panel

    def remove_panel(self, panel_id: str) -> bool:
        """Remove a panel from the dashboard."""
        with self._lock:
            if panel_id in self._panels:
                del self._panels[panel_id]
                return True
            return False

    def get_panel(self, panel_id: str) -> Optional[DashboardPanel]:
        """Get a panel by ID."""
        with self._lock:
            return self._panels.get(panel_id)

    def list_panels(self) -> List[DashboardPanel]:
        """List all panels sorted by position."""
        with self._lock:
            panels = list(self._panels.values())
        return sorted(panels, key=lambda p: p.position)

    def register_health_check(
        self,
        name: str,
        check_fn: Callable[[], StatusCheck],
    ) -> None:
        """Register a health check function."""
        with self._lock:
            self._health_checks[name] = check_fn

    def register_data_source(
        self,
        name: str,
        source_fn: Callable[[], Any],
    ) -> None:
        """Register a custom data source."""
        with self._lock:
            self._custom_data_sources[name] = source_fn

    def get_health_status(self) -> Dict[str, StatusCheck]:
        """Run all health checks and get status."""
        results = {}
        with self._lock:
            checks = dict(self._health_checks)

        for name, check_fn in checks.items():
            try:
                results[name] = check_fn()
            except Exception as e:
                results[name] = StatusCheck(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Check failed: {str(e)}",
                )

        return results

    def get_overall_health(self) -> HealthStatus:
        """Get overall health status."""
        statuses = self.get_health_status()

        if not statuses:
            return HealthStatus.UNKNOWN

        status_values = [s.status for s in statuses.values()]

        if any(s == HealthStatus.UNHEALTHY for s in status_values):
            return HealthStatus.UNHEALTHY
        elif any(s == HealthStatus.DEGRADED for s in status_values):
            return HealthStatus.DEGRADED
        elif any(s == HealthStatus.UNKNOWN for s in status_values):
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    def get_logs(
        self,
        level: Optional[LogLevel] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent log entries."""
        handler = get_memory_handler()
        if handler is None:
            return []

        limit = limit or self.config.max_log_entries
        entries = handler.get_entries(level=level, limit=limit)

        return [e.to_dict() for e in entries]

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        try:
            metrics = get_metrics()
            return metrics.collect_all()
        except Exception:
            return {"error": "Failed to collect metrics"}

    def get_traces(
        self,
        trace_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent traces."""
        processor = get_span_processor()
        if processor is None:
            return []

        limit = limit or self.config.max_traces
        spans = processor.get_spans(trace_id=trace_id, limit=limit)

        return [s.to_dict() for s in spans]

    def get_panel_data(self, panel_id: str) -> Dict[str, Any]:
        """Get data for a specific panel."""
        panel = self.get_panel(panel_id)
        if panel is None:
            return {"error": "Panel not found"}

        if panel.panel_type == PanelType.LOGS:
            level = panel.options.get("level")
            if level:
                level = LogLevel(level)
            return {
                "entries": self.get_logs(level=level),
            }

        elif panel.panel_type == PanelType.METRICS:
            return self.get_metrics_summary()

        elif panel.panel_type == PanelType.TRACES:
            trace_id = panel.options.get("trace_id")
            return {
                "spans": self.get_traces(trace_id=trace_id),
            }

        elif panel.panel_type == PanelType.STATUS:
            return {
                "overall": self.get_overall_health().value,
                "checks": {
                    name: check.to_dict()
                    for name, check in self.get_health_status().items()
                },
            }

        elif panel.panel_type == PanelType.CUSTOM:
            if panel.data_source and panel.data_source in self._custom_data_sources:
                try:
                    return {"data": self._custom_data_sources[panel.data_source]()}
                except Exception as e:
                    return {"error": str(e)}
            return {"error": "No data source configured"}

        return {}

    def refresh(self) -> Dict[str, Any]:
        """Refresh all dashboard data."""
        self._last_refresh = datetime.now()

        result = {
            "timestamp": self._last_refresh.isoformat(),
            "config": self.config.to_dict(),
            "overall_health": self.get_overall_health().value,
            "panels": {},
        }

        for panel in self.list_panels():
            if panel.visible:
                result["panels"][panel.panel_id] = {
                    "config": panel.to_dict(),
                    "data": self.get_panel_data(panel.panel_id),
                }

        return result

    def render_console(self) -> str:
        """Render dashboard to console-friendly text."""
        lines = []
        lines.append("=" * 60)
        lines.append(f"  {self.config.title}")
        lines.append("=" * 60)
        lines.append("")

        # Overall health
        health = self.get_overall_health()
        lines.append(f"Overall Health: {health.symbol} {health.value.upper()}")
        lines.append("")

        # Health checks
        lines.append("Health Checks:")
        lines.append("-" * 40)
        for name, check in self.get_health_status().items():
            lines.append(f"  {check.status.symbol} {name}: {check.message}")
        lines.append("")

        # Recent logs summary
        logs = self.get_logs(limit=5)
        if logs:
            lines.append("Recent Logs:")
            lines.append("-" * 40)
            for log in logs[-5:]:
                level = log["level"].upper()[:4]
                msg = log["message"][:50]
                lines.append(f"  [{level}] {msg}")
            lines.append("")

        # Metrics summary
        metrics = self.get_metrics_summary()
        counter_count = len(metrics.get("counters", {}))
        gauge_count = len(metrics.get("gauges", {}))
        if counter_count or gauge_count:
            lines.append(f"Metrics: {counter_count} counters, {gauge_count} gauges")
            lines.append("")

        # Traces summary
        traces = self.get_traces(limit=5)
        if traces:
            lines.append("Recent Traces:")
            lines.append("-" * 40)
            for span in traces[-5:]:
                name = span["name"][:30]
                duration = span.get("duration_ms", "?")
                status = "✓" if span["status"] == "ok" else "✗"
                lines.append(f"  {status} {name} ({duration}ms)")
            lines.append("")

        lines.append("=" * 60)
        lines.append(f"Last refresh: {self._last_refresh or 'Never'}")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Export dashboard configuration."""
        return {
            "config": self.config.to_dict(),
            "panels": [p.to_dict() for p in self.list_panels()],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Dashboard":
        """Create dashboard from dictionary."""
        config = DashboardConfig.from_dict(data.get("config", {}))
        dashboard = cls(config=config)

        for panel_data in data.get("panels", []):
            panel = DashboardPanel.from_dict(panel_data)
            dashboard.add_panel(panel)

        return dashboard


def create_dashboard(
    title: str = "Pipeline Dashboard",
    include_default_panels: bool = True,
) -> Dashboard:
    """Create a dashboard with optional default panels."""
    config = DashboardConfig(title=title)
    dashboard = Dashboard(config=config)

    if include_default_panels:
        # Status panel
        dashboard.add_panel(DashboardPanel(
            panel_id="status",
            title="System Status",
            panel_type=PanelType.STATUS,
            position=0,
            width=4,
            height=1,
        ))

        # Logs panel
        dashboard.add_panel(DashboardPanel(
            panel_id="logs",
            title="Recent Logs",
            panel_type=PanelType.LOGS,
            position=1,
            width=2,
            height=2,
        ))

        # Metrics panel
        dashboard.add_panel(DashboardPanel(
            panel_id="metrics",
            title="Metrics",
            panel_type=PanelType.METRICS,
            position=2,
            width=2,
            height=2,
        ))

        # Traces panel
        dashboard.add_panel(DashboardPanel(
            panel_id="traces",
            title="Recent Traces",
            panel_type=PanelType.TRACES,
            position=3,
            width=4,
            height=2,
        ))

    return dashboard


# Global dashboard instance
_dashboard: Optional[Dashboard] = None
_dashboard_lock = threading.Lock()


def get_dashboard() -> Dashboard:
    """Get or create the global dashboard instance."""
    global _dashboard

    with _dashboard_lock:
        if _dashboard is None:
            _dashboard = create_dashboard()
        return _dashboard


def reset_dashboard() -> None:
    """Reset the global dashboard instance."""
    global _dashboard

    with _dashboard_lock:
        _dashboard = None
