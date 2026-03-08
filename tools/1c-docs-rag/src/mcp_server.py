#!/usr/bin/env python3
"""
MCP сервер для гибридного поиска по документации фреймворка 1C
Интеграция с Claude Code через Model Context Protocol

ВАЖНО: MCP использует stdout для JSON-RPC. ВСЕ логи должны идти в stderr!
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

def log_stderr(*args, **kwargs):
    """Логирование в stderr (НЕ в stdout - там MCP протокол!)"""
    print(*args, file=sys.stderr, **kwargs)

# Добавляем текущую директорию в путь для импорта
sys.path.append(str(Path(__file__).parent))

try:
    from mcp.server import Server
    from mcp.types import Resource, Tool, TextContent, ImageContent, EmbeddedResource
    from hybrid_search_engine import HybridSearchEngine, SearchResult, DocsFileWatcher, WATCHDOG_AVAILABLE
    from rag_module import RAGModule, RAGResponse
    MCP_AVAILABLE = True
    RAG_AVAILABLE = True
except ImportError as e:
    MCP_AVAILABLE = False
    RAG_AVAILABLE = False
    WATCHDOG_AVAILABLE = False
    log_stderr(f"[ERROR] Импорт не удался: {e}. Установите: pip install mcp aiohttp")

class FrameworkDocsMCPServer:
    """MCP сервер для документации фреймворка"""
    
    def __init__(self):
        """Инициализация сервера"""
        self.search_engine = HybridSearchEngine()
        self.server = Server("1c-framework-docs") if MCP_AVAILABLE else None
        self.rag_module = RAGModule(self.search_engine) if RAG_AVAILABLE else None
        
        # Получаем пути к документации из переменной окружения (поддержка множественных путей через ';')
        docs_root = os.getenv('DOCS_ROOT')
        if docs_root:
            # Поддержка множественных путей, разделённых ';' или '|'
            separator = ';' if ';' in docs_root else '|'
            self.docs_paths = [Path(p.strip()) for p in docs_root.split(separator)]
        else:
            # Абсолютный путь к документации (singular для обратной совместимости)
            self.docs_paths = [Path("D:/1С-Framework/docs")]
        
        # Для обратной совместимости - первый путь как основной
        self.docs_path = self.docs_paths[0]

        # Файловый наблюдатель для автоматической индексации
        self.file_watchers = []  # Список наблюдателей для всех путей

        if MCP_AVAILABLE:
            self._setup_handlers()
    
    def _setup_handlers(self):
        """Настройка обработчиков MCP"""
        if not self.server:
            return
        
        # Список доступных инструментов
        @self.server.list_tools()
        async def list_tools() -> List[Tool]:
            """Список доступных инструментов поиска"""
            return [
                Tool(
                    name="search_docs",
                    description="Поиск по документации фреймворка 1C. Поддерживает полнотекстовый, семантический и гибридный поиск.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Поисковый запрос на русском или английском языке"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Максимальное количество результатов (по умолчанию: 5)",
                                "default": 5,
                                "minimum": 1,
                                "maximum": 20
                            },
                            "search_type": {
                                "type": "string",
                                "description": "Тип поиска: fulltext, semantic, hybrid",
                                "enum": ["fulltext", "semantic", "hybrid"],
                                "default": "hybrid"
                            },
                            "source": {
                                "type": "string",
                                "description": "Фильтр по источнику (путь к документации). По умолчанию ищет во всех источниках."
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="get_document",
                    description="Получить полное содержимое документа по ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "document_id": {
                                "type": "string",
                                "description": "ID документа для получения"
                            }
                        },
                        "required": ["document_id"]
                    }
                ),
                Tool(
                    name="reindex_docs",
                    description="Переиндексация всей документации фреймворка",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "force": {
                                "type": "boolean",
                                "description": "Принудительная переиндексация всех документов",
                                "default": False
                            }
                        }
                    }
                ),
                Tool(
                    name="get_stats",
                    description="Получить статистику поискового индекса",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="ask_docs",
                    description="Задать вопрос по документации с генерацией ответа (RAG). Использует LLM для формирования ответа на основе найденных документов.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "Вопрос по документации фреймворка 1C"
                            },
                            "use_cache": {
                                "type": "boolean",
                                "description": "Использовать кеш ответов (по умолчанию: true)",
                                "default": True
                            },
                            "top_k": {
                                "type": "integer",
                                "description": "Количество документов для контекста (по умолчанию: 5)",
                                "default": 5,
                                "minimum": 1,
                                "maximum": 10
                            },
                            "source": {
                                "type": "string",
                                "description": "Фильтр по источнику (путь к документации). По умолчанию ищет во всех источниках."
                            }
                        },
                        "required": ["question"]
                    }
                ),
                Tool(
                    name="clear_rag_cache",
                    description="Очистить кеш RAG ответов",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="validate_solution",
                    description="Валидация решения Claude против документации фреймворка. Проверяет соответствие стандартам и лучшим практикам 1C:Enterprise.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "solution": {
                                "type": "string",
                                "description": "Описание решения или код для валидации"
                            },
                            "context": {
                                "type": "string",
                                "description": "Контекст задачи (опционально)"
                            },
                            "check_type": {
                                "type": "string",
                                "description": "Тип проверки: standards, security, performance, best_practices, all",
                                "enum": ["standards", "security", "performance", "best_practices", "all"],
                                "default": "all"
                            }
                        },
                        "required": ["solution"]
                    }
                ),
                Tool(
                    name="get_watcher_status",
                    description="Получить статус файлового наблюдателя (автоиндексация). Показывает информацию о мониторинге папок документации.",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="index_incremental",
                    description="Инкрементальная индексация документации. Индексирует только новые, изменённые и удалённые файлы без полной переиндексации.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "docs_path": {
                                "type": "string",
                                "description": "Путь к директории для индексации (опционально, по умолчанию DOCS_ROOT)"
                            }
                        }
                    }
                ),
                Tool(
                    name="search_docs_with_facets",
                    description="Поиск по документации с фасетной фильтрацией. Позволяет фильтровать результаты по типу документа, тегам, дате и источнику.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Поисковый запрос на русском или английском языке"
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Максимальное количество результатов (по умолчанию: 10)",
                                "default": 10,
                                "minimum": 1,
                                "maximum": 50
                            },
                            "search_type": {
                                "type": "string",
                                "description": "Тип поиска: fulltext, semantic, hybrid",
                                "enum": ["fulltext", "semantic", "hybrid"],
                                "default": "hybrid"
                            },
                            "doc_type": {
                                "type": "string",
                                "description": "Фильтр по типу документа (markdown, bsl, xml)"
                            },
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Фильтр по тегам (OR логика - хоть один тег совпал)"
                            },
                            "date_after": {
                                "type": "string",
                                "description": "Фильтр по дате (ISO format, например \"2025-01-01\") - документы после этой даты"
                            },
                            "date_before": {
                                "type": "string",
                                "description": "Фильтр по дате (ISO format) - документы до этой даты"
                            },
                            "source": {
                                "type": "string",
                                "description": "Фильтр по источнику (часть пути, например \"claude\", \"framework\")"
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="get_available_facets",
                    description="Получить доступные значения фасетов для фильтрации. Возвращает типы документов, теги, источники и диапазон дат.",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="index_bsl_project",
                    description="Индексация BSL файлов конфигурации 1С для семантического поиска. Поддерживает EDT формат проектов.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_path": {
                                "type": "string",
                                "description": "Путь к проекту 1С (директория с src/). Если не указан, используется активный проект Serena."
                            },
                            "chunk_mode": {
                                "type": "string",
                                "description": "Режим индексации: 'full' (весь файл), 'procedures' (по процедурам), 'smart' (структурированный анализ + API). Рекомендуется 'smart'.",
                                "enum": ["full", "procedures", "smart"],
                                "default": "smart"
                            },
                            "force": {
                                "type": "boolean",
                                "description": "Принудительная переиндексация (даже если файлы не изменились)",
                                "default": False
                            }
                        },
                        "required": []
                    }
                ),
                Tool(
                    name="index_xml_project",
                    description="Индексация XML файлов конфигурации 1С (формы, подсистемы, права, языки) для семантического поиска. Поддерживает EDT формат.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "project_path": {
                                "type": "string",
                                "description": "Путь к проекту 1С (директория src/). Обязательный параметр."
                            },
                            "xml_types": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Типы XML для индексации: 'subsystems', 'forms', 'rights', 'languages', 'command_interface', 'metadata'. По умолчанию: ['subsystems', 'forms', 'languages']"
                            }
                        },
                        "required": ["project_path"]
                    }
                ),
                Tool(
                    name="delete_by_source",
                    description="Удаление всех документов из индекса по пути источника (проекта). Используется для очистки индекса при удалении проекта.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "source_path": {
                                "type": "string",
                                "description": "Путь к папке проекта для удаления из индекса"
                            }
                        },
                        "required": ["source_path"]
                    }
                ),
                Tool(
                    name="get_indexed_projects",
                    description="Получение списка всех проиндексированных проектов с информацией о количестве документов и типах.",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                )
            ]
        
        # Обработчик поиска документов
        @self.server.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
            """Обработка вызовов инструментов"""
            
            if name == "search_docs":
                return await self._handle_search(arguments)
            elif name == "get_document":
                return await self._handle_get_document(arguments)
            elif name == "reindex_docs":
                return await self._handle_reindex(arguments)
            elif name == "get_stats":
                return await self._handle_get_stats(arguments)
            elif name == "ask_docs":
                return await self._handle_ask_docs(arguments)
            elif name == "clear_rag_cache":
                return await self._handle_clear_rag_cache(arguments)
            elif name == "validate_solution":
                return await self._handle_validate_solution(arguments)
            elif name == "get_watcher_status":
                return await self._handle_get_watcher_status(arguments)
            elif name == "index_incremental":
                return await self._handle_index_incremental(arguments)
            elif name == "search_docs_with_facets":
                return await self._handle_search_with_facets(arguments)
            elif name == "get_available_facets":
                return await self._handle_get_available_facets(arguments)
            elif name == "index_bsl_project":
                return await self._handle_index_bsl_project(arguments)
            elif name == "index_xml_project":
                return await self._handle_index_xml_project(arguments)
            elif name == "delete_by_source":
                return await self._handle_delete_by_source(arguments)
            elif name == "get_indexed_projects":
                return await self._handle_get_indexed_projects(arguments)
            else:
                return [TextContent(
                    type="text",
                    text=f"[ERROR] Неизвестный инструмент: {name}"
                )]
    
    async def _handle_search(self, args: Dict[str, Any]) -> List[TextContent]:
        """Обработка поиска по документации"""
        query = args.get("query", "")
        limit = args.get("limit", 5)
        search_type = args.get("search_type", "hybrid")
        source = args.get("source", "")
        
        if not query.strip():
            return [TextContent(
                type="text",
                text="[ERROR] Пустой поисковый запрос"
            )]
        
        try:
            # Выполняем поиск
            results = self.search_engine.search(query, limit=limit, search_type=search_type)
            
            # Фильтрация по источнику если указан
            if source:
                results = [r for r in results if source.lower() in r.document.path.lower()]
            
            if not results:
                return [TextContent(
                    type="text",
                    text=f"[SEARCH] По запросу '{query}' ничего не найдено." + 
                           (f" (фильтр: {source})" if source else "")
                )]
            
            # Форматируем результаты
            response_text = f"[SEARCH] **Результаты поиска по запросу:** '{query}'\n"
            response_text += f"[STATS] **Тип поиска:** {search_type}\n"
            response_text += f"[LIST] **Найдено:** {len(results)} результат(ов)\n\n"
            
            for i, result in enumerate(results, 1):
                doc = result.document
                score = result.score
                match_type = result.match_type
                snippet = result.snippet
                
                response_text += f"## {i}. {doc.title}\n"
                response_text += f"**[FOLDER] Файл:** `{Path(doc.path).name}`\n"
                response_text += f"**[TARGET] Релевантность:** {score:.3f} ({match_type})\n"
                response_text += f"**📏 Размер:** {doc.size} символов\n"
                response_text += f"**🏷️ Теги:** {', '.join(doc.tags) if doc.tags else 'нет'}\n"
                response_text += f"**[NOTE] Фрагмент:**\n```\n{snippet}\n```\n"
                response_text += f"**🆔 ID:** `{doc.id}`\n\n"
                response_text += "---\n\n"
            
            response_text += f"[INFO] **Совет:** Используйте `get_document` с ID для получения полного содержимого.\n"
            
            return [TextContent(type="text", text=response_text)]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"[ERROR] Ошибка поиска: {str(e)}"
            )]
    
    async def _handle_get_document(self, args: Dict[str, Any]) -> List[TextContent]:
        """Получение полного содержимого документа"""
        document_id = args.get("document_id", "")
        
        if not document_id:
            return [TextContent(
                type="text",
                text="[ERROR] Не указан ID документа"
            )]
        
        try:
            # Поиск документа по ID
            import sqlite3
            conn = sqlite3.connect(self.search_engine.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT title, path, content, size, modified, tags, doc_type
                FROM documents 
                WHERE id = ?
            """, (document_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if not result:
                return [TextContent(
                    type="text",
                    text=f"[ERROR] Документ с ID '{document_id}' не найден"
                )]
            
            title, path, content, size, modified, tags, doc_type = result
            tags_list = json.loads(tags) if tags else []
            
            response_text = f"# [FILE] {title}\n\n"
            response_text += f"**[FOLDER] Путь:** `{path}`\n"
            response_text += f"**📏 Размер:** {size} символов\n"
            response_text += f"**📅 Изменен:** {modified}\n"
            response_text += f"**🏷️ Теги:** {', '.join(tags_list) if tags_list else 'нет'}\n"
            response_text += f"**[LIST] Тип:** {doc_type}\n\n"
            response_text += "---\n\n"
            response_text += "## 📖 Содержимое\n\n"
            response_text += content
            
            return [TextContent(type="text", text=response_text)]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"[ERROR] Ошибка получения документа: {str(e)}"
            )]
    
    async def _handle_reindex(self, args: Dict[str, Any]) -> List[TextContent]:
        """Переиндексация документации"""
        force = args.get("force", False)
        
        try:
            # Проверяем существование всех путей документации
            non_existing = [p for p in self.docs_paths if not p.exists()]
            if non_existing:
                return [TextContent(
                    type="text",
                    text=f"[ERROR] Папки документации не найдены:\n" + 
                           "\n".join(f"  - {p}" for p in non_existing)
                )]
            
            response_text = "[SYNC] **Переиндексация документации фреймворка**\n\n"
            response_text += f"[INFO] Обрабатывается папок: {len(self.docs_paths)}\n\n"
            
            indexed_count = 0
            skipped_count = 0
            error_count = 0
            
            # Индексируем все markdown файлы из всех путей
            for docs_path in self.docs_paths:
                response_text += f"[PATH] Индексация: {docs_path}\n"
                for md_file in docs_path.rglob("*.md"):
                    try:
                        if self.search_engine.index_document(str(md_file)):
                            indexed_count += 1
                            response_text += f"[OK] {md_file.name}\n"
                        else:
                            skipped_count += 1
                            response_text += f"⏭️ {md_file.name} (актуален)\n"
                    except Exception as e:
                        error_count += 1
                        response_text += f"[ERROR] {md_file.name}: {e}\n"
            
            # Статистика
            response_text += f"\n[STATS] **Результаты индексации:**\n"
            response_text += f"- [OK] Проиндексировано: {indexed_count}\n"
            response_text += f"- ⏭️ Пропущено: {skipped_count}\n"
            response_text += f"- [ERROR] Ошибок: {error_count}\n"
            
            # Общая статистика индекса
            stats = self.search_engine.get_statistics()
            response_text += f"\n📈 **Статистика индекса:**\n"
            response_text += f"- [DOCS] Всего документов: {stats['total_documents']}\n"
            response_text += f"- 🧠 С эмбеддингами: {stats['documents_with_embeddings']}\n"
            response_text += f"- [SAVE] Размер: {stats['total_size_mb']} MB\n"
            
            return [TextContent(type="text", text=response_text)]
            
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"[ERROR] Ошибка переиндексации: {str(e)}"
            )]
    
    async def _handle_get_stats(self, args: Dict[str, Any]) -> List[TextContent]:
        """Получение статистики индекса"""
        try:
            stats = self.search_engine.get_statistics()
            
            response_text = "[STATS] **Статистика поискового индекса**\n\n"
            response_text += f"[DOCS] **Документы:**\n"
            response_text += f"- Всего: {stats['total_documents']}\n"
            response_text += f"- С эмбеддингами: {stats['documents_with_embeddings']}\n"
            response_text += f"- Уникальных тегов: {stats['unique_tags']}\n\n"
            
            response_text += f"[SAVE] **Размер:**\n"
            response_text += f"- Общий: {stats['total_size_mb']} MB\n"
            response_text += f"- Байт: {stats['total_size_bytes']:,}\n\n"
            
            response_text += f"[LIST] **Типы документов:**\n"
            for doc_type, count in stats['document_types'].items():
                response_text += f"- {doc_type}: {count}\n"
            
            response_text += f"\n🧠 **Эмбеддинги:**\n"
            response_text += f"- Включены: {'[OK]' if stats['embeddings_enabled'] else '[ERROR]'}\n"
            if stats['model_name']:
                response_text += f"- Модель: {stats['model_name']}\n"
            
            response_text += f"\n[CONFIG] **Возможности:**\n"
            response_text += f"- Полнотекстовый поиск: [OK] (SQLite FTS5)\n"
            response_text += f"- Семантический поиск: {'[OK]' if stats['embeddings_enabled'] else '[ERROR]'}\n"
            response_text += f"- Гибридный поиск: {'[OK]' if stats['embeddings_enabled'] else '[WARNING] (только FTS5)'}\n"
            
            return [TextContent(type="text", text=response_text)]

        except Exception as e:
            return [TextContent(
                type="text",
                text=f"[ERROR] Ошибка получения статистики: {str(e)}"
            )]

    async def _handle_ask_docs(self, args: Dict[str, Any]) -> List[TextContent]:
        """Обработка RAG запроса - генерация ответа на вопрос"""
        question = args.get("question", "")
        use_cache = args.get("use_cache", True)
        top_k = args.get("top_k", 5)
        source = args.get("source", "")

        if not question.strip():
            return [TextContent(
                type="text",
                text="[ERROR] Пустой вопрос"
            )]

        if not self.rag_module:
            return [TextContent(
                type="text",
                text="[ERROR] RAG модуль недоступен. Проверьте установку aiohttp."
            )]

        try:
            # Вызываем RAG модуль
            response = await self.rag_module.ask(
                query=question,
                use_cache=use_cache,
                search_type="hybrid",
                top_k=top_k,
                source_filter=source  # Передаем фильтр по источнику
            )

            # Форматируем ответ
            result_text = f"## 🤖 Ответ на вопрос\n\n"
            result_text += f"**Вопрос:** {question}\n\n"
            result_text += f"---\n\n"
            result_text += response.answer
            result_text += f"\n\n---\n\n"
            result_text += f"**📊 Метаданные:**\n"
            result_text += f"- Модель: `{response.model_used}`\n"
            result_text += f"- Время генерации: {response.generation_time:.2f}с\n"
            result_text += f"- Токенов: {response.total_tokens}\n"
            result_text += f"- Из кеша: {'да' if response.cached else 'нет'}\n"
            result_text += f"- Источников: {len(response.sources)}\n"

            return [TextContent(type="text", text=result_text)]

        except Exception as e:
            return [TextContent(
                type="text",
                text=f"[ERROR] Ошибка RAG: {str(e)}"
            )]

    async def _handle_clear_rag_cache(self, args: Dict[str, Any]) -> List[TextContent]:
        """Очистка кеша RAG ответов"""
        if not self.rag_module:
            return [TextContent(
                type="text",
                text="[ERROR] RAG модуль недоступен"
            )]

        try:
            cleared = self.rag_module.clear_cache()
            stats = self.rag_module.get_cache_stats()

            result_text = f"[OK] **Кеш RAG очищен**\n\n"
            result_text += f"- Удалено записей: {cleared}\n"
            result_text += f"- Директория: `{stats['cache_dir']}`\n"
            result_text += f"- TTL: {stats['ttl_hours']} часов\n"

            return [TextContent(type="text", text=result_text)]

        except Exception as e:
            return [TextContent(
                type="text",
                text=f"[ERROR] Ошибка очистки кеша: {str(e)}"
            )]

    async def _handle_validate_solution(self, args: Dict[str, Any]) -> List[TextContent]:
        """Валидация решения против документации фреймворка"""
        solution = args.get("solution", "")
        context = args.get("context", "")
        check_type = args.get("check_type", "all")

        if not solution.strip():
            return [TextContent(
                type="text",
                text="[ERROR] Пустое описание решения"
            )]

        if not self.rag_module:
            return [TextContent(
                type="text",
                text="[ERROR] RAG модуль недоступен. Валидация невозможна."
            )]

        try:
            # Формируем промпт для валидации
            validation_prompt = self._build_validation_prompt(solution, context, check_type)

            # Выполняем RAG запрос для поиска релевантных стандартов
            search_queries = self._get_validation_queries(check_type)
            all_results = []

            for query in search_queries:
                results = self.search_engine.search(query, limit=3, search_type="hybrid")
                all_results.extend(results)

            # Убираем дубликаты по document.id
            unique_results = {r.document.id: r for r in all_results}
            results = list(unique_results.values())[:10]  # Максимум 10 документов

            if not results:
                return [TextContent(
                    type="text",
                    text=f"[VALIDATION] **Результат валидации**\n\n"
                           f"**Статус:** ⚠️ Предупреждение\n\n"
                           f"По документации не найдено релевантных стандартов для проверки. "
                           f"Рекомендуется дополнительно проверить решение вручную.\n\n"
                           f"**Проверяемое решение:**\n```\n{solution}\n```"
                )]

            # Строим контекст из найденных документов
            context_docs = "\n---\n".join([
                f"### {r.document.title}\n"
                f"**Путь:** {r.document.path}\n"
                f"**Релевантность:** {r.score:.2f}\n"
                f"{r.snippet[:500]}..."
                for r in results
            ])

            # Формируем полный промпт
            full_prompt = f"""# Контекст из документации 1C Framework

{context_docs}

---

# Задача на валидацию

{validation_prompt}

## Инструкции по валидации:
1. Проанализируй решение на соответствие стандартам из документации
2. Укажи потенциальные проблемы или несоответствия
3. Дай конкретные рекомендации по улучшению
4. Используй только информацию из предоставленного контекста

## Формат ответа:
```
## [СТАТУС] ✅ Соответствует / ⚠️ Требует доработки / ❌ Не соответствует

### Найденные проблемы:
- (если есть)

### Рекомендации:
- (конкретные улучшения)

### Соответствие стандартам:
- (анализ по пунктам)
```
"""

            # Вызываем LLM для валидации
            response = await self.rag_module.ask(
                query=full_prompt,
                use_cache=False,
                search_type="hybrid",
                top_k=5
            )

            # Форматируем результат
            result_text = f"## [VALIDATION] Отчёт о валидации решения\n\n"
            result_text += f"**Тип проверки:** {check_type}\n"
            result_text += f"**Проверено документов:** {len(results)}\n"
            result_text += f"**Модель:** {response.model_used}\n"
            result_text += f"**Время проверки:** {response.generation_time:.2f}с\n\n"
            result_text += "---\n\n"
            result_text += response.answer
            result_text += "\n\n---\n\n"
            result_text += "**Источники:**\n"
            for r in results:
                result_text += f"- [{r.document.title}]({r.document.path}) (релевантность: {r.score:.2f})\n"

            return [TextContent(type="text", text=result_text)]

        except Exception as e:
            return [TextContent(
                type="text",
                text=f"[ERROR] Ошибка валидации: {str(e)}"
            )]

    def _build_validation_prompt(self, solution: str, context: str, check_type: str) -> str:
        """Строит промпт для валидации"""
        prompt = f"""## Проверяемое решение:

```
{solution}
```

"""

        if context:
            prompt += f"""## Контекст задачи:

{context}

"""

        prompt += f"""## Тип проверки: {check_type}

Проверь решение на соответствие стандартам и лучшим практикам разработки на 1C:Enterprise.
"""

        return prompt

    async def _handle_get_watcher_status(self, args: Dict[str, Any]) -> List[TextContent]:
        """Получение статуса файлового наблюдателя"""
        try:
            if not WATCHDOG_AVAILABLE:
                return [TextContent(
                    type="text",
                    text="[WARNING] **Автоиндексация недоступна**\n\n"
                           "Библиотека watchdog не установлена.\n"
                           "Установите: `pip install watchdog`"
                )]

            if not self.file_watchers:
                return [TextContent(
                    type="text",
                    text="[INFO] **Файловые наблюдатели не запущены**\n\n"
                           "Автоиндексация не активна."
                )]

            result_text = "[WATCH] **Статус файловых наблюдателей**\n\n"
            result_text += f"**Всего наблюдателей:** {len(self.file_watchers)}\n\n"

            for i, watcher in enumerate(self.file_watchers, 1):
                status = watcher.get_status()
                result_text += f"### Наблюдатель #{i}\n"
                result_text += f"- **Путь:** `{status['docs_path']}`\n"
                result_text += f"- **Статус:** {'🟢 Активен' if status['running'] else '🔴 Остановлен'}\n"
                result_text += f"- **Debounce:** {status['debounce_seconds']}с\n"
                result_text += f"- **В очереди:** {status['pending_events']} событий\n\n"

            result_text += "---\n"
            result_text += "[INFO] **Отслеживаемые события:**\n"
            result_text += "- 📝 Создание .md файлов\n"
            result_text += "- ✏️ Изменение .md файлов\n"
            result_text += "- 🗑️ Удаление .md файлов\n"
            result_text += "- 📁 Перемещение .md файлов\n"

            return [TextContent(type="text", text=result_text)]

        except Exception as e:
            return [TextContent(
                type="text",
                text=f"[ERROR] Ошибка получения статуса: {str(e)}"
            )]

    def _get_validation_queries(self, check_type: str) -> List[str]:
        """Получить поисковые запросы для типа проверки"""
        queries_map = {
            "standards": [
                "стандарты разработки 1С",
                "кодирование BSL стиль",
                "оформление кода"
            ],
            "security": [
                "безопасность кода",
                "защита данных",
                "права доступа"
            ],
            "performance": [
                "оптимизация производительности",
                "эффективность запросов",
                "рекомендации по ускорению"
            ],
            "best_practices": [
                "лучшие практики",
                "рекомендации",
                "паттерны разработки"
            ],
            "all": [
                "стандарты разработки 1С",
                "безопасность кода",
                "оптимизация производительности",
                "лучшие практики BSL",
                "рекомендации по коду"
            ]
        }

        return queries_map.get(check_type, queries_map["all"])

    async def _handle_index_incremental(self, args: Dict[str, Any]) -> List[TextContent]:
        """Инкрементальная индексация документации"""
        try:
            # Получаем путь для индексации
            docs_path = args.get("docs_path", str(self.docs_path))

            # Выполняем инкрементальную индексацию
            stats = self.search_engine.index_directory_incremental(docs_path)

            if "error" in stats:
                return [TextContent(
                    type="text",
                    text=f"[ERROR] {stats['error']}"
                )]

            # Форматируем результат
            result_text = f"[OK] **Инкрементальная индексация завершена**\n\n"
            result_text += f"**Путь:** `{docs_path}`\n\n"
            result_text += f"**Статистика:**\n"
            result_text += f"- ➕ Новых файлов: {stats['new']}\n"
            result_text += f"- ✏️ Изменённых файлов: {stats['modified']}\n"
            result_text += f"- 🗑️ Удалённых файлов: {stats['deleted']}\n"
            result_text += f"- ⏭️ Пропущено (актуальны): {stats['skipped']}\n"
            result_text += f"\n**Всего обработано:** {stats['new'] + stats['modified'] + stats['deleted']} файлов"

            return [TextContent(type="text", text=result_text)]

        except Exception as e:
            return [TextContent(
                type="text",
                text=f"[ERROR] Ошибка инкрементальной индексации: {str(e)}"
            )]

    async def _handle_search_with_facets(self, args: Dict[str, Any]) -> List[TextContent]:
        """Поиск с фасетной фильтрацией"""
        try:
            query = args.get("query", "")
            limit = args.get("limit", 10)
            search_type = args.get("search_type", "hybrid")
            doc_type = args.get("doc_type", None)
            tags = args.get("tags", None)
            date_after = args.get("date_after", None)
            date_before = args.get("date_before", None)
            source = args.get("source", None)

            if not query.strip():
                return [TextContent(
                    type="text",
                    text="[ERROR] Пустой поисковый запрос"
                )]

            # Выполняем поиск с фасетами
            results = self.search_engine.search_with_facets(
                query=query,
                limit=limit,
                search_type=search_type,
                doc_type=doc_type,
                tags=tags,
                date_after=date_after,
                date_before=date_before,
                source=source
            )

            # Форматируем результаты
            result_text = f"## 🔍 Результаты поиска с фасетами\n\n"
            result_text += f"**Запрос:** {query}\n\n"
            
            # Показываем применённые фильтры
            active_filters = []
            if doc_type:
                active_filters.append(f"тип={doc_type}")
            if tags:
                active_filters.append(f"теги={', '.join(tags)}")
            if date_after:
                active_filters.append(f"после={date_after}")
            if date_before:
                active_filters.append(f"до={date_before}")
            if source:
                active_filters.append(f"источник={source}")
            
            if active_filters:
                result_text += f"**Фильтры:** {', '.join(active_filters)}\n\n"
                result_text += "---\n\n"

            if not results:
                result_text += "*Нет результатов.*"
            else:
                for i, result in enumerate(results, 1):
                    doc = result.document
                    result_text += f"### {i}. {doc.title}\n"
                    result_text += f"**Релевантность:** {result.score:.3f} ({result.match_type})\n"
                    result_text += f"**Путь:** `{doc.path}`\n"
                    result_text += f"**Тип:** {doc.doc_type}\n"
                    if doc.tags:
                        result_text += f"**Теги:** {', '.join(doc.tags)}\n"
                    result_text += f"**Сниппет:**\n{result.snippet}\n\n"

            return [TextContent(type="text", text=result_text)]

        except Exception as e:
            return [TextContent(
                type="text",
                text=f"[ERROR] Ошибка поиска с фасетами: {str(e)}"
            )]

    async def _handle_get_available_facets(self, args: Dict[str, Any]) -> List[TextContent]:
        """Получение доступных фасетов"""
        try:
            facets = self.search_engine.get_available_facets()

            # Форматируем результат
            result_text = f"## 📊 Доступные фасеты для фильтрации\n\n"

            # Типы документов
            result_text += "### 📁 Типы документов\n\n"
            if facets['doc_types']:
                for doc_type, count in facets['doc_types'].items():
                    result_text += f"- **{doc_type}**: {count} документов\n"
            else:
                result_text += "*Нет данных*\n"

            # Теги
            result_text += "\n### 🏷️ Теги\n\n"
            if facets['tags']:
                for tag, count in list(facets['tags'].items())[:20]:  # ТОП-20
                    result_text += f"- **{tag}**: {count} документов\n"
                if len(facets['tags']) > 20:
                    result_text += f"- ... и ещё {len(facets['tags']) - 20} тегов\n"
            else:
                result_text += "*Нет данных*\n"

            # Источники
            result_text += "\n### 📂 Источники\n\n"
            if facets['sources']:
                for source in facets['sources']:
                    result_text += f"- `{source}`\n"
            else:
                result_text += "*Нет данных*\n"

            # Диапазон дат
            result_text += "\n### 📅 Диапазон дат\n\n"
            if facets['date_range']['min'] and facets['date_range']['max']:
                result_text += f"- **От:** {facets['date_range']['min']}\n"
                result_text += f"- **До:** {facets['date_range']['max']}\n"
            else:
                result_text += "*Нет данных*\n"

            result_text += "\n---\n\n"
            result_text += "**Пример использования:**\n"
            result_text += "```\n"
            result_text += "# Фильтр по источнику\n"
            result_text += "mcp__1c-docs-rag__search_docs_with_facets(\n"
            result_text += "    query='хуки',\n"
            result_text += "    source='claude'\n"
            result_text += ")\n\n"
            result_text += "# Фильтр по тегам и дате\n"
            result_text += "mcp__1c-docs-rag__search_docs_with_facets(\n"
            result_text += "    query='API',\n"
            result_text += "    tags=['api', 'integration'],\n"
            result_text += "    date_after='2025-01-01'\n"
            result_text += ")\n"
            result_text += "```\n"

            return [TextContent(type="text", text=result_text)]

        except Exception as e:
            return [TextContent(
                type="text",
                text=f"[ERROR] Ошибка получения фасетов: {str(e)}"
            )]

    async def _handle_index_bsl_project(self, args: Dict[str, Any]) -> List[TextContent]:
        """Индексация BSL файлов конфигурации 1С"""
        project_path = args.get("project_path", "")
        chunk_mode = args.get("chunk_mode", "smart")
        force = args.get("force", False)

        try:
            # Если путь не указан, пытаемся найти активный проект
            if not project_path:
                # Проверяем переменные окружения
                project_path = os.getenv('BSL_PROJECT_PATH', '')

            if not project_path:
                return [TextContent(
                    type="text",
                    text="[ERROR] Не указан путь к проекту. Укажите project_path или установите переменную BSL_PROJECT_PATH."
                )]

            project_dir = Path(project_path)
            if not project_dir.exists():
                return [TextContent(
                    type="text",
                    text=f"[ERROR] Директория проекта не найдена: {project_path}"
                )]

            # Ищем BSL файлы
            bsl_files = list(project_dir.rglob("*.bsl"))

            if not bsl_files:
                return [TextContent(
                    type="text",
                    text=f"[WARNING] В директории {project_path} не найдено BSL файлов"
                )]

            # Индексируем файлы с параллельной обработкой и прогресс-баром
            result_text = f"## 📂 Индексация BSL проекта\n\n"
            result_text += f"**[PATH] Проект:** `{project_path}`\n"
            result_text += f"**⚙️ Режим:** `{chunk_mode}`\n"
            result_text += f"**📁 Найдено файлов:** {len(bsl_files)}\n"

            # Определяем количество воркеров (не больше 8 и не больше CPU/2)
            import multiprocessing
            max_workers = min(8, max(1, multiprocessing.cpu_count() // 2))
            result_text += f"**🔄 Параллельных потоков:** {max_workers}\n\n"

            indexed_count = 0
            error_count = 0
            total_chunks = 0
            all_documents = []
            errors_list = []

            # Время начала для расчёта ETA
            start_time = time.time()
            total_files = len(bsl_files)

            # Фаза 1: Параллельное чтение и парсинг файлов (без эмбеддингов)
            result_text += "### 📖 Фаза 1: Чтение файлов (параллельно)\n\n"

            def process_file(bsl_file):
                """Обработка одного файла (для ThreadPoolExecutor)"""
                try:
                    docs, chunks = self.search_engine.index_bsl_file_data(
                        str(bsl_file), chunk_mode=chunk_mode
                    )
                    return {"success": True, "file": bsl_file.name, "docs": docs, "chunks": chunks}
                except Exception as e:
                    return {"success": False, "file": bsl_file.name, "error": str(e)[:100]}

            # Параллельная обработка с прогрессом
            processed = 0
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {executor.submit(process_file, f): f for f in bsl_files}

                for future in as_completed(futures):
                    processed += 1
                    result = future.result()

                    if result["success"]:
                        if result["docs"]:
                            all_documents.extend(result["docs"])
                            indexed_count += 1
                            total_chunks += result["chunks"]
                    else:
                        error_count += 1
                        errors_list.append(result)

                    # Прогресс каждые 100 файлов или в конце
                    if processed % 100 == 0 or processed == total_files:
                        elapsed = time.time() - start_time
                        files_per_sec = processed / elapsed if elapsed > 0 else 0
                        remaining = total_files - processed
                        eta_sec = remaining / files_per_sec if files_per_sec > 0 else 0

                        # Форматируем ETA
                        if eta_sec > 60:
                            eta_str = f"{int(eta_sec // 60)}м {int(eta_sec % 60)}с"
                        else:
                            eta_str = f"{int(eta_sec)}с"

                        progress_pct = (processed / total_files) * 100
                        result_text += f"[PROGRESS] {processed}/{total_files} ({progress_pct:.1f}%) | ETA: {eta_str}\n"

            phase1_time = time.time() - start_time
            result_text += f"\n**⏱️ Фаза 1 завершена:** {phase1_time:.1f}с | {len(all_documents)} документов\n\n"

            # Фаза 2: Батчевая генерация эмбеддингов
            if all_documents:
                result_text += "### 🧠 Фаза 2: Генерация эмбеддингов (батчами)\n\n"

                phase2_start = time.time()
                batch_size = 32
                total_batches = (len(all_documents) + batch_size - 1) // batch_size

                def progress_callback(current, total, status):
                    nonlocal result_text
                    if current % 5 == 0 or current == total:  # Каждые 5 батчей
                        pct = (current / total) * 100
                        result_text += f"[EMBEDDINGS] Батч {current}/{total} ({pct:.0f}%)\n"

                embedded_count = self.search_engine.generate_embeddings_batch(
                    all_documents,
                    batch_size=batch_size,
                    progress_callback=progress_callback
                )

                phase2_time = time.time() - phase2_start
                result_text += f"\n**⏱️ Фаза 2 завершена:** {phase2_time:.1f}с | {embedded_count} эмбеддингов\n\n"

            # Показываем первые ошибки
            if errors_list:
                result_text += "### ❌ Ошибки\n\n"
                for err in errors_list[:5]:
                    result_text += f"- `{err['file']}`: {err['error']}\n"
                if len(errors_list) > 5:
                    result_text += f"... и ещё {len(errors_list) - 5} ошибок\n"

            total_time = time.time() - start_time

            # Статистика
            result_text += f"\n### 📊 Результаты индексации\n\n"
            result_text += f"- **[OK] Успешно:** {indexed_count} файлов\n"
            result_text += f"- **📄 Чанков создано:** {total_chunks}\n"
            result_text += f"- **[ERROR] Ошибок:** {error_count}\n"

            # Метрики производительности
            result_text += f"\n### ⏱️ Производительность\n\n"
            result_text += f"- **Общее время:** {total_time:.1f}с"
            if total_time > 60:
                result_text += f" ({total_time/60:.1f} мин)"
            result_text += "\n"
            files_per_sec = indexed_count / total_time if total_time > 0 else 0
            result_text += f"- **Скорость:** {files_per_sec:.1f} файлов/сек\n"
            result_text += f"- **Потоков:** {max_workers}\n"

            # Общая статистика
            stats = self.search_engine.get_statistics()
            result_text += f"\n### 📈 Общая статистика индекса\n\n"
            result_text += f"- **[DOCS] Всего документов:** {stats['total_documents']}\n"
            result_text += f"- **🧠 С эмбеддингами:** {stats['documents_with_embeddings']}\n"
            result_text += f"- **[SAVE] Размер БД:** {stats['total_size_mb']} MB\n"

            result_text += f"\n---\n\n"
            result_text += "**Теперь можно искать по BSL коду:**\n"
            result_text += "```python\n"
            result_text += "mcp__1c-docs-rag__search_docs(query='СохранитьДанные', search_type='hybrid')\n"
            result_text += "```\n"

            return [TextContent(type="text", text=result_text)]

        except Exception as e:
            import traceback
            return [TextContent(
                type="text",
                text=f"[ERROR] Ошибка индексации BSL проекта: {str(e)}\n\n{traceback.format_exc()}"
            )]

    async def _handle_index_xml_project(self, args: Dict[str, Any]) -> List[TextContent]:
        """Индексация XML файлов конфигурации 1С (формы, подсистемы, права, языки)"""
        project_path = args.get("project_path", "")
        xml_types = args.get("xml_types", None)

        try:
            if not project_path:
                return [TextContent(
                    type="text",
                    text="[ERROR] Не указан путь к проекту. Параметр project_path обязателен."
                )]

            project_dir = Path(project_path)
            if not project_dir.exists():
                return [TextContent(
                    type="text",
                    text=f"[ERROR] Директория проекта не найдена: {project_path}"
                )]

            # Формируем описание типов
            types_desc = ", ".join(xml_types) if xml_types else "subsystems, forms, languages (по умолчанию)"

            result_text = f"## 📂 Индексация XML проекта 1С\n\n"
            result_text += f"**📍 Проект:** `{project_path}`\n"
            result_text += f"**📋 Типы XML:** `{types_desc}`\n\n"

            # Индексируем через движок
            stats = self.search_engine.index_xml_project(str(project_dir), xml_types=xml_types)

            # Результаты по типам
            result_text += f"### 📊 Результаты индексации\n\n"
            result_text += f"- **✅ Файлов обработано:** {stats['files']}\n"
            result_text += f"- **📄 Документов создано:** {stats['documents']}\n"
            result_text += f"- **❌ Ошибок:** {stats['errors']}\n\n"

            # Детализация по типам
            if 'by_type' in stats:
                result_text += f"### 📋 По типам XML\n\n"
                for xml_type, count in stats['by_type'].items():
                    if count > 0:
                        result_text += f"- **{xml_type}:** {count}\n"

            # Общая статистика индекса
            total_stats = self.search_engine.get_statistics()
            result_text += f"\n### 📈 Общая статистика индекса\n\n"
            result_text += f"- **📚 Всего документов:** {total_stats['total_documents']}\n"
            result_text += f"- **🧠 С эмбеддингами:** {total_stats['documents_with_embeddings']}\n"
            result_text += f"- **💾 Размер БД:** {total_stats['total_size_mb']} MB\n"

            result_text += f"\n---\n\n"
            result_text += "**Теперь можно искать по XML структуре конфигурации:**\n"
            result_text += "```python\n"
            result_text += "mcp__1c-docs-rag__search_docs(query='подсистема Администрирование', search_type='hybrid')\n"
            result_text += "```\n"

            return [TextContent(type="text", text=result_text)]

        except Exception as e:
            import traceback
            return [TextContent(
                type="text",
                text=f"[ERROR] Ошибка индексации XML проекта: {str(e)}\n\n{traceback.format_exc()}"
            )]

    async def _handle_delete_by_source(self, args: Dict[str, Any]) -> List[TextContent]:
        """Удаление всех документов из индекса по пути источника"""
        source_path = args.get("source_path", "")

        if not source_path:
            return [TextContent(
                type="text",
                text="[ERROR] Не указан путь к источнику (source_path)"
            )]

        try:
            result_text = f"# 🗑️ Удаление документов из индекса\n\n"
            result_text += f"**📂 Источник:** `{source_path}`\n\n"

            # Удаляем документы
            stats = self.search_engine.delete_by_source(source_path)

            if stats["total_files"] == 0:
                result_text += "⚠️ **Документы не найдены** в индексе для указанного пути.\n"
            else:
                result_text += f"### 📊 Результаты удаления\n\n"
                result_text += f"- **📄 Найдено файлов:** {stats['total_files']}\n"
                result_text += f"- **✅ Удалено документов:** {stats['documents']}\n"
                result_text += f"- **📝 Удалено FTS записей:** {stats['fts']}\n"
                result_text += f"- **🧠 Удалено эмбеддингов:** {stats['embeddings']}\n"

            return [TextContent(type="text", text=result_text)]

        except Exception as e:
            import traceback
            return [TextContent(
                type="text",
                text=f"[ERROR] Ошибка удаления: {str(e)}\n\n{traceback.format_exc()}"
            )]

    async def _handle_get_indexed_projects(self, args: Dict[str, Any]) -> List[TextContent]:
        """Получение списка проиндексированных проектов"""
        try:
            projects = self.search_engine.get_indexed_projects()

            result_text = f"# 📚 Проиндексированные проекты\n\n"
            result_text += f"**Всего источников:** {len(projects)}\n\n"

            if not projects:
                result_text += "⚠️ Индекс пуст. Проекты не проиндексированы.\n"
            else:
                result_text += "| Проект | Документов | Типы | Последняя индексация |\n"
                result_text += "|--------|------------|------|----------------------|\n"

                for proj in projects:
                    doc_types = ", ".join(proj["doc_types"][:3])
                    if len(proj["doc_types"]) > 3:
                        doc_types += f" (+{len(proj['doc_types'])-3})"
                    result_text += f"| `{proj['project_name']}` | {proj['doc_count']} | {doc_types} | {proj['last_indexed'][:10]} |\n"

                result_text += f"\n### 📂 Полные пути:\n\n"
                for proj in projects:
                    result_text += f"- **{proj['project_name']}:** `{proj['source_path']}`\n"

            return [TextContent(type="text", text=result_text)]

        except Exception as e:
            import traceback
            return [TextContent(
                type="text",
                text=f"[ERROR] Ошибка получения списка проектов: {str(e)}\n\n{traceback.format_exc()}"
            )]

    async def run(self):
        """Запуск MCP сервера"""
        if not MCP_AVAILABLE:
            log_stderr("[ERROR] MCP не доступен. Установите зависимости.")
            return

        log_stderr("[START] Запуск MCP сервера документации фреймворка 1C")
        log_stderr("[DOCS] Доступные инструменты:")
        log_stderr("  - search_docs: Поиск по документации")
        log_stderr("  - get_document: Получение полного документа")
        log_stderr("  - reindex_docs: Переиндексация")
        log_stderr("  - get_stats: Статистика индекса")
        log_stderr("  - ask_docs: RAG - генерация ответов на вопросы")
        log_stderr("  - clear_rag_cache: Очистка кеша RAG")
        log_stderr("  - get_watcher_status: Статус автоиндексации")
        log_stderr("  - index_incremental: Инкрементальная индексация (NEW!)")
        log_stderr("  - search_docs_with_facets: Фасетный поиск (NEW!)")
        log_stderr("  - get_available_facets: Доступные фасеты (NEW!)")
        log_stderr("  - index_bsl_project: Индексация BSL конфигурации 1С (NEW!)")
        log_stderr("  - index_xml_project: Индексация XML конфигурации 1С (NEW!)")
        log_stderr("  - delete_by_source: Удаление документов по источнику (NEW!)")
        log_stderr("  - get_indexed_projects: Список проиндексированных проектов (NEW!)")
        log_stderr(f"\n[RAG] RAG модуль: {'[OK]' if self.rag_module else '[ERROR] недоступен'}")
        log_stderr("\n[OK] Сервер готов к работе")

        # Запуск сервера СРАЗУ (не блокируем подключение)
        from mcp.server.stdio import stdio_server
        async with stdio_server() as (read_stream, write_stream):
            # Запускаем индексацию ПАРАЛЛЕЛЬНО с сервером
            asyncio.create_task(self._background_index_check())
            await self.server.run(read_stream, write_stream,
                                 self.server.create_initialization_options())

    async def _background_index_check(self):
        """Фоновая проверка и индексация документации"""
        await asyncio.sleep(0.1)  # Даём серверу время подключиться

        existing_paths = [p for p in self.docs_paths if p.exists()]
        if not existing_paths:
            return

        log_stderr(f"[ASYNC] Фоновая проверка индекса ({len(existing_paths)} папок)...")
        stats = self.search_engine.get_statistics()
        if stats['total_documents'] == 0:
            log_stderr("[DOCS] Первичная индексация документации...")
            for docs_path in existing_paths:
                log_stderr(f"  [PATH] {docs_path}")
                for md_file in docs_path.rglob("*.md"):
                    self.search_engine.index_document(str(md_file))
                await asyncio.sleep(0)  # yield для других задач
            log_stderr("[OK] Индексация завершена")

        # Запуск файловых наблюдателей для автоиндексации
        if WATCHDOG_AVAILABLE:
            log_stderr("[WATCH] Запуск автоиндексации...")
            for docs_path in existing_paths:
                try:
                    watcher = DocsFileWatcher(self.search_engine, str(docs_path))
                    watcher.start()
                    self.file_watchers.append(watcher)
                    log_stderr(f"  [OK] Наблюдатель запущен: {docs_path}")
                except Exception as e:
                    log_stderr(f"  [ERROR] Не удалось запустить наблюдатель для {docs_path}: {e}")
            log_stderr(f"[OK] Автоиндексация активна ({len(self.file_watchers)} наблюдателей)")
        else:
            log_stderr("[WARNING] watchdog не установлен - автоиндексация недоступна")


async def main():
    """Главная функция"""
    server = FrameworkDocsMCPServer()
    await server.run()


if __name__ == "__main__":
    if not MCP_AVAILABLE:
        log_stderr("[ERROR] Для работы требуется установка MCP:")
        log_stderr("pip install mcp sentence-transformers")
        sys.exit(1)

    asyncio.run(main())