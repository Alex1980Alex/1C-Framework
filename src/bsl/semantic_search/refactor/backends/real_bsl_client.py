"""Real BSL Language Server client over multilspy (sync facade, R1.3).

Wraps the async multilspy LanguageServer behind a sync interface compatible
with `MultilspyBackend`. Runs an asyncio event loop in a background thread;
all public methods block until the coroutine completes on that loop.

Lifecycle: start() -> open_workspace() -> rename()/references()/... -> stop().
Also supports the context-manager protocol.
"""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from collections.abc import AsyncIterator, Iterable
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from typing import Any

from multilspy.language_server import LanguageServer
from multilspy.lsp_protocol_handler.server import ProcessLaunchInfo
from multilspy.multilspy_config import Language, MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger

from ..types import BackendError

DEFAULT_JAR = Path(__file__).resolve().parents[5] / "tools" / "bsl-ls" / "bsl-language-server.jar"
DEFAULT_START_TIMEOUT = 60.0
DEFAULT_REQUEST_TIMEOUT = 30.0
DEFAULT_PRELOAD_THROTTLE_FPS = 10.0  # files per second after each batch
DEFAULT_PRELOAD_BATCH_SIZE = 50


def _build_init_params(root: Path) -> dict:
    """BSL-LS-specific initialize parameters (workspace folders + capabilities)."""
    return {
        "processId": os.getpid(),
        "rootPath": str(root),
        "rootUri": root.as_uri(),
        "workspaceFolders": [{"uri": root.as_uri(), "name": root.name}],
        "capabilities": {
            "workspace": {
                "workspaceFolders": True,
                "configuration": True,
                "didChangeWatchedFiles": {"dynamicRegistration": False},
            },
            "textDocument": {
                "synchronization": {"didSave": True},
                "documentSymbol": {"hierarchicalDocumentSymbolSupport": True},
                "references": {},
                "rename": {"prepareSupport": True},
                "hover": {},
                "definition": {},
            },
        },
        "initializationOptions": {},
        "trace": "off",
    }


class _BSLLanguageServer(LanguageServer):
    """multilspy adapter that spawns `java -jar bsl-language-server.jar --lsp`."""

    def __init__(
        self,
        config: MultilspyConfig,
        logger: MultilspyLogger,
        root: str,
        jar: Path,
    ) -> None:
        if not jar.exists():
            raise BackendError(f"BSL LS jar not found: {jar}", code="jar_missing")
        launch = ProcessLaunchInfo(cmd=["java", "-jar", str(jar), "--lsp"], cwd=root)
        super().__init__(config, logger, root, launch, language_id="bsl")

    @asynccontextmanager
    async def start_server(self) -> AsyncIterator[_BSLLanguageServer]:
        async def _noop(_params: Any) -> None:
            return None

        async def _log(msg: Any) -> None:
            self.logger.log(f"LSP: window/logMessage: {msg}", logging.INFO)

        self.server.on_request("client/registerCapability", _noop)
        self.server.on_notification("language/status", _noop)
        self.server.on_notification("window/logMessage", _log)
        self.server.on_notification("window/showMessage", _noop)
        self.server.on_notification("textDocument/publishDiagnostics", _noop)
        self.server.on_notification("$/progress", _noop)

        async with super().start_server():
            await self.server.start()
            await self.server.send.initialize(
                _build_init_params(Path(self.repository_root_path))  # type: ignore[arg-type]
            )
            self.server.notify.initialized({})
            try:
                yield self
            finally:
                try:
                    await self.server.shutdown()
                except Exception:
                    pass
                try:
                    await self.server.stop()
                except Exception:
                    pass


class _StderrLogger(MultilspyLogger):
    """Minimal MultilspyLogger writing to the logging module at DEBUG level."""

    def __init__(self, name: str = "real_bsl_client") -> None:
        self.logger = logging.getLogger(name)


