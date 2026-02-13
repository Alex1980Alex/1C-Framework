# Phase 26: MCP Native & Tool Integration

**Приоритет:** СРЕДНИЙ | **Квартал:** Q2-Q3 2026 | **Версия:** v0.17.0
**Источники:** AnythingLLM, Dify, Claude Code
**Статус: НЕ РЕАЛИЗОВАНО** (перенумеровано из Phase 25, т.к. Phase 25 использован для LLM Reranker)

---

## Проблема

Текущий MCP Server (`src/mcp_server/server.py`) предоставляет 5 базовых tools (index_pdf, search_documents, ask_question, graph_query, get_stats), но:

1. **Нет Resources** — MCP Resources позволяют предоставлять контекстные данные клиенту
2. **Нет Prompts** — MCP Prompts дают шаблоны для типичных задач
3. **Нет Streaming** — ответы на ask_question приходят целиком, без промежуточных шагов
4. **Ограниченный набор стратегий** — search_documents поддерживает только vector/graph/hybrid
5. **Нет web search tool** — агент не может дополнить контекст из интернета
6. **Нет 1С API connector** — нет прямого подключения к API 1С:Предприятие
7. **Нет внешних коннекторов** — только локальные PDF, нет Confluence/Wiki/Notion

## Текущее состояние

### Что уже есть
- **MCP Server** (`src/mcp_server/server.py`): stdio transport, 5 tools
- **Components** singleton — все компоненты фреймворка доступны через DI
- **SearchManager** с 10+ стратегиями (vector, graph, hybrid, bm25, mmr, adaptive, graphrag_local, graphrag_global, raptor, two_stage)
- **RAG Agent** (Phase 5): LangGraph с Self-RAG
- **Deep Research Agent** (Phase 19, если реализован): multi-hop reasoning
- **Streaming** (`src/pdf_framework/agents/rag/streaming.py`): SSE streaming для API

### Чего не хватает
- MCP Resources (документы, графы, статистика)
- MCP Prompts (шаблоны запросов)
- Streaming через MCP (промежуточные шаги)
- Полный список стратегий в tool schema
- Web search integration
- 1С:Предприятие API коннектор
- Confluence/Wiki/Notion коннекторы
- Batch operations tools

---

## Архитектура решения

```
MCP Server v2
  ├─ Tools (12+):
  │   ├─ index_pdf (existing)
  │   ├─ index_batch (NEW: batch indexing)
  │   ├─ search (enhanced: all strategies)
  │   ├─ ask (enhanced: streaming + deep research)
  │   ├─ graph_query (existing)
  │   ├─ graph_explore (NEW: graph navigation)
  │   ├─ get_stats (existing)
  │   ├─ web_search (NEW: internet fallback)
  │   ├─ manage_cache (NEW: cache operations)
  │   ├─ evaluate (NEW: run eval on question)
  │   ├─ feedback (NEW: submit feedback)
  │   └─ connector_sync (NEW: sync external sources)
  │
  ├─ Resources (4+):
  │   ├─ documents://list — список проиндексированных документов
  │   ├─ documents://{id} — метаданные и чанки документа
  │   ├─ graph://stats — статистика графа знаний
  │   ├─ graph://entities/{name} — сущности и связи
  │   └─ cache://stats — статистика всех кэшей
  │
  ├─ Prompts (5+):
  │   ├─ search-1c — поиск по документации 1С
  │   ├─ compare — сравнение концепций
  │   ├─ explain — объяснение термина
  │   ├─ troubleshoot — диагностика проблемы
  │   └─ deep-research — глубокое исследование
  │
  └─ External Connectors:
      ├─ Web Search (Tavily/SerpAPI)
      ├─ 1С:Предприятие HTTP API
      ├─ Confluence REST API
      └─ Notion API
```

---

## Пошаговый план

### 24.1. MCP Server v2 — Enhanced Tools

**Модификация:** `src/mcp_server/server.py`

