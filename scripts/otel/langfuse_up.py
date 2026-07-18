#!/usr/bin/env python3
"""Оркестратор Langfuse self-host для тяжёлого пути tool-observability (260718 H-P2, ADR-052).

Подъём opt-in дашборд-слоя: генерит секреты в gitignored `.env.otel`, поднимает стек
(6 контейнеров), ждёт health langfuse-web, вычисляет Basic-auth для коллектора и
пересоздаёт коллектор с fan-out на Langfuse (сохраняя file-путь H-P3). stdlib-only.

Команды:
  up      (default)  генерировать секреты → up стек → ждать health → провести коллектор
  down    [--volumes]  остановить стек (--volumes = снести данные); коллектор → базовый
  status               health langfuse-web + список контейнеров стека

Реверс полный: `down --volumes` + пересоздать коллектор без Langfuse-overlay.
Безопасность (ADR-052): все порты на 127.0.0.1, контент OFF, секреты вне git.
"""

from __future__ import annotations

import argparse
import base64
import json
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env.otel"
ENV_EXAMPLE = ROOT / ".env.otel.example"
LF_COMPOSE = ROOT / "docker" / "docker-compose.langfuse.yml"
COLL_BASE = ROOT / "docker" / "docker-compose.otel-collector.yml"
COLL_LF = ROOT / "docker" / "docker-compose.otel-collector.langfuse.yml"
WEB_HEALTH = "http://localhost:3000/api/public/health"

# Секреты, которые генерим при пустом значении (крипто-стойко, НЕ compose-дефолты).
_GEN_HEX32 = ["ENCRYPTION_KEY"]  # ровно 64 hex
_GEN_TOKEN = [
    "SALT",
    "NEXTAUTH_SECRET",
    "REDIS_AUTH",
    "POSTGRES_PASSWORD",
    "CLICKHOUSE_PASSWORD",
    "MINIO_ROOT_PASSWORD",
    "LANGFUSE_INIT_USER_PASSWORD",
]
_GEN_PK = "LANGFUSE_INIT_PROJECT_PUBLIC_KEY"
_GEN_SK = "LANGFUSE_INIT_PROJECT_SECRET_KEY"


def _log(msg: str) -> None:
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def _read_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln:
            continue
        k, _, v = ln.partition("=")
        env[k.strip()] = v.strip()
    return env


