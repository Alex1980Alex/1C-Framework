"""Hermes Phase 2.1 — Eval Benchmark for DSPy Migrated RAG Agents.

Compares baseline (LangChain-only) vs candidate (DSPy) backends on:
- Grader: precision, recall, F1, accuracy (binary)
- Hallucination: F1 binary, accuracy on grounded:bool
- All: latency p50/p95

Usage:
    python scripts/eval_hermes_phase2.py --baseline langchain --output-dir data/eval/hermes
    python scripts/eval_hermes_phase2.py --candidate dspy --output-dir data/eval/hermes
    python scripts/eval_hermes_phase2.py --report data/eval/hermes/report.md
    python scripts/eval_hermes_phase2.py --smoke   # 10 queries, <30s
"""

import argparse
import asyncio
import json
import os
import random
import statistics
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Any
from unittest.mock import patch

from langchain_anthropic import ChatAnthropic

from src.pdf_framework.agents.rag.nodes.grader import grade_documents
from src.pdf_framework.agents.rag.nodes.hallucination_checker import (
    check_hallucination,
)
from src.pdf_framework.agents.rag.state import RAGState
from src.pdf_framework.config import SelfRAGSettings
from src.pdf_framework.schemas.documents import (
    DocumentChunk,
    SearchResponse,
    SearchResult,
)

# ---------------------------------------------------------------------------
# Backend forcing via monkeypatch
# ---------------------------------------------------------------------------

_GRADER_MOD = "src.pdf_framework.agents.rag.nodes.grader"
_REWRITER_MOD = "src.pdf_framework.agents.rag.nodes.rewriter"
_HALL_MOD = "src.pdf_framework.agents.rag.nodes.hallucination_checker"
_PROMPTS_MOD = "src.pdf_framework.prompts"
_ADAPTER_MOD = "src.shared.llm_rotation.adapter"

_METRIC_MODULES = (_GRADER_MOD, _REWRITER_MOD, _HALL_MOD)

# JSON keys that hold raw result lists (not metrics)
_RESULT_KEYS = {"grader_results", "hall_results"}


class BackendConfig:
    """Defines which backends are enabled for a run."""

    def __init__(self, cheap_llm: bool, dspy: bool, label: str):
        self.cheap_llm = cheap_llm
        self.dspy = dspy
        self.label = label


BASELINE = BackendConfig(cheap_llm=False, dspy=False, label="langchain")
CANDIDATE = BackendConfig(cheap_llm=False, dspy=True, label="dspy")


def _build_backend_patches(backend: BackendConfig) -> list:
    """Build monkeypatch objects forcing a specific backend."""
    patches = []
    for mod in _METRIC_MODULES:
        patches.append(
            patch(f"{_ADAPTER_MOD}.is_cheap_llm_enabled", return_value=backend.cheap_llm)
        )
        patches.append(
            patch(f"{mod}.is_cheap_llm_enabled", return_value=backend.cheap_llm)
        )
        patches.append(
            patch(f"{_PROMPTS_MOD}.is_dspy_available", return_value=backend.dspy)
        )
        patches.append(
            patch(f"{mod}.is_dspy_available", return_value=backend.dspy)
        )
    return patches


# ---------------------------------------------------------------------------
# State construction helpers
# ---------------------------------------------------------------------------

def make_grader_state(query: str, context: str) -> RAGState:
    chunk = DocumentChunk(
        id="eval-chunk-001",
        content=context,
        document_id="eval-doc",
    )
    result = SearchResult(chunk=chunk, score=0.8)
    response = SearchResponse(query=query, results=[result])
    return RAGState(
        question=query,
        original_question=query,
        search_response=response,
    )


def make_hallucination_state(answer: str, context: str) -> RAGState:
    return RAGState(
        question="eval question",
        original_question="eval question",
        answer=answer,
        context=context,
    )


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def precision_recall_f1(tp: int, fp: int, fn: int) -> dict[str, float]:
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {"precision": prec, "recall": rec, "f1": f1}