```python
@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # --- Existing (enhanced) ---
        Tool(
            name="search",
            description="Search indexed 1C documentation using various strategies",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query in Russian or English"},
                    "strategy": {
                        "type": "string",
                        "enum": [
                            "vector", "graph", "hybrid", "bm25", "mmr",
                            "adaptive", "graphrag_local", "graphrag_global",
                            "raptor", "two_stage",
                        ],
                        "default": "hybrid",
                        "description": "Search strategy. 'adaptive' auto-selects the best.",
                    },
                    "k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
                    "filter": {
                        "type": "object",
                        "description": "Metadata filter (e.g., {\"source\": \"document.pdf\"})",
                    },
                },
                "required": ["query"],
            },
        ),

        Tool(
            name="ask",
            description="Ask a question about 1C:Enterprise documentation and get an LLM-generated answer with RAG.",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "strategy": {"type": "string", "default": "adaptive"},
                    "deep_research": {
                        "type": "boolean",
                        "default": False,
                        "description": "Use deep research for complex multi-step questions",
                    },
                },
                "required": ["question"],
            },
        ),

        # --- New tools ---
        Tool(
            name="index_batch",
            description="Index multiple PDF files from a directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Path to directory with PDFs"},
                    "incremental": {
                        "type": "boolean",
                        "default": True,
                        "description": "Skip unchanged files (Phase 18)",
                    },
                },
                "required": ["directory"],
            },
        ),

        Tool(
            name="graph_explore",
            description="Explore knowledge graph: navigate entities, find paths, discover communities.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {"type": "string", "description": "Entity name to start from"},
                    "operation": {
                        "type": "string",
                        "enum": ["neighbors", "path", "community", "related_docs"],
                        "default": "neighbors",
                    },
                    "target": {"type": "string", "description": "Target entity (for path operation)"},
                    "depth": {"type": "integer", "default": 2, "minimum": 1, "maximum": 5},
                },
                "required": ["entity"],
            },
        ),

        Tool(
            name="web_search",
            description="Search the web for additional context when local documents are insufficient.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "default": 5},
                    "domain_filter": {
                        "type": "string",
                        "description": "Limit to domain (e.g., 'its.1c.ru')",
                    },
                },
                "required": ["query"],
            },
        ),

        Tool(
            name="manage_cache",
            description="Cache management operations.",
            inputSchema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["stats", "clear", "clear_semantic", "clear_embedding"],
                    },
                },
                "required": ["operation"],
            },
        ),

        Tool(
            name="submit_feedback",
            description="Submit feedback for a previous answer to improve future responses.",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "answer": {"type": "string"},
                    "score": {"type": "integer", "enum": [-1, 1], "description": "-1 = bad, 1 = good"},
                    "comment": {"type": "string", "default": ""},
                },
                "required": ["question", "answer", "score"],
            },
        ),
    ]
```

### 24.2. MCP Resources

**Модификация:** `src/mcp_server/server.py`

```python
from mcp.types import Resource, ResourceTemplate

@server.list_resources()
async def list_resources() -> list[Resource]:
    return [
        Resource(
            uri="documents://list",
            name="Indexed Documents",
            description="List of all indexed PDF documents with metadata",
            mimeType="application/json",
        ),
        Resource(
            uri="graph://stats",
            name="Knowledge Graph Statistics",
            description="Graph statistics: nodes, edges, communities",
            mimeType="application/json",
        ),
        Resource(
            uri="cache://stats",
            name="Cache Statistics",
            description="Statistics for all caches (embedding, LLM, semantic, document)",
            mimeType="application/json",
        ),
    ]

@server.list_resource_templates()
async def list_resource_templates() -> list[ResourceTemplate]:
    return [
        ResourceTemplate(
            uriTemplate="documents://{document_id}",
            name="Document Details",
            description="Get chunks and metadata for a specific document",
            mimeType="application/json",
        ),
        ResourceTemplate(
            uriTemplate="graph://entities/{entity_name}",
            name="Entity Graph",
            description="Get entity details, neighbors, and relations",
            mimeType="application/json",
        ),
    ]

@server.read_resource()
async def read_resource(uri: str) -> str:
    components = await _get_components()

    if uri == "documents://list":
        # List all unique documents from vector store
        collection = components.vector_store.collection
        results = collection.get(include=["metadatas"], limit=1000)
        documents = {}
        for meta in results.get("metadatas", []):
            source = meta.get("source", "unknown")
            if source not in documents:
                documents[source] = {
                    "source": source,
                    "document_id": meta.get("document_id", ""),
                    "chunks_count": 0,
                }
            documents[source]["chunks_count"] += 1
        return json.dumps(list(documents.values()), ensure_ascii=False)

    elif uri == "graph://stats":
        stats = await components.graph_store.get_statistics()
        return json.dumps(stats, ensure_ascii=False)

    elif uri == "cache://stats":
        # Aggregate cache stats
        from src.api.routes.cache import cache_stats
        stats = await cache_stats()
        return json.dumps(stats, ensure_ascii=False)

    elif uri.startswith("documents://"):
        doc_id = uri.split("//")[1]
        # Get chunks for this document
        ...

    elif uri.startswith("graph://entities/"):
        entity_name = uri.split("/")[-1]
        entities = await components.graph_store.find_entities(name=entity_name)
        ...
```

