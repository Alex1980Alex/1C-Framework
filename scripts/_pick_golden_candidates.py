"""One-off helper: scroll CommonModules symbols and print 12 diverse candidates for manual golden-set crafting."""
from __future__ import annotations
import os
import random
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qdrant_client import QdrantClient
from qdrant_client.http import models

random.seed(42)
c = QdrantClient(host="localhost", port=6333)
flt = models.Filter(must=[models.FieldCondition(key="module_path", match=models.MatchText(text="CommonModules"))])
all_pts: list = []
offset = None
while True:
    pts, offset = c.scroll("bsl_code_v4_late", limit=256, with_payload=True, scroll_filter=flt, offset=offset)
    all_pts.extend([p for p in pts if (p.payload or {}).get("symbol_type") in ("Function","Procedure") and (p.payload or {}).get("content")])
    if offset is None or len(all_pts) >= 3000:
        break
print(f"Total CommonModules candidates: {len(all_pts)}")

small, medium, god = [], [], []
for p in all_pts:
    mp = p.payload.get("module_path","")
    try:
        sz = os.path.getsize(mp)
    except OSError:
        continue
    if sz < 50_000: small.append((p, sz))
    elif sz < 300_000: medium.append((p, sz))
    else: god.append((p, sz))
print(f"By slice: small={len(small)} medium={len(medium)} god={len(god)}")

def pick(pool, n):
    random.shuffle(pool)
    picks = []
    seen = set()
    for p, sz in pool:
        mp = p.payload.get("module_path","")
        nm = p.payload.get("name","") or ""
        if len(nm) < 12: continue
        if "_part" in nm or nm.startswith("Тест"): continue
        if mp in seen: continue
        seen.add(mp)
        picks.append((p, sz))
        if len(picks) >= n: break
    return picks

picks = pick(small, 5) + pick(medium, 4) + pick(god, 3)
# Dump full metadata for downstream golden-set crafting
import json
dump = []
for i, (p, sz) in enumerate(picks):
    pl = p.payload
    kb = sz // 1024
    slc = "small" if kb < 50 else "medium" if kb < 300 else "god_object"
    dump.append({
        "idx": i,
        "name": pl.get("name"),
        "module_path": pl.get("module_path"),
        "line_start": int(pl.get("line_start") or 0),
        "line_end": int(pl.get("line_end") or 0),
        "size_kb": kb,
        "slice": slc,
        "content_preview": (pl.get("content") or "")[:500],
    })
Path("data/_golden_candidates.json").write_text(json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Dumped {len(dump)} candidates to data/_golden_candidates.json")
print(f"\nSelected {len(picks)} symbols:")
for i, (p, sz) in enumerate(picks):
    pl = p.payload
    mp = pl.get("module_path","")
    kb = sz // 1024
    slc = "small" if kb < 50 else "medium" if kb < 300 else "god_object"
    name = pl.get("name","?")
    line = pl.get("line_start","?")
    parts = mp.replace("\\","/").split("/CommonModules/")
    short = parts[-1] if len(parts) > 1 else mp[-50:]
    content_preview = (pl.get("content") or "")[:180].replace("\n"," | ")
    print(f"  [{i:2d}] {name:<55} | {kb:>4}KB ({slc:<10}) | line {line:>5}")
    print(f"       module: ...CommonModules/{short}")
    print(f"       content: {content_preview}")
    print()
