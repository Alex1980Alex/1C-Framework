"""JWT token handling for authentication (Phase 12.3).

Author: Claude Code
Version: 1.3.0 - Phase 12.3: JWT Authentication
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Literal

import jwt
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class TokenPayload(BaseModel):
    """JWT token payload."""

    tenant_id: str
    role: Literal["viewer", "editor", "admin"]
    exp: datetime
    iat: datetime


class JWTHandler:
    """
    Handles JWT token creation and verification.

    Tokens encode tenant_id and role for authorization.
    """

    def __init__(
        self,
        secret: str,
        algorithm: str = "HS256",
        expire_hours: int = 24,
    ):
        """
        Initialize JWT handler.

        Args:
            secret: Secret key for signing tokens
            algorithm: JWT algorithm (default: HS256)
            expire_hours: Token expiration time in hours
        """
        self._secret = secret
        self._algorithm = algorithm
        self._expire_hours = expire_hours

    def create_token(
        self,
        tenant_id: str,
        role: Literal["viewer", "editor", "admin"] = "viewer",
    ) -> str:
        """
        Create a JWT token.

        Args:
            tenant_id: Tenant identifier
            role: User role

        Returns:
            JWT token string
        """
        now = datetime.now(timezone.utc)
        exp = now + timedelta(hours=self._expire_hours)

        payload = {
            "tenant_id": tenant_id,
            "role": role,
            "exp": exp,
            "iat": now,
        }

        token = jwt.encode(payload, self._secret, algorithm=self._algorithm)
        logger.debug(f"[JWT] Created token for tenant '{tenant_id}', role '{role}'")

        return token

    def verify_token(self, token: str) -> TokenPayload | None:
        """
        Verify and decode a JWT token.

        Args:
            token: JWT token string

        Returns:
            TokenPayload if valid, None if invalid
        """
        try:
            # Decode token
            decoded = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
            )

            # Validate payload structure
            payload = TokenPayload(
                tenant_id=decoded["tenant_id"],
                role=decoded["role"],
                exp=datetime.fromtimestamp(decoded["exp"], tz=timezone.utc),
                iat=datetime.fromtimestamp(decoded["iat"], tz=timezone.utc),
            )

            # Check expiration (JWT library does this, but double-check)
            if payload.exp < datetime.now(timezone.utc):
                logger.warning("[JWT] Token expired")
                return None

            return payload

        except jwt.ExpiredSignatureError:
            logger.warning("[JWT] Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"[JWT] Invalid token: {e}")
            return None
        except ValidationError as e:
            logger.warning(f"[JWT] Invalid payload structure: {e}")
            return None
        except Exception as e:
            logger.error(f"[JWT] Token verification error: {e}")
            return None

    def extract_tenant_id(self, token: str) -> str | None:
        """
        Extract tenant_id from token (lightweight verification).

        Args:
            token: JWT token string

        Returns:
            tenant_id if valid, None otherwise
        """
        payload = self.verify_token(token)
        return payload.tenant_id if payload else None

    def get_default_token(self) -> str:
        """
        Get a default token for development/testing.

        Returns:
            Token for default tenant with admin role
        """
        return self.create_token("default", "admin")


# Global JWT handler instance
_jwt_handler: JWTHandler | None = None


def get_jwt_handler(**kwargs) -> JWTHandler:
    """Get or create global JWT handler instance."""
    global _jwt_handler
    if _jwt_handler is None:
        _jwt_handler = JWTHandler(**kwargs)
    return _jwt_handler
