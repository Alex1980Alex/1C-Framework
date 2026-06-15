# F-1.5 — Дизайн реализации (на approve)

## Файлы (1 new hook + 1 helper-функция + settings.json + тест)

### 1. EDIT `shared/pipeline_1c_bridge.py` — +`advance_for_artifact(file_path)`
```python
import re
_ARTIFACT_STAGES = [
    (re.compile(r"ANALYSIS-REPORT", re.I), (1, 2)),        # analyze → Планирование + Дизайн
    (re.compile(r"IMPLEMENTATION-PROGRESS", re.I), (3,)),  # implement → Кодирование
]

def advance_for_artifact(file_path: str) -> tuple[int, ...] | None:
    """Продвинуть этапы CURRENT 1С-пайплайна по записи 1С-артефакта. best-effort → None."""
    try:
        name = (file_path or "").replace("\\", "/").rsplit("/", 1)[-1]
        stages = next((st for rx, st in _ARTIFACT_STAGES if rx.search(name)), None)
        if not stages:
            return None
        hooks = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if hooks not in sys.path:
            sys.path.insert(0, hooks)
        from shared import pipeline_state
        slug = pipeline_state.resolve_current()
        data = pipeline_state.load(slug) if slug else None
        if not data or not str(data.get("title", "")).startswith("1С-задача"):
            return None  # guard: только 1С-пайплайн (метка F-1)
        done_now = []
        for n in stages:
            st = next((s for s in data.get("stages", []) if s.get("n") == n), None)
            if st and st.get("status") != "done":
                pipeline_state.mark_done(slug, n)
                done_now.append(n)
        return tuple(done_now) or None
    except Exception:
        return None
```
(`re` добавить в импорты модуля — уже есть; `os`/`sys` — уже есть.)

### 2. NEW `.claude/hooks/pipeline-1c-advance.py` (PostToolUse, matcher Write|Edit)
```python
#!/usr/bin/env python3
"""Hook: pipeline-1c-advance. Event: PostToolUse. Matcher: Write|Edit.
Двигает этапы 1С-пайплайна по записи ANALYSIS-REPORT(1,2)/IMPLEMENTATION-PROGRESS(3).
best-effort, НЕ блокирует. ADR-019 B′ F-1.5."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from base import BaseHook, HookInput, HookOutput

class Pipeline1CAdvance(BaseHook):
    def execute(self, inp: HookInput):
        if inp.tool_name not in ("Write", "Edit", "MultiEdit"):
            return None
        ti = inp.tool_input or {}
        path = ti.get("file_path") or ti.get("notebook_path") or ""
        from shared.pipeline_1c_bridge import advance_for_artifact
        adv = advance_for_artifact(path)
        if adv:
            return HookOutput().system_message(f"[pipeline-1c-advance] этап(ы) {adv} → done (1С-пайплайн)")
        return None

if __name__ == "__main__":
    Pipeline1CAdvance().run()
```

### 3. EDIT `.claude/settings.json` — регистрация PostToolUse
В `hooks.PostToolUse` добавить запись (matcher `"Write|Edit"`, timeout 5, абсолютный путь к `.venv` python + хуку).
Реверс = удалить эту запись.

### 4. EDIT `tests/unit/test_pipeline_1c_bridge.py` — +advance-тесты (collision-immune)
- `test_advance_matches_analysis`: `advance_for_artifact("…/GKSTCPLK-1-ANALYSIS-REPORT.md")` без CURRENT-1С → None (guard), НО матч-логика проверяется отдельно (через `_ARTIFACT_STAGES` regex напрямую).
- `test_advance_non_artifact_none`: произвольный путь → None.
- `test_advance_regex_mapping`: ANALYSIS-REPORT→(1,2), IMPLEMENTATION-PROGRESS→(3) по `bridge._ARTIFACT_STAGES` (чистый regex, без pipeline_state → collision-immune).
- `test_advance_best_effort`: при пустом `shared` (форс) → None, не кидает.
- Реальное движение этапов — live-DoD (как F-1 DoD-2).

## Контракт / гарантии
- Только 1С-пайплайн (guard по title-метке F-1) → не двигает framework-dev пайплайны.
- best-effort + PostToolUse не блокирует → 0 риска сломать сессию.
- Идемпотентно (mark_done только не-done) → повторная запись артефакта безвредна.
- Откат: settings.json-запись + хук + функция.

## DoD
1. `pytest tests/unit/test_pipeline_1c_bridge.py -m unit` зелёный (включая новые).
2. live: создать 1С-CURRENT-пайплайн (ensure_pipeline_1c) → синтетический PostToolUse с path `…ANALYSIS-REPORT.md` → этапы 1,2 done; не-1С CURRENT → не затронут.
3. settings.json валиден (json.load) + хук compile/ruff green.
4. 35+ pipeline-тестов без регрессий.

---
**Гейт:** жду **approve** перед Кодированием (B′ hard-гейт).
