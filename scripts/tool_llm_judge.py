#!/usr/bin/env python3
"""LLM-judge эффективности tool-call'ов на сэмпле (roadmap 260718 H-P4).

Семантический слой ПОВЕРХ rule-метрик (P2): то, что детерминированные правила не
ловят — правильность аргументов и завершённость задачи (deepeval-рубрики из кеша
tool-call-observability-effectiveness-2026). **Advisory-only** (вердикты rule-слоя
не двигает, лестница как ADR-035) и **на сэмпле** (5-10%, token-economy через
llm_complete/z.ai — [[feedback-delegation-aggressive]]), НЕ на потоке.

**Активация после H-P3** (roadmap-порядок) и требует источник с контентом
(args/result): native OTel с ``OTEL_LOG_TOOL_CONTENT=1`` (PII — осознанно) ЛИБО
явный jsonl judge-items. Без источника → no-op с внятным сообщением.

Контракт judge-item (dict): ``tool``/``tool_use_id``/``args``/``result``/``success``/
``duration_ms``. Выход: ``data/reports/tools/llm-judge.jsonl`` + опц. Langfuse Scores.

stdlib + инъектируемый ``judge_fn`` (default = LLMRotationService.complete async);
тесты подставляют синхронный fake — LLM в юнитах не вызывается.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JUDGE_OUT = ROOT / "data" / "reports" / "tools" / "llm-judge.jsonl"

# Рубрики (deepeval/Confident-AI 2026, кеш tool-call-observability-effectiveness-2026):
# Argument Correctness (правильные ли параметры) + Task Completion (решена ли задача
# по входу+результату). Судья возвращает СТРОГО JSON — парсим устойчиво.
_JUDGE_RUBRIC = """Ты — строгий оценщик вызовов инструментов AI-агента. Оцени ОДИН вызов.

Инструмент: {tool}
Аргументы: {args}
Результат: {result}
Технический успех (без runtime-ошибки): {success}

Оцени по двум осям (0.0-1.0):
- argument_correctness: корректны ли аргументы для очевидной цели вызова (типы, пути,
  полнота; 1.0 = идеально, 0.0 = грубо неверно).
- task_completion: судя по результату, достигнута ли под-цель вызова (1.0 = да,
  0.0 = нет/пусто/не то). Технический успех ≠ решённая задача.

Ответь СТРОГО JSON одной строкой, без пояснений вокруг:
{{"argument_correctness": <float>, "task_completion": <float>, "comment": "<кратко>"}}"""

_DEFAULT_SAMPLE_RATE = 0.10  # 10% успехов (все провалы берём всегда)
_DEFAULT_CAP = 50  # потолок вызовов судьи за прогон (бюджет)


def _truncate(v: object, cap: int = 800) -> str:
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False, default=str)
    return s[:cap]


def stratified_sample(
    items: list[dict], rate: float = _DEFAULT_SAMPLE_RATE, cap: int = _DEFAULT_CAP
) -> list[dict]:
    """Все провалы (``success=False``) + детерминированный сэмпл успехов по ``rate``.

    Детерминизм без RNG-состояния: успех берётся, если ``sha1(tool_use_id) % 1000``
    попадает в первые ``rate*1000`` — воспроизводимо между прогонами (тот же вход →
    тот же сэмпл), тестируемо. Провалы приоритетны, ``cap`` режет общий размер."""
    fails = [it for it in items if not it.get("success")]
    succ = [it for it in items if it.get("success")]
    picked_succ = []
    thresh = int(max(0.0, min(1.0, rate)) * 1000)
    for it in succ:
        tid = str(it.get("tool_use_id") or json.dumps(it, sort_keys=True, default=str))
        h = int(hashlib.sha1(tid.encode("utf-8")).hexdigest(), 16) % 1000
        if h < thresh:
            picked_succ.append(it)
    out = fails + picked_succ  # провалы всегда, затем сэмпл успехов
    return out[:cap]


def build_judge_prompt(item: dict) -> str:
    return _JUDGE_RUBRIC.format(
        tool=item.get("tool", "?"),
        args=_truncate(item.get("args", "")),
        result=_truncate(item.get("result", "")),
        success=bool(item.get("success")),
    )


def parse_judge_response(text: str) -> dict | None:
    """Устойчивый разбор JSON-ответа судьи (может обрамляться прозой/```json```).

    None → неразобрано (не роняем прогон, метим как skipped). Клампим 0..1."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)  # первый JSON-объект
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return None

    def _clamp(x: object) -> float | None:
        try:
            return max(0.0, min(1.0, float(x)))
        except (ValueError, TypeError):
            return None

    ac = _clamp(obj.get("argument_correctness"))
    tc = _clamp(obj.get("task_completion"))
    if ac is None and tc is None:
        return None
    return {
        "argument_correctness": ac,
        "task_completion": tc,
        "comment": str(obj.get("comment", ""))[:300],
    }


def judge_items(items: list[dict], judge_fn: Callable[[str], str]) -> list[dict]:
    """Прогнать ``judge_fn`` (prompt→text) по item'ам, вернуть scored-записи.

    Изоляция per-item: судья упал/невнятный ответ → запись ``status='skipped'``
    (прогон не падает — advisory-контур не должен рушиться на одном item'е)."""
    out: list[dict] = []
    for it in items:
        rec = {
            "tool": it.get("tool"),
            "tool_use_id": it.get("tool_use_id"),
            "success": bool(it.get("success")),
        }
        try:
            text = judge_fn(build_judge_prompt(it))
        except Exception as exc:  # advisory-контур не роняем на одном item'е
            rec["status"] = "error"
            rec["error"] = f"{type(exc).__name__}: {exc}"[:200]
            out.append(rec)
            continue
        parsed = parse_judge_response(text)
        if parsed is None:
            rec["status"] = "skipped"  # неразобрано
        else:
            rec["status"] = "scored"
            rec.update(parsed)
        out.append(rec)
    return out


