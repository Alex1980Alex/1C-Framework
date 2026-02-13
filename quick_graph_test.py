"""Quick graph extraction test with first 10 chunks."""

import asyncio
from pathlib import Path

from src.api.dependencies.components import Components


async def quick_test():
    """Test graph extraction on first 10 chunks."""
    print("Quick Graph Extraction Test")
    print("=" * 60)

    components = Components()
    await components.initialize()

    pdf_file = list(Path("data/pdfs").glob("*.pdf"))[0]
    document = await components.loader.load(str(pdf_file))
    chunks = components.pipeline.process(document)

    # Take first 10 chunks
    test_chunks = chunks[:10]
    print(f"Testing with {len(test_chunks)} chunks from {pdf_file.name}")
    print()

    from src.pdf_framework.graph_store.construction.builder import GraphBuilder
    from src.pdf_framework.processing.extractors.entity_extractor import (
        LLMEntityExtractor,
    )

    # Clear graph
    from src.pdf_framework.graph_store.providers.networkx_store import NetworkXGraphStore

    components.graph_store = NetworkXGraphStore(
        settings=components.settings.graph_store
    )

    extractor = LLMEntityExtractor(
        settings=components.settings.agent,
        api_key=components.settings.anthropic_api_key,
    )
    builder = GraphBuilder(extractor, components.graph_store)

    total_entities = 0
    total_relations = 0

    for i, chunk in enumerate(test_chunks, 1):
        print(f"[{i}/{len(test_chunks)}] Processing chunk...", end="\r")
        extraction = await extractor.extract(chunk)
        entities_added, relations_added = await builder._store_extraction(extraction)
        total_entities += entities_added
        total_relations += relations_added

    print()
    print(f"\nResults:")
    print(f"  Entities extracted: {total_entities}")
    print(f"  Relations extracted: {total_relations}")

    stats = await components.graph_store.get_statistics()
    print(f"\nGraph stats:")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    asyncio.run(quick_test())
