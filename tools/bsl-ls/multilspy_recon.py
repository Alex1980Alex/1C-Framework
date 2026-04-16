"""Multilspy-based BSL Language Server recon (R0.1).

Replaces lsp_recon.py with multilspy's managed subprocess lifecycle.
Tests: references, rename, document_symbols with bulk workspace preload.
"""
import asyncio
import json
import time
from contextlib import ExitStack
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


class BSLLanguageServer(LanguageServer):
    """Custom multilspy adapter for BSL Language Server."""

    def __init__(self, config: MultilspyConfig, logger: MultilspyLogger,
                 repository_root_path: str):
        if not JAR.exists():
            raise FileNotFoundError(f"BSL LS JAR not found: {JAR}")
        launch_info = ProcessLaunchInfo(
            cmd=f'java -jar "{JAR}" --stdio',
            cwd=repository_root_path,
        )
        super().__init__(config, logger, repository_root_path, launch_info,
                         language_id="bsl")


class FileLogger(MultilspyLogger):
    """Simple file-based logger."""

    def __init__(self, log_path: Path):
        self._fh = open(log_path, "w", encoding="utf-8")

    def log(self, message: str, level: int = 0):
        self._fh.write(message + "\n")
        self._fh.flush()

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
        code_language=Language.PYTHON,  # placeholder; BSLLanguageServer overrides
        trace_lsp_communication=True,
    )
    logger = FileLogger(LOGDIR / "trace.log")

    bsl_files = list(WORKSPACE.rglob("*.bsl"))
    print(f"Found {len(bsl_files)} BSL files")

    server = BSLLanguageServer(config, logger, str(WORKSPACE.resolve()))

    t0 = time.time()
    async with server.start_server():
        init_ms = int((time.time() - t0) * 1000)
        print(f"Server started in {init_ms}ms")

        # Bulk preload ALL files — keep them open via ExitStack
        preload_t0 = time.time()
        with ExitStack() as stack:
            rel_paths = []
            for fpath in sorted(bsl_files):
                rel = fpath.relative_to(WORKSPACE.resolve())
                rel_str = str(rel).replace("\\", "/")
                stack.enter_context(server.open_file(rel_str))
                rel_paths.append(rel_str)
            preload_ms = int((time.time() - preload_t0) * 1000)
            print(f"Bulk preload {len(bsl_files)} files in {preload_ms}ms")

            # Let LS index
            await asyncio.sleep(3)

            util_rel = "CommonModules/ТестоваяУтилита/Ext/Module.bsl"
            caller_rel = "CommonModules/ТестовыйВызыватель/Ext/Module.bsl"
            util_uri = Path(WORKSPACE / util_rel).resolve().as_uri()

            # 1. Document symbols
            print("\n--- Document Symbols (util) ---")
            try:
                symbols, tree = await server.request_document_symbols(util_rel)
                syms = symbols if symbols else []
                dump("01_document_symbols", {
                    "count": len(syms),
                    "symbols": [{"name": s["name"], "kind": s["kind"]} for s in syms],
                    "tree": str(tree)[:500] if tree else None,
                })
                print(f"  Found {len(syms)} symbols")
            except Exception as e:
                dump("01_document_symbols", {"error": str(e)})
                print(f"  Error: {e}")

            # 2. References for ПолучитьПараметр (line 0, col 10)
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

            # 3. Definition from caller (cross-file)
            print("\n--- Definition from caller (cross-file) ---")
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
            print("\n--- Prepare Rename (ПолучитьПараметр) ---")
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

            # 5. Rename (cross-file) — dry run
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
                print(f"  Files affected: {len(changes)}, total edits: {total_edits}")
                for file_uri, edits in changes.items():
                    print(f"    {file_uri}: {len(edits)} edits")
            except Exception as e:
                dump("05_rename_cross_file", {"error": str(e)})
                print(f"  Error: {e}")

            # 6. Rename local function
            print("\n--- Rename local (ПолучитьЗначениеПоУмолчанию) ---")
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

            # 7. Workspace symbol search
            print("\n--- Workspace Symbol (Получить) ---")
            try:
                ws_symbols = await server.request_workspace_symbol("Получить")
                ws = ws_symbols if ws_symbols else []
                dump("07_workspace_symbol", {
                    "count": len(ws),
                    "symbols": [{"name": s.get("name"), "kind": s.get("kind")}
                                for s in ws[:10]],
                })
                print(f"  Found {len(ws)} symbols")
            except Exception as e:
                dump("07_workspace_symbol", {"error": str(e)})
                print(f"  Error: {e}")

    logger.close()

    # Summary
    print("\n=== Summary ===")
    rename_file = LOGDIR / "05_rename_cross_file.json"
    if rename_file.exists():
        data = json.loads(rename_file.read_text(encoding="utf-8"))
        if "error" in data:
            print(f"DoD FAIL: rename error: {data['error']}")
        elif data.get("total_edits", 0) >= 2:
            print(f"DoD PASS: cross-file rename returned {data['total_edits']} edits "
                  f"across {len(data.get('files_affected', []))} files")
        else:
            print(f"DoD FAIL: cross-file rename returned only {data.get('total_edits', 0)} "
                  f"edits (need >=2)")
            print("  BSL LS does NOT support cross-file rename even with multilspy preload")
    else:
        print("DoD FAIL: no rename result file")


if __name__ == "__main__":
    asyncio.run(run_recon())
