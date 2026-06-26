"""Unit: supervised reindex `--recreate-once` (чистый rebuild через дроп в супервизоре).

Раньше супервизор всегда шёл resume → recreate делали ручным дропом. Флаг --recreate-once
дропает коллекцию ОДИН раз в самом супервизоре ДО лестницы (детерминированно, не зависит от
того, дойдёт ли дочерний reindex до своего create_collection — закрывает edge, где краш в
model_load ДО дропа свалил бы прогон в resume против стэйл-данных). Дальше все прогоны —
обычный resume, дочерний создаёт коллекцию заново hybrid. Если дроп не удался (Qdrant down) —
супервизор ПРЕРЫВАЕТ. stdlib-only модуль → тест без модели/CUDA/Qdrant.
"""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_IMPORT_OK = True
try:
    _spec = importlib.util.spec_from_file_location(
        "reindex_supervised", _ROOT / "scripts" / "reindex_supervised.py"
    )
    _m = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_m)
except Exception:  # pragma: no cover — модуль stdlib-only, импорт не должен падать
    _IMPORT_OK = False

pytestmark = [
    pytest.mark.unit,
    pytest.mark.skipif(not _IMPORT_OK, reason="reindex_supervised import failed"),
]


def _args(**kw):
    base = dict(project="D:/x", collection="c", max_file_bytes=0, long_batch1_tokens=0)
    base.update(kw)
    return SimpleNamespace(**base)


# --- _build_cmd: всегда resume (дроп — отдельно, в супервизоре) ----------------------


def test_build_cmd_is_resume_with_sparse():
    cmd = _m._build_cmd(_args(), 32, 512)
    assert "--skip-indexed" in cmd
    assert "--recreate" not in cmd  # супервизор НЕ просит дочерний дропать
    assert "--enable-sparse" in cmd  # свежая коллекция создаётся hybrid
    assert "c" in cmd and "D:/x" in cmd


def test_build_cmd_passthrough_flags():
    cmd = _m._build_cmd(_args(max_file_bytes=2097152, long_batch1_tokens=1024), 8, 128)
    assert "--max-file-bytes" in cmd and "2097152" in cmd
    assert "--long-batch1-tokens" in cmd and "1024" in cmd


# --- main: --recreate-once дропает ОДИН раз в супервизоре, до лестницы ----------------


def _patch_run_attempt(monkeypatch, verdict="ok"):
    calls = []

    def fake(args, batch, log):
        calls.append(batch)
        return verdict

    monkeypatch.setattr(_m, "run_attempt", fake)
    return calls


def test_recreate_once_drops_then_runs(monkeypatch):
    drops = []
    monkeypatch.setattr(_m, "_points_count", lambda c: 1341006)
    monkeypatch.setattr(_m, "_drop_collection", lambda c: drops.append(c) or True)
    calls = _patch_run_attempt(monkeypatch, "ok")
    rc = _m.main(["--project", "X", "--collection", "c", "--recreate-once", "--ladder", "32,8,1"])
    assert rc == 0
    assert drops == ["c"]  # дроп ровно один раз, до прогонов
    assert calls == [32]  # ok на первом прогоне → стоп


def test_recreate_once_aborts_if_drop_fails(monkeypatch):
    """Edge D: дроп не удался (Qdrant down) → прерывание, НИ ОДИН прогон не стартует
    (иначе тихий resume против стэйл-коллекции с дублями)."""
    monkeypatch.setattr(_m, "_points_count", lambda c: 10)
    monkeypatch.setattr(_m, "_drop_collection", lambda c: False)
    calls = _patch_run_attempt(monkeypatch, "ok")
    rc = _m.main(["--project", "X", "--collection", "c", "--recreate-once"])
    assert rc == 1
    assert calls == []  # resume против стэйл НЕ запущен


def test_no_recreate_once_skips_drop(monkeypatch):
    drops = []
    monkeypatch.setattr(_m, "_drop_collection", lambda c: drops.append(c) or True)
    calls = _patch_run_attempt(monkeypatch, "ok")
    rc = _m.main(["--project", "X", "--collection", "c", "--ladder", "32,8,1"])
    assert rc == 0
    assert drops == []  # без флага дропа нет — поведение прежнее
    assert calls == [32]