def compute_grader_metrics(results: list[dict]) -> dict[str, float]:
    """Binary accuracy + P/R/F1 on relevant detection."""
    clean = [r for r in results if "error" not in r]
    if not clean:
        return {"accuracy": 0.0, "binary_precision": 0.0, "binary_recall": 0.0, "binary_f1": 0.0}

    correct = sum(1 for r in clean if r["predicted_relevant"] == r["expected_relevant"])
    accuracy = correct / len(clean)

    tp = sum(1 for r in clean if r["predicted_relevant"] and r["expected_relevant"])
    fp = sum(1 for r in clean if r["predicted_relevant"] and not r["expected_relevant"])
    fn = sum(1 for r in clean if not r["predicted_relevant"] and r["expected_relevant"])
    binary = precision_recall_f1(tp, fp, fn)
    return {"accuracy": accuracy, **{f"binary_{k}": v for k, v in binary.items()}}


def compute_hallucination_metrics(results: list[dict]) -> dict[str, float]:
    """F1 and accuracy on grounded (not hallucinated) detection."""
    clean = [r for r in results if "error" not in r]
    if not clean:
        return {"accuracy": 0.0, "grounded_precision": 0.0, "grounded_recall": 0.0, "grounded_f1": 0.0}

    correct = sum(1 for r in clean if r["predicted_grounded"] == r["expected_grounded"])
    accuracy = correct / len(clean)

    tp = sum(1 for r in clean if r["predicted_grounded"] and r["expected_grounded"])
    fp = sum(1 for r in clean if r["predicted_grounded"] and not r["expected_grounded"])
    fn = sum(1 for r in clean if not r["predicted_grounded"] and r["expected_grounded"])
    binary = precision_recall_f1(tp, fp, fn)
    return {"accuracy": accuracy, **{f"grounded_{k}": v for k, v in binary.items()}}


def compute_latency_metrics(latencies: list[float]) -> dict[str, float]:
    if not latencies:
        return {"p50": 0.0, "p95": 0.0, "mean": 0.0}
    sorted_l = sorted(latencies)
    n = len(sorted_l)
    p95_idx = min(int(n * 0.95), n - 1)
    return {
        "p50": sorted_l[int(n * 0.5)],
        "p95": sorted_l[p95_idx],
        "mean": statistics.mean(sorted_l),
    }


def bootstrap_ci(values: list[float], n_boot: int = 1000, ci: float = 0.95) -> dict[str, float]:
    """Bootstrap confidence interval for mean of values."""
    if not values:
        return {"lo": 0.0, "hi": 0.0, "mean": 0.0}
    rng = random.Random(42)
    means = []
    n = len(values)
    for _ in range(n_boot):
        sample = [values[rng.randint(0, n - 1)] for _ in range(n)]
        means.append(statistics.mean(sample))
    means.sort()
    alpha = (1 - ci) / 2
    lo = means[int(n_boot * alpha)]
    hi = means[int(n_boot * (1 - alpha))]
    return {"lo": lo, "hi": hi, "mean": statistics.mean(values)}


# ---------------------------------------------------------------------------
# Eval runners
# ---------------------------------------------------------------------------

async def run_grader_eval(
    entries: list[dict],
    llm: ChatAnthropic,
    settings: SelfRAGSettings,
    backend: BackendConfig,
) -> tuple[list[dict], list[float]]:
    results = []
    latencies = []

    with ExitStack() as stack:
        for p in _build_backend_patches(backend):
            stack.enter_context(p)

        for entry in entries:
            state = make_grader_state(entry["query"], entry["context"])
            t0 = time.perf_counter()
            try:
                out = await grade_documents(state, llm, settings)
                latency = time.perf_counter() - t0
                latencies.append(latency)

                graded = out.get("graded_documents", [])
                predicted = graded[0]["is_relevant"] if graded else True
                results.append({
                    "id": entry["id"],
                    "predicted_relevant": predicted,
                    "expected_relevant": entry["expected_is_relevant"],
                    "latency": latency,
                })
            except Exception as exc:
                latencies.append(time.perf_counter() - t0)
                results.append({
                    "id": entry["id"],
                    "predicted_relevant": True,
                    "expected_relevant": entry["expected_is_relevant"],
                    "latency": 0.0,
                    "error": str(exc),
                })

    return results, latencies


