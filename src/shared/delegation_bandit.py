"""
DelegationBandit — LinUCB contextual bandit for Z.AI delegation routing.

4 arms: Soft, Medium, Hard, Never.
Feature extraction from context dict. State persistence via pickle.
Warm-up: rule-based <20, hybrid 20-50, pure bandit >50.
"""

import argparse
import json
import logging
import pickle
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

ACTIONS = ["Soft", "Medium", "Hard", "Never"]
N_ARMS = len(ACTIONS)
ACTION_INDEX = {a: i for i, a in enumerate(ACTIONS)}
FEATURE_DIM = 6

CONTENT_TYPE_MAP = {"docs": 0, "code": 1, "test": 2, "config": 3, "template": 4}
DOMAIN_MAP = {"roadmap": 0, "skill": 1, "hook": 2, "src": 3, "docs": 4, "test": 5, "bsl": 6}

_STATE_DIR = Path(__file__).resolve().parent.parent.parent / "data"
STATE_FILE = _STATE_DIR / "delegation-bandit.pkl"
OUTCOMES_FILE = _STATE_DIR / "delegation-outcomes.jsonl"


def _extract_features(ctx: dict[str, object]) -> np.ndarray:
    """Convert context dict to 6-dim feature vector."""
    ext = ctx.get("file_extension", "")
    return np.array([
        CONTENT_TYPE_MAP.get(ctx.get("content_type", ""), 4),
        min(ctx.get("estimated_lines", ctx.get("line_count", 0)) / 200.0, 1.0),
        1.0 if ctx.get("has_code") else 0.0,
        1.0 if ctx.get("has_architecture") else 0.0,
        DOMAIN_MAP.get(ctx.get("domain", ""), 4) / 7.0,
        1.0 if ext in (".py", ".ts", ".bsl", ".js", ".go") else 0.0,
    ], dtype=np.float64)


class LinUCBModel:
    """Disjoint LinUCB: separate A (d×d), b (d×1) per arm."""

    def __init__(self, d: int = FEATURE_DIM, alpha: float = 1.5):
        self.d = d
        self.alpha = alpha
        self.A = [np.eye(d, dtype=np.float64) for _ in range(N_ARMS)]
        self.b = [np.zeros(d, dtype=np.float64) for _ in range(N_ARMS)]
        self.n_updates = [0] * N_ARMS

    def predict(self, x: np.ndarray) -> tuple[int, np.ndarray]:
        """Return (best_arm_idx, all_ucb_scores)."""
        scores = np.zeros(N_ARMS, dtype=np.float64)
        for a in range(N_ARMS):
            A_inv = np.linalg.inv(self.A[a])
            theta = A_inv @ self.b[a]
            scores[a] = theta @ x + self.alpha * np.sqrt(x @ A_inv @ x)
        return int(np.argmax(scores)), scores

    def update(self, x: np.ndarray, arm: int, reward: float):
        self.A[arm] += np.outer(x, x)
        self.b[arm] += reward * x
        self.n_updates[arm] += 1


