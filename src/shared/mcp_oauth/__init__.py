"""Generic OAuth 2.1 + PKCE service for MCP servers.

Extracted from src/bsl/mcp_server/auth/oauth2.py (Phase 12.3);
the donor module has since been retired (ADR-056, 2026-07-24).
Reusable across all MCP servers: pdf-vector-graph, etc.
"""

from .audit import AuditedOAuth2Service, AuditEmitter, OAuthAuditEvent
from .models import AccessTokenData, AuthCodeData, RefreshTokenData
from .service import OAuth2Service
from .store import OAuth2Store

__all__ = [
    "AuthCodeData",
    "AccessTokenData",
    "RefreshTokenData",
    "OAuth2Store",
    "OAuth2Service",
    "AuditedOAuth2Service",
    "AuditEmitter",
    "OAuthAuditEvent",
]
