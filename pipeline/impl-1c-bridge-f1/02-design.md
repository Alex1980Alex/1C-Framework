# F-1 — Дизайн реализации (на approve)

## Изменяемые/новые файлы (3 шт.)

### 1. NEW `.claude/hooks/shared/pipeline_1c_bridge.py` (helper, stdlib + pipeline_state)
```python
"""Мост 1С-слэш-команд → generic pipeline-state (ADR-019 B′ F-1, ядро G3).
Зовётся из analyze/implement-1c-task-preflight. Best-effort: НИКОГДА не ломает preflight."""
import re
_JIRA = re.compile(r"[A-Z]{2,}-\d+")

def derive_slug(prompt: str) -> str:
    # 1) JIRA-код (GKSTCPLK-2182) — стабильный идентификатор задачи
    m = _JIRA.search(prompt or "")
    if m:
        return m.group(0)
    # 2) fallback: первые слова → ASCII-slug; пусто → "1c-task"
    import unicodedata
    base = (prompt or "").strip().split("\n")[0][:40]
    ascii_ = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_).strip("-")
    return slug or "1c-task"

def ensure_pipeline_1c(prompt: str, command: str) -> str | None:
    """Идемпотентно init pipeline для 1С-задачи. Возврат slug | None (best-effort)."""
    try:
        import sys, os
        hooks = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if hooks not in sys.path:
            sys.path.insert(0, hooks)
        from shared import pipeline_state  # уже importable из preflight
        slug = derive_slug(prompt)
        pipeline_state.init_task(slug, title=f"1С-задача ({command}): {slug}")  # идемпотентно
        return slug
    except Exception:
        return None  # никогда не ломаем preflight
```
- `derive_slug`: JIRA-код приоритетно (стабилен между analyze и implement → ОДИН пайплайн на задачу); fallback ASCII-slug.
- `ensure_pipeline_1c`: best-effort, `try/except` глушит всё (инвариант «не ломать preflight»).

### 2. EDIT `.claude/hooks/analyze-1c-task-preflight.py`
В `execute()` ПОСЛЕ `if detect_slash_command(...) != TARGET_COMMAND: return None` и ДО/ПОСЛЕ probe — добавить:
```python
from shared.pipeline_1c_bridge import ensure_pipeline_1c
ensure_pipeline_1c(prompt, TARGET_COMMAND)   # ADR-019 F-1: автозавод pipeline-state (G3)
```
Ничего больше не меняем: debug-probe + systemMessage + лог — как есть.

### 3. EDIT `.claude/hooks/implement-1c-task-preflight.py`
Аналогично — после детекта команды добавить `ensure_pipeline_1c(prompt, TARGET_COMMAND)` (init-or-touch: если
analyze уже создал пайплайн с тем же JIRA-slug → init вернёт его и обновит `updated_at` → implement-сессия удовлетворяет Stop-инвариант).

### 4. NEW `tests/unit/test_pipeline_1c_bridge.py` (marker `unit`)
- `test_derive_slug_jira`: «…GKSTCPLK-2182…» → `GKSTCPLK-2182`.
- `test_derive_slug_fallback`: кириллица/без-JIRA → непустой ASCII-slug, без спецсимволов.
- `test_ensure_idempotent`: дважды `ensure_pipeline_1c` с тем же prompt → один пайплайн, не падает (monkeypatch PIPELINE_DIR в tmp_path).
- `test_best_effort_never_raises`: при сломанном pipeline_state (monkeypatch init_task→raise) → `ensure_pipeline_1c` возвращает None, НЕ кидает.

## Контракт / гарантии
- **Behavior-preserving:** helper зовётся только из 2 1С-preflight; generic `pl-*`/`pipeline_state` default — без изменений (регресс-тест существующего `test_pipeline_state_*` остаётся зелёным).
- **Не ломать preflight:** best-effort try/except.
- **Один пайплайн на задачу:** JIRA-slug стабилен → analyze и implement пишут в один `pipeline/<JIRA>/`.
- **Откат:** revert 2 строк в preflight + удалить helper + тест. Single rollback.

## DoD
1. `pytest tests/unit/test_pipeline_1c_bridge.py -m unit` — зелёный (4/4).
2. Синтетический прогон analyze-preflight с prompt «/analyze-1c-task GKSTCPLK-9999 …» → создан `pipeline/GKSTCPLK-9999/.pipeline-state.json`.
3. `pipeline-protocol-stop` синтетика на сессии с правкой + этим state → exit 0 (G3 закрыт).
4. Existing `test_pipeline_protocol_git_signal` / pipeline_state-тесты — без регрессий (compileall + targeted pytest).

## Открытые мелочи (решаются в Кодировании, не блокируют approve)
- Точное место вставки в implement-preflight (после smoke-probe vs до) — не влияет на семантику (UPS, оба до команды).
- title формат — косметика.

---
**Гейт:** перед Кодированием жду **approve** этого дизайна (B′/ADR-017 hard-гейт «Дизайн→Кодирование»).
