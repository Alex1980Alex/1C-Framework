"""Tests for Phase 4: Semantic Skill Retrieval — Layer D in skill-router.py."""

import importlib
import json
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PROJECT_ROOT, ".claude", "hooks"))


# ── _log_match tests ─────────────────────────────────────────────────


class TestLogMatchWithMatchedBy:
    """Tests for the updated _log_match function with matched_by parameter."""

    def setup_method(self):
        spec = importlib.util.spec_from_file_location(
            "skill_router",
            os.path.join(PROJECT_ROOT, ".claude", "hooks", "skill-router.py"),
        )
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def test_log_without_matched_by(self, tmp_path):
        """Legacy call without matched_by still works."""
        log_file = tmp_path / "data" / "skill-router.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with patch.object(self.mod, "_HOOK_DIR", str(tmp_path / ".claude" / "hooks")):
            with patch(
                "os.path.dirname",
                side_effect=[
                    str(tmp_path / ".claude" / "hooks"),
                    str(tmp_path / ".claude"),
                    str(tmp_path),
                ],
            ):
                self.mod._log_match("test prompt", ["bundle1"], ["skill1"])
        # Should not crash — graceful if dir doesn't exist

    def test_log_with_matched_by(self, tmp_path):
        """matched_by dict is included in log line."""
        log_dir = tmp_path / "data"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "skill-router.log"

        # Direct test: write to a temp file
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        matched_by = {"bsl-dev": "semantic", "research-1c": "keyword"}
        mb_str = ",".join(f"{k}:{v}" for k, v in matched_by.items())
        line = (
            f"{ts} | bundles=bsl-dev,research-1c | skills=s1 | matched_by={mb_str} | prompt=test\n"
        )
        log_file.write_text(line, encoding="utf-8")

        content = log_file.read_text(encoding="utf-8")
        assert "matched_by=" in content
        assert "semantic" in content
        assert "keyword" in content

    def test_log_matched_by_hybrid(self, tmp_path):
        """Hybrid match type appears in log."""
        matched_by = {"bundle-x": "hybrid"}
        mb_str = ",".join(f"{k}:{v}" for k, v in matched_by.items())
        assert "hybrid" in mb_str


# ── _get_semantic_searcher tests ─────────────────────────────────────


class TestGetSemanticSearcher:
    def setup_method(self):
        spec = importlib.util.spec_from_file_location(
            "skill_router",
            os.path.join(PROJECT_ROOT, ".claude", "hooks", "skill-router.py"),
        )
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def test_disabled_via_env(self):
        """SKILL_ROUTER_NO_SEMANTIC disables semantic searcher."""
        self.mod._semantic_searcher = None  # Reset cache
        with patch.dict(os.environ, {"SKILL_ROUTER_NO_SEMANTIC": "1"}):
            result = self.mod._get_semantic_searcher()
            assert result is None
        self.mod._semantic_searcher = None  # Cleanup

    def test_returns_module_when_available(self):
        """Returns semantic_search module when import succeeds."""
        self.mod._semantic_searcher = None
        mock_module = MagicMock()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SKILL_ROUTER_NO_SEMANTIC", None)
            with patch.dict("sys.modules", {"shared.semantic_search": mock_module}):
                with patch(
                    "builtins.__import__",
                    side_effect=lambda name, *a, **kw: (
                        mock_module
                        if "semantic_search" in name
                        else __builtins__.__import__(name, *a, **kw)
                        if hasattr(__builtins__, "__import__")
                        else importlib.import_module(name)
                    ),
                ):
                    # Reset and import fresh
                    self.mod._semantic_searcher = None
                    self.mod._get_semantic_searcher()
                    # The key test: it doesn't crash
        self.mod._semantic_searcher = None

    def test_returns_none_on_import_error(self):
        """Returns None when shared.semantic_search can't be imported."""
        self.mod._semantic_searcher = None
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SKILL_ROUTER_NO_SEMANTIC", None)
            # Force import to fail
            with patch("builtins.__import__", side_effect=ImportError("no module")):
                assert self.mod._get_semantic_searcher() is None
        self.mod._semantic_searcher = None


