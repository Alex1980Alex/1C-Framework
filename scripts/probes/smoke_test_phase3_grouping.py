"""Smoke test for Phase 3 _group_chunks_for_late grouping logic
(roadmap 260518). Mirrors the production helper signature.
"""

from dataclasses import dataclass, field


@dataclass
class FakeChunk:
    metadata: dict = field(default_factory=dict)


def _group_chunks_for_late(chunks, region_aware):
    groups = {}
    for idx, c in enumerate(chunks):
        module_path = c.metadata.get("module_path", "")
        region = c.metadata.get("region", "") if region_aware else ""
        groups.setdefault((module_path, region), []).append(idx)
    return list(groups.values())


# Build a fake module with two regions + one symbol outside regions
chunks = [
    FakeChunk({"module_path": "ModuleA.bsl", "region": "ОбработчикиСобытийФормы"}),  # 0
    FakeChunk({"module_path": "ModuleA.bsl", "region": "ОбработчикиСобытийФормы"}),  # 1
    FakeChunk({"module_path": "ModuleA.bsl", "region": "ПрограммныйИнтерфейс"}),  # 2
    FakeChunk({"module_path": "ModuleA.bsl", "region": ""}),  # 3 (no region)
    FakeChunk({"module_path": "ModuleB.bsl", "region": "ОбработчикиСобытийФормы"}),  # 4
    FakeChunk({"module_path": "ModuleB.bsl", "region": ""}),  # 5
]

# Phase 3 ON: 5 groups
g = _group_chunks_for_late(chunks, region_aware=True)
assert sorted(g) == sorted([[0, 1], [2], [3], [4], [5]]), g
print(f"Test region-aware: {len(g)} groups (expected 5): {g}")

# Phase 3 OFF: 2 groups (one per module)
g = _group_chunks_for_late(chunks, region_aware=False)
assert sorted(g) == sorted([[0, 1, 2, 3], [4, 5]]), g
print(f"Test legacy module-grouping: {len(g)} groups (expected 2): {g}")

# Edge: empty chunks
assert _group_chunks_for_late([], region_aware=True) == []
print("Test empty input: OK")

# Edge: all chunks no region (legacy code without #Область)
chunks2 = [FakeChunk({"module_path": "Legacy.bsl"}) for _ in range(3)]
g = _group_chunks_for_late(chunks2, region_aware=True)
assert g == [[0, 1, 2]]
print(f"Test no-region module (legacy): {len(g)} group: {g}")

# Order preservation: chunk indices preserve module/region encounter order
chunks3 = [
    FakeChunk({"module_path": "M.bsl", "region": "Z"}),  # 0
    FakeChunk({"module_path": "M.bsl", "region": "A"}),  # 1
    FakeChunk({"module_path": "M.bsl", "region": "Z"}),  # 2
]
g = _group_chunks_for_late(chunks3, region_aware=True)
# Z group seen first, then A
assert g == [[0, 2], [1]], g
print(f"Test order preservation: {g}")

print("\nALL TESTS PASS")
