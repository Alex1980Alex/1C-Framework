"""LLM provider health probe — graceful degradation для token-economy гейта.

`ZAIWriteGuard` форсит делегирование больших code-write на Z.AI через llm-rotation.
Если провайдеры недоступны — делегировать нельзя, и хард-блок записи = чистая friction.
`is_provider_down()` читает СОБСТВЕННЫЕ логи llm-rotation (`data/llm-rotation-*.jsonl`):
если свежие (в окне) вызовы преимущественно провальные — провайдер недоступен,
и гард может graceful-пропустить запись.

Best-effort: нет логов / неоднозначно → False (поведение гарда не меняется).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

# .claude/hooks/shared/llm_health.py → parents[3] = корень репо
_DATA = Path(__file__).resolve().parents[3] / "data"
_METRICS = "llm-rotation-metrics.jsonl"  # {ts, success, provider, ...}
_COMPLETIONS = "llm-rotation-completions.jsonl"  # {ts, provider, error?, ...}
_DOWN_MARKERS = ("no available providers", "all failed", "down")


def _tail(path: Path, n: int) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except OSError:
        return []
    out: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def _to_utc(ts) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(ts))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.astimezone()  # naive → считаем локальным временем
    return dt.astimezone(UTC)


def _is_failure(r: dict) -> bool:
    if r.get("success") is False:
        return True
    if str(r.get("provider", "")).lower() in ("error", "none"):
        return True
    err = str(r.get("error") or "").lower()
    return bool(err) and any(m in err for m in _DOWN_MARKERS)


def is_provider_down(window_min: int = 30, sample: int = 8) -> bool:
    """True, если свежие (в окне ``window_min`` мин) вызовы llm-rotation преимущественно провальны.

    Требует ≥2 свежих записей И ≥50% провалов — чтобы единичный сбой не разоружал гард.
    Best-effort: нет данных / неоднозначно → False.
    """
    cutoff = datetime.now(UTC) - timedelta(minutes=window_min)
    total = fails = 0
    for fname in (_METRICS, _COMPLETIONS):
        for r in _tail(_DATA / fname, sample):
            dt = _to_utc(r.get("ts"))
            if dt is not None and dt < cutoff:
                continue  # вне окна
            total += 1
            if _is_failure(r):
                fails += 1
    return total >= 2 and fails * 2 >= total
