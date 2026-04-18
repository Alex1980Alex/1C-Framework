# tree-sitter-bsl Coverage Report

**Version:** tree-sitter-bsl 0.1.6 (patched with `parenthesized_expression` fix)
**tree-sitter:** 0.25.2
**Date:** 2026-04-18

---

## Summary

| Metric | Value |
|---|---|
| Total files | 3 |
| Total lines | 1,518 |
| Total ERROR nodes | **0** (was 14 before fix) |
| ERR rate | **0.0%** (was 0.9%) |
| Applied fix | Added `parenthesized_expression` rule to `grammar.js` |

---

## Per-File Results

| # | Module | Type | Lines | Nodes | Errors | Status |
|---|---|---|---|---|---|---|
| 1 | гкс_ОчередьСообщенийRMQ | CommonModule | 679 | 3,900 | 0 (was 12) | OK |
| 2 | гкс_ФормировательСообщенийRMQ | DataProcessor (ObjectModule) | 217 | 1,039 | 0 (was 2) | OK |
| 3 | гкс_Взвешивание.ФормаДокумента | Form Module | 622 | 3,606 | 0 (unchanged) | OK |

---

## Fix Details

**Rule added to `grammar.js`:**

```js
parenthesized_expression: $ => seq('(', $.expression, ')'),
```

**Impact:**
- File 1: 12 errors -> 0 (fully resolved)
- File 2: 2 errors -> 0 (fully resolved)
- File 3: 0 errors -> 0 (unaffected)

---

## Conclusion

All 3 test files (1,518 lines, 8,545 AST nodes) parse with **zero errors** after applying the `parenthesized_expression` fix. The ERR rate dropped from **0.9% to 0.0%**.
