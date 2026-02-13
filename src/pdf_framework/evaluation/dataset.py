"""Evaluation dataset schemas.

Defines TestCase and EvalDataset models for loading ground-truth
evaluation data from JSON files.
"""

import json
from pathlib import Path

from pydantic import BaseModel


class TestCase(BaseModel):
    """Single evaluation test case with query and ground truth."""

    query: str
    relevant_chunk_ids: list[str] = []
    expected_keywords: list[str] = []
    category: str = ""  # factual / analytical / procedural / conceptual


class EvalDataset(BaseModel):
    """Collection of test cases for evaluation."""

    name: str
    test_cases: list[TestCase]

    @classmethod
    def from_json(cls, path: str) -> "EvalDataset":
        """Load dataset from a JSON file."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(**data)
