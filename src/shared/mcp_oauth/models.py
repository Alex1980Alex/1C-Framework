"""OAuth 2.1 data models."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class AuthCodeData:
    """Authorization code data."""

    client_id: str
    redirect_uri: str
    code_challenge: str
    user_data: dict
    exp: datetime


@dataclass
class AccessTokenData:
    """Access token data."""

    client_id: str
    user_data: dict
    exp: datetime


@dataclass
class RefreshTokenData:
    """Refresh token data with rotation counter."""

    client_id: str
    user_data: dict
    exp: datetime
    rotation_counter: int = 0
