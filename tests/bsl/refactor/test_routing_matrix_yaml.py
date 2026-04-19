from __future__ import annotations

import pytest
import yaml

from src.bsl.semantic_search.refactor.classifier import (
    RouteDecision,
    RoutingMatrix,
    SymbolKind,
)


@pytest.fixture(autouse=True)
def _isolate_routing_matrix():
    RoutingMatrix.reset()
    yield
    RoutingMatrix.reset()


def _write_yaml(path, data):
    path.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")


def test_routing_matrix_yaml_roundtrip():
    defaults = {k: RoutingMatrix.route_for(k) for k in RoutingMatrix.all_kinds()}
    RoutingMatrix.load()
    for kind in RoutingMatrix.all_kinds():
        loaded = RoutingMatrix.route_for(kind)
        expected = defaults[kind]
        assert loaded.primary == expected.primary
        assert loaded.fallback == expected.fallback
        assert loaded.confidence == pytest.approx(expected.confidence)
        assert loaded.reason == expected.reason
        assert loaded.manual_fallback == expected.manual_fallback


def test_routing_matrix_yaml_missing_kind_falls_back_to_unknown(tmp_path):
    yaml_path = tmp_path / "routes.yaml"
    _write_yaml(yaml_path, {
        "version": 2,
        "routes": {
            "unknown": {
                "primary": "semantic",
                "fallback": None,
                "confidence": 0.25,
                "reason": "unknown catch-all",
                "manual_fallback": True,
            },
        },
    })
    RoutingMatrix.load(yaml_path)
    result = RoutingMatrix.route_for(SymbolKind.MODULE_EXPORT_PROC)
    assert result.primary == "semantic"
    assert result.confidence == pytest.approx(0.25)
    assert result.manual_fallback is True


def test_routing_matrix_yaml_unknown_route_name_skipped(tmp_path):
    yaml_path = tmp_path / "routes.yaml"
    _write_yaml(yaml_path, {
        "version": 2,
        "routes": {
            "nonexistent_kind": {
                "primary": "x",
                "fallback": None,
                "confidence": 0.1,
                "reason": "bad",
            },
        },
    })
    RoutingMatrix.load(yaml_path)
    for kind in RoutingMatrix.all_kinds():
        decision = RoutingMatrix.route_for(kind)
        assert isinstance(decision, RouteDecision)


def test_routing_matrix_yaml_bad_version_raises(tmp_path):
    yaml_path = tmp_path / "routes.yaml"
    _write_yaml(yaml_path, {"version": 99, "routes": {}})
    with pytest.raises(ValueError, match="[Vv]ersion"):
        RoutingMatrix.load(yaml_path)


def test_global_ast_grep_defaults_when_block_missing(tmp_path):
    yaml_path = tmp_path / "routes.yaml"
    _write_yaml(yaml_path, {"version": 2, "routes": {}})
    RoutingMatrix.load(yaml_path)
    cfg = RoutingMatrix.ast_grep_global()
    assert cfg["use_call_graph_prefilter"] is False
    assert cfg["call_graph_db"] == "cache/bsl_call_graph.db"
    assert cfg["graph_stale_threshold_days"] == 7


def test_global_ast_grep_overrides_loaded(tmp_path):
    yaml_path = tmp_path / "routes.yaml"
    _write_yaml(yaml_path, {
        "version": 2,
        "global": {
            "ast_grep": {
                "use_call_graph_prefilter": True,
                "call_graph_db": "cache/custom.db",
                "graph_stale_threshold_days": 3,
            },
        },
        "routes": {},
    })
    RoutingMatrix.load(yaml_path)
    cfg = RoutingMatrix.ast_grep_global()
    assert cfg["use_call_graph_prefilter"] is True
    assert cfg["call_graph_db"] == "cache/custom.db"
    assert cfg["graph_stale_threshold_days"] == 3


def test_global_ast_grep_unknown_keys_dropped(tmp_path):
    yaml_path = tmp_path / "routes.yaml"
    _write_yaml(yaml_path, {
        "version": 2,
        "global": {
            "ast_grep": {
                "use_call_graph_prefilter": True,
                "rogue_key": "ignored",
            },
        },
        "routes": {},
    })
    RoutingMatrix.load(yaml_path)
    cfg = RoutingMatrix.ast_grep_global()
    assert "rogue_key" not in cfg
    assert cfg["use_call_graph_prefilter"] is True


def test_routing_matrix_reset_restores_defaults(tmp_path):
    yaml_path = tmp_path / "routes.yaml"
    _write_yaml(yaml_path, {
        "version": 2,
        "routes": {
            "module_export_proc": {
                "primary": "regex",
                "fallback": None,
                "confidence": 0.1,
                "reason": "custom",
                "manual_fallback": True,
            },
        },
    })
    RoutingMatrix.load(yaml_path)
    assert RoutingMatrix.route_for(SymbolKind.MODULE_EXPORT_PROC).primary == "regex"

    RoutingMatrix.reset()
    restored = RoutingMatrix.route_for(SymbolKind.MODULE_EXPORT_PROC)
    assert restored.primary == "multilspy"
    assert restored.manual_fallback is False
