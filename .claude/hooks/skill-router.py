#!/usr/bin/env python3
"""
Hook: skill-router
Event: UserPromptSubmit
Matcher: (none — fires on every user prompt)
Purpose: Config-driven skill routing. Reads skill-router-config.json,
         matches prompt keywords to bundles, recommends relevant skills.
Timeout: 5s

Complements research-task-detector.py:
  - skill-router → DATA-DRIVEN, says WHICH skills to load
  - research-task-detector → CODE-DRIVEN, says WHICH WORKFLOW to use
"""

import json
import os
import sys
from datetime import datetime

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if os.path.isdir(os.path.join(_USER_HOOKS, "shared")):
    sys.path.insert(0, _USER_HOOKS)
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput

# --- Config path resolution ---
_CONFIG_LOCATIONS = [
    os.path.join(_HOOK_DIR, "..", "skills", "skill-router-config.json"),
    os.path.join(_HOOK_DIR, "..", "skill-router-config.json"),
]

# Lazy-load fuzzy matcher
_fuzzy_matcher = None


def _get_fuzzy_matcher(all_keywords: list[str]):
    """Create FuzzyMatcher with all single-word keywords from config."""
    global _fuzzy_matcher
    if _fuzzy_matcher is None:
        try:
            from shared.fuzzy_match import FuzzyMatcher
            # Only single words for fuzzy (multi-word phrases use exact match)
            single_words = [kw for kw in all_keywords if " " not in kw]
            if single_words:
                _fuzzy_matcher = FuzzyMatcher(
                    keywords=single_words,
                    fuzzy_threshold=78,
                )
            else:
                _fuzzy_matcher = False
        except Exception:
            _fuzzy_matcher = False
    return _fuzzy_matcher if _fuzzy_matcher is not False else None


def _log_match(prompt_snippet: str, bundles: list[str], skills: list[str]) -> None:
    """Append match info to data/skill-router.log for monitoring (Phase 10)."""
    try:
        project_dir = os.path.dirname(os.path.dirname(_HOOK_DIR))
        log_path = os.path.join(project_dir, "data", "skill-router.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} | bundles={','.join(bundles)} | skills={','.join(skills)} | prompt={prompt_snippet}\n"
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass  # Logging must never block the hook


def _load_config() -> dict | None:
    """Load skill-router-config.json from known locations."""
    for path in _CONFIG_LOCATIONS:
        abs_path = os.path.abspath(path)
        if os.path.isfile(abs_path):
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return None
    return None


class SkillRouter(BaseHook):
    """Config-driven skill router via keyword bundle matching."""

    def execute(self, inp: HookInput) -> HookOutput | None:
        prompt = inp.prompt
        if not prompt or len(prompt) < 3:
            return None

        # Load config
        config = _load_config()
        if not config or "bundles" not in config:
            return None

        bundles = config["bundles"]
        min_score = config.get("min_score", 1)
        max_bundles = config.get("max_bundles", 3)

        prompt_lower = prompt.lower()

        # Collect all single-word keywords for fuzzy matching
        all_keywords = []
        for bundle in bundles.values():
            all_keywords.extend(bundle.get("keywords", []))

        # --- Layer A: Phrase matching ---
        scores: dict[str, int] = {}
        for name, bundle in bundles.items():
            score = 0
            for kw in bundle.get("keywords", []):
                if kw in prompt_lower:
                    score += 1
            scores[name] = score

        # --- Layer B: Fuzzy single-word matching ---
        fuzzy = _get_fuzzy_matcher(all_keywords)
        if fuzzy is not None:
            matches = fuzzy.match_prompt(prompt)
            # Map matched keywords back to bundles
            for matched_kw, _score in matches:
                for name, bundle in bundles.items():
                    if matched_kw in bundle.get("keywords", []):
                        # Only add +1 if Layer A didn't already match this keyword
                        if matched_kw not in prompt_lower:
                            scores[name] = scores.get(name, 0) + 1

        # --- Filter bundles above min_score ---
        matched = {
            name: score for name, score in scores.items()
            if score >= min_score
        }

        if not matched:
            return None

        # --- Rank and limit bundles ---
        ranked = sorted(matched.items(), key=lambda x: x[1], reverse=True)
        top_bundles = ranked[:max_bundles]

        # --- Collect skills (dedup, preserve order) ---
        required_skills: list[str] = []
        optional_skills: list[str] = []
        matched_bundle_names: list[str] = []

        for name, _score in top_bundles:
            matched_bundle_names.append(name)
            bundle = bundles[name]

            for skill in bundle.get("skills", []):
                if skill not in required_skills:
                    required_skills.append(skill)

            for skill in bundle.get("optional", []):
                if skill not in optional_skills and skill not in required_skills:
                    optional_skills.append(skill)

        # Final dedup: remove from optional anything that ended up in required
        optional_skills = [s for s in optional_skills if s not in required_skills]

        # --- Log match ---
        _log_match(prompt_lower[:80], matched_bundle_names, required_skills)

        # --- Build systemMessage ---
        parts = [
            f"[SKILL-ROUTER] Bundles: {', '.join(matched_bundle_names)}",
            f"Рекомендованные скиллы: {', '.join(required_skills)}",
        ]

        if optional_skills:
            parts.append(
                f"Опционально (по контексту): {', '.join(optional_skills)}"
            )

        return HookOutput().system_message("\n".join(parts))


if __name__ == "__main__":
    SkillRouter().run()
