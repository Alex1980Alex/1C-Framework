"""Rule-based verdict gauge + auto action item synthesizer.

Aggregates anomalies → PASS / WARN / FAIL verdict, top wins/issues
extraction for TL;DR, and suggested actions with skill/file pointers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .anomaly_tracker import classify_severity


@dataclass
class Verdict:
    gauge: str  # PASS | WARN | FAIL
    fails: int
    warns: int
    infos: int
    wins: list[str]
    issues: list[str]
    action_items: list[str]


_ACTION_RULES: tuple[tuple[str, str], ...] = (
    (
        "self recall@1",
        "Если коллекция SQ-quantized — проверь что probe передаёт `rescore=True` "
        "(`scripts/analyzers/indexing.py:_run_quality_probes`). Если recall < 0.85 "
        "на full-precision коллекции — investigate HNSW config (`ef_search`) "
        "и `using=` для named vectors. Skill: `qdrant-operations`.",
    ),
    (
        "dimension mismatch",
        "Silent model swap. Сверь `EmbeddingSettings.dimensions` vs collection "
        "config через `qdrant_client.get_collection()`. Возможно требуется recreate. "
        "Skill: `embedding-models`.",
    ),
    (
        "qdrant introspection failed",
        "Проверь что Qdrant контейнер запущен (`docker ps | grep qdrant`); "
        "URL в `QDRANT_URL` env. Hook `ensure-docker-qdrant.py` должен поднять "
        "его автоматически на PreToolUse — проверь логи хука.",
    ),
    (
        "heartbeat",
        "Indexer завис в одной stage > 60s. Tail `data/indexing-progress.jsonl` "
        "по `run_id` чтобы найти stuck stage. Возможны OOM / TEI 413 / GPU OOM.",
    ),
    (
        "user-defined dangling",
        "Top-15 user-defined dangling в Schema integrity section — review как "
        "typos/удалённые методы. Если ложно-positives → extend `BSL_STDLIB_NAMES` "
        "в `scripts/analyzers/graph.py`. Skill: `bsl-development`.",
    ),
    (
        "orphan",
        "Isolated nodes/modules в графе. Investigate `load_graph_to_neo4j.py` "
        "filter logic, либо реальный dead code. Cypher: "
        "`MATCH (n) WHERE NOT (n)--() RETURN n LIMIT 50`.",
    ),
    (
        "norm",
        "L2 norm drift > 25% vs prev — вероятный model swap. Сверь embedder "
        "config (`EmbeddingSettings.model`) между runs. Если интенциональный "
        "swap — baseline нужно обновить.",
    ),
    (
        "run_end отсутствует",
        "Indexer упал ДО `atexit` cleanup. Last heartbeat покажет stage. "
        "Проверь exit code; добавь `errors=N` в `tracker.stop()` summary для post-mortem.",
    ),
    (
        "stage",
        "Stage завершился с err. Точный exception в `data/indexing-progress.jsonl` "
        "по `category=stage_end ok=false`.",
    ),
    (
        "effective rank",
        "Embedding rank collapse — модель «забывает» dimensions. Возможные "
        "причины: degenerate training data, too aggressive truncation, или MRL "
        "fine-tune нужен. Skill: `embedding-models`. Defer if not chronic.",
    ),
    (
        "anisotropy",
        "Векторы сжаты в узкий конус — типичный failure mode. Mitigate post-hoc "
        "centering (`v -= mean(V)`) или whitening. Skill: `embedding-models`.",
    ),
    (
        "near-duplicate",
        "Near-duplicate chunks — chunker не дедуплицирует. Surface через "
        "`tools/bsl-semantic-diff` или recheck splitter config "
        "(`pdf_framework.processing.splitters`).",
    ),
    (
        "empty chunks",
        "Empty/near-empty chunks — parser bug. Tail `event=parse_error` для " "stack trace.",
    ),
)


def compute_verdict(anomalies: list[str]) -> Verdict:
    fails, warns, infos = 0, 0, 0
    for msg in anomalies:
        sev = classify_severity(msg)
        if sev == "FAIL":
            fails += 1
        elif sev == "WARN":
            warns += 1
        else:
            infos += 1

    if fails > 0:
        gauge = "FAIL"
    elif warns > 0:
        gauge = "WARN"
    else:
        gauge = "PASS"

    sev_rank = {"FAIL": 0, "WARN": 1, "INFO": 2}
    issues = sorted(anomalies, key=lambda m: sev_rank.get(classify_severity(m), 3))[:3]

    actions: list[str] = []
    seen: set[str] = set()
    for msg in anomalies:
        msg_l = msg.lower()
        for substr, action in _ACTION_RULES:
            if substr in msg_l and substr not in seen:
                actions.append(action)
                seen.add(substr)
                break

    return Verdict(
        gauge=gauge,
        fails=fails,
        warns=warns,
        infos=infos,
        wins=[],
        issues=issues,
        action_items=actions,
    )


def extract_wins(summary: dict[str, Any], probes: dict[str, Any] | None = None) -> list[str]:
    wins: list[str] = []
    if probes:
        recall = probes.get("self_recall_at_1")
        if isinstance(recall, int | float) and recall >= 0.95:
            wins.append(f"self recall@1 = {recall:.3f} (target ≥0.95) ✓")
        if probes.get("dimension_check") is True:
            wins.append("dimension consistency: match ✓")
        if probes.get("zero_vectors") == 0:
            wins.append("zero zero-vector points ✓")
        eff_rank = probes.get("effective_rank")
        sample = probes.get("sample_size", 0)
        if isinstance(eff_rank, int) and sample and eff_rank >= sample * 0.5:
            wins.append(f"effective rank = {eff_rank} (full dim utilization)")
    errors = summary.get("errors")
    if isinstance(errors, int) and errors == 0:
        wins.append("zero pipeline errors")
    return wins[:3]


def render_verdict_section(verdict: Verdict, anomaly_stats: dict[str, Any] | None = None) -> str:
    icon = {"PASS": "✓", "WARN": "!", "FAIL": "✗"}[verdict.gauge]
    lines = [
        f"**Verdict: {icon} {verdict.gauge}** "
        f"(FAIL={verdict.fails}, WARN={verdict.warns}, INFO={verdict.infos})",
    ]
    if anomaly_stats:
        bits = []
        if anomaly_stats.get("new"):
            bits.append(f"{anomaly_stats['new']} new")
        if anomaly_stats.get("recurring"):
            bits.append(f"{anomaly_stats['recurring']} recurring")
        if anomaly_stats.get("resolved"):
            bits.append(f"{anomaly_stats['resolved']} resolved")
        if bits:
            lines.append(f"Anomaly delta vs prev: {', '.join(bits)}.")
    if verdict.wins:
        lines.append("")
        lines.append("**Top wins:**")
        for w in verdict.wins:
            lines.append(f"- {w}")
    if verdict.issues:
        lines.append("")
        lines.append("**Top issues:**")
        for i in verdict.issues:
            lines.append(f"- {i}")
    if verdict.action_items:
        lines.append("")
        lines.append("**Action items:**")
        for a in verdict.action_items:
            lines.append(f"- {a}")
    return "\n".join(lines)
