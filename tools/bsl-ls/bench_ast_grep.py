#!/usr/bin/env python3
"""R0.3 baseline timing benchmark for ast-grep + tree-sitter-bsl."""

import json
import shutil
import subprocess
import time
from pathlib import Path
from statistics import mean, median

BSL_LS = Path(__file__).parent
AST_GREP = shutil.which("ast-grep.cmd") or shutil.which("ast-grep") or "ast-grep"
SGCONFIG = BSL_LS / "sgconfig.yml"
TEST_WS = BSL_LS / "test-workspace"
REAL_PROJECT = Path(
    r"D:\1С-Framework\src\projects\configuration"
    r"\260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС\src"
)
RULES = ["rename-export-method", "rename-local-var", "rename-catalog-method"]
RUNS = 5


def count_bsl(path: Path) -> int:
    return sum(1 for _ in path.rglob("*.bsl"))


def time_rule(rule_id: str, target: Path) -> dict:
    cmd = [
        AST_GREP, "scan",
        "--config", str(SGCONFIG),
        "--filter", rule_id,
        "--json=compact",
        str(target),
    ]
    timings_ms: list[float] = []
    matches = 0
    for _ in range(RUNS):
        t0 = time.perf_counter()
        proc = subprocess.run(
            cmd, cwd=BSL_LS, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000
        timings_ms.append(elapsed_ms)
        if proc.returncode not in (0, 1):  # 1 = matches found (non-error)
            return {"rule": rule_id, "error": proc.stderr.strip()[:200]}
        try:
            matches = len(json.loads(proc.stdout or "[]"))
        except json.JSONDecodeError:
            matches = -1
    return {
        "rule": rule_id,
        "runs": RUNS,
        "matches": matches,
        "min_ms": round(min(timings_ms), 1),
        "median_ms": round(median(timings_ms), 1),
        "mean_ms": round(mean(timings_ms), 1),
        "max_ms": round(max(timings_ms), 1),
    }


def bench(target: Path, label: str) -> dict:
    file_count = count_bsl(target)
    print(f"\n=== {label}: {target}  ({file_count} .bsl files) ===")
    results = [time_rule(r, target) for r in RULES]
    for r in results:
        if "error" in r:
            print(f"  {r['rule']}: ERROR {r['error']}")
        else:
            print(
                f"  {r['rule']:>24s}: {r['matches']:>5d} matches | "
                f"min={r['min_ms']:>7.1f}ms median={r['median_ms']:>7.1f}ms "
                f"max={r['max_ms']:>7.1f}ms"
            )
    return {"label": label, "target": str(target), "file_count": file_count, "rules": results}


def main() -> None:
    print(f"ast-grep baseline timing (RUNS={RUNS} per rule)")
    print(f"Config: {SGCONFIG}")
    all_results = [
        bench(TEST_WS, "test-workspace"),
        bench(REAL_PROJECT, "real-project (260304_GKSTCPLK-2182)"),
    ]
    out = BSL_LS / "ast-grep-baseline.json"
    out.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
