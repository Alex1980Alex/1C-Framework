"""Lightweight progress + heartbeat helper for long-running indexing scripts.

Roadmap 260518 follow-up: при verification фаз 1/2 Late Chunking главный
жалобный паттерн — «процесс висит без feedback» (god-object module → 30+
sliding windows × ~5–15s GPU forward без output между ними). Этот модуль
покрывает все 5 индексных скриптов (`reindex_bsl_qwen3.py`,
`index_framework.py`, `build_call_graph.py`, `build_graph_embeddings.py`,
`load_graph_to_neo4j.py`) единым контрактом:

  1. **Heartbeat thread** — daemon-поток печатает `[hb] ...` каждые
     `heartbeat_interval` секунд, основываясь на актуальном snapshot
     состояния. Гарантирует видимость даже когда работа сидит в одном
     CUDA forward / Neo4j UNWIND / TEI HTTP-вызове на минуту.

  2. **Stage context manager** — `with tracker.stage("embed"): ...` —
     открывает span, при выходе печатает elapsed + emit'ит запись в JSONL.

  3. **Event method** — `tracker.event("sliding_window", win=3, of=39, ...)`
     — discrete event, stdout + JSONL.

  4. **JSONL sink** — append-mode `data/indexing-progress.jsonl`. Один
     record на строку, ts/script/run_id/category/payload — годится для
     `jq` post-mortem.

Design constraints:
  * **No external deps** — только stdlib. Скрипты уже импортируют
    тяжёлые либы (torch, sentence-transformers, neo4j); этот модуль
    должен оставаться cheap-to-import.
  * **Thread-safe state** — `set_state(**kw)` обновляет dict под Lock.
    Heartbeat читает snapshot.
  * **Graceful shutdown** — `stop()` сигналит Event, ждёт join. SIGINT
    тоже триггерит stop через atexit.
  * **Non-TTY friendly** — все вывод через `print(..., flush=True)`,
    без ANSI carriage returns, чтобы nohup/redirect не ломали output.
"""
from __future__ import annotations

import atexit
import json
import os
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

DEFAULT_HEARTBEAT_SECONDS = 10.0
DEFAULT_LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "indexing-progress.jsonl"


def _now_iso() -> str:
    # Local time with TZ offset — easier to correlate with `print()` output
    # than UTC. `time.strftime("%z")` returns `+0300` style; insert `:` for
    # ISO-8601 strictness (some log viewers care).
    tz = time.strftime("%z")
    if tz and len(tz) == 5:
        tz = tz[:3] + ":" + tz[3:]
    return time.strftime("%Y-%m-%dT%H:%M:%S") + tz


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(int(seconds), 60)
    if m < 60:
        return f"{m}m{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m{s:02d}s"


def _short(v: Any, limit: int = 80) -> str:
    s = str(v)
    if len(s) <= limit:
        return s
    return s[: limit - 1] + "…"


