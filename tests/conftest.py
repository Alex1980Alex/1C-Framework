"""Shared test fixtures for PDF Vector & Graph Framework."""

import os
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# Memory sink isolation (roadmap 260609 P0.2)
# =============================================================================
# Tests must never write to the production observability sinks
# (.claude/cache/confidence-lifecycle.log, memory-*.log, epoch, surfaced files)
# or to data/link_registry.db: 27 pytest runs left 183 fixture events in the
# real lifecycle log and 5 garbage edges in the real link graph (see
# docs/roadmap/260609_ROADMAP_MEMORY_REMEDIATION.md, A2).
#
# All memory writers honor these env overrides (lifecycle_log, epoch,
# trace_log, ingest_metrics, pattern_reinforce, LinkRegistry). They are set at
# conftest import time — BEFORE test modules import memory code — because some
# modules (shared/pattern_reinforce.py) resolve paths into module-level
# constants at import. Opt-out: MEMORY_TEST_ISOLATION_DISABLE=1.
if os.environ.get("MEMORY_TEST_ISOLATION_DISABLE") != "1":
    _mem_iso_root = Path(tempfile.mkdtemp(prefix="memtest-sinks-"))
    _mem_iso_cache = _mem_iso_root / "cache"
    _mem_iso_cache.mkdir(parents=True, exist_ok=True)
    os.environ["CLAUDE_CACHE_DIR"] = str(_mem_iso_cache)
    os.environ["LINK_REGISTRY_PATH"] = str(_mem_iso_root / "link_registry.db")


# =============================================================================
# Pipeline-state pollution guard (order-flake defense, 2026-06-18)
# =============================================================================
# pipeline_state пишет 1С-реестр / CURRENT / generic-состояния под РЕАЛЬНЫЙ
# репозиторный `pipeline/` через module-level path-константы (НЕ env-настраиваемые,
# в отличие от memory-синков выше). Тест, дотянувшийся до реального init_task/
# register_1c (напр. неполный sys.modules-мок, при котором `from shared import
# pipeline_state` резолвится из кэша — order-флейк, починенный в
# test_pipeline_1c_bridge), молча портит `pipeline/_1c_index.json` / `CURRENT`,
# а падает потом СОСЕДНИЙ тест — флейково и с неверной атрибуцией.
#
# Этот autouse-гард снимает снимок указанных файлов до теста и РОНЯЕТ сам
# тест-полютер, если они изменились — детерминированно, в ЛЮБОМ порядке, с
# кэшером или без. Детекция (а не tmp-изоляция) выбрана намеренно: пишущий в
# репо тест должен всплыть как падение и быть починен, а не «пройти», записав в
# tmp. Снимок восстанавливается, чтобы утечка не каскадила и не пачкала дерево.
# Opt-out: PIPELINE_POLLUTION_GUARD_DISABLE=1.
_PIPELINE_DIR = Path(__file__).resolve().parents[1] / "pipeline"
_PIPELINE_GUARD_TARGETS = (_PIPELINE_DIR / "_1c_index.json", _PIPELINE_DIR / "CURRENT")


@pytest.fixture(autouse=True)
def _pipeline_state_pollution_guard():
    if os.environ.get("PIPELINE_POLLUTION_GUARD_DISABLE") == "1":
        yield
        return

    def _snap() -> dict:
        out: dict = {}
        for t in _PIPELINE_GUARD_TARGETS:
            try:
                out[t] = t.read_bytes() if t.exists() else None
            except OSError:
                out[t] = None
        return out

    before = _snap()
    yield
    after = _snap()
    polluted = [t.name for t in _PIPELINE_GUARD_TARGETS if before.get(t) != after.get(t)]
    # best-effort restore — утечка не должна каскадить в следующий тест / рабочее дерево
    for t in _PIPELINE_GUARD_TARGETS:
        if before.get(t) != after.get(t):
            try:
                if before.get(t) is None:
                    t.unlink(missing_ok=True)
                else:
                    t.write_bytes(before[t])
            except OSError:
                pass
    assert not polluted, (
        f"Тест записал в РЕАЛЬНЫЙ pipeline/ ({', '.join(polluted)}) — нужна изоляция "
        "(tmp PIPELINE_DIR/REGISTRY_PTR/CURRENT либо force-fail импорта shared.pipeline_state). "
        "Снимок восстановлен."
    )