### 24.3. MCP Prompts

**Модификация:** `src/mcp_server/server.py`

```python
from mcp.types import Prompt, PromptArgument, PromptMessage, TextContent as PromptTextContent

@server.list_prompts()
async def list_prompts() -> list[Prompt]:
    return [
        Prompt(
            name="search-1c",
            description="Найти информацию в документации 1С:Предприятие",
            arguments=[
                PromptArgument(name="topic", description="Тема для поиска", required=True),
            ],
        ),
        Prompt(
            name="compare",
            description="Сравнить два концепта из документации 1С",
            arguments=[
                PromptArgument(name="concept1", description="Первый концепт", required=True),
                PromptArgument(name="concept2", description="Второй концепт", required=True),
            ],
        ),
        Prompt(
            name="explain",
            description="Объяснить термин или механизм из 1С:Предприятие",
            arguments=[
                PromptArgument(name="term", description="Термин или механизм", required=True),
                PromptArgument(name="level", description="Уровень детализации: brief/detailed", required=False),
            ],
        ),
        Prompt(
            name="troubleshoot",
            description="Помочь с диагностикой проблемы в 1С:Предприятие",
            arguments=[
                PromptArgument(name="problem", description="Описание проблемы", required=True),
            ],
        ),
        Prompt(
            name="deep-research",
            description="Глубокое исследование темы с анализом нескольких источников",
            arguments=[
                PromptArgument(name="question", description="Исследовательский вопрос", required=True),
            ],
        ),
    ]

@server.get_prompt()
async def get_prompt(name: str, arguments: dict) -> list[PromptMessage]:
    if name == "search-1c":
        topic = arguments["topic"]
        return [PromptMessage(
            role="user",
            content=PromptTextContent(
                type="text",
                text=f"""Найди в документации 1С:Предприятие информацию по теме: {topic}

Используй инструмент search с strategy="adaptive" для поиска.
Затем используй ask для получения структурированного ответа.
Если результатов мало, попробуй web_search для дополнительного контекста.

Предоставь ответ с указанием источников."""
            ),
        )]

    elif name == "compare":
        c1, c2 = arguments["concept1"], arguments["concept2"]
        return [PromptMessage(
            role="user",
            content=PromptTextContent(
                type="text",
                text=f"""Сравни два концепта из документации 1С:Предприятие:
1. {c1}
2. {c2}

Шаги:
1. Используй search для поиска информации по каждому концепту отдельно
2. Используй graph_explore для поиска связей между ними
3. Составь таблицу сравнения с критериями: назначение, применение, ограничения, примеры
4. Дай рекомендацию, когда использовать каждый"""
            ),
        )]

    elif name == "explain":
        term = arguments["term"]
        level = arguments.get("level", "detailed")
        return [PromptMessage(
            role="user",
            content=PromptTextContent(
                type="text",
                text=f"""Объясни термин или механизм из 1С:Предприятие: {term}

Уровень детализации: {level}

Шаги:
1. Используй search с strategy="bm25" для точного поиска термина
2. Используй graph_explore для связанных концептов
3. {"Дай краткое определение (2-3 предложения)" if level == "brief" else "Предоставь подробное объяснение: определение, назначение, как работает, примеры использования, связанные объекты"}"""
            ),
        )]

    elif name == "troubleshoot":
        problem = arguments["problem"]
        return [PromptMessage(
            role="user",
            content=PromptTextContent(
                type="text",
                text=f"""Помоги диагностировать проблему в 1С:Предприятие:

Проблема: {problem}

Шаги:
1. Используй search для поиска описания подобных проблем в документации
2. Используй ask для получения рекомендаций по решению
3. Если в документации недостаточно информации, используй web_search (домен its.1c.ru)
4. Предоставь пошаговый план решения с указанием источников"""
            ),
        )]

    elif name == "deep-research":
        question = arguments["question"]
        return [PromptMessage(
            role="user",
            content=PromptTextContent(
                type="text",
                text=f"""Проведи глубокое исследование по вопросу: {question}

Используй ask с deep_research=true для multi-step analysis.
Это автоматически:
1. Разобьёт вопрос на под-вопросы
2. Выполнит поиск по каждому
3. Синтезирует финальный ответ с цитатами

Представь результат структурированно с ссылками на источники."""
            ),
        )]
```

