"""Guardrails Middleware (Phase 53.4).

FastAPI middleware that chains PII detection, injection defense,
and content filtering on every request.
"""

import logging
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.pdf_framework.guardrails.pii_detector import PIIDetector
from src.pdf_framework.guardrails.injection_defense import InjectionDefense
from src.pdf_framework.guardrails.content_filter import ContentFilter

logger = logging.getLogger(__name__)


class GuardrailsMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware: PII → Injection → ContentFilter pipeline."""

    def __init__(
        self,
        app,
        pii_mode: str = "detect",
        injection_mode: str = "log",
        injection_threshold: float = 0.7,
        max_query_length: int = 10_000,
        max_file_size_bytes: int = 100 * 1024 * 1024,
    ):
        super().__init__(app)
        self.pii_detector = PIIDetector(mode=pii_mode)
        self.injection_defense = InjectionDefense(
            mode=injection_mode,
            threshold=injection_threshold,
        )
        self.content_filter = ContentFilter(
            max_query_length=max_query_length,
            max_file_size_bytes=max_file_size_bytes,
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through guardrails pipeline."""
        # Skip health checks and metrics
        if request.url.path in ("/health", "/health/ready", "/health/live", "/metrics"):
            return await call_next(request)

        # Only scan POST/PUT request bodies
        if request.method in ("POST", "PUT"):
            try:
                body = await request.body()
                if body:
                    text = body.decode("utf-8", errors="ignore")

                    # 1. Content length check
                    filter_result = self.content_filter.validate_input(text)
                    if not filter_result.allowed:
                        logger.warning(
                            "[GUARDRAILS] Content filter blocked: %s",
                            filter_result.reason,
                        )
                        return JSONResponse(
                            status_code=400,
                            content={
                                "error": "content_filter",
                                "detail": filter_result.reason,
                            },
                        )

                    # 2. PII Detection
                    pii_result = self.pii_detector.scan(text)
                    if pii_result.blocked:
                        pii_types = [m.pii_type.value for m in pii_result.matches]
                        logger.warning(
                            "[GUARDRAILS] PII blocked: %s", pii_types,
                        )
                        return JSONResponse(
                            status_code=400,
                            content={
                                "error": "pii_detected",
                                "detail": f"PII detected: {', '.join(pii_types)}",
                            },
                        )
                    if pii_result.has_pii:
                        logger.info(
                            "[GUARDRAILS] PII detected (%s mode): %d matches",
                            self.pii_detector.mode,
                            len(pii_result.matches),
                        )

                    # 3. Injection Defense
                    injection_result = self.injection_defense.scan(text)
                    if injection_result.action_taken == "blocked":
                        logger.warning(
                            "[GUARDRAILS] Injection blocked (score=%.2f): %s",
                            injection_result.score,
                            [m.pattern_name for m in injection_result.matches],
                        )
                        # Audit log
                        _audit_log(
                            event="injection_blocked",
                            score=injection_result.score,
                            patterns=[m.pattern_name for m in injection_result.matches],
                            ip=_get_client_ip(request),
                        )
                        return JSONResponse(
                            status_code=400,
                            content={
                                "error": "injection_detected",
                                "detail": "Request blocked: potential prompt injection",
                                "score": injection_result.score,
                            },
                        )

            except Exception as e:
                logger.error("[GUARDRAILS] Error processing request: %s", e)
                # Fail open — don't block on guardrail errors

        response = await call_next(request)
        return response


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _audit_log(event: str, **kwargs) -> None:
    """Write audit log entry for security events."""
    logger.info("[AUDIT] %s: %s", event, kwargs)
