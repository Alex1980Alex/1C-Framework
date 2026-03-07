"""
Error Learner for Development Pipeline.

Sprint 3.3.3: Learning from errors

This module provides functionality for:
- Recording and analyzing errors
- Learning prevention strategies
- Providing error-based recommendations
"""

import re
import logging
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
from collections import defaultdict

from models import (
    ErrorRecord,
    ErrorSeverity,
    MemoryEntry,
    MemoryType,
    LearningContext,
    Recommendation,
    RecommendationType,
)
from .unified_memory_client import (
    UnifiedMemoryClient,
    SearchResult,
    SaveResult,
)


logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Categories of errors for learning."""
    SYNTAX = "syntax"  # Syntax/parsing errors
    RUNTIME = "runtime"  # Runtime exceptions
    LOGIC = "logic"  # Logic/business errors
    CONFIGURATION = "configuration"  # Config/setup errors
    INTEGRATION = "integration"  # External system errors
    PERFORMANCE = "performance"  # Performance issues
    SECURITY = "security"  # Security-related errors
    DATA = "data"  # Data validation/integrity errors
    UNKNOWN = "unknown"


@dataclass
class ErrorSignature:
    """Unique signature of an error for deduplication and matching."""

    error_type: str
    key_message: str
    file_pattern: Optional[str] = None
    line_pattern: Optional[str] = None
    category: ErrorCategory = ErrorCategory.UNKNOWN

    def generate_hash(self) -> str:
        """Generate unique hash for this signature."""
        content = f"{self.error_type}|{self.key_message}|{self.category.value}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    @classmethod
    def from_error(cls, error: ErrorRecord) -> "ErrorSignature":
        """Create signature from error record."""
        # Extract key message (first line or first 100 chars)
        key_message = error.error_message.split('\n')[0][:100]

        # Detect category
        category = cls._detect_category(error)

        # Extract file pattern if available
        file_pattern = None
        if error.context and "file" in error.context:
            file_path = error.context["file"]
            # Generalize file path (remove specific names)
            file_pattern = re.sub(r'\d+', '*', file_path)

        return cls(
            error_type=error.error_type,
            key_message=key_message,
            file_pattern=file_pattern,
            category=category,
        )

    @staticmethod
    def _detect_category(error: ErrorRecord) -> ErrorCategory:
        """Detect error category from error record."""
        message_lower = error.error_message.lower()
        type_lower = error.error_type.lower()

        # Category detection rules
        if any(kw in type_lower for kw in ['syntax', 'parse', 'compile']):
            return ErrorCategory.SYNTAX
        elif any(kw in type_lower for kw in ['runtime', 'exception', 'error']):
            return ErrorCategory.RUNTIME
        elif any(kw in message_lower for kw in ['config', 'setting', 'environment']):
            return ErrorCategory.CONFIGURATION
        elif any(kw in message_lower for kw in ['connect', 'api', 'external', 'timeout']):
            return ErrorCategory.INTEGRATION
        elif any(kw in message_lower for kw in ['slow', 'performance', 'memory', 'timeout']):
            return ErrorCategory.PERFORMANCE
        elif any(kw in message_lower for kw in ['security', 'permission', 'access', 'auth']):
            return ErrorCategory.SECURITY
        elif any(kw in message_lower for kw in ['data', 'validation', 'constraint', 'null']):
            return ErrorCategory.DATA
        elif any(kw in message_lower for kw in ['logic', 'business', 'rule']):
            return ErrorCategory.LOGIC
        else:
            return ErrorCategory.UNKNOWN


@dataclass
class ErrorAnalysis:
    """Analysis result for an error."""

    error: ErrorRecord
    signature: ErrorSignature
    similar_errors: List[ErrorRecord] = field(default_factory=list)
    occurrence_count: int = 1
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    known_fixes: List[str] = field(default_factory=list)
    prevention_hints: List[str] = field(default_factory=list)
    related_patterns: List[str] = field(default_factory=list)

    @property
    def is_recurring(self) -> bool:
        """Check if this is a recurring error."""
        return self.occurrence_count > 1

    @property
    def recurrence_frequency(self) -> Optional[float]:
        """Calculate recurrence frequency (errors per day)."""
        if not self.first_seen or not self.last_seen:
            return None
        if self.first_seen == self.last_seen:
            return None

        days = (self.last_seen - self.first_seen).days
        if days == 0:
            return float(self.occurrence_count)

        return self.occurrence_count / days


@dataclass
class PreventionRule:
    """Rule for preventing an error."""

    error_signature_hash: str
    rule_type: str  # 'code_check', 'pre_condition', 'validation', 'warning'
    description: str
    check_pattern: Optional[str] = None  # Regex pattern to check
    recommendation: Optional[str] = None
    effectiveness: float = 0.5  # 0.0 to 1.0
    created_at: datetime = field(default_factory=datetime.now)


class ErrorAnalyzer:
    """
    Analyzes errors to extract learning insights.

    The analyzer provides:
    - Error categorization and signature extraction
    - Pattern detection across similar errors
    - Root cause analysis suggestions
    - Fix effectiveness tracking
    """

    def __init__(
        self,
        memory_client: UnifiedMemoryClient,
    ):
        self.memory_client = memory_client
        self._signature_cache: Dict[str, ErrorSignature] = {}

    async def analyze_error(
        self,
        error: ErrorRecord,
        learning_context: Optional[LearningContext] = None,
    ) -> ErrorAnalysis:
        """
        Analyze an error and find related information.

        Args:
            error: Error record to analyze
            learning_context: Optional learning context

        Returns:
            ErrorAnalysis with insights
        """
        # Generate signature
        signature = ErrorSignature.from_error(error)
        self._signature_cache[error.id] = signature

        # Search for similar errors in memory
        similar = await self._find_similar_errors(error, signature)

        # Extract known fixes
        known_fixes = self._extract_fixes(similar)

        # Generate prevention hints
        prevention_hints = self._generate_prevention_hints(
            error, signature, similar
        )

        # Find related patterns
        related_patterns = await self._find_related_patterns(error, signature)

        # Calculate occurrence stats
        occurrence_count = len(similar) + 1
        first_seen = None
        last_seen = None

        if similar:
            timestamps = [
                s.timestamp for s in similar
                if s.timestamp
            ]
            if timestamps:
                first_seen = min(timestamps)
                last_seen = max(timestamps)

        return ErrorAnalysis(
            error=error,
            signature=signature,
            similar_errors=similar,
            occurrence_count=occurrence_count,
            first_seen=first_seen,
            last_seen=last_seen,
            known_fixes=known_fixes,
            prevention_hints=prevention_hints,
            related_patterns=related_patterns,
        )

    async def _find_similar_errors(
        self,
        error: ErrorRecord,
        signature: ErrorSignature,
    ) -> List[ErrorRecord]:
        """Find similar errors from memory."""
        query = f"{error.error_type} {signature.key_message}"

        results = await self.memory_client.search_memory(
            query=query,
            memory_type=MemoryType.ERROR,
            limit=20,
        )

        similar = []
        for result in results:
            parsed = self._parse_error_from_result(result)
            if parsed and parsed.id != error.id:
                similar.append(parsed)

        return similar

    def _parse_error_from_result(
        self,
        result: SearchResult,
    ) -> Optional[ErrorRecord]:
        """Parse ErrorRecord from search result."""
        try:
            metadata = result.metadata

            if "error_data" in metadata:
                return ErrorRecord.from_dict(metadata["error_data"])

            # Parse from content
            content = result.content
            lines = content.split('\n')

            error_type = ""
            error_message = ""
            severity = ErrorSeverity.MEDIUM

            for line in lines:
                if line.startswith("Type:") or line.startswith("Тип:"):
                    error_type = line.split(":", 1)[1].strip()
                elif line.startswith("Message:") or line.startswith("Сообщение:"):
                    error_message = line.split(":", 1)[1].strip()
                elif line.startswith("Severity:") or line.startswith("Критичность:"):
                    sev_str = line.split(":", 1)[1].strip().lower()
                    for s in ErrorSeverity:
                        if s.value == sev_str:
                            severity = s
                            break

            if error_type and error_message:
                return ErrorRecord(
                    id=result.id,
                    error_type=error_type,
                    error_message=error_message,
                    severity=severity,
                    timestamp=datetime.fromisoformat(result.created_at)
                    if result.created_at else None,
                )

            return None

        except Exception as e:
            logger.warning(f"Failed to parse error from result: {e}")
            return None

    def _extract_fixes(
        self,
        similar_errors: List[ErrorRecord],
    ) -> List[str]:
        """Extract known fixes from similar errors."""
        fixes = []
        seen = set()

        for error in similar_errors:
            if error.fix_applied and error.fix_applied not in seen:
                fixes.append(error.fix_applied)
                seen.add(error.fix_applied)

            if error.resolution and error.resolution not in seen:
                fixes.append(error.resolution)
                seen.add(error.resolution)

        return fixes[:5]  # Limit to 5 most relevant fixes

    def _generate_prevention_hints(
        self,
        error: ErrorRecord,
        signature: ErrorSignature,
        similar_errors: List[ErrorRecord],
    ) -> List[str]:
        """Generate prevention hints based on analysis."""
        hints = []

        # Collect existing prevention hints
        for similar in similar_errors:
            if similar.prevention_hint and similar.prevention_hint not in hints:
                hints.append(similar.prevention_hint)

        # Generate hints based on category
        category_hints = {
            ErrorCategory.SYNTAX: [
                "Используйте линтер для проверки синтаксиса перед запуском",
                "Включите строгую проверку типов",
            ],
            ErrorCategory.RUNTIME: [
                "Добавьте обработку исключений Попытка/Исключение",
                "Проверяйте значения на Неопределено перед использованием",
            ],
            ErrorCategory.CONFIGURATION: [
                "Документируйте все необходимые настройки",
                "Используйте значения по умолчанию для опциональных параметров",
            ],
            ErrorCategory.INTEGRATION: [
                "Добавьте таймауты для внешних вызовов",
                "Реализуйте повторные попытки с экспоненциальной задержкой",
            ],
            ErrorCategory.PERFORMANCE: [
                "Профилируйте код перед оптимизацией",
                "Используйте кеширование для частых запросов",
            ],
            ErrorCategory.DATA: [
                "Добавьте валидацию входных данных",
                "Проверяйте обязательные поля перед обработкой",
            ],
        }

        for hint in category_hints.get(signature.category, []):
            if hint not in hints:
                hints.append(hint)

        return hints[:5]

    async def _find_related_patterns(
        self,
        error: ErrorRecord,
        signature: ErrorSignature,
    ) -> List[str]:
        """Find patterns related to the error."""
        query = f"fix {signature.category.value} {signature.key_message}"

        from .pattern_saver import PatternMatcher
        matcher = PatternMatcher(self.memory_client)

        results = await matcher.find_matching_patterns(
            context=query,
            learning_context=None,
        )

        return [r.pattern.name for r in results[:3]]


class ErrorLearner:
    """
    Learns from errors to prevent future occurrences.

    The learner handles:
    - Error recording and tracking
    - Prevention rule generation
    - Fix effectiveness measurement
    - Proactive error warnings
    """

    def __init__(
        self,
        memory_client: UnifiedMemoryClient,
        analyzer: Optional[ErrorAnalyzer] = None,
    ):
        self.memory_client = memory_client
        self.analyzer = analyzer or ErrorAnalyzer(memory_client)
        self._prevention_rules: Dict[str, PreventionRule] = {}
        self._error_counts: Dict[str, int] = defaultdict(int)

    async def learn_from_error(
        self,
        error: ErrorRecord,
        learning_context: Optional[LearningContext] = None,
    ) -> ErrorAnalysis:
        """
        Learn from an error and save to memory.

        Args:
            error: Error record to learn from
            learning_context: Optional learning context

        Returns:
            ErrorAnalysis with insights
        """
        # Analyze the error
        analysis = await self.analyzer.analyze_error(error, learning_context)

        # Update error counts
        sig_hash = analysis.signature.generate_hash()
        self._error_counts[sig_hash] += 1

        # Save error to memory
        await self._save_error(error, analysis, learning_context)

        # Generate prevention rule if recurring
        if analysis.is_recurring:
            await self._generate_prevention_rule(analysis)

        return analysis

    async def _save_error(
        self,
        error: ErrorRecord,
        analysis: ErrorAnalysis,
        learning_context: Optional[LearningContext] = None,
    ) -> SaveResult:
        """Save error to memory with analysis."""
        # Add analysis info to tags for searchability
        error.tags.append(f"category:{analysis.signature.category.value}")
        error.tags.append(f"recurring:{analysis.is_recurring}")

        if analysis.occurrence_count > 1:
            error.tags.append(f"occurrences:{analysis.occurrence_count}")

        # Store prevention hint if we have known fixes
        if analysis.known_fixes and not error.prevention_hint:
            error.prevention_hint = analysis.known_fixes[0]

        return await self.memory_client.save_error(error)

    async def _generate_prevention_rule(
        self,
        analysis: ErrorAnalysis,
    ) -> Optional[PreventionRule]:
        """Generate prevention rule for recurring error."""
        sig_hash = analysis.signature.generate_hash()

        # Skip if rule already exists
        if sig_hash in self._prevention_rules:
            return self._prevention_rules[sig_hash]

        # Determine rule type based on category
        rule_type_map = {
            ErrorCategory.SYNTAX: "code_check",
            ErrorCategory.DATA: "validation",
            ErrorCategory.CONFIGURATION: "pre_condition",
            ErrorCategory.INTEGRATION: "warning",
        }

        rule_type = rule_type_map.get(
            analysis.signature.category, "warning"
        )

        # Generate description
        description = self._generate_rule_description(analysis)

        # Generate check pattern if applicable
        check_pattern = self._generate_check_pattern(analysis)

        # Generate recommendation
        recommendation = None
        if analysis.known_fixes:
            recommendation = analysis.known_fixes[0]
        elif analysis.prevention_hints:
            recommendation = analysis.prevention_hints[0]

        rule = PreventionRule(
            error_signature_hash=sig_hash,
            rule_type=rule_type,
            description=description,
            check_pattern=check_pattern,
            recommendation=recommendation,
            effectiveness=0.5,  # Initial effectiveness
        )

        self._prevention_rules[sig_hash] = rule

        # Save rule to memory
        await self._save_prevention_rule(rule)

        return rule

    def _generate_rule_description(
        self,
        analysis: ErrorAnalysis,
    ) -> str:
        """Generate human-readable rule description."""
        category = analysis.signature.category.value
        key_message = analysis.signature.key_message

        return (
            f"Prevent {category} error: {key_message[:50]}... "
            f"(occurred {analysis.occurrence_count} times)"
        )

    def _generate_check_pattern(
        self,
        analysis: ErrorAnalysis,
    ) -> Optional[str]:
        """Generate regex check pattern if applicable."""
        category = analysis.signature.category

        if category == ErrorCategory.SYNTAX:
            # Try to extract syntax pattern from error message
            return None  # Would need language-specific analysis

        if category == ErrorCategory.DATA:
            # Look for field names in error message
            field_match = re.search(
                r"field[:\s]+['\"]?(\w+)['\"]?",
                analysis.error.error_message,
                re.IGNORECASE
            )
            if field_match:
                field_name = field_match.group(1)
                return rf"\b{field_name}\s*="

        return None

    async def _save_prevention_rule(
        self,
        rule: PreventionRule,
    ) -> SaveResult:
        """Save prevention rule to memory."""
        content = (
            f"Prevention Rule: {rule.description}\n"
            f"Type: {rule.rule_type}\n"
            f"Recommendation: {rule.recommendation or 'N/A'}"
        )

        if rule.check_pattern:
            content += f"\nCheck Pattern: {rule.check_pattern}"

        return await self.memory_client.save_memory(
            content=content,
            memory_type=MemoryType.GENERAL,
            importance=0.7,
            tags=["prevention_rule", rule.rule_type],
            context={
                "rule_hash": rule.error_signature_hash,
                "effectiveness": rule.effectiveness,
            },
        )

    async def check_for_potential_errors(
        self,
        code: str,
        file_path: Optional[str] = None,
    ) -> List[Recommendation]:
        """
        Check code for potential errors based on learned patterns.

        Args:
            code: Code to check
            file_path: Optional file path for context

        Returns:
            List of recommendations to prevent errors
        """
        recommendations = []

        for sig_hash, rule in self._prevention_rules.items():
            if rule.check_pattern:
                if re.search(rule.check_pattern, code, re.IGNORECASE):
                    recommendations.append(Recommendation(
                        id=f"rec_{sig_hash}",
                        recommendation_type=RecommendationType.PREVENTIVE,
                        title=f"Potential {rule.rule_type} issue",
                        action=rule.recommendation or rule.description,
                        rationale=f"Based on {self._error_counts[sig_hash]} previous occurrences",
                        confidence=rule.effectiveness,
                        priority=2 if rule.effectiveness > 0.7 else 3,
                    ))

        return recommendations

    async def record_fix_success(
        self,
        error_id: str,
        fix_applied: str,
    ) -> bool:
        """
        Record that a fix was successful.

        Args:
            error_id: ID of the error that was fixed
            fix_applied: Description of the fix

        Returns:
            True if recorded successfully
        """
        # Get the signature for this error
        signature = self._signature_cache.get(error_id)
        if not signature:
            return False

        sig_hash = signature.generate_hash()

        # Update prevention rule effectiveness
        if sig_hash in self._prevention_rules:
            rule = self._prevention_rules[sig_hash]
            # Increase effectiveness (moving average)
            rule.effectiveness = rule.effectiveness * 0.8 + 0.2

        # Save success to memory
        content = f"Fix success for error {error_id}: {fix_applied}"
        result = await self.memory_client.save_memory(
            content=content,
            memory_type=MemoryType.EXECUTION,
            importance=0.7,
            tags=["fix_success", error_id],
            context={
                "error_id": error_id,
                "fix_applied": fix_applied,
                "signature_hash": sig_hash,
            },
        )

        return result.success

    async def record_fix_failure(
        self,
        error_id: str,
        fix_attempted: str,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Record that a fix attempt failed.

        Args:
            error_id: ID of the error
            fix_attempted: Description of the attempted fix
            reason: Optional reason for failure

        Returns:
            True if recorded successfully
        """
        signature = self._signature_cache.get(error_id)
        if not signature:
            return False

        sig_hash = signature.generate_hash()

        # Update prevention rule effectiveness
        if sig_hash in self._prevention_rules:
            rule = self._prevention_rules[sig_hash]
            # Decrease effectiveness
            rule.effectiveness = max(0.1, rule.effectiveness * 0.9)

        # Save failure to memory
        content = f"Fix failure for error {error_id}: {fix_attempted}"
        if reason:
            content += f"\nReason: {reason}"

        result = await self.memory_client.save_memory(
            content=content,
            memory_type=MemoryType.EXECUTION,
            importance=0.8,  # Failures are important to learn from
            tags=["fix_failure", error_id],
            context={
                "error_id": error_id,
                "fix_attempted": fix_attempted,
                "reason": reason,
                "signature_hash": sig_hash,
            },
        )

        return result.success

    def get_error_stats(self) -> Dict[str, Any]:
        """Get statistics about learned errors."""
        return {
            "total_error_signatures": len(self._error_counts),
            "total_occurrences": sum(self._error_counts.values()),
            "prevention_rules": len(self._prevention_rules),
            "top_errors": sorted(
                self._error_counts.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:10],
        }
