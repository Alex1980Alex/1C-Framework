"""LangSmith Sandbox backend — Firecracker microVM via langsmith SDK.

Requires ``langsmith[sandbox]>=0.3.0`` and ``LANGSMITH_API_KEY``.

GA: May 2026 (https://www.langchain.com/blog/langsmith-sandboxes-generally-available).
Each sandbox is a hardware-virtualized microVM with kernel-level isolation —
stronger than container backends. Secrets are routed via Auth Proxy so they
never reach the runtime.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path

from .base import SandboxBackend, SandboxQuotaExceeded, SandboxResult

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATE = "python-sandbox"
DEFAULT_TIMEOUT = 30.0
DAILY_QUOTA = 50
OUTPUT_LIMIT = 100_000  # ~100 KB per stream, then truncate


class LangSmithBackend(SandboxBackend):
    """LangSmith Sandbox backend.

    Lazily creates the sandbox on first ``execute``; reuses it across calls
    until ``close`` to amortize cold-start (~500ms-2s).
    """

    def __init__(
        self,
        api_key: str | None = None,
        template_name: str = DEFAULT_TEMPLATE,
        blueprint: str | None = None,
        daily_quota: int = DAILY_QUOTA,
    ):
        try:
            from langsmith.sandbox import SandboxClient
        except ImportError as e:
            raise RuntimeError(
                "LangSmith sandbox extra not installed. "
                "Run: pip install 'langsmith[sandbox]>=0.3.0'"
            ) from e

        from langsmith.sandbox import SandboxClient  # local import for runtime

        resolved_key = api_key or os.getenv("LANGSMITH_API_KEY")
        if not resolved_key:
            raise RuntimeError("LANGSMITH_API_KEY required")

        self._client = SandboxClient(api_key=resolved_key)
        self._template = template_name
        self._blueprint = blueprint
        self._sandbox = None
        self._call_count = 0
        self._quota = daily_quota
        self._lock = asyncio.Lock()

    async def _ensure_sandbox(self) -> None:
        if self._sandbox is None:
            kwargs: dict = {"template_name": self._template}
            if self._blueprint:
                kwargs["blueprint"] = self._blueprint
            self._sandbox = await asyncio.to_thread(self._client.create_sandbox, **kwargs)  # type: ignore[arg-type]

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> SandboxResult:
        async with self._lock:
            self._call_count += 1
            if self._call_count > self._quota:
                raise SandboxQuotaExceeded(f"daily quota {self._quota} exceeded")

        await self._ensure_sandbox()

        try:
            from langsmith.sandbox import CommandTimeoutError, SandboxClientError
        except ImportError:
            CommandTimeoutError = TimeoutError  # type: ignore
            SandboxClientError = Exception  # type: ignore

        # For Python source, use stdin-style execution via `python -c <quoted-code>`
        # (handles multi-line via single-quotes wrapping in shell).
        cmd = self._build_cmd(code, language)

        t0 = time.monotonic()
        try:
            result = await asyncio.to_thread(self._sandbox.run, cmd, timeout=timeout)
        except CommandTimeoutError as e:  # type: ignore[misc]
            logger.warning("LangSmith timeout after %ss", timeout)
            return SandboxResult(
                stdout="",
                stderr=str(e),
                exit_code=124,
                duration_seconds=timeout,
                truncated=False,
            )
        except SandboxClientError:  # type: ignore[misc]
            logger.exception("LangSmith client error")
            raise

        duration = time.monotonic() - t0
        stdout_raw = getattr(result, "stdout", "") or ""
        stderr_raw = getattr(result, "stderr", "") or ""
        exit_code = getattr(result, "exit_code", 0)

        truncated = len(stdout_raw) > OUTPUT_LIMIT or len(stderr_raw) > OUTPUT_LIMIT
        return SandboxResult(
            stdout=stdout_raw[:OUTPUT_LIMIT],
            stderr=stderr_raw[:OUTPUT_LIMIT],
            exit_code=exit_code,
            duration_seconds=duration,
            truncated=truncated,
        )

    @staticmethod
    def _build_cmd(code: str, language: str) -> str:
        """Build shell command for LangSmith sandbox.

        Assumes POSIX shell (sh/bash) receiver — the default for `python-sandbox`
        template. Escape pattern `'` → `'\\''` is the textbook POSIX safe quote-
        break-out: close single-quote, escape one literal `'`, reopen. If LangSmith
        ever ships a cmd.exe-based template, this escape breaks silently — update
        before switching templates.
        """
        if language == "python":
            escaped = code.replace("'", "'\\''")
            return f"python -c '{escaped}'"
        if language == "bash":
            return code
        raise ValueError(f"Unsupported language: {language}")

    async def install(self, packages: list[str]) -> None:
        await self._ensure_sandbox()
        cmd = "pip install " + " ".join(packages)
        await asyncio.to_thread(self._sandbox.run, cmd, timeout=120)

    async def upload(self, local_path: Path, remote_path: str) -> None:
        await self._ensure_sandbox()
        await asyncio.to_thread(
            self._sandbox.upload_file,
            str(local_path),
            remote_path,
        )

    async def download(self, remote_path: str, local_path: Path) -> None:
        await self._ensure_sandbox()
        await asyncio.to_thread(
            self._sandbox.download_file,
            remote_path,
            str(local_path),
        )

    async def close(self) -> None:
        if self._sandbox is not None:
            try:
                await asyncio.to_thread(self._sandbox.close)
            except Exception:
                logger.debug("LangSmith sandbox close raised; ignoring", exc_info=True)
            finally:
                self._sandbox = None
