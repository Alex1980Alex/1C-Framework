# -*- coding: utf-8 -*-
"""One-shot utility: register ensure-docker-qdrant SessionStart hook in .claude/settings.json.

Run once then delete. Preserves existing hook entries, idempotent.
"""
import json
from pathlib import Path

PROJECT = Path(r"D:\1С-Framework")
SETTINGS = PROJECT / ".claude" / "settings.json"
PY = PROJECT / ".venv" / "Scripts" / "python.exe"
HOOK = PROJECT / ".claude" / "hooks" / "ensure-docker-qdrant.py"

HOOK_CMD = f"{PY} {HOOK}"

data = json.loads(SETTINGS.read_text(encoding="utf-8"))
hooks_block = data.setdefault("hooks", {}).setdefault("SessionStart", [])

already = any(
    any(h.get("command") == HOOK_CMD for h in block.get("hooks", []))
    for block in hooks_block
)
if already:
    print("Already registered — no change")
else:
    hooks_block.append({
        "hooks": [{
            "type": "command",
            "command": HOOK_CMD,
            "timeout": 10,
            "statusMessage": "ensure-docker-qdrant",
        }]
    })
    SETTINGS.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("Registered ensure-docker-qdrant SessionStart hook")

print("Command:", HOOK_CMD)
print("SessionStart entries:", len(data["hooks"]["SessionStart"]))
