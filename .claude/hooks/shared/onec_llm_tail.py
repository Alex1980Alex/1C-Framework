#!/usr/bin/env python3
"""#3 stage-3 (LLM-on-tail): классификатор 1С/не-1С для неоднозначного хвоста.

Зачем: эмбеддинги Qwen3 на коротком РУ 1С-тексте коллапсируют (ADR-023) — frozen-эмбеддинги
(cosine ИЛИ обученный probe, 5-fold F1≤0.76) проигрывают rule+TF-IDF (F1 0.976). LLM
классифицирует по СМЫСЛУ — закрывает near-domain хвост («обмен 1С» vs «обмен kafka»),
который лексика не различает. Через cheap_llm_call (llm-rotation: claude-cli-haiku / ollama).

Контракт (framework design): НЕ в синхронном hook-пути — хуки лёгкие (5с, regex), LLM-работа
у Claude/агента. Зовётся:
  * харнессом `scripts/eval_1c_detector.py --llm-tail` (замер потолка LLM на хвосте);
  * Claude on-demand на помеченном `route_1c_task` хвосте (`out["llm_tail"]`).
best-effort → None (LLM down / parse-fail → вызыватель ОСТАВЛЯЕТ TF-IDF-вердикт). Структурный
JSON-выход + температура 0 (детерминизм).
"""

from __future__ import annotations

import asyncio
import os
import re

_SYS = "Ты строгий классификатор задач. Отвечай ТОЛЬКО JSON, без пояснений."
_TMPL = (
    'Сообщение из чата: "{p}"\n\n'
    "Это ЗАДАЧА на разработку или доработку в системе 1С:Предприятие "
    "(конфигурация: документы, справочники, регистры, формы, печатные формы, проведение, "
    "движения, обмен данными 1С, BSL-код)? "
    "НЕ 1С: задачи по другим технологиям (Python, web, kafka, postgres, docker, "
    "микросервисы, RAG/ML), общие вопросы, не-задачи.\n"
    'Ответь строго JSON: {{"is_1c": true|false}}'
)

# Instruct-модель ollama (НЕ coder — qwen2.5-coder:7b отдаёт false на всё, ADR-024).
# qwen2.5:7b уже в allow-list провайдера ollama-local (service.py:185); env-override на будущее.
_MODEL = os.environ.get("ONEC_TAIL_MODEL", "qwen2.5:7b")


def _parse(text: str) -> bool | None:
    """Извлечь is_1c из ответа LLM. None если не распознано."""
    if not text:
        return None
    m = re.search(r'"?is_1c"?\s*[:=]\s*(true|false|да|нет|1|0)', text, re.IGNORECASE)
    if m:
        return m.group(1).lower() in ("true", "да", "1")
    low = text.strip().lower()
    has_t, has_f = ("true" in low or "да" in low), ("false" in low or "нет" in low)
    if has_t and not has_f:
        return True
    if has_f and not has_t:
        return False
    return None


async def _aclassify(prompt: str, timeout: float) -> bool | None:
    # service.complete напрямую (НЕ cheap_llm_call): нужно нацелить на instruct-модель _MODEL
    # + форсировать ollama-local (claude-cli спавнит in-repo агента → мусор, ADR-024).
    from src.shared.llm_rotation.service import get_service

    result = await asyncio.wait_for(
        get_service().complete(
            prompt=_TMPL.format(p=prompt[:300]),
            system_prompt=_SYS,
            model=_MODEL,
            preferred_provider="ollama-local",
            temperature=0.0,
            max_tokens=24,
        ),
        timeout=timeout,
    )
    return _parse(result.get("text", "") if isinstance(result, dict) else "")


_loop = None


def _get_loop():
    """Один переиспользуемый event loop на процесс. asyncio.run() закрывал бы loop, к которому
    привязан кэш-клиент сервиса llm-rotation → 'Event loop is closed' на 2-м вызове (batch/eval)."""
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
    return _loop


def llm_classify(prompt: str, timeout: float = 25.0) -> bool | None:
    """1С-задача? по СМЫСЛУ через LLM. True | False | None (сбой). best-effort, не кидает."""
    try:
        return _get_loop().run_until_complete(_aclassify(prompt or "", timeout))
    except Exception:
        return None


if __name__ == "__main__":
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if len(sys.argv) >= 2:
        print(llm_classify(sys.argv[1]))
    else:
        print("usage: onec_llm_tail.py <text>")
