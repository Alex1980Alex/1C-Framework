# Deep Analysis — Maximum Debug Coverage для `1c-debug-hmr` Pipeline

> **Дата:** 2026-05-11
> **Статус:** Research COMPLETE → Recommendations pending approval
> **Связано:** roadmaps 260510 + 260511 + 36_AUTONOMOUS_DEBUG_CONTROL

## §1. Executive Summary

Wrapper `1c-debug-hmr` достиг **production-grade baseline** после roadmaps 260508+260510+260511. 15 MCP tools, HMR persistent session, alias validation, 8-type target filter, no_fire_diagnostics, post-spawn polling, BP workspace re-apply. E2E PASS (GKSTCPLK-2468).

**НО** — покрыты только базовые DAP операции. Industry leaders (VS Code DAP, JetBrains IDEA, Chrome DevTools, pydevd, Coverage41C) предлагают **+11 классов features**. P0+P1 batch (~12-16ч) поднимет coverage с 8/19 до 14/19 industry-standard features.

## §2. Текущее vs Industry Feature Matrix

| Feature | 1c-debug-hmr now | VS Code DAP | IntelliJ | Chrome DevTools | pydevd |
|---|---|---|---|---|---|
| Line BP / stack / variables / eval / step | ✅ | ✅ | ✅ | ✅ | ✅ |
| Multi-target attach / remote / HMR | ✅ | ⚠ | ⚠ | ⚠ | ⚠ |
| **Conditional BP** (expression filter) | ❌ | ✅ | ✅ rich | ✅ | ✅ |
| **Hit-count BP** | ❌ | ✅ | ✅ | ✅ | ✅ |
| **Logpoint** (no halt) | ❌ | ✅ | ✅ | ✅ | ✅ |
| **Function BP** (method entry) | ❌ | ✅ | ✅ | ⚠ | ✅ |
| **Data BP** (variable change) | ❌ | ⚠ | ✅ | ✅ | ❌ |
| **Exception BP** | ❌ | ✅ | ✅ | ⚠ | ✅ |
| **Drop frame** (reset) | ❌ | ⚠ | ✅ | ❌ | ❌ |
| **Force return value** | ❌ | ❌ | ✅ | ❌ | ❌ |
| **Time-travel record/replay** | ❌ | ⚠ Replay.io | ⚠ rr | ⚠ RR | ⚠ PyTrace |
| **Precise coverage** (per-line callCount) | ❌ | ❌ | ⚠ | ✅ V8 | ❌ |
| **Coverage export** (genericCoverage.xml) | ❌ | ⚠ | ✅ | ⚠ | ⚠ |
| **CI artifact capture** | ❌ | ⚠ | ⚠ | ⚠ Replay | ❌ |
| **Source mapping** (UUID → FQN) | ⚠ partial | ✅ | ✅ | ✅ | ✅ |

**Gap summary:** 11/19 features absent. 4 critical (conditional, logpoint, coverage, CI artifacts).

## §3. Top-5 Best Practices с GitHub (deep research)

### BP-1: VS Code Debug Adapter Protocol — Conditional BPs + Logpoints

[microsoft/debug-adapter-protocol](https://github.com/microsoft/debug-adapter-protocol) — открытый стандарт, реализован ≥40 adapter'ами.

- `SetBreakpointsRequest.breakpoints[].condition` — expression evaluated при hit; BP не fire если false
- `SetBreakpointsRequest.breakpoints[].hitCondition` — `">10"` / `"%5"` (every 5th) / `"=3"`
- `SetBreakpointsRequest.breakpoints[].logMessage` — **logpoint**: evaluate + emit, no halt
- `FunctionBreakpointsRequest` — break on method entry by name
- `DataBreakpointsRequest` — break когда target variable changes value
- `ExceptionBreakpointsRequest` — break on raise

**Применимость к 1С:** RDBG XSD (`debugBreakpoints.xsd`) нужно проверить native support. Wrapper-level fallback — break + evaluate + auto-Continue if condition false. **Source:** [microsoft.github.io/debug-adapter-protocol/specification.html](https://microsoft.github.io/debug-adapter-protocol/specification.html), [code.visualstudio.com/blogs/2018/07/12/introducing-logpoints-and-auto-attach](https://code.visualstudio.com/blogs/2018/07/12/introducing-logpoints-and-auto-attach).
