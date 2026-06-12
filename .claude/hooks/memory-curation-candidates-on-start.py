#!/usr/bin/env python3
"""
Hook: memory-curation-candidates-on-start
Event: SessionStart
Purpose: R1 (ADR-007, рекомендации 2026-06-12): входящий конвейер для
  КУРИРУЕМОЙ памяти (MEMORY.md + memory/*.md). Store→канон до сих пор
  переносился только «если человек сам вспомнил»; индустриальный паттерн —
  holding-area → human review → promotion (GitHub Copilot agentic memory,
  agentmemory). Хук НЕ пишет в канон (write-gate остаётся ручным!) — только
  показывает кандидатов: устоявшиеся паттерны learned_patterns
  (effective_confidence >= 0.85, application_count >= 5, не archived),
  ещё не отражённые в memory/*.md.
Opt-out: MEMORY_CURATION_BANNER_DISABLE=1
Cooldown: 20h (sentinel mtime) — баннер не чаще раза в день.
Timeout: 8s (один Qdrant scroll learned_patterns ~50 точек, fail-soft).
"""

import os
import re
import sys
import time
from pathlib import Path

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)
# src через append, НЕ insert(0) — иначе src/shared затеняет hooks/shared
# (memory feedback-hook-src-shared-collision)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT / "src"))

from base import BaseHook, HookInput, HookOutput

MEMORY_DIR = Path.home() / ".claude" / "projects" / "C--1--Framework" / "memory"
COOLDOWN_FILE = PROJECT_ROOT / ".claude" / "cache" / "memory-curation-banner-last.txt"
COOLDOWN_SECONDS = 20 * 3600
CONF_MIN = 0.85
COUNT_MIN = 5
TOP_N = 3
# Jaccard-порог совпадения имени паттерна со слагом memory-записи:
# выше → считаем, что канон уже покрывает паттерн
COVERED_JACCARD = 0.5


def _tokens(text: str) -> set[str]:
    """Content-bearing токены (len>=4) из имени/слага, регистронезависимо."""
    return {
        t
        for t in re.split(r"[^\w]+", text.replace("_", " ").replace("-", " ").lower())
        if len(t) >= 4
    }


def _jaccard_prefix(a: set[str], b: set[str]) -> float:
    """Jaccard с prefix-эквивалентностью токенов (alias~aliases, паттерн~паттерны).

    Морфоформы RU/EN различаются хвостом — точное равенство множества рвёт
    (naive-стеммер ловушка: alias→alia ≠ aliases→alias). Токены считаются
    совпавшими, если один — префикс другого (min len 4 гарантирован _tokens).
    """
    if not a or not b:
        return 0.0
    matched = sum(1 for x in a if any(x.startswith(y) or y.startswith(x) for y in b))
    return matched / (len(a) + len(b) - matched)


def select_candidates(
    patterns: list[dict],
    corpus: str,
    slug_token_sets: list[set[str]],
    conf_min: float = CONF_MIN,
    count_min: int = COUNT_MIN,
) -> list[dict]:
    """Отбор кандидатов в курируемую память (pure, тестируемо).

    pattern: {id, name, effective_confidence, application_count, archived,
    content_hash}. Покрытым считается паттерн, чей id/content_hash упомянут
    в corpus (тексты всех memory/*.md) ЛИБО имя сильно пересекается со
    слагом существующей записи (Jaccard >= COVERED_JACCARD).
    """
    out: list[dict] = []
    for p in patterns:
        if p.get("archived"):
            continue
        # `or 0`: payload может нести явный null — .get(default) его не покрывает
        if float(p.get("effective_confidence") or 0.0) < conf_min:
            continue
        if int(p.get("application_count") or 0) < count_min:
            continue
        pid = str(p.get("id", ""))
        chash = str(p.get("content_hash", ""))
        if (pid and pid in corpus) or (chash and chash in corpus):
            continue
        ptoks = _tokens(str(p.get("name", "")))
        if ptoks and any(
            _jaccard_prefix(ptoks, st) >= COVERED_JACCARD for st in slug_token_sets if st
        ):
            continue
        out.append(p)
    out.sort(key=lambda x: float(x.get("effective_confidence") or 0.0), reverse=True)
    return out


def _load_memory_layer() -> tuple[str, list[set[str]]]:
    """corpus (конкатенация .md, lower) + token-sets слагов записей."""
    corpus_parts: list[str] = []
    slug_sets: list[set[str]] = []
    if not MEMORY_DIR.exists():
        return "", []
    for p in MEMORY_DIR.glob("*.md"):
        slug_sets.append(_tokens(p.stem))
        try:
            corpus_parts.append(p.read_text(encoding="utf-8", errors="replace").lower())
        except OSError:
            continue
    return "\n".join(corpus_parts), slug_sets


def _scroll_patterns() -> list[dict]:
    """learned_patterns с effective confidence (lazy decay-on-read §22 P2)."""
    from qdrant_client import QdrantClient

    from memory.vector_memory.confidence import payload_effective_confidence

    client = QdrantClient(url=os.environ.get("QDRANT_URL", "http://localhost:6333"), timeout=5)
    out: list[dict] = []
    offset = None
    while True:
        pts, offset = client.scroll(
            collection_name="learned_patterns",
            limit=200,
            with_payload=True,
            with_vectors=False,
            offset=offset,
        )
        for pt in pts:
            pay = pt.payload or {}
            out.append(
                {
                    "id": str(pt.id),
                    "name": pay.get("name", ""),
                    "effective_confidence": payload_effective_confidence(pay),
                    "application_count": pay.get("application_count", 0),
                    "archived": bool(pay.get("expired_at")),
                    "content_hash": pay.get("content_hash", ""),
                }
            )
        if offset is None:
            break
    return out


class MemoryCurationCandidates(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get("MEMORY_CURATION_BANNER_DISABLE") == "1":
            return None
        try:
            if (
                COOLDOWN_FILE.exists()
                and time.time() - COOLDOWN_FILE.stat().st_mtime < COOLDOWN_SECONDS
            ):
                return None
        except OSError:
            return None

        try:
            patterns = _scroll_patterns()
        except Exception:
            return None  # Qdrant down / cold — молча, не трогая cooldown (ретрай след. сессией)

        corpus, slug_sets = _load_memory_layer()
        candidates = select_candidates(patterns, corpus, slug_sets)

        try:
            COOLDOWN_FILE.parent.mkdir(parents=True, exist_ok=True)
            COOLDOWN_FILE.write_text(str(time.time()), encoding="utf-8")
        except OSError:
            pass

        if not candidates:
            return None

        names = "; ".join(
            f"{(c.get('name') or c['id'])[:60]} (conf {c['effective_confidence']:.2f}, "
            f"apps {c['application_count']})"
            for c in candidates[:TOP_N]
        )
        msg = (
            f"[CURATION] {len(candidates)} паттерн(ов) созрели для курируемой памяти "
            f"(conf>={CONF_MIN}, apps>={COUNT_MIN}), top-{min(TOP_N, len(candidates))}: {names}\n"
            "  Если согласен — оформи memory/*.md записью (write-gate ручной, ADR-007); "
            "запись с citations (file:line) — verify-at-read дешевле."
        )
        return HookOutput().system_message(msg)


if __name__ == "__main__":
    MemoryCurationCandidates().run()
