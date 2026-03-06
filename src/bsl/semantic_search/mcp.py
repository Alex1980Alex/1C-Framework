"""
BSL Semantic Search MCP Server - Entry Point

FastMCP сервер для семантического поиска по BSL коду

Запуск: python -m src.bsl.semantic_search.mcp

Phase 45: Миграция из 1C-Enterprise_Framework
"""

import asyncio
import logging
import sys
import os
from typing import List, Dict, Any

# Добавляем родительские директории в путь для импортов
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Импорты MCP (FastMCP)
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    logger.error("FastMCP не установлен. Установите: pip install mcp[cli]")
    sys.exit(1)

# Импорты сервисов
from .services.search import BSLSearchService, SearchRequest, SearchMode
from .services.embedding import EmbeddingService
from .config import get_bsl_settings

# Создаем FastMCP server
mcp = FastMCP("BSL Semantic Search")

# Глобальные сервисы (ленивая инициализация)
_services_initialized = False
search_service = None
embedding_service = None


async def ensure_services():
    """Ленивая инициализация всех сервисов"""
    global _services_initialized, search_service, embedding_service

    if _services_initialized:
        return

    logger.info("=== Инициализация BSL Semantic Search сервисов ===")

    settings = get_bsl_settings()

    # Embedding Service
    embedding_service = EmbeddingService(
        ollama_host=settings.ollama_host,
        model=settings.embedding_model
    )
    logger.info("✓ Embedding Service")

    # BSL Search Service (пока без Neo4j и LLM)
    search_service = BSLSearchService(
        qdrant_service=None,  # Будет инициализирован лениво
        neo4j_service=None,
        hybrid_engine=None,
        llm_service=None
    )
    logger.info("✓ BSL Search Service")

    _services_initialized = True
    logger.info("=== Все сервисы инициализированы ===")


# ================================================================
# Tool 1: bsl_search - Семантический поиск по BSL коду
# ================================================================
@mcp.tool()
async def bsl_search(
    query: str,
    limit: int = 10,
    mode: str = "semantic"
) -> str:
    """
    Семантический поиск по BSL коду

    Args:
        query: Поисковый запрос (на русском или английском)
        limit: Максимальное количество результатов (по умолчанию 10)
        mode: Режим поиска (semantic, graph, hybrid, intelligent)

    Returns:
        Список найденных модулей с метаданными и релевантностью
    """
    await ensure_services()

    logger.info(f"bsl_search: query='{query}', limit={limit}, mode={mode}")

    try:
        # Маппинг режима поиска
        mode_map = {
            "semantic": SearchMode.SEMANTIC_ONLY,
            "graph": SearchMode.GRAPH_ONLY,
            "hybrid": SearchMode.HYBRID,
            "intelligent": SearchMode.INTELLIGENT,
            "multi_stage": SearchMode.MULTI_STAGE
        }

        # Создаем запрос
        request = SearchRequest(
            query=query,
            mode=mode_map.get(mode, SearchMode.SEMANTIC_ONLY),
            limit=min(limit, 50)
        )

        # Выполняем поиск
        results = await search_service.search(request)

        # Форматируем результаты
        if not results:
            return f"Результаты не найдены для запроса: '{query}'"

        formatted = []
        for i, result in enumerate(results, 1):
            formatted.append(f"""### Результат {i} (релевантность: {result.score:.3f})

**Файл**: {result.file_path}
**Тип модуля**: {result.module_type}
**Источник**: {result.source}
**Функций**: {result.functions_count}

**Описание**:
{result.summary[:500]}{'...' if len(result.summary) > 500 else ''}

{"**LLM анализ**: " + result.reasoning if result.reranked and result.reasoning else ""}
""")

        return f"""## Результаты поиска BSL

**Запрос**: {query}
**Режим**: {mode}
**Найдено**: {len(results)} модулей

{chr(10).join(formatted)}"""

    except Exception as e:
        logger.error(f"Ошибка в bsl_search: {e}", exc_info=True)
        return f"Ошибка при поиске: {str(e)}"


# ================================================================
# Tool 2: bsl_similar - Поиск похожих модулей
# ================================================================
@mcp.tool()
async def bsl_similar(
    file_path: str,
    limit: int = 5
) -> str:
    """
    Поиск модулей, похожих на указанный

    Args:
        file_path: Путь к файлу-образцу
        limit: Количество похожих модулей

    Returns:
        Список похожих модулей с оценкой схожести
    """
    await ensure_services()

    logger.info(f"bsl_similar: file='{file_path}', limit={limit}")

    try:
        # TODO: Реализовать через vector search по существующему embedding
        return f"""## Похожие модули для {file_path}

Функционал в разработке. Используйте bsl_search для семантического поиска.
"""

    except Exception as e:
        logger.error(f"Ошибка в bsl_similar: {e}", exc_info=True)
        return f"Ошибка при поиске похожих: {str(e)}"


# ================================================================
# Tool 3: bsl_context - Контекст модуля
# ================================================================
@mcp.tool()
async def bsl_context(
    file_path: str,
    include_dependencies: bool = True
) -> str:
    """
    Получение контекста модуля: зависимости, функции, метаданные

    Args:
        file_path: Путь к файлу модуля
        include_dependencies: Включить информацию о зависимостях

    Returns:
        Детальный контекст модуля
    """
    await ensure_services()

    logger.info(f"bsl_context: file='{file_path}'")

    try:
        # TODO: Реализовать через Qdrant + Neo4j
        return f"""## Контекст модуля: {file_path}

Функционал в разработке. Используйте bsl_search для получения информации о модуле.
"""

    except Exception as e:
        logger.error(f"Ошибка в bsl_context: {e}", exc_info=True)
        return f"Ошибка при получении контекста: {str(e)}"


# ================================================================
# Tool 4: bsl_stats - Статистика индекса
# ================================================================
@mcp.tool()
async def bsl_stats() -> str:
    """
    Статистика BSL индекса: количество модулей, распределение по типам

    Returns:
        Статистика индекса
    """
    await ensure_services()

    logger.info("bsl_stats: запрос статистики")

    try:
        settings = get_bsl_settings()

        # Попытка подключения к Qdrant
        try:
            from qdrant_client import QdrantClient

            client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port
            )

            collection_info = client.get_collection(settings.collection_name)

            return f"""## Статистика BSL индекса

**Коллекция**: {settings.collection_name}
**Векторная размерность**: {settings.embedding_dim}
**Модель embeddings**: {settings.embedding_model}

**Количество точек**: {collection_info.points_count}
**Статус**: {collection_info.status}

**Qdrant**: {settings.qdrant_host}:{settings.qdrant_port}
**Ollama**: {settings.ollama_host}
"""

        except ImportError:
            return "qdrant-client не установлен"
        except Exception as e:
            return f"Ошибка подключения к Qdrant: {e}"

    except Exception as e:
        logger.error(f"Ошибка в bsl_stats: {e}", exc_info=True)
        return f"Ошибка при получении статистики: {str(e)}"


if __name__ == "__main__":
    logger.info("=== Starting BSL Semantic Search MCP Server ===")
    mcp.run()
