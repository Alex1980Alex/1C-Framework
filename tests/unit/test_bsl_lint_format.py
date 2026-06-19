"""Unit-тесты write-back контракта форматера bsl_lint.py (`--format`).

Форматер ПИШЕТ пользовательские файлы → инвариант критичен:
- changed + rc==0      → оригинал перезаписан;
- unchanged + rc==0    → оригинал не тронут;
- changed + rc!=0      → оригинал НЕ перезаписан (не доверяем сбойному выводу);
- tmp-файл пропал      → оригинал не тронут + предупреждение в stderr.

`run_format` (вызов java/bsl-ls) замокан — тесты не требуют Java/jar (marker `unit`, в CI-гейте).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import bsl_lint

pytestmark = pytest.mark.unit


def _mock_run_format(new_bytes: bytes | None, rc: int = 0, delete: bool = False):
    """Сымитировать bsl-ls `--format`: пишет new_bytes в копию внутри srcDir (или удаляет её)."""

    def _fake(java: str, src_dir: Path, config: Path):
        f = next(Path(src_dir).glob("*"))  # единственная копия
        if delete:
            f.unlink()
        elif new_bytes is not None:
            f.write_bytes(new_bytes)
        return rc, ""

    return _fake


def test_changed_rc0_writes_back(tmp_path, monkeypatch, capsys):
    target = tmp_path / "m.bsl"
    target.write_bytes(b"A=1;\n")
    monkeypatch.setattr(bsl_lint, "run_format", _mock_run_format(b"\tA = 1;\n", rc=0))
    assert bsl_lint._do_format("java", target, None) == 0
    assert target.read_bytes() == b"\tA = 1;\n"
    assert "изменён" in capsys.readouterr().out


def test_unchanged_rc0_no_write(tmp_path, monkeypatch, capsys):
    target = tmp_path / "m.bsl"
    orig = b"\tA = 1;\n"
    target.write_bytes(orig)
    monkeypatch.setattr(bsl_lint, "run_format", _mock_run_format(orig, rc=0))
    bsl_lint._do_format("java", target, None)
    assert target.read_bytes() == orig
    assert "без изменений" in capsys.readouterr().out


def test_changed_rc_nonzero_no_write(tmp_path, monkeypatch, capsys):
    target = tmp_path / "m.bsl"
    orig = b"A=1;\n"
    target.write_bytes(orig)
    monkeypatch.setattr(bsl_lint, "run_format", _mock_run_format(b"corrupt", rc=3))
    bsl_lint._do_format("java", target, None)
    assert target.read_bytes() == orig  # НЕ перезаписан при rc!=0
    assert "НЕ перезаписан" in capsys.readouterr().out


def test_tmp_missing_warns_no_write(tmp_path, monkeypatch, capsys):
    target = tmp_path / "m.bsl"
    orig = b"A=1;\n"
    target.write_bytes(orig)
    monkeypatch.setattr(bsl_lint, "run_format", _mock_run_format(None, rc=0, delete=True))
    bsl_lint._do_format("java", target, None)
    assert target.read_bytes() == orig
    assert "временный srcDir" in capsys.readouterr().err
