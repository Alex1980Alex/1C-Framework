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
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

# .claude/hooks/shared/llm_health.py → parents[3] = корень репо.
# LLM_HEALTH_DATA_DIR — env-override каталога логов (2026-07-26). Без него у тестов,
# гоняющих гард ПОДПРОЦЕССОМ, оставалась живая зависимость от машины: любые свежие
# провальные записи в продовом `data/llm-rotation-*.jsonl` (в т.ч. от ручного прогона
# сервиса вне pytest) делали is_provider_down() истинным, гард graceful-пропускал
# запись, и все assert'ы «должно блокировать» краснели. Это было задокументировано
# в test_z_ai_write_guard_scope.py как «known residual, accepted» — и сработало.
_DATA = Path(__file__).resolve().parents[3] / "data"


def _data_dir() -> Path:
    """Каталог логов, читается В МОМЕНТ ВЫЗОВА.

    Не на импорте (ревью 2026-07-26): при связывании на импорте `monkeypatch.setenv`
    в уже загруженном модуле был бы МОЛЧАЛИВЫМ no-op — тот же класс фиктивной изоляции,
    что и мёртвая CLAUDE_SESSION_STATE_PATH в истории test_z_ai_write_guard_scope.py.
    `_DATA` остаётся дефолтом и точкой для существующих monkeypatch.setattr.
    ⚠ Кто может задать эту переменную процессу хука — тот и так владеет гардом;
    это инструмент изоляции тестов, а не граница безопасности.
    """
    return Path(os.environ.get("LLM_HEALTH_DATA_DIR") or _DATA)


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
    data_dir = _data_dir()
    for fname in (_METRICS, _COMPLETIONS):
        for r in _tail(data_dir / fname, sample):
            dt = _to_utc(r.get("ts"))
            if dt is not None and dt < cutoff:
                continue  # вне окна
            total += 1
            if _is_failure(r):
                fails += 1
    return total >= 2 and fails * 2 >= total
