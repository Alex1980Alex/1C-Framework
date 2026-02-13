"""RAG agents with caching and conversation memory (Phase 9-11)."""

from src.pdf_framework.agents.cache import LLMResponseCache, get_llm_cache
from src.pdf_framework.agents.memory.conversation import (
    ConversationMemory,
    Message,
)

# Phase 19: Deep Research Agent
from src.pdf_framework.agents.query_decomposer import (
    QueryDecomposer,
    QueryDecomposition,
    decompose_query,
)
from src.pdf_framework.agents.multi_step_retriever import (
    MultiStepRetriever,
    MultiStepResult,
    retrieve_multi_step,
)
from src.pdf_framework.agents.cross_document_synthesizer import (
    CrossDocumentSynthesizer,
    SynthesizedAnswer,
    synthesize_cross_document,
)
from src.pdf_framework.agents.research_agent import (
    DeepResearchAgent,
    ResearchReport,
    deep_research,
)

__all__ = [
    "ConversationMemory",
    "Message",
    "LLMResponseCache",
    "get_llm_cache",
    # Phase 19
    "QueryDecomposer",
    "QueryDecomposition",
    "decompose_query",
    "MultiStepRetriever",
    "MultiStepResult",
    "retrieve_multi_step",
    "CrossDocumentSynthesizer",
    "SynthesizedAnswer",
    "synthesize_cross_document",
    "DeepResearchAgent",
    "ResearchReport",
    "deep_research",
]
