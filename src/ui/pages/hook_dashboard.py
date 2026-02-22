"""Hook & Skill Observability Dashboard - Streamlit UI (Phase 5).

Real-time web dashboard for monitoring hook invocations, skill activations,
and system health.

Features:
- Real-time metrics (auto-refresh)
- Hook invocation timeline
- Skill activation rate tracking
- Per-hook latency charts
- Error log viewer
- Session history

Usage:
    streamlit run src/ui/pages/hook_dashboard.py

Reference: GAP_P5_HOOK_OBSERVABILITY.md Phase 5
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Add project root to path for imports
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

try:
    from pdf_framework.observability.hook_metrics_db import HookMetricsDB
except ImportError:
    # Fallback for development
    HookMetricsDB = None

# --- Page config ---

st.set_page_config(
    page_title="Hook Observability Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🔗 Hook & Skill Observability Dashboard")
st.caption("Real-time monitoring of Claude Code hooks and skill activations")

# --- Sidebar ---

st.sidebar.header("⚙️ Settings")

# Auto-refresh
auto_refresh = st.sidebar.checkbox("Auto-refresh", value=False)
refresh_interval = st.sidebar.slider(
    "Refresh interval (seconds)",
    min_value=5,
    max_value=300,
    value=30,
    disabled=not auto_refresh,
)

# Time period
time_period = st.sidebar.selectbox(
    "Time period",
    options=["1h", "6h", "24h", "7d", "30d"],
    index=2,
)

# Convert time period to hours
PERIOD_TO_HOURS = {"1h": 1, "6h": 6, "24h": 24, "7d": 168, "30d": 720}
hours = PERIOD_TO_HOURS[time_period]

# Manual refresh
if st.sidebar.button("🔄 Refresh Now"):
    st.rerun()

st.sidebar.markdown("---")

# --- Database initialization ---

@st.cache_resource
def get_db():
    """Initialize database connection (cached)."""
    if HookMetricsDB is None:
        return None
    return HookMetricsDB()


db = get_db()

if db is None:
    st.error("❌ HookMetricsDB not available. Please ensure the module is installed.")
    st.stop()

# --- Data ingestion ---

with st.spinner("📥 Ingesting latest log data..."):
    ingest_counts = db.ingest_from_logs()

if sum(ingest_counts.values()) > 0:
    st.success(
        f"✅ Ingested {ingest_counts['invocations']} invocations, "
        f"{ingest_counts['recommendations']} recommendations, "
        f"{ingest_counts['activations']} activations"
    )

# --- Metrics Overview ---

st.header("📈 Overview Metrics")

# Get metrics
hook_metrics = db.get_hook_metrics(hours=hours)
skill_metrics = db.get_skill_metrics(hours=hours)
recent = db.get_recent_invocations(limit=1000)

# Calculate summary stats
total_invocations = sum(m["count"] for m in hook_metrics)
total_errors = sum(m["errors"] for m in hook_metrics)
total_blocks = sum(m["blocks"] for m in hook_metrics)

# Calculate p95 latency
all_latencies = []
for r in recent:
    all_latencies.append(r.get("elapsed_ms", 0))
all_latencies.sort()
p95_latency = all_latencies[int(len(all_latencies) * 0.95)] if all_latencies else 0

# Display metric cards
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        label="Total Invocations",
        value=f"{total_invocations:,}",
        delta=None,
    )

with col2:
    st.metric(
        label="Activation Rate",
        value=f"{skill_metrics['activation_rate']:.1f}%",
        delta=f"{skill_metrics['total_activated']} / {skill_metrics['total_recommended']}",
    )

with col3:
    st.metric(
        label="p95 Latency",
        value=f"{p95_latency}ms",
        delta=None,
    )

with col4:
    st.metric(
        label="Errors",
        value=f"{total_errors}",
        delta=None,
    )

with col5:
    st.metric(
        label="Blocks",
        value=f"{total_blocks}",
        delta=None,
    )

# --- Tabs ---

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Hook Invocations",
    "🎯 Skill Activations",
    "⏱️ Latency Analysis",
    "📋 Error Log",
    "👤 Sessions",
])

# --- Tab 1: Hook Invocations ---

with tab1:
    st.subheader("Hook Invocation Metrics")

    if hook_metrics:
        # Create DataFrame
        df = pd.DataFrame(hook_metrics)

        # Display table
        st.dataframe(
            df,
            column_config={
                "hook": st.column_config.TextColumn("Hook", width="medium"),
                "count": st.column_config.NumberColumn("Count", width="small"),
                "avg_ms": st.column_config.NumberColumn("Avg (ms)", width="small", format="%.1f"),
                "max_ms": st.column_config.NumberColumn("Max (ms)", width="small"),
                "blocks": st.column_config.NumberColumn("Blocks", width="small"),
                "errors": st.column_config.NumberColumn("Errors", width="small"),
            },
            hide_index=True,
            use_container_width=True,
        )

        # Chart
        fig = px.bar(
            df,
            x="hook",
            y="count",
            title="Hook Invocation Count",
            labels={"count": "Invocations", "hook": "Hook"},
            color="count",
            color_continuous_scale="Blues",
        )
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

        # Outcome distribution
        outcome_counts = df[["count", "blocks", "errors"]].sum()
        fig_pie = go.Figure(data=[
            go.Pie(
                labels=["Allow", "Block", "Error"],
                values=[
                    outcome_counts["count"] - outcome_counts["blocks"] - outcome_counts["errors"],
                    outcome_counts["blocks"],
                    outcome_counts["errors"],
                ],
                hole=0.4,
            )
        ])
        fig_pie.update_layout(title="Outcome Distribution")
        col_a, col_b = st.columns(2)
        with col_a:
            st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("No hook invocations found for the selected time period.")

# --- Tab 2: Skill Activations ---

with tab2:
    st.subheader("Skill Activation Metrics")

    # Activation gauge
    activation_rate = skill_metrics["activation_rate"]
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=activation_rate,
        title={"text": "Activation Rate (%)"},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": "darkblue"},
            "steps": [
                {"range": [0, 50], "color": "lightgray"},
                {"range": [50, 80], "color": "gray"},
            ],
            "threshold": {
                "line": {"color": "red", "width": 4},
                "thickness": 0.75,
                "value": 80,
            },
        },
    ))
    st.plotly_chart(fig_gauge, use_container_width=True)

    # Per-skill breakdown
    per_skill = skill_metrics.get("per_skill", {})
    if per_skill:
        skill_df = pd.DataFrame([
            {
                "skill": skill,
                "recommended": metrics["recommended"],
                "activated": metrics["activated"],
                "rate": metrics["rate"],
            }
            for skill, metrics in per_skill.items()
        ]).sort_values("recommended", ascending=False)

        st.dataframe(
            skill_df,
            column_config={
                "skill": st.column_config.TextColumn("Skill", width="large"),
                "recommended": st.column_config.NumberColumn("Recommended", width="small"),
                "activated": st.column_config.NumberColumn("Activated", width="small"),
                "rate": st.column_config.ProgressColumn(
                    "Rate (%)",
                    width="medium",
                    format="%.1f%%",
                    min_value=0,
                    max_value=100,
                ),
            },
            hide_index=True,
            use_container_width=True,
        )

        # Chart
        fig_skills = px.bar(
            skill_df.head(15),
            x="skill",
            y=["recommended", "activated"],
            title="Top Skills: Recommended vs Activated",
            barmode="group",
            labels={"value": "Count", "skill": "Skill"},
        )
        fig_skills.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_skills, use_container_width=True)
    else:
        st.info("No skill activations found for the selected time period.")

# --- Tab 3: Latency Analysis ---

with tab3:
    st.subheader("Latency Analysis")

    if hook_metrics:
        # Latency by hook
        df = pd.DataFrame(hook_metrics)
        df = df[df["avg_ms"] > 0].sort_values("avg_ms", ascending=False)

        fig_latency = px.bar(
            df,
            x="hook",
            y="avg_ms",
            error_y=df["max_ms"] - df["avg_ms"],
            title="Average Latency by Hook (with max)",
            labels={"avg_ms": "Latency (ms)", "hook": "Hook"},
            color="avg_ms",
            color_continuous_scale="Reds",
        )
        fig_latency.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_latency, use_container_width=True)

        # Latency distribution
        if all_latencies:
            fig_hist = px.histogram(
                x=all_latencies,
                nbins=50,
                title="Latency Distribution",
                labels={"x": "Latency (ms)"},
            )
            fig_hist.add_vline(
                x=p95_latency,
                line_dash="dash",
                line_color="red",
                annotation_text=f"p95: {p95_latency}ms",
            )
            st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.info("No latency data available.")

# --- Tab 4: Error Log ---

with tab4:
    st.subheader("Error Log")

    errors = db.get_error_log(limit=100)

    if errors:
        for err in errors:
            with st.expander(
                f"❌ {err['hook']} - {err['timestamp'][:19]}"
            ):
                st.code(err["error"], language="text")
                st.caption(f"Event: {err['event']} | Tool: {err.get('tool', 'N/A')}")
    else:
        st.success("🎉 No errors recorded for the selected time period!")

# --- Tab 5: Sessions ---

with tab5:
    st.subheader("Recent Sessions")

    sessions = db.get_session_history(limit=50)

    if sessions:
        session_df = pd.DataFrame(sessions)

        st.dataframe(
            session_df,
            column_config={
                "session": st.column_config.TextColumn("Session", width="medium"),
                "invocations": st.column_config.NumberColumn("Invocations", width="small"),
                "hooks": st.column_config.NumberColumn("Unique Hooks", width="small"),
                "duration_min": st.column_config.NumberColumn("Duration (min)", width="small", format="%.1f"),
            },
            hide_index=True,
            use_container_width=True,
        )

        # Session scatter
        fig_sessions = px.scatter(
            session_df,
            x="duration_min",
            y="invocations",
            size="hooks",
            hover_name="session",
            title="Session Analysis",
            labels={"duration_min": "Duration (min)", "invocations": "Invocations", "hooks": "Unique Hooks"},
        )
        st.plotly_chart(fig_sessions, use_container_width=True)
    else:
        st.info("No session data available.")

# --- Footer ---

st.markdown("---")
st.caption(
    f"📊 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
    f"Data source: {PROJECT_ROOT / 'data'}"
)

# --- Auto-refresh ---

if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()
