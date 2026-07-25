"""Регрессия 260725: клиентский потолок ожидания ≠ провал инструмента.

У долгой операции EDT клиент обрывает ожидание (~60с) и PostToolUse не приходит, хотя на
сервере вызов завершился `outcome=ok` (живой замер журнала: `create_project` 60 253мс,
`delete_project` 134 035/203 137мс, `update_database` 119 398/215 360/3 147 392мс). Метрика
читала такой непарный Pre как провал инструмента → ложные broken/degraded (`delete_project`
«0 успешных из 3 попыток» при ДВУХ успешных удалениях).

Фикс тем же приёмом, что вычет блоков гардов: серверный успех, подтверждённый журналом,
уходит в отдельный счётчик `client_timeout`, а не в `failed`. Тесты пинят обе стороны
инварианта — вычет применяется, когда доказательство есть, и НЕ применяется, когда его нет
(нет журнала / вне допуска по времени / длительность ниже клиентского потолка).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import edt_journal as ej
import tool_effectiveness as te

_ATH_PATH = _SCRIPTS / "analyze_tool_health.py"
_spec = importlib.util.spec_from_file_location("_ath_client_timeout", _ATH_PATH)
ath = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ath)

NOW = datetime(2026, 7, 25, 12, 0, 0)
T0 = NOW - timedelta(hours=3)  # вне grace-окна: непарный Pre уже разрешился

JOURNAL = """\
!ENTRY com.ditrix.edt.mcp.server 1 0 2026-07-23 13:00:38.100
!MESSAGE Completed tools/call: update_database in 119398ms, outcome=ok

!ENTRY com.ditrix.edt.mcp.server 1 0 2026-07-23 13:05:00.000
!MESSAGE Completed tools/call: list_projects in 12ms, outcome=ok

!ENTRY com.ditrix.edt.mcp.server 2 0 2026-07-24 18:16:12.375
!MESSAGE Failed tools/call: delete_project - Project not found: гкс_Эмуляция. Use list_projects.