# =============================================================================
# Basic Fixtures
# =============================================================================


@pytest.fixture
def sample_pdf_path(tmp_path):
    """Path to a sample PDF for testing (to be created in fixtures)."""
    return tmp_path / "sample.pdf"


@pytest.fixture
def sample_chunks():
    """Sample document chunks for testing."""
    from src.pdf_framework.schemas.documents import DocumentChunk

    return [
        DocumentChunk(
            id=f"chunk_{i}",
            content=f"Sample content for chunk {i}",
            document_id="doc_1",
            page_number=i,
            chunk_index=i,
        )
        for i in range(5)
    ]


@pytest.fixture
def sample_embeddings():
    """Sample embedding vectors for testing."""
    import random

    random.seed(42)
    return [[random.random() for _ in range(384)] for _ in range(5)]


# =============================================================================
# Mock Fixtures for External Services
# =============================================================================


@pytest.fixture
def mock_qdrant_client() -> Generator[MagicMock, None, None]:
    """Mock Qdrant client for testing (no Docker required)."""
    mock_client = MagicMock()

    # Mock collection operations
    mock_client.collection_exists.return_value = True
    mock_client.create_collection.return_value = None
    mock_client.delete_collection.return_value = None

    # Mock point operations
    mock_client.upsert.return_value = None
    mock_client.delete.return_value = None

    # Mock search operations
    mock_client.search.return_value = [
        MagicMock(
            id="chunk_1",
            score=0.95,
            payload={
                "content": "Sample content",
                "document_id": "doc_1",
                "page_number": 1,
            },
        )
    ]

    # Mock scroll operations
    mock_client.scroll.return_value = ([], None)

    with patch(
        "src.pdf_framework.vector_store.providers.qdrant.QdrantClient", return_value=mock_client
    ):
        yield mock_client


@pytest.fixture
def mock_anthropic_client() -> Generator[AsyncMock, None, None]:
    """Mock Anthropic client for testing (no API calls)."""
    mock_client = AsyncMock()

    # Mock message creation
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Test response")]
    mock_response.usage = MagicMock(input_tokens=10, output_tokens=20)
    mock_client.messages.create.return_value = mock_response

    # Mock streaming
    async def mock_stream(*_args, **_kwargs):
        yield MagicMock(type="message_start", message=MagicMock(id="msg_123"))
        yield MagicMock(type="content_block_delta", delta=MagicMock(text="Streaming"))
        yield MagicMock(type="message_delta")

    mock_client.messages.stream = mock_stream

    with patch("anthropic.AsyncAnthropic", return_value=mock_client):
        yield mock_client


@pytest.fixture
def mock_openai_client() -> Generator[AsyncMock, None, None]:
    """Mock OpenAI client for testing (no API calls)."""
    mock_client = AsyncMock()

    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
    mock_client.embeddings.create.return_value = mock_response

    with patch("openai.AsyncOpenAI", return_value=mock_client):
        yield mock_client


# =============================================================================
# Document Fixtures
# =============================================================================


@pytest.fixture
def sample_processed_document():
    """Sample ProcessedDocument for testing (reusable in unit tests)."""
    from src.pdf_framework.schemas.documents import (
        DocumentChunk,
        DocumentMetadata,
        ProcessedDocument,
    )

    return ProcessedDocument(
        id="test_doc_1",
        source_path="/path/to/test.pdf",
        metadata=DocumentMetadata(
            title="Test Document",
            author="Test Author",
            page_count=3,
        ),
        chunks=[
            DocumentChunk(
                id="chunk_1",
                content="First chunk content",
                document_id="test_doc_1",
                page_number=1,
                chunk_index=0,
                section="Introduction",
            ),
            DocumentChunk(
                id="chunk_2",
                content="Second chunk content",
                document_id="test_doc_1",
                page_number=2,
                chunk_index=1,
                section="Body",
            ),
        ],
    )


