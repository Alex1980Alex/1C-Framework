"""J-P0.2/0.3 (roadmap 260725): адаптеры источников judge-items + курсор + fail-loud.

Что пинится:
  - контракт judge-item из обоих источников (собственный per-call лог и native OTel);
  - `stringValue`-коэрсинг OTel (провал не должен читаться как успех);
  - metadata-only записи пропускаются, но пустой батч НЕ молчит (`content_disabled`);
  - курсор не даёт пересудить те же вызовы и не двигается при падении прогона.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import tool_llm_judge as lj


@pytest.fixture(autouse=True)
def _isolate_out(tmp_path, monkeypatch):
    """Журнал вердиктов — в tmp, чтобы тесты не пачкали живой отчёт."""
    monkeypatch.setenv("TOOL_JUDGE_OUT", str(tmp_path / "llm-judge.jsonl"))
    monkeypatch.setenv("TOOL_JUDGE_CURSOR", str(tmp_path / "cursor.json"))


def _write_mcp_log(root: Path, name: str, records: list[dict]) -> Path:
    d = root / ".claude" / "cache"
    d.mkdir(parents=True, exist_ok=True)
    p = d / name
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records), encoding="utf-8")
    return p


def _otel_line(attrs: dict, ts_nano: str = "1700000000000000000") -> str:
    return json.dumps(
        {
            "resourceLogs": [
                {
                    "resource": {"attributes": []},
                    "scopeLogs": [
                        {
                            "logRecords": [
                                {
                                    "timeUnixNano": ts_nano,
                                    "attributes": [
                                        {"key": k, "value": {"stringValue": str(v)}}
                                        for k, v in attrs.items()
                                    ],
                                }
                            ]
                        }
                    ],
                }
            ]
        }
    )


def _write_otel(root: Path, lines: list[str]) -> Path:
    d = root / "data" / "otel"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "claude-otel-logs.jsonl"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


# ── источник mcp-calls ────────────────────────────────────────────────────────


def test_mcp_calls_maps_contract(tmp_path):
    _write_mcp_log(
        tmp_path,
        "mcp-vector-memory-calls.jsonl",
        [
            {
                "ts": "2026-07-25T10:00:00.000",
                "server": "vector-memory",
                "tool": "search_patterns",
                "ok": True,
                "ms": 331.2,
                "args_digest": '{"query": "гейт"}',
                "result_digest": '{"hits": 3}',
            }
        ],
    )
    items, cursor = lj.judge_items_from_mcp_calls(tmp_path)
    assert len(items) == 1
    it = items[0]
    assert it["tool"] == "search_patterns"
    assert it["args"] == '{"query": "гейт"}' and it["result"] == '{"hits": 3}'
    assert it["success"] is True and it["duration_ms"] == 331.2
    assert cursor["mcp-vector-memory-calls.jsonl"] == "2026-07-25T10:00:00.000"


def test_mcp_calls_skips_metadata_only(tmp_path):
    """Записи без контента (флаг был выключен) судить нечем — пропуск, не падение."""
    _write_mcp_log(
        tmp_path,
        "mcp-x-calls.jsonl",
        [{"ts": "2026-07-25T10:00:00.000", "server": "x", "tool": "t", "ok": True, "ms": 1.0}],
    )
    items, cursor = lj.judge_items_from_mcp_calls(tmp_path)
    assert items == []
    # курсор всё равно двинулся: перечитывать эти строки незачем
    assert cursor["mcp-x-calls.jsonl"] == "2026-07-25T10:00:00.000"


def test_mcp_calls_cursor_skips_seen(tmp_path):
    _write_mcp_log(
        tmp_path,
        "mcp-x-calls.jsonl",
        [
            {
                "ts": "2026-07-25T10:00:00.000",
                "server": "x",
                "tool": "a",
                "ok": True,
                "ms": 1.0,
                "args_digest": "1",
            },
            {
                "ts": "2026-07-25T11:00:00.000",
                "server": "x",
                "tool": "b",
                "ok": True,
                "ms": 1.0,
                "args_digest": "2",
            },
        ],
    )
    cursor = {"mcp-x-calls.jsonl": "2026-07-25T10:00:00.000"}
    items, new_cursor = lj.judge_items_from_mcp_calls(tmp_path, cursor)
    assert [i["tool"] for i in items] == ["b"]
    assert new_cursor["mcp-x-calls.jsonl"] == "2026-07-25T11:00:00.000"


def test_mcp_calls_failed_call_kept(tmp_path):
    """Провалы — самое ценное для судьи, они обязаны попадать в выборку."""
    _write_mcp_log(
        tmp_path,
        "mcp-x-calls.jsonl",
        [
            {
                "ts": "2026-07-25T10:00:00.000",
                "server": "x",
                "tool": "execute_query",
                "ok": False,
                "ms": 5.0,
                "error_type": "HTTPStatusError",
                "args_digest": "ВЫБРАТЬ ...",
            }
        ],
    )
    items, _ = lj.judge_items_from_mcp_calls(tmp_path)
    assert items[0]["success"] is False


# ── источник otel ─────────────────────────────────────────────────────────────


def test_otel_maps_contract(tmp_path):
    _write_otel(
        tmp_path,
        [
            _otel_line(
                {
                    "event.name": "claude_code.tool_result",
                    "tool_name": "Bash",
                    "tool_use_id": "toolu_1",
                    "tool_input": "ls -la",
                    "tool_result": "total 8",
                    "success": "true",
                    "duration_ms": "3879",
                }
            )
        ],
    )
    items, cursor = lj.judge_items_from_otel(tmp_path)
    assert len(items) == 1
    assert items[0]["tool"] == "Bash" and items[0]["tool_use_id"] == "toolu_1"
    assert items[0]["duration_ms"] == 3879
    assert cursor["claude-otel-logs.jsonl"] == "1700000000000000000"


def test_otel_string_false_is_failure(tmp_path):
    """⚠ Платформа кодирует success как stringValue: наивный bool("false") == True
    прочитал бы ВСЕ провалы как успехи (класс бага, пойманный в H-P3)."""
    _write_otel(
        tmp_path,
        [
            _otel_line(
                {
                    "event.name": "claude_code.tool_result",
                    "tool_name": "Edit",
                    "tool_use_id": "toolu_2",
                    "tool_input": "{}",
                    "success": "false",
                }
            )
        ],
    )
    items, _ = lj.judge_items_from_otel(tmp_path)
    assert items[0]["success"] is False


def test_otel_without_content_skipped(tmp_path):
    """OTEL_LOG_TOOL_CONTENT выключен → args/result пусты → судить нечего."""
    _write_otel(
        tmp_path,
        [
            _otel_line(
                {
                    "event.name": "claude_code.tool_result",
                    "tool_name": "Read",
                    "tool_use_id": "toolu_3",
                    "success": "true",
                }
            )
        ],
    )
    items, _ = lj.judge_items_from_otel(tmp_path)
    assert items == []


# ── fail-loud + курсор в run() ────────────────────────────────────────────────


def _read_out(tmp_path: Path) -> list[dict]:
    p = tmp_path / "llm-judge.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def test_run_empty_source_is_loud_not_silent(tmp_path):
    """Пустой источник пишет маркер: «судья не работал» ≠ «нарушений нет»."""
    res = lj.run(source="mcp-calls", root=tmp_path)
    assert res["available"] is False
    recs = _read_out(tmp_path)
    assert recs and recs[0]["status"] == "content_disabled"
    assert "MCP_CALL_LOG_CONTENT" in recs[0]["reason"]


def test_run_scores_and_advances_cursor(tmp_path):
    _write_mcp_log(
        tmp_path,
        "mcp-x-calls.jsonl",
        [
            {
                "ts": "2026-07-25T10:00:00.000",
                "server": "x",
                "tool": "t",
                "ok": False,
                "ms": 1.0,
                "args_digest": "a",
                "result_digest": "r",
            }
        ],
    )
    fake = lambda _p: '{"argument_correctness": 0.9, "task_completion": 0.2, "comment": "пусто"}'  # noqa: E731
    res = lj.run(judge_fn=fake, source="mcp-calls", root=tmp_path)
    assert res["available"] is True and res["scored"] == 1
    assert lj._load_cursor()["mcp-x-calls.jsonl"] == "2026-07-25T10:00:00.000"

    # повторный прогон: тот же вызов не пересуживается
    res2 = lj.run(judge_fn=fake, source="mcp-calls", root=tmp_path)
    assert res2["available"] is False


def test_cursor_not_advanced_when_run_fails(tmp_path, monkeypatch):
    """Упавшая запись вердиктов не должна «съедать» вызовы (иначе тихая потеря)."""
    _write_mcp_log(
        tmp_path,
        "mcp-x-calls.jsonl",
        [
            {
                "ts": "2026-07-25T10:00:00.000",
                "server": "x",
                "tool": "t",
                "ok": True,
                "ms": 1.0,
                "args_digest": "a",
            }
        ],
    )
    monkeypatch.setattr(
        lj, "_append_records", lambda *_a, **_k: (_ for _ in ()).throw(OSError("disk"))
    )
    with pytest.raises(OSError):
        lj.run(judge_fn=lambda _p: "{}", source="mcp-calls", root=tmp_path)
    assert lj._load_cursor() == {}


# ── Р2/Р3 (code-verify): изоляция источников и честный курсор ─────────────────


def test_source_error_does_not_lose_other_source(tmp_path, monkeypatch):
    """Р2: падение одного адаптера не должно уносить собранное вторым."""
    _write_mcp_log(
        tmp_path,
        "mcp-x-calls.jsonl",
        [
            {
                "ts": "2026-07-25T10:00:00.000",
                "server": "x",
                "tool": "t",
                "ok": True,
                "ms": 1.0,
                "args_digest": "a",
            }
        ],
    )
    monkeypatch.setattr(
        lj,
        "judge_items_from_otel",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("otel down")),
    )
    res = lj.run(
        judge_fn=lambda _p: '{"argument_correctness":0.5,"task_completion":0.5}',
        source="auto",
        root=tmp_path,
        rate=1.0,
    )
    assert res["available"] is True and res["scored"] == 1, "упавший источник унёс живой"
    statuses = [r.get("status") for r in _read_out(tmp_path)]
    assert "source_error" in statuses, "падение источника должно быть видно, а не молчать"


def test_cap_does_not_swallow_unjudged_calls(tmp_path):
    """Р3: срез по cap не должен «съедать» историю — курсор идёт по осуждённым."""
    records = [
        {
            "ts": f"2026-07-25T10:00:{i:02d}.000",
            "server": "x",
            "tool": "t",
            "ok": False,  # провалы берутся всегда → сэмпл упирается в cap
            "ms": 1.0,
            "args_digest": f"a{i}",
        }
        for i in range(10)
    ]
    _write_mcp_log(tmp_path, "mcp-x-calls.jsonl", records)
    fake = lambda _p: '{"argument_correctness":0.5,"task_completion":0.5}'  # noqa: E731

    first = lj.run(judge_fn=fake, source="mcp-calls", root=tmp_path, cap=3)
    assert first["scored"] == 3
    # оставшиеся 7 обязаны дождаться следующего прогона, а не пропасть
    second = lj.run(judge_fn=fake, source="mcp-calls", root=tmp_path, cap=3)
    assert second["available"] is True and second["scored"] == 3


def test_service_fields_do_not_leak_into_verdict(tmp_path):
    """Служебные `_src_file`/`_ts` — внутренние, в журнал вердиктов не попадают."""
    _write_mcp_log(
        tmp_path,
        "mcp-x-calls.jsonl",
        [
            {
                "ts": "2026-07-25T10:00:00.000",
                "server": "x",
                "tool": "t",
                "ok": True,
                "ms": 1.0,
                "args_digest": "a",
            }
        ],
    )
    lj.run(
        judge_fn=lambda _p: '{"argument_correctness":0.5,"task_completion":0.5}',
        source="mcp-calls",
        root=tmp_path,
        rate=1.0,
    )
    scored = [r for r in _read_out(tmp_path) if r.get("status") == "scored"]
    assert scored and "_src_file" not in scored[0] and "_ts" not in scored[0]


def test_corrupt_cursor_falls_back_to_full_window(tmp_path):
    (tmp_path / "cursor.json").write_text("{не json", encoding="utf-8")
    assert lj._load_cursor() == {}
