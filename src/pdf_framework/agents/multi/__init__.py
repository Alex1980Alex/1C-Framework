"""Multi-Agent Orchestration (Phase 39).

Specialized agents: Retrieval, Analysis, Writing, Verification.
Orchestrator coordinates handoffs between agents.
"""

from src.pdf_framework.agents.multi.orchestrator import create_multi_agent

__all__ = ["create_multi_agent"]
