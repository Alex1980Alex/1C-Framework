"""Unit-тесты pipeline_1c_bridge (ADR-019 B′ F-1, ядро G3). marker: unit.

Покрытие: slug-деривация (JIRA приоритет / ASCII-fallback / общий слот), гарантия
«один slug на задачу» (analyze↔implement), best-effort (не кидает при сбое импорта
pipeline_state). Тесты **collision-immune** к src/shared↔hooks/shared (см. memory
feedback-hook-src-shared-collision): не делают runtime `from shared import pipeline_state`,
который в общем pytest-прогоне резолвится в src/shared. Реальное создание `.pipeline-state.json`
покрыто live-DoD-2 (синтетический analyze-preflight) — см. 04-testing.md.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _setfit_gate_off(monkeypatch):
    """Детерминизм независимо от dev-окружения: тесты этого модуля проверяют route/classify +
    TF-IDF откат (поведение при ВЫКЛ SetFit-гейте = CI-дефолт). Локально gate может быть ВКЛ
    (ONEC_SETFIT_ENABLE=1 в settings.local.json) → semantic_source/semantic_sim расходятся и
    semantic-assert-тесты флейкуют. Снимаем флаг на каждый тест. SetFit gate-on покрыт отдельно
    (test_onec_setfit_gate.py). См. memory feedback-deterministic-test-robustness."""
    monkeypatch.delenv("ONEC_SETFIT_ENABLE", raising=False)


_HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"

_spec = importlib.util.spec_from_file_location(
    "pipeline_1c_bridge_t", _HOOKS / "shared" / "pipeline_1c_bridge.py"
)
bridge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bridge)


def _force_shared_import_failure(monkeypatch):
    """Гарантированно уронить `from shared import pipeline_state` внутри bridge-функций.

    Замены sys.modules['shared'] пустым модулем НЕДОСТАТОЧНО: если sys.modules['shared.pipeline_state']
    закэширован прошлым тестом/хуком (полный прогон), Python резолвит submodule ИЗ КЭША → import
    проходит, ensure_pipeline_1c/gate_1c_implement/advance_for_artifact уходят в РЕАЛЬНЫЙ pipeline_state
    и пишут CURRENT/реестр в репозиторий (root-cause order-dependent флейка + полютер pipeline/_1c_index.json).
    Удаляем и подмодуль — тогда import гарантированно падает (ImportError) → best-effort путь (None/ok=True).
    """
    monkeypatch.setitem(sys.modules, "shared", types.ModuleType("shared"))
    monkeypatch.delitem(sys.modules, "shared.pipeline_state", raising=False)


def test_derive_slug_jira():
    # JIRA-код = стабильный ID задачи
    assert bridge.derive_slug("/implement-1c-task GKSTCPLK-2182 доработать") == "GKSTCPLK-2182"


def test_is_1c_task_title():
    # N4: единый предикат 1С-пайплайна — paren-form True, lookalike/прочее False
    assert bridge.is_1c_task_title("1С-задача (run-1c-task): GKSTCPLK-1") is True
    assert bridge.is_1c_task_title("1С-задача (analyze-1c-task): x") is True
    assert (
        bridge.is_1c_task_title("1С-задача из чата: классификатор") is False
    )  # lookalike (без скобки)
    assert bridge.is_1c_task_title("B' доработка: docs") is False
    assert bridge.is_1c_task_title("") is False
    assert bridge.is_1c_task_title(None) is False


def test_derive_slug_fallback_ascii():
    s = bridge.derive_slug("Refactor unload direction form")
    assert s and s == s.lower() and all(c.isalnum() or c == "-" for c in s)


def test_derive_slug_empty_and_cyrillic():
    # пусто и чистая кириллица-без-JIRA → общий слот (ASCII-decompose пуст)
    assert bridge.derive_slug("") == "1c-task"
    assert bridge.derive_slug("Доработать форму") == "1c-task"


def test_same_jira_one_slug():
    # «один пайплайн на задачу»: analyze и implement одного JIRA → один slug
    a = bridge.derive_slug("/analyze-1c-task GKSTCPLK-5 анализ")
    i = bridge.derive_slug("/implement-1c-task GKSTCPLK-5 реализация")
    assert a == i == "GKSTCPLK-5"


def test_best_effort_never_raises(monkeypatch):
    # форсируем сбой импорта pipeline_state (пустой `shared` без сабмодуля) →
    # ensure_pipeline_1c обязан вернуть None, НЕ кинуть (инвариант «не ломать preflight»)
    _force_shared_import_failure(monkeypatch)
    assert bridge.ensure_pipeline_1c("/analyze-1c-task GKSTCPLK-1 x", "analyze-1c-task") is None


def test_force_shared_failure_evicts_cached_submodule(monkeypatch):
    """Регресс-гард на изоляцию `_force_shared_import_failure` (root-cause order-флейка).

    Воспроизводим «кэшер» ПРЯМО в тесте: кладём `shared.pipeline_state` в sys.modules ДО мока
    (как сделал бы сосед/хук через `from shared import pipeline_state`). Инвариант фикса — helper
    ОБЯЗАН выселить подмодуль, иначе `from shared import pipeline_state` резолвится ИЗ КЭША и
    best-effort функции уходят в РЕАЛЬНЫЙ pipeline_state (полютер CURRENT/реестра). Тест экспонирует
    worst-case КАЖДЫЙ прогон — без зависимости от порядка тестов и наличия естественного кэшера
    («а если кешера не будет»). Откатят `delitem` — этот тест красный ВСЕГДА, а не флейково.
    """
    monkeypatch.setitem(
        sys.modules, "shared.pipeline_state", types.ModuleType("shared.pipeline_state")
    )
    _force_shared_import_failure(monkeypatch)
    assert "shared.pipeline_state" not in sys.modules  # выселен → import не резолвится из кэша
    # сквозной best-effort контракт держится даже при предзаполненном кэше:
    assert bridge.ensure_pipeline_1c("/analyze-1c-task GKSTCPLK-1 x", "analyze-1c-task") is None


# --- F-1.5: advance_for_artifact (collision-immune; live-движение этапов — в 04-testing DoD) ---


def test_advance_regex_mapping():
    # артефакт→этапы (чистый regex, без pipeline_state)
    a = next(st for rx, st in bridge._ARTIFACT_STAGES if rx.search("GKSTCPLK-1-ANALYSIS-REPORT.md"))
    i = next(st for rx, st in bridge._ARTIFACT_STAGES if rx.search("IMPLEMENTATION-PROGRESS.md"))
    assert a == (1, 2) and i == (3,)


def test_advance_non_artifact_none():
    # путь без 1С-артефакта → None (ранний выход, pipeline_state не трогается)
    assert bridge.advance_for_artifact("/x/some_random.py") is None
    assert bridge.advance_for_artifact("") is None


def test_advance_best_effort(monkeypatch, tmp_path):
    # матч + содержимое есть (>порог), но pipeline_state недоступен (пустой shared) → None, не кидает
    f = tmp_path / "GKSTCPLK-1-ANALYSIS-REPORT.md"
    f.write_text("# Анализ\n" + "Существенное содержимое отчёта. " * 20, encoding="utf-8")
    _force_shared_import_failure(monkeypatch)
    assert bridge.advance_for_artifact(str(f)) is None


def test_advance_h7_content_guard(tmp_path):
    # H7: пустой/stub-артефакт не проходит content-guard; существенный — проходит
    full = tmp_path / "GKSTCPLK-1-ANALYSIS-REPORT.md"
    full.write_text("# Анализ\n" + "Существенное содержимое. " * 20, encoding="utf-8")
    assert bridge._artifact_has_content(str(full)) is True
    stub = tmp_path / "stub-ANALYSIS-REPORT.md"
    stub.write_text("# TODO", encoding="utf-8")
    assert bridge._artifact_has_content(str(stub)) is False
    assert bridge._artifact_has_content(str(tmp_path / "nope.md")) is False


# --- F-2: gate_1c_implement (collision-immune; block/allow реального пайплайна — в 04-testing DoD) ---


def test_gate_no_pipeline_or_fail_ok():
    # нет 1С-пайплайна для slug (ИЛИ collision→except) → ok=True (не блокируем нормальный поток)
    res = bridge.gate_1c_implement("/implement-1c-task GKSTCPLK-40404 нет такого")
    assert res["ok"] is True and res["hard"] is False


def test_gate_best_effort_ok(monkeypatch):
    # сбой pipeline_state (пустой shared) → ok=True, не кидает
    _force_shared_import_failure(monkeypatch)
    res = bridge.gate_1c_implement("/implement-1c-task GKSTCPLK-1 x")
    assert res["ok"] is True


# --- C2/C3: единая идентификация активного 1С-пайплайна (resolve_active_1c_slug) ---


def _inject_fake_pipeline_state(monkeypatch, current=None, pipelines=None):
    """Фейковый shared.pipeline_state (паттерн _force_shared_import_failure, но с функциями)."""
    pipelines = pipelines or {}
    fake = types.ModuleType("shared.pipeline_state")
    fake.resolve_current = lambda: current
    fake.load = lambda s=None: pipelines.get(s if s else current)
    shared = types.ModuleType("shared")
    shared.pipeline_state = fake
    monkeypatch.setitem(sys.modules, "shared", shared)
    monkeypatch.setitem(sys.modules, "shared.pipeline_state", fake)


def test_resolve_active_jira_returns_own_slug(monkeypatch):
    # JIRA в промпте → его код (стабильный ID); CURRENT не используется (даже если иной)
    _inject_fake_pipeline_state(monkeypatch, current="other")
    assert bridge.resolve_active_1c_slug("/implement-1c-task GKSTCPLK-9 реализация") == "GKSTCPLK-9"


def test_resolve_active_non_jira_uses_current_if_1c(monkeypatch):
    # не-JIRA → CURRENT, если это 1С-пайплайн (метка title)
    _inject_fake_pipeline_state(
        monkeypatch,
        current="slug-A",
        pipelines={"slug-A": {"title": "1С-задача (analyze-1c-task): slug-A"}},
    )
    assert bridge.resolve_active_1c_slug("реализовать доработку формы") == "slug-A"


def test_resolve_active_non_jira_non_1c_current_is_none(monkeypatch):
    # не-JIRA, CURRENT — НЕ 1С-пайплайн (framework-dev) → None (не зацепим чужой пайплайн)
    _inject_fake_pipeline_state(
        monkeypatch, current="fw", pipelines={"fw": {"title": "framework work (C1-C4)"}}
    )
    assert bridge.resolve_active_1c_slug("реализовать доработку формы") is None


def test_gate_non_jira_converges_on_analyze_pipeline(monkeypatch):
    # C2/C3 ГВОЗДЬ: не-JIRA /implement находит пайплайн /analyze через CURRENT → дизайн approved → allow
    approved = {
        "title": "1С-задача (analyze-1c-task): slug-A",
        "stages": [{"n": 2, "status": "done", "approved": True}],
    }
    _inject_fake_pipeline_state(monkeypatch, current="slug-A", pipelines={"slug-A": approved})
    res = bridge.gate_1c_implement("реализовать доработку формы")  # не-JIRA prompt
    assert res["ok"] is True and res["hard"] is False


def test_gate_non_jira_blocks_when_design_not_approved(monkeypatch):
    # G4 теперь РАБОТАЕТ для не-JIRA: дизайн НЕ approved в активном пайплайне → hard-блок
    not_approved = {
        "title": "1С-задача (analyze-1c-task): slug-A",
        "stages": [{"n": 2, "status": "done", "approved": False}],
    }
    _inject_fake_pipeline_state(monkeypatch, current="slug-A", pipelines={"slug-A": not_approved})
    res = bridge.gate_1c_implement("реализовать доработку формы")  # не-JIRA prompt
    assert res["ok"] is False and res["hard"] is True


# --- ADR-041 R1: G4 honors OpenSpec-approval (нет расхождения двух гейтов) ---


def _inject_fake_approval_state(monkeypatch, approved: bool):
    """Фейковый shared.approval_state.is_design_approved_via_openspec → approved (R1-плечо G4)."""
    fake = types.ModuleType("shared.approval_state")
    fake.is_design_approved_via_openspec = lambda text, root=None: approved
    monkeypatch.setitem(sys.modules, "shared.approval_state", fake)
    sh = sys.modules.get("shared")
    if sh is not None:
        monkeypatch.setattr(sh, "approval_state", fake, raising=False)


def test_gate_honors_openspec_approval(monkeypatch):
    # R1 ГВОЗДЬ: pipeline-state этап-2 НЕ approved, но OpenSpec change для JIRA == approved →
    # G4 пропускает (раньше — ложный блок implement в SDD-потоке). source=openspec.
    not_approved = {
        "title": "1С-задача (analyze-1c-task): GKSTCPLK-7",
        "stages": [{"n": 2, "status": "done", "approved": False}],
    }
    _inject_fake_pipeline_state(
        monkeypatch, current="GKSTCPLK-7", pipelines={"GKSTCPLK-7": not_approved}
    )
    _inject_fake_approval_state(monkeypatch, approved=True)
    res = bridge.gate_1c_implement("/implement-1c-task GKSTCPLK-7 реализация")
    assert res["ok"] is True and res["hard"] is False and res.get("source") == "openspec"


def test_gate_openspec_pending_still_blocks(monkeypatch):
    # ИНВАРИАНТ: OpenSpec НЕ approved (pending) И pipeline НЕ approved → блок (поведение прежнее).
    not_approved = {
        "title": "1С-задача (analyze-1c-task): GKSTCPLK-8",
        "stages": [{"n": 2, "status": "done", "approved": False}],
    }
    _inject_fake_pipeline_state(
        monkeypatch, current="GKSTCPLK-8", pipelines={"GKSTCPLK-8": not_approved}
    )
    _inject_fake_approval_state(monkeypatch, approved=False)
    res = bridge.gate_1c_implement("/implement-1c-task GKSTCPLK-8 реализация")
    assert res["ok"] is False and res["hard"] is True


def test_gate_pipeline_approved_skips_openspec(monkeypatch):
    # ИНВАРИАНТ: pipeline-state approved → allow СРАЗУ (openspec-плечо даже не нужно).
    approved = {
        "title": "1С-задача (analyze-1c-task): GKSTCPLK-9",
        "stages": [{"n": 2, "status": "done", "approved": True}],
    }
    _inject_fake_pipeline_state(
        monkeypatch, current="GKSTCPLK-9", pipelines={"GKSTCPLK-9": approved}
    )
    _inject_fake_approval_state(
        monkeypatch, approved=False
    )  # openspec бы заблокировал — но не зовётся
    res = bridge.gate_1c_implement("/implement-1c-task GKSTCPLK-9 реализация")
    assert res["ok"] is True and res["hard"] is False and "source" not in res


# --- ADR-041 R2: sync_approval — мост state↔yaml (проекция OpenSpec→pipeline, one-way) ---


def _inject_fake_ps_with_approve(monkeypatch, current, pipelines, calls):
    """Фейковый shared.pipeline_state с РАБОЧИМ approve (записывает в calls + ставит approved)."""
    fake = types.ModuleType("shared.pipeline_state")
    fake.resolve_current = lambda: current
    fake.load = lambda s=None: pipelines.get(s if s else current)

    def _approve(slug, by="human", n=2):
        calls.append((slug, by))
        st = next((x for x in pipelines[slug]["stages"] if x.get("n") == 2), None)
        if st:
            st["approved"] = True
        return pipelines[slug]

    fake.approve = _approve
    shared = types.ModuleType("shared")
    shared.pipeline_state = fake
    monkeypatch.setitem(sys.modules, "shared", shared)
    monkeypatch.setitem(sys.modules, "shared.pipeline_state", fake)


def test_sync_approval_projects_openspec_to_pipeline(monkeypatch):
    # R2 ГВОЗДЬ: OpenSpec approved + pipeline НЕ approved -> проекция (approve вызван by=openspec-bridge)
    calls = []
    pipelines = {
        "GKSTCPLK-20": {
            "title": "1С-задача (analyze-1c-task): GKSTCPLK-20",
            "stages": [{"n": 2, "status": "done", "approved": False}],
        }
    }
    _inject_fake_ps_with_approve(monkeypatch, "GKSTCPLK-20", pipelines, calls)
    _inject_fake_approval_state(monkeypatch, approved=True)
    res = bridge.sync_approval("/implement-1c-task GKSTCPLK-20 x")
    assert res["openspec_approved"] is True and res["synced"] is True
    assert calls == [("GKSTCPLK-20", "openspec-bridge")]


def test_sync_approval_already_synced_no_write(monkeypatch):
    # ИДЕМПОТЕНТНОСТЬ: pipeline уже approved -> already-synced, approve НЕ вызван
    calls = []
    pipelines = {
        "GKSTCPLK-21": {
            "title": "1С-задача (analyze-1c-task): GKSTCPLK-21",
            "stages": [{"n": 2, "status": "done", "approved": True}],
        }
    }
    _inject_fake_ps_with_approve(monkeypatch, "GKSTCPLK-21", pipelines, calls)
    _inject_fake_approval_state(monkeypatch, approved=True)
    res = bridge.sync_approval("/implement-1c-task GKSTCPLK-21 x")
    assert res["synced"] is False and res["reason"] == "already-synced" and calls == []


def test_sync_approval_openspec_not_approved_no_write(monkeypatch):
    # OpenSpec НЕ approved -> проекции нет (мост не выдумывает одобрение)
    calls = []
    pipelines = {
        "GKSTCPLK-22": {
            "title": "1С-задача (analyze-1c-task): GKSTCPLK-22",
            "stages": [{"n": 2, "status": "done", "approved": False}],
        }
    }
    _inject_fake_ps_with_approve(monkeypatch, "GKSTCPLK-22", pipelines, calls)
    _inject_fake_approval_state(monkeypatch, approved=False)
    res = bridge.sync_approval("/implement-1c-task GKSTCPLK-22 x")
    assert res["openspec_approved"] is False and res["synced"] is False and calls == []


def test_sync_approval_no_jira(monkeypatch):
    res = bridge.sync_approval("реализовать доработку без джиры")
    assert res["openspec_approved"] is False and res["reason"] == "no-jira"


def test_sync_approval_best_effort(monkeypatch):
    # сбой импорта shared -> не кидает, openspec_approved False (fail-open)
    _force_shared_import_failure(monkeypatch)
    res = bridge.sync_approval("/implement-1c-task GKSTCPLK-1 x")
    assert res["openspec_approved"] is False


def test_sync_approval_systemexit_no_leak(monkeypatch):
    # РЕГРЕСС (code-verify R2): approve кидает SystemExit (BaseException) → sync НЕ всплывает,
    # synced=False, reason approve-failed (openspec_approved уже True — дизайн одобрен через SDD)
    pipelines = {
        "GKSTCPLK-30": {
            "title": "1С-задача (analyze-1c-task): GKSTCPLK-30",
            "stages": [{"n": 2, "status": "done", "approved": False}],
        }
    }
    fake = types.ModuleType("shared.pipeline_state")
    fake.resolve_current = lambda: "GKSTCPLK-30"
    fake.load = lambda s=None: pipelines.get(s if s else "GKSTCPLK-30")

    def _boom(slug, by="human", n=2):
        raise SystemExit("pipeline: нет этапа 2")

    fake.approve = _boom
    shared = types.ModuleType("shared")
    shared.pipeline_state = fake
    monkeypatch.setitem(sys.modules, "shared", shared)
    monkeypatch.setitem(sys.modules, "shared.pipeline_state", fake)
    _inject_fake_approval_state(monkeypatch, approved=True)
    res = bridge.sync_approval("/implement-1c-task GKSTCPLK-30 x")  # НЕ должно кинуть
    assert res["openspec_approved"] is True and res["synced"] is False
    assert res["reason"] == "approve-failed"


def test_sync_approval_no_stage2_skips_approve(monkeypatch):
    # этапа 2 нет (malformed) → no-stage-2, approve НЕ зовётся (иначе SystemExit)
    calls = []
    pipelines = {
        "GKSTCPLK-31": {
            "title": "1С-задача (analyze-1c-task): GKSTCPLK-31",
            "stages": [{"n": 1, "status": "done"}],
        }
    }
    _inject_fake_ps_with_approve(monkeypatch, "GKSTCPLK-31", pipelines, calls)
    _inject_fake_approval_state(monkeypatch, approved=True)
    res = bridge.sync_approval("/implement-1c-task GKSTCPLK-31 x")
    assert res["reason"] == "no-stage-2" and res["synced"] is False and calls == []


def test_gate_systemexit_no_leak(monkeypatch):
    # РЕГРЕСС: approve→SystemExit, но гейт НЕ падает → allow(source=openspec) (fail-open сохранён)
    pipelines = {
        "GKSTCPLK-32": {
            "title": "1С-задача (analyze-1c-task): GKSTCPLK-32",
            "stages": [{"n": 2, "status": "done", "approved": False}],
        }
    }
    fake = types.ModuleType("shared.pipeline_state")
    fake.resolve_current = lambda: "GKSTCPLK-32"
    fake.load = lambda s=None: pipelines.get(s if s else "GKSTCPLK-32")

    def _boom2(slug, by="human", n=2):
        raise SystemExit("boom")

    fake.approve = _boom2
    shared = types.ModuleType("shared")
    shared.pipeline_state = fake
    monkeypatch.setitem(sys.modules, "shared", shared)
    monkeypatch.setitem(sys.modules, "shared.pipeline_state", fake)
    _inject_fake_approval_state(monkeypatch, approved=True)
    res = bridge.gate_1c_implement("/implement-1c-task GKSTCPLK-32 x")  # НЕ должно кинуть
    assert res["ok"] is True and res["hard"] is False and res.get("source") == "openspec"


# --- ADR-041 R3: check_lineage — consistency-чек ANALYSIS-REPORT<->proposal/specs (advisory) ---


def test_lineage_issues_consistent(tmp_path):
    ch = tmp_path / "ch"
    ch.mkdir()
    (ch / "proposal.md").write_text("# P\n" + "x" * 100, encoding="utf-8")
    (ch / "tasks.md").write_text("- [ ] 1.1\n", encoding="utf-8")
    (ch / "specs").mkdir()
    (ch / "specs" / "spec.md").write_text("## ADDED\n", encoding="utf-8")
    assert bridge._lineage_issues(str(ch)) == []


def test_lineage_issues_missing_artifacts(tmp_path):
    ch = tmp_path / "ch"
    ch.mkdir()
    (ch / "proposal.md").write_text("# P\n" + "x" * 100, encoding="utf-8")
    issues = bridge._lineage_issues(str(ch))  # нет tasks.md, нет specs/
    assert any("tasks.md" in i for i in issues) and any("specs/" in i for i in issues)


def test_lineage_issues_staleness(tmp_path):
    import os as _os

    ch = tmp_path / "ch"
    ch.mkdir()
    (ch / "proposal.md").write_text("# P\n" + "x" * 100, encoding="utf-8")
    (ch / "tasks.md").write_text("- [ ] 1.1\n", encoding="utf-8")
    (ch / "specs").mkdir()
    (ch / "specs" / "spec.md").write_text("## ADDED\n", encoding="utf-8")
    ar = tmp_path / "GKSTCPLK-1-ANALYSIS-REPORT.md"
    ar.write_text("# Анализ\n", encoding="utf-8")
    _os.utime(ch / "proposal.md", (1000, 1000))  # proposal старше
    _os.utime(ar, (2000, 2000))  # AR новее -> дрейф
    issues = bridge._lineage_issues(str(ch), str(ar))
    assert any("дрейф" in i for i in issues)


def test_check_lineage_no_jira():
    assert bridge.check_lineage("реализовать без джиры")["checked"] is False


def test_check_lineage_best_effort(monkeypatch):
    _force_shared_import_failure(monkeypatch)
    res = bridge.check_lineage("/implement-1c-task GKSTCPLK-1 x")
    assert res["checked"] is False


def test_check_lineage_wires_change(monkeypatch, tmp_path):
    # discovery: JIRA -> связанный change -> _lineage_issues; checked=True, consistent=False (нет tasks/specs)
    change = tmp_path / "openspec" / "changes" / "gkstcplk-50-x"
    change.mkdir(parents=True)
    (change / ".openspec.yaml").write_text("approval:\n  status: approved\n", encoding="utf-8")
    (change / "proposal.md").write_text("# P\n" + "x" * 100, encoding="utf-8")
    yaml_path = str(change / ".openspec.yaml")
    fake_as = types.ModuleType("shared.approval_state")
    fake_as.list_active_changes = lambda root=None: [("gkstcplk-50-x", yaml_path)]
    fake_as.change_matches_jira = lambda name, yp, jira: True
    monkeypatch.setitem(sys.modules, "shared.approval_state", fake_as)
    sh = sys.modules.get("shared") or types.ModuleType("shared")
    monkeypatch.setitem(sys.modules, "shared", sh)
    monkeypatch.setattr(sh, "approval_state", fake_as, raising=False)
    res = bridge.check_lineage("/implement-1c-task GKSTCPLK-50 x")
    assert res["checked"] is True and res["change_id"] == "gkstcplk-50-x"
    assert res["consistent"] is False and any("tasks.md" in i for i in res["issues"])


# --- ADR-041 R4: use_sdd — единое решение SDD-обёртка vs голый пайплайн в route_1c_task ---


def test_route_use_sdd_simple_false():
    r = bridge.route_1c_task("GKSTCPLK-1 исправить опечатку в наименовании гкс_Справочник")
    assert r["complexity"] == "simple" and r["flow"] == "auto" and r["use_sdd"] is False


def test_route_use_sdd_medium_true():
    r = bridge.route_1c_task("доработать обработку гкс_ЗагрузкаДанных, добавить колонку")
    assert r["complexity"] == "medium" and r["flow"] == "ask_flow" and r["use_sdd"] is True


def test_route_use_sdd_complex_true():
    r = bridge.route_1c_task("GKSTCPLK-2 создать новый документ Перемещение с регистром накопления")
    assert r["complexity"] == "complex" and r["flow"] == "gated" and r["use_sdd"] is True


def test_route_use_sdd_actionless_false():
    # actionless (simple, действие не названо) → use_sdd False (нет SDD для не-задачи)
    r = bridge.route_1c_task("РегистрыСведений.гкс_СостоянияРегистрации.СрезПоследних(&Дата)")
    assert r["actionless"] is True and r["use_sdd"] is False


def test_route_use_sdd_key_all_branches():
    # ключ use_sdd во ВСЕХ ветках возврата (none / ask_1c / confident)
    assert bridge.route_1c_task("как работает RAG embeddings")["use_sdd"] is False  # none
    assert (
        bridge.route_1c_task("исправить ошибку при проведении")["use_sdd"] is False
    )  # ask_1c weak
    assert "use_sdd" in bridge.route_1c_task(
        "GKSTCPLK-1 доработать форму, добавить колонку"
    )  # confident


# --- F-1.6: advance_test_done (collision-immune; all-passed→этап4 — live DoD) ---


def test_advance_test_done_non_runstate():
    assert bridge.advance_test_done("/x/features/foo/other.json") is None
    assert bridge.advance_test_done("") is None


def test_advance_test_done_best_effort():
    # .run-state.json, но файла нет → except → None (best-effort)
    assert bridge.advance_test_done("/no/such/.run-state.json") is None


# --- ADR-050: _live_data_test_passed (чистая функция → collision-immune, без I/O) ---


def test_live_data_pass_clean():
    txt = (
        "## Реализация\nкод...\n\n"
        "## Тестирование на реальных данных\n"
        "- База: ИБ MFM; документ Реализация №123.\n"
        "- Провёл документ на реальных данных → **PASS** (движения сформированы).\n"
    )
    assert bridge._live_data_test_passed(txt) is True


def test_live_data_fail_in_section_rejected():
    txt = (
        "## Тестирование на реальных данных\n- Провёл документ → FAIL: движения не сформированы.\n"
    )
    assert bridge._live_data_test_passed(txt) is False


def test_live_data_skip_static_rejected():
    txt = (
        "## Тестирование на реальных данных\n"
        "SKIP: debug env недоступен [STATIC-ASSUMPTION] — проверено статикой.\n"
    )
    assert bridge._live_data_test_passed(txt) is False


def test_live_data_neuspeshno_rejected():
    # code-verify рек.1: «неуспешно»/«не успешно» НЕ должны ловиться как PASS (успешн⊃неуспешно)
    for neg in ("тест завершён неуспешно", "проверка прошла не успешно", "безуспешно"):
        txt = f"## Тестирование на реальных данных\n- Провёл документ → {neg}.\n"
        assert bridge._live_data_test_passed(txt) is False, neg
    # контроль: легитимное «успешно» (без «не») по-прежнему PASS
    ok = "## Тестирование на реальных данных\n- Документ проведён успешно на данных MFM.\n"
    assert bridge._live_data_test_passed(ok) is True


def test_live_data_checkmark_only_not_verdict():
    # code-verify рек.1: одиночный ✓ на подготовительном подпункте ≠ вердикт → НЕ закрываем
    txt = "## Тестирование на реальных данных\n- ✓ база подготовлена\n- ✓ данные загружены\n"
    assert bridge._live_data_test_passed(txt) is False


def test_live_data_no_heading_rejected():
    # PASS есть, но НЕ в секции live-данных (нет заголовка) → False
    txt = "## Кодирование\nSonar-дельта чистая, PASS. EDT без ошибок.\n"
    assert bridge._live_data_test_passed(txt) is False


def test_live_data_scope_pass_in_other_section():
    # секция live-данных БЕЗ вердикта; PASS — в СОСЕДНЕЙ секции после заголовка → не засчитываем
    txt = (
        "## Тестирование на реальных данных\n"
        "- Данные подготовлены на базе MFM.\n"
        "## Статанализ\n"
        "- Sonar-дельта чистая, PASS.\n"
    )
    assert bridge._live_data_test_passed(txt) is False


def test_live_data_zhivoy_variant():
    txt = "### Живой тест\nПротокол №1 (Янв 2099) — ПРОВЕДЁН. Тестовые данные удалены.\n"
    assert bridge._live_data_test_passed(txt) is True


def test_live_data_empty():
    assert bridge._live_data_test_passed("") is False
    assert bridge._live_data_test_passed(None) is False  # type: ignore[arg-type]


def test_advance_test_done_impl_no_livedata_returns_none(tmp_path):
    # IMPLEMENTATION-PROGRESS с контентом, но БЕЗ секции live-данных → этап 4 НЕ закрываем.
    # (возврат None до использования pipeline_state — путь распознан, но нет доказательства теста)
    f = tmp_path / "IMPLEMENTATION-PROGRESS.md"
    f.write_text("## Кодирование\n" + ("текст реализации " * 30), encoding="utf-8")
    assert bridge.advance_test_done(str(f)) is None


def test_advance_test_done_impl_empty_stub_returns_none(tmp_path):
    # пустой IMPLEMENTATION-PROGRESS (< порога content) → H7-guard → None (даже с заголовком)
    f = tmp_path / "IMPLEMENTATION-PROGRESS.md"
    f.write_text("## Тестирование на реальных данных\nPASS\n", encoding="utf-8")
    assert bridge.advance_test_done(str(f)) is None


# --- input-ingestion: classify_1c_task (чистая функция → fully collision-immune) ---


def test_classify_t1_t2_t3():
    assert bridge.classify_1c_task("Доработать создание Направление GKSTCPLK-2182")["ttype"] == "T1"
    assert (
        bridge.classify_1c_task("Исправить ошибку формирования пробы GKSTCPLK-2177")["ttype"]
        == "T2"
    )
    assert (
        bridge.classify_1c_task("Исправить ошибки тестирование нового функционала GKSTCPLK-2236")[
            "ttype"
        ]
        == "T3"
    )


def test_classify_non_1c_and_ask():
    assert bridge.classify_1c_task("как работает RAG embeddings")["is_1c"] is False
    c = bridge.classify_1c_task("исправь ошибку в гкс_ЛабораторныйАнализ при проведении")
    assert c["is_1c"] is True and c["ask"] is True  # 1С-сигнал+глагол, нет JIRA → ask


# --- Д-1 (P0.3): JIRA-regex denylist технических акронимов + allowlist проектных префиксов ---


def test_jira_acronym_denylist_not_1c():
    """UTF-8/GPT-4/SHA-256 больше НЕ считаются JIRA-кодом → не дают confidence 1.0/veto-иммунитет."""
    for txt in ("поправь кодировку UTF-8", "сравни ответы GPT-4 и GPT-5", "ошибка в SHA-256"):
        c = bridge.classify_1c_task(txt)
        assert c["is_1c"] is False, txt
        assert c["jira"] is None, txt


def test_jira_acronym_downgrades_signal_to_ask():
    """«UTF-8 в отчёте» — 1С-сигнал «отчёт» есть, но акроним не даёт 1.0 → confidence 0.5 (ask)."""
    c = bridge.classify_1c_task("поправь кодировку UTF-8 в отчёте")
    assert c["is_1c"] is True
    assert c["confidence"] == 0.5  # НЕ 1.0 (акроним не JIRA) → безопасный ask, не auto
    assert c["jira"] is None


def test_jira_allowlist_prefix_confident():
    """Проектный префикс GKSTCPLK сохраняет confidence 1.0 (veto-иммунитет)."""
    c = bridge.classify_1c_task("GKSTCPLK-2597 доработать проведение")
    assert c["is_1c"] is True and c["confidence"] == 1.0 and c["jira"] == "GKSTCPLK-2597"


def test_jira_generic_prefix_veto_able():
    """Generic (не allowlist) JIRA-код → is_1c, но confidence 0.7 (veto-able), не 1.0."""
    c = bridge.classify_1c_task("ABC-123 fix something")
    assert c["is_1c"] is True and c["confidence"] == 0.7 and c["jira"] == "ABC-123"


def test_jira_env_allowlist(monkeypatch):
    """env ONEC_JIRA_PREFIXES расширяет allowlist → указанный префикс получает 1.0."""
    monkeypatch.setenv("ONEC_JIRA_PREFIXES", "PROJ,FOO")
    c = bridge.classify_1c_task("PROJ-42 доработать документ")
    assert c["confidence"] == 1.0 and c["jira"] == "PROJ-42"


def test_find_jira_skips_acronym_keeps_real_code():
    """_find_jira: пропускает акроним, но возвращает реальный код если он есть в тексте."""
    m = bridge._find_jira("кодировка UTF-8 в задаче GKSTCPLK-2597")
    assert m is not None and m.group(0) == "GKSTCPLK-2597"
    assert bridge._find_jira("только UTF-8 и SHA-256") is None


# --- P1.1 (Д-2): SetFit-порог из калиброванного onec_setfit_gate.threshold() ---


def test_setfit_threshold_safe_uses_gate(monkeypatch):
    """_setfit_threshold_safe делегирует onec_setfit_gate.threshold() (калиброванный), не константе."""
    import types

    fake = types.ModuleType("shared.onec_setfit_gate")
    fake.threshold = lambda: 0.83
    monkeypatch.setitem(sys.modules, "shared.onec_setfit_gate", fake)
    assert bridge._setfit_threshold_safe() == 0.83


def test_setfit_threshold_safe_fallback(monkeypatch):
    """Сбой импорта гейта → fallback на константу _SETFIT_THRESHOLD (не падаем)."""
    import builtins

    real_import = builtins.__import__

    def boom(name, *a, **k):
        if name == "shared.onec_setfit_gate":
            raise ImportError("no gate")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", boom)
    assert bridge._setfit_threshold_safe() == bridge._SETFIT_THRESHOLD


# --- P1.3 (К-4): gate_1c_implement advisory при отсутствии активного 1С-пайплайна ---


def test_gate_implement_advisory_when_no_pipeline(monkeypatch):
    """Нет активного 1С-пайплайна → ok=True (не блок) + advisory-поле (G4 no-op не молчалив)."""
    monkeypatch.setattr(bridge, "resolve_active_1c_slug", lambda p: None)
    res = bridge.gate_1c_implement("реализуй что-то без jira и без пайплайна")
    assert res["ok"] is True and res["hard"] is False
    assert "advisory" in res and "G4" in res["advisory"]


# --- P1.5 (класс «чужой задачи»): _owning_1c_slug — владелец артефакта по пути ---


def test_owning_slug_by_statedir_ancestor(tmp_path):
    """Владелец = пайплайн, чей state_dir — предок артефакта (точная привязка, не CURRENT)."""

    class FakePS:
        @staticmethod
        def iter_states():
            yield "GKSTCPLK-1", {"title": "1С-задача (analyze): a"}
            yield "GKSTCPLK-2", {"title": "1С-задача (analyze): b"}

        @staticmethod
        def state_dir(slug):
            return tmp_path / slug

    (tmp_path / "GKSTCPLK-2").mkdir()
    art = tmp_path / "GKSTCPLK-2" / "ANALYSIS-REPORT.md"
    assert bridge._owning_1c_slug(str(art), FakePS) == "GKSTCPLK-2"


def test_owning_slug_prefers_deepest_ancestor(tmp_path):
    """P1.5 harden: среди нескольких state_dir-предков выбирается САМЫЙ ГЛУБОКИЙ (специфичный)."""

    class FakePS:
        @staticmethod
        def iter_states():
            yield "PARENT", {"title": "1С-задача (analyze): parent"}
            yield "CHILD", {"title": "1С-задача (analyze): child"}

        @staticmethod
        def state_dir(slug):
            return tmp_path if slug == "PARENT" else tmp_path / "sub" / "task"

    art = tmp_path / "sub" / "task" / "ANALYSIS-REPORT.md"
    assert bridge._owning_1c_slug(str(art), FakePS) == "CHILD"


def test_owning_slug_by_jira_fallback(tmp_path):
    """Fallback: JIRA в пути совпал с зарегистрированным slug (когда state_dir не предок)."""

    class FakePS:
        @staticmethod
        def iter_states():
            yield "GKSTCPLK-2637", {"title": "1С-задача (analyze): sonar"}

        @staticmethod
        def state_dir(slug):
            return tmp_path / "elsewhere" / slug

    art = "configuration/260304_GKSTCPLK-2182/docs/260701_GKSTCPLK-2637/ANALYSIS-REPORT.md"
    assert bridge._owning_1c_slug(art, FakePS) == "GKSTCPLK-2637"


def test_owning_slug_none_when_unregistered(tmp_path):
    """Артефакт вне зарегистрированных задач → None (caller падает на CURRENT-legacy)."""

    class FakePS:
        @staticmethod
        def iter_states():
            yield "GKSTCPLK-9", {"title": "1С-задача (analyze): x"}

        @staticmethod
        def state_dir(slug):
            return tmp_path / slug

    assert bridge._owning_1c_slug(str(tmp_path / "other" / "REPORT.md"), FakePS) is None


# --- run-1c-task: resolve_task_input (чистая функция: os.path + derive_slug → collision-immune) ---


def test_resolve_input_jira():
    r = bridge.resolve_task_input("GKSTCPLK-2182 доработать форму")
    assert r["kind"] == "jira" and r["slug"] == "GKSTCPLK-2182" and r["folder"] is None


def test_resolve_input_chat():
    # описание из чата (нет пути, нет JIRA) → chat; кириллица → общий slug
    r = bridge.resolve_task_input("исправить ошибку проведения накладной")
    assert r["kind"] == "chat" and r["folder"] is None and r["slug"]


def test_resolve_input_folder(tmp_path):
    # существующая папка ТЗ с JIRA в имени → kind=folder, slug из имени папки
    d = tmp_path / "260615_GKSTCPLK-2200"
    d.mkdir()
    r = bridge.resolve_task_input(str(d))
    assert r["kind"] == "folder" and r["slug"] == "GKSTCPLK-2200" and r["folder"] == str(d)


def test_resolve_input_nonexistent_path_with_jira():
    # путь-вид, но папки нет; в строке есть JIRA → ветка jira (не folder)
    r = bridge.resolve_task_input("C:/no/such/GKSTCPLK-2201")
    assert r["kind"] == "jira" and r["slug"] == "GKSTCPLK-2201" and r["folder"] is None


def test_resolve_input_empty_is_chat():
    # граница (контракт явно): пусто → chat со слотом "1c-task"
    assert bridge.resolve_task_input("")["kind"] == "chat"
    assert bridge.resolve_task_input("")["slug"] == "1c-task"


def test_resolve_input_folder_no_jira_ascii_slug(tmp_path):
    # папка без JIRA в имени → kind=folder, slug = ASCII-slug имени папки (под-ветка derive_slug)
    d = tmp_path / "unload-spec"
    d.mkdir()
    r = bridge.resolve_task_input(str(d))
    assert r["kind"] == "folder" and r["slug"] == "unload-spec" and r["folder"] == str(d)


# --- классификатор сложности (estimate_effort) + маршрутизация (route_1c_task) ---


def test_estimate_effort_bands():
    # light → simple; modify → medium; heavy_obj → complex
    assert (
        bridge.estimate_effort("исправить опечатку в наименовании справочника")["complexity"]
        == "simple"
    )
    assert bridge.estimate_effort("доработать форму, добавить колонку")["complexity"] == "medium"
    assert (
        bridge.estimate_effort("создать новый документ с регистром накопления")["complexity"]
        == "complex"
    )


def test_estimate_effort_folder_bump():
    # ТЗ-папка (+2) поднимает баллы: cross(+3)=medium → +folder=complex
    base = bridge.estimate_effort("настроить обмен данными")
    folder = bridge.estimate_effort("настроить обмен данными", is_folder=True)
    assert base["complexity"] == "medium" and folder["points"] > base["points"]


def test_route_non_1c_none():
    r = bridge.route_1c_task("как работает RAG embeddings")
    assert r["flow"] == "none" and r["is_1c"] is False


def test_route_simple_auto():
    # уверенный 1С (JIRA), light → simple → auto
    r = bridge.route_1c_task("GKSTCPLK-1 исправить опечатку в наименовании гкс_Справочник")
    assert r["confident_1c"] is True and r["complexity"] == "simple" and r["flow"] == "auto"


def test_route_complex_gated():
    # уверенный 1С (JIRA), heavy_obj → complex → gated
    r = bridge.route_1c_task("GKSTCPLK-2 создать новый документ Перемещение с регистром накопления")
    assert r["complexity"] == "complex" and r["flow"] == "gated"


def test_route_medium_ask_flow():
    # уверенный 1С (гкс_/CamelCase), modify → medium → ask_flow
    r = bridge.route_1c_task("доработать обработку гкс_ЗагрузкаДанных, добавить колонку")
    assert r["confident_1c"] is True and r["complexity"] == "medium" and r["flow"] == "ask_flow"


def test_route_weak_1c_ask():
    # 1С-сигнал есть (проведени+исправ), но НЕТ JIRA/strong-маркера → ask_1c (сомнение → спросить)
    r = bridge.route_1c_task("исправить ошибку при проведении")
    assert r["is_1c"] is True and r["confident_1c"] is False and r["flow"] == "ask_1c"


def test_route_attribute_name_not_light_downgrade():
    # регресс (live-smoke 2026-06-15): имя реквизита «Комментарий»/«Заголовок» НЕ должно
    # косметически (light) занижать medium-задачу до simple — light только для чистой косметики
    r = bridge.route_1c_task("доработать обработку гкс_ЗагрузкаДанных добавить колонку Комментарий")
    assert r["complexity"] == "medium" and r["flow"] == "ask_flow"


# --- Находка 1 (2026-06-18): группа develop — substantial-задачи НЕ должны уходить в simple→auto ---


def test_estimate_effort_develop_group():
    # «разработать/реализовать + печатная форма/механизм/функционал» → develop (+2) → medium, не simple
    for txt in [
        "разработать печатную форму",
        "реализовать функционал по внесению данных",
        "разработать механизм приёмки авто",
        "создать новую печатную форму",
    ]:
        e = bridge.estimate_effort(txt, ttype="T1")
        assert e["complexity"] == "medium" and "develop" in e["signals"], (txt, e)


def test_route_develop_printform_not_auto():
    # РЕГРЕСС Находки 1: реальные печатные формы / «разработать механизм» с JIRA (confident)
    # больше НЕ авто-прогоняются мимо гейта ревью (раньше: simple→auto).
    for t in [
        "GKSTCPLK-2377 Создать новую печатную форму Акт забраковки товара",
        "GKSTCPLK-2400 Разработать печатную форму Ярлык пробы",
        "GKSTCPLK-2414 Разработать механизм приемки авто с другим порядком операции",
        "GKSTCPLK-2483 Реализовать функционал по внесению данных в документ Регистрация на ПЛК",
    ]:
        r = bridge.route_1c_task(t)
        assert r["confident_1c"] is True, t
        assert r["complexity"] in ("medium", "complex"), (t, r["complexity"])
        assert r["flow"] != "auto", (t, r["flow"])


def test_route_exchange_setup_not_auto():
    # «настроить обмен с базой УТ» → cross (расширенный) → medium → не auto (была simple/auto)
    r = bridge.route_1c_task("GMFM-5826 Настроить обмен с базой УТ Инфида и МФМ")
    assert r["complexity"] in ("medium", "complex") and r["flow"] != "auto"


def test_route_truly_cosmetic_still_auto():
    # инвариант: truly-cosmetic правка (нет develop/modify/heavy сигналов) остаётся simple→auto
    r = bridge.route_1c_task("GKSTCPLK-1 исправить опечатку в наименовании гкс_Справочник")
    assert r["complexity"] == "simple" and r["flow"] == "auto"


# --- Находка 2 (2026-06-18): veto НЕ-1С тех-контекста (precision на русскоязычной разработке) ---


def test_has_non_1c_context_helper():
    # высокоточные маркеры НЕ-1С разработки ловятся (regex-робастные формы + пробельные варианты)
    for t in [
        "обработка в FastAPI",
        "fast api роутер",
        "поиск в Qdrant",
        "тест на pytest",
        "агент на langchain",
        "rerank в search pipeline",
        "образ docker",
        "очистка redis",
    ]:
        assert bridge._has_non_1c_context(t) is True, t
    # чистая 1С-задача — НЕ тех-контекст
    for t in [
        "доработать проведение документа Реализация",
        "добавить реквизит в справочник",
        "разработать печатную форму Акт",
    ]:
        assert bridge._has_non_1c_context(t) is False, t


def test_route_veto_framework_dev_to_none():
    # РЕГРЕСС Находки 2: слабый 1С-сигнал (обработк/механизм/отчёт + глагол) + явный НЕ-1С маркер
    # → veto → flow=none (молчим), а не ask_1c (шум). Детерминично (is_1c через regex, не семантику).
    for t in [
        "Доработать обработку ошибок в API роутере FastAPI",
        "Создать обработку входящих webhook от GitHub",
        "Реализовать механизм rerank в search pipeline",
        "Сформировать отчёт по латентности через DuckDB",
        "Доработать механизм синхронизации векторов между Qdrant коллекциями",
    ]:
        r = bridge.route_1c_task(t)
        assert r["is_1c"] is False and r["flow"] == "none", (t, r["flow"])
        assert r["non_1c_context"] is True, t


def test_route_veto_respects_confident_1c():
    # ИНВАРИАНТ безопасности: confident-вход (гкс_/JIRA/код/CamelCase) с тех-словом НЕ ветируется —
    # реальная 1С-задача, упомянувшая инструмент, защищена.
    r = bridge.route_1c_task("доработать обработку гкс_ЛабораторныйАнализ с выгрузкой в postgres")
    assert r["confident_1c"] is True and r["is_1c"] is True and r["flow"] != "none"
    assert r["non_1c_context"] is False
    r2 = bridge.route_1c_task("GKSTCPLK-1 доработать выгрузку регистра для duckdb-отчёта")
    assert r2["is_1c"] is True and r2["flow"] != "none"


def test_route_veto_preserves_weak_real_1c():
    # 1С-задача со слабым сигналом, но БЕЗ тех-маркера → veto НЕ срабатывает → остаётся ask_1c
    r = bridge.route_1c_task("доработать обработку проведения накладной")
    assert r["is_1c"] is True and r["flow"] == "ask_1c" and r["non_1c_context"] is False


def test_route_non_1c_carries_non_1c_context_key():
    # ключ non_1c_context присутствует во всех возвратах (наблюдаемость)
    assert "non_1c_context" in bridge.route_1c_task("как работает RAG embeddings")
    assert "non_1c_context" in bridge.route_1c_task("GKSTCPLK-1 доработать форму")


def test_route_camelcase_confident_is_veto_able_c4():
    # C4: CamelCase-кириллица (confidence 0.7) — слабейший confident-сигнал — ВЕТИРУЕТСЯ НЕ-1С
    # тех-маркером → none (раньше confident обходил veto → ошибочный auto/ask_flow).
    r = bridge.route_1c_task("добавить функцию ПолучитьЭмбеддинг в langchain пайплайн")
    assert r["confidence"] == 0.7  # только CamelCase-strong, без jira/code/definitive
    assert r["is_1c"] is False and r["flow"] == "none" and r["non_1c_context"] is True


def test_route_strong_confident_stays_veto_immune_c4():
    # ИНВАРИАНТ C4: строго-уверенный (≥0.9 — гкс_/код/JIRA) с тем же тех-словом НЕ ветируется.
    r = bridge.route_1c_task("доработать гкс_ЗагрузкаДанных с выгрузкой в langchain")
    assert r["confidence"] == 0.9 and r["is_1c"] is True
    assert r["flow"] != "none" and r["non_1c_context"] is False


# --- recall-расширение детектора (заземлено на configuration/.../docs реальные задачи) ---


def test_recall_oblique_form_now_detected():
    # miss-кейс ревьюера: косвенный падеж, без точки/JIRA/гкс_ → теперь is_1c, но weak → ask_1c
    r = bridge.route_1c_task("доработать форму документа Расход")
    assert r["is_1c"] is True and r["confident_1c"] is False and r["flow"] == "ask_1c"


def test_recall_real_titles():
    # реальные заголовки configuration/260304…/docs (без JIRA) — детектятся через term+verb
    for t in [
        "Создать новую печатную форму Акт забраковки товара",
        "Настроить обмен с базой УТ Инфида",
        "Дополнить АРМ детали блок лаб анализ",
        "Восстановить предопределенные элементы справочников",
        "Скорректировать профили доступа в 1С Управление транспортом",
    ]:
        assert bridge.classify_1c_task(t)["is_1c"] is True, t


def test_recall_definitive_marker_without_verb():
    # гкс_ / configuration-path → 1С даже БЕЗ таск-глагола (definitive)
    assert bridge.classify_1c_task("посмотри гкс_НастройкиНазначенияРазгрузки")["is_1c"] is True
    assert bridge.classify_1c_task("открой configuration/260304_X/docs описание")["is_1c"] is True


def test_recall_camelcase_object_with_verb():
    # CamelCase-объект без доменного-термина-подстроки + глагол → is_1c (арбитрарные имена объектов)
    r = bridge.route_1c_task("доработать НаправлениеНаРазгрузку")
    assert r["is_1c"] is True and r["confident_1c"] is True


def test_recall_t3_passive_uchteno():
    # T3-формулировка «не учтено» (учт-глагол) + 1С-сигнал → is_1c + ttype T3 (рек. ревьюера)
    c = bridge.classify_1c_task("при тестировании не учтено формирование движений в регистре")
    assert c["is_1c"] is True and c["ttype"] == "T3"


def test_recall_non_1c_still_none():
    # расширение НЕ ловит не-1С: вопрос/код без таск-глагола ИЛИ без 1С-сигнала
    assert bridge.classify_1c_task("как работает RAG embeddings")["is_1c"] is False
    assert (
        bridge.classify_1c_task("что такое ТабличныйДокумент")["is_1c"] is False
    )  # CamelCase, но нет глагола
    assert bridge.classify_1c_task("напиши скрипт на python для парсинга")["is_1c"] is False


# --- code-presence path: наличие 1С-кода = ключевой признак (БЕЗ таск-глагола) ---


def test_code_path_manager_call_no_verb():
    # вызов менеджера (мн.число) + СрезПоследних — код без глагола → is_1c + confident
    r = bridge.route_1c_task("РегистрыСведений.гкс_СостоянияРегистрации.СрезПоследних(&Дата)")
    assert r["is_1c"] is True and r["code"] is True and r["confident_1c"] is True


def test_code_path_event_handler_no_verb():
    c = bridge.classify_1c_task("ПередЗаписью(Отказ, Замещение)")
    assert c["is_1c"] is True and c["code"] is True


def test_code_path_bsl_closer_no_verb():
    # закрывающее ключевое слово BSL — однозначный код
    assert bridge.classify_1c_task("вставь сюда КонецПроцедуры")["is_1c"] is True


def test_code_path_query_token_no_verb():
    c = bridge.classify_1c_task("ВЫРАЗИТЬ(Ссылка КАК Документ.Расход) ЕСТЬNULL(Сумма, 0)")
    assert c["code"] is True and c["is_1c"] is True


def test_code_path_bsp_call_confident_route():
    # БСП-вызов → код → confident → маршрут по сложности (НЕ ask_1c)
    r = bridge.route_1c_task("замени на ОбщегоНазначения.ЗначениеРеквизитаОбъекта")
    assert r["is_1c"] is True and r["confident_1c"] is True and r["flow"] != "ask_1c"


def test_code_path_pasted_bsl_block_no_dict_verb():
    # вставленный BSL без таск-глагола из словаря (Если/Тогда/Возврат — не _TASK_VERB)
    src = "Если ОбменДанными.Загрузка Тогда Возврат; КонецЕсли;"
    c = bridge.classify_1c_task(src)
    assert c["is_1c"] is True and c["code"] is True


# --- расширение доменной лексики (чат-транскрипты: домен-слово + глагол) ---


def test_domain_expansion_with_verb():
    for t in [
        "перепровести направление на разгрузку",
        "заблокировать приёмку по усиленному контролю",
        "доработать формирование номера пробы из АРМ композита",
        "зарегистрировать отгрузку к обмену",
        "выгрузить лабораторный анализ в отчёт",
    ]:
        assert bridge.classify_1c_task(t)["is_1c"] is True, t


def test_domain_abbreviations_with_verb():
    # узкие аббревиатуры предметной области + глагол
    assert bridge.classify_1c_task("дополнить проведение по ФНП")["is_1c"] is True
    assert bridge.classify_1c_task("исправить запись на ПЛК")["is_1c"] is True


# --- регрессия: расширение НЕ ломает негативы и инвариант «слабый сигнал → ask_1c» ---


def test_code_path_preserves_camelcase_negative():
    # CamelCase-идентификатор без кода-конструкции и без глагола → НЕ 1С (вопрос)
    c = bridge.classify_1c_task("что такое ТабличныйДокумент")
    assert c["is_1c"] is False and c["code"] is False


def test_code_path_no_prose_false_positive():
    # prose: заглавное слово + точка + ПРОБЕЛ — НЕ код (member-guard .(Заглавная|гкс_))
    assert bridge.classify_1c_task("Это важный Документ. Прочитай его внимательно")["code"] is False


def test_domain_term_alone_not_1c():
    # доменное слово БЕЗ глагола и БЕЗ кода → сигнала мало (нужна пара термин+глагол)
    assert bridge.classify_1c_task("лабораторный анализ")["is_1c"] is False


def test_code_path_no_module_suffix_or_bsl_false_positive():
    # ревью-фикс: англ. слова ООП и хвост `.bsl` НЕ должны давать code (иначе FP → auto-прогон).
    assert bridge.classify_1c_task("the ObjectModule pattern in OOP design")["code"] is False
    assert bridge.classify_1c_task("see utils.bsl in the repo for details")["code"] is False
    assert bridge.classify_1c_task("our FormModule handles the UI layer")["is_1c"] is False


# --- #2: калиброванная уверенность (confidence ∈ {0.0, 0.5, 0.7, 0.9, 1.0}) ---


def test_confidence_jira_max():
    assert bridge.classify_1c_task("GKSTCPLK-2182 доработать форму")["confidence"] == 1.0


def test_confidence_code_or_definitive_high():
    assert bridge.classify_1c_task("Документы.гкс_Основание.Записать()")["confidence"] == 0.9
    assert bridge.classify_1c_task("посмотри гкс_НастройкиРазгрузки")["confidence"] == 0.9
    assert bridge.classify_1c_task("вставь сюда КонецПроцедуры")["confidence"] == 0.9


def test_confidence_strong_camelcase_mid():
    # CamelCase-объект без гкс_/jira/code + глагол → strong → 0.7
    assert bridge.classify_1c_task("доработать НаправлениеНаРазгрузку")["confidence"] == 0.7


def test_confidence_weak_signal_verb_low():
    # доменный термин + глагол, без strong/code/jira → 0.5
    assert bridge.classify_1c_task("исправить ошибку при проведении")["confidence"] == 0.5


def test_confidence_non_1c_zero():
    assert bridge.classify_1c_task("как работает RAG embeddings")["confidence"] == 0.0


def test_confidence_threshold_preserves_confident_1c():
    # инвариант #2: confident_1c == (confidence >= 0.7), поведение прежнее
    cases = [
        ("GKSTCPLK-1 доработать", True),  # jira → 1.0
        ("доработать НаправлениеНаРазгрузку", True),  # strong → 0.7
        ("исправить ошибку при проведении", False),  # weak → 0.5 → ask_1c
        ("как работает RAG", False),  # none → 0.0
    ]
    for text, exp in cases:
        r = bridge.route_1c_task(text)
        assert r["confident_1c"] is exp, text
        if r["is_1c"]:
            assert (r["confidence"] >= 0.7) is r["confident_1c"], text


# --- #3: TF-IDF semantic fallback (recall-boost на неуверенных входах) ---


def test_semantic_sim_module():
    spec = importlib.util.spec_from_file_location(
        "onec_sf_t", _HOOKS / "shared" / "onec_semantic_fallback.py"
    )
    sf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sf)
    hi = sf.semantic_sim("не отрабатывает кнопка печати на форме акта приёмки")  # парафраз ТЗ
    lo = sf.semantic_sim("how does RAG embeddings work")  # английский, не 1С
    assert hi >= 0.55 and lo < 0.55 and hi > lo


def test_route_semantic_promotes_fn():
    # regex упускает (нет таск-глагола), semantic ловит парафраз ТЗ → is_1c=True, flow=ask_1c (мягко)
    r = bridge.route_1c_task("не отрабатывает кнопка печати на форме акта приёмки")
    assert r["is_1c"] is True and r["flow"] == "ask_1c" and r["confident_1c"] is False
    assert r["semantic_sim"] >= 0.55


def test_route_semantic_negative_stays_none():
    r = bridge.route_1c_task("как работает RAG embeddings")
    assert r["is_1c"] is False and r["flow"] == "none" and r["semantic_sim"] < 0.55


def test_route_confident_skips_semantic():
    # на confident-входе semantic НЕ вызывается (sem=0.0) — экономия + уверенный путь не тронут
    r = bridge.route_1c_task("GKSTCPLK-1 доработать форму")
    assert r["confident_1c"] is True and r["semantic_sim"] == 0.0


# --- ADR-025: SetFit-гейт opt-in — поведение route при выключенном гейте (behavior-preserving) ---


def test_route_semantic_source_tfidf_when_gate_off():
    # гейт по умолчанию ВЫКЛЮЧЕН → семантический слой = TF-IDF (откат), новый ключ проставлен
    r = bridge.route_1c_task("не отрабатывает кнопка печати на форме акта приёмки")
    assert r["is_1c"] is True and r["flow"] == "ask_1c"
    assert r["semantic_source"] == "tfidf"


def test_route_semantic_source_skipped_on_confident():
    # confident-вход → семантику не зовём → source=skipped (и sim=0.0, как прежде)
    r = bridge.route_1c_task("GKSTCPLK-1 доработать форму")
    assert r["semantic_sim"] == 0.0 and r["semantic_source"] == "skipped"


def test_route_non_1c_carries_source():
    # негатив тоже несёт semantic_source (ранний return дополнен ключом)
    r = bridge.route_1c_task("как работает RAG embeddings")
    assert r["flow"] == "none" and r["semantic_source"] == "tfidf"


def test_semantic_signal_falls_back_to_tfidf():
    # _semantic_signal: гейт спит (setfit_prob→None) → источник tfidf, скор = semantic_sim
    score, source, hit = bridge._semantic_signal(
        "не отрабатывает кнопка печати на форме акта приёмки"
    )
    assert source == "tfidf" and isinstance(hit, bool) and score > 0.0


# --- Находка 3 (2026-06-18): гейт «действие не названо» (actionless) auto → ask_flow ---

# Точный вход живого прогона: путь к ManagerModule + BSL + предупреждение анализатора + вопрос.
# Детект «1С» уверен (гкс_ + код), но действия НЕ названо (нет таск-глагола, нет work-сигнала).
_ACTIONLESS_PROMPT = (
    "Project/TransportManagement/src/DataProcessors/"
    "гкс_ПечатьАктВозврата_Беларусь/ManagerModule.bsl "
    "Шаблоны = Новый Структура(); "
    "Предыдущее значение переменной не используется "
    "Это 1С задача?"
)


def test_route_actionless_headline_user_example():
    # ГВОЗДЬ: ровно вход пользователя → 1С уверенно, но verb-less ∧ zero-signal → НЕ auto, а ask_flow.
    r = bridge.route_1c_task(_ACTIONLESS_PROMPT)
    assert r["is_1c"] is True
    assert r["confident_1c"] is True  # гкс_/код → confident сохранён
    assert r["complexity"] == "simple"  # ноль work-сигналов
    assert r["actionless"] is True
    assert r["flow"] == "ask_action"  # C1: actionless ≠ medium — отдельное значение flow
    assert r["flow"] != "auto"


def test_route_actionless_code_dump_no_verb():
    # вставленный вызов менеджера БЕЗ таск-глагола → confident по коду, но действие не названо → ask_flow
    r = bridge.route_1c_task("РегистрыСведений.гкс_СостоянияРегистрации.СрезПоследних(&Дата)")
    assert r["confident_1c"] is True and r["actionless"] is True and r["flow"] == "ask_action"


def test_route_actionless_false_when_verb_present():
    # ИНВАРИАНТ: confident+simple С глаголом («исправить») → actionless=False, остаётся auto.
    r = bridge.route_1c_task("GKSTCPLK-1 исправить опечатку в наименовании гкс_Справочник")
    assert r["actionless"] is False and r["flow"] == "auto"


def test_route_actionless_false_when_work_signal_present():
    # work-сигнал (modify) даёт points>2 → не simple → гейт не достижим → actionless=False.
    r = bridge.route_1c_task("доработать обработку гкс_ЗагрузкаДанных, добавить колонку")
    assert r["actionless"] is False and r["flow"] == "ask_flow"  # medium ask_flow, НЕ actionless


def test_route_actionless_key_present_all_returns():
    # наблюдаемость: ключ actionless во ВСЕХ ветках возврата (none / ask_1c / confident).
    assert "actionless" in bridge.route_1c_task("как работает RAG embeddings")  # none
    assert "actionless" in bridge.route_1c_task("исправить ошибку при проведении")  # ask_1c (weak)
    assert "actionless" in bridge.route_1c_task(
        "GKSTCPLK-1 доработать форму, добавить колонку"
    )  # confident
    # в none/ask_1c ветках гейт неактуален → False
    assert bridge.route_1c_task("как работает RAG embeddings")["actionless"] is False
    assert bridge.route_1c_task("исправить ошибку при проведении")["actionless"] is False


# --- расширение _TASK_VERB частыми глаголами (start-`\b` против substring-FP) ---


def test_task_verb_extension_common_verbs():
    # частые глаголы, ранее отсутствовавшие в словаре → теперь распознаются
    for t in [
        "замени макет печати",
        "поменяй реквизит",
        "перепиши запрос",
        "переписать модуль",
        "переделай форму",
        "обнови справочник",
        "переименуй документ",
        "поправь печать",
    ]:
        assert bridge._TASK_VERB.search(t), t


def test_task_verb_extension_no_substring_fp():
    # start-`\b`: добавленные основы НЕ цепляют похожие НЕ-глаголы (и старые основы тоже их не ловят)
    for t in ["взамен старого порядка", "деловая переписка по почте", "переделка тут не нужна"]:
        assert bridge._TASK_VERB.search(t) is None, t


def test_task_verb_extension_route_replace_is_action():
    # эффект на гейт: «замени X на Y» теперь = названное действие (не actionless) → маршрут по сложности
    r = bridge.route_1c_task("замени на ОбщегоНазначения.ЗначениеРеквизитаОбъекта")
    assert r["confident_1c"] is True and r["actionless"] is False and r["flow"] != "ask_1c"
