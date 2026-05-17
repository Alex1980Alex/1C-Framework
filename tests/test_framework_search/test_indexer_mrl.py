"""Unit tests for MRL truncation helpers added for §4.1.6 swap."""

from __future__ import annotations

import math
from unittest.mock import MagicMock

import numpy as np
import pytest

from src.framework_search.indexer import (
    _mrl_truncate,
    maybe_truncate_vectors,
    resolve_collection_dim,
    resolve_physical_collection,
)

pytestmark = pytest.mark.unit


def test_resolve_collection_dim_single_vector():
    client = MagicMock()
    info = MagicMock()
    info.config.params.vectors = MagicMock(size=1024)
    client.get_collection.return_value = info
    assert resolve_collection_dim(client, "framework_code_v1") == 1024


def test_resolve_collection_dim_multi_vector_returns_none():
    client = MagicMock()
    info = MagicMock()
    info.config.params.vectors = {"dense": MagicMock(size=4096), "late": MagicMock(size=4096)}
    client.get_collection.return_value = info
    assert resolve_collection_dim(client, "bsl_code_v4_late") is None


def test_mrl_truncate_truncates_and_renorms():
    v = [1.0] * 4096
    out = _mrl_truncate(v, 1024)
    assert len(out) == 1024
    assert math.isclose(float(np.linalg.norm(out)), 1.0, abs_tol=1e-5)


def test_mrl_truncate_zero_vector_no_nan():
    v = [0.0] * 4096
    out = _mrl_truncate(v, 1024)
    assert len(out) == 1024
    assert all(x == 0.0 for x in out)


def test_maybe_truncate_vectors_idempotent_when_already_short():
    v = [[0.1] * 1024]
    out = maybe_truncate_vectors(v, 1024)
    assert out == v


def test_maybe_truncate_vectors_truncates_each():
    vectors = [[1.0] * 4096, [2.0] * 4096]
    out = maybe_truncate_vectors(vectors, 1024)
    assert all(len(o) == 1024 for o in out)
    for o in out:
        assert math.isclose(float(np.linalg.norm(o)), 1.0, abs_tol=1e-5)


def test_resolve_physical_collection_returns_underlying_for_alias():
    client = MagicMock()
    alias = MagicMock(alias_name="framework_code_v1", collection_name="framework_code_v1_mrl_1024")
    client.get_aliases.return_value = MagicMock(aliases=[alias])
    assert resolve_physical_collection(client, "framework_code_v1") == "framework_code_v1_mrl_1024"


def test_resolve_physical_collection_returns_name_when_not_alias():
    client = MagicMock()
    client.get_aliases.return_value = MagicMock(aliases=[])
    assert resolve_physical_collection(client, "framework_code_v1") == "framework_code_v1"


def test_resolve_physical_collection_safe_on_api_error():
    client = MagicMock()
    client.get_aliases.side_effect = RuntimeError("network")
    assert resolve_physical_collection(client, "anything") == "anything"