# ── источники judge-items ─────────────────────────────────────────────────────


def load_items_from_jsonl(path: Path) -> list[dict]:
    """Явный источник judge-items (jsonl, по dict на строку)."""
    if not path.exists():
        return []
    out = []
    for ln in path.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except ValueError:
            continue
    return out


# ── LLM-судья по умолчанию (llm_rotation, lazy) ───────────────────────────────


def _default_judge_fn(prompt: str) -> str:
    """LLM через LLMRotationService (z.ai/fallback). Async → синхронно обёрнуто.
    Ленивый импорт: без активации H-P4 тяжёлый src.* не тянется."""
    import asyncio

    from src.shared.llm_rotation.service import LLMRotationService  # type: ignore

    svc = LLMRotationService()

    async def _go() -> str:
        resp = await svc.complete(
            messages=[{"role": "user", "content": prompt}], max_tokens=200, temperature=0.0
        )
        # complete возвращает объект/строку — берём текст робастно
        return getattr(resp, "content", None) or getattr(resp, "text", None) or str(resp)

    return asyncio.run(_go())


# ── Langfuse Scores (опц.) ────────────────────────────────────────────────────


def _post_langfuse_scores(records: list[dict], endpoint: str, pk: str, sk: str) -> int:
    """Отправить scored-записи в Langfuse Scores API (advisory, best-effort).
    Возвращает число успешно отправленных. Нет creds/сети → 0, прогон цел."""
    import base64
    import urllib.request

    if not (endpoint and pk and sk):
        return 0
    token = base64.b64encode(f"{pk}:{sk}".encode()).decode()
    sent = 0
    for r in records:
        if r.get("status") != "scored":
            continue
        for axis in ("argument_correctness", "task_completion"):
            val = r.get(axis)
            if val is None:
                continue
            body = json.dumps(
                {
                    "name": f"llm_judge.{axis}",
                    "value": val,
                    "dataType": "NUMERIC",
                    "comment": r.get("comment", ""),
                    "traceId": r.get("tool_use_id") or "",
                }
            ).encode()
            req = urllib.request.Request(
                endpoint.rstrip("/") + "/api/public/scores",
                data=body,
                method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Basic {token}",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=5):
                    pass  # ответ не нужен; with закрывает fd (без утечки в цикле)
                sent += 1
            except Exception:
                pass  # advisory — не роняем
    return sent


# ── вход ──────────────────────────────────────────────────────────────────────


def run(
    source_jsonl: Path | None,
    judge_fn: Callable[[str], str] | None = None,
    rate: float = _DEFAULT_SAMPLE_RATE,
    cap: int = _DEFAULT_CAP,
    now: datetime | None = None,
) -> dict:
    """Прогон: источник → сэмпл → судья → jsonl. Нет источника/пусто → no-op."""
    now = now or datetime.now()
    items = load_items_from_jsonl(source_jsonl) if source_jsonl else []
    if not items:
        return {
            "available": False,
            "reason": "нет judge-items (нужен content-источник: OTEL_LOG_TOOL_CONTENT=1 "
            "или явный --source jsonl)",
        }
    sample = stratified_sample(items, rate=rate, cap=cap)
    fn = judge_fn or _default_judge_fn
    scored = judge_items(sample, fn)
    JUDGE_OUT.parent.mkdir(parents=True, exist_ok=True)
    ts = now.isoformat(timespec="seconds")
    with JUDGE_OUT.open("a", encoding="utf-8") as fh:
        for r in scored:
            fh.write(json.dumps({"ts": ts, **r}, ensure_ascii=False) + "\n")
    n_scored = sum(1 for r in scored if r.get("status") == "scored")
    return {
        "available": True,
        "total_items": len(items),
        "sampled": len(sample),
        "scored": n_scored,
        "skipped": sum(1 for r in scored if r.get("status") == "skipped"),
        "errors": sum(1 for r in scored if r.get("status") == "error"),
        "records": scored,
    }


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    p = argparse.ArgumentParser(description="LLM-judge tool-call'ов на сэмпле (260718 H-P4)")
    p.add_argument("--source", help="jsonl с judge-items (content-источник)")
    p.add_argument("--rate", type=float, default=_DEFAULT_SAMPLE_RATE, help="доля успехов в сэмпле")
    p.add_argument("--cap", type=int, default=_DEFAULT_CAP, help="потолок вызовов судьи")
    p.add_argument("--langfuse", action="store_true", help="слать Scores в Langfuse (env creds)")
    args = p.parse_args(argv)

    res = run(Path(args.source) if args.source else None, rate=args.rate, cap=args.cap)
    if not res.get("available"):
        print(f"llm-judge: no-op — {res.get('reason')}")
        return 0
    if args.langfuse:
        import os

        sent = _post_langfuse_scores(
            res["records"],
            os.environ.get("LANGFUSE_HOST", ""),
            os.environ.get("LANGFUSE_PUBLIC_KEY", ""),
            os.environ.get("LANGFUSE_SECRET_KEY", ""),
        )
        print(f"llm-judge: Langfuse scores отправлено {sent}")
    print(
        f"llm-judge: items={res['total_items']} sampled={res['sampled']} "
        f"scored={res['scored']} skipped={res['skipped']} errors={res['errors']} → {JUDGE_OUT}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
