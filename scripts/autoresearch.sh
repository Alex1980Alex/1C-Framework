#!/usr/bin/env bash
# autoresearch.sh — AutoResearch v2: Three-Agent Engine (Linux/Mac)
#
# Usage:
#   ./scripts/autoresearch.sh -d skills -n 15
#   ./scripts/autoresearch.sh -d python-quality -t 0
#   ./scripts/autoresearch.sh -d skills -n 20 -t 0.85

set -euo pipefail

DOMAIN=""
MAX_ITERATIONS=10
TARGET=""
COMPARE_EVERY=5
IDEA_DIR=""

usage() {
    echo "AutoResearch v2 — Three-Agent Engine"
    echo ""
    echo "Usage: $0 -d <domain> [-n max_iterations] [-t target] [-c compare_every] [-i idea_dir]"
    echo ""
    echo "Domains: skills, skill-health, python-quality, bsl, docs, hooks, security, tests"
    echo ""
    echo "Options:"
    echo "  -d  Domain (required unless -i specified)"
    echo "  -n  Max iterations (default: 10)"
    echo "  -t  Target metric value"
    echo "  -c  Compare every N iterations (default: 5)"
    echo "  -i  Custom idea directory (with autoresearch.md)"
    exit 1
}

while getopts "d:n:t:c:i:h" opt; do
    case $opt in
        d) DOMAIN="$OPTARG" ;;
        n) MAX_ITERATIONS="$OPTARG" ;;
        t) TARGET="$OPTARG" ;;
        c) COMPARE_EVERY="$OPTARG" ;;
        i) IDEA_DIR="$OPTARG" ;;
        h) usage ;;
        *) usage ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

mkdir -p data

# --- Session directory ---
if [ -n "$IDEA_DIR" ]; then
    SESSION_DIR="$IDEA_DIR"
    [ ! -f "$SESSION_DIR/autoresearch.md" ] && echo "[ERROR] $SESSION_DIR/autoresearch.md not found" && exit 1
elif [ -n "$DOMAIN" ]; then
    SESSION_DIR="data/autoresearch"
    mkdir -p "$SESSION_DIR"
else
    usage
fi

JSONL_PATH="$SESSION_DIR/autoresearch.jsonl"
TSV_PATH="$SESSION_DIR/autoresearch-results.tsv"
MD_PATH="$SESSION_DIR/autoresearch.md"
LOG_DIR="$SESSION_DIR/logs"
mkdir -p "$LOG_DIR"

# --- TSV Header ---
if [ ! -f "$TSV_PATH" ]; then
    printf "iteration\ttimestamp\tcommit\tchange\tmetric_before\tmetric_after\tdelta\ttests\tverdict\treason\n" > "$TSV_PATH"
fi

BASELINE_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BEST_METRIC=""
PLATEAU=0
START_ITER=0

# Resume from existing state
if [ -f "$MD_PATH" ]; then
    START_ITER=$(grep -oP 'Iteration:\s*\K\d+' "$MD_PATH" 2>/dev/null || echo 0)
    BEST_METRIC=$(grep -oP 'BestMetric:\s*\K[\d.]+' "$MD_PATH" 2>/dev/null || echo "")
    PLATEAU=$(grep -oP 'Plateau:\s*\K\d+' "$MD_PATH" 2>/dev/null || echo 0)
    BC=$(grep -oP 'BaselineCommit:\s*\K\w+' "$MD_PATH" 2>/dev/null || echo "")
    [ -n "$BC" ] && BASELINE_COMMIT="$BC"
fi

echo "=== AutoResearch v2: Three-Agent Engine ==="
echo "Domain: ${DOMAIN:-custom} | Max: $MAX_ITERATIONS | Target: ${TARGET:-none}"
echo "Session: $SESSION_DIR | Baseline: $BASELINE_COMMIT"
echo ""

export RALPH_ENABLED=1

