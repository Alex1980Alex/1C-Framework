"""
Trust Score Module for Skill-First Enforcement
Evaluates trustworthiness of information sources (Context7, GitHub, StackOverflow, Infostart.ru)

Author: Claude Code
Version: 1.0.0
Created: 2026-02-23
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional
import re


@dataclass
class TrustRubric:
    """Trust evaluation rubric for a source"""
    source: str
    criteria: Dict[str, float]  # criterion_name -> weight
    thresholds: Dict[str, Any]  # criterion_name -> threshold value
    description: str


class TrustScorer:
    """
    Evaluates trustworthiness of information sources using weighted rubrics.

    Trust scores range from 0.0 (untrusted) to 1.0 (fully trusted).
    """

    # Rubric definitions
    RUBRICS = {
        "context7": TrustRubric(
            source="context7",
            criteria={},
            thresholds={},
            description="Context7 official documentation (always trusted)"
        ),
        "github": TrustRubric(
            source="github",
            criteria={
                "stars": 0.30,          # Repository popularity
                "last_commit_days": 0.25,  # Recency of updates
                "has_docs": 0.25,       # README/docs existence
                "has_license": 0.20     # Open source license
            },
            thresholds={
                "stars": 100,           # >= 100 stars = good
                "last_commit_days": 90, # <= 90 days = good
                "has_docs": "yes",      # yes/no
                "has_license": ["MIT", "Apache", "BSD", "ISC"]  # Preferred licenses
            },
            description="GitHub repository evaluation"
        ),
        "stackoverflow": TrustRubric(
            source="stackoverflow",
            criteria={
                "is_accepted": 0.40,    # Answer marked as accepted
                "score": 0.30,          # Upvotes - downvotes
                "recency_days": 0.30    # How recent the answer is
            },
            thresholds={
                "is_accepted": True,
                "score": 3,             # >= 3 upvotes
                "recency_days": 365     # <= 1 year old
            },
            description="StackOverflow answer evaluation"
        ),
        "infostart": TrustRubric(
            source="infostart",
            criteria={
                "rating": 0.35,         # User rating (1-5 scale)
                "downloads": 0.35,      # Number of downloads
                "recency_days": 0.30    # Last update date
            },
            thresholds={
                "rating": 4.0,          # >= 4.0 stars
                "downloads": 100,       # >= 100 downloads
                "recency_days": 730     # <= 2 years old
            },
            description="Infostart.ru publication evaluation"
        )
    }

    @classmethod
    def compute_score(cls, source: str, data: Dict[str, Any]) -> float:
        """
        Compute trust score for a source based on provided data.

        Args:
            source: Source identifier ("context7", "github", "stackoverflow", "infostart")
            data: Dictionary with evaluation data for the source

        Returns:
            Trust score from 0.0 to 1.0

        Examples:
            >>> TrustScorer.compute_score("github", {"stars": 500, "last_commit_days": 30})
            0.925
            >>> TrustScorer.compute_score("context7", {})
            1.0
        """
        source = source.lower()
        rubric = cls.RUBRICS.get(source)

        if rubric is None:
            # Unknown source - return neutral score
            return 0.5

        # Context7 is always fully trusted
        if source == "context7":
            return 1.0

        # Compute weighted score for other sources
        total_score = 0.0

        for criterion, weight in rubric.criteria.items():
            threshold = rubric.thresholds.get(criterion)
            value = data.get(criterion)

            if value is None:
                # Missing data = partial score (0.5 for this criterion)
                criterion_score = 0.5
            else:
                criterion_score = cls._evaluate_criterion(value, threshold)

            total_score += criterion_score * weight

        return round(total_score, 3)

    @classmethod
    def _evaluate_criterion(cls, value: Any, threshold: Any) -> float:
        """
        Evaluate a single criterion against its threshold.

        Returns 1.0 if fully meets threshold, 0.0 if fails, 0.5 if partial.
        """
        if threshold is None:
            return 0.5

        # Boolean threshold (e.g., is_accepted: True)
        if isinstance(threshold, bool):
            return 1.0 if bool(value) == threshold else 0.0

        # Numeric threshold with >= comparison
        if isinstance(threshold, (int, float)):
            try:
                num_value = float(value)
                if num_value >= threshold:
                    return 1.0
                elif num_value >= threshold * 0.5:
                    return 0.5  # Partial credit for >= 50% of threshold
                else:
                    return 0.0
            except (ValueError, TypeError):
                return 0.0

        # List threshold (value must be in list)
        if isinstance(threshold, list):
            return 1.0 if value in threshold else 0.0

        # String threshold with yes/no
        if isinstance(threshold, str):
            if threshold.lower() == "yes":
                return 1.0 if str(value).lower() in ("yes", "true", "1") else 0.0
            if threshold.lower() == "no":
                return 1.0 if str(value).lower() in ("no", "false", "0") else 0.0

        # Pattern match (regex)
        if isinstance(threshold, str) and threshold.startswith("regex:"):
            pattern = threshold[6:]  # Remove "regex:" prefix
            return 1.0 if re.search(pattern, str(value)) else 0.0

        # Default: compare as strings
        return 1.0 if str(value) == str(threshold) else 0.0

    @classmethod
    def _matches_threshold(cls, value: Any, threshold: Any) -> bool:
        """
        Internal matcher for threshold expressions.

        Supports patterns like:
        - ">100" for numeric comparison
        - "yes"/"no" for boolean
        - "MIT|Apache" for pattern match
        """
        # Handle string expressions
        if isinstance(threshold, str):
            # Numeric comparison: ">100", "<=365"
            match = re.match(r'^([<>]=?)(\d+(?:\.\d+)?)$', threshold)
            if match:
                op = match.group(1)
                threshold_val = float(match.group(2))
                try:
                    val = float(value)
                    if op == ">": return val > threshold_val
                    if op == ">=": return val >= threshold_val
                    if op == "<": return val < threshold_val
                    if op == "<=": return val <= threshold_val
                except (ValueError, TypeError):
                    return False

            # Pattern match: "MIT|Apache|BSD"
            if "|" in threshold:
                return bool(re.search(threshold, str(value), re.IGNORECASE))

            # Yes/No
            if threshold.lower() in ("yes", "no"):
                expected = threshold.lower() == "yes"
                return str(value).lower() in ("yes", "true", "1") if expected else \
                       str(value).lower() in ("no", "false", "0")

        # Direct comparison
        return value == threshold

    @classmethod
    def format_trust_rubric(cls, domain: str) -> str:
        """
        Format trust rubric as text for system message.

        Args:
            domain: Research domain ("tech" or "1c")

        Returns:
            Formatted text with trust rubric information
        """
        if domain == "tech":
            sources = ["context7", "github", "stackoverflow"]
        elif domain == "1c":
            sources = ["infostart", "github", "stackoverflow"]
        else:
            sources = ["github", "stackoverflow"]

        lines = [
            "## Trust Scale for Information Sources",
            ""
        ]

        for source in sources:
            rubric = cls.RUBRICS.get(source)
            if rubric:
                lines.append(f"### {rubric.source.title()}")
                lines.append(f"**Description:** {rubric.description}")

                if rubric.criteria:
                    lines.append("**Criteria:**")
                    for criterion, weight in rubric.criteria.items():
                        threshold = rubric.thresholds.get(criterion)
                        lines.append(f"- {criterion} (weight: {weight:.0%}): threshold = {threshold}")

                lines.append("")

        return "\n".join(lines)

    @classmethod
    def get_research_protocol(cls, domain: str, label: str) -> str:
        """
        Get research protocol text for a given domain and label.

        Args:
            domain: Research domain ("tech" or "1c")
            label: Specific topic being researched

        Returns:
            Research protocol message with trust rubric
        """
        if domain == "tech":
            sources_order = ["Context7 documentation", "StackOverflow", "GitHub repositories"]
        else:  # 1c
            sources_order = ["Infostart.ru publications", "GitHub repositories", "its.1c.ru"]

        protocol = f"""## Research Protocol: {label}

You are about to implement code for **{label}** ({domain} domain).
Before writing any code, consult sources in this order:

### Research Order (Priority)
"""
        for i, source in enumerate(sources_order, 1):
            protocol += f"{i}. **{source}**\n"

        protocol += "\n" + cls.format_trust_rubric(domain)

        protocol += f"""

### Expected Outcome
After consulting sources, write code that follows:
- Best practices from trusted sources
- Common patterns in the ecosystem
- Security and performance considerations

If sources disagree, prioritize by trust score.
"""
        return protocol


# Export for use in hooks
__all__ = ["TrustScorer", "TrustRubric"]