def _write_env(path: Path, env: dict[str, str]) -> None:
    lines = ["# Секреты OTel→Langfuse (gitignored, генерит langfuse_up.py). ADR-052.", ""]
    for k, v in env.items():
        lines.append(f"{k}={v}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_env(path: Path = ENV_FILE) -> dict[str, str]:
    """Загрузить/создать .env.otel, догенерировать недостающие секреты."""
    if not path.exists() and ENV_EXAMPLE.exists():
        base = _read_env(ENV_EXAMPLE)
    else:
        base = _read_env(path)
    for k in _GEN_HEX32:
        if not base.get(k):
            base[k] = secrets.token_hex(32)  # 64 hex
    for k in _GEN_TOKEN:
        if not base.get(k):
            base[k] = secrets.token_urlsafe(24)
    if not base.get(_GEN_PK):
        base[_GEN_PK] = "pk-lf-" + secrets.token_hex(16)
    if not base.get(_GEN_SK):
        base[_GEN_SK] = "sk-lf-" + secrets.token_hex(16)
    # sane-дефолты для не-секретных полей, если пусто
    base.setdefault("CLICKHOUSE_USER", "clickhouse")
    base.setdefault("MINIO_ROOT_USER", "minio")
    base.setdefault("LANGFUSE_INIT_ORG_ID", "framework")
    base.setdefault("LANGFUSE_INIT_PROJECT_ID", "tool-observability")
    base.setdefault("LANGFUSE_INIT_USER_EMAIL", "admin@localhost")
    base.setdefault("LANGFUSE_OTLP_ENDPOINT", "http://langfuse-web:3000/api/public/otel")
    # Basic-auth для otlphttp-экспортера коллектора = base64(pk:sk)
    base["LANGFUSE_OTLP_AUTH"] = base64.b64encode(
        f"{base[_GEN_PK]}:{base[_GEN_SK]}".encode()
    ).decode()
    _write_env(path, base)
    return base


def _compose(args: list[str], env_file: bool = True) -> int:
    cmd = ["docker", "compose"]
    if env_file:
        cmd += ["--env-file", str(ENV_FILE)]
    cmd += args
    return subprocess.run(cmd, cwd=str(ROOT)).returncode


def _health_ok(url: str = WEB_HEALTH, timeout: float = 5.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError):
        return False


def wait_health(retries: int = 60, delay: float = 5.0) -> bool:
    """Ждать health langfuse-web (миграции ClickHouse/Postgres долгие — до ~5 мин)."""
    for i in range(retries):
        if _health_ok():
            return True
        _log(f"  … ждём langfuse-web health ({i + 1}/{retries})")
        time.sleep(delay)
    return False


def cmd_up(recreate_collector: bool = True) -> int:
    ensure_env()
    _log("[1/4] Секреты в .env.otel готовы (gitignored).")
    _log("[2/4] Поднимаю Langfuse-стек (6 контейнеров, ClickHouse-миграции ~минуты)…")
    rc = _compose(["-f", str(LF_COMPOSE), "up", "-d"])
    if rc != 0:
        _log("ОШИБКА: docker compose up Langfuse провалился.")
        return rc
    _log("[3/4] Жду health langfuse-web…")
    if not wait_health():
        _log("⚠ langfuse-web не поднялся за таймаут — проверь `docker logs langfuse-web`.")
        return 1
    _log(f"    Langfuse UI: http://localhost:3000  (login из .env.otel)")
    if recreate_collector:
        _log("[4/4] Пересоздаю коллектор с fan-out на Langfuse (file-путь H-P3 сохраняется)…")
        rc = _compose(
            [
                "-f",
                str(COLL_BASE),
                "-f",
                str(COLL_LF),
                "up",
                "-d",
                "--force-recreate",
            ]
        )
        if rc != 0:
            _log("⚠ коллектор не пересоздан — Langfuse жив, но fan-out не активен.")
            return rc
        _log("    Коллектор форвардит native OTel → Langfuse (+ file-сырец H-P3 цел).")
    else:
        _log("[4/4] Пропущено (--no-collector). Провести вручную — см. ADR-052.")
    _log("ГОТОВО. Claude уже шлёт в коллектор :4318 → рестарт claude не нужен.")
    return 0


def cmd_down(volumes: bool = False) -> int:
    args = ["-f", str(LF_COMPOSE), "down"]
    if volumes:
        args.append("-v")
    rc = _compose(args, env_file=ENV_FILE.exists())
    _log("Langfuse остановлен." + (" Данные снесены (-v)." if volumes else " Данные целы."))
    _log("Верни коллектор на базовый конфиг (без Langfuse-fan-out):")
    _log("  docker compose -f docker/docker-compose.otel-collector.yml up -d --force-recreate")
    return rc


def cmd_status() -> int:
    ok = _health_ok()
    _log(f"langfuse-web health: {'OK (200)' if ok else 'недоступен'} ({WEB_HEALTH})")
    subprocess.run(
        ["docker", "ps", "--filter", "name=langfuse", "--format", "{{.Names}} :: {{.Status}}"]
    )
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser(description="Langfuse self-host orchestrator (260718 H-P2)")
    p.add_argument("action", nargs="?", default="up", choices=["up", "down", "status"])
    p.add_argument("--no-collector", action="store_true", help="не пересоздавать коллектор")
    p.add_argument("--volumes", action="store_true", help="down: снести данные")
    args = p.parse_args(argv)
    if args.action == "up":
        return cmd_up(recreate_collector=not args.no_collector)
    if args.action == "down":
        return cmd_down(volumes=args.volumes)
    return cmd_status()


if __name__ == "__main__":
    raise SystemExit(main())