class RealBSLClient:
    """Sync facade over multilspy BSL Language Server.

    Compatible with `MultilspyBackend` via `.rename(params)`. Also exposes
    `open_workspace()` (bulk didOpen with throttle) and `references()`.

    The client owns a background thread running an asyncio event loop. All
    LSP I/O happens on that loop; public methods `run_coroutine_threadsafe`
    onto it and block until the result is ready or a timeout fires.
    """

    def __init__(
        self,
        workspace_root: Path | str,
        jar_path: Path | str | None = None,
        start_timeout: float = DEFAULT_START_TIMEOUT,
        request_timeout: float = DEFAULT_REQUEST_TIMEOUT,
    ) -> None:
        self._root = Path(workspace_root).resolve()
        self._jar = Path(jar_path) if jar_path else DEFAULT_JAR
        self._start_timeout = start_timeout
        self._request_timeout = request_timeout

        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._server: _BSLLanguageServer | None = None
        self._server_stack: AsyncExitStack | None = None
        self._file_stack: AsyncExitStack | None = None
        self._ready = threading.Event()
        self._start_error: BaseException | None = None
        self._open_files: set[str] = set()

    # ----- lifecycle -----------------------------------------------------

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._ready.clear()
        self._start_error = None
        self._thread = threading.Thread(
            target=self._run_loop,
            name="bsl-lsp-loop",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(timeout=self._start_timeout):
            self._force_stop()
            raise BackendError(
                f"BSL LS start timed out after {self._start_timeout}s",
                code="start_timeout",
            )
        if self._start_error is not None:
            err = self._start_error
            self._force_stop()
            raise BackendError(f"BSL LS start failed: {err!r}", code="start_failed") from err

    def stop(self) -> None:
        if self._loop is None:
            return
        loop = self._loop
        # Close file stack first so didClose is sent before shutdown.
        try:
            if self._file_stack is not None:
                fut = asyncio.run_coroutine_threadsafe(self._close_file_stack(), loop)
                try:
                    fut.result(timeout=10)
                except Exception:
                    pass
        finally:
            try:
                if self._server_stack is not None:
                    fut = asyncio.run_coroutine_threadsafe(self._server_stack.aclose(), loop)
                    try:
                        fut.result(timeout=15)
                    except Exception:
                        pass
            finally:
                loop.call_soon_threadsafe(loop.stop)
                if self._thread is not None:
                    self._thread.join(timeout=10)
                self._thread = None
                self._loop = None
                self._server = None
                self._server_stack = None
                self._file_stack = None
                self._open_files.clear()
                self._ready.clear()

    def _force_stop(self) -> None:
        try:
            if self._loop is not None and self._loop.is_running():
                self._loop.call_soon_threadsafe(self._loop.stop)
        finally:
            if self._thread is not None:
                self._thread.join(timeout=5)
            self._thread = None
            self._loop = None
            self._server = None
            self._server_stack = None
            self._file_stack = None
            self._ready.clear()

    def __enter__(self) -> RealBSLClient:
        self.start()
        return self

    def __exit__(self, *_exc_info: Any) -> None:
        self.stop()

    # ----- sync public API ----------------------------------------------

    def open_workspace(
        self,
        files: Iterable[Path | str],
        throttle_fps: float = DEFAULT_PRELOAD_THROTTLE_FPS,
        batch_size: int = DEFAULT_PRELOAD_BATCH_SIZE,
    ) -> dict[str, Any]:
        """Bulk-didOpen all files, throttled. Returns timing metrics.

        Files stay open for the lifetime of the client (held by AsyncExitStack).
        """
        self._ensure_ready()
        paths = [Path(p).resolve() for p in files]
        coro = self._open_workspace_async(paths, throttle_fps, batch_size)
        return self._run_on_loop(coro, timeout=max(60.0, len(paths) / 5.0))

    def rename(self, params: dict) -> dict:
        """LSP textDocument/rename; returns raw dict (empty dict on None)."""
        self._ensure_ready()
        coro = self._server.server.send.rename(params)  # type: ignore[union-attr]
        result = self._run_on_loop(coro, timeout=self._request_timeout)
        return result or {}

    def prepare_rename(self, params: dict) -> Any:
        self._ensure_ready()
        coro = self._server.server.send.prepare_rename(params)  # type: ignore[union-attr]
        return self._run_on_loop(coro, timeout=self._request_timeout)

    def references(self, params: dict) -> list:
        self._ensure_ready()
        coro = self._server.server.send.references(params)  # type: ignore[union-attr]
        result = self._run_on_loop(coro, timeout=self._request_timeout)
        return result or []

    # ----- internals -----------------------------------------------------

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_startup())
            self._ready.set()
            loop.run_forever()
        except BaseException as exc:  # noqa: BLE001
            self._start_error = exc
            self._ready.set()
        finally:
            try:
                pending = asyncio.all_tasks(loop)
                for t in pending:
                    t.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            try:
                loop.close()
            except Exception:
                pass

    async def _async_startup(self) -> None:
        config = MultilspyConfig(
            code_language=Language.PYTHON,  # placeholder — BSL not in upstream enum
            trace_lsp_communication=False,
        )
        logger = _StderrLogger()
        server = _BSLLanguageServer(
            config=config,
            logger=logger,
            root=str(self._root),
            jar=self._jar,
        )
        server_stack = AsyncExitStack()
        await server_stack.enter_async_context(server.start_server())
        file_stack = AsyncExitStack()
        self._server = server
        self._server_stack = server_stack
        self._file_stack = file_stack

    async def _open_workspace_async(
        self,
        paths: list[Path],
        throttle_fps: float,
        batch_size: int,
    ) -> dict[str, Any]:
        assert self._server is not None
        assert self._file_stack is not None
        t0 = time.perf_counter()
        opened = 0
        skipped_outside = 0
        skipped_duplicate = 0
        skipped_missing = 0
        for i, fpath in enumerate(paths):
            try:
                rel = fpath.relative_to(self._root)
            except ValueError:
                skipped_outside += 1
                continue
            if not fpath.exists():
                skipped_missing += 1
                continue
            rel_str = str(rel).replace("\\", "/")
            if rel_str in self._open_files:
                skipped_duplicate += 1
                continue
            self._file_stack.enter_context(self._server.open_file(rel_str))
            self._open_files.add(rel_str)
            opened += 1
            if batch_size > 0 and (i + 1) % batch_size == 0 and throttle_fps > 0:
                await asyncio.sleep(batch_size / throttle_fps)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        return {
            "opened": opened,
            "skipped_outside_workspace": skipped_outside,
            "skipped_duplicate": skipped_duplicate,
            "skipped_missing": skipped_missing,
            "elapsed_ms": elapsed_ms,
            "files_per_sec": (round(opened / (elapsed_ms / 1000), 1) if elapsed_ms > 0 else 0.0),
        }

    async def _close_file_stack(self) -> None:
        if self._file_stack is not None:
            await self._file_stack.aclose()
            self._file_stack = None
            self._open_files.clear()

    def _run_on_loop(self, coro: Any, *, timeout: float) -> Any:
        assert self._loop is not None
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        try:
            return fut.result(timeout=timeout)
        except TimeoutError as exc:
            fut.cancel()
            raise BackendError(
                f"LSP request timed out after {timeout}s", code="request_timeout"
            ) from exc
        except Exception as exc:
            raise BackendError(f"LSP request failed: {exc!r}", code="request_failed") from exc

    def _ensure_ready(self) -> None:
        if self._thread is None or not self._thread.is_alive() or self._server is None:
            raise BackendError("client not started; call start() first", code="not_started")

    @property
    def workspace_root(self) -> Path:
        return self._root

    @property
    def is_ready(self) -> bool:
        return self._ready.is_set() and self._server is not None


def create_bsl_client(
    workspace_root: Path | str,
    *,
    jar_path: Path | str | None = None,
    preload: Iterable[Path | str] | None = None,
    populate_wait_secs: float = 0.0,
    start_timeout: float = DEFAULT_START_TIMEOUT,
) -> RealBSLClient:
    """Factory: start client, optionally bulk-preload, return ready instance.

    Caller is responsible for calling `.stop()` (or using `with`).
    """
    client = RealBSLClient(
        workspace_root=workspace_root,
        jar_path=jar_path,
        start_timeout=start_timeout,
    )
    client.start()
    try:
        if preload:
            client.open_workspace(preload)
        if populate_wait_secs > 0:
            time.sleep(populate_wait_secs)
    except Exception:
        client.stop()
        raise
    return client
