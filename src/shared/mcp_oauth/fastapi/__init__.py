"""Reusable FastAPI integration for src.shared.mcp_oauth.

Provides a ready-to-mount router with:
- `GET  /.well-known/oauth-protected-resource` (RFC 9728 PRM)
- `GET  /.well-known/oauth-authorization-server` (RFC 8414 ASM)
- `GET  /authorize` (PKCE S256 authorization code grant)
- `POST /token` (code exchange + refresh rotation)

And a `require_oauth` dependency for protecting tool endpoints.

Wiring: `app.state.oauth_service` (OAuth2Service instance) + optional
`app.state.oauth_enabled` (bool, default True). Then mount router via
`app.include_router(build_oauth_router())` and protect endpoints with
`Depends(require_oauth)`.
"""

from .dependencies import require_oauth
from .routes import build_oauth_router

__all__ = ["build_oauth_router", "require_oauth"]
