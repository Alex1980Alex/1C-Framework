"""Регрессия тяжёлого пути OTel→Langfuse (roadmap 260718 H-P0..H-P4).

H-P0.1 — захват прямого `duration_ms` из PostToolUse-payload (точнее пэйринга):
  - `invocation_logger.extract_duration_ms` — контракт извлечения (Post-only, числа,
    отбраковка bool/negative/missing, camelCase-страховка);
  - `tool_effectiveness.tool_durations` — предпочтение прямого поля паре Pre→Post,
    смешанный режим, и behavior-preserving на данных без поля (саботаж-проверяемо).
H-P3 — cross-check native OTel ↔ hook-JSONL (FP/FN unpaired-Pre, дельта латентности).
H-P4 — LLM-judge sampling contract.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import tool_effectiveness as te

_IL_PATH = _ROOT / ".claude" / "hooks" / "shared" / "invocation_logger.py"
_spec = importlib.util.spec_from_file_location("_invocation_logger_hp0", _IL_PATH)
il = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(il)


# ── H-P0.1: extract_duration_ms контракт ──────────────────────────────────────


def test_extract_duration_post_int():
    """PostToolUse с числовым duration_ms → int."""
    assert il.extract_duration_ms({"duration_ms": 1234}, "PostToolUse") == 1234


def test_extract_duration_post_float_coerced():
    """float → int (усечение)."""
    assert il.extract_duration_ms({"duration_ms": 42.9}, "PostToolUse") == 42


def test_extract_duration_pre_is_none():
    """PreToolUse → None даже если поле каким-то образом присутствует."""
    assert il.extract_duration_ms({"duration_ms": 100}, "PreToolUse") is None


def test_extract_duration_missing_is_none():
    """Нет поля (строка старого формата) → None."""
    assert il.extract_duration_ms({"tool_response": {}}, "PostToolUse") is None


def test_extract_duration_bool_rejected():
    """bool ⊂ int, но не длительность → None (иначе True=1мс шум)."""
    assert il.extract_duration_ms({"duration_ms": True}, "PostToolUse") is None


def test_extract_duration_negative_rejected():
    """Отрицательное значение невалидно → None."""
    assert il.extract_duration_ms({"duration_ms": -5}, "PostToolUse") is None


def test_extract_duration_camelcase_fallback():
    """camelCase-страховка на случай дрейфа payload."""
    assert il.extract_duration_ms({"durationMs": 77}, "PostToolUse") == 77


def test_extract_duration_zero_is_valid():
    """0мс — валидное значение (мгновенный тул), не None."""
    assert il.extract_duration_ms({"duration_ms": 0}, "PostToolUse") == 0


# ── H-P0.1: tool_durations предпочитает прямое поле ───────────────────────────


def _pre(tcid, ts):
    return {"event": "PreToolUse", "tool": "Bash", "tool_call_id": tcid, "ts": ts}


def _post(tcid, ts, duration_ms=None):
    e = {"event": "PostToolUse", "tool": "Bash", "tool_call_id": tcid, "ts": ts}
    if duration_ms is not None:
        e["duration_ms"] = duration_ms
    return e


def test_tool_durations_all_direct():
    """Все посты несут duration_ms → берём напрямую, пэйринг не нужен."""
    posts = [_post("a", "2026-07-18T12:00:01", 500), _post("b", "2026-07-18T12:00:02", 900)]
    assert sorted(te.tool_durations([], posts)) == [500, 900]


def test_tool_durations_prefers_direct_over_pairing():
    """САБОТАЖ-ИНВАРИАНТ: при наличии duration_ms берётся ОНО, а не длительность пары.
    Pre→Post дали бы 5000мс (5 сек), прямое поле = 500мс — должно победить прямое."""
    pres = [_pre("a", "2026-07-18T12:00:00")]
    posts = [_post("a", "2026-07-18T12:00:05", 500)]  # пара = 5000мс, direct = 500мс
    assert te.tool_durations(pres, posts) == [500]


def test_tool_durations_no_field_falls_back_to_pairing():
    """Данные старого формата (без duration_ms) → результат идентичен pair_durations
    (behavior-preserving: исторический лог не меняет поведение)."""
    pres = [_pre("a", "2026-07-18T12:00:00")]
    posts = [_post("a", "2026-07-18T12:00:02")]  # поля нет → пара = 2000мс
    assert te.tool_durations(pres, posts) == te.pair_durations(pres, posts) == [2000]


def test_tool_durations_mixed():
    """Смешанный лог: один Post с полем (взят напрямую), один без (добран пэйрингом)."""
    pres = [_pre("a", "2026-07-18T12:00:00"), _pre("b", "2026-07-18T12:00:00")]
    posts = [
        _post("a", "2026-07-18T12:00:05", 300),  # direct 300
        _post("b", "2026-07-18T12:00:03"),  # paired 3000
    ]
    got = sorted(te.tool_durations(pres, posts))
    assert got == [300, 3000]


def test_tool_durations_empty():
    assert te.tool_durations([], []) == []


# ── H-P3: otel_crosscheck ─────────────────────────────────────────────────────

_CC_PATH = _SCRIPTS / "otel_crosscheck.py"
_cc_spec = importlib.util.spec_from_file_location("_otel_crosscheck_hp3", _CC_PATH)
cc = importlib.util.module_from_spec(_cc_spec)
_cc_spec.loader.exec_module(cc)

CC_NOW = __import__("datetime").datetime(2026, 7, 18, 12, 0, 0)


def _otlp_line(tool, tid, success, duration_ms=None, error_type="", encoding="string"):
    """OTLP-JSON строка с одним claude_code.tool_result (как пишет file-exporter).

    ``encoding="string"`` (default) = РЕАЛЬНАЯ платформенная кодировка (success и
    duration_ms как stringValue "true"/"3879" — эмпирика 2026-07-18); ``"typed"`` =
    boolValue/intValue (страховка совместимости на случай дрейфа платформы)."""
    if encoding == "string":  # РЕАЛЬНАЯ кодировка платформы
        succ_v = {"stringValue": "true" if success else "false"}
        dur_v = {"stringValue": str(duration_ms)} if duration_ms is not None else None
    else:  # typed: страховка на дрейф платформы
        succ_v = {"boolValue": success}
        dur_v = {"intValue": str(duration_ms)} if duration_ms is not None else None
    attrs = [
        {"key": "event.name", "value": {"stringValue": "claude_code.tool_result"}},
        {"key": "tool_name", "value": {"stringValue": tool}},
        {"key": "tool_use_id", "value": {"stringValue": tid}},
        {"key": "success", "value": succ_v},
    ]
    if dur_v is not None:
        attrs.append({"key": "duration_ms", "value": dur_v})
    if error_type:
        attrs.append({"key": "error_type", "value": {"stringValue": error_type}})
    obj = {
        "resourceLogs": [
            {
                "resource": {"attributes": [{"key": "session.id", "value": {"stringValue": "s1"}}]},
                "scopeLogs": [
                    {
                        "scope": {"name": "com.anthropic.claude_code.events"},
                        "logRecords": [
                            {
                                "body": {"stringValue": "claude_code.tool_result"},
                                "attributes": attrs,
                            }
                        ],
                    }
                ],
            }
        ]
    }
    import json as _j

    return _j.dumps(obj)


def test_parse_native_extracts_tool_results(tmp_path):
    """OTLP-структура → нормализованные dict'ы с success/duration/error_type."""
    f = tmp_path / "logs.jsonl"
    f.write_text(
        _otlp_line("Bash", "toolu_a", False, 42, "ShellError")
        + "\n"
        + _otlp_line("Read", "toolu_b", True, 13)
        + "\n",
        encoding="utf-8",
    )
    ev = cc.parse_native_tool_results(f)
    assert len(ev) == 2
    a = next(e for e in ev if e["tool_use_id"] == "toolu_a")
    assert a["success"] is False and a["duration_ms"] == 42 and a["error_type"] == "ShellError"


