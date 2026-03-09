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


# ---------------------------------------------------------------------------
# Phase 64: BSL Code Intelligence tools
# ---------------------------------------------------------------------------

_CALL_GRAPH_DB = _FRAMEWORK_ROOT / "cache" / "bsl_call_graph.db"
_call_graph_store = None
_metadata_extractor = None
_hybrid_pipeline = None


def _get_call_graph():
    """Lazy singleton for CallGraphStore."""
    global _call_graph_store
    if _call_graph_store is None:
        from src.bsl.call_graph.store import CallGraphStore
        if not _CALL_GRAPH_DB.exists():
            raise FileNotFoundError(
                f"Call graph DB not found: {_CALL_GRAPH_DB}. "
                "Run: python scripts/build_call_graph.py --project <path>"
            )
        _call_graph_store = CallGraphStore(_CALL_GRAPH_DB)
    return _call_graph_store


def _get_metadata_extractor(project_root: str | None = None):
    """Lazy singleton for MetadataExtractor."""
    global _metadata_extractor
    if _metadata_extractor is None:
        from src.bsl.knowledge_graph.metadata_extractor import MetadataExtractor
        if project_root:
            root = FilePath(project_root)
        else:
            # Auto-detect EDT project under src/projects/configuration/
            config_dir = _FRAMEWORK_ROOT / "src" / "projects" / "configuration"
            root = _FRAMEWORK_ROOT
            if config_dir.is_dir():
                for d in sorted(config_dir.iterdir()):
                    if d.is_dir() and (d / "src").is_dir():
                        root = d
                        break
        _metadata_extractor = MetadataExtractor(root)
    return _metadata_extractor


@mcp.tool()
def bsl_call_graph(
    symbol_name: str,
    direction: str = "both",
    module: str | None = None,
) -> Dict[str, Any]:
    """Query BSL call graph: find callers and/or callees of a symbol.

    Args:
        symbol_name: Name of the procedure/function (e.g. "ПриЗаписи")
        direction: "callers", "callees", or "both"
        module: Optional module path filter for callers query

    Returns:
        Dict with callers and/or callees lists
    """
    store = _get_call_graph()
    result: Dict[str, Any] = {"symbol": symbol_name}

    if direction in ("callers", "both"):
        callers = store.callers_of(symbol_name, module)
        result["callers"] = [
            {
                "name": c["name"],
                "module": c["module_path"],
                "type": c["type"],
                "line": c.get("call_line"),
            }
            for c in callers[:50]
        ]
        result["callers_count"] = len(callers)

    if direction in ("callees", "both"):
        # For callees we need a symbol_id; search by name across modules
        store_conn = store._conn
        cur = store_conn.cursor()
        cur.execute(
            "SELECT id, module_path FROM symbols WHERE name = ? LIMIT 1",
            (symbol_name,),
        )
        row = cur.fetchone()
        if row:
            sid = row["id"]
            callees = store.callees_of(sid)
            result["callees"] = [
                {
                    "name": c["callee_name"],
                    "module": c["callee_module"] or "(local)",
                    "line": c["line_number"],
                    "call_type": c["call_type"],
                }
                for c in callees[:50]
            ]
            result["callees_count"] = len(callees)
            result["resolved_module"] = row["module_path"]
        else:
            result["callees"] = []
            result["callees_count"] = 0
            result["error"] = f"Symbol '{symbol_name}' not found in call graph"

    return result


@mcp.tool()
def bsl_impact_analysis(
    symbol_name: str,
    depth: int = 3,
    module: str | None = None,
) -> Dict[str, Any]:
    """Transitive impact analysis: find all symbols affected by changing a given symbol.

    Uses BFS to traverse the call graph upward (callers of callers).

    Args:
        symbol_name: Name of the procedure/function to analyze
        depth: Maximum traversal depth (default 3)
        module: Optional module path filter

    Returns:
        Dict with affected symbols grouped by depth level
    """
    store = _get_call_graph()
    affected = store.impact_analysis(symbol_name, module, depth=depth)

    by_depth: Dict[int, list] = {}
    for item in affected:
        d = item.get("_depth", 0)
        by_depth.setdefault(d, []).append({
            "name": item["name"],
            "module": item["module_path"],
            "type": item["type"],
        })

    return {
        "symbol": symbol_name,
        "depth": depth,
        "total_affected": len(affected),
        "by_depth": {str(k): v for k, v in sorted(by_depth.items())},
    }


