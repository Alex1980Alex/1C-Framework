# F-2 — Дизайн (self-approve, оператор)

### 1. EDIT `shared/pipeline_1c_bridge.py` — +`gate_1c_implement(prompt)`
```python
def gate_1c_implement(prompt: str) -> dict:
    """G4: блок /implement-1c-task если дизайн (этап 2) 1С-пайплайна не approved. best-effort → ok."""
    try:
        hooks = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if hooks not in sys.path:
            sys.path.insert(0, hooks)
        from shared import pipeline_state
        slug = derive_slug(prompt)
        data = pipeline_state.load(slug)
        if not data or not str(data.get("title", "")).startswith("1С-задача"):
            return {"ok": True, "hard": False, "reason": ""}          # нет 1С-пайплайна → no-op
        st2 = next((s for s in data.get("stages", []) if s.get("n") == 2), None)
        if st2 and st2.get("status") == "done" and st2.get("approved"):
            return {"ok": True, "hard": False, "reason": ""}          # одобрен → allow
        return {"ok": False, "hard": True, "reason":
            f"Дизайн (ANALYSIS-REPORT, этап 2) задачи {slug} НЕ одобрен. Отревьюй ANALYSIS-REPORT и одобри: "
            f"`.venv/Scripts/python.exe .claude/hooks/shared/pipeline_state.py approve {slug}`"}
    except Exception:
        return {"ok": True, "hard": False, "reason": ""}              # best-effort: не блокируем
```

### 2. EDIT `.claude/hooks/pipeline-gate.py` — ветка implement-1c-task
После `cmd = detect_slash_command(...)`, ПЕРЕД `if cmd not in PIPELINE_COMMANDS`:
```python
        if cmd == "implement-1c-task":
            from shared.pipeline_1c_bridge import gate_1c_implement
            res = gate_1c_implement(inp.prompt or "")
            if not res["ok"] and res["hard"]:
                return HookOutput().block(f"[PIPELINE-GATE] {res['reason']}")
            return None
```
(opt-out `PIPELINE_GATE_DISABLE` уже проверяется выше — работает и для 1С.)

### 3. EDIT `tests/unit/test_pipeline_1c_bridge.py` — +2 collision-immune
- `test_gate_no_pipeline_or_fail_ok`: `gate_1c_implement("/implement-1c-task GKSTCPLK-404 x")` → `ok=True` (нет пайплайна ИЛИ collision→except — оба дают ok).
- `test_gate_best_effort_ok`: пустой `shared` форс → `ok=True` (не блокирует при сбое).
- Block/allow (реальный пайплайн) — live-DoD.

## DoD
1. `pytest -m unit` зелёный. 2. live: 1С-пайплайн этап2 не-approved → pipeline-gate синтетика на /implement-1c-task = **block (exit 2)**; после approve = **allow (exit 0)**; не-1С CURRENT → allow. 3. ruff/compile. 4. без регрессий.

**Откат:** revert ветки в pipeline-gate + функция + тесты.