def test_parse_native_missing_file():
    assert cc.parse_native_tool_results(Path("/nope/does-not-exist.jsonl")) == []


def test_coerce_bool_string_false_is_false():
    """САБОТАЖ-ИНВАРИАНТ: платформа шлёт success как stringValue "false" — наивный
    bool("false")==True сделал бы все провалы «успехом» (NB1-класс на OTel-парсинге)."""
    assert cc._coerce_bool("false") is False
    assert cc._coerce_bool("true") is True
    assert cc._coerce_bool(False) is False  # boolValue-путь тоже жив
    assert cc._coerce_bool("FALSE") is False  # регистронезависимо


def test_coerce_int_stringvalue():
    """duration_ms приходит stringValue "3879" — коэрсим в int (иначе latency слепа)."""
    assert cc._coerce_int("3879") == 3879
    assert cc._coerce_int(42) == 42
    assert cc._coerce_int("nan-ish") is None
    assert cc._coerce_int(True) is None  # bool не длительность


def test_parse_native_real_stringvalue_failure(tmp_path):
    """Реальная кодировка: success=stringValue"false" → провал корректно распознан."""
    f = tmp_path / "logs.jsonl"
    f.write_text(
        _otlp_line("Bash", "toolu_f", False, 3879, "ShellError", encoding="string") + "\n",
        encoding="utf-8",
    )
    ev = cc.parse_native_tool_results(f)
    assert ev[0]["success"] is False and ev[0]["duration_ms"] == 3879


