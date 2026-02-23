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

import hashlib
import json
import os
import re
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


def _generate_prompt_id(prompt: str) -> str:
    """Generate short deterministic prompt_id from timestamp + prompt."""
    ts = datetime.now().isoformat()
    raw = f"{ts}|{prompt[:80]}"
    return hashlib.md5(raw.encode("utf-8", errors="replace")).hexdigest()[:8]


def _log_accuracy_recommend(prompt_id: str, skills: list[str], prompt_snippet: str) -> None:
    """Write recommend event to data/skill-accuracy.jsonl."""
    try:
        project_dir = os.path.dirname(os.path.dirname(_HOOK_DIR))
        log_path = os.path.join(project_dir, "data", "skill-accuracy.jsonl")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        entry = {
            "ts": datetime.now().isoformat(),
            "type": "recommend",
            "prompt_id": prompt_id,
            "skills": skills,
            "prompt": prompt_snippet[:120],
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # Never block


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

    # Regex to strip file paths from prompt (prevents false matches on paths)
    _PATH_RE = re.compile(r'[a-zA-Z]:\\[^\s>]*|/[^\s>]*\.\w+')

    def execute(self, inp: HookInput) -> HookOutput | None:
        prompt = inp.prompt
        if not prompt or len(prompt) < 3:
            return None

        # TIER 2A: Skip IDE events (VS Code metadata, not user intent)
        prompt_stripped = prompt.strip()
        if prompt_stripped.startswith((
            "<ide_", "<ide_opened_file", "<ide_selection",
            "<file_", "<selection", "<cursor",
        )):
            return None
        # Skip prompts that are mostly XML tags (IDE metadata dumps)
        if len(prompt_stripped) > 20 and prompt_stripped.count("<") > len(prompt_stripped) / 10:
            return None

        # Load config
        config = _load_config()
        if not config or "bundles" not in config:
            return None

        bundles = config["bundles"]
        min_score = config.get("min_score", 1)
        max_bundles = config.get("max_bundles", 3)

        # TIER 2A: Strip file paths to prevent false matches
        # (e.g. "d:\1с-framework\" triggering "1с" keyword)
        prompt_lower = self._PATH_RE.sub('', prompt.lower())

        # Collect all single-word keywords for fuzzy matching
        all_keywords = []
        for bundle in bundles.values():
            all_keywords.extend(bundle.get("keywords", []))

        # --- Layer A: Phrase matching ---
        scores: dict[str, int] = {}
        for name, bundle in bundles.items():
            score = 0
            # Standard keywords: weight 1 (backward compatible)
            for kw in bundle.get("keywords", []):
                if kw in prompt_lower:
                    score += 1
            # TIER 2B: Weighted keywords (higher-value, specific terms)
            for kw, weight in bundle.get("weighted_keywords", {}).items():
                if kw.lower() in prompt_lower:
                    score += weight
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

        # --- TIER 3: Affinity injection ---
        affinities = config.get("affinities", {})
        affine_skills: list[str] = []
        for skill in required_skills:
            for related in affinities.get(skill, []):
                if (related not in required_skills
                        and related not in optional_skills
                        and related not in affine_skills):
                    affine_skills.append(related)
        # Add affine skills to optional (free injection)
        optional_skills.extend(affine_skills)

        # --- TIER 3: Session deduplication ---
        try:
            from shared.session_state import (
                get_already_recommended,
                record_recommendation,
            )
            already = get_already_recommended()
            new_required = [s for s in required_skills if s not in already]
            new_optional = [s for s in optional_skills if s not in already]

            # Record all recommendations (including already-recommended for stats)
            all_to_record = required_skills + optional_skills
            if all_to_record:
                record_recommendation(all_to_record)

            # If all skills already recommended this session, skip message
            if not new_required and not new_optional:
                return None

            # Use filtered lists for the message
            required_skills = new_required
            optional_skills = new_optional
        except Exception:
            pass  # Session dedup is optional; graceful degradation

        # --- TIER 4: Detect workflow type from matched bundles ---
        detected_workflow = None
        for name, _score in top_bundles:
            wf = bundles[name].get("workflow")
            if wf:
                detected_workflow = wf
                break  # First workflow bundle wins (highest score)

        # --- Log match ---
        _log_match(prompt_lower[:80], matched_bundle_names, required_skills)

        # --- Accuracy tracking: generate prompt_id and log recommend event ---
        all_recommended = list(required_skills) + list(optional_skills)
        if all_recommended:
            prompt_id = _generate_prompt_id(prompt)
            try:
                from shared.session_state import set_prompt_id
                set_prompt_id(prompt_id)
            except Exception:
                pass
            _log_accuracy_recommend(prompt_id, all_recommended, prompt_lower[:120])

        # --- Build systemMessage ---
        # Separate domain bundles from workflow bundles for display
        domain_bundle_names = [
            n for n in matched_bundle_names
            if "workflow" not in bundles.get(n, {})
        ]

        parts = [
            f"[SKILL-ROUTER] Bundles: {', '.join(matched_bundle_names)}",
        ]

        if required_skills:
            parts.append(
                f"Рекомендованные скиллы: {', '.join(required_skills)}"
            )

        if optional_skills:
            parts.append(
                f"Опционально (по контексту): {', '.join(optional_skills)}"
            )

        if affine_skills:
            parts.append(
                f"Аффинные скиллы (связанные): {', '.join(affine_skills)}"
            )

        # TIER 4: Append workflow instruction if detected
        if detected_workflow:
            parts.append(self._workflow_instruction(detected_workflow))

        return HookOutput().system_message("\n".join(parts))


    # --- Workflow instruction templates ---
    _WORKFLOW_TEMPLATES = {
        "research": (
            "\n[WORKFLOW: RESEARCH] Задача на исследование.\n"
            "Определи домен и используй соответствующий skill:\n"
            "- 1С-платформа -> `1c-doc-research`\n"
            "- RAG/ML/Python -> `tech-research`\n"
            "- Архитектура -> `architecture-research`\n"
            "Начни с проверки кеша соответствующего skill."
        ),
        "brainstorm": (
            "\n[WORKFLOW: BRAINSTORM] Задача на генерацию идей.\n"
            "Используй skill `task-evaluation` -- Brainstorm Workflow:\n"
            "1. Формулировка проблемы (что, контекст, критерии)\n"
            "2. Генерация 3-5 подходов\n"
            "3. Evaluation matrix (таблица сравнения)\n"
            "4. Рекомендация с обоснованием\n"
            "5. Сохрани решение как ADR"
        ),
        "hybrid": (
            "\n[WORKFLOW: HYBRID] Задача Research + Brainstorm.\n"
            "Используй skill `task-evaluation` -- Hybrid Workflow:\n"
            "ЧАСТЬ 1 (Research): domain skill -- фазы 0-5\n"
            "ЧАСТЬ 2 (Brainstorm): task-evaluation -- фазы 1-5\n"
            "  1. Формулировка проблемы\n"
            "  2. Генерация 3-5 подходов\n"
            "  3. Evaluation matrix\n"
            "  4. Рекомендация\n"
            "  5. Сохрани как ADR"
        ),
    }

    def _workflow_instruction(self, workflow: str) -> str:
        """Get workflow instruction template by type."""
        return self._WORKFLOW_TEMPLATES.get(workflow, "")


if __name__ == "__main__":
    SkillRouter().run()
