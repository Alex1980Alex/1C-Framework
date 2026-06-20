"""Throwaway smoke: подтвердить, что прод-путь BSLSearchService._call_qdrant_search
теперь идёт через hybrid RRF и возвращает хиты (TEI dense + FastEmbed bm25 + Qdrant RRF)."""

import asyncio
import importlib


class _QStub:
    collection_name = "bsl_code_v4_late"


async def main():
    m = importlib.import_module("src.bsl.semantic_search.services.search")
    cls = next(
        c for _n, c in vars(m).items() if isinstance(c, type) and hasattr(c, "_call_qdrant_search")
    )
    mgr = cls(qdrant_service=_QStub())
    queries = [
        "получить поддерживаемые версии для подключения к удалённому узлу обмена",
        "отразить изменения документа в дополнительных реестрах",
        "получить числовой код субъекта по его названию",
    ]
    for q in queries:
        res = await mgr._call_qdrant_search(q, 10, None)
        top = ""
        if res:
            mp = str(res[0].get("module_path") or res[0].get("name") or "?")
            top = "/".join(mp.replace("\\", "/").split("/")[-2:])
        print(f"hits={len(res):2d}  top={top!r}  q={q[:38]!r}")


if __name__ == "__main__":
    asyncio.run(main())