def test_parse_native_typed_encoding_compat(tmp_path):
    """Страховка: boolValue/intValue (если платформа сменит кодировку) тоже парсится."""
    f = tmp_path / "logs.jsonl"
    f.write_text(_otlp_line("Read", "toolu_t", True, 13, encoding="typed") + "\n", encoding="utf-8")
    ev = cc.parse_native_tool_results(f)
    assert ev[0]["success"] is True and ev[0]["duration_ms"] == 13


def _hpre(tid, ts=CC_NOW):
    return {
        "category": "tool_call",
        "event": "PreToolUse",
        "tool": "Bash",
        "tool_call_id": tid,
        "ts": ts.isoformat(),
    }


def _hpost(tid, ts=CC_NOW, outcome="allow", error=None, duration_ms=None):
    r = {
        "category": "tool_call",
        "event": "PostToolUse",
        "tool": "Bash",
        "tool_call_id": tid,
        "ts": ts.isoformat(),
        "outcome": outcome,
        "error": error,
    }
    if duration_ms is not None:
        r["duration_ms"] = duration_ms
    return r


def test_crosscheck_fn_native_fail_hook_success():
    """native провал + hook имеет Post (счёл успехом) → FN (детектор пропустил)."""
    native = [
        {"tool_use_id": "x", "tool": "Bash", "success": False, "duration_ms": 10, "error_type": "E"}
    ]
    res = cc.crosscheck(native, [_hpre("x")], [_hpost("x")], now=CC_NOW)
    assert res["fn_count"] == 1 and res["fp_count"] == 0 and res["tp"] == 0


def test_crosscheck_fp_hook_flag_native_success():
    """hook непарный Pre (пометил провал) + native success=true → FP (ложная тревога)."""
    old = CC_NOW - __import__("datetime").timedelta(hours=1)  # старше grace
    native = [
        {"tool_use_id": "x", "tool": "Bash", "success": True, "duration_ms": 10, "error_type": ""}
    ]
    res = cc.crosscheck(native, [_hpre("x", old)], [], now=CC_NOW)
    assert res["fp_count"] == 1 and res["fn_count"] == 0
    assert res["fp"][0]["hook_signal"] == "unpaired_pre"


def test_crosscheck_tp_both_fail():
    """native провал + hook непарный Pre → TP (согласны)."""
    old = CC_NOW - __import__("datetime").timedelta(hours=1)
    native = [
        {"tool_use_id": "x", "tool": "Bash", "success": False, "duration_ms": 10, "error_type": "E"}
    ]
    res = cc.crosscheck(native, [_hpre("x", old)], [], now=CC_NOW)
    assert res["tp"] == 1 and res["fp_count"] == 0 and res["fn_count"] == 0


def test_crosscheck_in_flight_skipped():
    """Непарный Pre МОЛОЖЕ grace → in-flight, не FP (Post ещё может прийти)."""
    fresh = CC_NOW - __import__("datetime").timedelta(seconds=5)
    native = [
        {"tool_use_id": "x", "tool": "Bash", "success": True, "duration_ms": 10, "error_type": ""}
    ]
    res = cc.crosscheck(native, [_hpre("x", fresh)], [], now=CC_NOW)
    assert res["skipped_in_flight"] == 1 and res["fp_count"] == 0


