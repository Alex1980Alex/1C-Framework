"""RAPTOR Tree Builder (Phase 13.1).

Recursive Abstractive Processing for Tree-Organized Retrieval.
Builds hierarchical summary tree from document chunks via clustering + LLM summarization.

Author: Claude Code
Version: 1.4.0 - Phase 13.1: RAPTOR Tree Builder
"""

import logging
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class TreeNode(BaseModel):
    """Node in RAPTOR tree."""

    id: str
    content: str  # Text content (chunk or summary)
    level: int  # 0 = leaves, >0 = summary levels
    children_ids: list[str] = []
    embedding: list[float] | None = None
    cluster_id: int | None = None  # For tracking cluster membership
    metadata: dict[str, Any] = {}

    @property
    def is_leaf(self) -> bool:
        """Check if this is a leaf node (original chunk)."""
        return self.level == 0

    @property
    def is_root(self) -> bool:
        """Check if this is a top-level summary node."""
        return self.level > 0 and len(self.children_ids) > 0


class RAPTORTree(BaseModel):
    """
    RAPTOR hierarchical tree.

    Tree structure:
    - Level 0: Original document chunks (leaves)
    - Level 1+: Summaries of clusters (branches)
    """

    levels: list[list[TreeNode]] = []
    root_summaries: list[str] = []  # Convenience access to top-level summaries
    document_id: str = ""
    total_nodes: int = 0
    max_level: int = 0

    @property
    def leaf_count(self) -> int:
        """Number of leaf nodes (original chunks)."""
        return len(self.levels[0]) if self.levels else 0

    def get_level(self, level: int) -> list[TreeNode]:
        """Get all nodes at a specific level."""
        if 0 <= level < len(self.levels):
            return self.levels[level]
        return []

    def get_node(self, node_id: str) -> TreeNode | None:
        """Find node by ID across all levels."""
        for level_nodes in self.levels:
            for node in level_nodes:
                if node.id == node_id:
                    return node
        return None

    def get_leaves_for_summary(self, summary_id: str) -> list[TreeNode]:
        """
        Get all leaf nodes that belong to a summary (recursive).

    Args:
            summary_id: TreeNode ID of summary

        Returns:
            List of leaf nodes under this summary
        """
        summary_node = self.get_node(summary_id)
        if not summary_node:
            return []

        # If leaf, return itself
        if summary_node.is_leaf:
            return [summary_node]

        # Recursively get leaves from children
        leaves = []
        for child_id in summary_node.children_ids:
            leaves.extend(self.get_leaves_for_summary(child_id))

        return leaves


