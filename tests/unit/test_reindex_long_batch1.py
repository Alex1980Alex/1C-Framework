"""Unit: Part A (ADR-038) — `_long_batch1_buckets` форсит batch=1 для длинных чанков.

Профилактика тихого CUDA-wedge Qwen3-8B на тяжёлых ERP-модулях: чанки длиннее порога
идут batch=1, короткие сохраняют быстрый batch. Чистая функция → тестируется без модели/CUDA.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_IMPORT_OK = True
try:
    _spec = importlib.util.spec_from_file_location(
        "reindex_bsl_qwen3", _ROOT / "scripts" / "reindex_bsl_qwen3.py"
    )
    _m = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_m)
except Exception:  # heavy deps (src.bsl.*) недоступны в окружении → скип
    _IMPORT_OK = False

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(not _IMPORT_OK, reason="reindex_bsl_qwen3 import failed (heavy deps)"),
]

DEFAULT = ((512, 32), (1024, 16), (2048, 8), (4096, 4), (8192, 2), (None, 1))


def test_threshold_zero_is_noop():
    assert _m._long_batch1_buckets(DEFAULT, 0) == DEFAULT
    assert _m._long_batch1_buckets(DEFAULT, -5) == DEFAULT


def test_threshold_1024_forces_long_to_batch1():
    out = dict(_m._long_batch1_buckets(DEFAULT, 1024))
    # короткие (<= порога) сохраняют batch
    assert out[512] == 32
    assert out[1024] == 16
    # длинные (> порога) → batch=1
    assert out[2048] == 1
    assert out[4096] == 1
    assert out[8192] == 1
    assert out[None] == 1  # unbounded хвост всегда 1


def test_threshold_2048_keeps_midsize():
    out = dict(_m._long_batch1_buckets(DEFAULT, 2048))
    assert out[2048] == 8  # ровно на пороге — НЕ форсится
    assert out[4096] == 1  # выше порога → 1
    assert out[None] == 1


def test_preserves_order_and_length():
    out = _m._long_batch1_buckets(DEFAULT, 1024)
    assert [u for u, _ in out] == [u for u, _ in DEFAULT]  # порядок/ключи не тронуты
