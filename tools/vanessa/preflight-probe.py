#!/usr/bin/env python3
"""
preflight-probe.py — Pre-flight data check for VA BDD tests against 1C TestDB.

Universal, YAML-driven probe engine. Reads probe definitions from
`tools/vanessa/probes/*.yaml` at startup and dispatches METADATA requirements
to the matching probe. To add support for a new configuration object type —
drop a YAML file into probes/ with a `tag:`, `parser:`, and `checks:`; no
Python code changes needed.

METADATA format in .feature files (machine-readable subset):

    # METADATA:
    #   TS: М012УХ (fresh, PLK)
    #   Catalog: Номенклатура[Рапс (Россия), Пшеница 3 кл 13.5% протеин]
    #   Catalog: Контрагенты[Интеграция Агро]
    #   Role: ДоступенДиспетчер
    #   Setting: НастройкаЭлектронногоТабло[ПЛК Светлый/НеПрошедшиеРегистрацию]

The freeform fields (Task, Logical block, Dependencies, ...) that
/write-1c-tests and /run-1c-tests also read coexist in the same METADATA
block — preflight-probe simply ignores lines with unknown tags.

Core engine (parsers + _check_result + run_probe) generated via
mcp__llm-rotation__llm_complete (zai-glm5) per MEMORY Token Economy policy.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# 1C HTTP service endpoint (published as "mcp" on TestDB)
DEFAULT_TOOLKIT_URL = os.environ.get(
    "ONEC_RPC_URL", "http://localhost/TestDB/hs/mcp/rpc"
)
DEFAULT_USERNAME = os.environ.get("ONEC_USERNAME", "a.terletskiy@sodru.com")
DEFAULT_PASSWORD = os.environ.get("ONEC_PASSWORD", "")
HTTP_TIMEOUT = 10

PROBES_DIR = Path(__file__).resolve().parent / "probes"

# ANSI colour helpers (Windows 10+ ENABLE_VIRTUAL_TERMINAL_PROCESSING safe)
_GREEN = "\033[92m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
_CYAN = "\033[96m"
_RESET = "\033[0m"

_rpc_id_counter = itertools.count(1)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    type: str
    name: str
    status: str
    detail: str


@dataclass
class FeatureReport:
    feature: str
    timestamp: str
    checks: list[CheckResult] = field(default_factory=list)
    exit_code: int = 0

    @property
    def summary(self) -> dict:
        ok = sum(1 for c in self.checks if c.status == "OK")
        fail = sum(1 for c in self.checks if c.status == "FAIL")
        skip = sum(1 for c in self.checks if c.status == "SKIP")
        return {"ok": ok, "fail": fail, "skip": skip}

    def recalc_exit_code(self) -> None:
        self.exit_code = 1 if any(c.status == "FAIL" for c in self.checks) else 0

    def to_dict(self) -> dict:
        return {
            "feature": self.feature,
            "timestamp": self.timestamp,
            "checks": [
                {"type": c.type, "name": c.name, "status": c.status, "detail": c.detail}
                for c in self.checks
            ],
            "summary": self.summary,
            "exit_code": self.exit_code,
        }


# ---------------------------------------------------------------------------
# 1C MCP Toolkit communication (JSON-RPC)
# ---------------------------------------------------------------------------

def _rpc_call(
    rpc_url: str,
    auth: tuple[str, str],
    tool_name: str,
    arguments: dict,
) -> Any:
    """Call a 1C MCP tool via JSON-RPC 2.0.

    The 1C HTTP service responds with MCP CallToolResult wrapped in JSON-RPC:
        {"jsonrpc":"2.0","id":N,"result":{"content":[{"type":"text","text":"<inner>"}]}}
    The inner text is itself JSON: {"success": bool, "data"|"error": ...}.
    Returns the unwrapped `data` field.
    """
    rpc_request = {
        "jsonrpc": "2.0",
        "id": next(_rpc_id_counter),
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }

    resp = requests.post(rpc_url, json=rpc_request, auth=auth, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    envelope = resp.json()

    if "error" in envelope:
        err = envelope["error"]
        raise RuntimeError(f"JSON-RPC error {err.get('code')}: {err.get('message')}")

    result = envelope.get("result") or {}
    content = result.get("content") or []
    if not content:
        raise RuntimeError("Empty result from 1C tool")

    text = content[0].get("text", "")
    try:
        inner = json.loads(text)
    except json.JSONDecodeError:
        return text

    if isinstance(inner, dict) and not inner.get("success", True):
        raise RuntimeError(inner.get("error", "Unknown 1C tool error"))

    if isinstance(inner, dict) and "data" in inner:
        return inner["data"]

    return inner


def run_query(
    toolkit_url: str,
    query: str,
    params: dict | None = None,
    auth: tuple[str, str] = (DEFAULT_USERNAME, DEFAULT_PASSWORD),
) -> list:
    """Execute a 1C query via the JSON-RPC endpoint."""
    arguments: dict = {"query": query}
    if params:
        arguments["params"] = params

    data = _rpc_call(toolkit_url, auth, "execute_query", arguments)

    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "rows" in data:
        return data["rows"]
    return []


# ---------------------------------------------------------------------------
# Probe definition loader
# ---------------------------------------------------------------------------

def load_probes(probes_dir: Path) -> dict[str, dict]:
    """Load all *.yaml probe definitions from probes_dir.

    Returns a dict mapping probe tag → probe definition.
    """
    probes: dict[str, dict] = {}
    if not probes_dir.is_dir():
        return probes

    for yaml_path in sorted(probes_dir.glob("*.yaml")):
        try:
            with open(yaml_path, encoding="utf-8") as fh:
                definition = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            print(
                f"{_YELLOW}[WARN]{_RESET} Cannot parse {yaml_path.name}: {exc}",
                file=sys.stderr,
            )
            continue

        if not isinstance(definition, dict):
            continue
        if not definition.get("enabled", True):
            continue
        tag = definition.get("tag")
        if not tag:
            continue
        probes[tag] = definition

    return probes


# ---------------------------------------------------------------------------
# METADATA parser
# ---------------------------------------------------------------------------

def parse_metadata(
    feature_path: str,
    known_tags: set[str],
) -> list[dict]:
    """Parse METADATA section from a .feature file.

    For each line `# <Tag>: <raw>` where Tag is a known probe tag,
    emit a requirement dict {"type": Tag, "raw": raw}. Unknown tags
    (Task, Dependencies, ...) are silently ignored — they belong to
    /write-1c-tests and /run-1c-tests freeform fields.
    """
    requirements: list[dict] = []
    in_metadata = False

    if not known_tags:
        return requirements
    alt = "|".join(re.escape(t) for t in known_tags)
    tag_re = re.compile(rf"^(?P<tag>{alt}):\s*(?P<raw>.+)$", re.IGNORECASE)

    with open(feature_path, encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()

            if line.upper().startswith("# METADATA"):
                in_metadata = True
                continue

            if in_metadata:
                if not line.startswith("#"):
                    if line == "":
                        continue
                    break
                content = line.lstrip("#").strip()
                if not content:
                    continue

                m = tag_re.match(content)
                if not m:
                    continue

                canonical = next(
                    (t for t in known_tags if t.lower() == m.group("tag").lower()),
                    m.group("tag"),
                )
                requirements.append({"type": canonical, "raw": m.group("raw").strip()})

    return requirements


# ---------------------------------------------------------------------------
# Parser adapters — turn a METADATA raw string into a list of check items
# ---------------------------------------------------------------------------

def _parse_csv_with_flags(raw: str, cfg: dict) -> list[dict]:
    """'Name1, Name2 (flag1, flag2)' → [{item, flags}]."""
    flags_regex: str = cfg.get("flags_regex", r"\(([^)]*)\)")
    item_sep: str = cfg.get("item_separator", ",")
    flag_sep: str = cfg.get("flag_separator", ",")

    global_flags: set[str] = set()
    m_global = re.search(flags_regex, raw)
    if m_global:
        global_flags = {
            f.strip().lower()
            for f in m_global.group(1).split(flag_sep)
            if f.strip()
        }
        raw = (raw[: m_global.start()] + raw[m_global.end():]).strip()

    results: list[dict] = []
    for part in raw.split(item_sep):
        part = part.strip()
        if not part:
            continue
        results.append({"item": part, "flags": set(global_flags)})
    return results


def _parse_bracketed_list(raw: str, cfg: dict) -> list[dict]:
    """'Catalog[item1, item2]' → [{catalog, item, flags: set()}]."""
    pattern: str = cfg.get("pattern", r"^(?P<catalog>\S+)\[(?P<items>.+)\]$")
    item_sep: str = cfg.get("item_separator", ",")

    m = re.match(pattern, raw.strip())
    if not m:
        return []
    catalog = m.group("catalog")
    items_str = m.group("items")
    results: list[dict] = []
    for item in items_str.split(item_sep):
        item = item.strip()
        if item:
            results.append({"catalog": catalog, "item": item, "flags": set()})
    return results


def _parse_bracketed_slashed(raw: str, cfg: dict) -> list[dict]:
    """'Name[Point/Kind]' → [{name, point, kind, item: raw, flags: set()}]."""
    pattern: str = cfg.get(
        "pattern",
        r"^(?P<name>\S+)\[(?P<point>[^/]+)/(?P<kind>[^\]]+)\]$",
    )
    m = re.match(pattern, raw.strip())
    if not m:
        return []
    return [
        {
            "name": m.group("name"),
            "point": m.group("point"),
            "kind": m.group("kind"),
            "item": raw.strip(),
            "flags": set(),
        }
    ]


def _parse_literal(raw: str, cfg: dict) -> list[dict]:
    """Whole raw string is one item."""
    del cfg  # unused — signature required for registry protocol
    val = raw.strip()
    return [{"item": val, "literal": val, "flags": set()}]


_PARSER_REGISTRY: dict[str, Callable[[str, dict], list[dict]]] = {
    "csv_with_flags": _parse_csv_with_flags,
    "bracketed_list": _parse_bracketed_list,
    "bracketed_slashed": _parse_bracketed_slashed,
    "literal": _parse_literal,
}


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------

def _render_template(template: str, context: dict) -> str:
    """Replace {key} placeholders with values from context dict."""
    def _replacer(m: re.Match) -> str:
        return str(context.get(m.group(1), m.group(0)))
    return re.sub(r"\{(\w+)\}", _replacer, template)


def _render_params(params_cfg: dict | None, context: dict) -> dict:
    if not params_cfg:
        return {}
    return {k: _render_template(str(v), context) for k, v in params_cfg.items()}


# ---------------------------------------------------------------------------
# Check evaluator
# ---------------------------------------------------------------------------

def _check_result(
    rows: list[dict],
    check_cfg: dict,
    context: dict,
) -> tuple[bool, str, dict]:
    """Evaluate one check against query rows.

    Returns (passed, rendered_detail, merged_context).
    """
    expect: str = check_cfg.get("expect", "non_empty")
    expect_field: str | None = check_cfg.get("expect_field")

    # Merge first-row fields into context so templates like {Active} resolve
    ctx = dict(context)
    if rows:
        ctx.update(rows[0])

    passed: bool = False

    if expect == "non_empty":
        passed = len(rows) > 0

    elif expect == "field_truthy":
        if rows:
            val = rows[0].get(expect_field)
            passed = bool(val)

    elif expect == "field_positive":
        if rows:
            val = rows[0].get(expect_field)
            try:
                passed = int(val) > 0 if val is not None else False
            except (ValueError, TypeError):
                passed = False

    elif expect == "field_zero":
        if rows:
            val = rows[0].get(expect_field)
            try:
                passed = int(val if val is not None else 0) == 0
            except (ValueError, TypeError):
                passed = False
        else:
            passed = True  # no rows → field is effectively zero

    elif expect == "field_equals":
        if rows:
            expected_val = check_cfg.get("expect_value")
            passed = rows[0].get(expect_field) == expected_val

    if passed:
        label = _render_template(check_cfg.get("on_pass_label", ""), ctx)
        return True, label, ctx
    else:
        fail_msg = _render_template(
            check_cfg.get("on_fail", "check failed"), ctx
        )
        return False, fail_msg, ctx


# ---------------------------------------------------------------------------
# Probe runner
# ---------------------------------------------------------------------------

def run_probe(
    toolkit_url: str,
    probe_def: dict,
    raw: str,
    run_query_fn: Callable[..., list[dict]] = run_query,
) -> list[CheckResult]:
    """Execute one probe definition against a raw METADATA value."""
    results: list[CheckResult] = []

    tag: str = probe_def.get("tag", "UNKNOWN")
    parser_cfg: dict = probe_def.get("parser", {}) or {}
    checks: list[dict] = probe_def.get("checks", []) or []
    default_status: str = (probe_def.get("default_status") or "SKIP").upper()
    default_message: str = probe_def.get("default_message", "skipped")

    parser_type: str = parser_cfg.get("type", "literal")
    parser_fn = _PARSER_REGISTRY.get(parser_type, _parse_literal)
    parsed_items: list[dict] = parser_fn(raw, parser_cfg)

    if not parsed_items:
        results.append(CheckResult(tag, raw, "SKIP", "cannot parse expression"))
        return results

    item_label_tpl: str = parser_cfg.get("item_label", "{item}")

    # No checks at all → emit default_status (e.g. Role probe defaults to SKIP)
    if not checks:
        for parsed in parsed_items:
            display_name = _render_template(item_label_tpl, parsed)
            results.append(
                CheckResult(tag, display_name, default_status, default_message)
            )
        return results

    for parsed in parsed_items:
        context: dict[str, Any] = {
            k: v for k, v in parsed.items() if k != "flags"
        }
        display_name: str = _render_template(item_label_tpl, context)
        flags: set[str] = parsed.get("flags", set())

        pass_labels: list[str] = []
        failed: bool = False

        for check in checks:
            if check.get("always"):
                should_run = True
            elif "if_flag" in check:
                required_flag = str(check["if_flag"]).lower()
                should_run = required_flag in flags
            else:
                should_run = False

            if not should_run:
                continue

            query: str = _render_template(check.get("query", ""), context)
            params: dict = _render_params(check.get("params"), context)

            try:
                rows = run_query_fn(toolkit_url, query, params)
            except Exception as exc:
                results.append(
                    CheckResult(tag, display_name, "FAIL", f"query error: {exc}")
                )
                failed = True
                break

            ok, detail, ctx = _check_result(rows, check, context)
            context = ctx

            if not ok:
                results.append(CheckResult(tag, display_name, "FAIL", detail))
                failed = True
                break

            if detail:
                pass_labels.append(detail)

        if not failed:
            results.append(
                CheckResult(
                    tag,
                    display_name,
                    "OK",
                    ", ".join(pass_labels) if pass_labels else "ok",
                )
            )

    return results


# ---------------------------------------------------------------------------
# Feature checking orchestrator
# ---------------------------------------------------------------------------

def check_feature(
    feature_path: str,
    toolkit_url: str,
    probes: dict[str, dict],
) -> FeatureReport:
    """Run all pre-flight probes for a single feature file."""
    report = FeatureReport(
        feature=os.path.basename(feature_path),
        timestamp=datetime.now(UTC).isoformat(),
    )

    print(f"{_CYAN}[preflight]{_RESET} feature: {report.feature}")

    requirements = parse_metadata(feature_path, set(probes.keys()))
    if not requirements:
        print(f"  {_YELLOW}No machine-readable METADATA — skipping checks{_RESET}")
        report.checks.append(
            CheckResult("Meta", report.feature, "OK", "no probes in METADATA (back-compat)")
        )
        report.recalc_exit_code()
        return report

    for req in requirements:
        probe_def = probes.get(req["type"])
        if not probe_def:
            report.checks.append(
                CheckResult(req["type"], req["raw"], "SKIP", "unknown probe tag")
            )
            continue
        report.checks.extend(run_probe(toolkit_url, probe_def, req["raw"]))

    for c in report.checks:
        if c.status == "OK":
            tag = f"{_GREEN}[OK]{_RESET}  "
        elif c.status == "FAIL":
            tag = f"{_RED}[FAIL]{_RESET}"
        else:
            tag = f"{_YELLOW}[SKIP]{_RESET}"
        print(f"  {tag}  {c.type:<8s} {c.name} — {c.detail}")

    summary = report.summary
    print("  ---")
    print(
        f"  Result: {_RED}{summary['fail']} BLOCKER{_RESET}, "
        f"{_GREEN}{summary['ok']} OK{_RESET}, "
        f"{_YELLOW}{summary['skip']} SKIP{_RESET}"
    )

    report.recalc_exit_code()
    return report


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pre-flight data check for VA BDD tests against 1C TestDB"
    )
    parser.add_argument(
        "--feature",
        default=None,
        help="Path to a single .feature file or directory; omit to scan features/",
    )
    parser.add_argument(
        "--toolkit-url",
        default=DEFAULT_TOOLKIT_URL,
        help=f"1C HTTP service JSON-RPC endpoint (default: {DEFAULT_TOOLKIT_URL})",
    )
    parser.add_argument(
        "--probes-dir",
        default=str(PROBES_DIR),
        help=f"Directory with probe YAML definitions (default: {PROBES_DIR})",
    )
    parser.add_argument(
        "--json",
        default=None,
        dest="json_path",
        help="Path to write structured JSON result for run-bdd.ps1 integration",
    )
    args = parser.parse_args()

    toolkit_url: str = args.toolkit_url
    probes_dir = Path(args.probes_dir)

    probes = load_probes(probes_dir)
    if not probes:
        print(
            f"{_YELLOW}[WARN]{_RESET} No probe definitions found in {probes_dir}",
            file=sys.stderr,
        )
    else:
        print(
            f"{_CYAN}[preflight]{_RESET} loaded probes: "
            + ", ".join(sorted(probes.keys()))
        )

    # Verify toolkit is reachable via a cheap ping query
    try:
        _rpc_call(
            toolkit_url,
            (DEFAULT_USERNAME, DEFAULT_PASSWORD),
            "execute_code",
            {"code": 'Результат = "ping";'},
        )
    except requests.ConnectionError:
        print(
            f"{_RED}[ERROR]{_RESET} Cannot reach 1C HTTP service at {toolkit_url}",
            file=sys.stderr,
        )
        sys.exit(2)
    except Exception as exc:
        print(
            f"{_RED}[ERROR]{_RESET} 1C HTTP service ping failed: {exc}",
            file=sys.stderr,
        )
        sys.exit(2)

    feature_files: list[str] = []

    if args.feature:
        p = Path(args.feature)
        if not p.exists():
            print(f"{_RED}[ERROR]{_RESET} Feature file not found: {args.feature}", file=sys.stderr)
            sys.exit(2)
        if p.is_file():
            feature_files.append(str(p))
        elif p.is_dir():
            feature_files.extend(
                str(f) for f in sorted(p.rglob("*.feature")) if ".off" not in f.name
            )
    else:
        features_dir = Path("features")
        if not features_dir.is_dir():
            print(
                f"{_RED}[ERROR]{_RESET} features/ directory not found and --feature not specified",
                file=sys.stderr,
            )
            sys.exit(2)
        feature_files.extend(
            str(f) for f in sorted(features_dir.rglob("*.feature")) if ".off" not in f.name
        )

    if not feature_files:
        print(f"{_YELLOW}[WARN]{_RESET} No .feature files found", file=sys.stderr)
        sys.exit(0)

    reports: list[FeatureReport] = []
    for fp in feature_files:
        reports.append(check_feature(fp, toolkit_url, probes))

    if args.json_path:
        json_data = {
            "toolkit_url": toolkit_url,
            "probes_dir": str(probes_dir),
            "probes_loaded": sorted(probes.keys()),
            "generated_at": datetime.now(UTC).isoformat(),
            "features": [r.to_dict() for r in reports],
            "total_exit_code": 1 if any(r.exit_code == 1 for r in reports) else 0,
        }
        json_path = Path(args.json_path)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump(json_data, jf, ensure_ascii=False, indent=2)

    total_exit = 1 if any(r.exit_code == 1 for r in reports) else 0
    sys.exit(total_exit)


if __name__ == "__main__":
    main()
