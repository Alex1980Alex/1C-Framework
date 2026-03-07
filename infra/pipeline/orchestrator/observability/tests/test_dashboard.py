"""Tests for monitoring dashboard module."""

import pytest
from datetime import datetime

from .dashboard import (
    PanelType,
    HealthStatus,
    DashboardConfig,
    DashboardPanel,
    StatusCheck,
    Dashboard,
    create_dashboard,
    get_dashboard,
    reset_dashboard,
)
from .logger import configure_logging, get_logger, LogLevel
from .metrics import get_metrics, reset_metrics
from .tracer import configure_tracing, get_tracer


class TestPanelType:
    """Tests for PanelType enum."""

    def test_panel_type_values(self):
        """Test panel type values."""
        assert PanelType.LOGS.value == "logs"
        assert PanelType.METRICS.value == "metrics"
        assert PanelType.TRACES.value == "traces"
        assert PanelType.STATUS.value == "status"
        assert PanelType.CUSTOM.value == "custom"


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_health_status_values(self):
        """Test health status values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.UNKNOWN.value == "unknown"

    def test_health_status_symbols(self):
        """Test health status symbols."""
        assert HealthStatus.HEALTHY.symbol == "✓"
        assert HealthStatus.DEGRADED.symbol == "⚠"
        assert HealthStatus.UNHEALTHY.symbol == "✗"
        assert HealthStatus.UNKNOWN.symbol == "?"

    def test_health_status_colors(self):
        """Test health status colors."""
        assert HealthStatus.HEALTHY.color == "green"
        assert HealthStatus.DEGRADED.color == "yellow"
        assert HealthStatus.UNHEALTHY.color == "red"
        assert HealthStatus.UNKNOWN.color == "gray"


class TestDashboardConfig:
    """Tests for DashboardConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = DashboardConfig()

        assert config.title == "Pipeline Dashboard"
        assert config.refresh_interval_ms == 5000
        assert config.max_log_entries == 100
        assert config.max_traces == 50
        assert config.show_timestamps is True
        assert config.compact_mode is False
        assert config.auto_refresh is True

    def test_custom_config(self):
        """Test custom configuration."""
        config = DashboardConfig(
            title="Custom Dashboard",
            refresh_interval_ms=1000,
            max_log_entries=50,
            compact_mode=True,
        )

        assert config.title == "Custom Dashboard"
        assert config.refresh_interval_ms == 1000
        assert config.max_log_entries == 50
        assert config.compact_mode is True

    def test_config_to_dict(self):
        """Test configuration serialization."""
        config = DashboardConfig(title="Test")
        result = config.to_dict()

        assert result["title"] == "Test"
        assert "refresh_interval_ms" in result
        assert "max_log_entries" in result
        assert "auto_refresh" in result

    def test_config_from_dict(self):
        """Test configuration deserialization."""
        data = {
            "title": "From Dict",
            "refresh_interval_ms": 2000,
            "compact_mode": True,
        }
        config = DashboardConfig.from_dict(data)

        assert config.title == "From Dict"
        assert config.refresh_interval_ms == 2000
        assert config.compact_mode is True
        assert config.max_log_entries == 100  # Default

    def test_config_roundtrip(self):
        """Test serialization roundtrip."""
        original = DashboardConfig(
            title="Roundtrip Test",
            refresh_interval_ms=3000,
            max_log_entries=75,
        )
        data = original.to_dict()
        restored = DashboardConfig.from_dict(data)

        assert restored.title == original.title
        assert restored.refresh_interval_ms == original.refresh_interval_ms
        assert restored.max_log_entries == original.max_log_entries


class TestDashboardPanel:
    """Tests for DashboardPanel."""

    def test_create_panel(self):
        """Test creating a panel."""
        panel = DashboardPanel(
            panel_id="test-panel",
            title="Test Panel",
            panel_type=PanelType.LOGS,
        )

        assert panel.panel_id == "test-panel"
        assert panel.title == "Test Panel"
        assert panel.panel_type == PanelType.LOGS
        assert panel.position == 0
        assert panel.width == 1
        assert panel.height == 1
        assert panel.visible is True

    def test_panel_with_options(self):
        """Test panel with custom options."""
        panel = DashboardPanel(
            panel_id="custom",
            title="Custom",
            panel_type=PanelType.METRICS,
            position=5,
            width=2,
            height=3,
            options={"filter": "cpu"},
        )

        assert panel.position == 5
        assert panel.width == 2
        assert panel.height == 3
        assert panel.options["filter"] == "cpu"

    def test_panel_to_dict(self):
        """Test panel serialization."""
        panel = DashboardPanel(
            panel_id="test",
            title="Test",
            panel_type=PanelType.TRACES,
            width=2,
        )
        result = panel.to_dict()

        assert result["panel_id"] == "test"
        assert result["title"] == "Test"
        assert result["panel_type"] == "traces"
        assert result["width"] == 2

    def test_panel_from_dict(self):
        """Test panel deserialization."""
        data = {
            "panel_id": "from-dict",
            "title": "From Dict",
            "panel_type": "status",
            "position": 3,
            "visible": False,
        }
        panel = DashboardPanel.from_dict(data)

        assert panel.panel_id == "from-dict"
        assert panel.panel_type == PanelType.STATUS
        assert panel.position == 3
        assert panel.visible is False


