"""Authentication routes (Phase 12.3).

Author: Claude Code
Version: 1.3.0 - Phase 12.3: JWT Authentication
"""

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, status

from src.api.auth.jwt_handler import get_jwt_handler
from src.pdf_framework.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/token")
async def create_token(
    api_key: str,
    tenant_id: str | None = None,
    role: Literal["viewer", "editor", "admin"] = "viewer",
):
    """
    Create a JWT token.

    For development, accepts any API key.
    In production, validate against stored API keys.
    """
    settings = get_settings()

    # In production, validate api_key against database
    # For now, accept any non-empty key in dev mode
    if not settings.auth.enabled and not api_key:
        # Allow empty in dev if auth disabled
        pass
    elif not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
        )

    # Use provided tenant_id or default
    final_tenant_id = tenant_id or settings.auth.default_tenant

    # Create token
    jwt_handler = get_jwt_handler(
        secret=settings.auth.jwt_secret,
        algorithm=settings.auth.jwt_algorithm,
        expire_hours=settings.auth.token_expire_hours,
    )

    token = jwt_handler.create_token(final_tenant_id, role)

    logger.info(f"[AUTH] Token created for tenant '{final_tenant_id}', role '{role}'")

    return {
        "token": token,
        "token_type": "Bearer",
        "tenant_id": final_tenant_id,
        "role": role,
        "expires_in_hours": settings.auth.token_expire_hours,
    }


@router.post("/validate")
async def validate_token(
    token: str,
):
    """Validate a JWT token and return its payload."""
    settings = get_settings()

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
        )

    return {
        "valid": True,
        "tenant_id": payload.tenant_id,
        "role": payload.role,
        "issued_at": payload.iat.isoformat(),
        "expires_at": payload.exp.isoformat(),
    }