for ((i=START_ITER+1; i<=MAX_ITERATIONS; i++)); do
    TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo ""
    echo "=== Iteration $i / $MAX_ITERATIONS [$TS] ==="

    COMMIT_BEFORE=$(git rev-parse --short HEAD 2>/dev/null)

    # AGENT 1: EXECUTOR
    echo "  [EXECUTOR] Making change..."
    EXECUTOR_PROMPT="You are EXECUTOR in AutoResearch v2. Iteration $i of $MAX_ITERATIONS. Domain: ${DOMAIN:-custom}. Make ONE atomic change. Git commit with prefix [AR-$i]. Do NOT run tests."
    claude -p "$EXECUTOR_PROMPT" --dangerously-skip-permissions > "$LOG_DIR/executor_$i.txt" 2>&1 || true
    echo "  [EXECUTOR] Done."

    COMMIT_AFTER=$(git rev-parse --short HEAD 2>/dev/null)

    if [ "$COMMIT_AFTER" = "$COMMIT_BEFORE" ]; then
        echo "  [SKIP] No commit made."
        PLATEAU=$((PLATEAU + 1))
        continue
    fi

    # AGENT 2: REVIEWER
    echo "  [REVIEWER] Verifying..."
    REVIEWER_PROMPT="You are REVIEWER in AutoResearch v2. Iteration $i. Check git diff HEAD~1. Run verify command. Output: METRIC: <number>, TESTS: PASS/FAIL, VERDICT: KEEP/REVERT/FIX/SKIP, REASON: <text>. If REVERT: git revert HEAD --no-edit."
    claude -p "$REVIEWER_PROMPT" --dangerously-skip-permissions > "$LOG_DIR/reviewer_$i.txt" 2>&1 || true

    REVIEWER_OUT=$(cat "$LOG_DIR/reviewer_$i.txt")
    VERDICT=$(echo "$REVIEWER_OUT" | grep -oP 'VERDICT:\s*\K(KEEP|REVERT|FIX|SKIP)' | head -1)
    METRIC=$(echo "$REVIEWER_OUT" | grep -oP 'METRIC:\s*\K[\d.]+' | head -1)

    echo "  [REVIEWER] Verdict: ${VERDICT:-unknown} | Metric: ${METRIC:-N/A}"

    case "$VERDICT" in
        KEEP)
            if [ -n "$METRIC" ] && [ -z "$BEST_METRIC" -o "$(echo "$METRIC > $BEST_METRIC" | bc -l 2>/dev/null || echo 0)" = "1" ]; then
                BEST_METRIC="$METRIC"
                PLATEAU=0
            else
                PLATEAU=$((PLATEAU + 1))
            fi
            ;;
        *) PLATEAU=$((PLATEAU + 1)) ;;
    esac

    # AGENT 3: COMPARATOR (every N iterations)
    if [ $((i % COMPARE_EVERY)) -eq 0 ]; then
        echo "  [COMPARATOR] Blind A/B..."
        COMP_PROMPT="You are COMPARATOR. Compare baseline ($BASELINE_COMMIT) vs current code. Score quality/readability (1-10). Output JSON with winner."
        claude -p "$COMP_PROMPT" --dangerously-skip-permissions > "$LOG_DIR/comparator_$i.txt" 2>&1 || true
        echo "  [COMPARATOR] Done."
    fi

    # LOG
    COMMIT_HASH=$(git rev-parse --short HEAD 2>/dev/null)
    printf "%d\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" \
        "$i" "$TS" "$COMMIT_HASH" "" "$BEST_METRIC" "$METRIC" "" "${VERDICT:-unknown}" "" >> "$TSV_PATH"

    # Update state
    cat > "$MD_PATH" <<EOF
# AutoResearch Session
Domain: ${DOMAIN:-custom}
Iteration: $i
BestMetric: $BEST_METRIC
Plateau: $PLATEAU
Target: $TARGET
BaselineCommit: $BASELINE_COMMIT
Updated: $TS
EOF

    # Target check
    if [ -n "$TARGET" ] && [ -n "$BEST_METRIC" ]; then
        if [ "$(echo "$BEST_METRIC >= $TARGET" | bc -l 2>/dev/null || echo 0)" = "1" ]; then
            echo "  Target reached: $BEST_METRIC >= $TARGET"
            break
        fi
    fi

    # Plateau check
    if [ "$PLATEAU" -ge 5 ]; then
        echo "  Plateau: 5 iterations without improvement."
        break
    fi

    sleep 2
done

echo ""
echo "=== AutoResearch v2 Complete ==="
echo "Domain: ${DOMAIN:-custom} | Best: ${BEST_METRIC:-N/A} | Target: ${TARGET:-N/A}"