### 24.4. Web Search Integration

**Новый файл:** `src/pdf_framework/tools/web_search.py`

```python
from tavily import TavilyClient

class WebSearchTool:
    """Web search fallback when local documents are insufficient.

    Uses Tavily API for web search (optimized for LLM use).
    Alternative: SerpAPI, Brave Search API.
    """

    def __init__(
        self,
        api_key: str,
        provider: Literal["tavily", "serpapi", "brave"] = "tavily",
    ):
        if provider == "tavily":
            self._client = TavilyClient(api_key=api_key)
        ...

    async def search(
        self,
        query: str,
        max_results: int = 5,
        domain_filter: str | None = None,
        search_depth: str = "basic",
    ) -> list[WebSearchResult]:
        """Search the web for additional context.

        Args:
            query: Search query
            max_results: Maximum number of results
            domain_filter: Limit to specific domain (e.g., "its.1c.ru")
            search_depth: "basic" (fast) or "advanced" (thorough)
        """
        kwargs = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
        }
        if domain_filter:
            kwargs["include_domains"] = [domain_filter]

        results = self._client.search(**kwargs)

        return [
            WebSearchResult(
                title=r["title"],
                url=r["url"],
                content=r["content"],
                score=r.get("score", 0.0),
            )
            for r in results.get("results", [])
        ]

class WebSearchResult(BaseModel):
    title: str
    url: str
    content: str
    score: float
```

### 24.5. 1С:Предприятие HTTP API Connector

**Новый файл:** `src/pdf_framework/tools/connector_1c.py`

```python
import httpx

class Connector1C:
    """Connect to 1C:Enterprise HTTP services for live data.

    Supports:
    - OData (read metadata, catalogs, documents)
    - HTTP services (custom endpoints)
    - Configuration metadata retrieval
    """

    def __init__(
        self,
        base_url: str,              # http://server/base/hs/api
        username: str = "",
        password: str = "",
        auth_type: Literal["basic", "ntlm"] = "basic",
    ):
        self._base_url = base_url.rstrip("/")
        self._auth = (username, password) if username else None
        self._client = httpx.AsyncClient(
            auth=self._auth,
            timeout=30.0,
            verify=False,  # 1C servers often use self-signed certs
        )

    async def get_metadata(self) -> dict:
        """Get configuration metadata from OData.

        Returns list of available entities: catalogs, documents, registers, etc.
        """
        response = await self._client.get(f"{self._base_url}/$metadata")
        ...

    async def query_odata(
        self,
        entity: str,
        filter: str = "",
        select: str = "",
        top: int = 100,
    ) -> list[dict]:
        """Query OData endpoint.

        Example:
            await connector.query_odata(
                "Catalog_Номенклатура",
                filter="Наименование eq 'Товар'",
                select="Ref_Key,Наименование,Код",
                top=10,
            )
        """
        params = {"$format": "json", "$top": str(top)}
        if filter:
            params["$filter"] = filter
        if select:
            params["$select"] = select

        response = await self._client.get(
            f"{self._base_url}/{entity}",
            params=params,
        )
        data = response.json()
        return data.get("value", [])

    async def call_http_service(
        self,
        service_name: str,
        method: str,
        params: dict | None = None,
        body: dict | None = None,
    ) -> dict:
        """Call custom 1C HTTP service.

        Example:
            await connector.call_http_service(
                "GetDocumentInfo",
                method="POST",
                body={"DocumentRef": "..."},
            )
        """
```

