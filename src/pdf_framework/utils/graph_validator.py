"""LangGraph CompiledGraph validator.

Validates compiled LangGraph graphs for structural correctness:
- Reachability from START
- Dangling nodes (no outgoing edges and not END)
- Infinite cycles (cycles without a conditional exit)
- Required state fields presence

Usage::

    from langgraph.graph import StateGraph, MessagesState, START, END

    graph = StateGraph(MessagesState)
    graph.add_node("a", my_fn)
    graph.add_edge(START, "a")
    graph.add_edge("a", END)
    compiled = graph.compile()

    result = validate_graph(compiled, required_state_fields=["messages"])
    assert result.is_valid
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, get_type_hints

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph


__all__ = ["GraphValidationResult", "validate_graph"]

_START = "__start__"
_END = "__end__"


@dataclass
class GraphValidationResult:
    """Result of graph validation."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0


def validate_graph(
    graph: CompiledStateGraph,
    required_state_fields: list[str] | None = None,
) -> GraphValidationResult:
    """Validate a compiled LangGraph for structural correctness.

    Checks performed:
        1. All nodes are reachable from ``__start__``.
        2. No dangling nodes (nodes with no outgoing edges that are not
           ``__end__``).
        3. No cycles that lack a conditional exit (potential infinite loops).
        4. State schema contains all *required_state_fields* (when provided).

    Args:
        graph: A compiled LangGraph ``CompiledStateGraph`` instance.
        required_state_fields: Optional list of field names that must be
            present in the graph's state TypedDict schema.

    Returns:
        A :class:`GraphValidationResult` with validation outcome.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # ------------------------------------------------------------------
    # Extract topology from builder (authoritative source) and drawable
    # graph (for reachability / dangling checks including auto-edges).
    #
    # builder.edges: set of (source, target) tuples — user-defined static
    # builder.branches: dict[source -> dict[name -> BranchSpec]] — user-
    #   defined conditional edges.  BranchSpec.ends maps labels to targets.
    #
    # drawable graph includes auto-generated edges (e.g. runtime adds a
    # conditional __end__ edge to cycles for recursion-limit safety).
    # We use it for full adjacency but distinguish user-conditional from
    # auto-generated edges when analysing cycles.
    # ------------------------------------------------------------------
    drawable = graph.get_graph()

    node_ids: set[str] = set(drawable.nodes.keys())
    edges = drawable.edges

    # Full adjacency (includes auto-generated edges)
    adjacency: dict[str, list[str]] = {n: [] for n in node_ids}
    for edge in edges:
        adjacency[edge.source].append(edge.target)

    # User-defined conditional targets — from builder.branches only
    # (excludes runtime auto-generated conditional __end__ edges)
    user_conditional_targets: dict[str, set[str]] = {n: set() for n in node_ids}
    try:
        for source, branches in graph.builder.branches.items():
            for _name, branch_spec in branches.items():
                if branch_spec.ends:
                    for target in branch_spec.ends.values():
                        user_conditional_targets[source].add(target)
    except AttributeError:
        # Fallback: use drawable conditional edges if builder API changed
        for edge in edges:
            if edge.conditional:
                user_conditional_targets[edge.source].add(edge.target)

    edge_count = len(edges)
    # User-visible nodes (exclude virtual __start__ / __end__)
    user_nodes = node_ids - {_START, _END}
    node_count = len(user_nodes)

    # ------------------------------------------------------------------
    # 1. Reachability from START
    # ------------------------------------------------------------------
    reachable = _bfs(adjacency, _START)
    unreachable = user_nodes - reachable
    for node in sorted(unreachable):
        errors.append(f"Node '{node}' is not reachable from START")

    # ------------------------------------------------------------------
    # 2. Dangling nodes — no outgoing edges and not __end__
    # ------------------------------------------------------------------
    for node in sorted(user_nodes):
        if not adjacency.get(node):
            errors.append(
                f"Node '{node}' has no outgoing edges and is not END (dangling)"
            )

    # ------------------------------------------------------------------
    # 3. Cycles without conditional exit (infinite loop detection)
    # ------------------------------------------------------------------
    cycles = _find_cycles(adjacency, user_nodes)
    for cycle in cycles:
        cycle_set = set(cycle)
        has_conditional_exit = False
        for node in cycle:
            for target in conditional_targets.get(node, set()):
                if target not in cycle_set:
                    has_conditional_exit = True
                    break
            if has_conditional_exit:
                break

        cycle_repr = " -> ".join(cycle + [cycle[0]])
        if not has_conditional_exit:
            errors.append(
                f"Cycle without conditional exit (potential infinite loop): "
                f"{cycle_repr}"
            )
        else:
            warnings.append(
                f"Cycle detected (has conditional exit, OK): {cycle_repr}"
            )

    # ------------------------------------------------------------------
    # 4. Required state fields
    # ------------------------------------------------------------------
    if required_state_fields:
        state_fields = _extract_state_fields(graph)
        for req in required_state_fields:
            if req not in state_fields:
                errors.append(
                    f"Required state field '{req}' not found in schema. "
                    f"Available fields: {sorted(state_fields)}"
                )

    is_valid = len(errors) == 0
    return GraphValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        node_count=node_count,
        edge_count=edge_count,
    )


# ======================================================================
# Internal helpers
# ======================================================================


def _bfs(adjacency: dict[str, list[str]], start: str) -> set[str]:
    """Breadth-first search returning all reachable node ids."""
    visited: set[str] = set()
    queue: deque[str] = deque([start])
    while queue:
        node = queue.popleft()
        if node in visited:
            continue
        visited.add(node)
        for neighbour in adjacency.get(node, []):
            if neighbour not in visited:
                queue.append(neighbour)
    return visited


def _find_cycles(
    adjacency: dict[str, list[str]],
    user_nodes: set[str],
) -> list[list[str]]:
    """Find elementary cycles via DFS back-edge detection.

    Returns a list of cycles where each cycle is a list of node IDs.
    Skips ``__start__`` and ``__end__`` since they cannot participate
    in meaningful loops.
    """
    cycles: list[list[str]] = []
    color: dict[str, int] = {n: 0 for n in user_nodes}  # 0=white 1=gray 2=black
    path: list[str] = []
    path_set: set[str] = set()

    def _dfs(node: str) -> None:
        color[node] = 1  # gray — in current path
        path.append(node)
        path_set.add(node)

        for neighbour in adjacency.get(node, []):
            if neighbour in (_END, _START):
                continue
            if neighbour not in color:
                continue  # skip nodes outside user_nodes
            if color[neighbour] == 1 and neighbour in path_set:
                # Back-edge found — extract the cycle
                idx = path.index(neighbour)
                cycle = path[idx:]
                if cycle:
                    # Normalise: rotate to start from lex-smallest node
                    min_idx = cycle.index(min(cycle))
                    normalised = cycle[min_idx:] + cycle[:min_idx]
                    if normalised not in cycles:
                        cycles.append(normalised)
            elif color[neighbour] == 0:
                _dfs(neighbour)

        path.pop()
        path_set.discard(node)
        color[node] = 2  # black — fully explored

    for node in sorted(user_nodes):
        if color[node] == 0:
            _dfs(node)

    return cycles


def _extract_state_fields(graph: CompiledStateGraph) -> set[str]:
    """Extract field names from the graph's state schema.

    Tries two strategies:
    1. ``builder.schemas`` — iterate TypedDict classes, extract type hints.
    2. ``channels`` — fallback, filter out internal channel names.
    """
    fields: set[str] = set()

    # Strategy 1: TypedDict schemas from builder
    try:
        schemas = graph.builder.schemas
        for schema_cls in schemas:
            try:
                hints = get_type_hints(schema_cls)
                fields.update(hints.keys())
            except Exception:
                annotations = getattr(schema_cls, "__annotations__", {})
                fields.update(annotations.keys())
    except AttributeError:
        pass

    # Strategy 2: Fallback to channels (filter out internal ones)
    if not fields:
        try:
            internal_prefixes = ("__", "branch:")
            for ch_name in graph.channels:
                if not any(ch_name.startswith(p) for p in internal_prefixes):
                    fields.add(ch_name)
        except AttributeError:
            pass

    return fields