def test_crosscheck_coverage_native_only():
    """native id вне hook-окна → coverage native_only, не FP/FN."""
    native = [
        {
            "tool_use_id": "orphan",
            "tool": "Bash",
            "success": False,
            "duration_ms": 1,
            "error_type": "E",
        }
    ]
    res = cc.crosscheck(native, [], [], now=CC_NOW)
    assert res["native_only"] == 1 and res["fn_count"] == 0 and res["fp_count"] == 0


def test_crosscheck_latency_vs_direct_and_paired():
    """Латентность: native↔hook-direct (H-P0.1 совпадает) и native↔пэйринг (ошибка пары)."""
    pre_ts = CC_NOW - __import__("datetime").timedelta(seconds=5)  # пара дала бы 5000мс
    native = [
        {"tool_use_id": "x", "tool": "Bash", "success": True, "duration_ms": 500, "error_type": ""}
    ]
    posts = [_hpost("x", CC_NOW, duration_ms=500)]  # direct == native → дельта 0
    res = cc.crosscheck(native, [_hpre("x", pre_ts)], posts, now=CC_NOW)
    lat = res["latency"]
    assert lat["native_vs_direct"]["count"] == 1 and lat["native_vs_direct"]["max"] == 0.0
    assert lat["native_vs_paired"]["count"] == 1 and lat["native_vs_paired"]["max"] == 4500.0


def test_run_crosscheck_graceful_no_file():
    """Нет native-файла → available=False (потребитель прячет секцию)."""
    res = cc.run_crosscheck(
        otel_logs=Path("/nope.jsonl"), hook_log=Path("/nope2.jsonl"), now=CC_NOW
    )
    assert res["available"] is False
    assert cc.format_section(res) == ""


# ── H-P4: tool_llm_judge ──────────────────────────────────────────────────────

_LJ_PATH = _SCRIPTS / "tool_llm_judge.py"
_lj_spec = importlib.util.spec_from_file_location("_tool_llm_judge_hp4", _LJ_PATH)
lj = importlib.util.module_from_spec(_lj_spec)
_lj_spec.loader.exec_module(lj)


def test_stratified_sample_all_failures_kept():
    """Все провалы попадают в сэмпл (rate=0 → успехи отброшены, провалы нет)."""
    items = [{"tool_use_id": f"s{i}", "success": True} for i in range(20)]
    items += [{"tool_use_id": f"f{i}", "success": False} for i in range(3)]
    s = lj.stratified_sample(items, rate=0.0, cap=50)
    assert len(s) == 3 and all(not it["success"] for it in s)


def test_stratified_sample_deterministic():
    """Тот же вход → тот же сэмпл (хеш-детерминизм, без RNG-состояния)."""
    items = [{"tool_use_id": f"s{i}", "success": True} for i in range(100)]
    a = lj.stratified_sample(items, rate=0.2, cap=50)
    b = lj.stratified_sample(items, rate=0.2, cap=50)
    assert [x["tool_use_id"] for x in a] == [x["tool_use_id"] for x in b]
    assert 0 < len(a) < 100  # часть успехов, не все и не пусто


def test_stratified_sample_cap():
    """cap режет общий размер (провалов больше cap → урезано)."""
    items = [{"tool_use_id": f"f{i}", "success": False} for i in range(80)]
    assert len(lj.stratified_sample(items, rate=0.1, cap=50)) == 50


def test_parse_judge_response_clean_json():
    r = lj.parse_judge_response(
        '{"argument_correctness": 0.9, "task_completion": 0.8, "comment": "ok"}'
    )
    assert r["argument_correctness"] == 0.9 and r["task_completion"] == 0.8


def test_parse_judge_response_wrapped_in_prose():
    """Судья обрамил JSON прозой/```json``` — извлекаем первый объект."""
    r = lj.parse_judge_response(
        'Вот оценка:\n```json\n{"argument_correctness": 1.0, "task_completion": 0.0}\n```'
    )
    assert r["argument_correctness"] == 1.0 and r["task_completion"] == 0.0


