"""Multilspy-based BSL Language Server recon (R0.1).

Replaces lsp_recon.py with multilspy's managed subprocess lifecycle.
Tests: references, rename, document_symbols with bulk workspace preload.
"""
import asyncio
import json
import logging
import os
import time
from collections.abc import AsyncIterator
from contextlib import ExitStack, asynccontextmanager
from pathlib import Path
from typing import Any

from multilspy.language_server import LanguageServer
from multilspy.lsp_protocol_handler.server import ProcessLaunchInfo
from multilspy.multilspy_config import Language, MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger

HERE = Path(__file__).parent
JAR = HERE / "bsl-language-server.jar"
WORKSPACE = HERE / "test-workspace"
LOGDIR = HERE / "multilspy-logs"
LOGDIR.mkdir(exist_ok=True)


def _build_init_params(root: str) -> dict:
    root_path = Path(root)
    return {
        "processId": os.getpid(),
        "rootPath": root,
        "rootUri": root_path.as_uri(),
        "workspaceFolders": [
            {"uri": root_path.as_uri(), "name": root_path.name}
        ],
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


class BSLLanguageServer(LanguageServer):
    """Custom multilspy adapter for BSL Language Server."""

    def __init__(self, config: MultilspyConfig, logger: MultilspyLogger,
                 repository_root_path: str):
        if not JAR.exists():
            raise FileNotFoundError(f"BSL LS JAR not found: {JAR}")
        launch_info = ProcessLaunchInfo(
            cmd=f'java -jar "{JAR}" --lsp',
            cwd=repository_root_path,
        )
        super().__init__(config, logger, repository_root_path, launch_info,
                         language_id="bsl")

    @asynccontextmanager
    async def start_server(self) -> AsyncIterator["BSLLanguageServer"]:
        """Start BSL LS, send initialize, wait for ready, yield self."""
        async def do_nothing(params):
            return

        async def log_message(msg):
            self.logger.log(f"LSP: window/logMessage: {msg}", logging.INFO)

        self.server.on_request("client/registerCapability", do_nothing)
        self.server.on_notification("language/status", do_nothing)
        self.server.on_notification("window/logMessage", log_message)
        self.server.on_notification("window/showMessage", do_nothing)
        self.server.on_notification("textDocument/publishDiagnostics", do_nothing)
        self.server.on_notification("$/progress", do_nothing)

        async with super().start_server():
            self.logger.log("Starting BSL Language Server process", logging.INFO)
            await self.server.start()

            init_params = _build_init_params(self.repository_root_path)
            self.logger.log("Sending initialize request", logging.INFO)
            init_response = await self.server.send.initialize(init_params)
            caps = init_response.get("capabilities", {})
            self.logger.log(f"Capabilities: {list(caps.keys())}", logging.INFO)

            self.server.notify.initialized({})
            self.logger.log("BSL LS initialized", logging.INFO)

            yield self

            await self.server.shutdown()
            await self.server.stop()


class FileLogger(MultilspyLogger):
    """Simple file-based logger matching MultilspyLogger interface."""

    def __init__(self, log_path: Path):
        self._fh = open(log_path, "w", encoding="utf-8")
        self.logger = logging.Logger("multilspy_bsl", level=logging.DEBUG)
        self.logger.addHandler(logging.StreamHandler(self._fh))

    def close(self):
        self._fh.close()


def dump(name: str, payload: Any) -> None:
    path = LOGDIR / f"{name}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"  wrote {path.name}")


async def run_recon():
    print("=== Multilspy BSL LS Recon ===")
    print(f"JAR: {JAR}")
    print(f"Workspace: {WORKSPACE}")

    config = MultilspyConfig(
        code_language=Language.PYTHON,
        trace_lsp_communication=False,
    )
    logger = FileLogger(LOGDIR / "trace.log")

    bsl_files = list(WORKSPACE.rglob("*.bsl"))
    print(f"Found {len(bsl_files)} BSL files")

    server = BSLLanguageServer(config, logger, str(WORKSPACE.resolve()))

    try:
        await _run_tests(server, logger, bsl_files)
    finally:
        logger.close()


async def _run_tests(server: BSLLanguageServer, logger: FileLogger,
                     bsl_files: list) -> None:
    t0 = time.time()
    async with server.start_server():
        init_ms = int((time.time() - t0) * 1000)
        print(f"Server initialized in {init_ms}ms")

        preload_t0 = time.time()
        with ExitStack() as stack:
            for fpath in sorted(bsl_files):
                rel = fpath.relative_to(WORKSPACE.resolve())
                rel_str = str(rel).replace("\\", "/")
                stack.enter_context(server.open_file(rel_str))
            preload_ms = int((time.time() - preload_t0) * 1000)
            print(f"Bulk preload {len(bsl_files)} files in {preload_ms}ms")

            await asyncio.sleep(3)

            util_rel = "CommonModules/ТестоваяУтилита/Ext/Module.bsl"
            caller_rel = "CommonModules/ТестовыйВызыватель/Ext/Module.bsl"
            util_uri = Path(WORKSPACE / util_rel).resolve().as_uri()

            # 1. Document symbols
            print("\n--- Document Symbols ---")
            try:
                symbols, tree = await server.request_document_symbols(util_rel)
                syms = symbols if symbols else []
                dump("01_document_symbols", {
                    "count": len(syms),
                    "symbols": [{"name": s["name"], "kind": s["kind"]} for s in syms],
                })
                print(f"  Found {len(syms)} symbols")
            except Exception as e:
                dump("01_document_symbols", {"error": str(e)})
                print(f"  Error: {e}")

            # 2. References
            print("\n--- References (ПолучитьПараметр) ---")
            try:
                refs = await server.request_references(util_rel, 0, 10)
                locs = refs if refs else []
                dump("02_references", {
                    "count": len(locs),
                    "locations": [
                        {"uri": str(r.get("uri", "")),
                         "line": r.get("range", {}).get("start", {}).get("line")}
                        for r in locs[:20]
                    ],
                })
                print(f"  Found {len(locs)} references")
            except Exception as e:
                dump("02_references", {"error": str(e)})
                print(f"  Error: {e}")

            # 3. Definition from caller
            print("\n--- Definition from caller ---")
            try:
                defs = await server.request_definition(caller_rel, 1, 20)
                d_list = defs if defs else []
                dump("03_definition", {
                    "count": len(d_list),
                    "locations": [
                        {"uri": str(d.get("uri", "")),
                         "line": d.get("range", {}).get("start", {}).get("line")}
                        for d in d_list[:5]
                    ],
                })
                print(f"  Found {len(d_list)} definitions")
            except Exception as e:
                dump("03_definition", {"error": str(e)})
                print(f"  Error: {e}")

            # 4. Prepare rename
            print("\n--- Prepare Rename ---")
            try:
                prep = await server.server.send.prepare_rename({
                    "textDocument": {"uri": util_uri},
                    "position": {"line": 0, "character": 10},
                })
                dump("04_prepare_rename", prep)
                print(f"  Result: {json.dumps(prep, ensure_ascii=False)[:200]}")
            except Exception as e:
                dump("04_prepare_rename", {"error": str(e)})
                print(f"  Error: {e}")

            # 5. Rename cross-file
            print("\n--- Rename cross-file (dry run) ---")
            try:
                rename_result = await server.server.send.rename({
                    "textDocument": {"uri": util_uri},
                    "position": {"line": 0, "character": 10},
                    "newName": "ПолучитьПараметрНовый",
                })
                changes = rename_result.get("changes", {}) if rename_result else {}
                total_edits = sum(len(v) for v in changes.values())
                dump("05_rename_cross_file", {
                    "total_edits": total_edits,
                    "files_affected": list(changes.keys()),
                    "changes": {
                        k: [{"line": e.get("range", {}).get("start", {}).get("line"),
                             "newText": e.get("newText", "")}
                            for e in v]
                        for k, v in changes.items()
                    } if changes else {},
                })
                print(f"  Files: {len(changes)}, edits: {total_edits}")
                for file_uri, edits in changes.items():
                    print(f"    {file_uri}: {len(edits)} edits")
            except Exception as e:
                dump("05_rename_cross_file", {"error": str(e)})
                print(f"  Error: {e}")

            # 6. Rename local
            print("\n--- Rename local ---")
            try:
                rename_local = await server.server.send.rename({
                    "textDocument": {"uri": util_uri},
                    "position": {"line": 8, "character": 12},
                    "newName": "ПолучитьДефолт",
                })
                ch = rename_local.get("changes", {}) if rename_local else {}
                dump("06_rename_local", {
                    "total_edits": sum(len(v) for v in ch.values()),
                    "files_affected": list(ch.keys()),
                })
                print(f"  Files: {len(ch)}, edits: {sum(len(v) for v in ch.values())}")
            except Exception as e:
                dump("06_rename_local", {"error": str(e)})
                print(f"  Error: {e}")

    # Summary
    print("\n=== Summary ===")
    rename_file = LOGDIR / "05_rename_cross_file.json"
    if rename_file.exists():
        data = json.loads(rename_file.read_text(encoding="utf-8"))
        if "error" in data:
            print(f"DoD FAIL: rename error: {data['error']}")
        elif data.get("total_edits", 0) >= 2:
            print(f"DoD PASS: {data['total_edits']} edits across "
                  f"{len(data.get('files_affected', []))} files")
        else:
            print(f"DoD FAIL: only {data.get('total_edits', 0)} edits (need >=2)")
            print("  BSL LS does NOT support cross-file rename even with preload")
    else:
        print("DoD FAIL: no rename result file")


if __name__ == "__main__":
    asyncio.run(run_recon())