@mcp.tool()
def bsl_dead_code(limit: int = 50) -> Dict[str, Any]:
    """Find exported BSL symbols that are never called anywhere.

    Returns:
        Dict with dead code candidates (exported but unreferenced symbols)
    """
    store = _get_call_graph()
    dead = store.dead_code()

    items = [
        {
            "name": s["name"],
            "module": s["module_path"],
            "type": s["type"],
            "line": s["line_start"],
        }
        for s in dead[:limit]
    ]

    return {
        "total_dead": len(dead),
        "showing": len(items),
        "symbols": items,
    }


@mcp.tool()
def bsl_object_info(
    object_name: str,
    project_root: str | None = None,
) -> Dict[str, Any]:
    """Get 1C Enterprise object metadata from EDT folder structure.

    Args:
        object_name: Name of the 1C object (e.g. "Номенклатура", "ЗаказКлиента")
        project_root: Optional project root path (auto-detected if not set)

    Returns:
        Dict with object type, modules, forms, and related call graph stats
    """
    extractor = _get_metadata_extractor(project_root)
    obj = extractor.get_object_by_name(object_name)

    if obj is None:
        # Try partial match
        all_objects = extractor.extract_objects()
        matches = [
            o for o in all_objects
            if object_name.lower() in o.name.lower()
        ]
        if not matches:
            return {"error": f"Object '{object_name}' not found", "hint": "Use exact object folder name"}
        # Return first partial match
        obj = matches[0]
        if len(matches) > 1:
            return {
                "error": f"Ambiguous name '{object_name}', multiple matches",
                "matches": [{"name": m.name, "type": m.object_type} for m in matches[:10]],
            }

    result: Dict[str, Any] = {
        "name": obj.name,
        "object_type": obj.object_type,
        "path": obj.path,
        "modules": obj.modules,
        "has_forms": obj.has_forms,
        "form_names": obj.form_names,
    }

    # Enrich with call graph stats if available
    try:
        store = _get_call_graph()
        module_paths = extractor.get_object_modules(object_name)
        symbols_count = 0
        exports_count = 0
        for mp in module_paths:
            cur = store._conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM symbols WHERE module_path = ?", (mp,)
            )
            symbols_count += cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM symbols WHERE module_path = ? AND is_export = 1",
                (mp,),
            )
            exports_count += cur.fetchone()[0]
        result["call_graph"] = {
            "symbols": symbols_count,
            "exports": exports_count,
        }
    except Exception:
        result["call_graph"] = None

    return result


def _get_hybrid_pipeline():
    """Lazy singleton for BSLHybridPipeline."""
    global _hybrid_pipeline
    if _hybrid_pipeline is None:
        from .services.hybrid_search import BSLHybridPipeline

        # Qdrant client (optional)
        qdrant = None
        try:
            from qdrant_client import QdrantClient
            qdrant = QdrantClient(host="localhost", port=6333, timeout=10)
            qdrant.get_collections()  # connectivity check
        except Exception:
            qdrant = None

        # E5-large embedder (fast, 1024d) — wraps sentence-transformers
        embedder = None
        if qdrant:
            try:
                from sentence_transformers import SentenceTransformer

                class _E5Embedder:
                    def __init__(self):
                        self._model = SentenceTransformer("intfloat/multilingual-e5-large")
                    def embed_query(self, text: str) -> list[float]:
                        return self._model.encode(f"query: {text}").tolist()

                embedder = _E5Embedder()
            except ImportError:
                pass

        # Call graph (optional)
        cg = None
        try:
            cg = _get_call_graph()
        except Exception:
            pass

        _hybrid_pipeline = BSLHybridPipeline(
            sqlite_db=_SQLITE_DB,
            qdrant_client=qdrant,
            embedder=embedder,
            call_graph=cg,
        )
    return _hybrid_pipeline