def test_parse_judge_response_clamped():
    """Значения вне 0..1 клампятся."""
    r = lj.parse_judge_response('{"argument_correctness": 1.7, "task_completion": -0.5}')
    assert r["argument_correctness"] == 1.0 and r["task_completion"] == 0.0


def test_parse_judge_response_garbage_none():
    assert lj.parse_judge_response("совсем не json") is None
    assert lj.parse_judge_response("") is None


def test_judge_items_with_fake_llm():
    """Инъекция синхронного fake-судьи — реальный LLM не зовётся."""
    items = [
        {
            "tool": "Bash",
            "tool_use_id": "x",
            "args": {"command": "ls"},
            "result": "ok",
            "success": True,
        }
    ]

    def fake(_p):
        return '{"argument_correctness": 0.95, "task_completion": 0.9, "comment": "fine"}'

    out = lj.judge_items(items, fake)
    assert out[0]["status"] == "scored" and out[0]["argument_correctness"] == 0.95


def test_judge_items_isolates_llm_error():
    """Судья бросил исключение на item → status=error, прогон не падает."""

    def boom(_p):
        raise RuntimeError("provider down")

    out = lj.judge_items([{"tool": "Bash", "tool_use_id": "x", "success": True}], boom)
    assert out[0]["status"] == "error" and "provider down" in out[0]["error"]


def test_judge_items_skips_unparseable():
    out = lj.judge_items(
        [{"tool": "Bash", "tool_use_id": "x", "success": True}], lambda _p: "мусор"
    )
    assert out[0]["status"] == "skipped"


def test_run_graceful_no_source():
    """Нет источника judge-items → no-op available=False (content off by default)."""
    res = lj.run(source_jsonl=None)
    assert res["available"] is False and "content" in res["reason"]


# ── code-verify fix'ы (2026-07-18): регресс на найденные дефекты ──────────────

_ATH2_PATH = _SCRIPTS / "analyze_tool_health.py"
_ath2_spec = importlib.util.spec_from_file_location("_ath_hp3render", _ATH2_PATH)
ath2 = importlib.util.module_from_spec(_ath2_spec)
_ath2_spec.loader.exec_module(ath2)


def test_render_md_info_severity_no_crash():
    """code-verify #1: infra-alert severity=info (Langfuse down) НЕ роняет render_md
    KeyError'ом (_VERDICT_MARK не знал 'info'). Триггерится когда проба ДОЛЖНА сработать."""
    health = {
        "generated": "2026-07-18T12:00:00",
        "tools": {},
        "infra_alerts": [
            {"level": "info", "source": "langfuse", "reason": "down ≥2д", "affects": ["x"]}
        ],
    }
    md = ath2.render_md(health, window_days=14)  # не должно бросить
    assert "langfuse" in md and "ℹ" in md


def test_render_md_unknown_severity_graceful():
    """Будущий неизвестный severity → маркер '•', не KeyError (defensive .get)."""
    health = {
        "generated": "t",
        "tools": {},
        "infra_alerts": [{"level": "future-sev", "source": "s", "reason": "r", "affects": []}],
    }
    md = ath2.render_md(health, window_days=14)
    assert "**s**" in md


def test_parse_native_missing_success_not_failure(tmp_path):
    """code-verify #2: событие БЕЗ атрибута success → НЕ провал (иначе манфактурим FN).
    Строим tool_result без ключа success."""
    import json as _j

    obj = {
        "resourceLogs": [
            {
                "resource": {"attributes": []},
                "scopeLogs": [
                    {
                        "scope": {"name": "com.anthropic.claude_code.events"},
                        "logRecords": [
                            {
                                "body": {"stringValue": "claude_code.tool_result"},
                                "attributes": [
                                    {
                                        "key": "event.name",
                                        "value": {"stringValue": "claude_code.tool_result"},
                                    },
                                    {"key": "tool_name", "value": {"stringValue": "Bash"}},
                                    {"key": "tool_use_id", "value": {"stringValue": "toolu_ns"}},
                                    # НЕТ success
                                ],
                            }
                        ],
                    }
                ],
            }
        ]
    }
    f = tmp_path / "logs.jsonl"
    f.write_text(_j.dumps(obj) + "\n", encoding="utf-8")
    ev = cc.parse_native_tool_results(f)
    assert ev[0]["success"] is True  # missing → успех, не провал
