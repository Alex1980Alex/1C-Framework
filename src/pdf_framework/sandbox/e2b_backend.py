"""E2B Code Interpreter backend — stateful Jupyter Kernel in Firecracker microVM.

Requires ``e2b-code-interpreter>=1.2.0`` and ``E2B_API_KEY``.

Key advantage over LangSmith: **stateful** — variables/imports persist across
``execute`` calls (Jupyter Kernel inside the sandbox). Pricing: ~$0.10/hour
vCPU; pause-resume preserves state up to 30 days at $0 compute.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path

from .base import SandboxBackend, SandboxQuotaExceeded, SandboxResult

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30.0
DAILY_QUOTA = 50
SANDBOX_TTL_SEC = 3600  # 1h Base tier; pass higher value for Pro 24h tier
OUTPUT_LIMIT = 100_000


class E2BBackend(SandboxBackend):
    """E2B Sandbox — vendor-neutral microVM with stateful Jupyter."""

    def __init__(
        self,
        api_key: str | None = None,
        template: str | None = None,
        sandbox_timeout: int = SANDBOX_TTL_SEC,
        daily_quota: int = DAILY_QUOTA,
    ):
        try:
            from e2b_code_interpreter import Sandbox
        except ImportError as e:
            raise RuntimeError(
                "E2B extra not installed. Run: pip install 'e2b-code-interpreter>=1.2.0'"
            ) from e

        from e2b_code_interpreter import Sandbox  # runtime import

        self._SandboxCls = Sandbox
        self._api_key = api_key or os.getenv("E2B_API_KEY")
        if not self._api_key:
            raise RuntimeError("E2B_API_KEY required")
        self._template = template
        self._sandbox_timeout = sandbox_timeout
        self._sandbox = None
        self._call_count = 0
        self._quota = daily_quota
        self._lock = asyncio.Lock()

    async def _ensure_sandbox(self) -> None:
        if self._sandbox is None:
            kwargs = {"api_key": self._api_key, "timeout": self._sandbox_timeout}
            if self._template:
                kwargs["template"] = self._template
            self._sandbox = await asyncio.to_thread(self._SandboxCls, **kwargs)

    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout: float = DEFAULT_TIMEOUT,
    ) -> SandboxResult:
        if language != "python":
            return SandboxResult(
                stdout="",
                stderr=f"E2B supports python only, got {language}",
                exit_code=1,
                duration_seconds=0.0,
                truncated=False,
            )

        async with self._lock:
            self._call_count += 1
            if self._call_count > self._quota:
                raise SandboxQuotaExceeded(f"daily quota {self._quota} exceeded")

        await self._ensure_sandbox()

        t0 = time.monotonic()
        try:
            execution = await asyncio.to_thread(
                self._sandbox.run_code,
                code,
                timeout=int(timeout),
            )
        except TimeoutError as e:
            return SandboxResult(
                stdout="",
                stderr=str(e),
                exit_code=124,
                duration_seconds=timeout,
                truncated=False,
            )

        duration = time.monotonic() - t0
        logs = getattr(execution, "logs", None)
        stdout_lines = list(getattr(logs, "stdout", [])) if logs else []
        stderr_lines = list(getattr(logs, "stderr", [])) if logs else []
        stdout = "\n".join(stdout_lines)
        stderr = "\n".join(stderr_lines)
        exit_code = 0

        err = getattr(execution, "error", None)
        if err:
            name = getattr(err, "name", "Error")
            value = getattr(err, "value", "")
            tb = getattr(err, "traceback", "")
            stderr = f"{name}: {value}\n{tb}"
            exit_code = 1

        truncated = len(stdout) > OUTPUT_LIMIT or len(stderr) > OUTPUT_LIMIT
        return SandboxResult(
            stdout=stdout[:OUTPUT_LIMIT],
            stderr=stderr[:OUTPUT_LIMIT],
            exit_code=exit_code,
            duration_seconds=duration,
            truncated=truncated,
        )

    async def install(self, packages: list[str]) -> None:
        await self._ensure_sandbox()
        code = (
            "import subprocess, sys\n"
            f"subprocess.check_call([sys.executable, '-m', 'pip', 'install', *{packages!r}])"
        )
        await asyncio.to_thread(self._sandbox.run_code, code, timeout=120)

    async def upload(self, local_path: Path, remote_path: str) -> None:
        await self._ensure_sandbox()
        content = Path(local_path).read_bytes()
        await asyncio.to_thread(self._sandbox.files.write, remote_path, content)

    async def download(self, remote_path: str, local_path: Path) -> None:
        await self._ensure_sandbox()
        content = await asyncio.to_thread(self._sandbox.files.read, remote_path)
        data = content if isinstance(content, bytes) else str(content).encode("utf-8")
        Path(local_path).write_bytes(data)

    async def close(self) -> None:
        if self._sandbox is not None:
            try:
                await asyncio.to_thread(self._sandbox.kill)
            except Exception:
                logger.debug("E2B sandbox kill raised; ignoring", exc_info=True)
            finally:
                self._sandbox = None
