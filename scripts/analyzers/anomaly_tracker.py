"""Persistent anomaly registry for closing the analytical loop.

After each analyzer run, write detected anomalies to
``data/reports/anomalies.jsonl`` with stable fingerprints. Recurring
anomalies bump their counter; anomalies absent from the current run are
auto-marked as ``resolved``. Optionally, new WARN/FAIL anomalies trigger
``gh issue create`` if ``ANALYZER_GH_REPO`` env var is set and ``gh`` CLI
is available.

Schema (one JSON record per line, full registry rewritten atomically):
    fingerprint           — stable sha1 hash (subject + numeric-normalized message)
    subject               — collection / graph name
    message               — latest human-readable text
    severity              — INFO | WARN | FAIL
    status                — active | resolved
    first_seen            — ISO ts when first detected
    last_seen             — ISO ts of latest active run
    last_run_id           — run_id that last surfaced this anomaly
    resolved_at           — ISO ts when marked resolved (if status=resolved)
    recurrence_count      — int, ≥1
    github_issue          — URL if auto-created
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

SEVERITY_FAIL_TOKENS = (
    "fail",
    "mismatch",
    "corruption",
    "abort",
    "broken",
    "error",
    "не найден",
    "не удалось",
    "missing",
    "crashed",
)
SEVERITY_WARN_TOKENS = (
    "drift",
    "orphan",
    "dangling",
    "warn",
    "below",
    "above",
    "выше",
    "ниже",
    "stale",
    "deprecated",
    "skipped",
    "incomplete",
    "вероятные",
)


def _anomaly_fingerprint(subject: str, message: str) -> str:
    """Hash subject + numerically-normalized message → stable identity across runs."""
    normalized = re.sub(r"\d+(?:[.,]\d+)?", "N", message)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    h = hashlib.sha1(f"{subject}::{normalized}".encode()).hexdigest()[:12]
    return h


def classify_severity(message: str) -> str:
    m = message.lower()
    if any(tok in m for tok in SEVERITY_FAIL_TOKENS):
        return "FAIL"
    if any(tok in m for tok in SEVERITY_WARN_TOKENS):
        return "WARN"
    return "INFO"


class AnomalyTracker:
    def __init__(self, reports_dir: Path) -> None:
        self.path = reports_dir / "anomalies.jsonl"
        self.gh_repo = os.environ.get("ANALYZER_GH_REPO", "").strip()

    def _load_index(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        index: dict[str, dict[str, Any]] = {}
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                fp = rec.get("fingerprint")
                if fp:
                    index[fp] = rec
        except OSError:
            pass
        return index

    def record(self, subject: str, anomalies: list[str], run_id: str) -> dict[str, Any]:
        """Update registry. Returns counts {new, recurring, resolved, fingerprints, chronic}."""
        index = self._load_index()
        now = datetime.now().isoformat(timespec="seconds")
        new_count = 0
        recurring_count = 0
        fingerprints: list[str] = []

        for msg in anomalies:
            fp = _anomaly_fingerprint(subject, msg)
            fingerprints.append(fp)
            severity = classify_severity(msg)
            existing = index.get(fp)
            if existing and existing.get("status") == "active":
                existing["last_seen"] = now
                existing["last_run_id"] = run_id
                existing["recurrence_count"] = int(existing.get("recurrence_count", 1)) + 1
                existing["message"] = msg
                existing["severity"] = severity
                recurring_count += 1
            else:
                first_seen = (existing or {}).get("first_seen", now)
                prior_count = int((existing or {}).get("recurrence_count", 0))
                record: dict[str, Any] = {
                    "fingerprint": fp,
                    "subject": subject,
                    "message": msg,
                    "severity": severity,
                    "status": "active",
                    "first_seen": first_seen,
                    "last_seen": now,
                    "last_run_id": run_id,
                    "recurrence_count": prior_count + 1,
                    "github_issue": (existing or {}).get("github_issue"),
                }
                if existing and existing.get("status") == "resolved":
                    record["reopened_at"] = now
                index[fp] = record
                if not existing:
                    new_count += 1
                    self._maybe_open_issue(record)

        resolved_count = 0
        for fp_old, rec_old in list(index.items()):
            if (
                rec_old.get("subject") == subject
                and rec_old.get("status") == "active"
                and fp_old not in fingerprints
            ):
                rec_old["status"] = "resolved"
                rec_old["resolved_at"] = now
                rec_old["last_run_id_at_resolution"] = run_id
                resolved_count += 1

        self._rewrite(index)

        chronic = sorted(
            (
                r
                for r in index.values()
                if r.get("subject") == subject
                and r.get("status") == "active"
                and int(r.get("recurrence_count", 1)) >= 3
            ),
            key=lambda r: -int(r.get("recurrence_count", 1)),
        )
        return {
            "new": new_count,
            "recurring": recurring_count,
            "resolved": resolved_count,
            "fingerprints": fingerprints,
            "chronic": chronic[:10],
        }

    def summary_section(self, subject: str) -> str:
        index = self._load_index()
        relevant = [r for r in index.values() if r.get("subject") == subject]
        if not relevant:
            return "_Нет истории аномалий для этого subject._"
        active = [r for r in relevant if r.get("status") == "active"]
        resolved = [r for r in relevant if r.get("status") == "resolved"]
        lines = [
            f"- **total tracked:** {len(relevant)}",
            f"- **currently active:** {len(active)}",
            f"- **resolved (historical):** {len(resolved)}",
        ]
        chronic = sorted(
            (r for r in active if int(r.get("recurrence_count", 1)) >= 3),
            key=lambda r: -int(r.get("recurrence_count", 1)),
        )
        if chronic:
            lines.append("- **chronic (≥3 recurrences):**")
            for r in chronic[:5]:
                gh = ""
                if r.get("github_issue"):
                    gh = f" — {r['github_issue']}"
                lines.append(
                    f"  - `{r['fingerprint']}` ×{r['recurrence_count']} "
                    f"({r['severity']}): {r['message'][:100]}{gh}"
                )
        return "\n".join(lines)

    def _rewrite(self, index: dict[str, dict[str, Any]]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                for rec in index.values():
                    fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
            os.replace(tmp, self.path)
        except OSError:
            pass

    def _maybe_open_issue(self, record: dict[str, Any]) -> None:
        if not self.gh_repo:
            return
        if record["severity"] not in ("WARN", "FAIL"):
            return
        title = f"[auto-reports] {record['subject']}: {record['message'][:80]}"
        body = (
            f"Auto-detected anomaly by `scripts/analyze_run.py`.\n\n"
            f"- **fingerprint:** `{record['fingerprint']}`\n"
            f"- **severity:** {record['severity']}\n"
            f"- **subject:** {record['subject']}\n"
            f"- **first_seen:** {record['first_seen']}\n"
            f"- **last_run_id:** {record['last_run_id']}\n\n"
            f"## Message\n{record['message']}\n\n"
            f"## Resolution\n"
            f"Fix the underlying issue, then re-run indexing/graph build. "
            f"The analyzer will mark this anomaly as `resolved` on the next "
            f"run that doesn't surface it.\n\n"
            f"Tracked in `data/reports/anomalies.jsonl`."
        )
        try:
            result = subprocess.run(
                [
                    "gh",
                    "issue",
                    "create",
                    "--repo",
                    self.gh_repo,
                    "--title",
                    title,
                    "--body",
                    body,
                    "--label",
                    "auto-reports",
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if result.returncode == 0:
                url = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
                if url:
                    record["github_issue"] = url
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
