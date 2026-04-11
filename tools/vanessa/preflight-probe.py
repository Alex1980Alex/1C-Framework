#!/usr/bin/env python3
"""
preflight-probe.py — Pre-flight data check for VA BDD tests against 1C TestDB.
Verifies that all referenced test data exists before launching Vanessa Automation BDD tests.
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_TOOLKIT_URL = "http://localhost:6003/api/execute_query"
HTTP_TIMEOUT = 10

# ANSI colour helpers (safe on Windows 10+ with ENABLE_VIRTUAL_TERMINAL_PROCESSING)
_GREEN = "\033[92m"
_RED = "\033[91m"
_YELLOW = "\033[93m"
_CYAN = "\033[96m"
_RESET = "\033[0m"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    type: str          # TS / Catalog / Role / Setting
    name: str
    status: str        # OK / FAIL / SKIP
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
# 1C MCP Toolkit communication
# ---------------------------------------------------------------------------

def run_query(
    toolkit_url: str,
    query: str,
    params: dict | None = None,
    channel: str | None = None,
) -> list:
    """Execute a 1C query via the MCP toolkit HTTP API.

    Returns the list of rows from the response.
    Raises on HTTP errors or toolkit-level failures.
    """
    payload: dict = {"query": query}
    if params:
        payload["params"] = params
    if channel:
        payload["channel"] = channel

    resp = requests.post(toolkit_url, json=payload, timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    body = resp.json()

    if not body.get("success", False):
        raise RuntimeError(body.get("error", "Unknown toolkit error"))

    return body.get("data", [])


# ---------------------------------------------------------------------------
# Metadata parser
# ---------------------------------------------------------------------------

def parse_metadata(feature_path: str) -> list[dict]:
    """Parse METADATA section from a .feature file.

    Returns a list of requirement dicts, each with at least 'type' and 'raw'.
    """
    requirements: list[dict] = []
    in_metadata = False

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

                # TS: ...
                m = re.match(r"^TS:\s*(.+)$", content, re.IGNORECASE)
                if m:
                    requirements.append({"type": "TS", "raw": m.group(1).strip()})
                    continue

                # Catalog: Name[item1, item2]
                m = re.match(r"^Catalog:\s*(.+)$", content, re.IGNORECASE)
                if m:
                    requirements.append({"type": "Catalog", "raw": m.group(1).strip()})
                    continue

                # Role: Name
                m = re.match(r"^Role:\s*(.+)$", content, re.IGNORECASE)
                if m:
                    requirements.append({"type": "Role", "raw": m.group(1).strip()})
                    continue

                # Setting: Name[Param1/Param2]
                m = re.match(r"^Setting:\s*(.+)$", content, re.IGNORECASE)
                if m:
                    requirements.append({"type": "Setting", "raw": m.group(1).strip()})
                    continue

    return requirements


# ---------------------------------------------------------------------------
# Probe implementations
# ---------------------------------------------------------------------------

def probe_ts(
    toolkit_url: str,
    raw: str,
    channel: str | None,
) -> list[CheckResult]:
    """Probe transport vehicles for existence and freshness."""
    results: list[CheckResult] = []

    # Parse flags
    flags_part = ""
    bracket_match = re.search(r"\(([^)]*)\)", raw)
    if bracket_match:
        flags_part = bracket_match.group(1).strip().lower()
        raw = raw[: bracket_match.start()] + raw[bracket_match.end():]

    want_fresh = "fresh" in flags_part
    want_plk = "plk_catalog" in flags_part or "plk" in flags_part

    names = [n.strip() for n in raw.split(",") if n.strip()]

    for name in names:
        # existence
        try:
            rows = run_query(
                toolkit_url,
                "ВЫБРАТЬ ТС.Наименование ИЗ Справочник.ТранспортныеСредства КАК ТС "
                "ГДЕ ТС.Наименование = &Name И НЕ ТС.ПометкаУдаления",
                {"Name": name},
                channel,
            )
            if not rows:
                results.append(CheckResult("TS", name, "FAIL", "not found in TestDB"))
                continue
        except Exception as exc:
            results.append(CheckResult("TS", name, "FAIL", f"query error: {exc}"))
            continue

        details: list[str] = ["exists"]

        if want_plk:
            try:
                plk_rows = run_query(
                    toolkit_url,
                    "ВЫБРАТЬ ТС.ЭтоСправочникПЛК ИЗ Справочник.ТранспортныеСредства КАК ТС "
                    "ГДЕ ТС.Наименование = &Name И НЕ ТС.ПометкаУдаления",
                    {"Name": name},
                    channel,
                )
                plk_val = plk_rows[0].get("ЭтоСправочникПЛК", False) if plk_rows else False
                if plk_val:
                    details.append("PLK")
                else:
                    results.append(
                        CheckResult("TS", name, "FAIL", "exists but ЭтоСправочникПЛК=False")
                    )
                    continue
            except Exception:
                details.append("PLK-check-error")

        if want_fresh:
            try:
                fresh_rows = run_query(
                    toolkit_url,
                    "ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Active "
                    "ИЗ РегистрСведений.гкс_СостоянияРегистрации.СрезПоследних КАК Сост "
                    "ГДЕ Сост.ДокументРегистрации.ТранспортноеСредство.Наименование = &Name "
                    "И Сост.Состояние <> ЗНАЧЕНИЕ(Перечисление.гкс_СостоянияРегистрации.Убыл)",
                    {"Name": name},
                    channel,
                )
                active = fresh_rows[0].get("Active", 0) if fresh_rows else 0
                if active and int(active) > 0:
                    results.append(
                        CheckResult(
                            "TS",
                            name,
                            "FAIL",
                            f"has {active} active registrations — not fresh",
                        )
                    )
                    continue
                details.append("fresh")
            except Exception as exc:
                details.append(f"freshness-check-error({exc})")

        results.append(CheckResult("TS", name, "OK", ", ".join(details)))

    return results


def probe_catalog(
    toolkit_url: str,
    raw: str,
    channel: str | None,
) -> list[CheckResult]:
    """Probe catalog items for existence."""
    results: list[CheckResult] = []

    m = re.match(r"^(\S+)\[(.+)\]$", raw)
    if not m:
        results.append(CheckResult("Catalog", raw, "SKIP", "cannot parse expression"))
        return results

    catalog_name = m.group(1).strip()
    items_str = m.group(2).strip()
    items = [i.strip() for i in items_str.split(",") if i.strip()]

    for item in items:
        try:
            rows = run_query(
                toolkit_url,
                f"ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Cnt ИЗ Справочник.{catalog_name} "
                "ГДЕ Наименование = &Name И НЕ ПометкаУдаления",
                {"Name": item},
                channel,
            )
            cnt = rows[0].get("Cnt", 0) if rows else 0
            if cnt and int(cnt) > 0:
                results.append(CheckResult("Catalog", f"{catalog_name}[{item}]", "OK", "found"))
            else:
                results.append(
                    CheckResult("Catalog", f"{catalog_name}[{item}]", "FAIL", "not found")
                )
        except Exception as exc:
            results.append(
                CheckResult("Catalog", f"{catalog_name}[{item}]", "FAIL", f"query error: {exc}")
            )

    return results


def probe_role(
    toolkit_url: str,
    raw: str,
    channel: str | None,
) -> list[CheckResult]:
    """Probe role availability.

    The reliable 1C role check requires an active user session which we may not
    have in the toolkit context. We attempt the query but mark as SKIP on failure.
    """
    role_name = raw.strip()

    try:
        rows = run_query(
            toolkit_url,
            f'ВЫБРАТЬ 1 КАК Ok ИЗ Справочник.Пользователи ГДЕ РольДоступна("{role_name}")',
            channel=channel,
        )
        if rows:
            return [CheckResult("Role", role_name, "OK", "role available")]
        return [CheckResult("Role", role_name, "SKIP", "manual check required")]
    except Exception:
        return [CheckResult("Role", role_name, "SKIP", "manual check required")]


def probe_setting(
    toolkit_url: str,
    raw: str,
    channel: str | None,
) -> list[CheckResult]:
    """Probe electronic board settings."""
    results: list[CheckResult] = []

    m = re.match(r"^(\S+)\[(.+)\]$", raw)
    if not m:
        results.append(CheckResult("Setting", raw, "SKIP", "cannot parse expression"))
        return results

    setting_name = m.group(1).strip()
    params_str = m.group(2).strip()
    parts = [p.strip() for p in params_str.split("/") if p.strip()]

    if len(parts) < 2:
        results.append(
            CheckResult("Setting", raw, "SKIP", "expected Setting: Name[Point/Kind]")
        )
        return results

    point = parts[0]
    kind = parts[1]

    try:
        rows = run_query(
            toolkit_url,
            "ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Cnt "
            "ИЗ РегистрСведений.гкс_НастройкаЭлектронногоТабло "
            "ГДЕ ТочкаМаршрута.Наименование = &Point "
            f"И ВидТабло = ЗНАЧЕНИЕ(Перечисление.гкс_ВидыЭлектронныхТабло.{kind})",
            {"Point": point},
            channel,
        )
        cnt = rows[0].get("Cnt", 0) if rows else 0
        if cnt and int(cnt) > 0:
            results.append(
                CheckResult("Setting", f"{setting_name}[{point}/{kind}]", "OK", "found")
            )
        else:
            results.append(
                CheckResult("Setting", f"{setting_name}[{point}/{kind}]", "FAIL", "not found")
            )
    except Exception as exc:
        results.append(
            CheckResult(
                "Setting", f"{setting_name}[{point}/{kind}]", "FAIL", f"query error: {exc}"
            )
        )

    return results


# ---------------------------------------------------------------------------
# Feature checking orchestrator
# ---------------------------------------------------------------------------

def check_feature(
    feature_path: str,
    toolkit_url: str,
    channel: str | None,
) -> FeatureReport:
    """Run all pre-flight probes for a single feature file."""
    report = FeatureReport(
        feature=os.path.basename(feature_path),
        timestamp=datetime.now(UTC).isoformat(),
    )

    print(f"{_CYAN}[preflight]{_RESET} feature: {report.feature}")

    requirements = parse_metadata(feature_path)
    if not requirements:
        print(f"  {_YELLOW}No METADATA section found — skipping checks{_RESET}")
        report.checks.append(
            CheckResult("Meta", report.feature, "OK", "no METADATA section (back-compat)")
        )
        report.recalc_exit_code()
        return report

    for req in requirements:
        req_type = req["type"]
        raw = req["raw"]

        if req_type == "TS":
            report.checks.extend(probe_ts(toolkit_url, raw, channel))
        elif req_type == "Catalog":
            report.checks.extend(probe_catalog(toolkit_url, raw, channel))
        elif req_type == "Role":
            report.checks.extend(probe_role(toolkit_url, raw, channel))
        elif req_type == "Setting":
            report.checks.extend(probe_setting(toolkit_url, raw, channel))
        else:
            report.checks.append(CheckResult(req_type, raw, "SKIP", "unknown requirement type"))

    for c in report.checks:
        if c.status == "OK":
            tag = f"{_GREEN}[OK]{_RESET}  "
        elif c.status == "FAIL":
            tag = f"{_RED}[FAIL]{_RESET}"
        else:
            tag = f"{_YELLOW}[SKIP]{_RESET}"
        print(f"  {tag}  {c.type:<7s} {c.name} — {c.detail}")

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
        help="Path to a single .feature file; omit to scan features/ directory",
    )
    parser.add_argument(
        "--toolkit-url",
        default=DEFAULT_TOOLKIT_URL,
        help=f"1C MCP toolkit URL (default: {DEFAULT_TOOLKIT_URL})",
    )
    parser.add_argument(
        "--channel",
        default=None,
        help="Optional channel ID passed to toolkit requests",
    )
    parser.add_argument(
        "--json",
        default=None,
        dest="json_path",
        help="Path to write structured JSON result for run-bdd.ps1 integration",
    )
    args = parser.parse_args()

    toolkit_url: str = args.toolkit_url
    channel: str | None = args.channel

    # Verify toolkit is reachable (host-level only, endpoint may return 404 for GET)
    try:
        requests.get(toolkit_url.replace("/api/execute_query", "/"), timeout=HTTP_TIMEOUT)
    except requests.ConnectionError:
        print(
            f"{_RED}[ERROR]{_RESET} Cannot reach 1c-mcp-toolkit at {toolkit_url}",
            file=sys.stderr,
        )
        sys.exit(2)
    except Exception:
        pass

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
        reports.append(check_feature(fp, toolkit_url, channel))

    if args.json_path:
        json_data = {
            "toolkit_url": toolkit_url,
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
