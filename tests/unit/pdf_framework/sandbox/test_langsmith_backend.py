"""Unit tests for LangSmithBackend (mock-based)."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pdf_framework.sandbox.base import SandboxQuotaExceeded


@pytest.fixture
def fake_langsmith_module(monkeypatch):
    """Inject a fake `langsmith.sandbox` module so import succeeds without the real package."""
    mod = MagicMock()
    mod.SandboxClient = MagicMock()
    mod.CommandTimeoutError = TimeoutError
    mod.SandboxClientError = Exception
    monkeypatch.setitem(sys.modules, "langsmith", MagicMock(sandbox=mod))
    monkeypatch.setitem(sys.modules, "langsmith.sandbox", mod)
    return mod


@pytest.fixture
def backend(fake_langsmith_module, monkeypatch):
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")
    from src.pdf_framework.sandbox.langsmith_backend import LangSmithBackend
    b = LangSmithBackend()
    # Stub the sandbox object
    b._sandbox = MagicMock()
    b._sandbox.run = MagicMock(return_value=SimpleNamespace(
        stdout="hello\n", stderr="", exit_code=0,
    ))
    return b


class TestInit:
    def test_init_without_api_key_raises(self, fake_langsmith_module, monkeypatch):
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
        from src.pdf_framework.sandbox.langsmith_backend import LangSmithBackend
        with pytest.raises(RuntimeError, match="LANGSMITH_API_KEY"):
            LangSmithBackend()

    def test_init_without_extra_raises(self, monkeypatch):
        # Remove the langsmith module → import should fail
        monkeypatch.delitem(sys.modules, "langsmith.sandbox", raising=False)
        monkeypatch.delitem(sys.modules, "langsmith", raising=False)
        # Also block fresh imports
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *a, **kw):
            if name.startswith("langsmith"):
                raise ImportError(name)
            return real_import(name, *a, **kw)

        with patch("builtins.__import__", side_effect=fake_import):
            # Force re-import of the backend module
            sys.modules.pop("src.pdf_framework.sandbox.langsmith_backend", None)
            with pytest.raises(RuntimeError, match="LangSmith sandbox extra"):
                from src.pdf_framework.sandbox.langsmith_backend import LangSmithBackend
                LangSmithBackend(api_key="x")


class TestExecute:
    @pytest.mark.asyncio
    async def test_execute_returns_result(self, backend):
        result = await backend.execute("print('hello')")
        assert "hello" in result.stdout
        assert result.exit_code == 0
        assert result.duration_seconds >= 0.0

    @pytest.mark.asyncio
    async def test_execute_python_uses_python_c(self, backend):
        await backend.execute("print(42)", language="python")
        cmd_passed = backend._sandbox.run.call_args[0][0]
        assert cmd_passed.startswith("python -c '")
        assert "print(42)" in cmd_passed

    @pytest.mark.asyncio
    async def test_execute_quota_exceeded_after_50(self, backend):
        backend._quota = 2
        await backend.execute("a")
        await backend.execute("b")
        with pytest.raises(SandboxQuotaExceeded):
            await backend.execute("c")

    @pytest.mark.asyncio
    async def test_execute_unsupported_language(self, backend):
        with pytest.raises(ValueError, match="Unsupported language"):
            await backend.execute("print 'x'", language="ruby")

    @pytest.mark.asyncio
    async def test_execute_timeout_returns_124(self, backend, fake_langsmith_module):
        backend._sandbox.run = MagicMock(side_effect=TimeoutError("too slow"))
        result = await backend.execute("while True: pass", timeout=1.0)
        assert result.exit_code == 124
        assert "too slow" in result.stderr

    @pytest.mark.asyncio
    async def test_execute_truncation_100kb(self, backend):
        huge = "x" * 150_000
        backend._sandbox.run = MagicMock(return_value=SimpleNamespace(
            stdout=huge, stderr="", exit_code=0,
        ))
        result = await backend.execute("print('x' * 150000)")
        assert result.truncated is True
        assert len(result.stdout) == 100_000


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_install_runs_pip(self, backend):
        await backend.install(["httpx", "pydantic"])
        cmd = backend._sandbox.run.call_args[0][0]
        assert cmd == "pip install httpx pydantic"

    @pytest.mark.asyncio
    async def test_upload_download_delegate(self, backend, tmp_path):
        local = tmp_path / "file.txt"
        local.write_text("data")
        await backend.upload(local, "/sandbox/file.txt")
        assert backend._sandbox.upload_file.called

        await backend.download("/sandbox/file.txt", local)
        assert backend._sandbox.download_file.called

    @pytest.mark.asyncio
    async def test_close_idempotent(self, backend):
        await backend.close()
        await backend.close()  # second call must not raise
        assert backend._sandbox is None
