"""Phase 19: Deep Research Agent — modular components + legacy orchestrator.

Modular components (heuristic + LLM-optional):
  - ResearchPlanner: complexity detection, sub-question decomposition
  - ModularSynthesizer: cross-document synthesis with citations
  - ResearchQualityChecker: coverage and groundedness assessment

Legacy orchestrator (full LLM pipeline):
  - DeepResearchAgent: end-to-end deep research via QueryDecomposer + MultiStepRetriever + CrossDocumentSynthesizer
"""

# New modular components (heuristic + LLM-optional)
from src.pdf_framework.agents.deep.planner import ResearchPlan, ResearchPlanner
from src.pdf_framework.agents.deep.quality import QualityResult, ResearchQualityChecker
from src.pdf_framework.agents.deep.synthesizer import (
    CrossDocumentSynthesizer as ModularSynthesizer,
    SubResult,
)

# Legacy orchestrator (full LLM pipeline)
try:
    from src.pdf_framework.agents.research_agent import DeepResearchAgent, ResearchReport
except ImportError:
    DeepResearchAgent = None  # type: ignore[assignment,misc]
    ResearchReport = None  # type: ignore[assignment,misc]

__all__ = [
    "ResearchPlanner",
    "ResearchPlan",
    "ModularSynthesizer",
    "SubResult",
    "ResearchQualityChecker",
    "QualityResult",
    "DeepResearchAgent",
    "ResearchReport",
]
