"""One-shot: rewrite ~/AppData/Roaming/obsidian/obsidian.json with correct UTF-8 vault path."""
import json
import os
from pathlib import Path

cfg_path = Path(os.environ["APPDATA"]) / "obsidian" / "obsidian.json"

clean = {
    "vaults": {
        "2c6b4f346f58dce5": {
            "path": "C:\\1С-Framework",
            "ts": 1778835123888,
            "open": True,
        }
    }
}

cfg_path.write_text(
    json.dumps(clean, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print(f"Written: {cfg_path}")
print(cfg_path.read_text(encoding="utf-8"))