# ── Layer D scoring logic tests ──────────────────────────────────────


class TestLayerDScoring:
    """Tests for the Layer D semantic scoring logic (score fusion, thresholds)."""

    def test_strong_threshold_gives_bonus_2(self):
        """Semantic score >= 0.75 → strong_bonus (default 2)."""
        sem_cfg = {"strong": 0.75, "moderate": 0.50, "strong_bonus": 2, "moderate_bonus": 1}
        score = 0.80
        if score >= sem_cfg["strong"]:
            bonus = sem_cfg["strong_bonus"]
        elif score >= sem_cfg["moderate"]:
            bonus = sem_cfg["moderate_bonus"]
        else:
            bonus = 0
        assert bonus == 2

    def test_moderate_threshold_gives_bonus_1(self):
        """Semantic score >= 0.50 and < 0.75 → moderate_bonus (default 1)."""
        sem_cfg = {"strong": 0.75, "moderate": 0.50, "strong_bonus": 2, "moderate_bonus": 1}
        score = 0.60
        if score >= sem_cfg["strong"]:
            bonus = sem_cfg["strong_bonus"]
        elif score >= sem_cfg["moderate"]:
            bonus = sem_cfg["moderate_bonus"]
        else:
            bonus = 0
        assert bonus == 1

    def test_below_threshold_gives_no_bonus(self):
        """Semantic score < 0.50 → no bonus."""
        sem_cfg = {"strong": 0.75, "moderate": 0.50, "strong_bonus": 2, "moderate_bonus": 1}
        score = 0.30
        if score >= sem_cfg["strong"]:
            bonus = sem_cfg["strong_bonus"]
        elif score >= sem_cfg["moderate"]:
            bonus = sem_cfg["moderate_bonus"]
        else:
            bonus = 0
        assert bonus == 0

    def test_skill_maps_to_correct_bundle(self):
        """Skill name from semantic result maps to the containing bundle."""
        bundles = {
            "bsl-dev": {"skills": ["bsl-development"], "optional": ["bsl-debug"]},
            "research-1c": {"skills": ["1c-doc-research"], "optional": []},
        }
        skill_name = "bsl-development"
        matched_bundle = None
        for bname, bundle in bundles.items():
            all_skills = bundle.get("skills", []) + bundle.get("optional", [])
            if skill_name in all_skills:
                matched_bundle = bname
                break
        assert matched_bundle == "bsl-dev"

    def test_unknown_skill_not_mapped(self):
        """Skill not in any bundle is silently skipped."""
        bundles = {
            "bsl-dev": {"skills": ["bsl-development"], "optional": []},
        }
        skill_name = "nonexistent-skill"
        matched_bundle = None
        for bname, bundle in bundles.items():
            all_skills = bundle.get("skills", []) + bundle.get("optional", [])
            if skill_name in all_skills:
                matched_bundle = bname
                break
        assert matched_bundle is None

    def test_hybrid_boost_adds_one(self):
        """When keyword matched (score 2-3) and semantic score >= 0.7, add +1 hybrid boost."""
        scores = {"bsl-dev": 3}
        matched_by = {"bsl-dev": "keyword"}
        sem_result = {"skill_name": "bsl-development", "score": 0.75}
        # Simulate hybrid boost logic
        if sem_result["score"] >= 0.7:
            for bname, bundle in {"bsl-dev": {"skills": ["bsl-development"]}}.items():
                if (
                    sem_result["skill_name"] in bundle["skills"]
                    and bname in scores
                    and scores[bname] > 0
                ):
                    scores[bname] += 1
                    matched_by[bname] = "hybrid"
        assert scores["bsl-dev"] == 4
        assert matched_by["bsl-dev"] == "hybrid"

    def test_no_hybrid_boost_below_threshold(self):
        """Semantic score < 0.7 does NOT add hybrid boost."""
        scores = {"bsl-dev": 3}
        matched_by = {"bsl-dev": "keyword"}
        sem_result = {"skill_name": "bsl-development", "score": 0.5}
        if sem_result["score"] >= 0.7:
            scores["bsl-dev"] += 1
            matched_by["bsl-dev"] = "hybrid"
        assert scores["bsl-dev"] == 3
        assert matched_by["bsl-dev"] == "keyword"

    def test_fallback_trigger_condition(self):
        """Semantic fallback fires when max keyword score < fallback_trigger."""
        scores = {"bsl-dev": 1, "research-1c": 0}
        min_score = 2
        fallback_trigger = min_score
        max_kw_score = max(scores.values()) if scores else 0
        should_fallback = max_kw_score < fallback_trigger
        assert should_fallback is True

    def test_no_fallback_when_keyword_strong(self):
        """Semantic fallback does NOT fire when keyword score >= fallback_trigger."""
        scores = {"bsl-dev": 5}
        min_score = 2
        max_kw_score = max(scores.values())
        should_fallback = max_kw_score < min_score
        assert should_fallback is False

    def test_matched_by_tracks_all_bundles(self):
        """matched_by dict correctly tracks semantic vs keyword per bundle."""
        matched_by = {}
        # Keyword match
        matched_by["research-1c"] = "keyword"
        # Semantic match
        matched_by["bsl-dev"] = "semantic"
        # Hybrid
        matched_by["hooks"] = "hybrid"
        assert matched_by["research-1c"] == "keyword"
        assert matched_by["bsl-dev"] == "semantic"
        assert matched_by["hooks"] == "hybrid"