class DelegationBandit:
    """Contextual bandit for delegation classification with warm-up strategy."""

    def __init__(self, state_path: str = ""):
        self.state_path = Path(state_path) if state_path else STATE_FILE
        self.model = LinUCBModel()
        self.total_updates = 0
        self._cached_outcome_count = -1  # -1 = not yet counted
        self._load_state()

    def _count_outcomes(self) -> int:
        if self._cached_outcome_count >= 0:
            return self._cached_outcome_count
        if not OUTCOMES_FILE.exists():
            self._cached_outcome_count = 0
            return 0
        try:
            with open(OUTCOMES_FILE, encoding="utf-8") as f:
                self._cached_outcome_count = sum(1 for _ in f)
                return self._cached_outcome_count
        except Exception:
            return 0

    @property
    def mode(self) -> str:
        n = self._count_outcomes()
        if n < 20:
            return "WARM-UP"
        elif n < 50:
            return "HYBRID"
        return "AUTONOMOUS"

    def predict(self, context: dict[str, object]) -> tuple[str, float]:
        """Predict delegation level. Returns (action, confidence)."""
        mode = self.mode
        rule_action = _rule_based_classify(context)

        if mode == "WARM-UP":
            return rule_action, 0.0

        x = _extract_features(context)
        arm_idx, scores = self.model.predict(x)
        bandit_action = ACTIONS[arm_idx]

        if mode == "HYBRID":
            # Majority: if bandit agrees with rules, use it; else rules win
            if bandit_action == rule_action:
                return bandit_action, 0.75
            return rule_action, 0.5

        # AUTONOMOUS — confidence from UCB gap
        sorted_scores = np.sort(scores)[::-1]
        gap = sorted_scores[0] - sorted_scores[1]
        confidence = float(min(gap / max(abs(sorted_scores[0]), 0.01), 1.0))

        # Low-confidence fallback to rules
        if confidence < 0.1:
            return rule_action, 0.3
        return bandit_action, confidence

    def update(self, context: dict[str, object], action: str, reward: float):
        """Update model with observed outcome."""
        if action not in ACTION_INDEX:
            return
        x = _extract_features(context)
        arm_idx = ACTION_INDEX[action]
        self.model.update(x, arm_idx, reward)
        self.total_updates += 1
        self._save_state()

    def train_from_outcomes(self, max_rows: int = 0) -> int:
        """Batch-train from existing outcomes JSONL."""
        if not OUTCOMES_FILE.exists():
            return 0

        trained = 0
        with open(OUTCOMES_FILE, encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line.strip())
                    classification = row.get("classification")
                    if classification not in ACTION_INDEX:
                        continue
                    reward = row.get("reward", 1.0 if row.get("delegated") else 0.5)
                    if reward is None:
                        reward = 0.5
                    # Merge context_features with top-level fields
                    ctx = dict(row.get("context_features", {}))
                    ctx.setdefault("content_type", row.get("content_type", "docs"))
                    ctx.setdefault("domain", row.get("domain", "other"))
                    ctx.setdefault("estimated_lines", row.get("estimated_lines", 0))

                    x = _extract_features(ctx)
                    self.model.update(x, ACTION_INDEX[classification], reward)
                    trained += 1
                    if 0 < max_rows <= trained:
                        break
                except (json.JSONDecodeError, KeyError):
                    continue

        self.total_updates += trained
        self._save_state()
        return trained

    def get_stats(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "total_outcomes": self._count_outcomes(),
            "total_updates": self.total_updates,
            "arm_updates": {ACTIONS[i]: self.model.n_updates[i] for i in range(N_ARMS)},
        }

    def _save_state(self):
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_path, "wb") as f:
                pickle.dump({
                    "A": [a.tolist() for a in self.model.A],
                    "b": [b.tolist() for b in self.model.b],
                    "n_updates": self.model.n_updates,
                    "total_updates": self.total_updates,
                }, f)
        except Exception as e:
            logger.warning("Failed to save bandit state: %s", e)

    def _load_state(self):
        if not self.state_path.exists():
            return
        try:
            with open(self.state_path, "rb") as f:
                state = pickle.load(f)
            if "A" in state and "b" in state:
                self.model.A = [np.array(a) for a in state["A"]]
                self.model.b = [np.array(b) for b in state["b"]]
                self.model.n_updates = state.get("n_updates", [0] * N_ARMS)
                self.total_updates = state.get("total_updates", 0)
        except Exception as e:
            logger.warning("Failed to load bandit state: %s", e)


def _rule_based_classify(context: dict[str, object]) -> str:
    """Fallback rule-based classification (mirrors z-ai-delegation-enforcer)."""
    domain = context.get("domain", "other")
    content_type = context.get("content_type", "other")
    lines = context.get("estimated_lines", context.get("line_count", 0))

    if domain in ("hook", "skill"):
        return "Never"
    if content_type == "code":
        return "Hard"
    if content_type == "docs":
        return "Medium" if lines > 30 else "Soft"
    if content_type == "config":
        return "Soft"
    return "Medium"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

    parser = argparse.ArgumentParser(description="Delegation Bandit CLI")
    sub = parser.add_subparsers(dest="cmd")

    train_p = sub.add_parser("train", help="Batch train from outcomes JSONL")
    train_p.add_argument("--max-rows", type=int, default=0)

    sub.add_parser("stats", help="JSON stats")
    sub.add_parser("dashboard", help="Formatted dashboard")

    args = parser.parse_args()
    bandit = DelegationBandit()

    if args.cmd == "train":
        n = bandit.train_from_outcomes(max_rows=args.max_rows)
        print(f"Trained on {n} outcomes")
    elif args.cmd == "stats":
        print(json.dumps(bandit.get_stats(), indent=2))
    elif args.cmd == "dashboard":
        stats = bandit.get_stats()
        print("=== Delegation Learning Dashboard ===")
        print(f"Mode: {stats['mode']} ({stats['total_outcomes']} outcomes, {stats['total_updates']} updates)")
        print("\n=== Arm Distribution ===")
        for arm, count in stats["arm_updates"].items():
            bar = "#" * min(count // 5, 40)
            print(f"  {arm:8s}: {count:4d} {bar}")
    else:
        parser.print_help()
