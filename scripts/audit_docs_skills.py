#!/usr/bin/env python3
"""
Audit: Framework Code ↔ Documentation ↔ Skills.

Scans the codebase, extracts implemented features, compares with
user documentation and skills, outputs a gap report.

Usage:
    python scripts/audit_docs_skills.py              # Full report (markdown)
    python scripts/audit_docs_skills.py --json        # JSON output
    python scripts/audit_docs_skills.py --fix         # Report + action items for Claude

Output: docs/analysis/AUDIT_DOCS_SKILLS.md (or stdout with --stdout)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ═══════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════


@dataclass
class Feature:
    """A single feature extracted from code."""
    name: str
    category: str  # endpoint, mcp_tool, strategy, agent, cli_command, config_var
    source_file: str
    details: str = ""


@dataclass
class Gap:
    """A gap between code and documentation/skills."""
    feature_name: str
    category: str
    gap_type: str  # undocumented, phantom, outdated
    location: str  # where it should be documented
    source_file: str = ""
    details: str = ""


@dataclass
class AuditReport:
    """Full audit results."""
    timestamp: str = ""
    features: list[Feature] = field(default_factory=list)
    doc_gaps: list[Gap] = field(default_factory=list)
    skill_gaps: list[Gap] = field(default_factory=list)
    phantom_docs: list[Gap] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════
# EXTRACTORS — parse source code to find implemented features
# ═══════════════════════════════════════════════════════════════════════


def extract_api_endpoints() -> list[Feature]:
    """Extract REST API endpoints from src/api/routes/*.py."""
    features = []
    routes_dir = PROJECT_ROOT / "src" / "api" / "routes"
    if not routes_dir.exists():
        return features

    pattern = re.compile(
        r'@router\.(get|post|put|delete|patch|websocket)\(\s*["\']([^"\']+)["\']',
        re.IGNORECASE,
    )

    for py_file in sorted(routes_dir.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        file_text = py_file.read_text(encoding="utf-8", errors="replace")
        router_prefix = _extract_router_prefix(file_text, py_file.stem)
        for m in pattern.finditer(file_text):
            method = m.group(1).upper()
            path = m.group(2)
            full_path = f"{router_prefix}{path}" if path != "/" else router_prefix + "/"
            features.append(Feature(
                name=f"{method} {full_path}",
                category="endpoint",
                source_file=str(py_file.relative_to(PROJECT_ROOT)),
                details=f"router={py_file.stem}",
            ))
    return features


def _extract_router_prefix(text: str, stem: str) -> str:
    """Try to guess router prefix from file content or name."""
    # Look for prefix in app.py include_router calls
    app_file = PROJECT_ROOT / "src" / "api" / "app.py"
    if app_file.exists():
        app_text = app_file.read_text(encoding="utf-8", errors="replace")
        # Match: include_router(xxx_router, prefix="/xxx")
        pat = re.compile(
            rf'include_router\([^)]*{stem}[^)]*prefix\s*=\s*["\']([^"\']+)["\']',
        )
        m = pat.search(app_text)
        if m:
            return m.group(1).rstrip("/")
    return f"/{stem}"


def extract_mcp_tools() -> list[Feature]:
    """Extract MCP tools from src/mcp_server/server.py."""
    features = []
    server_file = PROJECT_ROOT / "src" / "mcp_server" / "server.py"
    if not server_file.exists():
        return features

    text = server_file.read_text(encoding="utf-8", errors="replace")

    # Extract tool names from Tool(name="xxx", ...)
    pattern = re.compile(r'Tool\(\s*name\s*=\s*["\']([^"\']+)["\']')
    for m in pattern.finditer(text):
        features.append(Feature(
            name=m.group(1),
            category="mcp_tool",
            source_file="src/mcp_server/server.py",
        ))

    # Fallback: extract from call_tool handler
    if not features:
        handler_pattern = re.compile(r'name\s*==\s*["\']([^"\']+)["\']')
        for m in handler_pattern.finditer(text):
            features.append(Feature(
                name=m.group(1),
                category="mcp_tool",
                source_file="src/mcp_server/server.py",
            ))

    return features


def extract_search_strategies() -> list[Feature]:
    """Extract search strategies from strategies directory."""
    features = []
    strats_dir = PROJECT_ROOT / "src" / "pdf_framework" / "search" / "strategies"
    if not strats_dir.exists():
        return features

    # Check __init__.py for STRATEGY_MAP or registry
    init_file = strats_dir / "__init__.py"
    if init_file.exists():
        init_text = init_file.read_text(encoding="utf-8", errors="replace")
        # Match: "strategy_name": ClassName or "strategy_name": ...
        map_pattern = re.compile(r'["\'](\w+)["\']\s*:\s*(\w+)')
        for m in map_pattern.finditer(init_text):
            features.append(Feature(
                name=m.group(1),
                category="strategy",
                source_file="src/pdf_framework/search/strategies/__init__.py",
                details=f"class={m.group(2)}",
            ))

    # Also scan individual files for Strategy classes
    class_pattern = re.compile(r'class\s+(\w+Strategy)\s*[:(]')
    for py_file in sorted(strats_dir.glob("*.py")):
        if py_file.name == "__init__.py":
            continue
        text = py_file.read_text(encoding="utf-8", errors="replace")
        for m in class_pattern.finditer(text):
            name = _class_to_strategy_name(m.group(1))
            # Avoid duplicates from __init__.py
            if not any(f.name == name for f in features):
                features.append(Feature(
                    name=name,
                    category="strategy",
                    source_file=str(py_file.relative_to(PROJECT_ROOT)),
                    details=f"class={m.group(1)}",
                ))
    return features


def _class_to_strategy_name(cls_name: str) -> str:
    """Convert ClassName to strategy_name: HybridSearchStrategy → hybrid."""
    name = cls_name.replace("Strategy", "").replace("Search", "")
    # CamelCase to snake_case
    s = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
    return s.strip("_")


def extract_cli_commands() -> list[Feature]:
    """Extract CLI commands from src/cli/main.py."""
    features = []
    cli_file = PROJECT_ROOT / "src" / "cli" / "main.py"
    if not cli_file.exists():
        return features

    text = cli_file.read_text(encoding="utf-8", errors="replace")

    # Match @app.command() followed by def func_name(
    # Also @app.command(name="xxx")
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if "@app.command" in line:
            # Extract explicit name if present
            name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', line)
            if name_match:
                cmd_name = name_match.group(1)
            else:
                # Get function name from next def line
                for j in range(i + 1, min(i + 5, len(lines))):
                    def_match = re.match(r'\s*def\s+(\w+)\s*\(', lines[j])
                    if def_match:
                        cmd_name = def_match.group(1)
                        break
                else:
                    continue

            features.append(Feature(
                name=cmd_name,
                category="cli_command",
                source_file="src/cli/main.py",
                details=f"line={i+1}",
            ))
    return features


def extract_config_vars() -> list[Feature]:
    """Extract config variables from pydantic Settings classes."""
    features = []
    config_dir = PROJECT_ROOT / "src" / "pdf_framework" / "config"
    if not config_dir.exists():
        return features

    # First, get root Settings to know sub-settings names
    base_file = config_dir / "_base.py"
    if not base_file.exists():
        return features

    base_text = base_file.read_text(encoding="utf-8", errors="replace")

    # Extract sub-settings field names: field_name: SettingsClass
    subsettings_pattern = re.compile(
        r'(\w+)\s*:\s*(\w+Settings)\s*=\s*Field'
    )
    subsettings = {}
    for m in subsettings_pattern.finditer(base_text):
        subsettings[m.group(2)] = m.group(1).upper()

    # Now scan all config files for field definitions in Settings classes
    class_pattern = re.compile(r'class\s+(\w+Settings)\s*\(')

    for py_file in sorted(config_dir.glob("*.py")):
        text = py_file.read_text(encoding="utf-8", errors="replace")
        current_class = None

        for line in text.splitlines():
            class_match = class_pattern.search(line)
            if class_match:
                current_class = class_match.group(1)
                continue

            if current_class and not line.startswith("class "):
                field_match = re.match(r'\s+(\w+)\s*:\s*[\w\[\], |"\']+\s*=', line)
                if field_match:
                    field_name = field_match.group(1)
                    if field_name.startswith("model_") or field_name.startswith("_"):
                        continue
                    prefix = subsettings.get(current_class, current_class.replace("Settings", "").upper())
                    env_var = f"{prefix}__{field_name}".upper()
                    features.append(Feature(
                        name=env_var,
                        category="config_var",
                        source_file=str(py_file.relative_to(PROJECT_ROOT)),
                        details=f"class={current_class}",
                    ))
    return features


def extract_agent_types() -> list[Feature]:
    """Extract agent types from src/pdf_framework/agents/."""
    features = []
    agents_dir = PROJECT_ROOT / "src" / "pdf_framework" / "agents"
    if not agents_dir.exists():
        return features

    # Look for agent.py files in subdirectories
    for agent_file in sorted(agents_dir.rglob("agent.py")):
        rel = agent_file.relative_to(agents_dir)
        agent_type = str(rel.parent)
        if agent_type == ".":
            continue
        features.append(Feature(
            name=agent_type,
            category="agent",
            source_file=str(agent_file.relative_to(PROJECT_ROOT)),
        ))

    # Also check for specific orchestrator/manager files
    for pattern_name in ["orchestrator.py", "manager.py"]:
        for f in agents_dir.rglob(pattern_name):
            agent_type = str(f.relative_to(agents_dir).parent)
            if not any(feat.name == agent_type for feat in features):
                features.append(Feature(
                    name=agent_type,
                    category="agent",
                    source_file=str(f.relative_to(PROJECT_ROOT)),
                ))
    return features


# ═══════════════════════════════════════════════════════════════════════
# DOCUMENTATION & SKILL PARSERS
# ═══════════════════════════════════════════════════════════════════════

DOCS_DIR = PROJECT_ROOT / "docs" / "framework documentation"
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"

# Mapping: category → (doc files to check, skill names to check)
CATEGORY_MAPPING: dict[str, dict[str, Any]] = {
    "endpoint": {
        "docs": [
            "06_ИНТЕРФЕЙСЫ/06.2_REST_API.md",
        ],
        "skills": ["framework-api"],
    },
    "mcp_tool": {
        "docs": [
            "06_ИНТЕРФЕЙСЫ/06.4_MCP_Server.md",
        ],
        "skills": ["framework-mcp-ui"],
    },
    "strategy": {
        "docs": [
            "04_ПОИСК/04.1_Обзор_стратегий.md",
            "04_ПОИСК/04.7_Расширенный_поиск.md",
        ],
        "skills": ["search-pipeline-debug"],
    },
    "cli_command": {
        "docs": [
            "06_ИНТЕРФЕЙСЫ/06.3_CLI.md",
        ],
        "skills": ["framework-cli"],
    },
    "config_var": {
        "docs": [
            "02_БЫСТРЫЙ_СТАРТ/02.2_Конфигурация.md",
        ],
        "skills": ["framework-config"],
    },
    "agent": {
        "docs": [
            "05_RAG_АГЕНТЫ/05.1_Self_RAG.md",
            "05_RAG_АГЕНТЫ/05.2_Adaptive_RAG.md",
            "05_RAG_АГЕНТЫ/05.3_Deep_Research.md",
            "05_RAG_АГЕНТЫ/05.5_Специализированные_агенты.md",
        ],
        "skills": ["agent-orchestration"],
    },
}


def _load_doc_text(relative_path: str) -> str:
    """Load documentation file text."""
    full_path = DOCS_DIR / relative_path
    if full_path.exists():
        return full_path.read_text(encoding="utf-8", errors="replace").lower()
    return ""


def _load_skill_text(skill_name: str) -> str:
    """Load SKILL.md text for a given skill."""
    skill_file = SKILLS_DIR / skill_name / "SKILL.md"
    if skill_file.exists():
        return skill_file.read_text(encoding="utf-8", errors="replace").lower()
    return ""


def _feature_documented(feature: Feature, text: str) -> bool:
    """Check if a feature is mentioned in the text."""
    name_lower = feature.name.lower()

    if feature.category == "endpoint":
        # For endpoints: check both full path and just the path part
        parts = name_lower.split(" ", 1)
        if len(parts) == 2:
            path = parts[1]
            # Check path variants
            return (path in text
                    or path.rstrip("/") in text
                    or path.lstrip("/") in text)
        return name_lower in text

    elif feature.category == "config_var":
        # For config vars: check both full env name and just the field name
        # EMBEDDING__MODEL → check "embedding__model" and "model"
        parts = name_lower.split("__")
        field_name = parts[-1] if len(parts) > 1 else name_lower
        return name_lower in text or f"__{field_name}" in text

    elif feature.category == "strategy":
        # For strategies: check name and common aliases
        return (name_lower in text
                or name_lower.replace("_", "") in text
                or name_lower.replace("_", "-") in text)

    elif feature.category == "mcp_tool":
        return name_lower in text

    elif feature.category == "cli_command":
        return name_lower in text

    elif feature.category == "agent":
        # Agent type names like "rag", "multi", "analytical"
        return name_lower in text

    return name_lower in text


# ═══════════════════════════════════════════════════════════════════════
# AUDIT ENGINE
# ═══════════════════════════════════════════════════════════════════════


def run_audit() -> AuditReport:
    """Run the full audit: extract → compare → report."""
    report = AuditReport(
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    # 1. Extract all features from code
    extractors = [
        ("API Endpoints", extract_api_endpoints),
        ("MCP Tools", extract_mcp_tools),
        ("Search Strategies", extract_search_strategies),
        ("CLI Commands", extract_cli_commands),
        ("Agents", extract_agent_types),
        ("Config Variables", extract_config_vars),
    ]

    for label, extractor_fn in extractors:
        try:
            features = extractor_fn()
            report.features.extend(features)
        except Exception as e:
            print(f"  [WARN] {label} extractor failed: {e}", file=sys.stderr)

    # 2. Compare with documentation and skills
    for feature in report.features:
        mapping = CATEGORY_MAPPING.get(feature.category)
        if not mapping:
            continue

        # Check documentation
        doc_found = False
        for doc_path in mapping["docs"]:
            doc_text = _load_doc_text(doc_path)
            if doc_text and _feature_documented(feature, doc_text):
                doc_found = True
                break

        if not doc_found:
            report.doc_gaps.append(Gap(
                feature_name=feature.name,
                category=feature.category,
                gap_type="undocumented",
                location=", ".join(mapping["docs"]),
                source_file=feature.source_file,
                details=feature.details,
            ))

        # Check skills
        skill_found = False
        for skill_name in mapping["skills"]:
            skill_text = _load_skill_text(skill_name)
            if skill_text and _feature_documented(feature, skill_text):
                skill_found = True
                break

        if not skill_found:
            report.skill_gaps.append(Gap(
                feature_name=feature.name,
                category=feature.category,
                gap_type="undocumented",
                location=", ".join(f".claude/skills/{s}/SKILL.md" for s in mapping["skills"]),
                source_file=feature.source_file,
                details=feature.details,
            ))

    # 3. Build summary
    categories = set(f.category for f in report.features)
    report.summary = {
        "total_features": len(report.features),
        "doc_gaps": len(report.doc_gaps),
        "skill_gaps": len(report.skill_gaps),
        "by_category": {},
    }

    for cat in sorted(categories):
        cat_features = [f for f in report.features if f.category == cat]
        cat_doc_gaps = [g for g in report.doc_gaps if g.category == cat]
        cat_skill_gaps = [g for g in report.skill_gaps if g.category == cat]
        report.summary["by_category"][cat] = {
            "total": len(cat_features),
            "doc_gaps": len(cat_doc_gaps),
            "skill_gaps": len(cat_skill_gaps),
            "coverage_docs": round(
                (1 - len(cat_doc_gaps) / max(len(cat_features), 1)) * 100, 1
            ),
            "coverage_skills": round(
                (1 - len(cat_skill_gaps) / max(len(cat_features), 1)) * 100, 1
            ),
        }

    return report


# ═══════════════════════════════════════════════════════════════════════
# OUTPUT FORMATTERS
# ═══════════════════════════════════════════════════════════════════════

CATEGORY_LABELS = {
    "endpoint": "REST API Endpoints",
    "mcp_tool": "MCP Tools",
    "strategy": "Search Strategies",
    "cli_command": "CLI Commands",
    "config_var": "Config Variables (.env)",
    "agent": "Agent Types",
}


def format_markdown(report: AuditReport, include_fix: bool = False) -> str:
    """Format report as markdown."""
    lines: list[str] = []
    a = lines.append

    a(f"# Audit: Code ↔ Documentation ↔ Skills")
    a(f"")
    a(f"**Generated:** {report.timestamp}")
    a(f"")

    # Summary table
    a("## Summary")
    a("")
    a("| Category | In Code | Doc Gaps | Skill Gaps | Doc Coverage | Skill Coverage |")
    a("|----------|---------|----------|------------|-------------|----------------|")

    for cat, stats in report.summary.get("by_category", {}).items():
        label = CATEGORY_LABELS.get(cat, cat)
        a(f"| {label} | {stats['total']} | "
          f"**{stats['doc_gaps']}** | **{stats['skill_gaps']}** | "
          f"{stats['coverage_docs']}% | {stats['coverage_skills']}% |")

    total = report.summary
    a(f"| **TOTAL** | **{total.get('total_features', 0)}** | "
      f"**{total.get('doc_gaps', 0)}** | **{total.get('skill_gaps', 0)}** | | |")
    a("")

    # Documentation gaps
    if report.doc_gaps:
        a("## Documentation Gaps (in code, NOT in docs)")
        a("")
        for cat in sorted(set(g.category for g in report.doc_gaps)):
            label = CATEGORY_LABELS.get(cat, cat)
            gaps = [g for g in report.doc_gaps if g.category == cat]
            a(f"### {label} ({len(gaps)} gaps)")
            a("")
            a("| Feature | Source | Should be in |")
            a("|---------|--------|-------------|")
            for g in gaps:
                a(f"| `{g.feature_name}` | `{g.source_file}` | `{g.location}` |")
            a("")

    # Skill gaps
    if report.skill_gaps:
        a("## Skill Gaps (in code, NOT in skills)")
        a("")
        for cat in sorted(set(g.category for g in report.skill_gaps)):
            label = CATEGORY_LABELS.get(cat, cat)
            gaps = [g for g in report.skill_gaps if g.category == cat]
            a(f"### {label} ({len(gaps)} gaps)")
            a("")
            a("| Feature | Source | Should be in |")
            a("|---------|--------|-------------|")
            for g in gaps:
                a(f"| `{g.feature_name}` | `{g.source_file}` | `{g.location}` |")
            a("")

    # Fix action items
    if include_fix:
        a("## Action Items")
        a("")
        a("### Documentation updates needed:")
        a("")
        # Group by target doc
        doc_targets: dict[str, list[Gap]] = {}
        for g in report.doc_gaps:
            for loc in g.location.split(", "):
                doc_targets.setdefault(loc, []).append(g)

        for doc, gaps in sorted(doc_targets.items()):
            a(f"**`{doc}`** — {len(gaps)} missing features:")
            for g in gaps[:20]:
                a(f"  - [ ] Add `{g.feature_name}` (from `{g.source_file}`)")
            if len(gaps) > 20:
                a(f"  - ... and {len(gaps) - 20} more")
            a("")

        a("### Skill updates needed:")
        a("")
        skill_targets: dict[str, list[Gap]] = {}
        for g in report.skill_gaps:
            for loc in g.location.split(", "):
                skill_targets.setdefault(loc, []).append(g)

        for skill, gaps in sorted(skill_targets.items()):
            a(f"**`{skill}`** — {len(gaps)} missing features:")
            for g in gaps[:20]:
                a(f"  - [ ] Add `{g.feature_name}` (from `{g.source_file}`)")
            if len(gaps) > 20:
                a(f"  - ... and {len(gaps) - 20} more")
            a("")

    # All features (reference)
    a("## All Extracted Features (reference)")
    a("")
    for cat in sorted(set(f.category for f in report.features)):
        label = CATEGORY_LABELS.get(cat, cat)
        feats = [f for f in report.features if f.category == cat]
        a(f"### {label} ({len(feats)})")
        a("")
        for f in feats:
            a(f"- `{f.name}` — `{f.source_file}`")
        a("")

    return "\n".join(lines)


def format_json(report: AuditReport) -> str:
    """Format report as JSON."""
    return json.dumps({
        "timestamp": report.timestamp,
        "summary": report.summary,
        "doc_gaps": [
            {"feature": g.feature_name, "category": g.category,
             "source": g.source_file, "target": g.location}
            for g in report.doc_gaps
        ],
        "skill_gaps": [
            {"feature": g.feature_name, "category": g.category,
             "source": g.source_file, "target": g.location}
            for g in report.skill_gaps
        ],
        "features": [
            {"name": f.name, "category": f.category, "source": f.source_file}
            for f in report.features
        ],
    }, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════════════
# AUTO-UPDATER — applies gap fixes to documentation and skills
# ═══════════════════════════════════════════════════════════════════════

# Router stem → human-readable section name (Russian)
_ROUTER_LABELS = {
    "analytics": "Аналитика",
    "auth": "Авторизация",
    "cache": "Кэш",
    "chat": "Чат",
    "collections": "Коллекции",
    "completions": "Chat Completions",
    "documents": "Документы",
    "feedback": "Feedback",
    "graph": "Граф",
    "health": "Health",
    "jobs": "Jobs (фоновые задачи)",
    "metrics": "Метрики",
    "openai_compat": "OpenAI Compatible",
    "optimization": "Оптимизация",
    "search": "Поиск",
    "tenants": "Тенанты",
    "toc": "ToC (Оглавление)",
    "websocket": "WebSocket",
}


def _find_section_insert_point(lines: list[str], section_header: str) -> int | None:
    """Find the end of a markdown section (### header) to insert new rows.

    Returns line index AFTER the last table row in that section,
    or None if section not found.
    """
    in_section = False
    last_table_row = None

    for i, line in enumerate(lines):
        if line.strip().startswith("### ") and section_header.lower() in line.lower():
            in_section = True
            continue
        if in_section:
            if line.strip().startswith("### ") or line.strip().startswith("## "):
                # New section started — insert before it
                return last_table_row + 1 if last_table_row else i
            if line.strip().startswith("|"):
                last_table_row = i

    if in_section and last_table_row:
        return last_table_row + 1
    return None


def _extract_endpoint_description(feature: Feature) -> str:
    """Generate a short description for an endpoint from its name."""
    parts = feature.name.split(" ", 1)
    if len(parts) < 2:
        return feature.name
    path = parts[1]
    # Simple heuristic: last meaningful path segment
    segments = [s for s in path.strip("/").split("/") if not s.startswith("{")]
    if segments:
        last = segments[-1].replace("-", " ").replace("_", " ").title()
        return last
    return path


def update_rest_api_doc(report: AuditReport) -> int:
    """Update REST API documentation with missing endpoints."""
    doc_path = DOCS_DIR / "06_ИНТЕРФЕЙСЫ" / "06.2_REST_API.md"
    if not doc_path.exists():
        return 0

    text = doc_path.read_text(encoding="utf-8", errors="replace")
    doc_lower = text.lower()
    lines = text.splitlines()

    # Get endpoint gaps for this doc
    endpoint_gaps = [
        g for g in report.doc_gaps
        if g.category == "endpoint" and "06.2_REST_API" in g.location
    ]
    if not endpoint_gaps:
        return 0

    # Group by router
    by_router: dict[str, list[Gap]] = {}
    for g in endpoint_gaps:
        router = g.details.replace("router=", "") if g.details else "unknown"
        by_router.setdefault(router, []).append(g)

    added = 0
    new_sections: list[str] = []

    for router, gaps in sorted(by_router.items()):
        section_label = _ROUTER_LABELS.get(router, router.replace("_", " ").title())

        # Try to find existing section
        insert_at = _find_section_insert_point(lines, section_label)

        if insert_at is not None:
            # Insert missing rows into existing table
            new_rows = []
            for g in gaps:
                parts = g.feature_name.split(" ", 1)
                method = parts[0] if len(parts) > 0 else "GET"
                path = parts[1] if len(parts) > 1 else g.feature_name
                # Check not already in doc
                if path.lower() in doc_lower:
                    continue
                feat = next(
                    (f for f in report.features if f.name == g.feature_name),
                    None,
                )
                desc = _extract_endpoint_description(feat) if feat else path
                new_rows.append(f"| `{method}` | `{path}` | {desc} |")
                added += 1

            if new_rows:
                for j, row in enumerate(new_rows):
                    lines.insert(insert_at + j, row)
        else:
            # Create new section
            section_lines = [f"\n### {section_label}\n"]
            section_lines.append("| Method | Endpoint | Описание |")
            section_lines.append("|--------|----------|----------|")
            for g in gaps:
                parts = g.feature_name.split(" ", 1)
                method = parts[0] if len(parts) > 0 else "GET"
                path = parts[1] if len(parts) > 1 else g.feature_name
                if path.lower() in doc_lower:
                    continue
                feat = next(
                    (f for f in report.features if f.name == g.feature_name),
                    None,
                )
                desc = _extract_endpoint_description(feat) if feat else path
                section_lines.append(f"| `{method}` | `{path}` | {desc} |")
                added += 1
            if added:
                new_sections.append("\n".join(section_lines))

    # Append new sections before ## Навигация
    if new_sections:
        nav_idx = None
        for i, line in enumerate(lines):
            if line.strip().startswith("## Навигация"):
                nav_idx = i
                break

        insert_pos = nav_idx if nav_idx else len(lines)
        combined = "\n".join(new_sections)
        lines.insert(insert_pos, combined + "\n")

    if added > 0:
        doc_path.write_text("\n".join(lines), encoding="utf-8")
    return added


def update_mcp_doc(report: AuditReport) -> int:
    """Update MCP Server documentation with missing tools."""
    doc_path = DOCS_DIR / "06_ИНТЕРФЕЙСЫ" / "06.4_MCP_Server.md"
    if not doc_path.exists():
        return 0

    text = doc_path.read_text(encoding="utf-8", errors="replace")
    doc_lower = text.lower()
    lines = text.splitlines()

    mcp_gaps = [
        g for g in report.doc_gaps
        if g.category == "mcp_tool" and "06.4_MCP" in g.location
    ]
    if not mcp_gaps:
        return 0

    # Find the last numbered tool row in the table
    last_tool_row = None
    last_num = 0
    for i, line in enumerate(lines):
        m = re.match(r'\|\s*(\d+)\s*\|', line)
        if m:
            last_tool_row = i
            last_num = int(m.group(1))

    if last_tool_row is None:
        return 0

    added = 0
    new_rows = []
    for g in mcp_gaps:
        if g.feature_name.lower() in doc_lower:
            continue
        last_num += 1
        desc = g.feature_name.replace("_", " ").title()
        new_rows.append(f"| {last_num} | `{g.feature_name}` | {desc} |")
        added += 1

    for j, row in enumerate(new_rows):
        lines.insert(last_tool_row + 1 + j, row)

    # Update tool count in header
    total = last_num
    for i, line in enumerate(lines):
        if "инструмент" in line.lower() and re.search(r'\d+', line):
            lines[i] = re.sub(r'\d+', str(total), line, count=1)
            break

    if added > 0:
        doc_path.write_text("\n".join(lines), encoding="utf-8")
    return added


def update_strategies_doc(report: AuditReport) -> int:
    """Update search strategies documentation."""
    doc_path = DOCS_DIR / "04_ПОИСК" / "04.1_Обзор_стратегий.md"
    if not doc_path.exists():
        return 0

    text = doc_path.read_text(encoding="utf-8", errors="replace")
    doc_lower = text.lower()
    lines = text.splitlines()

    strat_gaps = [
        g for g in report.doc_gaps
        if g.category == "strategy" and "04.1_Обзор" in g.location
    ]
    if not strat_gaps:
        return 0

    # Find last strategy row
    last_row = None
    last_num = 0
    for i, line in enumerate(lines):
        m = re.match(r'\|\s*(\d+)\s*\|', line)
        if m:
            last_row = i
            last_num = int(m.group(1))

    if last_row is None:
        return 0

    added = 0
    new_rows = []
    for g in strat_gaps:
        if g.feature_name.lower() in doc_lower:
            continue
        last_num += 1
        name = g.feature_name
        new_rows.append(
            f"| {last_num} | `{name}` | Средняя | Хорошее | "
            f"{name.replace('_', ' ').title()} |"
        )
        added += 1

    for j, row in enumerate(new_rows):
        lines.insert(last_row + 1 + j, row)

    # Update strategy count
    total = last_num
    for i, line in enumerate(lines):
        if "стратеги" in line.lower() and re.search(r'\d+', line):
            lines[i] = re.sub(r'\d+', str(total), line, count=1)
            break

    if added > 0:
        doc_path.write_text("\n".join(lines), encoding="utf-8")
    return added


def update_config_doc(report: AuditReport) -> int:
    """Update configuration documentation with missing env vars."""
    doc_path = DOCS_DIR / "02_БЫСТРЫЙ_СТАРТ" / "02.2_Конфигурация.md"
    if not doc_path.exists():
        return 0

    text = doc_path.read_text(encoding="utf-8", errors="replace")
    doc_lower = text.lower()

    config_gaps = [
        g for g in report.doc_gaps
        if g.category == "config_var" and "02.2_Конфигурация" in g.location
    ]
    if not config_gaps:
        return 0

    # Group by config prefix (AGENT, EMBEDDING, SEARCH, etc.)
    by_group: dict[str, list[Gap]] = {}
    for g in config_gaps:
        parts = g.feature_name.split("__", 1)
        group = parts[0] if len(parts) > 1 else "OTHER"
        by_group.setdefault(group, []).append(g)

    # Map group prefixes to existing section headers
    _GROUP_TO_SECTION = {
        "AGENT": "LLM настройки",
        "SELF_RAG": "Self-RAG",
        "DEEP_RESEARCH": "Deep Research",
        "EMBEDDING": "Embedding настройки",
        "VECTOR_STORE": "Vector Store",
        "SEARCH": "Поиск",
        "GRAPH_STORE": "Graph Store",
        "GRAPHRAG": "GraphRAG",
        "GRAPH_RAG": "GraphRAG",
        "LIGHTRAG": "LightRAG",
        "CACHE": "Кэширование",
        "AUTH": "Авторизация",
        "API": "API",
        "UI": "Web UI",
        "QUEUE": "Queue (фоновые задачи)",
        "GUARDRAILS": "Guardrails",
        "EXTERNAL": "External Sources",
        "OPTIMIZATION": "Оптимизация",
        "VISUAL_SEARCH": "Visual Search",
        "PARENT_CHILD": "Parent-Child",
        "ADAPTIVE": "Adaptive RAG",
        "CONVERSATION": "Conversation",
        "LAYOUT": "Layout",
        "RAPTOR": "RAPTOR",
        "SUMMARY_INDEX": "Summary Index",
        "SUGGESTIONS": "Suggestions",
        "HIERARCHICAL": "Hierarchical Search",
        "DOCLING": "Docling",
        "SMART_ROUTER": "Smart Router",
        "HYBRID_LOADER": "Hybrid Loader",
        "OBSERVABILITY": "Observability",
        "AUTORAG": "AutoRAG",
        "RAGAS_EVAL": "RAGAS",
        "FEEDBACK": "Feedback",
        "MCP_SERVER": "MCP Server",
        "OPENAI_COMPAT": "OpenAI Compatible",
        "CONTEXTUAL_RETRIEVAL": "Contextual Retrieval",
        "TWO_STAGE": "Two-Stage",
        "LIGHT_RAG": "LightRAG",
        "PDF": "PDF обработка",
    }

    new_sections: list[str] = []
    added = 0

    for group, gaps in sorted(by_group.items()):
        section_name = _GROUP_TO_SECTION.get(group, group.replace("_", " ").title())

        # Filter already-documented vars
        missing = [g for g in gaps if g.feature_name.lower() not in doc_lower]
        if not missing:
            continue

        # Check if section exists as an actual ## header in doc
        section_exists = any(
            section_name.lower() in line.lower() and line.strip().startswith("##")
            for line in text.splitlines()
        )

        if not section_exists:
            # Create new section
            lines = [f"\n## {section_name}\n", "```env"]
            for g in missing:
                lines.append(f"{g.feature_name}=")
            lines.append("```")
            new_sections.append("\n".join(lines))
            added += len(missing)
        else:
            # Find the section's code block and append vars
            doc_lines = text.splitlines()
            in_section = False
            last_env_line = None

            for i, line in enumerate(doc_lines):
                if section_name.lower() in line.lower() and line.strip().startswith("##"):
                    in_section = True
                    continue
                if in_section:
                    if line.strip().startswith("##"):
                        break
                    if line.strip() == "```":
                        if last_env_line is not None:
                            # End of code block — insert before it
                            insert_lines = []
                            for g in missing:
                                insert_lines.append(f"{g.feature_name}=")
                            for j, il in enumerate(insert_lines):
                                doc_lines.insert(last_env_line + 1 + j, il)
                            text = "\n".join(doc_lines)
                            doc_lower = text.lower()
                            added += len(insert_lines)
                            break
                        last_env_line = i
                    elif "=" in line:
                        last_env_line = i

    # Append new sections before navigation
    if new_sections:
        nav_marker = "## Навигация"
        if nav_marker in text:
            text = text.replace(nav_marker, "\n".join(new_sections) + f"\n\n{nav_marker}")
        else:
            text += "\n" + "\n".join(new_sections)

    if added > 0:
        doc_path = DOCS_DIR / "02_БЫСТРЫЙ_СТАРТ" / "02.2_Конфигурация.md"
        doc_path.write_text(text, encoding="utf-8")
    return added


def update_cli_doc(report: AuditReport) -> int:
    """Update CLI documentation with missing commands."""
    doc_path = DOCS_DIR / "06_ИНТЕРФЕЙСЫ" / "06.3_CLI.md"
    if not doc_path.exists():
        return 0

    text = doc_path.read_text(encoding="utf-8", errors="replace")
    doc_lower = text.lower()
    lines = text.splitlines()

    cli_gaps = [
        g for g in report.doc_gaps
        if g.category == "cli_command" and "06.3_CLI" in g.location
    ]
    if not cli_gaps:
        return 0

    # Find last command table row
    last_row = None
    for i, line in enumerate(lines):
        if line.strip().startswith("|") and "`" in line and "---" not in line:
            last_row = i

    if last_row is None:
        return 0

    added = 0
    for g in cli_gaps:
        if g.feature_name.lower() in doc_lower:
            continue
        last_row += 1
        lines.insert(last_row, f"| `{g.feature_name}` | {g.feature_name.replace('_', ' ').title()} |")
        added += 1

    if added > 0:
        doc_path.write_text("\n".join(lines), encoding="utf-8")
    return added


def update_agent_doc(report: AuditReport) -> int:
    """Update agent documentation with missing agent types."""
    # Target: 05.5_Специализированные_агенты.md (catch-all for new agents)
    doc_path = DOCS_DIR / "05_RAG_АГЕНТЫ" / "05.5_Специализированные_агенты.md"
    if not doc_path.exists():
        return 0

    text = doc_path.read_text(encoding="utf-8", errors="replace")
    doc_lower = text.lower()

    agent_gaps = [
        g for g in report.doc_gaps
        if g.category == "agent"
    ]
    if not agent_gaps:
        return 0

    added = 0
    new_lines: list[str] = []
    for g in agent_gaps:
        if g.feature_name.lower() in doc_lower:
            continue
        title = g.feature_name.replace("_", " ").title()
        new_lines.append(f"\n## {title} Agent\n")
        new_lines.append(f"**Исходный файл:** `{g.source_file}`\n")
        new_lines.append(f"Агент `{g.feature_name}` — специализированный агент фреймворка.\n")
        added += 1

    if added > 0:
        # Append before ## Навигация or at end
        nav_marker = "## Навигация"
        content = "\n".join(new_lines)
        if nav_marker in text:
            text = text.replace(nav_marker, content + f"\n{nav_marker}")
        else:
            text += "\n" + content + "\n"
        doc_path.write_text(text, encoding="utf-8")

    return added


def update_skill_file(skill_name: str, gaps: list[Gap]) -> int:
    """Update a skill SKILL.md with missing features."""
    skill_path = SKILLS_DIR / skill_name / "SKILL.md"
    if not skill_path.exists():
        return 0

    text = skill_path.read_text(encoding="utf-8", errors="replace")
    skill_lower = text.lower()

    # Filter already-documented
    missing = [g for g in gaps if not _feature_documented(
        Feature(name=g.feature_name, category=g.category, source_file=g.source_file),
        skill_lower,
    )]
    if not missing:
        return 0

    # Group by category for formatting
    by_cat: dict[str, list[Gap]] = {}
    for g in missing:
        by_cat.setdefault(g.category, []).append(g)

    new_content: list[str] = []
    added = 0

    for cat, cat_gaps in by_cat.items():
        label = CATEGORY_LABELS.get(cat, cat)

        if cat == "endpoint":
            new_content.append(f"\n## Незадокументированные {label}\n")
            new_content.append("| Method | Endpoint | Source |")
            new_content.append("|--------|----------|--------|")
            for g in cat_gaps:
                parts = g.feature_name.split(" ", 1)
                method = parts[0] if len(parts) > 0 else "?"
                path = parts[1] if len(parts) > 1 else g.feature_name
                new_content.append(f"| `{method}` | `{path}` | `{g.source_file}` |")
                added += 1

        elif cat == "config_var":
            new_content.append(f"\n## Незадокументированные {label}\n")
            new_content.append("```env")
            for g in cat_gaps:
                new_content.append(f"{g.feature_name}=")
                added += 1
            new_content.append("```")

        elif cat == "strategy":
            new_content.append(f"\n## Незадокументированные {label}\n")
            for g in cat_gaps:
                new_content.append(f"- `{g.feature_name}` ({g.source_file})")
                added += 1

        elif cat == "mcp_tool":
            new_content.append(f"\n## Незадокументированные {label}\n")
            for g in cat_gaps:
                new_content.append(f"- `{g.feature_name}`")
                added += 1

        else:
            new_content.append(f"\n## Незадокументированные {label}\n")
            for g in cat_gaps:
                new_content.append(f"- `{g.feature_name}` ({g.source_file})")
                added += 1

    if added > 0:
        # Insert before ## Файлы section (if exists), otherwise append
        if "## Файлы" in text or "## файлы" in text.lower():
            for marker in ["## Файлы", "## файлы"]:
                if marker in text:
                    text = text.replace(marker, "\n".join(new_content) + f"\n\n{marker}")
                    break
        else:
            text += "\n" + "\n".join(new_content) + "\n"

        skill_path.write_text(text, encoding="utf-8")

    return added


def apply_updates(report: AuditReport) -> dict[str, int]:
    """Apply all documentation and skill updates. Returns counts per file."""
    results: dict[str, int] = {}

    # Update documentation files
    print("  Updating REST API docs...", file=sys.stderr)
    n = update_rest_api_doc(report)
    if n:
        results["06.2_REST_API.md"] = n

    print("  Updating MCP docs...", file=sys.stderr)
    n = update_mcp_doc(report)
    if n:
        results["06.4_MCP_Server.md"] = n

    print("  Updating strategies docs...", file=sys.stderr)
    n = update_strategies_doc(report)
    if n:
        results["04.1_Обзор_стратегий.md"] = n

    print("  Updating config docs...", file=sys.stderr)
    n = update_config_doc(report)
    if n:
        results["02.2_Конфигурация.md"] = n

    print("  Updating CLI docs...", file=sys.stderr)
    n = update_cli_doc(report)
    if n:
        results["06.3_CLI.md"] = n

    print("  Updating agent docs...", file=sys.stderr)
    n = update_agent_doc(report)
    if n:
        results["05.5_Специализированные_агенты.md"] = n

    # Update skill files
    print("  Updating skills...", file=sys.stderr)
    skill_gaps: dict[str, list[Gap]] = {}
    for g in report.skill_gaps:
        for loc in g.location.split(", "):
            # Extract skill name from path
            m = re.search(r'skills/([^/]+)/', loc)
            if m:
                skill_gaps.setdefault(m.group(1), []).append(g)

    for skill_name, gaps in sorted(skill_gaps.items()):
        n = update_skill_file(skill_name, gaps)
        if n:
            results[f"skills/{skill_name}/SKILL.md"] = n

    return results


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="Audit framework code vs documentation vs skills",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--fix", action="store_true", help="Include action items in report")
    parser.add_argument("--update", action="store_true",
                        help="Auto-update docs and skills with missing features")
    parser.add_argument("--stdout", action="store_true", help="Print to stdout instead of file")
    args = parser.parse_args()

    print("Scanning codebase...", file=sys.stderr)
    report = run_audit()

    # Apply updates if requested
    if args.update:
        print("\nApplying updates...", file=sys.stderr)
        results = apply_updates(report)
        total_added = sum(results.values())
        print(f"\n{'='*60}", file=sys.stderr)
        print(f"UPDATES APPLIED: {total_added} features added to {len(results)} files",
              file=sys.stderr)
        for fname, count in sorted(results.items()):
            print(f"  {fname}: +{count}", file=sys.stderr)
        print(f"{'='*60}", file=sys.stderr)

        # Re-run audit to show updated coverage
        print("\nRe-scanning after updates...", file=sys.stderr)
        report = run_audit()

    if args.json:
        output = format_json(report)
    else:
        output = format_markdown(report, include_fix=args.fix)

    if args.stdout:
        try:
            print(output)
        except UnicodeEncodeError:
            sys.stdout.buffer.write(output.encode("utf-8"))
    else:
        out_dir = PROJECT_ROOT / "docs" / "analysis"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "AUDIT_DOCS_SKILLS.md"
        out_file.write_text(output, encoding="utf-8")
        print(f"Report saved to: {out_file}", file=sys.stderr)

    # Print summary to stderr
    s = report.summary
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"AUDIT COMPLETE: {s.get('total_features', 0)} features found", file=sys.stderr)
    print(f"  Documentation gaps: {s.get('doc_gaps', 0)}", file=sys.stderr)
    print(f"  Skill gaps:         {s.get('skill_gaps', 0)}", file=sys.stderr)
    print(f"{'='*60}", file=sys.stderr)

    for cat, stats in s.get("by_category", {}).items():
        label = CATEGORY_LABELS.get(cat, cat)
        print(
            f"  {label}: {stats['total']} total, "
            f"docs={stats['coverage_docs']}%, "
            f"skills={stats['coverage_skills']}%",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
