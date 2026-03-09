"""
BSL Semantic Search MCP Server - Entry Point

FastMCP сервер для семантического поиска по BSL коду.
SQLite FTS5 fallback когда Qdrant недоступен.

Запуск: python -m src.bsl.semantic_search.mcp

Phase 45: Миграция из 1C-Enterprise_Framework
"""

import asyncio
import logging
import sqlite3
import sys
import os
from pathlib import Path as FilePath
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
_qdrant_available = False

# Auto-detect framework root and SQLite DB path
_FRAMEWORK_ROOT = FilePath(__file__).resolve().parent.parent.parent.parent
_SQLITE_DB = _FRAMEWORK_ROOT / "cache" / "docs-mcp" / "hybrid_search.db"


def _check_qdrant() -> bool:
    """Быстрая проверка доступности Qdrant (таймаут 2с)"""
    try:
        from qdrant_client import QdrantClient as QC
        settings = get_bsl_settings()
        client = QC(host=settings.qdrant_host, port=settings.qdrant_port, timeout=2)
        client.get_collections()
        return True
    except Exception:
        return False


def _get_sqlite_conn():
    """Подключение к SQLite FTS базе (hybrid_search.db)"""
    if not _SQLITE_DB.exists():
        raise FileNotFoundError(f"SQLite DB не найдена: {_SQLITE_DB}")
    conn = sqlite3.connect(str(_SQLITE_DB))
    conn.row_factory = sqlite3.Row
    return conn


async def ensure_services():
    """Ленивая инициализация всех сервисов"""
    global _services_initialized, search_service, embedding_service, _qdrant_available

    if _services_initialized:
        return

    logger.info("=== Инициализация BSL Semantic Search сервисов ===")

    settings = get_bsl_settings()

    # Проверяем Qdrant
    _qdrant_available = _check_qdrant()
    if _qdrant_available:
        logger.info("Qdrant ДОСТУПЕН")
    else:
        logger.warning("Qdrant НЕДОСТУПЕН - используем SQLite FTS5 fallback")
        if _SQLITE_DB.exists():
            logger.info(f"SQLite DB: {_SQLITE_DB} ({_SQLITE_DB.stat().st_size // 1024 // 1024} MB)")
        else:
            logger.warning(f"SQLite DB не найдена. Запустите: scripts/index-folder.bat")

    # Embedding Service
    embedding_service = EmbeddingService(
        ollama_host=settings.ollama_host,
        model=settings.embedding_model
    )
    logger.info("Embedding Service OK")

    # BSL Search Service
    search_service = BSLSearchService(
        qdrant_service=None,
        neo4j_service=None,
        hybrid_engine=None,
        llm_service=None
    )
    logger.info("BSL Search Service OK")

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

        # Выполняем поиск (Qdrant или SQLite fallback)
        results = await search_service.search(request)

        # SQLite FTS5 fallback если Qdrant не дал результатов
        if not results and not _qdrant_available:
            try:
                results = await _sqlite_fts_search(query, limit)
            except Exception as e:
                logger.warning(f"SQLite fallback search failed: {e}")

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
        # SQLite fallback для контекста модуля
        if not _qdrant_available and _SQLITE_DB.exists():
            try:
                conn = _get_sqlite_conn()
                try:
                    cur = conn.cursor()
                    like_path = f"%{file_path.replace(chr(92), '/')}%"
                    cur.execute(
                        """SELECT path, doc_type, content, content_preview
                           FROM documents WHERE path LIKE ? LIMIT 1""",
                        (like_path,)
                    )
                    row = cur.fetchone()
                finally:
                    conn.close()

                if row:
                    content_preview = (row["content"] or "")[:2000]
                    return f"""## Контекст модуля: {row['path']}

**Тип**: {row['doc_type']}
**Источник**: SQLite FTS5

**Содержимое** (первые 2000 символов):

{content_preview}
"""
            except Exception as e:
                logger.warning(f"SQLite context failed: {e}")

        return f"""## Контекст модуля: {file_path}

Модуль не найден в индексе. Запустите индексацию: scripts/index-folder.bat
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
        if _qdrant_available:
            try:
                from qdrant_client import QdrantClient as QC
                client = QC(host=settings.qdrant_host, port=settings.qdrant_port, timeout=5)
                collection_info = client.get_collection(settings.collection_name)

                return f"""## Статистика BSL индекса (Qdrant)

