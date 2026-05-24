"""
Unit tests для alias-aware инициализации QdrantVectorStore.

Регрессия Phase 8 MIGRATE-3 (2026-05-19):
Production коллекции `pdf_documents`, `framework_code_v1`, `wiki_pages_v1` были переведены
на Qdrant aliases, указывающие на физические коллекции `*_mrl_1024`. Старый
QdrantVectorStore.initialize() проверял только get_collections() (физические имена),
получал exists=False для alias и пытался вызвать create_collection(), что приводило
к HTTP 400 "Alias with the same name already exists".

Фикс: объединить результаты get_collections() и get_aliases(), проверять оба источника
при определении существования коллекции. Graceful fallback на collection_names если
get_aliases() недоступен (AttributeError для старых Qdrant клиентов).

Ссылки:
- docs/framework documentation/04_ПОИСК/04.9_Matryoshka_Embeddings.md §4.1.16
- Коммит фикса: 2026-05-19
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pdf_framework.config import VectorStoreSettings
from src.pdf_framework.vector_store.providers.qdrant import QdrantVectorStore


def _make_collection(name: str) -> SimpleNamespace:
    """Создаёт mock коллекции с заданным именем."""
    return SimpleNamespace(name=name)


def _make_alias(alias_name: str, collection_name: str) -> SimpleNamespace:
    """Создаёт mock alias с именем и целевой коллекцией."""
    return SimpleNamespace(alias_name=alias_name, collection_name=collection_name)


def _make_collection_info(dim: int = 4096, has_sparse_bm25: bool = False) -> MagicMock:
    """Создаёт mock информацию о коллекции для ответа get_collection()."""
    config_mock = MagicMock()
    dense_mock = MagicMock()
    dense_mock.size = dim
    config_mock.params.vectors = {"dense": dense_mock}
    config_mock.params.sparse_vectors = {"bm25": MagicMock()} if has_sparse_bm25 else None

    info = MagicMock()
    info.config = config_mock
    info.points_count = 0
    return info


def _build_mock_client(
    *,
    collections: list[str],
    aliases: list[tuple[str, str]] | None = None,
    raise_on_get_aliases: type[BaseException] | None = None,
    dim: int = 4096,
) -> MagicMock:
    """Строит mock AsyncQdrantClient с заданными коллекциями и aliases."""
    client = MagicMock()
    client.get_collections = AsyncMock(
        return_value=SimpleNamespace(collections=[_make_collection(name) for name in collections])
    )
    if raise_on_get_aliases is not None:
        client.get_aliases = AsyncMock(side_effect=raise_on_get_aliases())
    else:
        alias_objs = [_make_alias(alias_name, target) for alias_name, target in (aliases or [])]
        client.get_aliases = AsyncMock(return_value=SimpleNamespace(aliases=alias_objs))
    client.get_collection = AsyncMock(return_value=_make_collection_info(dim=dim))
    client.create_collection = AsyncMock()
    return client


@pytest.mark.unit
class TestQdrantAliasAwareInitialize:
    """Regression coverage for alias-aware existence check (2026-05-19)."""

    @pytest.mark.asyncio
    async def test_alias_match_skips_create_collection(self):
        """Имя в конфиге = alias → exists=True → create_collection НЕ вызывается."""
        settings = VectorStoreSettings(
            provider="qdrant",
            collection_name="pdf_documents",
            dimensions=4096,
            qdrant_url="http://localhost:6333",
            qdrant_api_key="",
        )
        store = QdrantVectorStore(settings)

        mock_client = _build_mock_client(
            collections=["pdf_documents_mrl_1024", "bsl_code_v4"],
            aliases=[("pdf_documents", "pdf_documents_mrl_1024")],
            dim=1024,
        )

        with patch("qdrant_client.AsyncQdrantClient", return_value=mock_client):
            await store.initialize()

        mock_client.get_collections.assert_awaited_once()
        mock_client.get_aliases.assert_awaited_once()
        mock_client.create_collection.assert_not_awaited()
        assert store._initialized is True

    @pytest.mark.asyncio
    async def test_missing_collection_triggers_create(self):
        """Имя ни в collection_names, ни в alias_names → create_collection вызывается."""
        settings = VectorStoreSettings(
            provider="qdrant",
            collection_name="fresh_collection",
            dimensions=4096,
            qdrant_url="http://localhost:6333",
            qdrant_api_key="",
        )
        store = QdrantVectorStore(settings)

        mock_client = _build_mock_client(
            collections=["pdf_documents_mrl_1024"],
            aliases=[("pdf_documents", "pdf_documents_mrl_1024")],
        )

        with patch("qdrant_client.AsyncQdrantClient", return_value=mock_client):
            await store.initialize()

        mock_client.create_collection.assert_awaited_once()
        kwargs = mock_client.create_collection.await_args.kwargs
        assert kwargs["collection_name"] == "fresh_collection"

    @pytest.mark.asyncio
    async def test_get_aliases_attribute_error_graceful_fallback(self):
        """Старый qdrant-client без get_aliases() → AttributeError проглатывается."""
        settings = VectorStoreSettings(
            provider="qdrant",
            collection_name="pdf_documents_mrl_1024",
            dimensions=1024,
            qdrant_url="http://localhost:6333",
            qdrant_api_key="",
        )
        store = QdrantVectorStore(settings)

        mock_client = _build_mock_client(
            collections=["pdf_documents_mrl_1024"],
            raise_on_get_aliases=AttributeError,
            dim=1024,
        )

        with patch("qdrant_client.AsyncQdrantClient", return_value=mock_client):
            await store.initialize()

        mock_client.get_aliases.assert_awaited_once()
        mock_client.create_collection.assert_not_awaited()
        assert store._initialized is True

    @pytest.mark.asyncio
    async def test_physical_collection_match_works_without_aliases(self):
        """Имя = физическая коллекция (не alias) → exists=True по collection_names."""
        settings = VectorStoreSettings(
            provider="qdrant",
            collection_name="bsl_code_v4",
            dimensions=4096,
            qdrant_url="http://localhost:6333",
            qdrant_api_key="",
        )
        store = QdrantVectorStore(settings)

        mock_client = _build_mock_client(
            collections=["bsl_code_v4", "pdf_documents_mrl_1024"],
            aliases=[("pdf_documents", "pdf_documents_mrl_1024")],
        )

        with patch("qdrant_client.AsyncQdrantClient", return_value=mock_client):
            await store.initialize()

        mock_client.create_collection.assert_not_awaited()
        assert store._initialized is True