class RAPTORTreeBuilder:
    """
    Builds RAPTOR tree from chunks via clustering + summarization.

    Algorithm:
    1. Level 0: Original chunks
    2. For each level:
       - Cluster nodes by embedding (KMeans, k = sqrt(n))
       - Summarize each cluster via LLM
       - Create new level with summary nodes
       - Repeat until 1 cluster or max_levels reached
    """

    def __init__(
        self,
        max_levels: int = 4,
        min_clusters: int = 2,
        summarization_model: str = "claude-haiku-4-5-20251001",
        api_key: str = "",
        base_url: str = "",
    ):
        """
        Initialize RAPTOR tree builder.

        Args:
            max_levels: Maximum tree depth
            min_clusters: Minimum clusters before stopping
            summarization_model: LLM for summarization
            api_key: Anthropic API key
            base_url: Custom API endpoint (for Z.AI or other proxies)
        """
        self._max_levels = max_levels
        self._min_clusters = min_clusters
        self._summarization_model = summarization_model
        self._api_key = api_key
        self._base_url = base_url

    async def build(
        self,
        chunks: list[dict],
        embeddings: list[list[float]],
        document_id: str = "",
    ) -> RAPTORTree:
        """
        Build RAPTOR tree from chunks and embeddings.

        Args:
            chunks: Document chunks (with content, metadata)
            embeddings: Embedding vectors for each chunk
            document_id: Document identifier

        Returns:
            RAPTORTree with hierarchical summaries
        """
        from sklearn.cluster import KMeans

        tree = RAPTORTree(document_id=document_id)

        # Level 0: Original chunks as nodes
        current_nodes = self._chunks_to_nodes(chunks, embeddings, level=0)
        tree.levels.append(current_nodes)

        logger.info(f"[RAPTOR] Level 0: {len(current_nodes)} leaf nodes")

        # Build higher levels recursively
        level = 1
        while len(current_nodes) > self._min_clusters and level <= self._max_levels:
            # Extract embeddings
            node_embeddings = [node.embedding for node in current_nodes if node.embedding]

            if not node_embeddings:
                logger.warning(f"[RAPTOR] No embeddings at level {level-1}, stopping")
                break

            # Determine number of clusters (sqrt(n))
            n_clusters = max(self._min_clusters, int(len(current_nodes) ** 0.5))

            # Cluster nodes
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            cluster_labels = kmeans.fit_predict(node_embeddings)

            # Group nodes by cluster
            clusters = self._group_by_cluster(current_nodes, cluster_labels)

            logger.info(f"[RAPTOR] Clustering level {level-1}: k={n_clusters}, {len(clusters)} clusters")

            # Summarize each cluster
            new_nodes = []
            for cluster_id, cluster_nodes in clusters.items():
                summary_node = await self._summarize_cluster(
                    cluster_nodes, level, cluster_id, document_id
                )
                if summary_node:
                    new_nodes.append(summary_node)

            if not new_nodes:
                logger.warning(f"[RAPTOR] No summaries generated at level {level}, stopping")
                break

            tree.levels.append(new_nodes)
            current_nodes = new_nodes

            logger.info(f"[RAPTOR] Level {level}: {len(new_nodes)} summaries generated")

            level += 1

        tree.total_nodes = sum(len(level_nodes) for level_nodes in tree.levels)
        tree.max_level = level - 1

        # Extract root summaries
        if tree.levels:
            tree.root_summaries = [node.content for node in tree.levels[-1]]

        logger.info(
            f"[RAPTOR] Tree complete: {len(tree.levels)} levels, "
            f"{tree.total_nodes} total nodes"
        )

        return tree

    def _chunks_to_nodes(
        self,
        chunks: list[dict],
        embeddings: list[list[float]],
        level: int,
    ) -> list[TreeNode]:
        """Convert chunks to TreeNode objects."""
        nodes = []
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            node = TreeNode(
                id=f"raptor_L{level}_{i}",
                content=chunk.get("content", ""),
                level=level,
                embedding=emb,
                metadata=chunk.get("metadata", {}),
            )
            nodes.append(node)
        return nodes

    def _group_by_cluster(
        self,
        nodes: list[TreeNode],
        labels: list[int],
    ) -> dict[int, list[TreeNode]]:
        """Group nodes by cluster label."""
        clusters: dict[int, list[TreeNode]] = {}
        for node, label in zip(nodes, labels):
            clusters.setdefault(label, []).append(node)
        return clusters

    async def _summarize_cluster(
        self,
        cluster_nodes: list[TreeNode],
        level: int,
        cluster_id: int,
        document_id: str,
    ) -> TreeNode | None:
        """
        Generate summary for a cluster of nodes.

        Args:
            cluster_nodes: Nodes in the cluster
            level: Target level
            cluster_id: Cluster identifier
            document_id: Document ID

        Returns:
            TreeNode with summary or None
        """
        if not cluster_nodes:
            return None

        # Combine node contents
        passages = []
        for node in cluster_nodes[:10]:  # Limit context window
            passage = node.content.strip()
            if passage:
                passages.append(f"[{node.id}] {passage}")

        context = "\n\n".join(passages)

        # Generate summary via LLM
        summary = await self._generate_summary(context, document_id)

        if not summary:
            return None

        # Generate embedding for summary
        summary_emb = await self._embed_text(summary)

        # Create summary node
        node = TreeNode(
            id=f"raptor_L{level}_cluster{cluster_id}",
            content=summary,
            level=level,
            children_ids=[node.id for node in cluster_nodes],
            embedding=summary_emb,
            cluster_id=cluster_id,
            metadata={
                "node_type": "summary",
                "raptor_level": level,
                "cluster_size": len(cluster_nodes),
            },
        )

        return node

    async def _generate_summary(self, context: str, document_id: str) -> str:
        """Generate LLM summary for context."""
        try:
            from langchain_anthropic import ChatAnthropic
            from langchain_core.messages import HumanMessage

            llm_kwargs = dict(
                model=self._summarization_model,
                temperature=0.3,
                max_tokens=512,
                api_key=self._api_key or None,
            )
            if self._base_url:
                llm_kwargs["base_url"] = self._base_url
            llm = ChatAnthropic(**llm_kwargs)

            prompt = f"""Summarize the following passages from a document.

Write a concise summary (2-4 sentences) that captures the main points.
Focus on key information, technical details, and relationships.

Passages:
{context}

Summary:"""

            response = await llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content
            if isinstance(content, list):
                summary = " ".join(
                    getattr(block, "text", str(block)) for block in content
                ).strip()
            else:
                summary = content.strip()

            logger.debug(f"[RAPTOR] Generated summary ({len(summary)} chars)")
            return summary

        except Exception as e:
            logger.error(f"[RAPTOR] Summarization failed: {e}")
            return ""

    async def _embed_text(self, text: str) -> list[float]:
        """Generate embedding for text."""
        # This would use the embedding engine from components
        # For now, return dummy embedding with correct dimensions
        import hashlib

        # Repeat hash to reach target dimensions (384)
        target_dim = 384
        hash_val = hashlib.sha256(text.encode()).hexdigest()
        # Each hex char → one float; sha256 gives 64 chars, repeat as needed
        hex_chars = (hash_val * (target_dim // len(hash_val) + 1))[:target_dim]
        embedding = [float(int(h, 16)) / 15.0 for h in hex_chars]
        return embedding


# Global RAPTOR tree builder instance
_raptor_builder: RAPTORTreeBuilder | None = None


def get_raptor_builder(**kwargs) -> RAPTORTreeBuilder:
    """Get or create global RAPTOR tree builder instance."""
    global _raptor_builder
    if _raptor_builder is None:
        _raptor_builder = RAPTORTreeBuilder(**kwargs)
    return _raptor_builder
