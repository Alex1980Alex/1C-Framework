"""BSL-specific scoring for memory search.

Scores search results based on BSL (1C:Enterprise language) patterns:
object types, naming prefixes, export symbols, query/transaction context.

Migrated from: unified-memory-mcp/src/search/bsl_scorer.py (436 lines)
No external dependencies -- pure regex-based analysis.

Version: 1.0 (2026-04-04) -- P2 migration
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum

from .config import DEFAULT_SEARCH_CONFIG, BSLScorerConfig

logger = logging.getLogger(__name__)


class BSLObjectType(str, Enum):
    """1C metadata object types."""

    COMMON_MODULE = "CommonModule"
    DATA_PROCESSOR = "DataProcessor"
    REPORT = "Report"
    DOCUMENT = "Document"
    CATALOG = "Catalog"
    INFORMATION_REGISTER = "InformationRegister"
    ACCUMULATION_REGISTER = "AccumulationRegister"
    FORM_MODULE = "FormModule"
    OBJECT_MODULE = "ObjectModule"
    MANAGER_MODULE = "ManagerModule"
    UNKNOWN = "Unknown"


class BSLSymbolType(str, Enum):
    """BSL symbol types."""

    FUNCTION = "function"
    PROCEDURE = "procedure"
    EVENT_HANDLER = "event_handler"


@dataclass
class BSLSymbol:
    """A BSL code symbol."""

    name: str
    symbol_type: BSLSymbolType
    is_export: bool = False
    line_number: int = 0
    parameters: list[str] = field(default_factory=list)


@dataclass
class BSLAnalysisResult:
    """Result of BSL content analysis."""

    object_type: BSLObjectType
    symbols: list[BSLSymbol]
    prefix: str | None = None
    has_queries: bool = False
    has_transactions: bool = False
    complexity_score: float = 0.0


@dataclass
class BSLScoreResult:
    """Result of BSL scoring."""

    final_score: float
    base_score: float
    adjustments: dict[str, float]
    matched_patterns: list[str]
    explanation: str


class BSLScorer:
    """
    BSL-specific scoring for search results.

    Considers object types, naming prefixes, export symbols, and context.
    """

    def __init__(self, config: BSLScorerConfig | None = None):
        self.config = config or DEFAULT_SEARCH_CONFIG.bsl_scorer

        self._function_pattern = re.compile(
            r"(Функция|Function)\s+(\w+)\s*\(([^)]*)\)",
            re.IGNORECASE | re.MULTILINE,
        )
        self._procedure_pattern = re.compile(
            r"(Процедура|Procedure)\s+(\w+)\s*\(([^)]*)\)",
            re.IGNORECASE | re.MULTILINE,
        )
        self._export_pattern = re.compile(r"\bЭкспорт\b|\bExport\b", re.IGNORECASE)
        self._query_pattern = re.compile(
            r"(Новый\s+Запрос|New\s+Query|Запрос\.Текст)", re.IGNORECASE
        )
        self._transaction_pattern = re.compile(
            r"(НачатьТранзакцию|BeginTransaction|ЗафиксироватьТранзакцию)", re.IGNORECASE
        )

        self._prefix_patterns = [
            re.compile(f"^{re.escape(p)}", re.IGNORECASE) for p in self.config.prefix_patterns
        ]

        self._event_handlers = {
            "ПередЗаписью",
            "ПриЗаписи",
            "ПослеЗаписи",
            "ОбработкаПроведения",
            "ПриОткрытии",
            "ПриСозданииНаСервере",
            "BeforeWrite",
            "OnWrite",
            "AfterWrite",
            "Posting",
            "OnOpen",
        }

    def detect_object_type(self, file_path: str) -> BSLObjectType:
        """Detect 1C object type from file path."""
        path_lower = file_path.lower()

        type_patterns = {
            "commonmodules": BSLObjectType.COMMON_MODULE,
            "общиемодули": BSLObjectType.COMMON_MODULE,
            "dataprocessors": BSLObjectType.DATA_PROCESSOR,
            "обработки": BSLObjectType.DATA_PROCESSOR,
            "reports": BSLObjectType.REPORT,
            "отчеты": BSLObjectType.REPORT,
            "documents": BSLObjectType.DOCUMENT,
            "документы": BSLObjectType.DOCUMENT,
            "catalogs": BSLObjectType.CATALOG,
            "справочники": BSLObjectType.CATALOG,
            "informationregisters": BSLObjectType.INFORMATION_REGISTER,
            "регистрысведений": BSLObjectType.INFORMATION_REGISTER,
            "accumulationregisters": BSLObjectType.ACCUMULATION_REGISTER,
            "регистрынакопления": BSLObjectType.ACCUMULATION_REGISTER,
        }

        for pattern, obj_type in type_patterns.items():
            if pattern in path_lower:
                return obj_type

        if "objectmodule" in path_lower:
            return BSLObjectType.OBJECT_MODULE
        if "managermodule" in path_lower:
            return BSLObjectType.MANAGER_MODULE
        if "form" in path_lower:
            return BSLObjectType.FORM_MODULE

        return BSLObjectType.UNKNOWN

    def extract_symbols(self, content: str) -> list[BSLSymbol]:
        """Extract BSL symbols from code content."""
        symbols: list[BSLSymbol] = []

        for pattern, default_type in [
            (self._function_pattern, BSLSymbolType.FUNCTION),
            (self._procedure_pattern, BSLSymbolType.PROCEDURE),
        ]:
            for match in pattern.finditer(content):
                name = match.group(2)
                params_str = match.group(3)
                params = [p.strip() for p in params_str.split(",") if p.strip()]

                line_start = content.rfind("\n", 0, match.start()) + 1
                line_end = content.find("\n", match.end())
                line = content[line_start : line_end if line_end > 0 else len(content)]
                is_export = bool(self._export_pattern.search(line))

                symbol_type = default_type
                if name in self._event_handlers:
                    symbol_type = BSLSymbolType.EVENT_HANDLER

                symbols.append(
                    BSLSymbol(
                        name=name,
                        symbol_type=symbol_type,
                        is_export=is_export,
                        parameters=params,
                        line_number=content[: match.start()].count("\n") + 1,
                    )
                )

        return symbols

    def analyze_content(self, content: str, file_path: str = "") -> BSLAnalysisResult:
        """Full analysis of BSL content."""
        object_type = self.detect_object_type(file_path)
        symbols = self.extract_symbols(content)
        prefix = self._detect_prefix(content)

        has_queries = bool(self._query_pattern.search(content))
        has_transactions = bool(self._transaction_pattern.search(content))

        complexity = (
            len(symbols) * 0.1 + (1.0 if has_queries else 0.0) + (0.5 if has_transactions else 0.0)
        )

        return BSLAnalysisResult(
            object_type=object_type,
            symbols=symbols,
            prefix=prefix,
            has_queries=has_queries,
            has_transactions=has_transactions,
            complexity_score=min(complexity, 5.0),
        )

    def score_match(
        self,
        query: str,
        content: str,
        file_path: str = "",
        base_score: float = 1.0,
        analysis: BSLAnalysisResult | None = None,
    ) -> BSLScoreResult:
        """Compute BSL-specific score for a search match."""
        if analysis is None:
            analysis = self.analyze_content(content, file_path)

        adjustments: dict[str, float] = {}
        matched: list[str] = []
        query_tokens = set(re.findall(r"\w+", query.lower()))

        # 1. Object type boost
        type_weight = self.config.object_type_weights.get(analysis.object_type.value, 1.0)
        if type_weight != 1.0:
            adjustments["object_type"] = type_weight
            matched.append(f"object_type:{analysis.object_type.value}")

        # 2. Symbol matching
        for symbol in analysis.symbols:
            sym_lower = symbol.name.lower()
            if sym_lower in query_tokens:
                adjustments["exact_symbol"] = self.config.exact_match_weight
                matched.append(f"exact:{symbol.name}")
                break
            for token in query_tokens:
                if token in sym_lower or sym_lower in token:
                    if "partial_match" not in adjustments:
                        adjustments["partial_match"] = self.config.prefix_match_weight
                        matched.append(f"partial:{symbol.name}")

        # 3. Export boost
        export_count = sum(1 for s in analysis.symbols if s.is_export)
        if export_count:
            adjustments["has_exports"] = self.config.export_boost
            matched.append(f"exports:{export_count}")

        # 4. Function/procedure boost
        if any(s.symbol_type == BSLSymbolType.FUNCTION for s in analysis.symbols):
            adjustments["functions"] = self.config.function_boost
        if any(s.symbol_type == BSLSymbolType.PROCEDURE for s in analysis.symbols):
            adjustments["procedures"] = self.config.procedure_boost

        # 5. Context boosts
        if analysis.has_queries:
            adjustments["queries"] = self.config.context_weights.get("query", 1.5)
            matched.append("context:query")
        if analysis.has_transactions:
            adjustments["transactions"] = self.config.context_weights.get("transaction", 1.4)
            matched.append("context:transaction")

        # 6. Common module boost
        if analysis.object_type == BSLObjectType.COMMON_MODULE:
            adjustments["common_module"] = self.config.common_module_boost

        # Calculate final score
        final_score = base_score
        for weight in adjustments.values():
            final_score *= weight

        parts = [f"base={base_score:.3f}"]
        for name, weight in adjustments.items():
            parts.append(f"{name}x{weight:.2f}")
        explanation = " -> ".join(parts) + f" = {final_score:.3f}"

        return BSLScoreResult(
            final_score=final_score,
            base_score=base_score,
            adjustments=adjustments,
            matched_patterns=matched,
            explanation=explanation,
        )

    def rerank(
        self,
        query: str,
        results: list[tuple[str, str, float]],
        file_paths: dict[str, str] | None = None,
    ) -> list[tuple[str, float, BSLScoreResult]]:
        """Rerank search results with BSL scoring."""
        file_paths = file_paths or {}
        reranked = []

        for doc_id, content, base_score in results:
            score_result = self.score_match(
                query=query,
                content=content,
                file_path=file_paths.get(doc_id, ""),
                base_score=base_score,
            )
            reranked.append((doc_id, score_result.final_score, score_result))

        reranked.sort(key=lambda x: x[1], reverse=True)
        return reranked

    def _detect_prefix(self, content: str) -> str | None:
        """Detect naming prefix from BSL code."""
        for match in self._function_pattern.finditer(content):
            name = match.group(2)
            for prefix_pattern in self._prefix_patterns:
                if prefix_pattern.match(name):
                    return name.split("_")[0] + "_"
        return None


__all__ = [
    "BSLAnalysisResult",
    "BSLObjectType",
    "BSLScoreResult",
    "BSLScorer",
    "BSLSymbol",
    "BSLSymbolType",
]
