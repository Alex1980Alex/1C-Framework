"""Unit tests for E2BBackend (mock-based)."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.pdf_framework.sandbox.base import SandboxQuotaExceeded


@pytest.fixture
def fake_e2b_module(monkeypatch):
    """Inject a fake `e2b_code_interpreter` module."""
    mod = MagicMock()
    mod.Sandbox = MagicMock()
    monkeypatch.setitem(sys.modules, "e2b_code_interpreter", mod)
    return mod


@pytest.fixture
def backend(fake_e2b_module, monkeypatch):
    monkeypatch.setenv("E2B_API_KEY", "test-key")
    from src.pdf_framework.sandbox.e2b_backend import E2BBackend
    b = E2BBackend()
    b._sandbox = MagicMock()
    b._sandbox.run_code = MagicMock(return_value=SimpleNamespace(
        logs=SimpleNamespace(stdout=["hello"], stderr=[]),
        error=None,
    ))
    return b


class TestInit:
    def test_init_without_api_key_raises(self, fake_e2b_module, monkeypatch):
        monkeypatch.delenv("E2B_API_KEY", raising=False)
        from src.pdf_framework.sandbox.e2b_backend import E2BBackend
        with pytest.raises(RuntimeError, match="E2B_API_KEY"):
            E2BBackend()

    def test_init_without_extra_raises(self, monkeypatch):
        monkeypatch.delitem(sys.modules, "e2b_code_interpreter", raising=False)
        import builtins
        real_import = builtins.__import__

        def fake_import(name, *a, **kw):
            if name.startswith("e2b_code_interpreter"):
                raise ImportError(name)
            return real_import(name, *a, **kw)

        with patch("builtins.__import__", side_effect=fake_import):
            sys.modules.pop("src.pdf_framework.sandbox.e2b_backend", None)
            with pytest.raises(RuntimeError, match="E2B extra"):
                from src.pdf_framework.sandbox.e2b_backend import E2BBackend
                E2BBackend(api_key="x")


class TestExecute:
    @pytest.mark.asyncio
    async def test_execute_returns_result(self, backend):
        result = await backend.execute("print('hello')")
        assert "hello" in result.stdout
        assert result.exit_code == 0

    @pytest.mark.asyncio
    async def test_execute_quota_exceeded(self, backend):
        backend._quota = 1
        await backend.execute("a")
        with pytest.raises(SandboxQuotaExceeded):
            await backend.execute("b")

    @pytest.mark.asyncio
    async def test_execute_non_python_language(self, backend):
        result = await backend.execute("echo hi", language="bash")
        assert result.exit_code == 1
        assert "python only" in result.stderr

    @pytest.mark.asyncio
    async def test_execute_timeout_returns_124(self, backend):
        backend._sandbox.run_code = MagicMock(side_effect=TimeoutError("slow"))
        result = await backend.execute("while True: pass", timeout=1.0)
        assert result.exit_code == 124

    @pytest.mark.asyncio
    async def test_execute_error_in_jupyter(self, backend):
        backend._sandbox.run_code = MagicMock(return_value=SimpleNamespace(
            logs=SimpleNamespace(stdout=[], stderr=[]),
            error=SimpleNamespace(name="NameError", value="x not defined", traceback="..."),
        ))
        result = await backend.execute("print(x)")
        assert result.exit_code == 1
        assert "NameError" in result.stderr
        assert "x not defined" in result.stderr

    @pytest.mark.asyncio
    async def test_stateful_jupyter_persistence(self, backend):
        """E2B-unique: variables persist across run_code calls (single sandbox)."""
        # First call sets x=42
        backend._sandbox.run_code = MagicMock(side_effect=[
            SimpleNamespace(logs=SimpleNamespace(stdout=[], stderr=[]), error=None),
            SimpleNamespace(logs=SimpleNamespace(stdout=["84"], stderr=[]), error=None),
        ])
        await backend.execute("x = 42")
        result = await backend.execute("print(x * 2)")
        assert "84" in result.stdout
        # Single sandbox reused — both calls share state
        assert backend._sandbox.run_code.call_count == 2

    @pytest.mark.asyncio
    async def test_truncation_100kb(self, backend):
        huge = ["x" * 100_000, "y" * 50_000]
        backend._sandbox.run_code = MagicMock(return_value=SimpleNamespace(
            logs=SimpleNamespace(stdout=huge, stderr=[]),
            error=None,
        ))
        result = await backend.execute("print(big)")
        assert result.truncated is True
        assert len(result.stdout) == 100_000


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_install_uses_subprocess(self, backend):
        await backend.install(["httpx"])
        code = backend._sandbox.run_code.call_args[0][0]
        assert "subprocess.check_call" in code
        assert "'httpx'" in code

    @pytest.mark.asyncio
    async def test_upload_download(self, backend, tmp_path):
        local = tmp_path / "test.txt"
        local.write_bytes(b"data")
        await backend.upload(local, "/sandbox/test.txt")
        assert backend._sandbox.files.write.called

        backend._sandbox.files.read = MagicMock(return_value=b"data")
        await backend.download("/sandbox/test.txt", local)
        assert local.read_bytes() == b"data"

    @pytest.mark.asyncio
    async def test_close_idempotent(self, backend):
        await backend.close()
        await backend.close()
        assert backend._sandbox is None


class TestSelector:
    def test_select_backend_dryrun_explicit(self, monkeypatch):
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
        monkeypatch.delenv("E2B_API_KEY", raising=False)
        from src.pdf_framework.sandbox import DryRunBackend, select_backend
        backend = select_backend("dryrun")
        assert isinstance(backend, DryRunBackend)

    def test_select_backend_auto_falls_back_to_dryrun(self, monkeypatch):
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
        monkeypatch.delenv("E2B_API_KEY", raising=False)
        from src.pdf_framework.sandbox import DryRunBackend, select_backend
        backend = select_backend("auto")
        assert isinstance(backend, DryRunBackend)
