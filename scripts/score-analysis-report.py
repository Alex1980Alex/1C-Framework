#!/usr/bin/env python3
"""Parse ANALYSIS-REPORT.md and compute structured quality score (0-100).

Usage:
    python scripts/score-analysis-report.py path/to/ANALYSIS-REPORT.md

Output format (parseable by Reviewer):
    METRIC: {score}
    BREAKDOWN: req={N}/30 fields={N}/25 patterns={N}/20 sql={N}/15 questions={N}/10
    GAPS: [{...}, ...]
"""

import json
import re
import sys
from pathlib import Path

# Section heading patterns (## N. or ### N.N)
_SECTION_RE = re.compile(r"^#{1,3}\s+(\d+(?:\.\d+)?)\.?\s")
_MOD_POINT_RE = re.compile(
    r"^###\s+Точка\s+(?:модификации\s+)?(\d+)\s*:", re.IGNORECASE
)
_REQ_REF_RE = re.compile(r"\[REQ-(\d+)\]")
_SQL_OPEN_RE = re.compile(r"^```sql\b")
_SQL_CLOSE_RE = re.compile(r"^```\s*$")


def _current_section(line: str, prev: str) -> str:
    """Return section id like '1.1', '4', '6' or prev if not a heading."""
    m = _SECTION_RE.match(line.strip())
    return m.group(1) if m else prev


def parse_report(text: str) -> dict:
    """Extract structure from ANALYSIS-REPORT.md."""
    lines = text.split("\n")
    section = ""
    in_sql_block = False

    requirements: list[str] = []
    modification_points = 0
    sql_queries = 0
    verified_fields = 0
    unverified_fields = 0
    patterns = 0
    validated_queries = 0
    open_questions = 0
    all_req_refs: set[int] = set()

    for line in lines:
        stripped = line.strip()
        section = _current_section(stripped, section)

        # SQL code blocks
        if _SQL_OPEN_RE.match(stripped):
            sql_queries += 1
            in_sql_block = True
            continue
        if in_sql_block:
            if _SQL_CLOSE_RE.match(stripped):
                in_sql_block = False
            continue

        # Requirements (section 1.1) — numbered, bulleted, or table rows
        if section == "1.1":
            is_req = (
                re.match(r"^\d+\.", stripped)
                or stripped.startswith("- ")
                or re.match(r"^\|\s*\d+\s*\|", stripped)
            )
            if is_req and stripped and not stripped.startswith("|---"):
                requirements.append(stripped)

        # Open questions (section 6)
        if section == "6":
            if re.match(r"^\d+\.", stripped) or stripped.startswith("- "):
                if stripped:
                    open_questions += 1

        # Modification points
        if _MOD_POINT_RE.match(stripped):
            modification_points += 1

        # Markers (anywhere in document)
        if "\u2713 get_metadata" in stripped:
            verified_fields += 1
        if "\u2717 \u043d\u0435 \u043f\u0440\u043e\u0432\u0435\u0440\u0435\u043d\u043e" in stripped:
            unverified_fields += 1
        if "\u2713 pattern" in stripped:
            patterns += 1
        if "\u2713 execute_query" in stripped:
            validated_queries += 1

        # [REQ-N] refs (anywhere in document)
        for m in _REQ_REF_RE.finditer(stripped):
            all_req_refs.add(int(m.group(1)))

    # Count how many requirements (by 1-based index) are referenced
    requirements_with_refs = sum(
        1 for i in range(1, len(requirements) + 1) if i in all_req_refs
    )

    return {
        "total_requirements": len(requirements),
        "requirements_with_refs": requirements_with_refs,
        "modification_points": modification_points,
        "sql_queries": sql_queries,
        "verified_fields": verified_fields,
        "unverified_fields": unverified_fields,
        "patterns": patterns,
        "validated_queries": validated_queries,
        "open_questions": open_questions,
        "requirement_refs": sorted(all_req_refs),
    }


def compute_score(parsed: dict) -> dict:
    """Compute 5-component quality score and gaps list."""
    gaps: list[dict] = []
    total_req = parsed["total_requirements"]
    req_refs = parsed["requirements_with_refs"]

    # 1. Requirements coverage (0-30)
    if total_req > 0:
        req_score = min((req_refs / total_req) * 30, 30)
        missing = total_req - req_refs
        if missing > 0:
            gaps.append({
                "type": "requirement_gap",
                "detail": f"{missing} requirement(s) missing [REQ-N] reference in plan",
            })
    else:
        req_score = 0

    # 2. Fields verified (0-25)
    verified = parsed["verified_fields"]
    unverified = parsed["unverified_fields"]
    total_fields = verified + unverified
    if total_fields > 0:
        fields_score = min((verified / total_fields) * 25, 25)
        if unverified > 0:
            gaps.append({
                "type": "field_unverified",
                "detail": f"{unverified} field(s) not verified via get_metadata",
            })
    else:
        fields_score = 25  # no fields to check = full score

    # 3. Patterns found (0-20)
    mod_pts = parsed["modification_points"]
    pat = parsed["patterns"]
    if mod_pts > 0:
        patterns_score = min((pat / mod_pts) * 20, 20)
        missing_pat = mod_pts - pat
        if missing_pat > 0:
            gaps.append({
                "type": "pattern_missing",
                "detail": f"{missing_pat} modification point(s) without pattern from config",
            })
    else:
        patterns_score = 20

    # 4. SQL validated (0-15)
    sql_total = parsed["sql_queries"]
    sql_valid = parsed["validated_queries"]
    if sql_total > 0:
        sql_score = min((sql_valid / sql_total) * 15, 15)
        invalid = sql_total - sql_valid
        if invalid > 0:
            gaps.append({
                "type": "query_invalid",
                "detail": f"{invalid} SQL query(ies) not validated via execute_query",
            })
    else:
        sql_score = 15

    # 5. Open questions resolved (0-10)
    oq = parsed["open_questions"]
    questions_score = min((1 - oq / max(oq + 3, 1)) * 10, 10)
    if oq > 0:
        gaps.append({
            "type": "open_question",
            "detail": f"{oq} open question(s) remaining",
        })

    total = round(req_score + fields_score + patterns_score + sql_score + questions_score)

    return {
        "total": total,
        "req": round(req_score),
        "fields": round(fields_score),
        "patterns": round(patterns_score),
        "sql": round(sql_score),
        "questions": round(questions_score),
        "gaps": gaps,
    }


def format_output(score: dict) -> str:
    """Format for Reviewer parsing."""
    lines = [
        f"METRIC: {score['total']}",
        f"BREAKDOWN: req={score['req']}/30 fields={score['fields']}/25 "
        f"patterns={score['patterns']}/20 sql={score['sql']}/15 "
        f"questions={score['questions']}/10",
        f"GAPS: {json.dumps(score['gaps'], ensure_ascii=False)}",
    ]
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python scripts/score-analysis-report.py path/to/ANALYSIS-REPORT.md",
            file=sys.stderr,
        )
        sys.exit(1)

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    text = filepath.read_text(encoding="utf-8")
    parsed = parse_report(text)
    score = compute_score(parsed)
    print(format_output(score))


if __name__ == "__main__":
    main()
