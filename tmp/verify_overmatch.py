"""Quick verify: does name over-match across .bsl files?"""
from pathlib import Path
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

names = ["СписокРегионов", "РезультатЗапроса", "Параметры"]
for name in names:
    count_files = 0
    count_hits = 0
    sample_files = []
    for bsl in Path("src/bsl").rglob("*.bsl"):
        try:
            text = bsl.read_text(encoding="utf-8")
            if name in text:
                count_files += 1
                count_hits += text.count(name)
                if len(sample_files) < 3:
                    sample_files.append(str(bsl))
        except Exception:
            pass
    print(f"Name={name}: files={count_files}, occurrences={count_hits}")
    for f in sample_files:
        print(f"  - {f}")
