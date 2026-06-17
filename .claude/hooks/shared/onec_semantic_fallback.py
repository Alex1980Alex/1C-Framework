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
import os
import re
import sys
import urllib.request
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


# ── #3 stage-2b: TEI-эскалация — ОЦЕНЕНО, НЕ ПРИНЯТО в route (ADR-023) ───────────────────
# Гипотеза: эмбеддинги Qwen3 различат near-domain по СМЫСЛУ («обмен 1С» vs «обмен kafka»),
# чего bag-of-words TF-IDF не может. РЕЗУЛЬТАТ ЗАМЕРА (golden-set): эмбеддинги анизотропны на
# коротком РУ 1С-тексте — негативы (qdrant / «лабораторный анализ») дают cosine 0.85–0.90 наравне
# с позитивами; centering (вычитание mean) overlap не убирает (один явный FN даже упал до 0.45).
# Согласуется с [[feedback-bsl-embedding-collapse]]. Вывод: TF-IDF stage-2a разделяет лучше —
# оставлен финальным семантическим слоем. Функции ниже доступны через CLI (build-emb/emb) для
# будущего пересмотра (reranker), но В route НЕ ВКЛЮЧЕНЫ. graceful: TEI down → 0.0.
_TEI_URL = os.environ.get("ONEC_TEI_URL", "http://localhost:8080/embed")
_EMB_DIM = 1024  # MRL truncate 4096→1024 + renorm (как framework_code_v1 / prework-similar-code)
EMB_INDEX = PROJECT_ROOT / "data" / "1c-utterance-embeddings.json"
_emb_cache: dict | None = None


def _tei_embed(texts: list[str], timeout: float = 2.0) -> list | None:
    """Эмбеддинги через TEI (urllib, stdlib — без httpx в hook). list[vec] | None (сбой)."""
    try:
        req = urllib.request.Request(
            _TEI_URL,
            data=json.dumps({"inputs": texts}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _mrl(vec: list[float], dim: int = _EMB_DIM) -> list[float]:
    """Matryoshka: первые dim + L2-renorm (cosine = dot после нормировки)."""
    v = vec[:dim]
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def build_embeddings(path: Path = EMB_INDEX, timeout: float = 60.0, batch: int = 32) -> int:
    """Оффлайн: utterances → TEI → MRL-1024 → JSON. N | -1 (TEI down). Чанки ≤32 —
    TEI max_client_batch_size=32, batch>32 = HTTP 413 (memory feedback_tei_batch_size_limit)."""
    utt = _load_utterances()
    vecs: list = []
    for i in range(0, len(utt), batch):
        raw = _tei_embed(utt[i : i + batch], timeout=timeout)
        if not raw:
            return -1
        vecs.extend(_mrl(v) for v in raw)
    path.write_text(json.dumps({"dim": _EMB_DIM, "vecs": vecs}), encoding="utf-8")
    return len(utt)


def _get_embeddings() -> dict | None:
    global _emb_cache
    if _emb_cache is not None:
        return _emb_cache or None
    try:
        _emb_cache = json.loads(EMB_INDEX.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        _emb_cache = {}
    return _emb_cache or None


def embed_sim(text: str, timeout: float = 1.5) -> float:
    """Max cosine TEI-эмбеддинга текста к utterance-эмбеддингам ∈ [0,1]. best-effort → 0.0
    (TEI down / нет индекса → 0.0; вызыватель деградирует на TF-IDF-вердикт)."""
    try:
        idx = _get_embeddings()
        if not idx or not idx.get("vecs"):
            return 0.0
        raw = _tei_embed([text], timeout=timeout)
        if not raw:
            return 0.0
        q = _mrl(raw[0], idx.get("dim", _EMB_DIM))
        best = 0.0
        for v in idx["vecs"]:
            dot = sum(a * b for a, b in zip(q, v))  # обе L2-норм → dot = cosine
            if dot > best:
                best = dot
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
    if args and args[0] == "build-emb":
        k = build_embeddings()
        print(
            f"built embeddings from {k} utterances -> {EMB_INDEX}"
            if k >= 0
            else "TEI down — embeddings NOT built"
        )
        return 0 if k >= 0 else 1
    if len(args) >= 2 and args[0] == "sim":
        print(semantic_sim(args[1]))
        return 0
    if len(args) >= 2 and args[0] == "emb":
        print(embed_sim(args[1]))
        return 0
    print("usage: onec_semantic_fallback.py build | build-emb | sim <text> | emb <text>")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
