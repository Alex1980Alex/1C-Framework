#!/usr/bin/env python3
"""ADR-022 P2 — opt-in включение нативной OpenTelemetry Claude Code (точная телеметрия инструментов).

Пишет OTel-переменные в `env`-блок `.claude/settings.local.json` (gitignored, per-user) — team
`settings.json` НЕ трогается. Реверсивно (`--disable` убирает РОВНО добавленные ключи). stdlib-only.

Режимы:
  --console                 экспорт в console (stderr), zero-infra — проверить, что эмиссия работает
  --otlp <ENDPOINT>         экспорт по OTLP (http/protobuf) в коллектор/Langfuse/SigNoz
      [--public-key K --secret-key S]   Langfuse Basic-auth header (Authorization)
      [--headers "k=v,k2=v2"]           произвольные OTLP-заголовки (альтернатива ключам)
  --disable                 убрать все OTel-ключи (opt-out)
  --status                  показать текущее состояние OTel-env

  --settings <PATH>         целевой файл (по умолчанию .claude/settings.local.json) — для тестов
  --content                 включить логирование args/result/prompt (по умолчанию OFF — PII/секреты)

После изменения — перезапустить `claude` (env читается при старте). См. how-to:
docs/framework documentation/42_MONITOR_CI/42.8_Claude_Code_OTel_Tool_Telemetry.md
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SETTINGS = ROOT / ".claude" / "settings.local.json"

# Ключи, которыми управляет этот скрипт (disable убирает РОВНО их — не трогая чужой env).
_BASE_KEYS = [
    "CLAUDE_CODE_ENABLE_TELEMETRY",
    "CLAUDE_CODE_ENHANCED_TELEMETRY_BETA",
    "OTEL_METRICS_EXPORTER",
    "OTEL_LOGS_EXPORTER",
    "OTEL_TRACES_EXPORTER",
]
_OTLP_KEYS = [
    "OTEL_EXPORTER_OTLP_PROTOCOL",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_HEADERS",
]
_CONTENT_KEYS = [
    "OTEL_LOG_USER_PROMPTS",
    "OTEL_LOG_TOOL_DETAILS",
    "OTEL_LOG_TOOL_CONTENT",
]
_MANAGED = _BASE_KEYS + _OTLP_KEYS + _CONTENT_KEYS


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")) or {}
    except (ValueError, OSError) as e:
        print(f"ERROR: не прочитать {path}: {e}", file=sys.stderr)
        sys.exit(2)


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():  # бэкап перед мутацией
        bak = path.with_suffix(path.suffix + ".bak")
        bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _enabled_env(args) -> dict[str, str]:
    """Собрать OTel-env по режиму."""
    env = {
        "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
        "CLAUDE_CODE_ENHANCED_TELEMETRY_BETA": "1",  # traces (spans claude_code.tool.execution)
    }
    if args.console:
        env["OTEL_METRICS_EXPORTER"] = "console"
        env["OTEL_LOGS_EXPORTER"] = "console"
        env["OTEL_TRACES_EXPORTER"] = "console"
    else:  # otlp
        for k in ("OTEL_METRICS_EXPORTER", "OTEL_LOGS_EXPORTER", "OTEL_TRACES_EXPORTER"):
            env[k] = "otlp"
        env["OTEL_EXPORTER_OTLP_PROTOCOL"] = "http/protobuf"
        env["OTEL_EXPORTER_OTLP_ENDPOINT"] = args.otlp
        if args.public_key and args.secret_key:
            token = base64.b64encode(f"{args.public_key}:{args.secret_key}".encode()).decode()
            env["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {token}"
        elif args.headers:
            env["OTEL_EXPORTER_OTLP_HEADERS"] = args.headers
    if args.content:  # PII/секреты — только по явному запросу
        env["OTEL_LOG_USER_PROMPTS"] = "1"
        env["OTEL_LOG_TOOL_DETAILS"] = "1"
        env["OTEL_LOG_TOOL_CONTENT"] = "1"
    return env


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows cp1251: безопасный вывод кириллицы/символов
    except Exception:
        pass
    p = argparse.ArgumentParser(description="ADR-022 P2: opt-in OTel Claude Code")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--console", action="store_true", help="экспорт в console (zero-infra)")
    mode.add_argument("--otlp", metavar="ENDPOINT", help="OTLP-эндпоинт (Langfuse/SigNoz/collector)")
    mode.add_argument("--disable", action="store_true", help="убрать OTel-env (opt-out)")
    mode.add_argument("--status", action="store_true", help="показать текущее состояние")
    p.add_argument("--public-key")
    p.add_argument("--secret-key")
    p.add_argument("--headers")
    p.add_argument("--content", action="store_true", help="логировать args/result/prompt (PII!)")
    p.add_argument("--settings", default=str(DEFAULT_SETTINGS))
    args = p.parse_args(argv)

    path = Path(args.settings)
    data = _load(path)
    env = data.get("env") or {}

    if args.status:
        cur = {k: env[k] for k in _MANAGED if k in env}
        out = sys.stdout.buffer
        out.write((json.dumps(cur, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
        out.write(f"OTel: {'ВКЛ' if env.get('CLAUDE_CODE_ENABLE_TELEMETRY') == '1' else 'выкл'} ({path})\n".encode())
        return 0

    if args.disable:
        for k in _MANAGED:
            env.pop(k, None)
        data["env"] = env
        _save(path, data)
        print(f"OTel выключен (убрано {len(_MANAGED)} ключей при наличии) -> {path}. Перезапусти claude.")
        return 0

    # console / otlp
    env.update(_enabled_env(args))
    data["env"] = env
    _save(path, data)
    where = "console" if args.console else f"otlp -> {args.otlp}"
    print(f"OTel включён ({where}) -> {path}. Перезапусти claude. Контент: "
          f"{'ON' if args.content else 'OFF (без PII)'}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