**Коллекция**: {settings.collection_name}
**Векторная размерность**: {settings.embedding_dim}
**Модель embeddings**: {settings.embedding_model}

**Количество точек**: {collection_info.points_count}
**Статус**: {collection_info.status}

**Qdrant**: {settings.qdrant_host}:{settings.qdrant_port}
**Ollama**: {settings.ollama_host}
"""
            except Exception as e:
                logger.warning(f"Qdrant stats failed, trying SQLite: {e}")

        # SQLite FTS5 fallback
        try:
            conn = _get_sqlite_conn()
            try:
                cur = conn.cursor()

                cur.execute("SELECT COUNT(*) FROM documents")
                total_docs = cur.fetchone()[0]

                cur.execute("SELECT doc_type, COUNT(*) as cnt FROM documents GROUP BY doc_type ORDER BY cnt DESC")
                type_rows = cur.fetchall()

                db_size_mb = _SQLITE_DB.stat().st_size / 1024 / 1024

                type_stats = chr(10).join([f"  - {r['doc_type']}: {r['cnt']}" for r in type_rows])
            finally:
                conn.close()

            return f"""## Статистика BSL индекса (SQLite FTS5)

**База данных**: {_SQLITE_DB.name} ({db_size_mb:.1f} MB)
**Всего документов**: {total_docs}
**Бэкенд**: SQLite FTS5 (Qdrant недоступен)

**По типам**:
{type_stats}

**Ollama**: {settings.ollama_host}
**Модель embeddings**: {settings.embedding_model}
"""
        except FileNotFoundError:
            return "Индекс не найден. Запустите: scripts/index-folder.bat"
        except Exception as e:
            return f"Ошибка SQLite: {e}"

    except Exception as e:
        logger.error(f"Ошибка в bsl_stats: {e}", exc_info=True)
        return f"Ошибка при получении статистики: {str(e)}"


# ================================================================
# SQLite FTS5 fallback search
# ================================================================
async def _sqlite_fts_search(query: str, limit: int = 10):
    """Поиск через SQLite FTS5 когда Qdrant недоступен"""
    from .services.search import SearchResult

    conn = _get_sqlite_conn()
    try:
        cur = conn.cursor()

        # FTS5 поиск
        try:
            cur.execute(
                """SELECT d.id, d.path, d.doc_type, d.content, d.content_preview
                   FROM documents d
                   WHERE d.id IN (
                       SELECT id FROM documents_fts WHERE documents_fts MATCH ?
                   )
                   LIMIT ?""",
                (query, limit * 3)
            )
        except Exception:
            # Fallback: простой LIKE поиск
            like_q = f"%{query}%"
            cur.execute(
                """SELECT d.id, d.path, d.doc_type, d.content, d.content_preview
                   FROM documents d
                   WHERE d.content LIKE ? OR d.path LIKE ?
                   LIMIT ?""",
                (like_q, like_q, limit * 3)
            )

        rows = cur.fetchall()
    finally:
        conn.close()

    # Группируем по path и формируем результаты
    seen_paths = set()
    results = []
    for row in rows:
        fp = row["path"] or ""
        if fp in seen_paths:
            continue
        seen_paths.add(fp)

        summary = (row["content_preview"] or row["content"] or "")[:500]
        results.append(SearchResult(
            file_path=fp,
            module_type=row["doc_type"] or "bsl",
            score=0.8,
            original_score=0.8,
            summary=summary,
            functions_count=0,
            source="sqlite_fts5",
        ))

        if len(results) >= limit:
            break

    return results


if __name__ == "__main__":
    logger.info("=== Starting BSL Semantic Search MCP Server ===")
    mcp.run()
