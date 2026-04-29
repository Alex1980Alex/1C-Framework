"""Phase 8.12.8 shared config — paths, thresholds, collection ids."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTEFACT_DIR = ROOT / "tmp" / "phase8_12_8"
ARTEFACT_DIR.mkdir(parents=True, exist_ok=True)

CHUNKS_FILTERED = ARTEFACT_DIR / "chunks_filtered.jsonl"
CLUSTERS = ARTEFACT_DIR / "clusters.jsonl"
QUERIES_PILOT = ARTEFACT_DIR / "queries_pilot.jsonl"
GOLDEN_SET = ARTEFACT_DIR / "golden_set.jsonl"
EVAL_REPORT = ARTEFACT_DIR / "eval_report.json"

QDRANT_HOST = "localhost"
QDRANT_PORT = 6333

COLL_E5 = "bsl_code_v3"
COLL_QWEN3 = "bsl_code_v4"
COLL_QWEN3_LATE = "bsl_code_v4_late"

PILOT_QUERIES_TOTAL = 40
ANCHORS_PER_CLUSTER = 2
KL_DIV_THRESHOLD = 0.2