class TestStatusCheck:
    """Tests for StatusCheck."""

    def test_create_status_check(self):
        """Test creating status check."""
        check = StatusCheck(
            name="test-check",
            status=HealthStatus.HEALTHY,
            message="All good",
        )

        assert check.name == "test-check"
        assert check.status == HealthStatus.HEALTHY
        assert check.message == "All good"
        assert isinstance(check.last_check, datetime)

    def test_status_check_with_details(self):
        """Test status check with details."""
        check = StatusCheck(
            name="detailed",
            status=HealthStatus.DEGRADED,
            message="Some issues",
            details={"error_count": 3, "warning_count": 5},
        )

        assert check.details["error_count"] == 3
        assert check.details["warning_count"] == 5

    def test_status_check_to_dict(self):
        """Test status check serialization."""
        check = StatusCheck(
            name="serialize",
            status=HealthStatus.UNHEALTHY,
            message="Failed",
        )
        result = check.to_dict()

        assert result["name"] == "serialize"
        assert result["status"] == "unhealthy"
        assert result["message"] == "Failed"
        assert "last_check" in result


class TestDashboard:
    """Tests for Dashboard."""

    def test_dashboard_creation(self):
        """Test dashboard creation."""
        dashboard = Dashboard()

        assert dashboard.config.title == "Pipeline Dashboard"
        assert len(dashboard.list_panels()) == 0

    def test_dashboard_with_config(self):
        """Test dashboard with custom config."""
        config = DashboardConfig(title="Custom Title")
        dashboard = Dashboard(config=config)

        assert dashboard.config.title == "Custom Title"

    def test_add_panel(self):
        """Test adding a panel."""
        dashboard = Dashboard()
        panel = DashboardPanel(
            panel_id="test",
            title="Test",
            panel_type=PanelType.LOGS,
        )

        dashboard.add_panel(panel)

        assert len(dashboard.list_panels()) == 1
        assert dashboard.get_panel("test") is not None

    def test_remove_panel(self):
        """Test removing a panel."""
        dashboard = Dashboard()
        panel = DashboardPanel(
            panel_id="remove-me",
            title="Remove",
            panel_type=PanelType.LOGS,
        )
        dashboard.add_panel(panel)

        result = dashboard.remove_panel("remove-me")

        assert result is True
        assert dashboard.get_panel("remove-me") is None

    def test_remove_nonexistent_panel(self):
        """Test removing non-existent panel."""
        dashboard = Dashboard()

        result = dashboard.remove_panel("nonexistent")

        assert result is False

    def test_list_panels_sorted(self):
        """Test panels are sorted by position."""
        dashboard = Dashboard()
        dashboard.add_panel(DashboardPanel(
            panel_id="third",
            title="Third",
            panel_type=PanelType.LOGS,
            position=3,
        ))
        dashboard.add_panel(DashboardPanel(
            panel_id="first",
            title="First",
            panel_type=PanelType.LOGS,
            position=1,
        ))
        dashboard.add_panel(DashboardPanel(
            panel_id="second",
            title="Second",
            panel_type=PanelType.LOGS,
            position=2,
        ))

        panels = dashboard.list_panels()

        assert panels[0].panel_id == "first"
        assert panels[1].panel_id == "second"
        assert panels[2].panel_id == "third"

    def test_register_health_check(self):
        """Test registering custom health check."""
        dashboard = Dashboard()

        def custom_check() -> StatusCheck:
            return StatusCheck(
                name="custom",
                status=HealthStatus.HEALTHY,
                message="Custom check passed",
            )

        dashboard.register_health_check("custom", custom_check)

        status = dashboard.get_health_status()
        assert "custom" in status
        assert status["custom"].status == HealthStatus.HEALTHY

    def test_register_data_source(self):
        """Test registering custom data source."""
        dashboard = Dashboard()

        def custom_source():
            return {"value": 42}

        dashboard.register_data_source("custom", custom_source)
        panel = DashboardPanel(
            panel_id="custom-panel",
            title="Custom",
            panel_type=PanelType.CUSTOM,
            data_source="custom",
        )
        dashboard.add_panel(panel)

        data = dashboard.get_panel_data("custom-panel")

        assert data["data"]["value"] == 42

    def test_get_overall_health_healthy(self):
        """Test overall health when all healthy."""
        dashboard = Dashboard()

        # Clear default checks and add only healthy ones
        dashboard._health_checks.clear()
        dashboard.register_health_check(
            "test1",
            lambda: StatusCheck("test1", HealthStatus.HEALTHY, "OK"),
        )
        dashboard.register_health_check(
            "test2",
            lambda: StatusCheck("test2", HealthStatus.HEALTHY, "OK"),
        )

        assert dashboard.get_overall_health() == HealthStatus.HEALTHY

    def test_get_overall_health_degraded(self):
        """Test overall health with degraded check."""
        dashboard = Dashboard()
        dashboard._health_checks.clear()
        dashboard.register_health_check(
            "healthy",
            lambda: StatusCheck("healthy", HealthStatus.HEALTHY, "OK"),
        )
        dashboard.register_health_check(
            "degraded",
            lambda: StatusCheck("degraded", HealthStatus.DEGRADED, "Warning"),
        )

        assert dashboard.get_overall_health() == HealthStatus.DEGRADED

    def test_get_overall_health_unhealthy(self):
        """Test overall health with unhealthy check."""
        dashboard = Dashboard()
        dashboard._health_checks.clear()
        dashboard.register_health_check(
            "healthy",
            lambda: StatusCheck("healthy", HealthStatus.HEALTHY, "OK"),
        )
        dashboard.register_health_check(
            "unhealthy",
            lambda: StatusCheck("unhealthy", HealthStatus.UNHEALTHY, "Error"),
        )

        assert dashboard.get_overall_health() == HealthStatus.UNHEALTHY

    def test_get_overall_health_empty(self):
        """Test overall health with no checks."""
        dashboard = Dashboard()
        dashboard._health_checks.clear()

        assert dashboard.get_overall_health() == HealthStatus.UNKNOWN

    def test_get_panel_data_logs(self):
        """Test getting logs panel data."""
        configure_logging(console=False, memory=True)
        logger = get_logger("test")
        logger.info("Test message")

        dashboard = Dashboard()
        dashboard.add_panel(DashboardPanel(
            panel_id="logs",
            title="Logs",
            panel_type=PanelType.LOGS,
        ))

        data = dashboard.get_panel_data("logs")

        assert "entries" in data
        # May or may not have entries depending on test order

    def test_get_panel_data_metrics(self):
        """Test getting metrics panel data."""
        reset_metrics()
        metrics = get_metrics()
        counter = metrics.counter("test_counter")
        counter.inc(5)

        dashboard = Dashboard()
        dashboard.add_panel(DashboardPanel(
            panel_id="metrics",
            title="Metrics",
            panel_type=PanelType.METRICS,
        ))

        data = dashboard.get_panel_data("metrics")

        assert "counters" in data or "timestamp" in data

    def test_get_panel_data_traces(self):
        """Test getting traces panel data."""
        configure_tracing(console=False, memory=True)
        tracer = get_tracer("test")
        with tracer.start_as_current_span("test-span"):
            pass

        dashboard = Dashboard()
        dashboard.add_panel(DashboardPanel(
            panel_id="traces",
            title="Traces",
            panel_type=PanelType.TRACES,
        ))

        data = dashboard.get_panel_data("traces")

        assert "spans" in data

    def test_get_panel_data_status(self):
        """Test getting status panel data."""
        dashboard = Dashboard()
        dashboard.add_panel(DashboardPanel(
            panel_id="status",
            title="Status",
            panel_type=PanelType.STATUS,
        ))

        data = dashboard.get_panel_data("status")

        assert "overall" in data
        assert "checks" in data

    def test_get_panel_data_nonexistent(self):
        """Test getting data for non-existent panel."""
        dashboard = Dashboard()

        data = dashboard.get_panel_data("nonexistent")

        assert "error" in data

    def test_refresh(self):
        """Test dashboard refresh."""
        dashboard = Dashboard()
        dashboard.add_panel(DashboardPanel(
            panel_id="test",
            title="Test",
            panel_type=PanelType.STATUS,
        ))

        result = dashboard.refresh()

        assert "timestamp" in result
        assert "config" in result
        assert "overall_health" in result
        assert "panels" in result
        assert "test" in result["panels"]

    def test_refresh_excludes_hidden_panels(self):
        """Test refresh excludes hidden panels."""
        dashboard = Dashboard()
        dashboard.add_panel(DashboardPanel(
            panel_id="visible",
            title="Visible",
            panel_type=PanelType.STATUS,
            visible=True,
        ))
        dashboard.add_panel(DashboardPanel(
            panel_id="hidden",
            title="Hidden",
            panel_type=PanelType.STATUS,
            visible=False,
        ))

        result = dashboard.refresh()

        assert "visible" in result["panels"]
        assert "hidden" not in result["panels"]

    def test_render_console(self):
        """Test console rendering."""
        dashboard = Dashboard()
        output = dashboard.render_console()

        assert "Pipeline Dashboard" in output
        assert "Overall Health" in output
        assert "Health Checks" in output

    def test_to_dict(self):
        """Test dashboard export."""
        dashboard = Dashboard()
        dashboard.add_panel(DashboardPanel(
            panel_id="test",
            title="Test",
            panel_type=PanelType.LOGS,
        ))

        result = dashboard.to_dict()

        assert "config" in result
        assert "panels" in result
        assert len(result["panels"]) == 1

    def test_from_dict(self):
        """Test dashboard import."""
        data = {
            "config": {"title": "Imported"},
            "panels": [
                {
                    "panel_id": "p1",
                    "title": "Panel 1",
                    "panel_type": "logs",
                }
            ],
        }

        dashboard = Dashboard.from_dict(data)

        assert dashboard.config.title == "Imported"
        assert len(dashboard.list_panels()) == 1
        assert dashboard.get_panel("p1") is not None

    def test_dashboard_roundtrip(self):
        """Test dashboard export/import roundtrip."""
        original = Dashboard(DashboardConfig(title="Roundtrip"))
        original.add_panel(DashboardPanel(
            panel_id="panel1",
            title="Panel 1",
            panel_type=PanelType.METRICS,
            position=1,
            width=2,
        ))

        data = original.to_dict()
        restored = Dashboard.from_dict(data)

        assert restored.config.title == "Roundtrip"
        assert len(restored.list_panels()) == 1
        assert restored.get_panel("panel1").width == 2


