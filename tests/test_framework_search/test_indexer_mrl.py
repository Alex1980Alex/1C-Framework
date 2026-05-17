"""Unit tests for MRL truncation helpers added for §4.1.6 swap."""

from __future__ import annotations

import math
from unittest.mock import MagicMock

import numpy as np
import pytest

from src.framework_search.indexer import (
    _mrl_truncate,
    ensure_collection,
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


def test_ensure_collection_recreates_underlying_physical_when_alias():
    """recreate=True for an alias must delete+recreate the PHYSICAL collection."""
    client = MagicMock()
    client.collection_exists.return_value = True
    alias = MagicMock(alias_name="framework_code_v1", collection_name="framework_code_v1_mrl_1024")
    client.get_aliases.return_value = MagicMock(aliases=[alias])

    ensure_collection(client, "framework_code_v1", dims=1024, recreate=True)

    client.delete_collection.assert_called_once_with("framework_code_v1_mrl_1024")
    create_kwargs = client.create_collection.call_args.kwargs
    assert create_kwargs["collection_name"] == "framework_code_v1_mrl_1024"


def test_ensure_collection_reestablishes_alias_after_recreate():
    """After recreating physical, alias must be restored via update_collection_aliases."""
    client = MagicMock()
    client.collection_exists.return_value = True
    alias = MagicMock(alias_name="framework_code_v1", collection_name="framework_code_v1_mrl_1024")
    client.get_aliases.return_value = MagicMock(aliases=[alias])

    ensure_collection(client, "framework_code_v1", dims=1024, recreate=True)

    client.update_collection_aliases.assert_called_once()
    ops = client.update_collection_aliases.call_args.kwargs["change_aliases_operations"]
    assert len(ops) == 1
    create_alias = ops[0].create_alias
    assert create_alias.alias_name == "framework_code_v1"
    assert create_alias.collection_name == "framework_code_v1_mrl_1024"


def test_ensure_collection_no_alias_op_for_plain_collection_recreate():
    """recreate=True for a plain (non-alias) collection must NOT call alias APIs."""
    client = MagicMock()
    client.collection_exists.return_value = True
    client.get_aliases.return_value = MagicMock(aliases=[])

    ensure_collection(client, "bsl_code_v4_late", dims=4096, recreate=True)

    client.delete_collection.assert_called_once_with("bsl_code_v4_late")
    create_kwargs = client.create_collection.call_args.kwargs
    assert create_kwargs["collection_name"] == "bsl_code_v4_late"
    client.update_collection_aliases.assert_not_called()
