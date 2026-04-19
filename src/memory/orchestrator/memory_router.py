"""
Memory Router — Automatic routing between Memory subsystems.

Routes content to the appropriate memory subsystem based on:
- Phase 0: Auto-classify middleware (ContentType detection — Memori pattern)
- Phase 1: Rule-based classification (explicit keywords, intent detection, type detection)
- Phase 2: Keyword scoring (TF-IDF-like weighted scoring)
- Phase 3: Target selection (threshold-based)

Target subsystems:
- memory-ai: episodic facts, important messages
- vector-memory: patterns, code conventions, semantic knowledge
- skill-learning: captured skills, workflow patterns

Migrated from D:\\1C-Enterprise_Framework\\memory-orchestrator\\src\\memory_router.py
Adapted: 3 target servers (no conversation-memory, no docs-rag).
Auto-classify middleware added for P0 completion (Memori pattern).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .memcube import ContentType

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class RouterConfig:
    """Configuration for MemoryRouter."""

    # Confidence thresholds for multi-target routing
    single_target_threshold: float = 0.8
    dual_target_threshold: float = 0.5
    triple_target_threshold: float = 0.3

    # Content limits
    max_content_length: int = 10000
    truncate_length: int = 2000

    # Category weights for keyword scoring
    patterns_weight: float = 1.5
    facts_weight: float = 1.2
    skills_weight: float = 1.3

    # Feature flags
    enable_type_detection: bool = True
    enable_intent_detection: bool = True
    enable_keyword_scoring: bool = True


@dataclass
class RoutingDecision:
    """Result of routing classification."""

    targets: list[str]
    confidences: dict[str, float]
    method: str  # "auto_classify" | "explicit" | "intent" | "type_detection" | "keyword_scoring" | "fallback"
    reasoning: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    classification: ClassificationResult | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {
            "targets": self.targets,
            "confidences": self.confidences,
            "method": self.method,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp,
        }
        if self.classification:
            result["classification"] = self.classification.to_dict()
        return result

    def __str__(self) -> str:
        targets_str = ", ".join(self.targets)
        return f"RoutingDecision({self.method}: {targets_str})"


@dataclass
class RoutingStats:
    """Statistics for routing operations."""

    total_routes: int = 0
    auto_classify_matches: int = 0
    explicit_matches: int = 0
    intent_matches: int = 0
    type_detection_matches: int = 0
    keyword_scoring_routes: int = 0
    fallback_routes: int = 0
    multi_target_routes: int = 0
    single_target_routes: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_routes": self.total_routes,
            "auto_classify_matches": self.auto_classify_matches,
            "explicit_matches": self.explicit_matches,
            "intent_matches": self.intent_matches,
            "type_detection_matches": self.type_detection_matches,
            "keyword_scoring_routes": self.keyword_scoring_routes,
            "fallback_routes": self.fallback_routes,
            "multi_target_routes": self.multi_target_routes,
            "single_target_routes": self.single_target_routes,
        }


# =============================================================================
# Explicit Keyword Rules (Phase 1: Deterministic)
# =============================================================================

EXPLICIT_KEYWORDS: dict[str, list[str]] = {
    "patterns": [
        "паттерн", "pattern", "правило кода", "convention",
        "best practice", "bestpractice", "антипаттерн",
        "architecture", "design pattern", "standard",
    ],
    "facts": [
        "важно запомнить", "запомни", "сохранить", "fact",
        "важно", "вывод", "результат", "conclusion",
        "решение принято", "decision",
    ],
    "code": [
        "код", "function", "procedure", "class",
        "bsl", "python", "функция", "процедура",
    ],
    "skills": [
        "навык", "skill", "умение", "подтверждено",
        "confirmed", "best practice confirmed", "практика",
        "workflow", "рабочий процесс", "алгоритм работы",
    ],
    "wiki": [
        "wiki", "статья", "article", "документация",
        "promote", "продвинуть", "опубликовать", "publish",
        "obsidian", "заметка", "note", "драфт", "draft",
        "карточка", "card", "справка", "reference",
    ],
}

CATEGORY_TARGETS: dict[str, str] = {
    "patterns": "vector-memory",
    "facts": "memory-ai",
    "code": "vector-memory",
    "skills": "skill-learning",
    "wiki": "wiki",
}

INTENT_PATTERNS: dict[str, str] = {
    "сохранить в память": "memory-ai",
    "запомнить это": "memory-ai",
    "создать паттерн": "vector-memory",
    "сохранить навык": "skill-learning",
    "подтвердить практику": "skill-learning",
    "сохранить в wiki": "wiki",
    "promote to wiki": "wiki",
    "создать статью": "wiki",
    "опубликовать в wiki": "wiki",
    "создать заметку": "wiki",
    "wiki draft": "wiki",
}

# Content type detection patterns
CODE_PATTERNS: list[str] = [
    r"```(bsl|python|javascript|yaml|json)",
    r"Функция\s+\w+\s*\(",
    r"Процедура\s+\w+\s*\(",
    r"def\s+\w+\s*\(",
    r"class\s+\w+",
]

CONFIG_PATTERNS: list[str] = [
    r"\.(json|yaml|yml|xml|toml)",
    r"settings\.json",
    r"config\.",
]


# =============================================================================
# Keyword Lists for Scoring (Phase 2: Semantic)
# =============================================================================

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "patterns": [
        "bsl", "код", "функция", "процедура", "класс", "алгоритм",
        "паттерн", "pattern", "convention", "standard",
        "bestpractice", "архитектура", "design", "refactoring",
        "шаблон", "approach", "methodology", "strategy",
    ],
    "facts": [
        "важно", "запомнить", "сохранить", "fact",
        "вывод", "результат", "conclusion",
        "решение", "decision", "принято",
        "ошибка", "error", "bug", "issue",
        "fix", "исправлен", "решен",
    ],
    "skills": [
        "навык", "skill", "умение", "практика",
        "confirmed", "подтверждено", "workflow",
        "процесс", "алгоритм", "подход",
        "эффективный", "working", "проверенный",
    ],
}

# Valid target subsystems
VALID_TARGETS: set[str] = {"memory-ai", "vector-memory", "skill-learning", "wiki"}


# =============================================================================
# Auto-Classify Middleware (Memori pattern)
# =============================================================================


@dataclass
class ClassificationResult:
    """Result of content type auto-classification."""

    content_type: ContentType
    confidence: float  # 0..1
    signals: list[str]  # human-readable reasons

    def to_dict(self) -> dict[str, Any]:
        return {
            "content_type": self.content_type.value,
            "confidence": self.confidence,
            "signals": self.signals,
        }


# Patterns for content type classification
_FACT_SIGNALS: list[tuple[str, str]] = [
    (r"(?:важно|запомни|сохрани|решен[оие]|принято|вывод|conclusion|decision)", "keyword:fact"),
    (r"(?:ошибка|error|bug|issue|fix|исправлен)", "keyword:incident"),
    (r"(?:результат|итог|outcome)", "keyword:result"),
]

_PREFERENCE_SIGNALS: list[tuple[str, str]] = [
    (r"(?:предпочита|prefer|нравится|like|хочу|want|всегда использу|always use)", "keyword:preference"),
    (r"(?:не люблю|don'?t like|избега|avoid|никогда не|never)", "keyword:avoidance"),
    (r"(?:стиль|style|формат|format)", "keyword:style"),
]

_RULE_SIGNALS: list[tuple[str, str]] = [
    (r"(?:правило|rule|стандарт|standard|convention|запрещено|forbidden|обязательно|must)", "keyword:rule"),
    (r"(?:best.?practice|bestpractice|антипаттерн|anti.?pattern)", "keyword:practice"),
    (r"(?:lint|eslint|ruff|sonar)", "keyword:linter"),
]

_SKILL_SIGNALS: list[tuple[str, str]] = [
    (r"(?:навык|skill|умение|подтвержден|confirmed|практика)", "keyword:skill"),
    (r"(?:workflow|рабочий.?процесс|алгоритм.?работы)", "keyword:workflow"),
    (r"(?:проверенный|working|эффективный|efficient)", "keyword:proven"),
]

_CODE_SIGNALS: list[tuple[str, str]] = [
    (r"```(?:bsl|python|javascript|typescript|go|java|yaml|json|xml)", "codeblock"),
    (r"(?:Функция|Процедура)\s+\w+\s*\(", "bsl_definition"),
    (r"(?:def|class|function|const|let|var)\s+\w+", "code_definition"),
    (r"(?:import|from|require|include)\s+\w+", "import_statement"),
]

_CONTENT_TYPE_SIGNALS: dict[ContentType, list[tuple[str, str]]] = {
    ContentType.FACT: _FACT_SIGNALS,
    ContentType.PREFERENCE: _PREFERENCE_SIGNALS,
    ContentType.RULE: _RULE_SIGNALS,
    ContentType.SKILL: _SKILL_SIGNALS,
    ContentType.CODE: _CODE_SIGNALS,
}

# ContentType -> default routing target
CONTENT_TYPE_TARGETS: dict[ContentType, str] = {
    ContentType.FACT: "memory-ai",
    ContentType.PREFERENCE: "memory-ai",
    ContentType.RULE: "vector-memory",
    ContentType.SKILL: "skill-learning",
    ContentType.CODE: "vector-memory",
    ContentType.OBSERVATION: "memory-ai",
}


class ContentClassifier:
    """Middleware that auto-classifies content type before routing.

    Intercepts content, determines its ContentType (fact/preference/rule/skill/code),
    and annotates the metadata with classification result. The router then uses this
    to inform its routing decision.

    Reference: Memori (MemoriLabs/Memori) — auto-classify turns middleware.
    """

    def __init__(self):
        self._compiled: dict[ContentType, list[tuple[re.Pattern, str]]] = {}
        for ct, patterns in _CONTENT_TYPE_SIGNALS.items():
            self._compiled[ct] = [(re.compile(p, re.IGNORECASE), label) for p, label in patterns]

    def classify(self, content: str, metadata: dict[str, Any] | None = None) -> ClassificationResult:
        """Classify content into a ContentType with confidence and signals.

        Scoring: each matching signal adds weight. The type with the highest
        cumulative score wins. Ties are broken by priority order.
        """
        type_scores: dict[ContentType, float] = {}
        type_signals: dict[ContentType, list[str]] = {}

        for ct, patterns in self._compiled.items():
            score = 0.0
            signals: list[str] = []
            for regex, label in patterns:
                matches = regex.findall(content)
                if matches:
                    score += len(matches) * 0.3
                    signals.append(f"{label}(x{len(matches)})")
            if score > 0:
                type_scores[ct] = score
                type_signals[ct] = signals

        # Check metadata hints
        if metadata:
            hint = metadata.get("content_type")
            if hint:
                try:
                    hinted_ct = ContentType(hint)
                    type_scores[hinted_ct] = type_scores.get(hinted_ct, 0.0) + 1.0
                    type_signals.setdefault(hinted_ct, []).append("metadata_hint")
                except ValueError:
                    pass

        if not type_scores:
            return ClassificationResult(
                content_type=ContentType.OBSERVATION,
                confidence=0.3,
                signals=["no_signals_matched"],
            )

        # Pick the winner
        best_type = max(type_scores, key=lambda ct: type_scores[ct])
        raw_score = type_scores[best_type]
        confidence = min(raw_score / 3.0, 1.0)  # normalize: 3+ signals = 1.0

        return ClassificationResult(
            content_type=best_type,
            confidence=confidence,
            signals=type_signals.get(best_type, []),
        )


# =============================================================================
# MemoryRouter
# =============================================================================


class MemoryRouter:
    """Routes content to appropriate memory subsystems using 4-phase classification.

    Phase 0: Auto-classify middleware (ContentType detection)
    Phase 1: Rule-based classification (explicit keywords, intent, type detection)
    Phase 2: Keyword scoring (TF-IDF-like weighted scoring)
    Phase 3: Target selection (threshold-based)
    """

    def __init__(self, config: RouterConfig | None = None):
        self.config = config or RouterConfig()
        self.stats = RoutingStats()
        self._classifier = ContentClassifier()
        self._compile_patterns()

    def _compile_patterns(self):
        """Pre-compile regex patterns for content type detection."""
        self._code_patterns = [re.compile(p) for p in CODE_PATTERNS]
        self._config_patterns = [re.compile(p) for p in CONFIG_PATTERNS]

    def _validate_content(self, content: str) -> str:
        """Truncate content if over max length."""
        if len(content) > self.config.max_content_length:
            return content[: self.config.truncate_length]
        return content

    # ----- Phase 1: Rule-based classification -----

    async def _phase1_rule_classification(
        self, content: str, metadata: dict[str, Any] | None
    ) -> dict[str, float] | None:
        """Phase 1: Deterministic routing via explicit keywords, intents, and type detection."""

        # Check explicit keywords
        content_lower = content.lower()
        for category, keywords in EXPLICIT_KEYWORDS.items():
            for kw in keywords:
                if kw in content_lower:
                    target = CATEGORY_TARGETS.get(category)
                    if target:
                        self._track_stats("explicit")
                        return {target: 1.0}

        # Check intent patterns
        if self.config.enable_intent_detection:
            for intent_phrase, target in INTENT_PATTERNS.items():
                if intent_phrase in content_lower:
                    self._track_stats("intent")
                    return {target: 0.95}

        # Check content type (code blocks, config files)
        if self.config.enable_type_detection:
            for pattern in self._code_patterns:
                if pattern.search(content):
                    self._track_stats("type_detection")
                    return {"vector-memory": 0.85}
            for pattern in self._config_patterns:
                if pattern.search(content):
                    self._track_stats("type_detection")
                    return {"vector-memory": 0.7}

        return None

    # ----- Phase 2: Keyword scoring -----

    def _phase2_keyword_scoring(self, content: str) -> dict[str, float]:
        """Phase 2: TF-IDF-like keyword scoring across all categories."""
        content_lower = content.lower()
        words = set(content_lower.split())
        scores: dict[str, float] = {}

        weights = {
            "patterns": self.config.patterns_weight,
            "facts": self.config.facts_weight,
            "skills": self.config.skills_weight,
        }

        for category, keywords in CATEGORY_KEYWORDS.items():
            match_count = sum(1 for kw in keywords if kw in words or kw in content_lower)
            if match_count == 0:
                continue

            target = CATEGORY_TARGETS.get(category)
            if not target:
                continue

            raw_score = match_count / len(keywords)
            weighted = raw_score * weights.get(category, 1.0)
            current = scores.get(target, 0.0)
            scores[target] = current + weighted

        return scores

    # ----- Phase 3: Target selection -----

    def _phase3_select_targets(self, scores: dict[str, float]) -> list[str]:
        """Phase 3: Select targets based on confidence thresholds."""
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if not sorted_scores:
            return []

        top_target, top_score = sorted_scores[0]

        if top_score >= self.config.single_target_threshold:
            return [top_target]

        if len(sorted_scores) >= 2 and sorted_scores[1][1] >= self.config.dual_target_threshold:
            return [sorted_scores[0][0], sorted_scores[1][0]]

        if len(sorted_scores) >= 3 and sorted_scores[2][1] >= self.config.triple_target_threshold:
            return [s[0] for s in sorted_scores[:3]]

        # Fallback: top target only
        return [top_target]

    def _generate_reasoning(self, scores: dict[str, float], targets: list[str]) -> str:
        """Generate human-readable reasoning for the routing decision."""
        if not scores:
            return f"Fallback routing to {targets}"
        parts = []
        for target, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            parts.append(f"{target}({score:.2f})")
        return f"Routed by {self.stats.__dict__.get('total_routes', 0)} -> {', '.join(parts)}"

    def classify_content(self, content: str, metadata: dict[str, Any] | None = None) -> ClassificationResult:
        """Phase 0: Auto-classify content type (public API for external use)."""
        return self._classifier.classify(content, metadata)

    async def route(self, content: str, metadata: dict[str, Any] | None = None) -> RoutingDecision:
        """Main routing entry point: 4-phase classification.

        Phase 0: Auto-classify middleware (ContentType detection)
        Phase 1: Rule-based (explicit keywords, intent, type detection)
        Phase 2: Keyword scoring (TF-IDF-like)
        Phase 3: Target selection (threshold-based)

        Args:
            content: Content to classify and route.
            metadata: Optional metadata hints.

        Returns:
            RoutingDecision with target subsystems and confidences.
        """
        content = self._validate_content(content)
        self.stats.total_routes += 1

        # Phase 0: Auto-classify middleware
        classification = self._classifier.classify(content, metadata)
        if classification.confidence >= 0.6:
            target = CONTENT_TYPE_TARGETS[classification.content_type]
            self._track_stats("auto_classify")
            return RoutingDecision(
                targets=[target],
                confidences={target: classification.confidence},
                method="auto_classify",
                reasoning=(
                    f"Auto-classified as {classification.content_type.value} "
                    f"(conf={classification.confidence:.2f}, signals={classification.signals})"
                ),
                classification=classification,
            )

        # Phase 1: Rule-based
        rule_result = await self._phase1_rule_classification(content, metadata)
        if rule_result:
            self.stats.single_target_routes += 1
            return RoutingDecision(
                targets=list(rule_result.keys()),
                confidences=rule_result,
                method="explicit",
                reasoning=f"Explicit match: {rule_result}",
                classification=classification,
            )

        # Phase 2: Keyword scoring
        if self.config.enable_keyword_scoring:
            scores = self._phase2_keyword_scoring(content)
            if scores:
                targets = self._phase3_select_targets(scores)
                if len(targets) > 1:
                    self.stats.multi_target_routes += 1
                else:
                    self.stats.single_target_routes += 1
                self._track_stats("keyword_scoring")
                return RoutingDecision(
                    targets=targets,
                    confidences={t: scores.get(t, 0.0) for t in targets},
                    method="keyword_scoring",
                    reasoning=self._generate_reasoning(scores, targets),
                    classification=classification,
                )

        # Fallback: use classification hint if available, else memory-ai
        if classification.content_type != ContentType.OBSERVATION:
            target = CONTENT_TYPE_TARGETS[classification.content_type]
            self._track_stats("auto_classify")
            return RoutingDecision(
                targets=[target],
                confidences={target: max(classification.confidence, 0.3)},
                method="auto_classify_fallback",
                reasoning=(
                    f"Fallback to auto-classify: {classification.content_type.value} "
                    f"(conf={classification.confidence:.2f})"
                ),
                classification=classification,
            )

        self._track_stats("fallback")
        return RoutingDecision(
            targets=["memory-ai"],
            confidences={"memory-ai": 0.3},
            method="fallback",
            reasoning="No strong signals, defaulting to memory-ai",
            classification=classification,
        )

    def _track_stats(self, method: str):
        """Track routing statistics."""
        if method == "auto_classify":
            self.stats.auto_classify_matches += 1
        elif method == "explicit":
            self.stats.explicit_matches += 1
        elif method == "intent":
            self.stats.intent_matches += 1
        elif method == "type_detection":
            self.stats.type_detection_matches += 1
        elif method == "keyword_scoring":
            self.stats.keyword_scoring_routes += 1
        elif method == "fallback":
            self.stats.fallback_routes += 1

    def get_stats(self) -> RoutingStats:
        """Get routing statistics."""
        return self.stats

    def reset_stats(self):
        """Reset routing statistics."""
        self.stats = RoutingStats()


# =============================================================================
# Convenience Functions
# =============================================================================


async def route_memory(
    content: str,
    metadata: dict[str, Any] | None = None,
    config: RouterConfig | None = None,
) -> RoutingDecision:
    """Convenience function for routing memory content."""
    router = MemoryRouter(config)
    return await router.route(content, metadata)


__all__ = [
    "MemoryRouter",
    "RouterConfig",
    "RoutingDecision",
    "RoutingStats",
    "ClassificationResult",
    "ContentClassifier",
    "CONTENT_TYPE_TARGETS",
    "route_memory",
    "EXPLICIT_KEYWORDS",
    "CATEGORY_KEYWORDS",
    "INTENT_PATTERNS",
]
