"""
Constants and Enums for Development Pipeline.

Defines core types used across all pipeline components.
"""

from enum import Enum
from typing import List


class AgentRole(str, Enum):
    """Roles of agents in the pipeline."""

    PM_SPEC = "PM-SPEC"
    ARCHITECT = "ARCHITECT"
    IMPLEMENTER = "IMPLEMENTER"
    BSL_DEBUGGER = "BSL-DEBUGGER"
    ORCHESTRATOR = "ORCHESTRATOR"

    @property
    def description(self) -> str:
        """Get role description."""
        descriptions = {
            self.PM_SPEC: "Product Manager + Initializer + Verifier",
            self.ARCHITECT: "Software Architect + Code Reviewer",
            self.IMPLEMENTER: "Senior Developer + QA + Docs",
            self.BSL_DEBUGGER: "BSL Runtime Debugger Subagent",
            self.ORCHESTRATOR: "Pipeline Coordinator (Claude Code)",
        }
        return descriptions.get(self, "Unknown role")


class AgentMode(str, Enum):
    """Operating modes for agents."""

    # PM-SPEC modes
    INIT = "INIT"           # Initialize context
    SPEC = "SPEC"           # Create specification
    VERIFY = "VERIFY"       # Verify implementation

    # ARCHITECT modes
    DESIGN = "DESIGN"       # Create architecture design
    REVIEW = "REVIEW"       # Code review

    # IMPLEMENTER modes
    BUILD = "BUILD"         # Implement solution
    FIX = "FIX"             # Fix issues after verification

    # BSL-DEBUGGER modes
    DEBUG = "DEBUG"         # Debug BSL runtime errors


class ArtifactType(str, Enum):
    """Types of artifacts produced by agents."""

    CONTEXT = "context.md"
    SPEC = "spec.md"
    DESIGN = "design.md"
    RESULT = "result.md"
    VERIFICATION = "verification.md"
    QA_REPORT = "qa_report.md"
    REVIEW = "review.md"

    @property
    def producer(self) -> AgentRole:
        """Get the agent that produces this artifact."""
        producers = {
            self.CONTEXT: AgentRole.PM_SPEC,
            self.SPEC: AgentRole.PM_SPEC,
            self.DESIGN: AgentRole.ARCHITECT,
            self.RESULT: AgentRole.IMPLEMENTER,
            self.VERIFICATION: AgentRole.PM_SPEC,
            self.QA_REPORT: AgentRole.IMPLEMENTER,
            self.REVIEW: AgentRole.ARCHITECT,
        }
        return producers.get(self)


class PipelinePhase(str, Enum):
    """Phases of the pipeline execution."""

    INITIALIZATION = "initialization"
    SPECIFICATION = "specification"
    DESIGN = "design"
    IMPLEMENTATION = "implementation"
    REVIEW = "review"
    VERIFICATION = "verification"
    COMPLETED = "completed"
    FAILED = "failed"


class VerificationStatus(str, Enum):
    """Status of verification."""

    APPROVED = "APPROVED"
    REVISION_NEEDED = "REVISION_NEEDED"
    PENDING = "PENDING"
    FAILED = "FAILED"


class RequirementStatus(str, Enum):
    """Status of individual requirement."""

    PASSED = "✅"
    FAILED = "❌"
    WARNING = "⚠️"
    NOT_TESTED = "⬜"


# Pipeline configuration constants
MAX_REVISION_ATTEMPTS = 3
DEFAULT_TIMEOUT_SECONDS = 300
ARTIFACT_DIR = "artifacts"

# MCP tool categories by agent
PM_SPEC_READ_TOOLS = [
    "mcp__serena__list_dir",
    "mcp__serena__find_file",
    "mcp__serena__search_for_pattern",
    "mcp__serena__get_symbols_overview",
    "mcp__ast-grep-mcp__ast_grep",
    "mcp__1c-framework-docs__search_docs",
    "mcp__1c-dev-standards__search_docs",
    "mcp__unified-memory__search_memory",
    "mcp__code-reasoning__code-reasoning",
]

ARCHITECT_TOOLS = PM_SPEC_READ_TOOLS + [
    "mcp__serena__find_symbol",
    "mcp__serena__find_referencing_symbols",
    "mcp__bsl-semantic-search__search_bsl_code",
    "mcp__bsl-semantic-search__intelligent_search",
    "mcp__deep-code-reasoning__escalate_analysis",
    "mcp__llm-rotation__llm_complete",
]

IMPLEMENTER_TOOLS = ARCHITECT_TOOLS + [
    "mcp__serena__replace_symbol_body",
    "mcp__serena__insert_after_symbol",
    "mcp__serena__insert_before_symbol",
    "mcp__serena__write_memory",
    "mcp__auto-documenter__generate_documentation",
    "mcp__auto-documenter__generate_inline_docs",
    "mcp__unified-memory__save_memory",
    "mcp__memory__create_entities",
]
