"""Аудит покрытия MCP-серверов скиллами/бандлами роутера (surfacing-пробелы).

Проблема (инцидент codepilot1c, ADR-047): MCP-сервер подключён в `.mcp.json`, но у него
нет скилла/бандла в роутере → роутер его НИКОГДА не предлагает; всплывает только когда
уже упёрся в стену. Фаззи-матчинг «имя сервера ↔ keyword бандла» шаткий (obsidian-mcp vs
«obsidian», task-master-ai vs «task-protocol»), поэтому покрытие ведётся **явной картой** —
ground truth (обновляется при добавлении MCP). Аудит флагует серверы, которых в карте НЕТ:
их надо классифицировать (завести скилл+бандл / пометить intentional / dead).

Usage:
  python scripts/audit_mcp_coverage.py           # серверы .mcp.json vs карта; список untriaged
  python scripts/audit_mcp_coverage.py --strict  # exit 1 при untriaged (для CI)
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Явная карта покрытия (ground truth). Значение = как сервер доступен агенту.
#   skill:<name>  — доменный скилл + бандл роутера (surfaced по keyword)
#   via:<skill>   — покрыт другим доменным скиллом (документирован там)
#   variant:<srv> — тот же toolset, что <srv>, другая ИБ (покрыт его скиллом)
#   intentional   — намеренно не в роутере (slash-driven, _unrouted_intentional)
#   infra         — meta-инфраструктура, скилл не нужен
#   dead          — подключён, но не используется (нативная замена) — кандидат на удаление
COVERAGE = {
    "1c-debug": "skill:1c-debug-hmr",
    "1c-debug-hmr": "skill:1c-debug-hmr",
    "1c-mcp-crud": "skill:1c-mcp-crud",
    "1c-mcp-crud-erp": "variant:1c-mcp-crud",
    "1c-mcp-crud-mfm": "variant:1c-mcp-crud",
    "1c-mcp-crud-svetly": "variant:1c-mcp-crud",
    "1c-mcp-crud-trade": "variant:1c-mcp-crud",
    "ast-grep-mcp": "via:bsl-development",
    "auto-documenter": "via:bsl-development",
    "bsl-code-search": "via:bsl-development",
    "bsl-debugger": "via:bsl-development",
    "bsl-platform-context": "via:bsl-development",
    "bsl-semantic-search": "via:bsl-development",
    "codepilot1c": "skill:codepilot1c",
    "edt-mcp": "skill:edt-mcp",
    "framework-search": "skill:framework-search",
    "lazy-mcp": "infra",
    "llm-rotation": "skill:llm-rotation",
    "mcp-onec-test-runner": "via:yaxunit-unit-testing",
    "memory-ai": "skill:memory-unified",
    "memory-orchestrator": "skill:memory-unified",
    "vector-memory": "skill:memory-unified",
    "skill-learning": "skill:memory-unified",
    "obsidian-mcp": "skill:obsidian-vault",
    "openspec-mcp": "intentional",  # slash /opsx:*, _unrouted_intentional
    "pdf-vector-graph": "via:indexing-pipeline",
    "scene-detect": "skill:scene-detect-mcp",
    "task-master-ai": "dead",  # 0 использований в hooks/scripts; нативный TaskCreate
    "whisper": "skill:whisper-transcription",
}


def _mcp_servers() -> set[str]:
    servers: set[str] = set()
    for f in [str(ROOT / ".mcp.json"), *glob.glob(str(ROOT / ".mcp" / "*.json"))]:
        try:
            servers |= set(json.loads(Path(f).read_text(encoding="utf-8")).get("mcpServers", {}))
        except Exception:
            pass
    return servers


def audit() -> dict:
    servers = _mcp_servers()
    covered = set(COVERAGE)
    untriaged = sorted(servers - covered)  # в .mcp.json, но не в карте → классифицировать
    stale = sorted(covered - servers)  # в карте, но сервер убран из .mcp.json
    dead = sorted(s for s in servers if COVERAGE.get(s) == "dead")
    return {"servers": sorted(servers), "untriaged": untriaged, "stale": stale, "dead": dead}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="exit 1 при untriaged")
    args = ap.parse_args()
    a = audit()
    lines = [f"MCP серверов в .mcp.json: {len(a['servers'])}; в карте покрытия: {len(COVERAGE)}"]
    for s in a["servers"]:
        lines.append(f"  {s:24} {COVERAGE.get(s, '*** UNTRIAGED ***')}")
    lines.append("")
    lines.append(
        f"UNTRIAGED (нет в карте — классифицировать: skill+бандл / intentional / dead): {a['untriaged'] or 'нет'}"
    )
    lines.append(f"DEAD (кандидат на удаление из .mcp.json): {a['dead'] or 'нет'}")
    if a["stale"]:
        lines.append(f"STALE (в карте, но нет в .mcp.json — почистить карту): {a['stale']}")
    sys.stdout.buffer.write(("\n".join(lines) + "\n").encode("utf-8"))
    return 1 if (args.strict and a["untriaged"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
