"""Generic OAuth 2.1 + PKCE service for MCP servers.

Extracted from src/bsl/mcp_server/auth/oauth2.py (Phase 12.3).
Reusable across all MCP servers: BSL, pdf-vector-graph, etc.
"""

from .models import AuthCodeData, AccessTokenData, RefreshTokenData
from .store import OAuth2Store
from .service import OAuth2Service

__all__ = [
    "AuthCodeData",
    "AccessTokenData",
    "RefreshTokenData",
    "OAuth2Store",
    "OAuth2Service",
]
