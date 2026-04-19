"""Reproduce T02 multilspy rename failure from full-1b benchmark.

Task T02:
  file: src/bsl/CommonModules/АдресныйКлассификатор/Ext/Module.bsl
  position: line=303, character=1 (0-based per LSP spec)
  rename: РезультатЗапроса -> ЗапросРезультат
  expected: 1 file / 1 edit

Benchmark event: applied=false, duration_ms=1, error_code=null.
Suggests LSP returned quickly with no edits — investigate why.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from src.bsl.semantic_search.refactor.backends.real_bsl_client import create_bsl_client

BSL_ROOT = REPO_ROOT / "src" / "bsl"
REL = "CommonModules/АдресныйКлассификатор/Ext/Module.bsl"
TARGET = BSL_ROOT / REL
LINE_0BASED = 303
CHAR_0BASED = 1
OLD = "РезультатЗапроса"
NEW = "ЗапросРезультат"


def main() -> None:
    assert TARGET.exists(), f"target missing: {TARGET}"
    print(f"[repro] target file: {TARGET}")
    print(f"[repro] file size: {TARGET.stat().st_size} bytes")

    text = TARGET.read_text(encoding="utf-8-sig").splitlines()
    if LINE_0BASED < len(text):
        print(f"[repro] line {LINE_0BASED} (0-based) content: {text[LINE_0BASED]!r}")
    for offset in (-1, 0, 1):
        ln = LINE_0BASED + offset
        if 0 <= ln < len(text):
            print(f"[repro]   line {ln}: {text[ln]!r}")

    bsl_files = list(BSL_ROOT.rglob("*.bsl"))
    print(f"[repro] preloading {len(bsl_files)} .bsl files...")
    client = create_bsl_client(
        workspace_root=BSL_ROOT,
        preload=bsl_files,
        populate_wait_secs=3.0,
        start_timeout=120.0,
    )
    print("[repro] client ready")

    uri = TARGET.as_uri()
    print(f"[repro] uri: {uri}")

    for line_try, char_try in [
        (LINE_0BASED, CHAR_0BASED),
        (LINE_0BASED, 2),
        (LINE_0BASED - 1, CHAR_0BASED),
        (LINE_0BASED + 1, CHAR_0BASED),
    ]:
        params = {
            "textDocument": {"uri": uri},
            "position": {"line": line_try, "character": char_try},
            "newName": NEW,
        }
        try:
            pre = client.prepare_rename(params)
            print(f"[repro] prepare_rename(line={line_try}, char={char_try}) -> {pre!r}")
        except Exception as e:
            print(f"[repro] prepare_rename(line={line_try}, char={char_try}) RAISED: {e!r}")
        try:
            r = client.rename(params)
            n_changes = len(r.get("changes", {})) if isinstance(r, dict) else 0
            n_doc = len(r.get("documentChanges", [])) if isinstance(r, dict) else 0
            print(
                f"[repro] rename(line={line_try}, char={char_try}) -> "
                f"raw_keys={list(r.keys()) if isinstance(r, dict) else type(r).__name__} "
                f"changes={n_changes} documentChanges={n_doc}"
            )
            if r and isinstance(r, dict):
                print(f"[repro]   body: {json.dumps(r, ensure_ascii=False)[:500]}")
        except Exception as e:
            print(f"[repro] rename(line={line_try}, char={char_try}) RAISED: {e!r}")
        print()

    client.stop()
    print("[repro] done")


if __name__ == "__main__":
    main()