async def run_hallucination_eval(
    entries: list[dict],
    llm: ChatAnthropic,
    settings: SelfRAGSettings,
    backend: BackendConfig,
) -> tuple[list[dict], list[float]]:
    results = []
    latencies = []

    with ExitStack() as stack:
        for p in _build_backend_patches(backend):
            stack.enter_context(p)

        for entry in entries:
            answer = entry.get("hallucination_answer", "")
            context = entry.get("hallucination_context", entry.get("context", ""))
            if not answer:
                continue

            state = make_hallucination_state(answer, context)
            t0 = time.perf_counter()
            try:
                out = await check_hallucination(state, llm, settings)
                latency = time.perf_counter() - t0
                latencies.append(latency)

                predicted_grounded = not out.get("is_hallucinated", False)
                expected_grounded = entry.get("grounded", True)
                results.append({
                    "id": entry["id"],
                    "predicted_grounded": predicted_grounded,
                    "expected_grounded": expected_grounded,
                    "latency": latency,
                })
            except Exception as exc:
                latencies.append(time.perf_counter() - t0)
                results.append({
                    "id": entry["id"],
                    "predicted_grounded": True,
                    "expected_grounded": entry.get("grounded", True),
                    "latency": 0.0,
                    "error": str(exc),
                })

    return results, latencies


# ---------------------------------------------------------------------------
# Main eval orchestrator
# ---------------------------------------------------------------------------

