"""Minimal Python LSP client for BSL Language Server recon (Phase 0b).

Runs `java -jar bsl-language-server.jar --lsp` as subprocess over stdio
and drives through initialize → didOpen → documentSymbol → references →
prepareRename → rename. Logs responses to recon-logs/.
"""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).parent
JAR = HERE / "bsl-language-server.jar"
WORKSPACE = HERE / "test-workspace"
LOGDIR = HERE / "recon-logs"
LOGDIR.mkdir(exist_ok=True)


def uri(p: Path) -> str:
    return p.resolve().as_uri()


class LspClient:
    def __init__(self, jar: Path, root: Path):
        self.proc = subprocess.Popen(
            ["java", "-jar", str(jar), "--lsp"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(root),
            bufsize=0,
        )
        self.next_id = 1
        self.responses: dict = {}
        self.notifications: list = []
        self.stderr_lines: list = []
        self._stop = False
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self._err_reader = threading.Thread(target=self._read_stderr, daemon=True)
        self._err_reader.start()

    def _read_stderr(self):
        while not self._stop:
            line = self.proc.stderr.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").rstrip()
            self.stderr_lines.append(text)

    def _read_loop(self):
        stream = self.proc.stdout
        while not self._stop:
            try:
                length = 0
                while True:
                    line = stream.readline()
                    if not line:
                        return
                    s = line.decode("utf-8", errors="replace")
                    if s.lower().startswith("content-length:"):
                        length = int(s.split(":", 1)[1].strip())
                    if s == "\r\n" or s == "\n":
                        break
                if length == 0:
                    continue
                body = b""
                while len(body) < length:
                    chunk = stream.read(length - len(body))
                    if not chunk:
                        return
                    body += chunk
                msg = json.loads(body.decode("utf-8", errors="replace"))
                if "id" in msg and ("result" in msg or "error" in msg):
                    self.responses[msg["id"]] = msg
                else:
                    self.notifications.append(msg)
            except Exception as exc:
                self.stderr_lines.append(f"[reader-error] {exc!r}")
                return

    def _write(self, msg: dict):
        body = json.dumps(msg).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        self.proc.stdin.write(header + body)
        self.proc.stdin.flush()

    def request(self, method: str, params: dict, timeout: float = 30.0) -> dict:
        rid = self.next_id
        self.next_id += 1
        self._write({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        deadline = time.time() + timeout
        while time.time() < deadline:
            if rid in self.responses:
                return self.responses.pop(rid)
            time.sleep(0.02)
        raise TimeoutError(f"{method} timeout after {timeout}s")

    def notify(self, method: str, params: dict):
        self._write({"jsonrpc": "2.0", "method": method, "params": params})

    def shutdown(self):
        try:
            self.request("shutdown", None, timeout=5)
        except Exception:
            pass
        try:
            self.notify("exit", None)
        except Exception:
            pass
        self._stop = True
        try:
            self.proc.terminate()
        except Exception:
            pass


def dump(name: str, payload) -> None:
    path = LOGDIR / f"{name}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"wrote {path.relative_to(HERE)}")


def main():
    if not JAR.exists():
        print(f"JAR not found: {JAR}", file=sys.stderr)
        return 1
    if not WORKSPACE.exists():
        print(f"workspace not found: {WORKSPACE}", file=sys.stderr)
        return 1

    t0 = time.time()
    client = LspClient(JAR, WORKSPACE)

    try:
        init_params = {
            "processId": os.getpid(),
            "rootUri": uri(WORKSPACE),
            "workspaceFolders": [
                {"uri": uri(WORKSPACE), "name": "test-workspace"}
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
                },
            },
            "initializationOptions": {},
            "trace": "off",
        }
        init_resp = client.request("initialize", init_params, timeout=60)
        dump("01_initialize", init_resp)
        client.notify("initialized", {})
        cold_ms = int((time.time() - t0) * 1000)
        print(f"initialized in {cold_ms}ms")

        util = WORKSPACE / "CommonModules" / "ТестоваяУтилита" / "Ext" / "Module.bsl"
        caller = WORKSPACE / "CommonModules" / "ТестовыйВызыватель" / "Ext" / "Module.bsl"

        for path in (util, caller):
            client.notify(
                "textDocument/didOpen",
                {
                    "textDocument": {
                        "uri": uri(path),
                        "languageId": "bsl",
                        "version": 1,
                        "text": path.read_text(encoding="utf-8"),
                    }
                },
            )

        time.sleep(1.0)

        ds_resp = client.request(
            "textDocument/documentSymbol",
            {"textDocument": {"uri": uri(util)}},
            timeout=15,
        )
        dump("02_documentSymbol_util", ds_resp)

        # Position of "ПолучитьПараметр" in util (line 0, col 9 — 0-based)
        # Function ПолучитьПараметр starts at line 0. Name is at col 8-23.
        ref_resp = client.request(
            "textDocument/references",
            {
                "textDocument": {"uri": uri(util)},
                "position": {"line": 0, "character": 10},
                "context": {"includeDeclaration": True},
            },
            timeout=15,
        )
        dump("03_references_ПолучитьПараметр", ref_resp)

        prep_resp = client.request(
            "textDocument/prepareRename",
            {
                "textDocument": {"uri": uri(util)},
                "position": {"line": 0, "character": 10},
            },
            timeout=15,
        )
        dump("04_prepareRename", prep_resp)

        rename_resp = client.request(
            "textDocument/rename",
            {
                "textDocument": {"uri": uri(util)},
                "position": {"line": 0, "character": 10},
                "newName": "ПолучитьПараметрНовый",
            },
            timeout=30,
        )
        dump("05_rename_cross_file", rename_resp)

        # Also try rename on local (non-export) function
        # ПолучитьЗначениеПоУмолчанию at line 8 col 10
        prep_local = client.request(
            "textDocument/prepareRename",
            {
                "textDocument": {"uri": uri(util)},
                "position": {"line": 8, "character": 12},
            },
            timeout=15,
        )
        dump("06_prepareRename_local", prep_local)

        rename_local = client.request(
            "textDocument/rename",
            {
                "textDocument": {"uri": uri(util)},
                "position": {"line": 8, "character": 12},
                "newName": "ПолучитьДефолт",
            },
            timeout=15,
        )
        dump("07_rename_local", rename_local)

        dump("99_stderr", client.stderr_lines)
        dump("99_notifications", client.notifications)

    finally:
        client.shutdown()

    return 0


if __name__ == "__main__":
    sys.exit(main())
