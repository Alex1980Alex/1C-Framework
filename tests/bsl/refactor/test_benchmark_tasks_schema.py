import json
from collections import Counter
from pathlib import Path

import pytest

try:
    import jsonschema
except ImportError:
    pytest.skip("jsonschema not installed", allow_module_level=True)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TASKS_FILE = PROJECT_ROOT / "docs" / "roadmap" / "benchmark" / "tasks.json"

VALID_CATEGORIES = [
    "CAT-1-local-variable",
    "CAT-2-module-local-proc",
    "CAT-3-cross-file-export",
    "CAT-4-form-handler",
    "CAT-5-edge-case",
]

TASKS_JSON_SCHEMA = {
    "type": "object",
    "required": ["version", "created_at", "source_repo", "tasks"],
    "additionalProperties": False,
    "properties": {
        "version": {"type": "integer", "const": 1},
        "created_at": {"type": "string", "format": "date"},
        "source_repo": {"type": "string", "minLength": 1},
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "id",
                    "category",
                    "commit_sha",
                    "parent_sha",
                    "file_uri",
                    "line",
                    "character",
                    "old_name",
                    "new_name",
                    "expected_files_affected",
                    "expected_edits",
                    "expected_files",
                    "notes",
                ],
                "additionalProperties": False,
                "properties": {
                    "id": {"type": "string", "pattern": r"^T\d{2}$"},
                    "category": {"type": "string", "enum": VALID_CATEGORIES},
                    "commit_sha": {"type": "string", "minLength": 1},
                    "parent_sha": {"type": "string", "minLength": 1},
                    "file_uri": {"type": "string", "minLength": 1},
                    "line": {"type": "integer", "minimum": 0},
                    "character": {"type": "integer", "minimum": 0},
                    "old_name": {"type": "string", "minLength": 1},
                    "new_name": {"type": "string", "minLength": 1},
                    "expected_files_affected": {"type": "integer", "minimum": 0},
                    "expected_edits": {"type": "integer", "minimum": 0},
                    "expected_files": {"type": "array", "items": {"type": "string"}},
                    "notes": {"type": "string", "minLength": 1},
                },
            },
        },
    },
}


@pytest.fixture(scope="module")
def tasks_data():
    if not TASKS_FILE.exists():
        pytest.skip(f"Tasks file not found: {TASKS_FILE}")
    return json.loads(TASKS_FILE.read_text(encoding="utf-8"))


def test_tasks_json_valid_schema(tasks_data):
    jsonschema.validate(instance=tasks_data, schema=TASKS_JSON_SCHEMA)


def test_tasks_json_has_20_tasks(tasks_data):
    assert len(tasks_data["tasks"]) == 20


def test_tasks_categories_balanced(tasks_data):
    counts = Counter(t["category"] for t in tasks_data["tasks"])
    for cat in VALID_CATEGORIES:
        assert counts[cat] == 4, f"Expected 4 tasks for {cat}, got {counts[cat]}"


def test_tasks_ground_truth_nonempty(tasks_data):
    for t in tasks_data["tasks"]:
        if t["category"] in ("CAT-3-cross-file-export", "CAT-4-form-handler"):
            assert len(t["expected_files"]) >= 2, (
                f"Task {t['id']} ({t['category']}) must have >= 2 expected_files"
            )


def test_tasks_commit_refs_present(tasks_data):
    for t in tasks_data["tasks"]:
        assert t["commit_sha"], f"Task {t['id']} has empty commit_sha"
        assert t["parent_sha"], f"Task {t['id']} has empty parent_sha"


def test_task_ids_unique(tasks_data):
    ids = [t["id"] for t in tasks_data["tasks"]]
    assert len(ids) == len(set(ids)), f"Duplicate task IDs: {ids}"


def test_task_ids_sequential(tasks_data):
    expected = [f"T{i:02d}" for i in range(1, 21)]
    actual = sorted(t["id"] for t in tasks_data["tasks"])
    assert actual == expected, f"Expected T01..T20, got {actual}"
