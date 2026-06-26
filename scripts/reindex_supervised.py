#!/usr/bin/env python3
"""Part B (ADR-038): супервизор устойчивого ERP-reindex.

Запускает `reindex_bsl_qwen3.py` (resume) и следит за РОСТОМ числа точек в коллекции
(реальный индекс-выход). Если индекс не растёт дольше STALL_LIMIT — убивает дерево
процессов и перезапускает с МЕНЬШИМ batch (лестница 32->8->1). `--skip-indexed`
сохраняет прогресс; малый буфер на низком batch => частые флаши.

Почему по росту points, а НЕ по heartbeat-idle: idle обновляется по смене файла/флашу,
и при batch=1 один тяжёлый файл (или один флаш большого буфера) легитимно идёт >20мин ->
idle давал ЛОЖНЫЙ wedge и убивал рабочий прогон (наблюдалось: points росли 186879->199679,
а супервизор трижды убил по idle>1200s). Рост points = индекс реально пишется -> надёжный
liveness. Буфер уменьшается на низком batch, чтобы рост points был частым даже при batch=1.

Почему батч-эскалация, а не poison-by-path: буфер копит чанки нескольких файлов, атрибуция
нечёткая; resume + меньший batch проще и надёжнее. Part A (`--long-batch1-tokens`) снимает
почти все зависания заранее — супервизор тут страховочная сетка.

Запуск (resume — продолжить существующую коллекцию):
  python scripts/reindex_supervised.py --project <ABS> --collection bsl_code_erp_ref \
      --max-file-bytes 2097152 --long-batch1-tokens 1024

Чистый rebuild (--recreate-once: супервизор дропает коллекцию ОДИН раз перед лестницей,
дальше resume создаёт её заново hybrid) — для «переехал корень источника / нужна свежая
коллекция без дублей»:
  python scripts/reindex_supervised.py --project <ABS> --collection bsl_code_erp_ref \
      --recreate-once --max-file-bytes 2097152 --long-batch1-tokens 1024

Идемпотентно: повторный запуск БЕЗ --recreate-once продолжает с того же места (resume).
"""

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Windows: при redirect stdout в файл Python берёт locale-кодировку (cp1251/charmap),
# которая не кодирует часть Юникода -> UnicodeEncodeError рушит супервизор. UTF-8 + replace.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
QDRANT_URL = "http://localhost:6333"

# Макс. секунд БЕЗ роста points = реальный wedge. При batch=1 один флаш малого буфера идёт
# ~1-2мин, поэтому 1500с (25мин) без роста заведомо = зависание, а не медленность.
DEFAULT_STALL_LIMIT = 1500
POLL = 30
BATCH_LADDER = (32, 8, 1)


def _buffer_for(batch: int) -> int:
    """Размер буфера флаша под batch: меньше batch -> меньше буфер -> чаще флаши
    (частый рост points = видимый liveness даже на медленном batch=1)."""
    if batch >= 32:
        return 512
    if batch >= 8:
        return 128
    return 32


