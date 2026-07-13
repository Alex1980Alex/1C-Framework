"""Проактивный health-probe зависимостей MCP-серверов фреймворка.

P1.2 (B7, roadmap 260713 tool observability): пробим не сами MCP-tools
health_check (их вызывает клиент, а сервера тяжёлые/держат stdio-сессию),
а инфраструктурные зависимости, от которых зависит доступность серверов:
Qdrant (HTTP), TEI (HTTP embed), memory-ai / bsl-code-search (SQLite-файлы).
RDBG (1c-debug*) не пробим — он on-demand, поднимается по запросу.

Результат: append-only лог data/mcp-health.jsonl + сайдкар-снимок
data/reports/tools/_mcp_health.json (последний прогон, для баннеров/дашбордов).
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEALTH_JSONL = ROOT / "data" / "mcp-health.jsonl"
SIDECAR = ROOT / "data" / "reports" / "tools" / "_mcp_health.json"

# Мониторимые MCP-серверы (vector_memory/server.py:208 и др.) читают QDRANT_URL —
# читаем ЕГО первым (фоллбэк на pdf-framework-имя), чтобы пробить тот же адрес, что и они.
QDRANT_URL = os.environ.get(
    "QDRANT_URL", os.environ.get("VECTOR_STORE__QDRANT_URL", "http://localhost:6333")
).rstrip("/")
TEI_URL = os.environ.get("TEI_URL", "http://localhost:8080").rstrip("/")


def _http_ok(url: str, timeout: float, post: dict | None = None) -> tuple[bool, int, str]:
    """GET (post=None) или POST JSON-телом. Не падает — любая ошибка → (False, ms, текст)."""
    start = time.monotonic()
    try:
        if post is None:
            req = urllib.request.Request(url, method="GET")
        else:
            body = json.dumps(post).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=body,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency_ms = int((time.monotonic() - start) * 1000)
            ok = resp.status == 200
            return ok, latency_ms, "" if ok else f"HTTP {resp.status}"
    except Exception as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        return False, latency_ms, f"{type(exc).__name__}: {exc}"[:200]


def _sqlite_ok(path: Path, timeout: float) -> tuple[bool, int, str]:
    """Проверка доступности SQLite-файла в read-only режиме."""
    start = time.monotonic()
    if not path.exists():
        return False, 0, "file missing"
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=timeout)
        try:
            conn.execute("PRAGMA schema_version").fetchone()
        finally:
            conn.close()
        latency_ms = int((time.monotonic() - start) * 1000)
        return True, latency_ms, ""
    except Exception as exc:
        latency_ms = int((time.monotonic() - start) * 1000)
        return False, latency_ms, f"{type(exc).__name__}: {exc}"[:200]


def probe_all(timeout: float = 1.5) -> list[dict]:
    """Пробит 4 инфраструктурные цели, от которых зависят MCP-сервера."""
    probes: list[dict] = []

    # 1. Qdrant — векторное хранилище
    ok, latency_ms, error = _http_ok(f"{QDRANT_URL}/healthz", timeout)
    probes.append(
        {
            "target": "qdrant",
            "kind": "http",
            "endpoint": f"{QDRANT_URL}/healthz",
            "ok": ok,
            "latency_ms": latency_ms,
            "error": error,
            "affects": [
                "vector-memory",
                "bsl-semantic-search",
                "framework-search",
                "pdf-vector-graph",
                "memory-orchestrator(degraded→sqlite)",
            ],
        }
    )

    # 2. TEI — эмбеддинг-сервис
    ok, latency_ms, error = _http_ok(
        f"{TEI_URL}/embed", timeout, post={"inputs": "ping", "truncate": True}
    )
    probes.append(
        {
            "target": "tei",
            "kind": "http",
            "endpoint": f"{TEI_URL}/embed",
            "ok": ok,
            "latency_ms": latency_ms,
            "error": error,
            "affects": ["memory-first-surfacing", "bsl-semantic-search", "prework-similar-code"],
        }
    )

    # 3. memory-ai — эпизодическая БД memory_ai.db (ai_memory/db.py DEFAULT_DB_PATH +
    #    MEMORY_AI_DB_PATH override). НЕ conversations.db — то легаси дропнутой
    #    conversation_memory (2026-06-03), сервер memory-ai её не открывает.
    db_path = Path(os.environ.get("MEMORY_AI_DB_PATH") or ROOT / "data" / "memory_ai.db")
    ok, latency_ms, error = _sqlite_ok(db_path, timeout)
    probes.append(
        {
            "target": "memory-ai",
            "kind": "sqlite",
            "endpoint": str(db_path),
            "ok": ok,
            "latency_ms": latency_ms,
            "error": error,
            "affects": ["memory-ai"],
        }
    )

    # 4. bsl-code-search — SQLite bsl_call_graph.db
    db_path = ROOT / "cache" / "bsl_call_graph.db"
    ok, latency_ms, error = _sqlite_ok(db_path, timeout)
    probes.append(
        {
            "target": "bsl-code-search",
            "kind": "sqlite",
            "endpoint": str(db_path),
            "ok": ok,
            "latency_ms": latency_ms,
            "error": error,
            "affects": ["bsl-code-search"],
        }
    )

    return probes


_JSONL_CAP_BYTES = 2_000_000  # ротация истории проб (append не безграничен, review #7)


def _atomic_write(path: Path, text: str) -> None:
    """Атомарная запись через УНИКАЛЬНЫЙ tmp (mkstemp): фиксированное tmp-имя давало
    гонку двух параллельных SessionStart на Windows — PermissionError всплывал и баннер
    о down молча терялся (adversarial-review 260713 #6)."""
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp", prefix=path.stem + "-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, str(path))
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _rotate_jsonl(path: Path, cap_bytes: int = _JSONL_CAP_BYTES) -> None:
    """Ротация: при превышении cap сохранить новейшую половину (паттерн trace_log)."""
    import tempfile

    try:
        if path.exists() and path.stat().st_size > cap_bytes:
            data = path.read_bytes()[-(cap_bytes // 2) :]
            idx = data.find(b"\n")
            if idx != -1:
                data = data[idx + 1 :]
            fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp", prefix="health-")
            try:
                with os.fdopen(fd, "wb") as fh:
                    fh.write(data)
                os.replace(tmp, str(path))
            except OSError:
                os.unlink(tmp)
                raise
    except OSError:
        pass  # ротация не блокирует пробу


def run(timeout: float = 1.5, now: datetime | None = None) -> dict:
    """Прогоняет все пробы, пишет jsonl-лог + сайдкар-снимок, возвращает сводку."""
    now = now or datetime.now()
    ts = now.isoformat(timespec="seconds")

    probes = probe_all(timeout)
    down = [
        {
            "target": p["target"],
            "endpoint": p["endpoint"],
            "error": p["error"],
            "affects": p["affects"],
        }
        for p in probes
        if not p["ok"]
    ]

    HEALTH_JSONL.parent.mkdir(parents=True, exist_ok=True)
    _rotate_jsonl(HEALTH_JSONL)
    with HEALTH_JSONL.open("a", encoding="utf-8") as fh:
        for p in probes:
            fh.write(json.dumps({"ts": ts, **p}, ensure_ascii=False) + "\n")

    summary = {
        "ts": ts,
        "down": down,
        "total": len(probes),
        "up": len(probes) - len(down),
    }
    _atomic_write(SIDECAR, json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="Health-probe зависимостей MCP-серверов")
    parser.add_argument("--timeout", type=float, default=1.5, help="таймаут одной пробы, сек")
    args = parser.parse_args(argv)

    summary = run(timeout=args.timeout)
    down_targets = [d["target"] for d in summary["down"]] or "нет"
    print(f"mcp-health: up={summary['up']}/{summary['total']} down={down_targets} → {SIDECAR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
