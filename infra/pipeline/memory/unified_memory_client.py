"""
Unified Memory Client for Development Pipeline.

Sprint 3.3.1: Integration with unified-memory-mcp

This module provides a client interface for interacting with the
unified-memory MCP server to store and retrieve memory entries.
"""

import json
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable
from enum import Enum
from pathlib import Path

from models import (
    MemoryEntry,
    MemoryType,
    Pattern,
    ErrorRecord,
    Recommendation,
    LearningContext,
)


logger = logging.getLogger(__name__)


class SearchMode(Enum):
    """Search mode for memory queries."""
    SEMANTIC = "semantic"
    FULLTEXT = "fulltext"
    HYBRID = "hybrid"
    GRAPH = "graph"


@dataclass
class MemoryConfig:
    """Configuration for Unified Memory Client."""

    # MCP server settings
    server_name: str = "unified-memory"
    timeout_seconds: int = 30

    # Default memory settings
    default_importance: float = 0.5
    default_memory_type: str = "general"

    # Search settings
    default_search_mode: SearchMode = SearchMode.HYBRID
    default_search_limit: int = 10
    min_search_score: float = 0.5

    # Cache settings
    enable_cache: bool = True
    cache_ttl_seconds: int = 300
    max_cache_size: int = 1000

    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: float = 1.0

    # Project context
    project_id: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class SearchResult:
    """Result from memory search."""

    id: str
    content: str
    memory_type: str
    score: float
    importance: float
    created_at: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchResult":
        """Create SearchResult from dictionary."""
        return cls(
            id=data.get("id", ""),
            content=data.get("content", ""),
            memory_type=data.get("memory_type", "general"),
            score=data.get("score", 0.0),
            importance=data.get("importance", 0.5),
            created_at=data.get("created_at", ""),
            metadata=data.get("metadata", {}),
            tags=data.get("tags", []),
        )


@dataclass
class SaveResult:
    """Result from memory save operation."""

    success: bool
    memory_id: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None