# =============================================================================
# Temporary Data Directory Fixture
# =============================================================================


@pytest.fixture
def temp_data_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Temporary data directory for isolated test runs."""
    data_dir = tmp_path / "test_data"
    data_dir.mkdir()

    # Create subdirectories
    (data_dir / "vector_db").mkdir()
    (data_dir / "bm25_index.db").touch()
    (data_dir / "graph_db").mkdir()
    (data_dir / "cache" / "embeddings").mkdir(parents=True)
    (data_dir / "pdfs").mkdir()

    yield data_dir


# =============================================================================
# Settings Override Fixture
# =============================================================================


@pytest.fixture
def test_settings(temp_data_dir: Path) -> Generator[None, None, None]:
    """Override settings with in-memory stores for isolated tests."""
    original_env = os.environ.copy()

    # Set test environment variables
    os.environ.update(
        {
            "DATA_DIR": str(temp_data_dir),
            "VECTOR_STORE__PROVIDER": "qdrant",
            "VECTOR_STORE__QDRANT_URL": "http://localhost:6333",
            "EMBEDDING__MODEL": "intfloat/multilingual-e5-large",
            "EMBEDDING__DIMENSIONS": "1024",
            "EMBEDDING__DEVICE": "cpu",
            "SEARCH__BM25_WEIGHT": "0.3",
            "CACHE__ENABLED": "true",
            "CACHE__TYPE": "memory",
            "LOG_LEVEL": "DEBUG",
        }
    )

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


# =============================================================================
# Async Test Fixtures
# =============================================================================


@pytest.fixture
def event_loop_policy():
    """Use default event loop policy for async tests."""
    import asyncio

    return asyncio.DefaultEventLoopPolicy()


# =============================================================================
# Performance Testing Fixtures
# =============================================================================


@pytest.fixture
def benchmark_data():
    """Generate benchmark data for performance tests."""
    import random

    random.seed(42)
    return {
        "chunks": [f"Chunk {i} content " * 100 for i in range(1000)],
        "queries": [f"Query {i}" for i in range(100)],
        "embeddings": [[random.random() for _ in range(1024)] for _ in range(1000)],
    }


# T.6 (260430_AUDIT_TESTS_COVERAGE.md) — auto-mark phase tests by path so
# `pytest -m phase8` works without per-test decorators. Markers themselves
# are registered in pyproject.toml [tool.pytest.ini_options] markers.
_PHASE_PATH_MARKERS = {
    "test_phase4_": "phase4",
    "test_phase14": "phase14",
    "test_phase15": "phase15",
    "test_phase16": "phase16",
    "test_phase17": "phase17",
    "test_phase18": "phase18",
    "test_phase19": "phase19",
    "test_phase20": "phase20",
    "test_phase21": "phase21",
    "test_phase22": "phase22",
    "test_phase23": "phase23",
    "test_qwen3_": "phase8",
    "test_late_chunking": "phase8",
    "test_reindex_qwen3_oom": "phase8",
    "test_bsl_chunker_split": "phase8",
    "test_framework_search": "phase9",
    "test_memory_first_hook": "phase9",
    "test_post_commit_reindex": "phase9",
}
_DIR_MARKERS = {
    "test_framework_search": "framework_search",
    "bsl": "bsl",
}


def pytest_collection_modifyitems(config, items):
    for item in items:
        path = str(item.fspath).replace("\\", "/").lower()
        for fragment, marker in _PHASE_PATH_MARKERS.items():
            if fragment.lower() in path:
                item.add_marker(marker)
        for fragment, marker in _DIR_MARKERS.items():
            if f"/{fragment.lower()}/" in path:
                item.add_marker(marker)
