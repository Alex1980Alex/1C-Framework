"""FastAPI authentication dependencies for API routes (F3.2.4).

Author: Claude Code
Version: 1.0.0 - F3.2.4: User attribution for tracing
"""

import logging
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.api.auth.jwt_handler import TokenPayload, get_jwt_handler
from src.pdf_framework.config import get_settings

logger = logging.getLogger(__name__)

# Security scheme for Bearer tokens (auto_error=False for optional auth)
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> str | None:
    """
    Extract user_id from JWT token for tracing/observability.

    For development (AUTH__ENABLED=false), returns None (anonymous).
    For authenticated requests, returns tenant_id as user identifier.

    Args:
        credentials: Bearer token from Authorization header (optional)

    Returns:
        user_id (tenant_id) or None for anonymous users

    Raises:
        HTTPException: If auth is enabled and token is invalid
    """
    settings = get_settings()

    # Auth disabled - return None (anonymous)
    if not settings.auth.enabled:
        return None

    # No credentials provided - return None (anonymous)
    if credentials is None:
        return None

    # Verify token and extract tenant_id as user identifier
    token = credentials.credentials
    jwt_handler = get_jwt_handler(
        secret=settings.auth.jwt_secret,
        algorithm=settings.auth.jwt_algorithm,
        expire_hours=settings.auth.token_expire_hours,
    )

    payload = jwt_handler.verify_token(token)
    if payload is None:
        # Invalid token - log warning but don't raise (allow anonymous)
        logger.debug("[AUTH] Invalid token, treating as anonymous")
        return None

    logger.debug(f"[AUTH] User '{payload.tenant_id}' authenticated for tracing")
    return payload.tenant_id


# Type alias for dependency injection
UserId = Annotated[str | None, Depends(get_current_user)]