### 24.6. Confluence/Wiki Connector

**Новый файл:** `src/pdf_framework/tools/connector_confluence.py`

```python
class ConfluenceConnector:
    """Sync Confluence pages to local knowledge base.

    Indexes Confluence pages as documents alongside PDFs.
    """

    def __init__(
        self,
        base_url: str,              # https://company.atlassian.net
        username: str,
        api_token: str,
        space_key: str = "",
    ):
        ...

    async def list_pages(
        self,
        space_key: str = "",
        label: str = "",
        limit: int = 100,
    ) -> list[ConfluencePage]:
        """List pages from Confluence space."""

    async def get_page_content(self, page_id: str) -> str:
        """Get page content as markdown/plain text."""

    async def sync_to_index(
        self,
        components: Components,
        space_key: str,
        incremental: bool = True,
    ) -> SyncResult:
        """Sync Confluence pages to vector store.

        1. List pages in space
        2. For each page:
           a. Check if content changed (hash comparison)
           b. Convert HTML → markdown → chunks
           c. Index chunks (incremental if Phase 18 available)
        3. Remove chunks for deleted pages
        """

class ConfluencePage(BaseModel):
    page_id: str
    title: str
    space_key: str
    content_hash: str
    last_modified: str
    url: str

class SyncResult(BaseModel):
    pages_synced: int
    pages_skipped: int
    pages_deleted: int
    chunks_added: int
    elapsed_seconds: float
```

### 24.7. Notion Connector

**Новый файл:** `src/pdf_framework/tools/connector_notion.py`

```python
class NotionConnector:
    """Sync Notion pages/databases to local knowledge base."""

    def __init__(
        self,
        api_key: str,
        database_id: str = "",
    ):
        ...

    async def list_pages(self, database_id: str = "") -> list[NotionPage]:
        """List pages from Notion database."""

    async def get_page_content(self, page_id: str) -> str:
        """Get page content as plain text."""

    async def sync_to_index(
        self,
        components: Components,
        database_id: str,
        incremental: bool = True,
    ) -> SyncResult:
        """Sync Notion database pages to vector store."""
```

### 24.8. MCP SSE Transport

**Новый файл:** `src/mcp_server/sse_transport.py`

```python
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route

class MCPSSEServer:
    """MCP Server with SSE transport for web clients.

    Allows connecting to MCP server via HTTP/SSE
    instead of stdio (for browser-based clients).
    """

    def __init__(self, server: Server, port: int = 8001):
        self._server = server
        self._port = port

    def create_app(self) -> Starlette:
        """Create Starlette app for SSE transport."""
        sse = SseServerTransport("/messages")

        async def handle_sse(request):
            async with sse.connect_sse(
                request.scope, request.receive, request._send
            ) as streams:
                await self._server.run(
                    streams[0], streams[1],
                    self._server.create_initialization_options(),
                )

        async def handle_messages(request):
            await sse.handle_post_message(
                request.scope, request.receive, request._send
            )

        return Starlette(
            routes=[
                Route("/sse", endpoint=handle_sse),
                Route("/messages", endpoint=handle_messages, methods=["POST"]),
            ],
        )

    async def start(self) -> None:
        import uvicorn
        app = self.create_app()
        await uvicorn.Server(
            uvicorn.Config(app, host="0.0.0.0", port=self._port)
        ).serve()
```

