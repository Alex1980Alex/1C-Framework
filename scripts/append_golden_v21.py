"""One-shot: append 20 new items (gv1-041..060) to golden_v1.json for v2.1.

Each item targets specific code areas known to exist in framework_code_v1
to maximize grounding hit rate. Run grounding script after to populate
expected_chunk_ids.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PATH = REPO / "data" / "eval" / "golden_v1.json"


def main() -> None:
    data = json.loads(PATH.read_text(encoding="utf-8"))

    new_items = [
        {
            "id": "gv1-041",
            "query": "How does Qdrant ID conversion handle string chunk_ids?",
            "difficulty": "medium",
            "category": "procedural",
            "domain": "rag-framework",
            "expected_keywords": ["UUID5", "uuid5", "_to_qdrant_id", "namespace"],
            "expected_answer_summary": "QdrantStore._to_qdrant_id uses deterministic uuid5 with a namespace to convert string chunk_ids to UUIDs; original_id preserved in payload.",
        },
        {
            "id": "gv1-042",
            "query": "How is MMR diversity computed for search results?",
            "difficulty": "medium",
            "category": "procedural",
            "domain": "rag-framework",
            "expected_keywords": ["MMR", "lambda", "diversity", "fetch_k"],
            "expected_answer_summary": "MMR balances relevance vs diversity using lambda; fetches more candidates than k, iteratively selects with diversity penalty.",
        },
        {
            "id": "gv1-043",
            "query": "What does rebuild_sparse_vectors do in QdrantStore?",
            "difficulty": "medium",
            "category": "procedural",
            "domain": "rag-framework",
            "expected_keywords": ["rebuild_sparse_vectors", "BM25", "scroll", "sparse"],
            "expected_answer_summary": "Iterates all points via scroll API, regenerates BM25 sparse vectors from content; idempotent.",
        },
        {
            "id": "gv1-044",
            "query": "How is hybrid search RRF formula implemented?",
            "difficulty": "hard",
            "category": "analytical",
            "domain": "rag-framework",
            "expected_keywords": ["RRF", "Reciprocal Rank Fusion", "fuse"],
            "expected_answer_summary": "RRF combines two ranked lists by summing 1/(k+rank) per item; default k=60; sorted by fused score.",
        },
        {
            "id": "gv1-045",
            "query": "How does smart loader choose between pymupdf and docling?",
            "difficulty": "medium",
            "category": "procedural",
            "domain": "rag-framework",
            "expected_keywords": ["smart", "router", "min_text_chars", "docling", "pymupdf"],
            "expected_answer_summary": "SmartRouter samples PDF pages: text-sparse OR table-heavy -> docling (full pipeline), else fast loader (pymupdf).",
        },
        {
            "id": "gv1-046",
            "query": "How does HybridLoader handle Vision OCR retries?",
            "difficulty": "medium",
            "category": "procedural",
            "domain": "rag-framework",
            "expected_keywords": ["vision_max_retries", "attempt", "OCR", "fallback"],
            "expected_answer_summary": "HybridLoader retries Claude Vision up to vision_max_retries on transient errors, then falls back to next loader tier.",
        },
        {
            "id": "gv1-047",
            "query": "How is incremental indexing implemented?",
            "difficulty": "hard",
            "category": "procedural",
            "domain": "rag-framework",
            "expected_keywords": ["incremental", "mtime", "sha1", "skip"],
            "expected_answer_summary": "IncrementalIndexer checks mtime + sha1 hash; skips unchanged; re-indexes only modified files.",
        },
        {
            "id": "gv1-048",
            "query": "Where is the parent-child chunk relationship stored?",
            "difficulty": "medium",
            "category": "procedural",
            "domain": "rag-framework",
            "expected_keywords": ["ParentStore", "child_id", "parent_id", "merge"],
            "expected_answer_summary": "ParentStore (SQLite) maps child chunk IDs to parent chunks; child retrieved by vector search, parent expanded for context.",
        },
        {
            "id": "gv1-049",
            "query": "What setting controls the TEI client batch size?",
            "difficulty": "easy",
            "category": "factual",
            "domain": "infra",
            "expected_keywords": ["TEI_CLIENT_BATCH", "batch_size", "tei", "sub-batch"],
            "expected_answer_summary": "EMBEDDING__TEI_CLIENT_BATCH (default 32) caps per-request batch; client sub-batches automatically.",
        },
        {
            "id": "gv1-050",
            "query": "How is JWT secret loaded from environment?",
            "difficulty": "easy",
            "category": "procedural",
            "domain": "infra",
            "expected_keywords": ["JWTHandler", "AUTH__JWT_SECRET", "jwt", "HS256"],
            "expected_answer_summary": "JWTHandler reads AUTH__JWT_SECRET via pydantic-settings; HS256 algorithm; validates secret length.",
        },
        {
            "id": "gv1-051",
            "query": "What is the default value of AGENT__RERANKER_TYPE?",
            "difficulty": "easy",
            "category": "factual",
            "domain": "infra",
            "expected_keywords": ["reranker_type", "llm", "AgentSettings", "default"],
            "expected_answer_summary": "AgentSettings.reranker_type defaults to llm; alternatives: cross_encoder, flashrank, colbert.",
        },
        {
            "id": "gv1-052",
            "query": "How does Self-RAG grader decide if a chunk is relevant?",
            "difficulty": "hard",
            "category": "analytical",
            "domain": "rag-framework",
            "expected_keywords": ["grader", "relevance", "yes", "no", "ainvoke"],
            "expected_answer_summary": "Self-RAG grader sends query+chunk to small LLM, parses yes/no/да/нет from response; retries with corrective feedback on invalid output.",
        },
        {
            "id": "gv1-053",
            "query": "How does the plan-execute agent decompose queries?",
            "difficulty": "hard",
            "category": "procedural",
            "domain": "rag-framework",
            "expected_keywords": ["plan_execute", "decompose", "sub_questions", "planner"],
            "expected_answer_summary": "Plan-execute uses planner LLM to decompose complex query into ordered sub-questions, executes each, synthesizes final answer.",
        },
        {
            "id": "gv1-054",
            "query": "Where is conversation history persisted in Conversational RAG?",
            "difficulty": "medium",
            "category": "procedural",
            "domain": "rag-framework",
            "expected_keywords": ["ConversationStore", "SQLite", "session_id", "history"],
            "expected_answer_summary": "ConversationStore persists messages to SQLite keyed by session_id; max_history limits window; supports query reformulation.",
        },
        {
            "id": "gv1-055",
            "query": "How does GraphRAG community detection group entities?",
            "difficulty": "hard",
            "category": "analytical",
            "domain": "rag-framework",
            "expected_keywords": ["community", "leiden", "resolution", "hierarchical"],
            "expected_answer_summary": "GraphRAG runs Leiden on entity graph; resolution param controls community size; multi-level hierarchy for global search.",
        },
        {
            "id": "gv1-056",
            "query": "How is rate limiting enforced on REST endpoints?",
            "difficulty": "medium",
            "category": "procedural",
            "domain": "infra",
            "expected_keywords": ["rate_limit", "RateLimit", "requests_per_minute", "burst"],
            "expected_answer_summary": "Rate limiting middleware uses token bucket: REQUESTS_PER_MINUTE default 60 with burst capacity, keyed by tenant/IP.",
        },
        {
            "id": "gv1-057",
            "query": "What MCP tools does the pdf-vector-graph server expose?",
            "difficulty": "easy",
            "category": "factual",
            "domain": "infra",
            "expected_keywords": ["mcp", "tools", "search_documents", "index_pdf", "ask_question"],
            "expected_answer_summary": "MCP server exposes 14 tools including index_pdf, search_documents, ask_question, plan_execute, web_search, visual_search, list_collections, get_stats, graph_query, research, analyze.",
        },
        {
            "id": "gv1-058",
            "query": "How is REST tenant isolation enforced via assert_tenant_access?",
            "difficulty": "hard",
            "category": "procedural",
            "domain": "infra",
            "expected_keywords": ["assert_tenant_access", "get_current_tenant", "admin", "tenant_id"],
            "expected_answer_summary": "assert_tenant_access guard takes path tenant_id + current_tenant + role; raises 403 unless role=admin or tenants match.",
        },
        {
            "id": "gv1-059",
            "query": "How does LLM reranker score candidate chunks?",
            "difficulty": "medium",
            "category": "procedural",
            "domain": "rag-framework",
            "expected_keywords": ["LLMReranker", "rerank", "JSON", "relevance", "Claude"],
            "expected_answer_summary": "LLMReranker sends query + numbered candidates to Claude, parses JSON array of index/score; sorts by score; truncates to top_k.",
        },
        {
            "id": "gv1-060",
            "query": "What is the FlashRank token budget parameter for?",
            "difficulty": "medium",
            "category": "factual",
            "domain": "rag-framework",
            "expected_keywords": ["flashrank", "token_budget", "caps", "truncate"],
            "expected_answer_summary": "FLASHRANK_TOKEN_BUDGET caps total tokens sent to local FlashRank reranker; truncates chunks to stay under context limit.",
        },
        {
            "id": "gv1-061",
            "query": "How does Qwen3STEmbedder load the model on GPU with bf16?",
            "difficulty": "medium",
            "category": "procedural",
            "domain": "embeddings",
            "expected_keywords": ["Qwen3STEmbedder", "SentenceTransformer", "bfloat16", "cuda"],
            "expected_answer_summary": "Qwen3STEmbedder constructs SentenceTransformer with model name, model_kwargs torch_dtype=bfloat16 device=cuda; tokenizer_kwargs padding_side=left for last-token pooling.",
        },
        {
            "id": "gv1-062",
            "query": "Where is the TEI HTTP embedder client implemented?",
            "difficulty": "easy",
            "category": "factual",
            "domain": "embeddings",
            "expected_keywords": ["Qwen3TEIEmbedder", "httpx", "embed", "client_batch_size"],
            "expected_answer_summary": "Qwen3TEIEmbedder uses httpx.AsyncClient to POST to TEI /embed endpoint; sub-batches to client_batch_size (default 32) to respect server max.",
        },
        {
            "id": "gv1-063",
            "query": "How does the BSL chunker apply sliding-window splitting?",
            "difficulty": "hard",
            "category": "procedural",
            "domain": "1c",
            "expected_keywords": ["bsl_chunker", "window", "overlap", "sliding"],
            "expected_answer_summary": "BSL chunker splits XXL symbols via sliding window=1024 overlap=256 to stay under embedding max input length 4096 tokens.",
        },
        {
            "id": "gv1-064",
            "query": "What does the Late Chunking pooling mode produce?",
            "difficulty": "hard",
            "category": "conceptual",
            "domain": "embeddings",
            "expected_keywords": ["late_chunking", "full-document", "mean-pool", "per-chunk"],
            "expected_answer_summary": "Late Chunking runs full-document forward pass then mean-pools per-chunk token spans; preserves cross-chunk context lost in standard chunking.",
        },
        {
            "id": "gv1-065",
            "query": "How is the BM25 SQLite fallback FTS5 schema defined?",
            "difficulty": "medium",
            "category": "procedural",
            "domain": "rag-framework",
            "expected_keywords": ["fts5", "CREATE VIRTUAL TABLE", "tokenize", "BM25Store"],
            "expected_answer_summary": "BM25Store creates FTS5 virtual table with tokenize=unicode61 or custom; columns (chunk_id, content, metadata); searched via MATCH.",
        },
        {
            "id": "gv1-066",
            "query": "Where is the semantic cache similarity threshold checked?",
            "difficulty": "medium",
            "category": "procedural",
            "domain": "rag-framework",
            "expected_keywords": ["SemanticCache", "threshold", "0.95", "embedding"],
            "expected_answer_summary": "SemanticCache embeds query, searches own SQLite cache, returns hit if cosine similarity exceeds threshold (default 0.95).",
        },
        {
            "id": "gv1-067",
            "query": "How is the LLM rotation service circuit breaker triggered?",
            "difficulty": "hard",
            "category": "procedural",
            "domain": "infra",
            "expected_keywords": ["CircuitBreaker", "failure_threshold", "open", "cooldown"],
            "expected_answer_summary": "CircuitBreaker counts consecutive failures; opens after failure_threshold; rejects calls during cooldown; half-opens for probe.",
        },
        {
            "id": "gv1-068",
            "query": "How does the Qdrant payload filter convert Pydantic dict to Qdrant Filter?",
            "difficulty": "hard",
            "category": "procedural",
            "domain": "rag-framework",
            "expected_keywords": ["_to_qdrant_filter", "Filter", "FieldCondition", "MatchValue"],
            "expected_answer_summary": "_to_qdrant_filter converts dict {key:value} or list filters to Qdrant Filter with FieldCondition + MatchValue per field; supports nested AND/OR.",
        },
        {
            "id": "gv1-069",
            "query": "Where is the embedding cache backed by SQLite?",
            "difficulty": "medium",
            "category": "procedural",
            "domain": "rag-framework",
            "expected_keywords": ["EmbeddingCache", "SQLite", "hash", "ttl"],
            "expected_answer_summary": "EmbeddingCache stores text_hash -> vector in SQLite with TTL; lookup before calling embedder; write-through on miss.",
        },
        {
            "id": "gv1-070",
            "query": "How does the auto-git-save hook detect modified files for commit?",
            "difficulty": "medium",
            "category": "procedural",
            "domain": "infra",
            "expected_keywords": ["auto-git-save", "git", "modified", "staged"],
            "expected_answer_summary": "auto-git-save hook reads git status, stages modified files, creates structured commit with hook signature.",
        },
        {
            "id": "gv1-071",
            "query": "Where is the HybridSearchStrategy class defined?",
            "difficulty": "easy",
            "category": "factual",
            "domain": "rag-framework",
            "expected_keywords": ["HybridSearchStrategy", "class", "hybrid_search.py"],
            "expected_answer_summary": "HybridSearchStrategy class is defined in src/pdf_framework/search/strategies/hybrid_search.py.",
        },
        {
            "id": "gv1-072",
            "query": "Where is the Self-RAG agent graph constructed?",
            "difficulty": "easy",
            "category": "factual",
            "domain": "rag-framework",
            "expected_keywords": ["SelfRAGAgent", "build_graph", "nodes", "grader"],
            "expected_answer_summary": "Self-RAG agent wires grader, retriever, rewriter, generator, hallucination_checker nodes in build_graph.",
        },
        {
            "id": "gv1-073",
            "query": "How does the Adaptive RAG classifier route queries?",
            "difficulty": "medium",
            "category": "procedural",
            "domain": "rag-framework",
            "expected_keywords": ["Adaptive", "classifier", "route", "complexity"],
            "expected_answer_summary": "Adaptive RAG classifier LLM labels query as simple/moderate/complex/thematic; routes to appropriate strategy.",
        },
    ]

    for item in new_items:
        item["expected_chunk_ids"] = []

    existing_ids = {it["id"] for it in data["items"]}
    added = 0
    for item in new_items:
        if item["id"] not in existing_ids:
            data["items"].append(item)
            added += 1

    tmp = PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PATH)
    print(f"Added {added} new items. Total: {len(data['items'])}")


if __name__ == "__main__":
    main()
