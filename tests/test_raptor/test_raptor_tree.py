"""Tests for RAPTOR Tree Builder (Phase 13.1)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pdf_framework.processing.raptor import (
    TreeNode,
    RAPTORTree,
    RAPTORTreeBuilder,
    get_raptor_builder,
)

# ChatAnthropic is imported lazily inside methods, patch at source
PATCH_CHAT = "langchain_anthropic.ChatAnthropic"


# ---------------------------------------------------------------------------
# TreeNode model
# ---------------------------------------------------------------------------

class TestTreeNode:
    def test_defaults(self):
        node = TreeNode(id="n1", content="hello", level=0)
        assert node.id == "n1"
        assert node.content == "hello"
        assert node.level == 0
        assert node.children_ids == []
        assert node.embedding is None
        assert node.cluster_id is None
        assert node.metadata == {}

    def test_is_leaf_at_level_zero(self):
        node = TreeNode(id="n1", content="x", level=0)
        assert node.is_leaf is True

    def test_is_not_leaf_at_higher_level(self):
        node = TreeNode(id="n1", content="x", level=1)
        assert node.is_leaf is False

    def test_is_root_for_summary_with_children(self):
        node = TreeNode(id="s1", content="summary", level=2, children_ids=["a", "b"])
        assert node.is_root is True

    def test_is_not_root_for_leaf(self):
        node = TreeNode(id="n1", content="x", level=0)
        assert node.is_root is False

    def test_is_not_root_for_summary_without_children(self):
        node = TreeNode(id="s1", content="summary", level=1, children_ids=[])
        assert node.is_root is False

    def test_with_embedding(self):
        emb = [0.1, 0.2, 0.3]
        node = TreeNode(id="n1", content="x", level=0, embedding=emb)
        assert node.embedding == emb

    def test_with_cluster_id(self):
        node = TreeNode(id="n1", content="x", level=1, cluster_id=3)
        assert node.cluster_id == 3

    def test_with_metadata(self):
        node = TreeNode(id="n1", content="x", level=0, metadata={"key": "val"})
        assert node.metadata["key"] == "val"


# ---------------------------------------------------------------------------
# RAPTORTree model
# ---------------------------------------------------------------------------

class TestRAPTORTree:
    def _make_tree(self):
        leaves = [
            TreeNode(id="L0_0", content="chunk0", level=0),
            TreeNode(id="L0_1", content="chunk1", level=0),
            TreeNode(id="L0_2", content="chunk2", level=0),
        ]
        summaries = [
            TreeNode(
                id="L1_c0", content="summary0", level=1,
                children_ids=["L0_0", "L0_1"],
            ),
            TreeNode(
                id="L1_c1", content="summary1", level=1,
                children_ids=["L0_2"],
            ),
        ]
        tree = RAPTORTree(
            levels=[leaves, summaries],
            root_summaries=["summary0", "summary1"],
            document_id="doc1",
            total_nodes=5,
            max_level=1,
        )
        return tree

    def test_leaf_count(self):
        tree = self._make_tree()
        assert tree.leaf_count == 3

    def test_leaf_count_empty(self):
        tree = RAPTORTree()
        assert tree.leaf_count == 0

    def test_get_level(self):
        tree = self._make_tree()
        assert len(tree.get_level(0)) == 3
        assert len(tree.get_level(1)) == 2

    def test_get_level_out_of_range(self):
        tree = self._make_tree()
        assert tree.get_level(99) == []

    def test_get_node_found(self):
        tree = self._make_tree()
        node = tree.get_node("L0_1")
        assert node is not None
        assert node.content == "chunk1"

    def test_get_node_not_found(self):
        tree = self._make_tree()
        assert tree.get_node("nonexistent") is None

    def test_get_leaves_for_summary(self):
        tree = self._make_tree()
        leaves = tree.get_leaves_for_summary("L1_c0")
        assert len(leaves) == 2
        assert {l.id for l in leaves} == {"L0_0", "L0_1"}

    def test_get_leaves_for_leaf(self):
        tree = self._make_tree()
        leaves = tree.get_leaves_for_summary("L0_0")
        assert len(leaves) == 1
        assert leaves[0].id == "L0_0"

    def test_get_leaves_for_nonexistent(self):
        tree = self._make_tree()
        assert tree.get_leaves_for_summary("nonexistent") == []


# ---------------------------------------------------------------------------
# RAPTORTreeBuilder
# ---------------------------------------------------------------------------

class TestRAPTORTreeBuilder:
    def test_init_defaults(self):
        builder = RAPTORTreeBuilder()
        assert builder._max_levels == 4
        assert builder._min_clusters == 2

    def test_init_custom(self):
        builder = RAPTORTreeBuilder(
            max_levels=2, min_clusters=3,
            summarization_model="custom-model",
            api_key="key123",
        )
        assert builder._max_levels == 2
        assert builder._min_clusters == 3
        assert builder._summarization_model == "custom-model"
        assert builder._api_key == "key123"

    def test_chunks_to_nodes(self):
        builder = RAPTORTreeBuilder()
        chunks = [
            {"content": "Hello", "metadata": {"page": 1}},
            {"content": "World", "metadata": {"page": 2}},
        ]
        embeddings = [[0.1, 0.2], [0.3, 0.4]]
        nodes = builder._chunks_to_nodes(chunks, embeddings, level=0)
        assert len(nodes) == 2
        assert nodes[0].id == "raptor_L0_0"
        assert nodes[0].content == "Hello"
        assert nodes[0].level == 0
        assert nodes[0].embedding == [0.1, 0.2]
        assert nodes[1].metadata == {"page": 2}

    def test_group_by_cluster(self):
        builder = RAPTORTreeBuilder()
        nodes = [
            TreeNode(id="a", content="x", level=0),
            TreeNode(id="b", content="y", level=0),
            TreeNode(id="c", content="z", level=0),
        ]
        labels = [0, 1, 0]
        clusters = builder._group_by_cluster(nodes, labels)
        assert len(clusters) == 2
        assert len(clusters[0]) == 2
        assert len(clusters[1]) == 1
        assert clusters[0][0].id == "a"
        assert clusters[0][1].id == "c"

    @pytest.mark.asyncio
    async def test_embed_text_returns_384_floats(self):
        builder = RAPTORTreeBuilder()
        emb = await builder._embed_text("test text")
        assert len(emb) == 384
        assert all(isinstance(v, float) for v in emb)

    @pytest.mark.asyncio
    async def test_embed_text_deterministic(self):
        builder = RAPTORTreeBuilder()
        emb1 = await builder._embed_text("same text")
        emb2 = await builder._embed_text("same text")
        assert emb1 == emb2

    @pytest.mark.asyncio
    async def test_embed_text_different_inputs(self):
        builder = RAPTORTreeBuilder()
        emb1 = await builder._embed_text("text a")
        emb2 = await builder._embed_text("text b")
        assert emb1 != emb2

    @pytest.mark.asyncio
    async def test_summarize_cluster_empty(self):
        builder = RAPTORTreeBuilder()
        result = await builder._summarize_cluster([], level=1, cluster_id=0, document_id="doc1")
        assert result is None

    @pytest.mark.asyncio
    async def test_generate_summary_handles_error(self):
        builder = RAPTORTreeBuilder(api_key="")
        # Without valid API key, should return empty string gracefully
        with patch(PATCH_CHAT) as mock_cls:
            mock_cls.side_effect = Exception("API error")
            result = await builder._generate_summary("some context", "doc1")
        assert isinstance(result, str)
        assert result == ""

    @pytest.mark.asyncio
    async def test_build_creates_leaf_level(self):
        """Test build with min_clusters set high to avoid clustering."""
        builder = RAPTORTreeBuilder(max_levels=1, min_clusters=5)
        chunks = [{"content": f"chunk {i}", "metadata": {}} for i in range(3)]
        embeddings = [[float(i)] * 10 for i in range(3)]

        tree = await builder.build(chunks, embeddings, document_id="doc1")

        # With min_clusters=5 and only 3 chunks, should only have level 0
        assert len(tree.levels) >= 1
        assert tree.levels[0][0].content == "chunk 0"
        assert tree.document_id == "doc1"
        assert tree.total_nodes >= 3

    @pytest.mark.asyncio
    async def test_summarize_cluster_with_mock_llm(self):
        """Test cluster summarization with mocked LLM."""
        builder = RAPTORTreeBuilder(api_key="test-key")

        nodes = [
            TreeNode(id="n0", content="First passage about AI", level=0),
            TreeNode(id="n1", content="Second passage about ML", level=0),
        ]

        mock_response = MagicMock()
        mock_response.content = "Summary of AI and ML passages."

        with patch(PATCH_CHAT) as mock_cls:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_llm

            result = await builder._summarize_cluster(nodes, level=1, cluster_id=0, document_id="doc")

        assert result is not None
        assert result.content == "Summary of AI and ML passages."
        assert result.level == 1
        assert result.id == "raptor_L1_cluster0"
        assert "n0" in result.children_ids
        assert "n1" in result.children_ids

    @pytest.mark.asyncio
    async def test_generate_summary_handles_list_content(self):
        """Test that list content from LangChain is handled correctly."""
        builder = RAPTORTreeBuilder(api_key="test-key")

        # Simulate LangChain returning list[ContentBlock]
        mock_block = MagicMock()
        mock_block.text = "Summary text from block"

        mock_response = MagicMock()
        mock_response.content = [mock_block]

        with patch(PATCH_CHAT) as mock_cls:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_response)
            mock_cls.return_value = mock_llm

            result = await builder._generate_summary("context", "doc1")

        assert result == "Summary text from block"


# ---------------------------------------------------------------------------
# get_raptor_builder singleton
# ---------------------------------------------------------------------------

class TestGetRaptorBuilder:
    def test_returns_instance(self):
        import src.pdf_framework.processing.raptor as mod
        mod._raptor_builder = None

        builder = get_raptor_builder()
        assert isinstance(builder, RAPTORTreeBuilder)
        mod._raptor_builder = None

    def test_returns_same_instance(self):
        import src.pdf_framework.processing.raptor as mod
        mod._raptor_builder = None

        b1 = get_raptor_builder()
        b2 = get_raptor_builder()
        assert b1 is b2
        mod._raptor_builder = None

    def test_accepts_kwargs(self):
        import src.pdf_framework.processing.raptor as mod
        mod._raptor_builder = None

        builder = get_raptor_builder(max_levels=2, api_key="key")
        assert builder._max_levels == 2
        assert builder._api_key == "key"
        mod._raptor_builder = None