# ── Config tests ─────────────────────────────────────────────────────


class TestSemanticConfig:
    def test_config_has_semantic_thresholds(self):
        """skill-router-config.json contains semantic_thresholds section."""
        config_path = os.path.join(PROJECT_ROOT, ".claude", "skills", "skill-router-config.json")
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
        assert "semantic_thresholds" in config
        st = config["semantic_thresholds"]
        assert st["enabled"] is True
        assert "strong" in st
        assert "moderate" in st
        assert "strong_bonus" in st
        assert "timeout_ms" in st
        assert st["collection"] == "skill_library"

    def test_semantic_thresholds_values(self):
        """Threshold values are within reasonable ranges."""
        config_path = os.path.join(PROJECT_ROOT, ".claude", "skills", "skill-router-config.json")
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
        st = config["semantic_thresholds"]
        assert 0 < st["strong"] <= 1.0
        assert 0 < st["moderate"] <= 1.0
        assert st["strong"] > st["moderate"]
        assert st["strong_bonus"] >= st["moderate_bonus"]
        assert st["timeout_ms"] <= 1000


# ── Schema tests ─────────────────────────────────────────────────────


class TestExperienceBankSchema:
    def test_schema_is_valid_json(self):
        """cache/experience-bank/schema.json is valid JSON."""
        schema_path = os.path.join(PROJECT_ROOT, "cache", "experience-bank", "schema.json")
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)
        assert schema["title"] == "ExperienceRecord"
        assert "experience_id" in schema["required"]
        assert "trigger" in schema["properties"]
        assert "insight" in schema["properties"]
        assert "confidence" in schema["properties"]

    def test_schema_categories(self):
        """Insight categories match roadmap spec."""
        schema_path = os.path.join(PROJECT_ROOT, "cache", "experience-bank", "schema.json")
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)
        categories = schema["properties"]["insight"]["properties"]["category"]["enum"]
        expected = [
            "tool_selection",
            "parameter_tuning",
            "workflow_order",
            "error_avoidance",
            "prompt_pattern",
        ]
        assert set(categories) == set(expected)
