"""Throwaway smoke: подтвердить, что прод-путь _call_qdrant_search идёт через DBSF-fusion и возвращает хиты."""

import asyncio
import importlib


class _Q:
    collection_name = "bsl_code_v4_late"


async def main():
    m = importlib.import_module("src.bsl.semantic_search.services.search")
    cls = next(
        c for _n, c in vars(m).items() if isinstance(c, type) and hasattr(c, "_call_qdrant_search")
    )
    mgr = cls(qdrant_service=_Q())
    for q in [
        "получить поддерживаемые версии для подключения к удалённому узлу",
        "отразить изменения документа в дополнительных реестрах",
    ]:
        res = await mgr._call_qdrant_search(q, 10, None)
        print(f"hits={len(res):2d}  q={q[:40]!r}")


if __name__ == "__main__":
    asyncio.run(main())
