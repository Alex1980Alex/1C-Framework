"""Audit event protocol for OAuth 2.1 service.

Optional hook-based instrumentation: pass an `audit_emit` callable to
`AuditedOAuth2Service` and every credential lifecycle event will be reported.

Designed to integrate with `memory_orchestrator.memory_audit_log` or any other
sink (file, JSON-lines, structured logger). The protocol stays sync to avoid
forcing callers to await the sink — emission failures are swallowed so audit
never breaks the auth flow.
"""

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Literal

from .service import OAuth2Service

EventType = Literal[
    "code_issued",
    "token_exchanged",
    "token_refreshed",
    "token_validated",
    "token_rejected",
]


@dataclass
class OAuthAuditEvent:
    """Single observable in the OAuth flow.

    `success=False` events carry `failure_reason` for forensic queries.
    """

    event_type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    client_id: str = ""
    success: bool = True
    failure_reason: str | None = None
    remote_addr: str | None = None
    rotation_counter: int | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d


AuditEmitter = Callable[[OAuthAuditEvent], None]


def _noop(_: OAuthAuditEvent) -> None:
    return None


class AuditedOAuth2Service(OAuth2Service):
    """OAuth2Service variant that emits OAuthAuditEvent on every flow step.

    Sink is a sync callable. Failures inside the sink are swallowed so audit
    never breaks the auth path.
    """

    def __init__(self, *args, audit_emit: AuditEmitter | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._emit = audit_emit or _noop

    def _safe_emit(self, event: OAuthAuditEvent) -> None:
        try:
            self._emit(event)
        except Exception:
            pass

    async def generate_authorization_code(
        self,
        client_id,
        redirect_uri,
        code_challenge,
        user_data=None,
    ):
        code = await super().generate_authorization_code(
            client_id,
            redirect_uri,
            code_challenge,
            user_data,
        )
        self._safe_emit(
            OAuthAuditEvent(
                event_type="code_issued",
                client_id=client_id,
                success=True,
            )
        )
        return code

    async def exchange_code_for_tokens(self, code, redirect_uri, code_verifier):
        result = await super().exchange_code_for_tokens(code, redirect_uri, code_verifier)
        if result:
            self._safe_emit(
                OAuthAuditEvent(
                    event_type="token_exchanged",
                    success=True,
                )
            )
        else:
            self._safe_emit(
                OAuthAuditEvent(
                    event_type="token_exchanged",
                    success=False,
                    failure_reason="invalid_code_or_pkce_or_redirect",
                )
            )
        return result

    async def refresh_tokens(self, refresh_token):
        result = await super().refresh_tokens(refresh_token)
        if result:
            self._safe_emit(
                OAuthAuditEvent(
                    event_type="token_refreshed",
                    success=True,
                )
            )
        else:
            self._safe_emit(
                OAuthAuditEvent(
                    event_type="token_refreshed",
                    success=False,
                    failure_reason="invalid_or_expired_refresh",
                )
            )
        return result

    async def validate_access_token(self, token):
        result = await super().validate_access_token(token)
        if result:
            self._safe_emit(
                OAuthAuditEvent(
                    event_type="token_validated",
                    client_id=result.get("client_id", ""),
                    success=True,
                )
            )
        else:
            self._safe_emit(
                OAuthAuditEvent(
                    event_type="token_rejected",
                    success=False,
                    failure_reason="invalid_or_expired_token",
                )
            )
        return result
