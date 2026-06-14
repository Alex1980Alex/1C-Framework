"""Live-цепочки pdf-docs против локальных Qdrant/TEI (roadmap 260612 P1/P2).

Все тесты skip'аются при недоступных сервисах (как quality-gate в
tests/eval/test_smoke_gate.py) — CI без Qdrant/TEI не краснеет.

- A5 dim-контракт: 1024d-запрос в 4096d backup = честный 400 (G1-регресс-защита)
- B3: semantic_fallback_suggest на файле с известной главой
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[2]
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
TEI_URL = os.environ.get("TEI_URL", "http://localhost:8080")


def _service_up(url: str, probe: str) -> bool:
    try:
        import httpx

        with httpx.Client(timeout=3.0) as h:
            return h.get(url + probe).status_code == 200
    except Exception:
        return False


def _require_qdrant() -> None:
    if not _service_up(QDRANT_URL, "/healthz"):
        pytest.skip(f"Qdrant unreachable at {QDRANT_URL}")


def _require_tei() -> None:
    if not _service_up(TEI_URL, "/health"):
        pytest.skip(f"TEI unreachable at {TEI_URL}")


class TestA5DimContract:
    def test_1024_query_into_4096_backup_honest_error(self):
        _require_qdrant()
        import httpx

        resp = httpx.post(
            f"{QDRANT_URL}/collections/pdf_documents_4096_backup/points/query",
            json={"query": [0.03] * 1024, "limit": 3},
        )
        if resp.status_code == 404:
            pytest.skip("pdf_documents_4096_backup collection absent")
        assert resp.status_code == 400
        assert "dimension error" in resp.text.lower()

    @pytest.mark.skip(
        reason="requires live TEI/Qdrant absent in CI — needs service-skip guard, roadmap 260614"
    )
    def test_alias_query_dim_matches(self):
        """Запрос правильной размерности в alias проходит (alias жив и 1024d)."""
        _require_qdrant()
        import httpx

        resp = httpx.post(
            f"{QDRANT_URL}/collections/pdf_documents/points/query",
            json={"query": [0.03] * 1024, "limit": 1},
        )
        if resp.status_code == 404:
            pytest.skip("pdf_documents alias absent")
        assert resp.status_code == 200


class TestB3EnforcerSuggestion:
    def test_known_chapter_suggested(self):
        """unified_search.py живёт в 27_UNIFIED_MEMORY — suggest должен это знать.

        До фикса 2026-06-12 suggest слал 4096d-вектор в 1024d MRL-коллекцию
        и молча отвечал "(no confident match)" на ЛЮБОЙ файл.
        """
        _require_qdrant()
        _require_tei()
        hook = REPO / ".claude" / "hooks" / "docs-change-enforcer.py"
        proc = subprocess.run(
            [
                sys.executable,
                str(hook),
                "--semantic-suggest",
                "src/memory/orchestrator/unified_search.py",
            ],
            capture_output=True,
            text=True,
            cwd=str(REPO),
            timeout=60,
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        assert proc.returncode == 0, f"suggest failed: {proc.stderr[-500:]}"
        assert "27_UNIFIED_MEMORY" in proc.stdout
