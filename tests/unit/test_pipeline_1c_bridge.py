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

_HOOKS = Path(__file__).resolve().parents[2] / ".claude" / "hooks"

_spec = importlib.util.spec_from_file_location(
    "pipeline_1c_bridge_t", _HOOKS / "shared" / "pipeline_1c_bridge.py"
)
bridge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bridge)


def test_derive_slug_jira():
    # JIRA-код = стабильный ID задачи
    assert bridge.derive_slug("/implement-1c-task GKSTCPLK-2182 доработать") == "GKSTCPLK-2182"


def test_is_1c_task_title():
    # N4: единый предикат 1С-пайплайна — paren-form True, lookalike/прочее False
    assert bridge.is_1c_task_title("1С-задача (run-1c-task): GKSTCPLK-1") is True
    assert bridge.is_1c_task_title("1С-задача (analyze-1c-task): x") is True
    assert bridge.is_1c_task_title("1С-задача из чата: классификатор") is False  # lookalike (без скобки)
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
    monkeypatch.setitem(sys.modules, "shared", types.ModuleType("shared"))
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
    monkeypatch.setitem(sys.modules, "shared", types.ModuleType("shared"))
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
    monkeypatch.setitem(sys.modules, "shared", types.ModuleType("shared"))
    res = bridge.gate_1c_implement("/implement-1c-task GKSTCPLK-1 x")
    assert res["ok"] is True


# --- F-1.6: advance_test_done (collision-immune; all-passed→этап4 — live DoD) ---


def test_advance_test_done_non_runstate():
    assert bridge.advance_test_done("/x/features/foo/other.json") is None
    assert bridge.advance_test_done("") is None


def test_advance_test_done_best_effort():
    # .run-state.json, но файла нет → except → None (best-effort)
    assert bridge.advance_test_done("/no/such/.run-state.json") is None


# --- input-ingestion: classify_1c_task (чистая функция → fully collision-immune) ---


def test_classify_t1_t2_t3():
    assert bridge.classify_1c_task("Доработать создание Направление GKSTCPLK-2182")["ttype"] == "T1"
    assert bridge.classify_1c_task("Исправить ошибку формирования пробы GKSTCPLK-2177")["ttype"] == "T2"
    assert bridge.classify_1c_task("Исправить ошибки тестирование нового функционала GKSTCPLK-2236")["ttype"] == "T3"


def test_classify_non_1c_and_ask():
    assert bridge.classify_1c_task("как работает RAG embeddings")["is_1c"] is False
    c = bridge.classify_1c_task("исправь ошибку в гкс_ЛабораторныйАнализ при проведении")
    assert c["is_1c"] is True and c["ask"] is True  # 1С-сигнал+глагол, нет JIRA → ask


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
    assert bridge.estimate_effort("исправить опечатку в наименовании справочника")["complexity"] == "simple"
    assert bridge.estimate_effort("доработать форму, добавить колонку")["complexity"] == "medium"
    assert bridge.estimate_effort("создать новый документ с регистром накопления")["complexity"] == "complex"


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
    assert bridge.classify_1c_task("что такое ТабличныйДокумент")["is_1c"] is False  # CamelCase, но нет глагола
    assert bridge.classify_1c_task("напиши скрипт на python для парсинга")["is_1c"] is False
