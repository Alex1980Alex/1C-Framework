"""Audit 260705 skills, section BP G1 — линтер каталога скиллов по официальным бюджетам 2026.

Правила (источник: code.claude.com/docs + platform best-practices +
skill-framework/SkillSpec — кеш ``skills-system-best-practices-2026.md``):

  BODY500   body > 500 строк (официальный бюджет; progressive disclosure -> references/)
  NAME64    frontmatter ``name`` > 64 символов
  DESC1024  frontmatter ``description`` > 1024 символов
  TRUNC1536 description (+ when_to_use) > 1536 символов — листинг УСЕКАЕТ до 1536,
            хвост триггеров невидим модели при выборе
  NODESC    нет ``description`` (невидим для авто-активации)
  NAMEDUP   дубликат имени (SkillSpec: 46% коллизий в дикой природе)
  NAMEDIR   frontmatter ``name`` != имени каталога (роутер/enforcer ссылаются по dir-имени)
  DEADLINK  относительная markdown-ссылка из SKILL.md не резолвится
  DEEPREF   ссылка на .md глубже 1 уровня (официально: 1 уровень; глубже — модель
            читает head -100 и теряет контент) [advisory]

Advisory по умолчанию (exit 0); ``--strict`` -> exit 1 при errors (не warnings).
BODY500/DEEPREF — warnings; остальное — errors.

Usage:
  python scripts/lint_skills.py                # отчёт по всем
  python scripts/lint_skills.py --top 15       # топ-нарушители
  python scripts/lint_skills.py --json
  python scripts/lint_skills.py --strict       # CI
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"

BODY_LINES_BUDGET = 500
NAME_BUDGET = 64
DESC_BUDGET = 1024
TRUNC_BUDGET = 1536

_LINK_RE = re.compile(r"\]\(([^)#\s]+\.md)(#[^)]*)?\)")
# шаблонные плейсхолдеры в примерах (doc-to-skill/references и т.п.) — не DEADLINK
_PLACEHOLDER_LINK = re.compile(r"(^|/)(path\.md|file\.md)$|path/to/")

# G6 (audit 260705): императивы-абсолюты. Anthropic: при плато КОРОТИТЬ скилл;
# reasoning-«why» надёжнее ALWAYS/NEVER. Высокая плотность = over-constrained.
_ABSOLUTE_RE = re.compile(
    r"\b(ALWAYS|NEVER|MUST|ОБЯЗАТЕЛЬНО|ВСЕГДА|НИКОГДА|НЕЛЬЗЯ|ЗАПРЕЩЕНО|КРИТИЧЕСКИ)\b"
)
OVERCONSTRAINED_BUDGET = 25  # абсолютов на скилл; выше → advisory (текущий max каталога=12)
KNOWN_MATURITY = {"curated", "experimental", "deprecated"}  # G5 конвенция
# over-fragmentation (audit 260705): reference <CRUMB_LINES строк = крошка; >MAX_CRUMBS
# крошек = резали по-секционно ради бюджета, а не по связному знанию (анти-паттерн)
CRUMB_LINES = 60
MAX_CRUMBS = 3


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Minimal YAML-frontmatter parse: top-level key-value scalars only."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_text = text[3:end]
    body = text[end + 4 :]
    fm: dict[str, str] = {}
    for line in fm_text.splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip("\"'")
    return fm, body


def lint_one(skill_dir: Path) -> list[dict[str, Any]]:
    """Lint one skill directory; returns findings [{rule, level, detail}]."""
    findings: list[dict[str, Any]] = []
    md = skill_dir / "SKILL.md"
    if not md.exists():
        return [{"rule": "NOSKILLMD", "level": "error", "detail": "нет SKILL.md"}]
    text = md.read_text(encoding="utf-8", errors="replace")
    fm, body = parse_frontmatter(text)

    body_lines = len(body.splitlines())
    if body_lines > BODY_LINES_BUDGET:
        findings.append(
            {
                "rule": "BODY500",
                "level": "warning",
                "detail": f"body {body_lines} строк (бюджет {BODY_LINES_BUDGET}; progressive disclosure)",
            }
        )

    name = fm.get("name", "")
    desc = fm.get("description", "")
    when = fm.get("when_to_use", "")

    if name and len(name) > NAME_BUDGET:
        findings.append(
            {
                "rule": "NAME64",
                "level": "error",
                "detail": f"name {len(name)} симв. (бюджет {NAME_BUDGET})",
            }
        )
    if not desc:
        findings.append(
            {
                "rule": "NODESC",
                "level": "error",
                "detail": "нет description — невидим для авто-активации",
            }
        )
    else:
        if len(desc) > DESC_BUDGET:
            findings.append(
                {
                    "rule": "DESC1024",
                    "level": "error",
                    "detail": f"description {len(desc)} симв. (бюджет {DESC_BUDGET})",
                }
            )
        combined = len(desc) + len(when)
        if combined > TRUNC_BUDGET:
            findings.append(
                {
                    "rule": "TRUNC1536",
                    "level": "error",
                    "detail": (
                        f"description+when_to_use {combined} симв. > {TRUNC_BUDGET} — "
                        f"листинг УСЕКАЕТ, хвост триггеров невидим при выборе"
                    ),
                }
            )
    if name and name != skill_dir.name:
        findings.append(
            {
                "rule": "NAMEDIR",
                "level": "error",
                "detail": f"frontmatter name={name!r} != каталог {skill_dir.name!r}",
            }
        )

    for m in _LINK_RE.finditer(text):
        raw = m.group(1)
        if raw.startswith(("http://", "https://")):
            continue
        # url-decode перед резолвом: пути в доках несут %20 (пробел в
        # "framework documentation") и др. — без unquote всё это false-positive DEADLINK
        target = unquote(raw)
        if _PLACEHOLDER_LINK.search(target):
            continue  # шаблонный пример, не реальная ссылка
        resolved = (md.parent / target).resolve()
        if not resolved.exists():
            findings.append(
                {"rule": "DEADLINK", "level": "error", "detail": f"битая ссылка -> {target}"}
            )
        elif not target.startswith(".."):
            depth = len(Path(target).parts) - 1
            if depth > 1 and target.endswith(".md"):
                findings.append(
                    {
                        "rule": "DEEPREF",
                        "level": "warning",
                        "detail": f"ссылка глубже 1 уровня: {target} (официально: 1 уровень от SKILL.md)",
                    }
                )

    # G6: over-constrained — избыток императивов-абсолютов
    n_abs = len(_ABSOLUTE_RE.findall(body))
    if n_abs > OVERCONSTRAINED_BUDGET:
        findings.append(
            {
                "rule": "OVERCONSTRAINED",
                "level": "warning",
                "detail": f"{n_abs} императивов-абсолютов (>{OVERCONSTRAINED_BUDGET}); при плато КОРОТИ, reasoning-why > ALWAYS/NEVER",
            }
        )
    # G5: незнакомое значение maturity (если поле есть — должно быть из конвенции)
    mat = fm.get("maturity")
    if mat and mat not in KNOWN_MATURITY:
        findings.append(
            {
                "rule": "BADMATURITY",
                "level": "warning",
                "detail": f"maturity={mat!r} не из {sorted(KNOWN_MATURITY)}",
            }
        )
    # over-fragmentation: избыток крошечных references = резали по-секционно, не по знанию
    refs = (
        list((skill_dir / "references").glob("*.md")) if (skill_dir / "references").is_dir() else []
    )
    if refs:
        crumbs = [
            r.name
            for r in refs
            if len(r.read_text(encoding="utf-8", errors="replace").splitlines()) < CRUMB_LINES
        ]
        if len(crumbs) > MAX_CRUMBS:
            findings.append(
                {
                    "rule": "FRAGMENTED",
                    "level": "warning",
                    "detail": (
                        f"{len(crumbs)} references-крошек (<{CRUMB_LINES} строк) из {len(refs)} — "
                        f"дели по связному знанию, не по-секционно; консолидируй крошки"
                    ),
                }
            )
    return findings


def lint_all(skills_dir: Path = SKILLS_DIR) -> dict[str, Any]:
    """Lint the whole catalog; adds cross-skill NAMEDUP findings."""
    findings_map: dict[str, list[dict[str, Any]]] = {}
    names_seen: dict[str, list[str]] = {}
    # G4/G5 adoption-инвентарь frontmatter-2026 (не флаг per-skill — сводка)
    inv = {"when_to_use": 0, "paths": 0, "maturity": {}}
    for d in sorted(skills_dir.iterdir()):
        if not d.is_dir() or d.name.startswith((".", "_")):
            continue
        findings = lint_one(d)
        md = d / "SKILL.md"
        if md.exists():
            fm, _ = parse_frontmatter(md.read_text(encoding="utf-8", errors="replace"))
            eff_name = fm.get("name") or d.name
            names_seen.setdefault(eff_name, []).append(d.name)
            if fm.get("when_to_use"):
                inv["when_to_use"] += 1
            if fm.get("paths"):
                inv["paths"] += 1
            mat = fm.get("maturity") or "(unmarked)"
            inv["maturity"][mat] = inv["maturity"].get(mat, 0) + 1
        if findings:
            findings_map[d.name] = findings
    for eff_name, dirs in names_seen.items():
        if len(dirs) > 1:
            for dname in dirs:
                findings_map.setdefault(dname, []).append(
                    {
                        "rule": "NAMEDUP",
                        "level": "error",
                        "detail": f"имя {eff_name!r} у {len(dirs)} скиллов: {dirs}",
                    }
                )
    total = len(names_seen)
    errors = sum(1 for fl in findings_map.values() for f in fl if f["level"] == "error")
    warnings = sum(1 for fl in findings_map.values() for f in fl if f["level"] == "warning")
    return {
        "skills_total": total,
        "skills_with_findings": len(findings_map),
        "errors": errors,
        "warnings": warnings,
        "per_skill": findings_map,
        "frontmatter_2026": inv,
    }


def _print_utf8(s: str) -> None:
    sys.stdout.buffer.write((s + "\n").encode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Skill catalog linter (audit 260705 BP G1)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="exit 1 при errors (CI)")
    ap.add_argument("--top", type=int, default=0, help="топ-N нарушителей")
    args = ap.parse_args()

    report = lint_all()
    if args.json:
        _print_utf8(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_utf8(
            "# skill-lint: {} скиллов, {} с находками ({} errors / {} warnings)".format(
                report["skills_total"],
                report["skills_with_findings"],
                report["errors"],
                report["warnings"],
            )
        )
        items = sorted(
            report["per_skill"].items(),
            key=lambda kv: -sum(1 for f in kv[1] if f["level"] == "error"),
        )
        if args.top:
            items = items[: args.top]
        for sk_name, findings in items:
            for f in findings:
                mark = "E" if f["level"] == "error" else "W"
                _print_utf8("  [{}] {}: {} — {}".format(mark, sk_name, f["rule"], f["detail"]))
        inv = report.get("frontmatter_2026", {})
        _print_utf8(
            "# frontmatter-2026 adoption (G4/G5): when_to_use={} paths={} maturity={}".format(
                inv.get("when_to_use", 0), inv.get("paths", 0), inv.get("maturity", {})
            )
        )
    if args.strict and report["errors"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
