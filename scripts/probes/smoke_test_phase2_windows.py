"""Smoke test for Phase 2 _make_char_windows helper from roadmap 260518.

Stand-alone copy of the helper exercised against the corner cases the
sliding-window Late Chunking relies on:
  - short text → single window
  - exact-boundary text → single window
  - oversized text → multiple overlapping windows that cover [0, n)
  - line-snapped breaks for line-oriented BSL code
  - overlap >= window must raise (would loop forever otherwise)
"""


class T:
    @staticmethod
    def _make_char_windows(text, window_chars, overlap_chars):
        n = len(text)
        if n <= window_chars:
            return [(0, text)]
        if overlap_chars >= window_chars:
            raise ValueError(
                f"overlap_chars ({overlap_chars}) must be < window_chars "
                f"({window_chars}) - sliding would loop forever otherwise."
            )
        windows = []
        step = window_chars - overlap_chars  # noqa: F841 (kept for parity)
        snap_zone = max(1, window_chars // 10)
        start = 0
        while start < n:
            ideal_end = min(start + window_chars, n)
            if ideal_end < n:
                snap_min = max(start + 1, ideal_end - snap_zone)
                nl = text.rfind("\n", snap_min, ideal_end)
                end = nl + 1 if nl != -1 else ideal_end
            else:
                end = ideal_end
            windows.append((start, text[start:end]))
            if end >= n:
                break
            next_start = max(start + 1, end - overlap_chars)
            if next_start < n:
                snap_max = min(n, next_start + snap_zone)
                nl = text.find("\n", next_start, snap_max)
                if nl != -1:
                    next_start = nl + 1
            start = next_start
        return windows


# Test 1: short text → single window
w = T._make_char_windows("hello", 100, 10)
assert w == [(0, "hello")], w
print("Test 1 OK: short text -> single window")

# Test 2: exact boundary
w = T._make_char_windows("a" * 100, 100, 10)
assert len(w) == 1, w
assert w[0] == (0, "a" * 100)
print("Test 2 OK: exact-boundary text -> single window")

# Test 3: 250 chars, window=100, overlap=20 → multiple windows, full coverage
text3 = "a" * 250
w = T._make_char_windows(text3, 100, 20)
print(f"Test 3: 250 chars / window 100 / overlap 20 -> {len(w)} windows")
covered = set()
for s, t in w:
    covered.update(range(s, s + len(t)))
assert covered == set(range(250)), f"coverage gap: {set(range(250)) - covered}"
print(f"  full coverage [0, 250) verified, offsets={[(s, len(t)) for s, t in w]}")

# Test 4: line snapping at production-realistic scale.
# snap_zone = window_chars // 10, so for snap to find a newline the gap
# between ideal_end and the previous \n must be <= snap_zone.
# Production Phase 2 uses window ~24K chars / snap_zone ~2400, well above
# typical BSL line length (~50-150 chars). Use 1000-char window so snap
# (zone=100) can reach back across 60-char lines.
text4 = ("a" * 60 + "\n") * 30  # 1830 chars total, lines of 61 chars
w = T._make_char_windows(text4, 1000, 200)
print(f"Test 4: line-snapped text -> {len(w)} windows")
for s, t in w[:3]:
    print(f"  offset={s} len={len(t)} ends_with_newline={t.endswith(chr(10))}")
# at least one non-final window should end on newline thanks to snap
assert any(t.endswith("\n") for _, t in w[:-1]), "no snap-to-newline happened"

# Test 5: overlap >= window
try:
    T._make_char_windows("a" * 200, 50, 50)
    raise AssertionError("Test 5 FAIL: should have raised")
except ValueError as e:
    print(f"Test 5 OK: raised ValueError: {e}")

# Test 6: big text (8K chars) with realistic window/overlap matching Phase 2 defaults
text6 = "Процедура Т() Экспорт\nКонецПроцедуры\n" * 250  # ~9.5K chars
w = T._make_char_windows(text6, 3000, 450)
print(f"Test 6: 9.5K chars / window 3000 / overlap 450 -> {len(w)} windows")
covered = set()
for s, t in w:
    covered.update(range(s, s + len(t)))
assert covered == set(range(len(text6))), "coverage gap"
print(f"  full coverage verified, len text={len(text6)}, windows={[(s, len(t)) for s, t in w]}")

print("\nALL TESTS PASS")