@mcp.tool()
def bsl_hybrid_search(
    query: str,
    limit: int = 10,
    fetch_k: int = 50,
) -> Dict[str, Any]:
    """Hybrid BSL code search: BM25 + Vector + RRF fusion + Call Graph boost.

    Combines text search (SQLite FTS5) with semantic search (Qdrant vectors)
    using Reciprocal Rank Fusion, then boosts results by call graph importance.

    Args:
        query: Search query (BSL code pattern, function name, or description)
        limit: Number of results to return (default 10)
        fetch_k: Candidates per stage before fusion (default 50)

    Returns:
        Dict with search results and pipeline metadata
    """
    pipeline = _get_hybrid_pipeline()
    results = pipeline.search(query, limit=limit, fetch_k=fetch_k)

    return {
        "query": query,
        "total": len(results),
        "results": [
            {
                "name": r.name,
                "module_path": r.module_path,
                "score": round(r.score, 6),
                "source": r.source,
                "content": r.content[:300],
                "object_type": r.metadata.get("object_type", ""),
                "object_name": r.metadata.get("object_name", ""),
                "caller_count": r.metadata.get("caller_count", 0),
                "is_export": r.metadata.get("is_export", False),
            }
            for r in results
        ],
    }


@mcp.tool()
def bsl_coding_context(
    object_name: str,
    task_description: str = "",
    include_style: bool = True,
    similar_limit: int = 3,
) -> Dict[str, Any]:
    """Get full coding context for writing BSL code for a 1C object.

    Aggregates: object metadata, module structure, similar code,
    dependencies, and code style rules — everything needed for
    informed BSL code generation.

    Args:
        object_name: 1C object name (e.g. "Номенклатура")
        task_description: What code to write (used for similar code search)
        include_style: Include code style analysis (default True)
        similar_limit: Number of similar code results (default 3)

    Returns:
        Dict with object info, modules, dependencies, style rules, similar code
    """
    result: Dict[str, Any] = {"object_name": object_name}

    # 1. Object metadata
    try:
        extractor = _get_metadata_extractor()
        obj = extractor.get_object_by_name(object_name)
        if obj:
            result["object"] = {
                "type": obj.object_type,
                "path": obj.path,
                "modules": obj.modules,
                "has_forms": obj.has_forms,
                "form_names": obj.form_names,
            }
        else:
            result["object"] = {"error": f"Object '{object_name}' not found"}
    except Exception as e:
        result["object"] = {"error": str(e)}

    # 2. Call graph dependencies
    try:
        store = _get_call_graph()
        extractor = _get_metadata_extractor()
        module_paths = extractor.get_object_modules(object_name)
        exports = []
        deps = set()
        for mp in module_paths:
            cur = store._conn.cursor()
            cur.execute(
                "SELECT name, type FROM symbols WHERE module_path = ? AND is_export = 1",
                (mp,),
            )
            for row in cur.fetchall():
                exports.append({"name": row["name"], "type": row["type"]})
            # Cross-module dependencies
            cur.execute(
                "SELECT DISTINCT c.callee_module FROM calls c "
                "JOIN symbols s ON c.caller_id = s.id "
                "WHERE s.module_path = ? AND c.callee_module IS NOT NULL AND c.callee_module != ''",
                (mp,),
            )
            for row in cur.fetchall():
                deps.add(row["callee_module"])
        result["exports"] = exports
        result["dependencies"] = sorted(deps)
    except Exception:
        result["exports"] = []
        result["dependencies"] = []

    # 3. Similar code (via hybrid search)
    if task_description:
        try:
            pipeline = _get_hybrid_pipeline()
            similar = pipeline.search(task_description, limit=similar_limit)
            result["similar_code"] = [
                {
                    "name": r.name,
                    "module": r.module_path,
                    "content": r.content[:400],
                    "score": round(r.score, 6),
                }
                for r in similar
            ]
        except Exception:
            result["similar_code"] = []
    else:
        result["similar_code"] = []

    # 4. Code style
    if include_style:
        try:
            from src.bsl.coding_assistant.style_extractor import BSLStyleExtractor
            from src.bsl.parser import BSLASTParser

            parser = BSLASTParser()
            extractor = _get_metadata_extractor()
            module_paths = extractor.get_object_modules(object_name)

            parsed = []
            for mp in module_paths[:10]:
                try:
                    parsed.append(parser.parse_file(mp))
                except Exception:
                    pass

            if parsed:
                style_ext = BSLStyleExtractor()
                profile = style_ext.analyze(parsed)
                result["style"] = profile.to_dict()
                result["style_prompt"] = profile.to_prompt()
            else:
                result["style"] = None
        except Exception:
            result["style"] = None

    return result


if __name__ == "__main__":
    logger.info("=== Starting BSL Semantic Search MCP Server ===")
    mcp.run()
