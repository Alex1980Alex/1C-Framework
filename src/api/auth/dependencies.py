"""FastAPI authentication dependencies (Phase 12.3).

Author: Claude Code
Version: 1.3.0 - Phase 12.3: JWT Authentication
"""

import logging
from typing import Annotated, Literal

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.api.auth.jwt_handler import TokenPayload, get_jwt_handler
from src.pdf_framework.config import get_settings

logger = logging.getLogger(__name__)

# Security scheme for Bearer tokens
security = HTTPBearer(auto_error=False)


async def get_current_tenant(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> str:
    """
    Extract tenant_id from JWT token.

    For development (AUTH__ENABLED=false), returns default tenant.

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        tenant_id

    Raises:
        HTTPException: If auth is enabled and token is invalid
    """
    settings = get_settings()

    # Auth disabled - use default tenant
    if not settings.auth.enabled:
        return settings.auth.default_tenant

    # Auth enabled - verify token
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    jwt_handler = get_jwt_handler(
        secret=settings.auth.jwt_secret,
        algorithm=settings.auth.jwt_algorithm,
        expire_hours=settings.auth.token_expire_hours,
    )

    payload = jwt_handler.verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    logger.debug(f"[AUTH] Tenant '{payload.tenant_id}' authenticated")
    return payload.tenant_id


async def get_current_role(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> Literal["viewer", "editor", "admin"]:
    """
    Extract role from JWT token.

    For development (AUTH__ENABLED=false), returns admin role.

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        User role

    Raises:
        HTTPException: If auth is enabled and token is invalid
    """
    settings = get_settings()

    # Auth disabled - use admin role
    if not settings.auth.enabled:
        return "admin"

    # Auth enabled - verify token
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    jwt_handler = get_jwt_handler(
        secret=settings.auth.jwt_secret,
        algorithm=settings.auth.jwt_algorithm,
        expire_hours=settings.auth.token_expire_hours,
    )

    payload = jwt_handler.verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload.role


async def get_token_payload(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> TokenPayload:
    """
    Extract full token payload.

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        TokenPayload with tenant_id and role

    Raises:
        HTTPException: If auth is enabled and token is invalid
    """
    settings = get_settings()

    # Auth disabled - return default payload
    if not settings.auth.enabled:
        from datetime import datetime, timezone

        return TokenPayload(
            tenant_id=settings.auth.default_tenant,
            role="admin",
            exp=datetime.now(timezone.utc).replace(year=2099),
            iat=datetime.now(timezone.utc),
        )

    # Auth enabled - verify token
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    jwt_handler = get_jwt_handler(
        secret=settings.auth.jwt_secret,
        algorithm=settings.auth.jwt_algorithm,
        expire_hours=settings.auth.token_expire_hours,
    )

    payload = jwt_handler.verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


# Type aliases for dependency injection
TenantId = Annotated[str, Depends(get_current_tenant)]
UserRole = Annotated[Literal["viewer", "editor", "admin"], Depends(get_current_role)]
TokenPayloadDep = Annotated[TokenPayload, Depends(get_token_payload)]
