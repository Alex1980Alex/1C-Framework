#!/usr/bin/env python3
"""#3 stage-2a: TF-IDF semantic fallback для детектора 1С-задач.

Лексическое сходство сырого промта с курируемыми 1С-фразами (route-определения,
`data/1c-utterances.json`) — поднимает recall на парафразах/опечатках, которые
стем-словарь `classify_1c_task` упускает. Срабатывает ТОЛЬКО на неуверенных входах
(`confidence < 0.7`) из `route_1c_task`; семантика = МЯГКИЙ сигнал (→ ask_1c, не confident).

Чистый stdlib (math/Counter/re) — НЕТ sklearn/numpy в hot-path. Индекс строится оффлайн
(`build`), runtime лишь токенизирует + косинус по ~40 фразам (<5 мс). Кэш индекса на процесс.
Токены = слова + char-3-граммы (морфология русского без лемматизации — родственные словоформы
делят n-граммы). Контракт: НИКОГДА не кидает (вызыватель деградирует на 0.0).

CLI:
    python .claude/hooks/shared/onec_semantic_fallback.py build   # пересобрать индекс
    python .claude/hooks/shared/onec_semantic_fallback.py sim "текст"  # отладочный скор
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
UTTERANCES = PROJECT_ROOT / "data" / "1c-utterances.json"
INDEX = PROJECT_ROOT / "data" / "1c-semantic-index.json"

_WORD = re.compile(r"[а-яёa-z0-9]+", re.UNICODE)
_MIN_WORD = 3  # слова короче 3 символов берём как есть, без char-граммов

_cache: dict | None = None  # ленивый кэш индекса на процесс


def _tokenize(text: str) -> list[str]:
    """Слова (нормализованные ё→е) + char-3-граммы внутри слова (морфология)."""
    toks: list[str] = []
    for w in _WORD.findall((text or "").lower().replace("ё", "е")):
        toks.append("w:" + w)
        if len(w) >= _MIN_WORD:
            for i in range(len(w) - 2):
                toks.append("c:" + w[i : i + 3])
    return toks


def build_index(utterances: list[str]) -> dict:
    """TF-IDF индекс по route-фразам: {idf{token:idf}, docs[{vec,norm}]}."""
    docs_tokens = [_tokenize(u) for u in utterances]
    n = len(docs_tokens) or 1
    df: Counter = Counter()
    for toks in docs_tokens:
        for t in set(toks):
            df[t] += 1
    idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}
    docs = []
    for toks in docs_tokens:
        tf = Counter(toks)
        vec = {t: tf[t] * idf[t] for t in tf}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        docs.append({"vec": vec, "norm": norm})
    return {"idf": idf, "docs": docs, "n": len(utterances)}


def _load_utterances() -> list[str]:
    try:
        data = json.loads(UTTERANCES.read_text(encoding="utf-8"))
        return list(data.get("utterances", []))
    except (OSError, ValueError):
        return []


def save_index(path: Path = INDEX) -> int:
    utt = _load_utterances()
    idx = build_index(utt)
    path.write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
    return len(utt)


def _get_index() -> dict | None:
    """Индекс из utterances в памяти (кэш на процесс). Единственный источник истины —
    data/1c-utterances.json (нет рассинхрона index↔utterances; persisted-файл не нужен runtime,
    `build` CLI пишет его лишь для инспекции). ~мс на 40 фраз → дёшево даже на fresh-процесс хука."""
    global _cache
    if _cache is not None:
        return _cache or None
    try:
        utt = _load_utterances()
        _cache = build_index(utt) if utt else {}
    except Exception:
        _cache = {}
    return _cache or None


def semantic_sim(text: str, index: dict | None = None) -> float:
    """Max cosine сырого текста к route-фразам ∈ [0,1]. best-effort → 0.0.

    NB: query↔doc асимметрично (`sim(A, idxB) != sim(B, idxA)`) — общий idf принадлежит
    индексу, роли запроса и документа разные. Это by-design, не баг. Потолок precision:
    bag-of-words не различает смысл near-domain текста («обмен данными 1С» vs «обмен
    микросервисами kafka») — снимается TEI-эскалацией (#3 stage-2b).
    """
    try:
        idx = index if index is not None else _get_index()
        if not idx or not idx.get("docs"):
            return 0.0
        idf = idx["idf"]
        tf = Counter(_tokenize(text))
        q = {t: tf[t] * idf[t] for t in tf if t in idf}
        if not q:
            return 0.0
        qnorm = math.sqrt(sum(v * v for v in q.values())) or 1.0
        best = 0.0
        for d in idx["docs"]:
            dvec = d["vec"]
            # итерируем по меньшему словарю
            small, big = (q, dvec) if len(q) <= len(dvec) else (dvec, q)
            dot = sum(val * big.get(tok, 0.0) for tok, val in small.items())
            if dot:
                cos = dot / (qnorm * d["norm"])
                if cos > best:
                    best = cos
        return round(best, 4)
    except Exception:
        return 0.0


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if args and args[0] == "build":
        k = save_index()
        print(f"built index from {k} utterances -> {INDEX}")
        return 0
    if len(args) >= 2 and args[0] == "sim":
        print(semantic_sim(args[1]))
        return 0
    print("usage: onec_semantic_fallback.py build | sim <text>")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
