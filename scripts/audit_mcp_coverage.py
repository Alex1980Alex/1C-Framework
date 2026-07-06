"""Аудит покрытия MCP-серверов скиллами/бандлами роутера (surfacing-пробелы).

Проблема (инцидент codepilot1c, ADR-047): MCP-сервер подключён в `.mcp.json`, но у него
нет скилла/бандла в роутере → роутер его НИКОГДА не предлагает; всплывает только когда
уже упёрся в стену. Фаззи-матчинг «имя сервера ↔ keyword бандла» шаткий (obsidian-mcp vs
«obsidian», task-master-ai vs «task-protocol»), поэтому покрытие ведётся **явной картой** —
ground truth (обновляется при добавлении MCP). Аудит флагует серверы, которых в карте НЕТ:
их надо классифицировать (skill+бандл / via / intentional / redundant / dead).

Охватывает ОБА уровня: прямые серверы `.mcp.json`/`.mcp/*.json` И on-demand серверы за
прокси lazy-mcp (`infra/lazy-mcp/config/registry.yaml`) — иначе аудит слеп к ~19 proxied
серверам и даёт ложную «всё покрыто». Маркеры карты: skill:<n> (свой скилл+бандл),
via:<skill> (документирован в другом скилле), variant:<srv> (та же toolset, другая ИБ),
intentional (slash/on-demand by design), redundant (дубль нативного/другого MCP — скилл
не нужен), infra (meta-прокси), dead (не сконфигурирован/не используется — кандидат на удаление).

Usage:
  python scripts/audit_mcp_coverage.py           # direct + lazy-mcp vs карта; untriaged/dead/redundant
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
#   redundant     — дубль нативного тула/другого MCP (скилл не нужен, НЕ пробел)
#   infra         — meta-инфраструктура, скилл не нужен
#   dead          — не сконфигурирован/не используется (нативная замена) — кандидат на удаление
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
    # --- lazy-mcp-only (за прокси infra/lazy-mcp, on-demand; не в .mcp.json напрямую) ---
    #   redundant = дублируется нативным тулом/другим MCP → скилл не нужен, НЕ пробел
    "sonarqube": "via:fix-sonar-task",  # ADR-042
    "bsl-semantic-diff": "via:bsl-development",
    "1c-docs-rag": "via:1c-doc-research",
    "context7": "intentional",  # ADR-014 on-demand lazy-load by design
    "unified-memory": "via:memory-unified",
    "mcp-memory-libsql": "redundant",  # alt LibSQL-память; используется memory-orchestrator
    "vector-memory-mcp": "via:memory-unified",
    "skill-learning-mcp": "via:memory-unified",
    "reasoner": "via:bsl-development",  # mcp-reasoner, 3 BSL-стратегии
    "sequential-thinking": "redundant",  # нативное рассуждение / reasoner
    "filesystem": "redundant",  # нативные Read/Write/Glob
    "filesystem-extended": "redundant",
    "brave": "redundant",  # нативный WebSearch
    "github": "redundant",  # gh CLI / ecosystem_scan.py
    "puppeteer": "redundant",  # claude-in-chrome
    "playwright": "redundant",  # claude-in-chrome / its-research
    "chrome-devtools": "redundant",  # claude-in-chrome
    "slack": "dead",  # placeholder-ключ xoxb-xxx (не сконфигурирован)
    "google-maps": "dead",  # placeholder-ключ xxx (не сконфигурирован)
}


def _mcp_servers() -> set[str]:
    servers: set[str] = set()
    main = ROOT / ".mcp.json"
    for f in [str(main), *glob.glob(str(ROOT / ".mcp" / "*.json"))]:
        p = Path(f)
        if not p.exists():
            continue
        try:
            # utf-8-sig терпит BOM (Windows-редакторы); голый utf-8 падает на ведущем
            servers |= set(json.loads(p.read_text(encoding="utf-8-sig")).get("mcpServers", {}))
        except (json.JSONDecodeError, OSError) as e:
            # существующий, но битый файл НЕ глотаем тихо — иначе --strict даёт ложно-зелёный CI
            print(f"WARN: {p.name} не распарсен: {e}", file=sys.stderr)
            if p == main:
                raise SystemExit(f"FATAL: основной .mcp.json не парсится: {e}") from e
    return servers


def _lazy_servers() -> set[str]:
    """Серверы за прокси lazy-mcp (infra/lazy-mcp/config/registry.yaml, on-demand) —
    их нет в .mcp.json напрямую, но агенту они доступны через lazy-mcp execute_tool."""
    reg = ROOT / "infra" / "lazy-mcp" / "config" / "registry.yaml"
    if not reg.exists():
        return set()
    try:
        import yaml

        d = yaml.safe_load(reg.read_text(encoding="utf-8-sig")) or {}
    except Exception as e:
        print(f"WARN: lazy-mcp registry не распарсен: {e}", file=sys.stderr)
        return set()
    out: set[str] = set()
    for cat in (d.get("categories") or {}).values():
        out |= set((cat or {}).get("servers") or {})
    return out


def audit() -> dict:
    direct = _mcp_servers()
    lazy = _lazy_servers()
    allsrv = direct | lazy
    covered = set(COVERAGE)
    return {
        "direct": sorted(direct),
        "lazy": sorted(lazy - direct),  # только-lazy (не дублирующие .mcp.json)
        "untriaged": sorted(allsrv - covered),  # нет в карте → классифицировать
        "stale": sorted(covered - allsrv),  # в карте, но нет ни direct ни lazy
        "dead": sorted(s for s in allsrv if COVERAGE.get(s) == "dead"),
        "redundant": sorted(s for s in allsrv if COVERAGE.get(s) == "redundant"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="exit 1 при untriaged")
    args = ap.parse_args()
    a = audit()
    lines = [
        f"MCP: direct(.mcp.json)={len(a['direct'])} + lazy-mcp-only={len(a['lazy'])}; карта покрытия={len(COVERAGE)}",
        "— direct (.mcp.json) —",
    ]
    lines += [f"  {s:22} {COVERAGE.get(s, '*** UNTRIAGED ***')}" for s in a["direct"]]
    lines.append("— lazy-mcp (on-demand за прокси) —")
    lines += [f"  {s:22} {COVERAGE.get(s, '*** UNTRIAGED ***')}" for s in a["lazy"]]
    lines.append("")
    lines.append(
        f"UNTRIAGED (нет в карте — классифицировать: skill+бандл / via / intentional / redundant / dead): {a['untriaged'] or 'нет'}"
    )
    lines.append(f"DEAD (кандидат на удаление): {a['dead'] or 'нет'}")
    lines.append(
        f"REDUNDANT (дубль нативного/другого MCP; скилл не нужен): {a['redundant'] or 'нет'}"
    )
    if a["stale"]:
        lines.append(f"STALE (в карте, но нет ни direct ни lazy — почистить карту): {a['stale']}")
    sys.stdout.buffer.write(("\n".join(lines) + "\n").encode("utf-8"))
    return 1 if (args.strict and a["untriaged"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
