"""R0.1 extended validation: multilspy + BSL LS on a real 2k-file 1C project.

Target rename: гкс_ОчередьСообщенийRMQ.СоздатьСообщенияПоСобытиюОбъекта
(7 caller files — stress test cross-file resolution at scale).
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
PROJECT_ROOT = Path(
    r"D:\1С-Framework\src\projects\configuration"
    r"\260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС\src"
)
LOGDIR = HERE / "multilspy-logs-real"
LOGDIR.mkdir(exist_ok=True)

TARGET_MODULE_REL = "CommonModules/гкс_ОчередьСообщенийRMQ/Ext/Module.bsl"
TARGET_FUNCTION = "СоздатьСообщенияПоСобытиюОбъекта"
TARGET_LINE = 28  # 0-indexed; line 29 in 1-indexed
# "Функция " = 8 chars → char=10 is inside the identifier
TARGET_CHAR = 10

PRELOAD_BATCH_SIZE = 50
POPULATE_WAIT_SECS = 60  # heuristic — BSL LS populateContext on 2k files can be slow
NEW_NAME = "СоздатьСообщенияПоСобытиюОбъектаНовое"


def _build_init_params(root: str) -> dict:
    root_path = Path(root)
    return {
        "processId": os.getpid(),
        "rootPath": root,
        "rootUri": root_path.as_uri(),
        "workspaceFolders": [{"uri": root_path.as_uri(), "name": root_path.name}],
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
    def __init__(self, config: MultilspyConfig, logger: MultilspyLogger, root: str):
        if not JAR.exists():
            raise FileNotFoundError(f"BSL LS JAR not found: {JAR}")
        launch = ProcessLaunchInfo(cmd=f'java -jar "{JAR}" --lsp', cwd=root)
        super().__init__(config, logger, root, launch, language_id="bsl")

    @asynccontextmanager
    async def start_server(self) -> AsyncIterator["BSLLanguageServer"]:
        async def noop(params):  # noqa: ARG001
            return

        async def log_msg(msg):
            self.logger.log(f"LSP: window/logMessage: {msg}", logging.INFO)

        self.server.on_request("client/registerCapability", noop)
        self.server.on_notification("language/status", noop)
        self.server.on_notification("window/logMessage", log_msg)
        self.server.on_notification("window/showMessage", noop)
        self.server.on_notification("textDocument/publishDiagnostics", noop)
        self.server.on_notification("$/progress", noop)

        async with super().start_server():
            await self.server.start()
            await self.server.send.initialize(_build_init_params(self.repository_root_path))
            self.server.notify.initialized({})
            yield self
            await self.server.shutdown()
            await self.server.stop()


class FileLogger(MultilspyLogger):
    def __init__(self, log_path: Path):
        self._fh = open(log_path, "w", encoding="utf-8")
        self.logger = logging.Logger("multilspy_bsl", level=logging.DEBUG)
        self.logger.addHandler(logging.StreamHandler(self._fh))

    def close(self):
        self._fh.close()


def dump(name: str, run_id: int, payload: Any) -> None:
    path = LOGDIR / f"run{run_id}_{name}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


async def _one_run(run_id: int, bsl_files: list[Path]) -> dict:
    print(f"\n=== Run #{run_id} ===")
    metrics: dict = {"run": run_id, "file_count": len(bsl_files)}

    logger = FileLogger(LOGDIR / f"run{run_id}_trace.log")
    config = MultilspyConfig(code_language=Language.PYTHON, trace_lsp_communication=False)
    server = BSLLanguageServer(config, logger, str(PROJECT_ROOT.resolve()))

    try:
        t_init = time.perf_counter()
        async with server.start_server():
            metrics["init_ms"] = round((time.perf_counter() - t_init) * 1000, 1)
            print(f"  init_ms = {metrics['init_ms']}")

            # Bulk preload — batched to avoid overwhelming BSL LS
            t_pre = time.perf_counter()
            with ExitStack() as stack:
                for i, fpath in enumerate(sorted(bsl_files)):
                    rel = fpath.relative_to(PROJECT_ROOT.resolve())
                    rel_str = str(rel).replace("\\", "/")
                    stack.enter_context(server.open_file(rel_str))
                    if (i + 1) % PRELOAD_BATCH_SIZE == 0:
                        await asyncio.sleep(0.05)  # throttle
                metrics["preload_ms"] = round((time.perf_counter() - t_pre) * 1000, 1)
                metrics["preload_files_per_sec"] = round(
                    len(bsl_files) / (metrics["preload_ms"] / 1000), 1
                )
                print(
                    f"  preload_ms = {metrics['preload_ms']} "
                    f"({metrics['preload_files_per_sec']} files/s)"
                )

                # Wait for populateContext + ReferenceIndex to settle
                t_wait = time.perf_counter()
                print(f"  waiting {POPULATE_WAIT_SECS}s for populateContext…")
                await asyncio.sleep(POPULATE_WAIT_SECS)
                metrics["wait_ms"] = round((time.perf_counter() - t_wait) * 1000, 1)

                # Prepare rename (sanity)
                target_uri = (PROJECT_ROOT / TARGET_MODULE_REL).resolve().as_uri()
                t_pr = time.perf_counter()
                prep = await server.server.send.prepare_rename({
                    "textDocument": {"uri": target_uri},
                    "position": {"line": TARGET_LINE, "character": TARGET_CHAR},
                })
                metrics["prepare_ms"] = round((time.perf_counter() - t_pr) * 1000, 1)
                dump("prepare_rename", run_id, prep)

                # Cross-file rename
                t_ren = time.perf_counter()
                rename_result = await server.server.send.rename({
                    "textDocument": {"uri": target_uri},
                    "position": {"line": TARGET_LINE, "character": TARGET_CHAR},
                    "newName": NEW_NAME,
                })
                metrics["rename_ms"] = round((time.perf_counter() - t_ren) * 1000, 1)

                changes = rename_result.get("changes", {}) if rename_result else {}
                metrics["total_edits"] = sum(len(v) for v in changes.values())
                metrics["files_affected"] = len(changes)
                dump("rename", run_id, {
                    "total_edits": metrics["total_edits"],
                    "files_affected": sorted(changes.keys()),
                    "edit_counts": {k: len(v) for k, v in changes.items()},
                })
                print(
                    f"  prepare_ms = {metrics['prepare_ms']}  "
                    f"rename_ms = {metrics['rename_ms']}  "
                    f"edits = {metrics['total_edits']} across {metrics['files_affected']} files"
                )
    except Exception as e:
        metrics["error"] = f"{type(e).__name__}: {e}"
        print(f"  ERROR: {metrics['error']}")
    finally:
        logger.close()

    return metrics


async def main():
    print("=== Multilspy BSL LS — real-project validation ===")
    print(f"Project: {PROJECT_ROOT}")
    print(f"JAR: {JAR}")
    print(f"Target: {TARGET_MODULE_REL} :: {TARGET_FUNCTION}")

    bsl_files = list(PROJECT_ROOT.rglob("*.bsl"))
    print(f"BSL files: {len(bsl_files)}")

    all_metrics = []
    for run_id in (1, 2):
        m = await _one_run(run_id, bsl_files)
        all_metrics.append(m)

    out = LOGDIR / "summary.json"
    out.write_text(
        json.dumps(all_metrics, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\nSaved summary: {out}")
    print("\n=== Summary ===")
    for m in all_metrics:
        if "error" in m:
            print(f"  Run {m['run']}: ERROR {m['error']}")
        else:
            print(
                f"  Run {m['run']}: init={m.get('init_ms')}ms "
                f"preload={m.get('preload_ms')}ms "
                f"rename={m.get('rename_ms')}ms "
                f"edits={m.get('total_edits')}/{m.get('files_affected')}f"
            )


if __name__ == "__main__":
    asyncio.run(main())
