"""
Verification module for Development Pipeline.

Provides verification mechanisms for all agents.
"""

from verification.base_verifier import (
    BaseVerifier,
    CheckResult,
    CheckType,
    RequirementCheck,
    VerificationResult,
)
from verification.pm_spec_verifier import PMSpecVerifier
from verification.architect_verifier import ArchitectVerifier
from verification.implementer_verifier import ImplementerVerifier
from verification.revision_handler import (
    RevisionAction,
    RevisionHandler,
    RevisionHistory,
    RevisionRequest,
)
from verification.revision_limiter import (
    EscalationEvent,
    EscalationLevel,
    LimitConfig,
    RevisionLimiter,
    create_default_limiter,
    create_lenient_limiter,
    create_strict_limiter,
)

__all__ = [
    # Base verifier
    "BaseVerifier",
    "CheckResult",
    "CheckType",
    "RequirementCheck",
    "VerificationResult",
    # Agent verifiers
    "PMSpecVerifier",
    "ArchitectVerifier",
    "ImplementerVerifier",
    # Revision handling
    "RevisionAction",
    "RevisionHandler",
    "RevisionHistory",
    "RevisionRequest",
    # Revision limiting
    "EscalationEvent",
    "EscalationLevel",
    "LimitConfig",
    "RevisionLimiter",
    "create_default_limiter",
    "create_lenient_limiter",
    "create_strict_limiter",
]
