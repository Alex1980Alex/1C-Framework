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


# --- _selective_format: churn-guard (формат только своих строк) + EOL-preserve ---


def test_selective_format_no_head_full_format_keeps_crlf():
    # Новый файл (head=None): формат целиком, но CRLF-стиль исходника сохраняется
    before = b"A=1;\r\nB=2;\r\n"
    after = b"\tA = 1;\n\tB = 2;\n"  # bsl-ls тихо флипает EOL в LF
    merged = bsl_lint._selective_format(None, before, after)
    assert merged == b"\tA = 1;\r\n\tB = 2;\r\n"


def test_selective_format_keeps_legacy_lines():
    # Правка только строки 2 (MyOld→MyNew); формат почистил и легаси-строки (1, 3) —
    # легаси-whitespace НЕ течёт в результат, формат применён только к моей строке
    head = b"Legacy1\t\nMyOld\nLegacy3  \n"
    before = b"Legacy1\t\nMyNew\nLegacy3  \n"
    after = b"Legacy1\nMyNew_f\nLegacy3\n"
    merged = bsl_lint._selective_format(head, before, after)
    assert merged == b"Legacy1\t\nMyNew_f\nLegacy3  \n"


def test_selective_format_insert_at_my_edit():
    # Вставленная мной строка форматируется, чужие остаются
    head = b"L1  \nL2\n"
    before = b"L1  \nMine\nL2\n"
    after = b"L1\n\tMine\nL2\n"
    merged = bsl_lint._selective_format(head, before, after)
    assert merged == b"L1  \n\tMine\nL2\n"


def test_selective_format_all_legacy_untouched():
    # Формат хочет переписать ТОЛЬКО чужие строки → результат == before (write-back не нужен)
    head = b"L1\t\nL2  \n"
    before = b"L1\t\nL2  \n"
    after = b"L1\nL2\n"
    merged = bsl_lint._selective_format(head, before, after)
    assert merged == before


# ─── P4.1: SARIF 2.1.0 вывод (единый findings-контракт, R4) ──────────────────────


def test_build_sarif_schema_and_levels():
    """P4.1: build_sarif → SARIF 2.1.0; severity bsl-ls → уровень SARIF (error/warning/note)."""
    diags = [
        {
            "file": "src/CommonModules/гкс_Т/Module.bsl",
            "line": 12,
            "severity": "error",
            "code": "MethodSize",
            "message": "m1",
        },
        {"file": "x.bsl", "line": None, "severity": "info", "code": None, "message": "m2"},
        {"file": "y.bsl", "line": 3, "severity": "hint", "code": "R2", "message": "m3"},
    ]
    s = bsl_lint.build_sarif(diags)
    assert s["version"] == "2.1.0" and "sarif-2.1.0" in s["$schema"]
    res = s["runs"][0]["results"]
    assert [r["level"] for r in res] == ["error", "note", "note"]  # error→error, info/hint→note
    assert res[1]["locations"][0]["physicalLocation"]["region"]["startLine"] == 1  # None→1
    assert res[0]["ruleId"] == "MethodSize"
    assert res[0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"].endswith(
        "Module.bsl"
    )


def test_build_sarif_result_shape_matches_sonar():
    """P4.1 (единый контракт): форма result идентична sonar_issues_pull.build_sarif."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "sonar_issues_pull_t",
        Path(__file__).resolve().parents[2] / "scripts" / "sonar_issues_pull.py",
    )
    sp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sp)
    a = bsl_lint.build_sarif(
        [{"file": "f.bsl", "line": 1, "severity": "error", "code": "R", "message": "m"}]
    )
    b = sp.build_sarif(
        [
            {
                "rule": "R",
                "severity": "BLOCKER",
                "message": "m",
                "_file": "f.bsl",
                "line": 1,
                "type": "BUG",
                "_class": "judgment",
            }
        ],
        "proj",
    )
    assert sorted(a["runs"][0]["results"][0].keys()) == sorted(b["runs"][0]["results"][0].keys())
    assert a["$schema"] == b["$schema"] and a["version"] == b["version"]


def test_build_sarif_empty():
    """Пустой список диагностик → валидный SARIF с 0 results (не крах)."""
    s = bsl_lint.build_sarif([])
    assert s["runs"][0]["results"] == [] and s["runs"][0]["tool"]["driver"]["rules"] == []
