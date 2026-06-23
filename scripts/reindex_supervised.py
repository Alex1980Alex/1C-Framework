#!/usr/bin/env python3
"""Part B (ADR-038): супервизор устойчивого ERP-reindex.

Запускает `reindex_bsl_qwen3.py` (resume) и следит за прогрессом по heartbeat-строкам
лога. Если прогон «заклинило» (idle > IDLE_LIMIT) — убивает дерево процессов и
перезапускает с МЕНЬШИМ batch (лестница 32→8→1). `--skip-indexed` сохраняет прогресс,
batch=1 гарантированно не виснет (один чанк за раз). Так истинный CUDA-wedge Qwen3-8B
(который длится часами) переживается без потери уже проиндексированного.

Почему idle, а не poison-by-path: батч-эскалация + resume надёжнее и проще, чем
вычислять точный «отравленный» файл (буфер копит чанки нескольких файлов, атрибуция
нечёткая). Part A (`--long-batch1-tokens`) уже снимает почти все зависания заранее —
супервизор тут страховочная сетка.

Запуск:
  python scripts/reindex_supervised.py --project <ABS> --collection bsl_code_erp_ref \
      --max-file-bytes 2097152 --long-batch1-tokens 1024

Идемпотентно: повторный запуск продолжает с того же места (resume).
"""

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

# Истинный wedge длится часами; легитимный тяжёлый файл на batch=1 — минуты (621KB ~3мин
# наблюдалось). 20мин чисто разделяет «медленно, но идёт» и «зависло».
DEFAULT_IDLE_LIMIT = 1200
POLL = 30
BATCH_LADDER = (32, 8, 1)

_IDLE_RE = re.compile(r"idle=([0-9hms.]+)")


def _parse_idle(token: str) -> float:
    """'48.2s' / '1m40s' / '3m10s' / '10h35m' → секунды (0.0 при неразборе)."""
    total = 0.0
    for num, unit in re.findall(r"([0-9.]+)([hms])", token):
        v = float(num)
        total += v * {"h": 3600, "m": 60, "s": 1}[unit]
    return total


def _last_idle(log: Path) -> float | None:
    """Idle последней [hb]-строки лога (None если строк ещё нет)."""
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for ln in reversed(lines):
        if ln.startswith("[hb]"):
            m = _IDLE_RE.search(ln)
            if m:
                return _parse_idle(m.group(1))
    return None


def _kill_tree(proc: subprocess.Popen) -> None:
    try:
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            capture_output=True,
            timeout=30,
        )
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def _build_cmd(args, batch: int) -> list[str]:
    cmd = [
        PY,
        str(ROOT / "scripts" / "reindex_bsl_qwen3.py"),
        "--project",
        args.project,
        "--embedder",
        "qwen3-st",
        "--pooling-mode",
        "standard",
        "--collection",
        args.collection,
        "--skip-indexed",
        "--enable-sparse",
        "--batch-size",
        str(batch),
    ]
    if args.max_file_bytes:
        cmd += ["--max-file-bytes", str(args.max_file_bytes)]
    if args.long_batch1_tokens:
        cmd += ["--long-batch1-tokens", str(args.long_batch1_tokens)]
    return cmd


def run_attempt(args, batch: int, log: Path) -> str:
    """Один прогон reindex под надзором. Вернуть 'ok' | 'wedge' | 'error'."""
    print(f"[supervisor] старт batch={batch} → log {log.name}", flush=True)
    with log.open("w", encoding="utf-8") as fh:
        proc = subprocess.Popen(_build_cmd(args, batch), stdout=fh, stderr=subprocess.STDOUT)
    try:
        while True:
            time.sleep(POLL)
            rc = proc.poll()
            if rc is not None:
                return "ok" if rc == 0 else "error"
            idle = _last_idle(log)
            if idle is not None and idle > args.idle_limit:
                print(
                    f"[supervisor] WEDGE: idle={idle:.0f}s > {args.idle_limit}s @ batch={batch} → kill",
                    flush=True,
                )
                _kill_tree(proc)
                return "wedge"
    except KeyboardInterrupt:
        _kill_tree(proc)
        raise


def main() -> int:
    ap = argparse.ArgumentParser(description="Part B (ADR-038) supervised reindex")
    ap.add_argument("--project", required=True, help="ABS project root (для resume-match)")
    ap.add_argument("--collection", required=True)
    ap.add_argument("--max-file-bytes", type=int, default=0)
    ap.add_argument("--long-batch1-tokens", type=int, default=1024)
    ap.add_argument("--idle-limit", type=int, default=DEFAULT_IDLE_LIMIT)
    ap.add_argument(
        "--ladder",
        default=",".join(map(str, BATCH_LADDER)),
        help="batch-эскалация через запятую (default 32,8,1)",
    )
    args = ap.parse_args()

    ladder = [int(x) for x in args.ladder.split(",") if x.strip()]
    if not ladder:
        print("ERROR: --ladder must contain at least one batch value", flush=True)
        return 1
    logdir = ROOT / "logs"
    logdir.mkdir(parents=True, exist_ok=True)

    for i, batch in enumerate(ladder, 1):
        log = logdir / f"reindex_supervised_b{batch}.out.log"
        verdict = run_attempt(args, batch, log)
        if verdict == "ok":
            print(f"[supervisor] ГОТОВО — reindex завершён успешно (batch={batch})", flush=True)
            return 0
        if verdict == "wedge":
            print(f"[supervisor] эскалация: batch {batch} завис → следующий уровень", flush=True)
            continue
        # error: процесс упал не из-за wedge — пробуем тот же уровень ещё раз? нет:
        # resume идемпотентен, но повторная ошибка = реальная проблема → к меньшему batch.
        print(f"[supervisor] прогон batch={batch} вышел с ошибкой → следующий уровень", flush=True)
    print("[supervisor] ВСЕ уровни лестницы исчерпаны — требуется ручной разбор", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
