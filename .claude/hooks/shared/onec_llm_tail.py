#!/usr/bin/env python3
"""#3 stage-3 (LLM-on-tail): классификатор 1С/не-1С для неоднозначного хвоста.

Зачем: эмбеддинги Qwen3 на коротком РУ 1С-тексте коллапсируют (ADR-023) — frozen-эмбеддинги
(cosine ИЛИ обученный probe, 5-fold F1≤0.76) проигрывают rule+TF-IDF (F1 0.976). LLM
классифицирует по СМЫСЛУ — призван закрыть near-domain хвост, который лексика не различает.

Реализация — ПРЯМОЙ вызов Ollama (`/api/chat`, `format=json`), НЕ через llm-rotation:
дефолтный primary llm-rotation = claude-cli, который спавнит полноценный Claude-агент ВНУТРИ
репо (мусор + max-turns, ADR-024), а structured-output (`format=json`) сервис не пробрасывает.
Прямой вызов с `format=json` форсит валидный JSON → надёжный парсинг (без болтовни прозой).
Модель — env `ONEC_TAIL_MODEL` (default qwen2.5:7b instruct; coder отдаёт false на всё).
Синхронный urllib (stdlib) — без asyncio/SDK/event-loop проблем.

Контракт (framework design): НЕ в синхронном hook-пути (хуки лёгкие, 5с); зовётся харнессом
`scripts/eval_1c_detector.py --llm-tail` + Claude on-demand на помеченном route'ом хвосте.
best-effort → None (Ollama down / parse-fail → вызыватель ОСТАВЛЯЕТ TF-IDF-вердикт).
"""

from __future__ import annotations

import json
import os
import re
import urllib.request

_OLLAMA_URL = os.environ.get("ONEC_OLLAMA_URL", "http://localhost:11434/api/chat")
_MODEL = os.environ.get("ONEC_TAIL_MODEL", "qwen2.5:7b")

_SYS = 'Ты классификатор задач. Возвращаешь ТОЛЬКО JSON-объект {"is_1c": true|false}, без пояснений.'
_TMPL = (
    'Текст: "{p}".\n'
    "Это ЗАДАЧА на разработку или доработку в системе 1С:Предприятие "
    "(конфигурация: документы, регистры, справочники, формы, печатные формы, проведение, "
    "движения, обмен данными между базами 1С, код BSL)? "
    "Задачи по другим технологиям (Python, ML, kafka, postgres, qdrant, docker, "
    "микросервисы, веб) и не-задачи — НЕ 1С.\n"
    'Верни строго: {{"is_1c": true}} или {{"is_1c": false}}'
)


def _parse(text: str) -> bool | None:
    """Извлечь is_1c из JSON-ответа модели. None если не распознано (graceful)."""
    if not text:
        return None
    m = re.search(r'"?is_1c"?\s*[:=]\s*(true|false|да|нет|1|0)', text, re.IGNORECASE)
    if m:
        return m.group(1).lower() in ("true", "да", "1")
    return None


def llm_classify(prompt: str, timeout: float = 60.0) -> bool | None:
    """1С-задача? по СМЫСЛУ через Ollama (format=json). True | False | None (сбой). best-effort."""
    try:
        payload = {
            "model": _MODEL,
            "messages": [
                {"role": "system", "content": _SYS},
                {"role": "user", "content": _TMPL.format(p=(prompt or "")[:300])},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0, "num_predict": 40},
        }
        req = urllib.request.Request(
            _OLLAMA_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        return _parse(data.get("message", {}).get("content", ""))
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