class ProgressTracker:
    """Coordinator for stdout + JSONL + background heartbeat.

    Usage pattern:
        tracker = make_tracker("reindex_bsl_qwen3")
        tracker.start()
        tracker.event("startup", n_files=2098)
        with tracker.stage("model_load"):
            embedder = make_embedder(...)
        tracker.set_state(file_idx=i, total_files=n, current=str(fp))
        tracker.event("complete", chunks=37639)
        tracker.stop()
    """

    def __init__(
        self,
        script: str,
        run_id: str | None = None,
        log_path: Path | None = None,
        heartbeat_interval: float = DEFAULT_HEARTBEAT_SECONDS,
        stdout: bool = True,
    ) -> None:
        self.script = script
        self.run_id = run_id or f"{script}-{int(time.time())}-{uuid.uuid4().hex[:6]}"
        self.heartbeat_interval = float(heartbeat_interval)
        self.stdout = stdout

        self.log_path = Path(log_path) if log_path else DEFAULT_LOG_PATH
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            self._jsonl_ok = True
        except OSError:
            self._jsonl_ok = False

        self._t0 = time.perf_counter()
        self._state_lock = threading.Lock()
        self._state: dict[str, Any] = {}
        self._stage_stack: list[tuple[str, float]] = []
        self._stop_event = threading.Event()
        self._hb_thread: threading.Thread | None = None
        self._last_event_at = time.perf_counter()
        self._stopped = False

    # ---- Lifecycle -----------------------------------------------------

    def start(self) -> "ProgressTracker":
        if self._hb_thread is not None:
            return self
        self._write_jsonl(category="run_start", payload={"pid": os.getpid()})
        if self.stdout:
            print(
                f"[progress] run_id={self.run_id} script={self.script} "
                f"log={self.log_path.name} hb={self.heartbeat_interval:.0f}s",
                flush=True,
            )
        self._hb_thread = threading.Thread(
            target=self._heartbeat_loop, name=f"hb-{self.script}", daemon=True,
        )
        self._hb_thread.start()
        atexit.register(self._atexit_stop)
        return self

    def stop(self, summary: dict[str, Any] | None = None) -> None:
        if self._stopped:
            return
        self._stopped = True
        self._stop_event.set()
        if self._hb_thread is not None:
            self._hb_thread.join(timeout=self.heartbeat_interval + 2.0)
        elapsed = time.perf_counter() - self._t0
        payload: dict[str, Any] = {"elapsed_s": round(elapsed, 3)}
        if summary:
            payload.update(summary)
        self._write_jsonl(category="run_end", payload=payload)
        if self.stdout:
            tail = f" summary={summary}" if summary else ""
            print(f"[progress] run_end elapsed={_fmt_duration(elapsed)}{tail}", flush=True)

    def _atexit_stop(self) -> None:
        if not self._stopped:
            try:
                self.stop()
            except Exception:
                pass

    # ---- State (thread-safe) -------------------------------------------

    def set_state(self, **kw: Any) -> None:
        with self._state_lock:
            self._state.update(kw)

    def get_state(self) -> dict[str, Any]:
        with self._state_lock:
            return dict(self._state)

    # ---- Events --------------------------------------------------------

    def event(self, name: str, **payload: Any) -> None:
        self._last_event_at = time.perf_counter()
        self._write_jsonl(category="event", payload={"name": name, **payload})
        if self.stdout:
            extra = " ".join(f"{k}={_short(v)}" for k, v in payload.items())
            elapsed = _fmt_duration(time.perf_counter() - self._t0)
            print(f"[evt {elapsed}] {name} {extra}".rstrip(), flush=True)

    @contextmanager
    def stage(self, name: str, **start_payload: Any) -> Iterator[None]:
        t_in = time.perf_counter()
        self._stage_stack.append((name, t_in))
        self.set_state(stage=name)
        self._write_jsonl(category="stage_start", payload={"name": name, **start_payload})
        if self.stdout:
            elapsed = _fmt_duration(t_in - self._t0)
            extra = " ".join(f"{k}={_short(v)}" for k, v in start_payload.items())
            print(f"[stage {elapsed}] {name} START {extra}".rstrip(), flush=True)
        ok = True
        err_msg = ""
        try:
            yield
        except BaseException as exc:
            ok = False
            err_msg = f"{type(exc).__name__}: {exc}"[:240]
            raise
        finally:
            t_out = time.perf_counter()
            self._stage_stack.pop()
            if self._stage_stack:
                self.set_state(stage=self._stage_stack[-1][0])
            else:
                self.set_state(stage=None)
            dur = t_out - t_in
            self._write_jsonl(
                category="stage_end",
                payload={"name": name, "elapsed_s": round(dur, 3), "ok": ok, "err": err_msg or None},
            )
            if self.stdout:
                tag = "DONE" if ok else "FAIL"
                tail = f" err={err_msg}" if not ok else ""
                print(
                    f"[stage {_fmt_duration(t_out - self._t0)}] {name} {tag} "
                    f"in {_fmt_duration(dur)}{tail}",
                    flush=True,
                )

    # ---- Heartbeat -----------------------------------------------------

    def _heartbeat_loop(self) -> None:
        while not self._stop_event.wait(self.heartbeat_interval):
            try:
                self._emit_heartbeat()
            except Exception:
                # Heartbeat must never crash the worker. Swallow.
                pass

    def _emit_heartbeat(self) -> None:
        elapsed = time.perf_counter() - self._t0
        idle = time.perf_counter() - self._last_event_at
        state = self.get_state()
        bits = [f"elapsed={_fmt_duration(elapsed)}", f"idle={_fmt_duration(idle)}"]
        if state.get("stage"):
            bits.append(f"stage={state['stage']}")
        for k in ("file_idx", "total_files", "chunks_done", "windows_done", "windows_total"):
            v = state.get(k)
            if v is not None:
                bits.append(f"{k}={v}")
        if state.get("current"):
            bits.append(f"current={_short(state['current'])}")
        self._write_jsonl(
            category="heartbeat",
            payload={"elapsed_s": round(elapsed, 3), "idle_s": round(idle, 3), **state},
        )
        if self.stdout:
            print(f"[hb] {' '.join(bits)}", flush=True)

    # ---- JSONL sink ----------------------------------------------------

    def _write_jsonl(self, category: str, payload: dict[str, Any]) -> None:
        if not self._jsonl_ok:
            return
        rec = {
            "ts": _now_iso(),
            "run_id": self.run_id,
            "script": self.script,
            "category": category,
            "elapsed_s": round(time.perf_counter() - self._t0, 3),
            **payload,
        }
        try:
            line = json.dumps(rec, ensure_ascii=False, default=str)
            with self.log_path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
                fh.flush()
        except OSError:
            self._jsonl_ok = False


