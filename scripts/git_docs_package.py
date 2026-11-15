"""Build or verify the explicit Git/docs package using trusted code."""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
_helper = Path(__file__).with_name("git_docs_source_loader.py")
_loader = {"__file__": str(_helper), "__name__": "_git_docs_source_loader"}
exec(compile(_helper.read_bytes(), str(_helper), "exec"), _loader)
main = _loader["load_delivery"](Path(__file__).resolve().parents[1]).main

if __name__ == "__main__":
    raise SystemExit(main())
