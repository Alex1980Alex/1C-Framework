"""Tests for autonomous_debug_test.py scenario schema validator.

Run: pytest scripts/test_autonomous_debug_test.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# scripts/ is sibling of tools/; add to path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools" / "bsl-debug-server"))

import autonomous_debug_test as adt  # noqa: E402


# Reusable minimal valid scenario
def _valid_scenario() -> dict:
    return {
        "alias": "ИБTransportManagementDevelop",
        "bsl_trigger": "Результат = 1;",
        "breakpoints": [{"object_id": "uuid1", "line": 141, "module_type": "ObjectModule"}],
    }


class TestScenarioValidator:
    def test_valid_minimal_scenario(self):
        errors = adt.validate_scenario(_valid_scenario())
        assert errors == []

    def test_valid_with_all_optional_fields(self):
        scenario = _valid_scenario()
        scenario.update(
            {
                "iis": {
                    "url": "http://localhost/transport/hs/mcp/rpc",
                    "auth_user_env": "U",
                    "auth_pwd_env": "P",
                },
                "force_recycle": True,
                "stop_timeout_sec": 20,
                "pre_trigger_wait_sec": 5,
            }
        )
        scenario["breakpoints"][0]["inspections"] = [
            {"expr": "ТипЗнч(X)", "expect_substring": "Тип"}
        ]
        errors = adt.validate_scenario(scenario)
        assert errors == []

    def test_root_must_be_object(self):
        errors = adt.validate_scenario("not an object")
        assert any("must be object" in e for e in errors)

    def test_missing_alias_detected(self):
        scenario = _valid_scenario()
        del scenario["alias"]
        errors = adt.validate_scenario(scenario)
        assert any("alias is required" in e for e in errors)

    def test_missing_bsl_trigger_detected(self):
        scenario = _valid_scenario()
        del scenario["bsl_trigger"]
        errors = adt.validate_scenario(scenario)
        assert any("bsl_trigger is required" in e for e in errors)

    def test_breakpoints_must_be_array(self):
        scenario = _valid_scenario()
        scenario["breakpoints"] = "not array"
        errors = adt.validate_scenario(scenario)
        assert any("breakpoints must be list" in e for e in errors)

    def test_force_recycle_must_be_bool(self):
        scenario = _valid_scenario()
        scenario["force_recycle"] = "yes"
        errors = adt.validate_scenario(scenario)
        assert any("force_recycle must be bool" in e for e in errors)

    def test_bp_missing_object_id(self):
        scenario = _valid_scenario()
        del scenario["breakpoints"][0]["object_id"]
        errors = adt.validate_scenario(scenario)
        assert any("object_id is required" in e for e in errors)

    def test_bp_line_must_be_int(self):
        scenario = _valid_scenario()
        scenario["breakpoints"][0]["line"] = "141"
        errors = adt.validate_scenario(scenario)
        assert any("line must be int" in e for e in errors)

    def test_inspection_missing_expr(self):
        scenario = _valid_scenario()
        scenario["breakpoints"][0]["inspections"] = [{"expect_substring": "X"}]
        errors = adt.validate_scenario(scenario)
        assert any("expr is required" in e for e in errors)

    def test_iis_must_be_object(self):
        scenario = _valid_scenario()
        scenario["iis"] = "url-string"
        errors = adt.validate_scenario(scenario)
        assert any("iis must be object" in e for e in errors)

    def test_iis_missing_url(self):
        scenario = _valid_scenario()
        scenario["iis"] = {"auth_user_env": "U"}  # no url
        errors = adt.validate_scenario(scenario)
        assert any("iis.url is required" in e for e in errors)

    def test_multiple_errors_aggregated(self):
        scenario = {"force_recycle": "no", "breakpoints": "x"}
        errors = adt.validate_scenario(scenario)
        # Должно содержать 4+ errors: alias, bsl_trigger, breakpoints, force_recycle
        assert len(errors) >= 4

    def test_warmup_trigger_count_must_be_int(self):
        # Fix #1 §12.8: warmup_trigger_count optional но если есть — int
        scenario = _valid_scenario()
        scenario["warmup_trigger_count"] = "two"
        errors = adt.validate_scenario(scenario)
        assert any("warmup_trigger_count must be int" in e for e in errors)

    def test_warmup_trigger_count_int_passes(self):
        scenario = _valid_scenario()
        scenario["warmup_trigger_count"] = 3
        errors = adt.validate_scenario(scenario)
        assert errors == []