class _NoopTracker(ProgressTracker):
    """Drop-in no-op for INDEXING_NO_PROGRESS=1 (tests / quiet mode)."""

    def __init__(self, script: str) -> None:
        # Bypass parent __init__ — no files, no threads.
        self.script = script
        self.run_id = "noop"
        self.heartbeat_interval = 0.0
        self.stdout = False
        self._jsonl_ok = False
        self._t0 = time.perf_counter()
        self._state_lock = threading.Lock()
        self._state = {}
        self._stage_stack = []
        self._stop_event = threading.Event()
        self._hb_thread = None
        self._last_event_at = self._t0
        self._stopped = True
        # Use a fixed sentinel log_path so external code reading
        # tracker.log_path doesn't NPE.
        self.log_path = DEFAULT_LOG_PATH

    def start(self) -> "ProgressTracker":
        return self

    def stop(self, summary: dict[str, Any] | None = None) -> None:
        return

    def event(self, name: str, **payload: Any) -> None:
        return

    @contextmanager
    def stage(self, name: str, **start_payload: Any) -> Iterator[None]:
        yield

    def set_state(self, **kw: Any) -> None:
        return


def make_tracker(
    script: str,
    *,
    run_id: str | None = None,
    log_path: Path | None = None,
    heartbeat_interval: float | None = None,
) -> ProgressTracker:
    """Convenience constructor that honors env overrides.

    Env vars (set by CI / pipeline orchestrators):
      INDEXING_RUN_ID       — overrides run_id (correlate scripts in one pipeline).
      INDEXING_LOG_PATH     — overrides JSONL sink path.
      INDEXING_HEARTBEAT_S  — overrides heartbeat interval (float seconds).
      INDEXING_NO_PROGRESS  — non-empty → returns _NoopTracker.
    """
    if os.environ.get("INDEXING_NO_PROGRESS"):
        return _NoopTracker(script)
    if run_id is None:
        run_id = os.environ.get("INDEXING_RUN_ID") or None
    if log_path is None:
        env_path = os.environ.get("INDEXING_LOG_PATH")
        if env_path:
            log_path = Path(env_path)
    if heartbeat_interval is None:
        env_hb = os.environ.get("INDEXING_HEARTBEAT_S")
        if env_hb:
            try:
                heartbeat_interval = float(env_hb)
            except ValueError:
                heartbeat_interval = None
    return ProgressTracker(
        script=script,
        run_id=run_id,
        log_path=log_path,
        heartbeat_interval=heartbeat_interval or DEFAULT_HEARTBEAT_SECONDS,
    )


if __name__ == "__main__":
    # Smoke test runnable via `python scripts/_progress.py` — emits a few
    # stages and lets the heartbeat fire so callers can inspect the JSONL.
    tr = make_tracker("self_test", heartbeat_interval=2.0)
    tr.start()
    tr.event("startup", note="smoke")
    with tr.stage("phase_a", n_items=5):
        for i in range(5):
            tr.set_state(file_idx=i, total_files=5, current=f"item-{i}")
            time.sleep(1.0)
    with tr.stage("phase_b"):
        time.sleep(3.0)
    tr.event("complete", items=5)
    tr.stop(summary={"items": 5})
    print(f"\nJSONL written to: {tr.log_path}")
    sys.exit(0)
