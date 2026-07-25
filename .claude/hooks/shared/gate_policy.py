#!/usr/bin/env python3
"""R3 (ADR-034): composable gate-policy layer + decision logging.

Единая fail-closed точка композиции гейтов (approval / scope / completion) вместо
независимых конкурирующих Stop-хуков (натяжение T3). OPA-вдохновлено: policy-as-code,
fail-closed (любой deny -> общий deny), decision-log (аудит). Адоптируется хуками
ИНКРЕМЕНТАЛЬНО (additive, без слома существующих гейтов):
- log_decision(d) -> запись в data/gate-decisions.jsonl (аудит; no behavior change)
- evaluate_gates(context, policies) -> агрегированное fail-closed решение (для миграции)

Чистый stdlib; функции НИКОГДА не кидают (best-effort), чтобы не ронять цепочку хуков.
"""

import json
import os
import time

# Абсолютный якорь от корня проекта (hooks/shared -> ../../..): относительный путь
# резолвился от cwd хук-процесса и мусорил data/gate-decisions.jsonl внутрь сабмодулей
# конфигураций (замечено 2026-07-03: 3 файла в дереве TransportManagementDevelop_SVETLY).
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
_LOG_PATH = os.environ.get(
    "GATE_DECISIONS_LOG", os.path.join(_PROJECT_ROOT, "data", "gate-decisions.jsonl")
)


def decision(gate, allow, reason="", **metadata):
    """Однородное решение одного гейта."""
    return {"gate": gate, "allow": bool(allow), "reason": reason, "metadata": metadata}


def evaluate_gates(context, policies):
    """Fail-closed композиция: каждый policy(context) -> decision; любой deny => общий deny.

    policies: список callable(context) -> decision. Исключение в policy трактуется как
    deny (fail-closed). Возврат: {"allow": bool, "decisions": [...], "denied_by": [gate, ...]}.
    """
    decisions = []
    for p in policies:
        try:
            d = p(context)
        except Exception as e:  # fail-closed: ошибка policy = deny
            d = decision(getattr(p, "__name__", "policy"), False, f"policy error: {e}")
        decisions.append(d)
    denied = [d["gate"] for d in decisions if not d.get("allow", False)]
    return {"allow": not denied, "decisions": decisions, "denied_by": denied}


def log_decision(d, log_path=None):
    """Append decision в jsonl (decision-log / аудит). Best-effort, не кидает."""
    path = log_path or _LOG_PATH
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        rec = dict(d)
        rec.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S"))
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass  # аудит не должен ронять гейт
    return d
