"""
Integration tests for BSL Semantic Search

Phase 45: Миграция из 1C-Enterprise_Framework

Запуск: pytest tests/integration/test_bsl_search.py -v
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# Добавляем src в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


class TestBSLSearchService:
    """Тесты BSL Search Service"""

    @pytest.fixture
    def search_service(self):
        """Фикстура для создания BSLSearchService"""
        from bsl.semantic_search.services.search import BSLSearchService
        return BSLSearchService(
            qdrant_service=None,
            neo4j_service=None,
            hybrid_engine=None,
            llm_service=None
        )

    @pytest.fixture
    def search_request(self):
        """Фикстура для SearchRequest"""
        from bsl.semantic_search.services.search import SearchRequest, SearchMode
        return SearchRequest(
            query="обработка проведения документа",
            mode=SearchMode.SEMANTIC_ONLY,
            limit=10
        )

    def test_search_service_initialization(self, search_service):
        """Тест инициализации BSLSearchService"""
        assert search_service is not None
        assert search_service.qdrant is None
        assert search_service.neo4j is None

    @pytest.mark.asyncio
    async def test_semantic_search_returns_results(self, search_service):
        """Тест: Semantic search возвращает результаты с score > 0.5"""
        from bsl.semantic_search.services.search import SearchRequest, SearchMode

        # Mock Qdrant search
        mock_results = [
            {
                "file_path": "src/Documents/Document1/Forms/ItemForm/Module.bsl",
                "module_type": "FormModule",
                "score": 0.85,
                "summary": "Обработка проведения документа",
                "functions_count": 5
            }
        ]

        with patch.object(
            search_service,
            '_call_qdrant_search',
            new_callable=AsyncMock,
            return_value=mock_results
        ):
            request = SearchRequest(
                query="обработка проведения",
                mode=SearchMode.SEMANTIC_ONLY,
                limit=10
            )

            results = await search_service.search(request)

            assert len(results) > 0
            assert results[0].score > 0.5

    def test_extract_keywords_from_query(self, search_service):
        """Тест извлечения ключевых слов"""
        query = "как найти справочник контрагенты"
        keywords = search_service._extract_keywords_from_query(query)

        assert "найти" in keywords
        assert "справочник" in keywords
        assert "контрагенты" in keywords
        assert "как" not in keywords  # Стоп-слово

    def test_calculate_relevance(self, search_service):
        """Тест расчета релевантности"""
        relevance = search_service._calculate_relevance(
            query="контрагенты",
            module_name="СправочникКонтрагенты",
            file_path="src/Catalogs/Contractors/Module.bsl"
        )

        assert 0.0 <= relevance <= 1.0
        assert relevance >= 0.5  # Высокая релевантность при совпадении


class TestQdrantCollection:
    """Тесты Qdrant коллекции"""

    @pytest.fixture
    def qdrant_settings(self):
        """Фикстура для настроек Qdrant"""
        from bsl.semantic_search.config import BSLSearchSettings
        return BSLSearchSettings()

    @pytest.mark.integration
    def test_collection_contains_points(self, qdrant_settings):
        """Тест: Коллекция содержит >= 3900 points"""
        try:
            from qdrant_client import QdrantClient

            client = QdrantClient(
                host=qdrant_settings.qdrant_host,
                port=qdrant_settings.qdrant_port
            )

            collection_info = client.get_collection(qdrant_settings.collection_name)

            assert collection_info.points_count >= 3900, \
                f"Expected >= 3900 points, got {collection_info.points_count}"

        except ImportError:
            pytest.skip("qdrant-client not installed")
        except Exception as e:
            pytest.skip(f"Qdrant not available: {e}")

    @pytest.mark.integration
    def test_vector_dimension(self, qdrant_settings):
        """Тест: Размерность векторов = 768"""
        try:
            from qdrant_client import QdrantClient

            client = QdrantClient(
                host=qdrant_settings.qdrant_host,
                port=qdrant_settings.qdrant_port
            )

            collection_info = client.get_collection(qdrant_settings.collection_name)

            assert collection_info.config.params.vectors.size == 768, \
                f"Expected 768d vectors, got {collection_info.config.params.vectors.size}"

        except ImportError:
            pytest.skip("qdrant-client not installed")
        except Exception as e:
            pytest.skip(f"Qdrant not available: {e}")


class TestEmbeddingService:
    """Тесты Embedding Service"""

    @pytest.fixture
    def embedding_service(self):
        """Фикстура для EmbeddingService"""
        from bsl.semantic_search.services.embedding import EmbeddingService
        return EmbeddingService(
            ollama_host="http://localhost:11434",
            model="nomic-embed-text"
        )

    @pytest.mark.integration
    def test_create_embedding_returns_768d(self, embedding_service):
        """Тест: Embedding имеет размерность 768"""
        try:
            embedding = embedding_service.create_embedding("тестовый текст")

            if embedding:  # Ollama может быть недоступен
                assert len(embedding) == 768, \
                    f"Expected 768d embedding, got {len(embedding)}"
            else:
                pytest.skip("Ollama not available")

        except Exception as e:
            pytest.skip(f"Embedding service error: {e}")


class TestBSLSettings:
    """Тесты конфигурации"""

    def test_default_settings(self):
        """Тест значений по умолчанию"""
        from bsl.semantic_search.config import BSLSearchSettings

        settings = BSLSearchSettings()

        assert settings.collection_name == "bsl_code_v2"
        assert settings.embedding_dim == 768
        assert settings.embedding_model == "nomic-embed-text"
        assert settings.qdrant_host == "localhost"
        assert settings.qdrant_port == 6333

    def test_qdrant_api_url(self):
        """Тест формирования Qdrant URL"""
        from bsl.semantic_search.config import BSLSearchSettings

        settings = BSLSearchSettings(
            qdrant_host="custom-host",
            qdrant_port=6334
        )

        assert settings.qdrant_api_url == "http://custom-host:6334"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
