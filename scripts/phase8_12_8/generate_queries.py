"""Phase 8.12.8 Step 3: Promptagator-style query generation via Z.AI.

TODO: load clusters.jsonl, stratified sample ANCHORS_PER_CLUSTER per
cluster, prompt Z.AI with negative-exemplar BSL-style instruction,
output queries_pilot.jsonl with {query, anchor_chunk_id, cluster_id}.

Promptagator prompt (target ~PILOT_QUERIES_TOTAL queries):
Контекст: модуль кластера {summary}, файл {module_path}.
Якорный символ: {symbol_name}\n{symbol_body[:2000]}
Сгенерируй ОДИН реалистичный вопрос BSL-разработчика 1С.
Запрещено повторять имена идентификаторов из символа дословно.
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.phase8_12_8 import config  # noqa: E402,F401

if __name__ == "__main__":
    raise NotImplementedError("Phase 8.12.8 Step 3 — TODO")
