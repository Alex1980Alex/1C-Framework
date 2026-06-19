"""Unit-тесты co-location состояния 1С-пайплайна в папке задачи. marker: unit.

Collision-immune (importlib). Покрытие: state_dir (реестр 1С vs generic), init_task профиль
(STAGES_1C по title vs generic STAGES; task_dir → state в папке), relocate_1c (generic→папка задачи,
удаление generic, идемпотентность), iter_states (generic + 1С), is_1c предикат.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_PS = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "shared" / "pipeline_state.py"


def _load_ps(tmp: Path):
    """Загрузить pipeline_state с изолированными в tmp PIPELINE_DIR/реестром (collision-immune)."""
    spec = importlib.util.spec_from_file_location("ps_coloc_t", _PS)
    ps = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ps)
    ps.PROJECT_ROOT = tmp.resolve()
    ps.PIPELINE_DIR = ps.PROJECT_ROOT / "pipeline"
    ps.CURRENT_PTR = ps.PIPELINE_DIR / "CURRENT"
    ps.REGISTRY_PTR = ps.PIPELINE_DIR / "_1c_index.json"
    return ps


def test_is_1c_predicate(tmp_path):
    ps = _load_ps(tmp_path)
    assert ps.is_1c("1С-задача (run-1c-task): X") is True
    assert ps.is_1c("1С-задача из чата: X") is False  # lookalike без скобки
    assert ps.is_1c("Обычная задача") is False
    assert ps.is_1c(None) is False


def test_generic_unchanged(tmp_path):
    # не-1С задача → generic STAGES + pipeline/<slug>/ (обратная совместимость)
    ps = _load_ps(tmp_path)
    d = ps.init_task("gen-task", title="Обычная задача")
    assert [s["artifact"] for s in d["stages"]] == [
        "01-architecture.md",
        "02-design.md",
        "03-implementation.md",
        "04-testing.md",
    ]
    assert ps.state_dir("gen-task") == ps.PIPELINE_DIR / "gen-task"
    assert (ps.PIPELINE_DIR / "gen-task" / ps.STATE_NAME).exists()


def test_1c_profile_with_task_dir(tmp_path):
    # 1С-задача с task_dir → STAGES_1C + состояние сразу в папке задачи
    ps = _load_ps(tmp_path)
    td = tmp_path / "configuration" / "P" / "docs" / "260608_T"
    td.mkdir(parents=True)
    d = ps.init_task("GKSTCPLK-1", title="1С-задача (run-1c-task): GKSTCPLK-1", task_dir=str(td))
    assert [s["artifact"] for s in d["stages"]] == [
        "ANALYSIS-REPORT.md",
        "ANALYSIS-REPORT.md",
        "IMPLEMENTATION-PROGRESS.md",
        ".run-state.json",
    ]
    assert (td / ps.STATE_NAME).exists()
    assert ps.state_dir("gkstcplk-1") == td
    assert not (ps.PIPELINE_DIR / "gkstcplk-1").exists()  # generic-папка не создаётся


def test_1c_profile_without_task_dir_born_generic(tmp_path):
    # 1С-задача без task_dir (chat/jira) → STAGES_1C, но временно в pipeline/<slug>/ (до relocate)
    ps = _load_ps(tmp_path)
    d = ps.init_task("GKSTCPLK-2", title="1С-задача (analyze-1c-task): GKSTCPLK-2")
    assert d["stages"][0]["artifact"] == "ANALYSIS-REPORT.md"  # профиль 1С по title
    assert ps.state_dir("gkstcplk-2") == ps.PIPELINE_DIR / "gkstcplk-2"  # но расположение generic


def test_state_dir_registry_vs_generic(tmp_path):
    ps = _load_ps(tmp_path)
    td = tmp_path / "configuration" / "X" / "docs" / "Y"
    td.mkdir(parents=True)
    ps.register_1c("gkstcplk-3", str(td))
    assert ps.state_dir("gkstcplk-3") == td  # реестр
    assert ps.state_dir("unknown-slug") == ps.PIPELINE_DIR / "unknown-slug"  # generic fallback
    reg = json.loads(ps.REGISTRY_PTR.read_text(encoding="utf-8"))
    assert reg["gkstcplk-3"] == "configuration/X/docs/Y"  # rel-to-root POSIX


def test_relocate_on_artifact(tmp_path):
    # init generic → relocate в папку задачи: state перенесён, generic удалён, идемпотентно
    ps = _load_ps(tmp_path)
    ps.init_task("GKSTCPLK-4", title="1С-задача (analyze-1c-task): GKSTCPLK-4")  # без task_dir
    gen = ps.PIPELINE_DIR / "gkstcplk-4" / ps.STATE_NAME
    assert gen.exists()
    td = tmp_path / "configuration" / "P" / "docs" / "260608_GKSTCPLK-4"
    td.mkdir(parents=True)
    assert ps.relocate_1c("gkstcplk-4", str(td)) is True
    assert (td / ps.STATE_NAME).exists()  # перенесён в папку задачи
    assert not gen.exists()  # старый generic-файл удалён
    assert not (ps.PIPELINE_DIR / "gkstcplk-4").exists()  # пустая generic-папка убрана
    assert ps.relocate_1c("gkstcplk-4", str(td)) is False  # идемпотентно — no-op
    # mark_done после переезда пишет в папку задачи
    ps.mark_done("gkstcplk-4", 1)
    d = json.loads((td / ps.STATE_NAME).read_text(encoding="utf-8"))
    assert d["stages"][0]["status"] == "done"


def test_rel_to_root_relative_from_any_cwd(tmp_path, monkeypatch):
    # БАГ co-location (пойман живым /run-1c-task): относительный --task-dir резолвился от cwd процесса,
    # а не от корня репо → состояние попадало в .claude/hooks/configuration/... Фикс: от PROJECT_ROOT.
    ps = _load_ps(tmp_path)
    other = tmp_path / "elsewhere" / "deep"
    other.mkdir(parents=True)
    monkeypatch.chdir(other)  # cwd НЕ корень репо
    assert (
        ps._rel_to_root("configuration/X/docs/T") == "configuration/X/docs/T"
    )  # от PROJECT_ROOT, не от cwd
    # абсолютный путь под репо — без изменений
    abs_td = ps.PROJECT_ROOT / "configuration" / "Y"
    assert ps._rel_to_root(str(abs_td)) == "configuration/Y"
    # абсолютный путь ВНЕ репо → абсолютный POSIX-fallback (не repo-relative)
    outside = ps.PROJECT_ROOT.parent / "outside_repo"
    assert Path(ps._rel_to_root(str(outside))).is_absolute()


def test_relocate_convergence_partial_crash(tmp_path):
    # частичный крэш: register прошёл, _save в target НЕ успел → повторный relocate до-мигрирует из generic
    ps = _load_ps(tmp_path)
    ps.init_task("GKSTCPLK-7", title="1С-задача (run-1c-task): GKSTCPLK-7")  # generic
    generic = ps.PIPELINE_DIR / "gkstcplk-7"
    td = tmp_path / "configuration" / "C" / "docs" / "T7"
    td.mkdir(parents=True)
    ps.register_1c("gkstcplk-7", str(td))  # симуляция: реестр переключён, данные ещё в generic
    assert ps.state_dir("gkstcplk-7") == td
    assert not (td / ps.STATE_NAME).exists() and (generic / ps.STATE_NAME).exists()
    assert ps.relocate_1c("gkstcplk-7", str(td)) is True  # подхватывает из generic
    assert (td / ps.STATE_NAME).exists()  # до-мигрировано
    assert not (generic / ps.STATE_NAME).exists()  # generic подчищен
    d = json.loads((td / ps.STATE_NAME).read_text(encoding="utf-8"))
    assert d["stages"][0]["artifact"] == "ANALYSIS-REPORT.md"  # данные сохранены (STAGES_1C)


def test_iter_states_generic_and_1c(tmp_path):
    ps = _load_ps(tmp_path)
    ps.init_task("gen", title="Обычная")  # generic
    td = tmp_path / "configuration" / "Z" / "docs" / "W"
    td.mkdir(parents=True)
    ps.init_task(
        "GKSTCPLK-5", title="1С-задача (run-1c-task): GKSTCPLK-5", task_dir=str(td)
    )  # 1С в папке
    slugs = sorted(slug for slug, _ in ps.iter_states())
    assert slugs == ["gen", "gkstcplk-5"]  # энумератор видит оба расположения


def test_render_status_resolves_task_dir(tmp_path):
    # render_status проверяет наличие артефакта по state_dir (папка задачи), не generic
    ps = _load_ps(tmp_path)
    td = tmp_path / "configuration" / "R" / "docs" / "S"
    td.mkdir(parents=True)
    ps.init_task("GKSTCPLK-6", title="1С-задача (run-1c-task): GKSTCPLK-6", task_dir=str(td))
    (td / "ANALYSIS-REPORT.md").write_text("x" * 300, encoding="utf-8")
    out = ps.render_status("gkstcplk-6")
    assert "ANALYSIS-REPORT.md" in out
    # этап 1 (ANALYSIS-REPORT.md есть в папке задачи) → без пометки «файла нет»
    line1 = next(ln for ln in out.splitlines() if ln.strip().startswith("[ ] 1."))
    assert "файла нет" not in line1
