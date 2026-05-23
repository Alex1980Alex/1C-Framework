"""Unit tests for DryRunBackend — interface contract verification."""

from __future__ import annotations

import pytest

from src.pdf_framework.sandbox.base import SandboxQuotaExceeded, SandboxResult
from src.pdf_framework.sandbox.dry_run_backend import _QUOTA_LIMIT, DryRunBackend

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_backend() -> DryRunBackend:
    return DryRunBackend()


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


async def test_execute_returns_dry_run_result():
    backend = _make_backend()
    result = await backend.execute("print('hello')")

    assert isinstance(result, SandboxResult)
    assert result.stdout == "[dry-run] code not executed"
    assert result.stderr == ""
    assert result.exit_code == 0
    assert result.duration_seconds == 0.0
    assert result.truncated is False


async def test_execute_respects_language_and_timeout():
    backend = _make_backend()
    result = await backend.execute("echo hi", language="bash", timeout=5.0)

    assert result.exit_code == 0
    call = backend.calls[0]
    assert call["language"] == "bash"
    assert call["timeout"] == 5.0


# ---------------------------------------------------------------------------
# calls recording
# ---------------------------------------------------------------------------


async def test_execute_records_call():
    backend = _make_backend()
    code = "x = 1"
    await backend.execute(code)

    assert len(backend.calls) == 1
    call = backend.calls[0]
    assert call["method"] == "execute"
    assert call["code"] == code
    assert call["language"] == "python"


async def test_install_recorded_as_no_op():
    backend = _make_backend()
    await backend.install(["numpy", "pandas"])

    assert len(backend.calls) == 1
    call = backend.calls[0]
    assert call["method"] == "install"
    assert call["packages"] == ["numpy", "pandas"]


async def test_upload_recorded_as_no_op(tmp_path):
    backend = _make_backend()
    local = tmp_path / "file.txt"
    await backend.upload(local, "/sandbox/file.txt")

    assert len(backend.calls) == 1
    call = backend.calls[0]
    assert call["method"] == "upload"
    assert call["remote_path"] == "/sandbox/file.txt"
    assert call["local_path"] == str(local)


async def test_download_recorded_as_no_op(tmp_path):
    backend = _make_backend()
    local = tmp_path / "out.txt"
    await backend.download("/sandbox/result.txt", local)

    assert len(backend.calls) == 1
    call = backend.calls[0]
    assert call["method"] == "download"
    assert call["remote_path"] == "/sandbox/result.txt"
    assert call["local_path"] == str(local)


async def test_multiple_calls_all_recorded():
    backend = _make_backend()
    await backend.execute("pass")
    await backend.install(["requests"])
    await backend.execute("import requests")

    assert len(backend.calls) == 3
    assert backend.calls[0]["method"] == "execute"
    assert backend.calls[1]["method"] == "install"
    assert backend.calls[2]["method"] == "execute"


# ---------------------------------------------------------------------------
# Quota enforcement
# ---------------------------------------------------------------------------


async def test_quota_50_calls_succeed():
    backend = _make_backend()
    for i in range(_QUOTA_LIMIT):
        result = await backend.execute(f"x = {i}")
        assert result.exit_code == 0

    assert backend._execute_count == _QUOTA_LIMIT


async def test_quota_51st_call_raises():
    backend = _make_backend()
    for _ in range(_QUOTA_LIMIT):
        await backend.execute("pass")

    with pytest.raises(SandboxQuotaExceeded):
        await backend.execute("should fail")


async def test_quota_exceeded_message_contains_limit():
    backend = _make_backend()
    for _ in range(_QUOTA_LIMIT):
        await backend.execute("pass")

    with pytest.raises(SandboxQuotaExceeded, match=str(_QUOTA_LIMIT)):
        await backend.execute("fail")


async def test_quota_resets_on_new_instance():
    backend1 = _make_backend()
    for _ in range(_QUOTA_LIMIT):
        await backend1.execute("pass")

    # A fresh instance starts from zero
    backend2 = _make_backend()
    result = await backend2.execute("fresh")
    assert result.exit_code == 0
    assert backend2._execute_count == 1


# ---------------------------------------------------------------------------
# close() — idempotency
# ---------------------------------------------------------------------------


async def test_close_is_idempotent():
    backend = _make_backend()
    await backend.close()
    await backend.close()  # second call must not raise

    close_calls = [c for c in backend.calls if c["method"] == "close"]
    assert len(close_calls) == 2


async def test_close_recorded():
    backend = _make_backend()
    await backend.close()

    assert backend.calls[-1]["method"] == "close"
