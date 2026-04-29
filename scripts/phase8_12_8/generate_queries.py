"""Phase 8.12.8 Step 3: Promptagator-style query generation via Z.AI."""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.http.models import FieldCondition, Filter, MatchValue

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.phase8_12_8 import config  # noqa: E402

PROMPT_TEMPLATE = """Контекст: модуль 1С {module_name} (тип: {module_type}), кластер связных символов: {top_modules}.

Якорный BSL-символ: {symbol_name}

Тело символа:
{symbol_body}

Сгенерируй ОДИН реалистичный вопрос BSL-разработчика 1С, который мог бы привести к этому символу через семантический поиск.

ТРЕБОВАНИЯ:
1. Стиль — как 1С-программист спрашивает в чате/документации (на русском).
2. Запрещено повторять имена идентификаторов из тела символа дословно.
3. Запрещено фразы "функция которая..." — пиши по сути решаемой задачи.
4. Длина 5-15 слов.

Примеры стиля:
- "как реализовать обмен данными по плану обмена"
- "проверка прав доступа при проведении документа"
- "регистрация изменений для распределённой ИБ"

Ответ — ТОЛЬКО ОДНА СТРОКА запроса, без префикса, кавычек или объяснений."""


def call_z_ai(prompt: str) -> str:
    """Placeholder — caller wires in mcp__llm-rotation__llm_complete."""
    return "stub-query"


def parse_symbol_id(sid: str) -> tuple[str, str]:
    if "::" not in sid:
        return "", sid
    module_path, name = sid.rsplit("::", 1)
    return module_path, name


def fetch_chunk(client: QdrantClient, name: str, module_path: str,
                collection: str) -> tuple[str | None, str | None, str | None]:
    flt = Filter(must=[
        FieldCondition(key="name", match=MatchValue(value=name)),
        FieldCondition(key="module_path", match=MatchValue(value=module_path)),
    ])
    records, _ = client.scroll(
        collection_name=collection, scroll_filter=flt,
        limit=1, with_payload=True, with_vectors=False,
    )
    if not records:
        return None, None, None
    p = records[0]
    payload = p.payload or {}
    return str(p.id), payload.get("content", ""), payload.get("module_type", "")


def select_clusters(clusters: list[dict], n: int) -> list[dict]:
    sorted_c = sorted(clusters, key=lambda x: x.get("size", 0), reverse=True)
    n_top = math.ceil(n * 0.7)
    top = sorted_c[:n_top]
    rest = sorted_c[n_top:]
    middle = random.sample(rest, min(n - n_top, len(rest))) if rest else []
    selected = top + middle
    random.shuffle(selected)
    return selected


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--clusters", type=Path, default=config.CLUSTERS)
    p.add_argument("--output", type=Path, default=config.QUERIES_PILOT)
    p.add_argument("--total", type=int, default=config.PILOT_QUERIES_TOTAL)
    p.add_argument("--anchors-per-cluster", type=int, default=config.ANCHORS_PER_CLUSTER)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--qdrant-collection", default=config.COLL_QWEN3)
    args = p.parse_args()
    random.seed(args.seed)

    clusters: list[dict] = []
    with open(args.clusters, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                clusters.append(json.loads(line))

    if not clusters:
        print("No clusters loaded.")
        return

    n_clusters = math.ceil(args.total / args.anchors_per_cluster)
    selected = select_clusters(clusters, n_clusters)
    print(f"[gen] {len(selected)} clusters selected (target {args.total} queries)")

    client = QdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT, timeout=30)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    generated = 0
    skipped_unmatched = 0

    with open(args.output, "w", encoding="utf-8") as out:
        for cluster in selected:
            if generated >= args.total:
                break
            members = cluster.get("members", [])
            top_modules = cluster.get("summary", {}).get("top_modules", [])
            if not members:
                continue
            anchors = random.sample(members, min(args.anchors_per_cluster, len(members)))
            for sid in anchors:
                if generated >= args.total:
                    break
                module_path, name = parse_symbol_id(sid)
                if not module_path:
                    continue
                chunk_id, content, module_type = fetch_chunk(
                    client, name, module_path, args.qdrant_collection,
                )
                if chunk_id is None or not content:
                    skipped_unmatched += 1
                    continue
                module_name = Path(module_path).parent.name or Path(module_path).name
                prompt = PROMPT_TEMPLATE.format(
                    module_name=module_name, module_type=module_type or "BSL",
                    top_modules=", ".join(str(m) for m in (top_modules or [])[:3]) or "—",
                    symbol_name=name, symbol_body=content[:3000],
                )
                query = call_z_ai(prompt).strip()
                if not query:
                    continue
                out.write(json.dumps({
                    "query": query, "anchor_chunk_id": chunk_id, "anchor_symbol_id": sid,
                    "cluster_id": cluster.get("cluster_id"),
                    "cluster_top_modules": top_modules,
                    "anchor_module_path": module_path, "anchor_name": name,
                }, ensure_ascii=False) + "\n")
                generated += 1
                if generated % 10 == 0:
                    print(f"[{generated}/{args.total}] last: {sid}")

    print(f"Generated {generated} queries → {args.output} (skipped unmatched: {skipped_unmatched})")


if __name__ == "__main__":
    main()