class MemoryCache:
    """Simple in-memory cache for memory entries."""

    def __init__(self, ttl_seconds: int = 300, max_size: int = 1000) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_size = max_size
        self._cache: Dict[str, tuple[Any, datetime]] = {}

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            age = (datetime.now() - timestamp).total_seconds()
            if age < self.ttl_seconds:
                return value
            else:
                del self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Set value in cache."""
        # Evict oldest entries if cache is full
        if len(self._cache) >= self.max_size:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][1])
            del self._cache[oldest_key]

        self._cache[key] = (value, datetime.now())

    def invalidate(self, key: str) -> None:
        """Invalidate cache entry."""
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()


class UnifiedMemoryClient:
    """
    Client for interacting with unified-memory MCP server.

    This client provides a high-level interface for:
    - Saving memories (patterns, errors, recommendations)
    - Searching memories with semantic/hybrid search
    - Managing memory context and sessions
    - Analyzing dependencies in the knowledge graph

    Usage:
        client = UnifiedMemoryClient(config)

        # Save a memory
        result = await client.save_memory(
            content="Pattern: Always validate input in API handlers",
            memory_type=MemoryType.PATTERN,
            importance=0.8,
            tags=["validation", "api"]
        )

        # Search memories
        results = await client.search_memory(
            query="input validation patterns",
            mode=SearchMode.SEMANTIC,
            limit=5
        )
    """

    def __init__(
        self,
        config: Optional[MemoryConfig] = None,
        mcp_caller: Optional[Callable] = None,
    ):
        """
        Initialize Unified Memory Client.

        Args:
            config: Client configuration
            mcp_caller: Optional callable for MCP tool invocation
                       (for testing/mocking)
        """
        self.config = config or MemoryConfig()
        self._mcp_caller = mcp_caller

        # Initialize cache
        self._cache = MemoryCache(
            ttl_seconds=self.config.cache_ttl_seconds,
            max_size=self.config.max_cache_size,
        ) if self.config.enable_cache else None

        # Session state
        self._session_id = self.config.session_id or self._generate_session_id()
        self._project_id = self.config.project_id

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        return f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    async def _call_mcp(
        self,
        tool_name: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Call MCP tool with retry logic.

        Args:
            tool_name: Name of the MCP tool (without prefix)
            params: Tool parameters

        Returns:
            Tool response as dictionary
        """
        full_tool_name = f"mcp__unified-memory__{tool_name}"

        for attempt in range(self.config.max_retries):
            try:
                if self._mcp_caller:
                    # Use provided caller (for testing)
                    result = await self._mcp_caller(full_tool_name, params)
                else:
                    # In production, this would call the actual MCP tool
                    # For now, return mock response
                    logger.warning(
                        f"MCP caller not configured, returning mock for {tool_name}"
                    )
                    result = self._mock_mcp_response(tool_name, params)

                return result

            except Exception as e:
                logger.warning(
                    f"MCP call attempt {attempt + 1} failed: {e}"
                )
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(
                        self.config.retry_delay_seconds * (attempt + 1)
                    )
                else:
                    raise

        return {}

    def _mock_mcp_response(
        self,
        tool_name: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate mock MCP response for testing."""
        if tool_name == "save_memory":
            return {
                "success": True,
                "id": f"mem_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "message": "Memory saved successfully",
            }
        elif tool_name == "search_memory":
            return {
                "results": [],
                "total": 0,
                "mode": params.get("mode", "hybrid"),
            }
        elif tool_name == "health_check":
            return {
                "status": "healthy",
                "backends": {
                    "vector": True,
                    "graph": True,
                    "cache": True,
                },
            }
        elif tool_name == "get_context":
            return {
                "session_id": self._session_id,
                "entries": [],
            }
        elif tool_name == "analyze_dependencies":
            return {
                "entity": params.get("entity_name", ""),
                "dependencies": [],
                "dependents": [],
            }
        else:
            return {"success": True}

    async def save_memory(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.GENERAL,
        importance: Optional[float] = None,
        tags: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> SaveResult:
        """
        Save content to unified memory.

        Args:
            content: Text content to save
            memory_type: Type of memory
            importance: Importance score (0.0 to 1.0)
            tags: Optional tags for categorization
            context: Optional additional context

        Returns:
            SaveResult with success status and memory ID
        """
        params = {
            "content": content,
            "memory_type": memory_type.value,
            "importance": importance or self.config.default_importance,
            "tags": tags or [],
            "context": context or {},
        }

        # Add session context
        if self._session_id:
            params["context"]["session_id"] = self._session_id
        if self._project_id:
            params["context"]["project_id"] = self._project_id

        try:
            result = await self._call_mcp("save_memory", params)

            return SaveResult(
                success=result.get("success", False),
                memory_id=result.get("id"),
                message=result.get("message"),
            )

        except Exception as e:
            logger.error(f"Failed to save memory: {e}")
            return SaveResult(
                success=False,
                error=str(e),
            )

    async def save_pattern(self, pattern: Pattern) -> SaveResult:
        """
        Save a pattern to memory.

        Args:
            pattern: Pattern object to save

        Returns:
            SaveResult with success status
        """
        entry = pattern.to_memory_entry()
        entry.session_id = self._session_id

        return await self.save_memory(
            content=entry.content,
            memory_type=MemoryType.PATTERN,
            importance=entry.importance,
            tags=entry.tags,
            context=entry.metadata,
        )

    async def save_error(self, error: ErrorRecord) -> SaveResult:
        """
        Save an error record to memory.

        Args:
            error: ErrorRecord object to save

        Returns:
            SaveResult with success status
        """
        entry = error.to_memory_entry()
        entry.session_id = self._session_id

        return await self.save_memory(
            content=entry.content,
            memory_type=MemoryType.ERROR,
            importance=entry.importance,
            tags=entry.tags,
            context=entry.metadata,
        )

    async def save_recommendation(
        self,
        recommendation: Recommendation,
    ) -> SaveResult:
        """
        Save a recommendation to memory.

        Args:
            recommendation: Recommendation object to save

        Returns:
            SaveResult with success status
        """
        # Build content from recommendation fields
        content = f"{recommendation.title}\n\n{recommendation.description}\n\nAction: {recommendation.action}\nRationale: {recommendation.rationale}\nExpected benefit: {recommendation.expected_benefit}"

        return await self.save_memory(
            content=content,
            memory_type=MemoryType.RECOMMENDATION,
            importance=recommendation.confidence,
            tags=recommendation.tags,
            context=recommendation.to_dict(),
        )

    async def search_memory(
        self,
        query: str,
        mode: Optional[SearchMode] = None,
        memory_type: Optional[MemoryType] = None,
        limit: Optional[int] = None,
        min_score: Optional[float] = None,
        code_only: bool = False,
        entity_only: bool = False,
    ) -> List[SearchResult]:
        """
        Search memory with intelligent aggregation.

        Args:
            query: Search query
            mode: Search mode (semantic, fulltext, hybrid, graph)
            memory_type: Filter by memory type
            limit: Maximum results to return
            min_score: Minimum relevance score
            code_only: Search only code memories
            entity_only: Search only entity memories

        Returns:
            List of SearchResult objects
        """
        # Check cache
        cache_key = f"search:{query}:{mode}:{memory_type}:{limit}"
        if self._cache:
            cached = self._cache.get(cache_key)
            if cached:
                return cached

        params = {
            "query": query,
            "mode": (mode or self.config.default_search_mode).value,
            "limit": limit or self.config.default_search_limit,
            "min_importance": min_score or self.config.min_search_score,
            "code_only": code_only,
            "entity_only": entity_only,
        }

        if memory_type:
            params["memory_type"] = memory_type.value

        try:
            result = await self._call_mcp("search_memory", params)

            results = [
                SearchResult.from_dict(r)
                for r in result.get("results", [])
            ]

            # Cache results
            if self._cache:
                self._cache.set(cache_key, results)

            return results

        except Exception as e:
            logger.error(f"Failed to search memory: {e}")
            return []

    async def search_patterns(
        self,
        query: str,
        limit: int = 10,
    ) -> List[SearchResult]:
        """Search for patterns in memory."""
        return await self.search_memory(
            query=query,
            memory_type=MemoryType.PATTERN,
            limit=limit,
        )

    async def search_errors(
        self,
        query: str,
        limit: int = 10,
    ) -> List[SearchResult]:
        """Search for error records in memory."""
        return await self.search_memory(
            query=query,
            memory_type=MemoryType.ERROR,
            limit=limit,
        )

    async def get_context(
        self,
        session_id: Optional[str] = None,
        depth: int = 3,
        include_related: bool = True,
    ) -> Dict[str, Any]:
        """
        Get context for current or specific session.

        Args:
            session_id: Session ID (uses current if not specified)
            depth: Context depth
            include_related: Include related entries

        Returns:
            Context dictionary with relevant entries
        """
        params = {
            "session_id": session_id or self._session_id,
            "depth": depth,
            "include_related": include_related,
        }

        try:
            return await self._call_mcp("get_context", params)
        except Exception as e:
            logger.error(f"Failed to get context: {e}")
            return {}

    async def analyze_dependencies(
        self,
        entity_name: str,
        analysis_type: str = "dependencies",
    ) -> Dict[str, Any]:
        """
        Analyze dependencies for an entity.

        Args:
            entity_name: Name of the entity to analyze
            analysis_type: Type of analysis (dependencies, centrality, communities)

        Returns:
            Analysis results dictionary
        """
        params = {
            "entity_name": entity_name,
            "analysis_type": analysis_type,
        }

        try:
            return await self._call_mcp("analyze_dependencies", params)
        except Exception as e:
            logger.error(f"Failed to analyze dependencies: {e}")
            return {}

    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of all memory backends.

        Returns:
            Health status dictionary
        """
        try:
            return await self._call_mcp("health_check", {})
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {"status": "error", "error": str(e)}

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get memory statistics.

        Returns:
            Statistics dictionary
        """
        try:
            return await self._call_mcp("get_memory_stats", {})
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}

    def set_project_context(
        self,
        project_id: str,
        session_id: Optional[str] = None,
    ) -> None:
        """
        Set project context for memory operations.

        Args:
            project_id: Project identifier
            session_id: Optional session ID
        """
        self._project_id = project_id
        if session_id:
            self._session_id = session_id

        # Invalidate cache when context changes
        if self._cache:
            self._cache.clear()

    def get_learning_context(self) -> LearningContext:
        """
        Get current learning context.

        Returns:
            LearningContext object
        """
        return LearningContext(
            project_id=self._project_id or "",
            session_id=self._session_id,
        )

    @property
    def session_id(self) -> str:
        """Get current session ID."""
        return self._session_id

    @property
    def project_id(self) -> Optional[str]:
        """Get current project ID."""
        return self._project_id
