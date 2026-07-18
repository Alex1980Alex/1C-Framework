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
import urllib.error
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


def _http_reachable(url: str, timeout: float) -> tuple[bool, int, str]:
    """Reachability: ЛЮБОЙ HTTP-ответ (вкл. 401/403/404) = сервер жив (для 1С-веб-
    публикаций — они отвечают 401/OData-доком, не 200). Down только connection
    refused / timeout (URLError без code). N-P2.1."""
    start = time.monotonic()
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout):
            pass  # with закрывает fd (без утечки при частых пробах)
        return True, int((time.monotonic() - start) * 1000), ""
    except urllib.error.HTTPError as exc:  # получили ответ (4xx/5xx) → достижим
        return True, int((time.monotonic() - start) * 1000), f"HTTP {exc.code}"
    except Exception as exc:  # URLError/timeout/refused → недостижим
        return False, int((time.monotonic() - start) * 1000), f"{type(exc).__name__}: {exc}"[:200]


def _load_1c_instances() -> list[tuple[str, str]]:
    """(server-name, MCP_ONEC_URL) для всех 1c-mcp-crud* из .mcp.json (N-P2.1).
    Пусто при отсутствии/ошибке — проба 1С опциональна."""
    try:
        cfg = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    servers = cfg.get("mcpServers") or {}
    out: list[tuple[str, str]] = []
    for name, sc in servers.items():
        if not name.startswith("1c-mcp-crud"):
            continue
        url = (sc.get("env") or {}).get("MCP_ONEC_URL", "").strip()
        if url:
            out.append((name, url))
    return out


def _dir_writable(path: Path) -> tuple[bool, int, str]:
    """RW-проба каталога (skill-learning silo): создать+удалить пробный файл."""
    start = time.monotonic()
    if not path.exists():
        return False, 0, "dir missing"
    try:
        probe = path / ".health-probe.tmp"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True, int((time.monotonic() - start) * 1000), ""
    except OSError as exc:
        return False, int((time.monotonic() - start) * 1000), f"{type(exc).__name__}: {exc}"[:200]


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

    # core-зависимости выше = severity broken (down → сервер не работает).
    for p in probes:
        p.setdefault("severity", "broken")

    # 5. skill-learning — RW-доступность JSONL-силоса (severity broken)
    sl_dir = ROOT / "data" / "skill_learning"
    ok, latency_ms, error = _dir_writable(sl_dir)
    probes.append(
        {
            "target": "skill-learning",
            "kind": "fs",
            "endpoint": str(sl_dir),
            "ok": ok,
            "latency_ms": latency_ms,
            "error": error,
            "affects": ["skill-learning"],
            "severity": "broken",
        }
    )

    # 6. 1C-инстансы (N-P2.1) — reachability 1С-веб-публикаций из .mcp.json.
    # severity=degraded: dev-инфобазы легитимно то вверх/вниз → advisory (без авто-задачи),
    # но ≥2д непрерывного down всё равно всплывёт в баннере. Opt-out: MCP_PROBE_1C_DISABLE=1.
    if os.environ.get("MCP_PROBE_1C_DISABLE") != "1":
        for name, url in _load_1c_instances():
            ok, latency_ms, error = _http_reachable(url, timeout)
            probes.append(
                {
                    "target": name,
                    "kind": "http",
                    "endpoint": url,
                    "ok": ok,
                    "latency_ms": latency_ms,
                    "error": error,
                    "affects": [name],
                    "severity": "degraded",
                }
            )

    # 7. Langfuse (260718 H-P2, opt-in дашборд). Пробим ТОЛЬКО если .env.otel есть
    # (юзер настроил стек) — иначе «down» каждую сессию = шум. severity=info: Langfuse
    # не критичен (cross-check H-P3 работает без него; ADR-052). Opt-out MCP_PROBE_LANGFUSE_DISABLE=1.
    if (ROOT / ".env.otel").exists() and os.environ.get("MCP_PROBE_LANGFUSE_DISABLE") != "1":
        url = "http://localhost:3000/api/public/health"
        ok, latency_ms, error = _http_reachable(url, timeout)
        probes.append(
            {
                "target": "langfuse",
                "kind": "http",
                "endpoint": url,
                "ok": ok,
                "latency_ms": latency_ms,
                "error": error,
                "affects": ["langfuse-dashboards", "llm-judge-scores"],
                "severity": "info",
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
            "severity": p.get("severity", "broken"),
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