!ENTRY com.ditrix.edt.mcp.server 2 0 2026-07-24 18:16:12.375
!MESSAGE Completed tools/call: delete_project in 0ms, outcome=error
"""


def _pre(tool, tcid, ts, session="s1"):
    return {
        "event": "PreToolUse",
        "tool": tool,
        "tool_call_id": tcid,
        "ts": ts.isoformat(),
        "session": session,
    }


def _post(tool, tcid, ts):
    return {"event": "PostToolUse", "tool": tool, "tool_call_id": tcid, "ts": ts.isoformat()}


# ── 1. парсер журнала EDT ─────────────────────────────────────────────────────


def test_parse_journal_extracts_completed_and_failures():
    completed, failures = ej.parse_journal(JOURNAL, source="ws")
    assert [(r["tool"], r["ms"], r["outcome"]) for r in completed] == [
        ("update_database", 119398, "ok"),
        ("list_projects", 12, "ok"),
        ("delete_project", 0, "error"),
    ]
    # start = end − длительность: именно по нему вызов сопоставляется с Pre
    upd = completed[0]
    assert upd["end"] == datetime(2026, 7, 23, 13, 0, 38, 100000)
    assert upd["start"] == upd["end"] - timedelta(milliseconds=119398)
    assert upd["source"] == "ws"
    assert len(failures) == 1
    assert failures[0]["tool"] == "delete_project"
    assert failures[0]["text"].startswith("Project not found")


def test_parse_journal_broken_timestamp_drops_following_messages():
    """Битый `!ENTRY` не должен приписывать сообщению чужое время — запись теряется."""
    text = (
        "!ENTRY com.ditrix.edt.mcp.server 1 0 НЕ-ДАТА\n"
        "!MESSAGE Completed tools/call: update_database in 99999ms, outcome=ok\n"
    )
    completed, failures = ej.parse_journal(text)
    assert completed == [] and failures == []


def test_parse_journal_survives_absurd_duration():
    """Порча лога (длительность за пределами timedelta) не должна ронять прогон."""
    text = (
        "!ENTRY com.ditrix.edt.mcp.server 1 0 2026-07-23 13:00:38.100\n"
        "!MESSAGE Completed tools/call: update_database in 99999999999999999999ms, outcome=ok\n"
        "!ENTRY com.ditrix.edt.mcp.server 1 0 2026-07-23 13:05:00.000\n"
        "!MESSAGE Completed tools/call: list_projects in 12ms, outcome=ok\n"
    )
    completed, _ = ej.parse_journal(text)
    assert [r["tool"] for r in completed] == ["list_projects"]  # битая пропущена, годная взята


def test_parse_journal_ignores_unrelated_lines():
    text = (
        "!ENTRY com._1c.g5.v8.dt.common 8 0 2026-07-24 18:09:45.490\n"
        "!MESSAGE Преобразование XML во внешний объект\n"
        "!SESSION 2026-07-24\n"
    )
    assert ej.parse_journal(text) == ([], [])


def test_read_journals_filters_by_since_and_skips_unreadable(tmp_path):
    ws = tmp_path / "ws" / ".metadata"
    ws.mkdir(parents=True)
    log = ws / ".log"
    log.write_text(JOURNAL, encoding="utf-8")
    missing = tmp_path / "нет" / ".metadata" / ".log"  # несуществующий файл — пропуск

    completed, failures = ej.read_journals(since=datetime(2026, 7, 24), journals=[log, missing])
    assert [r["tool"] for r in completed] == ["delete_project"]  # 07-23 отфильтрованы
    assert len(failures) == 1
    assert completed[0]["source"] == "ws"  # `<ws>/.metadata/.log` → имя воркспейса


def test_find_journals_covers_main_log_and_rotations(tmp_path):
    meta = tmp_path / "ws" / ".metadata"
    meta.mkdir(parents=True)
    (meta / ".log").write_text("", encoding="utf-8")
    (meta / ".bak_0.log").write_text("", encoding="utf-8")
    (meta / "other.txt").write_text("", encoding="utf-8")
    names = {p.name for p in ej.find_journals(tmp_path)}
    assert names == {".log", ".bak_0.log"}


def test_find_journals_on_missing_root_is_empty(tmp_path):
    assert ej.find_journals(tmp_path / "нет-такого") == []


def test_server_ok_calls_filters_outcome_and_duration(tmp_path):
    log = tmp_path / "ws" / ".metadata" / ".log"
    log.parent.mkdir(parents=True)
    log.write_text(JOURNAL, encoding="utf-8")
    # min_ms отсекает короткий успех (list_projects 12ms), outcome=error не берётся вовсе
    assert set(ej.server_ok_calls(min_ms=55_000, journals=[log])) == {"update_database"}
    assert set(ej.server_ok_calls(min_ms=0, journals=[log])) == {
        "update_database",
        "list_projects",
    }


# ── 2. вычет в completion_stats ───────────────────────────────────────────────


def test_unpaired_pre_with_server_ok_is_client_timeout():
    """САБОТАЖ-ИНВАРИАНТ: серверный успех рядом по времени → client_timeout, НЕ failed."""
    pres = [_pre("mcp__edt-mcp__update_database", "a", T0)]
    got = te.completion_stats(
        pres, [], now=NOW, server_ok=[(T0 + timedelta(milliseconds=120), 119398)]
    )
    assert got["client_timeout"] == 1
    assert got["failed"] == 0


def test_without_server_ok_behaviour_is_unchanged():
    """Поведение бит-в-бит прежнее, когда доказательства нет (аддитивность фикса)."""
    pres = [_pre("mcp__edt-mcp__update_database", "a", T0)]
    got = te.completion_stats(pres, [], now=NOW)
    assert got["failed"] == 1
    assert got["client_timeout"] == 0


def test_server_ok_outside_tolerance_stays_failure():
    """Запись дальше допуска — чужой вызов: провал остаётся провалом (fail-closed)."""
    pres = [_pre("mcp__edt-mcp__update_database", "a", T0)]
    late = T0 + timedelta(seconds=te.SERVER_OK_MATCH_SEC + 1)
    got = te.completion_stats(pres, [], now=NOW, server_ok=[(late, 119398)])
    assert got["failed"] == 1
    assert got["client_timeout"] == 0


def test_server_ok_consumed_one_to_one():
    """Одна запись объясняет РОВНО один вызов — иначе один успех «оправдал» бы серию."""
    pres = [
        _pre("mcp__edt-mcp__delete_project", "a", T0),
        _pre("mcp__edt-mcp__delete_project", "b", T0 + timedelta(minutes=5)),
    ]
    got = te.completion_stats(pres, [], now=NOW, server_ok=[(T0, 134035)])
    assert got["client_timeout"] == 1
    assert got["failed"] == 1


def test_paired_pre_takes_its_own_server_record_first():
    """Успешно вернувшийся вызов забирает свою запись — соседний непарный её не крадёт."""
    paired_ts = T0
    unpaired_ts = T0 + timedelta(milliseconds=500)  # в пределах допуска от записи
    pres = [
        _pre("mcp__edt-mcp__delete_project", "paired", paired_ts),
        _pre("mcp__edt-mcp__delete_project", "lost", unpaired_ts),
    ]
    posts = [_post("mcp__edt-mcp__delete_project", "paired", paired_ts + timedelta(minutes=2))]
    got = te.completion_stats(pres, posts, now=NOW, server_ok=[(paired_ts, 134035)])
    assert got["completed"] == 1
    assert got["client_timeout"] == 0  # запись израсходована парным вызовом
    assert got["failed"] == 1


def test_blocked_call_does_not_consume_server_record():
    """Блок и серверный успех — разные объяснения; блок не должен съедать запись журнала."""
    pres = [
        _pre("mcp__edt-mcp__update_database", "blocked", T0),
        _pre("mcp__edt-mcp__update_database", "capped", T0 + timedelta(minutes=10)),
    ]
    got = te.completion_stats(
        pres,
        [],
        now=NOW,
        blocked=[("s1", T0)],
        server_ok=[(T0 + timedelta(minutes=10), 119398)],
    )
    assert got["blocked"] == 1
    assert got["client_timeout"] == 1
    assert got["failed"] == 0


def test_server_ok_ids_collected_for_second_cut():
    ids: set[str] = set()
    pres = [_pre("mcp__edt-mcp__update_database", "a", T0)]
    te.completion_stats(pres, [], now=NOW, server_ok=[(T0, 119398)], server_ok_ids=ids)
    assert ids == {"a"}


def test_in_flight_pre_not_counted_as_client_timeout():
    """Свежий непарный Pre — ещё in_flight: вычет к нему не применяется."""
    fresh = NOW - timedelta(seconds=5)
    got = te.completion_stats(
        [_pre("mcp__edt-mcp__update_database", "a", fresh)],
        [],
        now=NOW,
        server_ok=[(fresh, 119398)],
    )
    assert got["in_flight"] == 1
    assert got["client_timeout"] == 0


# ── 3. агрегация и вердикт ────────────────────────────────────────────────────

_DP = "mcp__edt-mcp__delete_project"


def _delete_project_rows():
    """Живой сценарий: 3 непарных Pre, из них 2 — успешные удаления (клиент не дождался)."""
    return [
        _pre(_DP, "a", T0),
        _pre(_DP, "b", T0 + timedelta(minutes=30)),
        _pre(_DP, "c", T0 + timedelta(minutes=60)),
    ]


def test_client_timeout_excluded_from_calls_and_errors():
    server_ok = {_DP: [(T0, 134035), (T0 + timedelta(minutes=30), 203137)]}
    stats = ath.aggregate_tools(_delete_project_rows(), now=NOW, server_ok=server_ok)[_DP]
    assert stats["client_timeout"] == 2
    assert stats["calls"] == 1  # оборванные по потолку не входят в попытки
    assert stats["errors"] == 1
    assert stats["incomplete"] == 1


def test_verdict_drops_broken_after_deduction():
    """Живой эффект: «0 успешных из 3 попыток» перестаёт быть broken (осталась 1 попытка)."""
    rows = _delete_project_rows()
    before = ath.aggregate_tools(rows, now=NOW)[_DP]
    assert ath.assign_verdict(before, None, tool=_DP)[0] == "broken"

    server_ok = {_DP: [(T0, 134035), (T0 + timedelta(minutes=30), 203137)]}
    after = ath.aggregate_tools(rows, now=NOW, server_ok=server_ok)[_DP]
    assert ath.assign_verdict(after, None, tool=_DP)[0] != "broken"


def test_agent_rollup_matches_per_tool_deduction():
    """Суммы вычета в двух разрезах обязаны совпадать (иначе таблицы противоречат)."""
    rows = _delete_project_rows()
    for r in rows:
        r["agent_id"] = "agent-1" if r["tool_call_id"] == "a" else "(main)"
    server_ok = {_DP: [(T0, 134035), (T0 + timedelta(minutes=30), 203137)]}
    per_tool = ath.aggregate_tools(rows, now=NOW, server_ok=server_ok)
    per_agent = ath.agent_rollup(rows, now=NOW, server_ok=server_ok)
    assert sum(s["client_timeout"] for s in per_tool.values()) == 2
    assert sum(v["client_timeout"] for v in per_agent.values()) == 2


# ── 4. источник записей и graceful degradation ────────────────────────────────


def test_server_ok_by_tool_maps_bare_names_and_applies_cap(tmp_path, monkeypatch):
    """Порог отсекает успехи КОРОЧЕ клиентского потолка, включая 20с — он в «пустой полосе»
    между максимумом парного вызова (13.4с) и минимумом оборванного (60.3с), поэтому его
    вычет недоказуем. Снижение CLIENT_CAP_MS обязано покраснить этот тест."""
    log = tmp_path / "ws" / ".metadata" / ".log"
    log.parent.mkdir(parents=True)
    log.write_text(
        JOURNAL
        + "\n!ENTRY com.ditrix.edt.mcp.server 1 0 2026-07-23 14:00:00.000\n"
        + "!MESSAGE Completed tools/call: build_external_objects in 20000ms, outcome=ok\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ej, "find_journals", lambda root=None: [log])

    got = ath.server_ok_by_tool(datetime(2026, 7, 25), window_days=14)
    assert set(got) == {"mcp__edt-mcp__update_database"}  # 12мс и 20 000мс отсечены порогом
    assert got["mcp__edt-mcp__update_database"][0][1] == 119398


def test_client_cap_env_cannot_disable_threshold(monkeypatch):
    """`TOOL_HEALTH_CLIENT_CAP_MS=0` не должен превращать вычет в глобальное подавление."""
    monkeypatch.setenv("TOOL_HEALTH_CLIENT_CAP_MS", "0")
    spec = importlib.util.spec_from_file_location("_ath_cap_env", _ATH_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.CLIENT_CAP_MS >= 1_000

    monkeypatch.setenv("TOOL_HEALTH_CLIENT_CAP_MS", "не-число")  # мусор не роняет импорт
    mod2 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod2)
    assert mod2.CLIENT_CAP_MS == 55_000


def test_server_ok_by_tool_without_journals_is_empty(monkeypatch):
    """Нет журналов → {} и прежнее поведение метрики (вычета просто нет)."""
    monkeypatch.setattr(ej, "find_journals", lambda root=None: [])
    assert ath.server_ok_by_tool(NOW, window_days=14) == {}


def test_parse_journal_ignores_foreign_bundle():
    """Записи чужого плагина не берём: в общий журнал пишут все, имена тулов пересекаются."""
    text = (
        "!ENTRY com.codepilot1c.core 1 0 2026-07-23 13:00:38.100\n"
        "!MESSAGE Completed tools/call: create_metadata in 119398ms, outcome=ok\n"
        "!ENTRY com.ditrix.edt.mcp.server 1 0 2026-07-23 13:05:00.000\n"
        "!MESSAGE Completed tools/call: create_metadata in 119398ms, outcome=ok\n"
    )
    completed, _ = ej.parse_journal(text)
    assert len(completed) == 1
    assert completed[0]["end"] == datetime(2026, 7, 23, 13, 5, 0)


def test_read_journals_deduplicates_paths(tmp_path):
    """Один журнал, поданный дважды, не должен удваивать записи (и вычет)."""
    log = tmp_path / "ws" / ".metadata" / ".log"
    log.parent.mkdir(parents=True)
    log.write_text(JOURNAL, encoding="utf-8")
    completed, _ = ej.read_journals(journals=[log, log])
    assert len(completed) == 3


def test_aware_pre_ts_matches_naive_journal_record():
    """Aware-ts у Pre против naive-времени журнала: рецидивирующий класс бага (tz-крэш)."""
    local_naive = T0
    aware = local_naive.astimezone(UTC)  # тот же момент, но с tzinfo
    pres = [
        {
            "event": "PreToolUse",
            "tool": "mcp__edt-mcp__update_database",
            "tool_call_id": "a",
            "ts": aware.isoformat(),
            "session": "s1",
        }
    ]
    got = te.completion_stats(pres, [], now=NOW, server_ok=[(local_naive, 119398)])
    assert got["client_timeout"] == 1


def test_empty_tool_call_id_never_enters_explained_sets():
    """Пустой id в множество объяснённых НЕ кладём: он не идентифицирует вызов, и во втором
    разрезе одно объяснение списало бы ВСЕ безыдентификаторные Pre группы."""
    no_id = {"event": "PreToolUse", "tool": _DP, "ts": T0.isoformat(), "session": "s"}
    ct_ids: set[str] = set()
    blk_ids: set[str] = set()
    got = te.completion_stats([no_id], [], now=NOW, server_ok=[(T0, 134035)], server_ok_ids=ct_ids)
    assert got["client_timeout"] == 1  # сам вычет per-tool работает
    assert ct_ids == set()  # но во второй разрез пустой id не уходит

    got_b = te.completion_stats(
        [dict(no_id)], [], now=NOW, blocked=[("s", T0)], blocked_ids=blk_ids
    )
    assert got_b["blocked"] == 1
    assert blk_ids == set()


def test_empty_tool_call_id_not_charged_to_every_call():
    """Пустой id не идентифицирует вызов: одно объяснение не должно списать все такие Pre."""
    rows = [
        {"event": "PreToolUse", "tool": _DP, "ts": T0.isoformat(), "session": "s"},
        {
            "event": "PreToolUse",
            "tool": _DP,
            "ts": (T0 + timedelta(minutes=30)).isoformat(),
            "session": "s",
        },
    ]
    for i, r in enumerate(rows):
        r["agent_id"] = f"agent-{i}"
    server_ok = {_DP: [(T0, 134035)]}  # объясняет РОВНО один вызов
    per_agent = ath.agent_rollup(rows, now=NOW, server_ok=server_ok)
    assert sum(v["client_timeout"] for v in per_agent.values()) <= 1


# ── 5. проводка в run(): без неё вычет тихо умирает в проде ───────────────────


def test_run_wires_deduction_into_sidecar_and_report(tmp_path, monkeypatch):
    """САБОТАЖ-ИНВАРИАНТ проводки: удаление `server_ok=` в run() обязано покраснить тест."""
    monkeypatch.setattr(ath, "REPORTS", tmp_path)
    monkeypatch.setattr(ath, "iter_window_rows", lambda *a, **k: _delete_project_rows())
    monkeypatch.setattr(
        ath,
        "server_ok_by_tool",
        lambda *a, **k: {_DP: [(T0, 134035), (T0 + timedelta(minutes=30), 203137)]},
    )
    monkeypatch.setattr(ath, "guard_blocks_by_tool", lambda *a, **k: {})
    monkeypatch.setattr(ath, "gather_infra_alerts", lambda *a, **k: [])  # без внешних вызовов
    monkeypatch.setattr(ath, "earliest_log_ts", lambda *a, **k: None)
    monkeypatch.setattr(
        ath,
        "journal_failures_for",
        lambda tools, now, window_days, limit=12: [
            {
                "tool": _DP,
                "ts": "2026-07-24T18:16:12",
                "ms": 0,
                "text": "Project not found",
                "source": "ws",
            }
        ],
    )
    monkeypatch.setitem(
        sys.modules,
        "otel_crosscheck",
        types.SimpleNamespace(
            run_crosscheck=lambda **k: {"available": False}, format_section=lambda cc: ""
        ),
    )

    sidecar = ath.run(window_days=14, now=NOW)

    assert sidecar["client_timeouts"][_DP] == 2  # вычет доехал до sidecar
    assert sidecar["tools"][_DP]["verdict"] != "broken"  # и до вердикта
    assert sidecar["journal_failures"], "причины отказов сервера не попали в sidecar"
    md = (tmp_path / "_latest.md").read_text(encoding="utf-8")
    assert "Серверные исходы (журнал EDT)" in md
    assert "Клиентский потолок" in md
    written = json.loads((tmp_path / "_latest.json").read_text(encoding="utf-8"))
    assert written["client_timeouts"][_DP] == 2


def test_journal_failures_only_for_alerting_edt_tools(tmp_path, monkeypatch):
    log = tmp_path / "ws" / ".metadata" / ".log"
    log.parent.mkdir(parents=True)
    log.write_text(JOURNAL, encoding="utf-8")
    monkeypatch.setattr(ej, "find_journals", lambda root=None: [log])

    healthy = {_DP: {"verdict": "healthy"}}
    assert ath.journal_failures_for(healthy, datetime(2026, 7, 25), 14) == []

    broken = {_DP: {"verdict": "broken"}}
    got = ath.journal_failures_for(broken, datetime(2026, 7, 25), 14)
    assert len(got) == 1
    assert got[0]["tool"] == _DP
    # длительность подтянута из парной записи Completed: 0мс = отказ до работы
    assert got[0]["ms"] == 0
    assert "Project not found" in got[0]["text"]
