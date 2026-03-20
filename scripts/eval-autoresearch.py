#!/usr/bin/env python3
"""Eval system for AutoResearch v2 skill.

Measures:
- Trigger accuracy: does autoresearch correctly trigger/not-trigger?
- Domain detection: is the correct domain identified?
- Tool selection: are expected tools mentioned?

Usage:
    python scripts/eval-autoresearch.py
    python scripts/eval-autoresearch.py --verbose
"""

import json
import os
import sys

EVAL_PROMPTS_PATH = os.path.join("data", "eval", "autoresearch", "eval_prompts.json")
SKILL_MD_PATH = os.path.join(".claude", "skills", "autoresearch", "SKILL.md")

# AutoResearch trigger keywords (from SKILL.md YAML description)
TRIGGER_KEYWORDS = [
    "autoresearch", "автономный цикл", "улучши", "оптимизируй",
    "уменьши", "повысь покрытие", "ускорь", "reduce errors",
    "improve", "optimize", "benchmark", "качество кода",
    "measure and improve", "keep/revert", "автоисследование",
    "итеративно", "автономное улучшение", "улучши метрику",
    "security audit", "docstring", "покрытие тестами",
    "повысь", "уменьши ошибки",
]

# Negative signals (should NOT trigger autoresearch)
NEGATIVE_KEYWORDS = [
    "исправь", "fix", "покажи", "объясни", "создай", "напиши",
    "git", "commit", "расскажи", "настрой", "переименуй",
]

# Domain detection keywords
DOMAIN_KEYWORDS = {
    "python-quality": ["ruff", "mypy", "lint", "ошибок", "errors", "quality"],
    "python-performance": ["время ответа", "response time", "performance", "benchmark", "ускорь", "latency"],
    "bsl": ["bsl", "1с код", "bsl_analyze"],
    "skills": ["skill", "скилл", "f1", "router", "description"],
    "docs": ["docstring", "документация", "documentation", "interrogate"],
    "hooks": ["хук", "hook", "eval-hooks"],
    "security": ["security", "owasp", "stride", "bandit", "audit", "уязвимост"],
    "tests": ["тест", "test", "coverage", "покрытие", "pytest"],
    "1c-study": ["конфигурац", "1с", "изучи конфигурац", "get_metadata"],
}


def should_trigger(prompt: str) -> bool:
    """Simulate trigger detection for autoresearch skill."""
    prompt_lower = prompt.lower()

    # Check negative signals first
    neg_score = sum(1 for kw in NEGATIVE_KEYWORDS if kw in prompt_lower)
    pos_score = sum(1 for kw in TRIGGER_KEYWORDS if kw in prompt_lower)

    # Strong positive signals override
    if pos_score >= 2:
        return True
    if pos_score >= 1 and neg_score == 0:
        return True
    return False


def detect_domain(prompt: str) -> str | None:
    """Detect which autoresearch domain matches the prompt."""
    prompt_lower = prompt.lower()
    best_domain = None
    best_score = 0

    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in prompt_lower)
        if score > best_score:
            best_score = score
            best_domain = domain

    return best_domain if best_score > 0 else None


def run_eval(verbose: bool = False) -> dict:
    """Run evaluation and return metrics."""
    with open(EVAL_PROMPTS_PATH, "r", encoding="utf-8") as f:
        prompts = json.load(f)

    tp = fp = tn = fn = 0
    domain_correct = domain_total = 0
    results = []

    for p in prompts:
        prompt = p["prompt"]
        expected_trigger = p["should_trigger"]
        expected_domain = p.get("expected_domain")

        actual_trigger = should_trigger(prompt)
        actual_domain = detect_domain(prompt) if actual_trigger else None

        # Trigger accuracy
        if expected_trigger and actual_trigger:
            tp += 1
        elif expected_trigger and not actual_trigger:
            fn += 1
        elif not expected_trigger and actual_trigger:
            fp += 1
        else:
            tn += 1

        # Domain accuracy (only for true positives)
        if expected_trigger and actual_trigger and expected_domain:
            domain_total += 1
            if actual_domain == expected_domain:
                domain_correct += 1

        result = {
            "id": p["id"],
            "prompt": prompt[:60],
            "expected": expected_trigger,
            "actual": actual_trigger,
            "correct": expected_trigger == actual_trigger,
            "domain_expected": expected_domain,
            "domain_actual": actual_domain,
        }
        results.append(result)

        if verbose:
            status = "OK" if result["correct"] else "FAIL"
            mark = "+" if actual_trigger else "-"
            print(f"  [{status}] {mark} {prompt[:50]}...")
            if not result["correct"]:
                print(f"       Expected: {expected_trigger}, Got: {actual_trigger}")
            if expected_domain and actual_trigger:
                d_status = "OK" if actual_domain == expected_domain else "MISS"
                print(f"       Domain [{d_status}]: expected={expected_domain}, got={actual_domain}")

    # Metrics
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = (tp + tn) / len(prompts) if prompts else 0
    domain_acc = domain_correct / domain_total if domain_total > 0 else 0

    metrics = {
        "total": len(prompts),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "domain_accuracy": round(domain_acc, 4),
        "domain_correct": domain_correct,
        "domain_total": domain_total,
    }

    return {"metrics": metrics, "results": results}


def main():
    verbose = "--verbose" in sys.argv or "-v" in sys.argv

    if not os.path.exists(EVAL_PROMPTS_PATH):
        print(f"[ERROR] {EVAL_PROMPTS_PATH} not found")
        sys.exit(1)

    print("=== AutoResearch v2 Eval ===\n")

    data = run_eval(verbose=verbose)
    m = data["metrics"]

    print(f"\n--- Results ---")
    print(f"Total prompts: {m['total']}")
    print(f"TP={m['tp']} FP={m['fp']} TN={m['tn']} FN={m['fn']}")
    print(f"Precision: {m['precision']}")
    print(f"Recall:    {m['recall']}")
    print(f"F1:        {m['f1']}")
    print(f"Accuracy:  {m['accuracy']}")
    print(f"Domain accuracy: {m['domain_accuracy']} ({m['domain_correct']}/{m['domain_total']})")

    # Save results
    results_path = os.path.join("data", "eval", "autoresearch", "eval_results.json")
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved: {results_path}")

    # Pass/fail
    if m["f1"] >= 0.9 and m["domain_accuracy"] >= 0.85:
        print("\nSTATUS: PASS")
        return 0
    else:
        print(f"\nSTATUS: NEEDS IMPROVEMENT (F1 target: 0.9, domain target: 0.85)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
