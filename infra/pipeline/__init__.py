"""
Development Pipeline - Multi-Agent System for 1C Development.

This module provides orchestration for 3-agent pipeline:
- PM-SPEC: Product Manager + Initializer + Verifier
- ARCHITECT: Software Architect + Code Reviewer
- IMPLEMENTER: Senior Developer + QA + Docs

Agents communicate through markdown artifacts stored in artifacts/ directory.
"""

__version__ = "0.1.0"
__author__ = "Claude Code"

from constants import (
    AgentRole,
    AgentMode,
    ArtifactType,
    PipelinePhase,
    VerificationStatus,
)

__all__ = [
    "AgentRole",
    "AgentMode",
    "ArtifactType",
    "PipelinePhase",
    "VerificationStatus",
]