async def run_eval(
    dataset_path: str,
    backend: BackendConfig,
    output_dir: str,
    smoke: bool = False,
) -> dict[str, Any]:
    entries = []
    with open(dataset_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    if smoke:
        random.Random(42).shuffle(entries)
        entries = entries[:10]

    llm = ChatAnthropic(model="claude-sonnet-4-5-20250929", temperature=0.0, max_tokens=256)
    settings = SelfRAGSettings()

    # Configure DSPy LM for candidate runs
    if backend.dspy:
        import dspy
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            print("[WARN] ANTHROPIC_API_KEY not set, DSPy will use fallback chain")
        else:
            lm = dspy.LM(model="anthropic/claude-sonnet-4-5-20250929", api_key=api_key, max_tokens=256)
            dspy.configure(lm=lm)
            print("[DSPY] Configured with anthropic/claude-sonnet-4-5-20250929")

    # Grader eval — all entries
    print(f"[GRADER] Running on {len(entries)} entries (backend={backend.label})...")
    grader_results, grader_latencies = await run_grader_eval(entries, llm, settings, backend)
    grader_metrics = compute_grader_metrics(grader_results)
    grader_latency = compute_latency_metrics(grader_latencies)

    # Hallucination eval — entries with hallucination_answer
    hall_entries = [e for e in entries if e.get("hallucination_answer")]
    print(f"[HALLUCINATION] Running on {len(hall_entries)} entries (backend={backend.label})...")
    hall_results, hall_latencies = await run_hallucination_eval(
        hall_entries, llm, settings, backend,
    )
    hall_metrics = compute_hallucination_metrics(hall_results)
    hall_latency = compute_latency_metrics(hall_latencies)

    # Bootstrap CI for key metrics
    grader_acc_ci = bootstrap_ci([int(r["predicted_relevant"] == r["expected_relevant"]) for r in grader_results])
    hall_acc_ci = bootstrap_ci([int(r["predicted_grounded"] == r["expected_grounded"]) for r in hall_results])

    report = {
        "backend": backend.label,
        "n_entries": len(entries),
        "smoke": smoke,
        "grader": {**grader_metrics, "latency": grader_latency, "accuracy_ci": grader_acc_ci},
        "hallucination": {**hall_metrics, "latency": hall_latency, "accuracy_ci": hall_acc_ci},
        "grader_results": grader_results,
        "hall_results": hall_results,
    }

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    suffix = "smoke" if smoke else backend.label
    result_file = out_path / f"{suffix}.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print(f"[DONE] Results saved to {result_file}")

    return report


def generate_report(baseline_path: str, candidate_path: str, report_path: str) -> None:
    with open(baseline_path, encoding="utf-8") as f:
        baseline = json.load(f)
    with open(candidate_path, encoding="utf-8") as f:
        candidate = json.load(f)

    lines = ["# Hermes Phase 2.1 — DSPy Migration Eval Report\n"]
    lines.append(f"- Baseline: `{baseline['backend']}` ({baseline['n_entries']} entries)")
    lines.append(f"- Candidate: `{candidate['backend']}` ({candidate['n_entries']} entries)")
    lines.append("")

    for component in ["grader", "hallucination"]:
        lines.append(f"## {component.title()}\n")
        lines.append("| Metric | Baseline | Candidate | Delta | CI (candidate) |")
        lines.append("|--------|----------|-----------|-------|----------------|")

        b = baseline[component]
        c = candidate[component]
        skip_keys = {"latency", "accuracy_ci"} | _RESULT_KEYS
        all_keys = set(b.keys()) - skip_keys
        for lat_key in b.get("latency", {}):
            all_keys.add(f"latency.{lat_key}")

        for key in sorted(all_keys):
            if key.startswith("latency."):
                subkey = key.split(".", 1)[1]
                bv = b.get("latency", {}).get(subkey, 0)
                cv = c.get("latency", {}).get(subkey, 0)
            else:
                bv = b.get(key, 0)
                cv = c.get(key, 0)

            if not isinstance(bv, (int, float)) or not isinstance(cv, (int, float)):
                continue
            delta = cv - bv
            ci_info = c.get("accuracy_ci", {})
            ci_str = f"[{ci_info.get('lo', 0):.3f}, {ci_info.get('hi', 0):.3f}]" if key == "accuracy" else "—"
            lines.append(f"| {key} | {bv:.4f} | {cv:.4f} | {delta:+.4f} | {ci_str} |")
        lines.append("")

    # Verdict
    b_acc = baseline["grader"]["accuracy"]
    c_acc = candidate["grader"]["accuracy"]
    regression = b_acc - c_acc > 0.05
    verdict = "ROLLBACK" if regression else "PASS"
    lines.append(f"## Verdict: **{verdict}**\n")
    if regression:
        lines.append(f"Grader accuracy regressed by >5%: {b_acc:.4f} -> {c_acc:.4f}")
    else:
        lines.append(f"No >5% regression detected. Grader: {b_acc:.4f} -> {c_acc:.4f}")
    lines.append("")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[REPORT] Written to {report_path}")


def main():
    parser = argparse.ArgumentParser(description="Hermes Phase 2.1 Eval Benchmark")
    parser.add_argument("--baseline", choices=["langchain"], help="Run baseline eval")
    parser.add_argument("--candidate", choices=["dspy"], help="Run candidate eval")
    parser.add_argument("--output-dir", default="data/eval/hermes", help="Output directory")
    parser.add_argument("--dataset", default="data/eval/hermes/phase2_eval_set.jsonl")
    parser.add_argument("--report", help="Generate comparison report from baseline+candidate")
    parser.add_argument("--smoke", action="store_true", help="Quick run: 10 queries, <30s")
    args = parser.parse_args()

    if args.smoke:
        asyncio.run(run_eval(args.dataset, BASELINE, args.output_dir, smoke=True))
        return

    if args.baseline:
        asyncio.run(run_eval(args.dataset, BASELINE, args.output_dir))
        return

    if args.candidate:
        asyncio.run(run_eval(args.dataset, CANDIDATE, args.output_dir))
        return

    if args.report:
        baseline_file = Path(args.output_dir) / "langchain.json"
        candidate_file = Path(args.output_dir) / "dspy.json"
        generate_report(str(baseline_file), str(candidate_file), args.report)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