class TestCreateDashboard:
    """Tests for create_dashboard function."""

    def test_create_default_dashboard(self):
        """Test creating dashboard with defaults."""
        dashboard = create_dashboard()

        assert dashboard.config.title == "Pipeline Dashboard"
        panels = dashboard.list_panels()
        assert len(panels) == 4

        panel_ids = [p.panel_id for p in panels]
        assert "status" in panel_ids
        assert "logs" in panel_ids
        assert "metrics" in panel_ids
        assert "traces" in panel_ids

    def test_create_custom_title(self):
        """Test creating dashboard with custom title."""
        dashboard = create_dashboard(title="My Dashboard")

        assert dashboard.config.title == "My Dashboard"

    def test_create_without_default_panels(self):
        """Test creating dashboard without default panels."""
        dashboard = create_dashboard(include_default_panels=False)

        assert len(dashboard.list_panels()) == 0


class TestGlobalDashboard:
    """Tests for global dashboard functions."""

    def test_get_dashboard(self):
        """Test getting global dashboard."""
        reset_dashboard()

        dashboard = get_dashboard()

        assert dashboard is not None
        assert isinstance(dashboard, Dashboard)

    def test_get_dashboard_reuse(self):
        """Test dashboard reuse."""
        reset_dashboard()

        dashboard1 = get_dashboard()
        dashboard2 = get_dashboard()

        assert dashboard1 is dashboard2

    def test_reset_dashboard(self):
        """Test resetting global dashboard."""
        dashboard1 = get_dashboard()
        dashboard1.add_panel(DashboardPanel(
            panel_id="temp",
            title="Temp",
            panel_type=PanelType.LOGS,
        ))

        reset_dashboard()

        dashboard2 = get_dashboard()
        assert dashboard2.get_panel("temp") is None


class TestDefaultHealthChecks:
    """Tests for default health checks."""

    def test_logging_health_check(self):
        """Test logging health check."""
        configure_logging(console=False, memory=True)

        dashboard = Dashboard()
        status = dashboard.get_health_status()

        assert "logging" in status

    def test_metrics_health_check(self):
        """Test metrics health check."""
        dashboard = Dashboard()
        status = dashboard.get_health_status()

        assert "metrics" in status
        assert status["metrics"].status in [
            HealthStatus.HEALTHY,
            HealthStatus.UNHEALTHY,
        ]

    def test_tracing_health_check(self):
        """Test tracing health check."""
        configure_tracing(console=False, memory=True)

        dashboard = Dashboard()
        status = dashboard.get_health_status()

        assert "tracing" in status

    def test_health_check_error_handling(self):
        """Test health check handles errors gracefully."""
        dashboard = Dashboard()

        def failing_check() -> StatusCheck:
            raise RuntimeError("Check failed")

        dashboard.register_health_check("failing", failing_check)

        status = dashboard.get_health_status()

        assert "failing" in status
        assert status["failing"].status == HealthStatus.UNHEALTHY
        assert "failed" in status["failing"].message.lower()