def _points_count(collection: str) -> int | None:
    """Точное число точек в коллекции (для детекта роста) или None при ошибке."""
    try:
        req = urllib.request.Request(
            f"{QDRANT_URL}/collections/{collection}/points/count",
            data=json.dumps({"exact": True}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return int(json.load(resp)["result"]["count"])
    except Exception:
        return None


def _drop_collection(collection: str) -> bool:
    """DELETE коллекции для --recreate-once. True = коллекции больше нет (удалена ИЛИ её и
    не было — 404). False = запрос реально не удался (Qdrant недоступен/5xx) → вызывающий
    прерывает прогон, чтобы не свалиться в resume против стэйл-данных."""
    try:
        req = urllib.request.Request(f"{QDRANT_URL}/collections/{collection}", method="DELETE")
        with urllib.request.urlopen(req, timeout=30) as resp:
            json.load(resp)
        return True
    except urllib.error.HTTPError as e:
        return e.code == 404  # уже отсутствует = желаемый итог
    except Exception:
        return False


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


def _build_cmd(args, batch: int, buffer: int) -> list[str]:
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
        "--buffer-size",
        str(buffer),
    ]
    if args.max_file_bytes:
        cmd += ["--max-file-bytes", str(args.max_file_bytes)]
    if args.long_batch1_tokens:
        cmd += ["--long-batch1-tokens", str(args.long_batch1_tokens)]
    return cmd


def run_attempt(args, batch: int, log: Path) -> str:
    """Один прогон reindex под надзором. Вернуть 'ok' | 'wedge' | 'error'.

    Liveness = рост points: если коллекция не растёт дольше stall_limit -> wedge.
    """
    buffer = _buffer_for(batch)
    print(f"[supervisor] старт batch={batch} buffer={buffer} -> log {log.name}", flush=True)
    with log.open("w", encoding="utf-8") as fh:
        proc = subprocess.Popen(
            _build_cmd(args, batch, buffer), stdout=fh, stderr=subprocess.STDOUT
        )
    last_count = _points_count(args.collection) or 0
    last_growth = time.monotonic()
    try:
        while True:
            time.sleep(POLL)
            rc = proc.poll()
            if rc is not None:
                return "ok" if rc == 0 else "error"
            cnt = _points_count(args.collection)
            if cnt is not None and cnt > last_count:
                last_count = cnt
                last_growth = time.monotonic()
            stalled = time.monotonic() - last_growth
            if stalled > args.stall_limit:
                print(
                    f"[supervisor] STALL: points не растут {stalled:.0f}s > {args.stall_limit}s "
                    f"@ batch={batch} (count={last_count}) -> kill",
                    flush=True,
                )
                _kill_tree(proc)
                return "wedge"
    except KeyboardInterrupt:
        _kill_tree(proc)
        raise


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Part B (ADR-038) supervised reindex")
    ap.add_argument("--project", required=True, help="ABS project root (для resume-match)")
    ap.add_argument("--collection", required=True)
    ap.add_argument("--max-file-bytes", type=int, default=0)
    ap.add_argument("--long-batch1-tokens", type=int, default=1024)
    ap.add_argument(
        "--recreate-once",
        action="store_true",
        help="Дроп коллекции ОДИН раз перед лестницей (чистый rebuild без дублей, напр. после "
        "переезда корня источника); дальше resume пересоздаёт её hybrid. Без флага — обычный resume.",
    )
    ap.add_argument(
        "--stall-limit",
        type=int,
        default=DEFAULT_STALL_LIMIT,
        help="макс. секунд без роста points -> wedge (default 1500)",
    )
    ap.add_argument(
        "--ladder",
        default=",".join(map(str, BATCH_LADDER)),
        help="batch-эскалация через запятую (default 32,8,1)",
    )
    args = ap.parse_args(argv)

    ladder = [int(x) for x in args.ladder.split(",") if x.strip()]
    if not ladder:
        print("ERROR: --ladder must contain at least one batch value", flush=True)
        return 1
    logdir = ROOT / "logs"
    logdir.mkdir(parents=True, exist_ok=True)

    # --recreate-once: дроп коллекции ОДИН раз ДО лестницы (детерминированно, в супервизоре —
    # не зависим от того, дойдёт ли дочерний reindex до своего create_collection). Дальше все
    # прогоны лестницы — обычный resume; дочерний создаст коллекцию заново hybrid (layout=absent
    # + --enable-sparse). Дроп не удался (Qdrant down) → ПРЕРЫВАЕМ, чтобы не уйти в resume против
    # стэйл-данных (иначе тихо нарушили бы контракт «чистый rebuild»).
    if args.recreate_once:
        _before = _points_count(args.collection)
        if not _drop_collection(args.collection):
            print(
                f"[supervisor] --recreate-once: не удалось дропнуть '{args.collection}' "
                "(Qdrant недоступен?) — ПРЕРЫВАЮ, чтобы не уйти в resume против стэйл-данных.",
                flush=True,
            )
            return 1
        print(
            f"[supervisor] --recreate-once: коллекция '{args.collection}' дропнута "
            f"(было {_before if _before is not None else '—'} точек) → дочерний создаст hybrid заново",
            flush=True,
        )

    for batch in ladder:
        log = logdir / f"reindex_supervised_b{batch}.out.log"
        verdict = run_attempt(args, batch, log)
        if verdict == "ok":
            print(f"[supervisor] ГОТОВО — reindex завершён успешно (batch={batch})", flush=True)
            return 0
        if verdict == "wedge":
            print(f"[supervisor] эскалация: batch {batch} застрял -> следующий уровень", flush=True)
            continue
        print(f"[supervisor] прогон batch={batch} вышел с ошибкой -> следующий уровень", flush=True)
    print("[supervisor] ВСЕ уровни лестницы исчерпаны — требуется ручной разбор", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
