"""Community Summarization for GraphRAG.

Generates LLM-based summaries for each detected community,
describing the main themes and relationships.

Author: Claude Code
Version: 0.7.0 - Phase 6.2: Community Summaries
"""

import logging
from typing import Any

import networkx as nx
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser

from src.pdf_framework.config import GraphRAGSettings
from src.pdf_framework.schemas.entities import Entity, Relation

logger = logging.getLogger(__name__)


class CommunitySummarizer:
    """
    Generate summaries for communities in the knowledge graph.

    Each community summary describes:
    - Main entities in the community
    - Key relationships between them
    - Thematic focus of the cluster
    """

    def __init__(
        self,
        llm: ChatAnthropic | None = None,
        settings: GraphRAGSettings | None = None,
        api_key: str = "",
        base_url: str = "",
    ):
        """
        Initialize community summarizer.

        Args:
            llm: LLM for summary generation (default: Haiku for speed)
            settings: GraphRAG configuration
            api_key: Anthropic API key
            base_url: Custom API endpoint (for Z.AI or other proxies)
        """
        if llm is None:
            llm_kwargs = dict(
                model="claude-haiku-4-5-20251001",
                temperature=0.0,
                max_tokens=1024,
            )
            if api_key:
                llm_kwargs["api_key"] = api_key
            if base_url:
                llm_kwargs["base_url"] = base_url
            llm = ChatAnthropic(**llm_kwargs)
        self.llm = llm
        self.settings = settings or GraphRAGSettings()
        self.parser = StrOutputParser()

        # Cache for summaries (community_id -> summary)
        self._summary_cache: dict[str, str] = {}

    async def summarize(
        self,
        entities: list[Entity],
        relations: list[Relation],
        community_id: int,
        level: int = 0,
    ) -> str:
        """
        Generate a summary for a single community.

        Args:
            entities: List of entities in the community
            relations: List of relations between entities
            community_id: Community identifier
            level: Hierarchy level

        Returns:
            Community summary text
        """
        cache_key = f"{community_id}_L{level}"
        if cache_key in self._summary_cache and self.settings.summary_cache_enabled:
            logger.debug(f"[SUMMARY] Cache hit for {cache_key}")
            return self._summary_cache[cache_key]

        if not entities:
            summary = f"Community {community_id} (level {level}) has no entities."
            self._summary_cache[cache_key] = summary
            return summary

        # Build prompt
        prompt = self._build_summary_prompt(entities, relations, community_id, level)

        messages = [
            SystemMessage(content=self._get_system_prompt()),
            HumanMessage(content=prompt),
        ]

        # Ralph Wiggum: self-correcting retry for community summaries
        entity_names = [e.name for e in entities[:5]]
        rw_feedback = ""

        for rw_attempt in range(1, 3):  # max 2 attempts
            try:
                attempt_messages = list(messages)
                if rw_feedback:
                    attempt_messages.append(HumanMessage(content=f"\u26a0\ufe0f {rw_feedback}"))

                response = await self.llm.ainvoke(attempt_messages)
                summary = self.parser.invoke(response).strip()

                # Validate: non-empty and mentions at least one entity
                if len(summary) < 30:
                    rw_feedback = (
                        f"Summary must be 2-4 sentences. Mention key entities: "
                        f"{', '.join(entity_names)}."
                    )
                    logger.warning(f"[SUMMARY] Attempt {rw_attempt}: too short ({len(summary)} chars)")
                    continue

                formatted_summary = f"[Community {community_id} (level {level})] {summary}"
                self._summary_cache[cache_key] = formatted_summary
                logger.info(
                    f"[SUMMARY] Generated summary for community {community_id} "
                    f"({len(entities)} entities, {len(relations)} relations)"
                )
                return formatted_summary

            except Exception as e:
                logger.error(f"[SUMMARY] Attempt {rw_attempt} error for {cache_key}: {e}")
                rw_feedback = f"Previous call failed: {e}."

        # Fallback summary
        fallback = (
            f"[Community {community_id} (level {level})] "
            f"Contains {len(entities)} entities focused on related topics. "
            f"Main entities: {', '.join(e.name for e in entities[:5])}"
        )
        return fallback

    async def summarize_all(
        self,
        graph: nx.DiGraph,
        communities: dict[str, int],
        level: int = 0,
    ) -> dict[int, str]:
        """
        Generate summaries for all communities.

        Args:
            graph: NetworkX graph with community attributes
            communities: entity_id -> community_id mapping
            level: Hierarchy level

        Returns:
            Dictionary mapping community_id -> summary
        """
        # Group entities by community
        community_entities: dict[int, list[Entity]] = {}
        community_relations: dict[int, list[Relation]] = {}

        # Initialize for all community IDs
        for comm_id in set(communities.values()):
            community_entities[comm_id] = []
            community_relations[comm_id] = []

        # Extract entities and relations per community
        for entity_id, comm_id in communities.items():
            if entity_id in graph.nodes:
                node_data = graph.nodes[entity_id]
                entity = Entity(
                    id=entity_id,
                    name=node_data.get("name", ""),
                    entity_type=node_data.get("entity_type", ""),
                    properties=node_data.get("properties", {}),
                    source_document_id=node_data.get("source_document_id", ""),
                    source_chunk_ids=node_data.get("source_chunk_ids", []),
                    confidence=node_data.get("confidence", 1.0),
                )
                community_entities[comm_id].append(entity)

        # Extract relations within each community
        for comm_id, entities_list in community_entities.items():
            entity_ids = {e.id for e in entities_list}
            for src, tgt, edge_data in graph.edges(data=True):
                if src in entity_ids and tgt in entity_ids:
                    community_relations[comm_id].append(
                        Relation(
                            id=edge_data.get("id", ""),
                            source_entity_id=src,
                            target_entity_id=tgt,
                            relation_type=edge_data.get("relation_type", ""),
                            properties=edge_data.get("properties", {}),
                            confidence=edge_data.get("confidence", 1.0),
                            source_chunk_id=edge_data.get("source_chunk_id", ""),
                        )
                    )

        # Generate summaries for each community
        summaries = {}
        for comm_id in sorted(community_entities.keys()):
            entities_list = community_entities[comm_id]
            relations_list = community_relations[comm_id]

            summary = await self.summarize(entities_list, relations_list, comm_id, level)
            summaries[comm_id] = summary

        logger.info(f"[SUMMARY] Generated {len(summaries)} community summaries for level {level}")

        return summaries

    def _build_summary_prompt(
        self,
        entities: list[Entity],
        relations: list[Relation],
        community_id: int,
        level: int,
    ) -> str:
        """Build the LLM prompt for community summarization."""
        # Format entities
        entity_desc = "\n".join(
            f"- {e.name} ({e.entity_type})"
            for e in entities[:20]  # Limit to prevent huge prompts
        )

        # Format relations
        relation_desc = "\n".join(
            f"- {r.source_entity_id} --[{r.relation_type}]--> {r.target_entity_id}"
            for r in relations[:20]
        )

        return f"""Analyze this community of entities and their relationships.

Entities ({len(entities)}):
{entity_desc}

Relations ({len(relations)}):
{relation_desc}

Provide a 2-3 sentence summary describing:
1. The main theme or topic of this community
2. Key relationships between entities
3. What makes this group of entities cohesive

Focus on the thematic connections, not just listing items."""

    def _get_system_prompt(self) -> str:
        """Get the system prompt for community summarization."""
        return """You are an expert at analyzing knowledge graphs and identifying thematic clusters.

Your task is to summarize a community of entities by:
1. Identifying the central theme or topic
2. Describing how the entities relate to each other
3. Explaining what makes this cluster cohesive

Keep your summary concise (2-3 sentences) and focused on the thematic connections.
Avoid simply listing entities - describe the patterns and relationships."""

    def clear_cache(self) -> None:
        """Clear the summary cache."""
        self._summary_cache.clear()
        logger.info("[SUMMARY] Cache cleared")

    def get_cached_summary(self, community_id: int, level: int = 0) -> str | None:
        """Get a cached summary if available."""
        cache_key = f"{community_id}_L{level}"
        return self._summary_cache.get(cache_key)
