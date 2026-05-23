"""Markdown + JSON writer for ReportSpec, with _latest_<subject>.md copy and
append-only ``data/reports/index.jsonl`` registry."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from .base import ReportSpec


def _ts_slug(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%Y%m%d_%H%M%S")
    except ValueError:
        return datetime.now().strftime("%Y%m%d_%H%M%S")


def _safe_subject(subject: str) -> str:
    cleaned = re.sub(r"[^\w\-.]+", "_", subject, flags=re.UNICODE).strip("_")
    return cleaned or "unknown"


def write_report(spec: ReportSpec, out_dir: Path) -> tuple[Path, Path]:
    """Persist ``spec`` to disk. Returns ``(md_path, json_path)``."""
    mode_dir = out_dir / spec.mode
    mode_dir.mkdir(parents=True, exist_ok=True)

    subj = _safe_subject(spec.subject)
    slug = f"{subj}_{_ts_slug(spec.generated_at)}"
    md_path = mode_dir / f"{slug}.md"
    json_path = mode_dir / f"{slug}.json"
    latest_path = mode_dir / f"_latest_{subj}.md"

    md_path.write_text(_render_markdown(spec), encoding="utf-8")
    json_path.write_text(
        json.dumps(spec.raw, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    shutil.copyfile(md_path, latest_path)

    index_path = out_dir / "index.jsonl"
    entry = {
        "ts": spec.generated_at,
        "mode": spec.mode,
        "subject": spec.subject,
        "run_id": spec.run_id,
        "md": str(md_path.relative_to(out_dir.parent)).replace("\\", "/"),
        "anomalies": len(spec.anomalies),
        "duration_sec": spec.duration_sec,
        "summary": spec.summary,
    }
    with index_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    return md_path, json_path


def _render_markdown(spec: ReportSpec) -> str:
    lines: list[str] = []
    icon = "Indexing" if spec.mode == "indexing" else "Graph"
    lines.append(f"# {icon} report — `{spec.subject}`")
    lines.append("")
    lines.append(f"- **run_id:** `{spec.run_id}`")
    lines.append(f"- **generated_at:** {spec.generated_at}")
    lines.append(f"- **indexer:** `{spec.indexer_script}`")
    if spec.duration_sec is not None:
        lines.append(f"- **duration:** {_fmt_duration(spec.duration_sec)}")
    lines.append("")

    if spec.summary:
        lines.append("## TL;DR")
        lines.append("")
        for k, v in spec.summary.items():
            lines.append(f"- **{k}:** {v}")
        lines.append("")

    if spec.anomalies:
        lines.append(f"## Anomalies ({len(spec.anomalies)})")
        lines.append("")
        for a in spec.anomalies:
            lines.append(f"- {a}")
        lines.append("")

    for heading, body in spec.sections:
        lines.append(f"## {heading}")
        lines.append("")
        lines.append((body or "_(пусто)_").rstrip())
        lines.append("")

    return "\n".join(lines)


def _fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(int(seconds), 60)
    if m < 60:
        return f"{m}m{s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h{m:02d}m{s:02d}s"
