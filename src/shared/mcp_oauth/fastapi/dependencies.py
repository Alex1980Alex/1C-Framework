"""FastAPI dependencies for OAuth 2.1 + PKCE."""

from fastapi import HTTPException, Request


async def require_oauth(request: Request) -> dict:
    """Validate Bearer token from Authorization header.

    Reads `request.app.state.oauth_service` (must be set to an `OAuth2Service`
    instance during app startup). Returns `user_data` dict on success, raises
    401 on missing/invalid/expired token.

    Skips validation entirely if `request.app.state.oauth_enabled` is False —
    enables feature-flag rollout without touching endpoint signatures.
    """
    oauth_enabled = getattr(request.app.state, "oauth_enabled", True)
    if not oauth_enabled:
        return {}

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing Bearer token",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        )

    service = getattr(request.app.state, "oauth_service", None)
    if service is None:
        raise HTTPException(
            status_code=500,
            detail="OAuth not configured (app.state.oauth_service missing)",
        )

    token = auth[7:]
    user_data = await service.validate_access_token(token)
    if not user_data:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        )
    return user_data