### 24.9. CLI команды

**Модификация:** `src/cli/main.py`

```bash
# Запуск MCP сервера (stdio)
pdf-framework mcp serve

# Запуск MCP сервера (SSE)
pdf-framework mcp serve --transport sse --port 8001

# Синхронизация Confluence
pdf-framework sync confluence --space "1C_DOCS" --url https://company.atlassian.net

# Синхронизация Notion
pdf-framework sync notion --database "abc123..."

# Web search test
pdf-framework web-search "1С регистры сведений примеры"
```

---

## Модифицируемые файлы

| Файл | Изменение |
|------|-----------|
| `src/mcp_server/server.py` | **MAJOR MODIFY**: +resources, +prompts, +enhanced tools |
| `src/mcp_server/sse_transport.py` | **NEW**: SSE transport for web clients |
| `src/pdf_framework/tools/web_search.py` | **NEW**: Web search tool (Tavily) |
| `src/pdf_framework/tools/connector_1c.py` | **NEW**: 1С:Предприятие HTTP connector |
| `src/pdf_framework/tools/connector_confluence.py` | **NEW**: Confluence connector |
| `src/pdf_framework/tools/connector_notion.py` | **NEW**: Notion connector |
| `src/cli/main.py` | **MODIFY**: +`mcp serve`, +`sync`, +`web-search` |
| `src/pdf_framework/config.py` | **MODIFY**: +MCPSettings, +ConnectorSettings |
| `src/api/dependencies/components.py` | **MODIFY**: +WebSearchTool, +connectors DI |
| `pyproject.toml` | **MODIFY**: +`tavily-python`, +`atlassian-python-api`, +`notion-client`, +`httpx` |

## Настройки

```python
class MCPSettings(BaseSettings):
    transport: Literal["stdio", "sse"] = "stdio"
    sse_port: int = 8001
    enable_resources: bool = True
    enable_prompts: bool = True

class ConnectorSettings(BaseSettings):
    # Web Search
    web_search_enabled: bool = False
    web_search_provider: Literal["tavily", "serpapi", "brave"] = "tavily"
    web_search_api_key: str = ""
    web_search_default_domain: str = ""     # e.g., "its.1c.ru"

    # 1С:Предприятие
    onec_enabled: bool = False
    onec_base_url: str = ""
    onec_username: str = ""
    onec_password: str = ""
    onec_auth_type: Literal["basic", "ntlm"] = "basic"

    # Confluence
    confluence_enabled: bool = False
    confluence_url: str = ""
    confluence_username: str = ""
    confluence_api_token: str = ""
    confluence_space_key: str = ""

    # Notion
    notion_enabled: bool = False
    notion_api_key: str = ""
    notion_database_id: str = ""
```

## Зависимости

```toml
[project.optional-dependencies]
connectors = [
    "tavily-python>=0.3.0",
    "atlassian-python-api>=3.41.0",
    "notion-client>=2.2.0",
    "httpx>=0.27.0",
]
```

## Порядок реализации

1. Enhanced MCP tools (расширить search, add batch) — максимальная отдача
2. MCP Resources + Prompts — улучшение UX для Claude Code
3. Web search integration — дополнение контекста из интернета
4. SSE transport — для веб-клиентов
5. Confluence connector — корпоративная интеграция
6. 1С API connector — прямой доступ к данным
7. Notion connector — дополнительный источник знаний

## Верификация

1. MCP tools: `search` с strategy="adaptive" → результаты
2. MCP resources: `documents://list` → JSON со списком документов
3. MCP prompts: `search-1c` topic="регистры" → сформированный промпт
4. Web search: запрос → результаты из Tavily с domain filter
5. Confluence sync: 10 страниц → проиндексированы → доступны в поиске
6. SSE transport: подключение из браузера → работающий MCP клиент
7. Claude Code: MCP server подключён → все tools и resources видны
