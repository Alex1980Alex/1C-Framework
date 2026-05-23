"""Backend wiring helpers (Option A — Pre-filter ast-grep по call graph)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from ..classifier import RoutingMatrix
from .ast_grep_backend import AstGrepBackend, AstGrepRunner
from .call_graph_prefilter import CallGraphPreFilter

logger = logging.getLogger(__name__)

PREFILTER_DISABLE_ENV = "BSL_REFACTOR_NO_PREFILTER"


def build_ast_grep_backend(
    runner: AstGrepRunner,
    workspace_root: Path,
    *,
    project_root: Path | None = None,
    config: dict | None = None,
    env: dict[str, str] | None = None,
) -> AstGrepBackend:
    """Construct AstGrepBackend with optional CallGraphPreFilter wired in.

    Resolution order:
      1. env BSL_REFACTOR_NO_PREFILTER=1 → no prefilter (A/B kill switch)
      2. config (or routing_matrix.yaml global.ast_grep) flag
         use_call_graph_prefilter=False → no prefilter
      3. configured `call_graph_db` does not exist → no prefilter (graceful)
      4. else → prefilter wired with CallGraphStore opened on the DB
    """
    env_map = env if env is not None else os.environ
    if env_map.get(PREFILTER_DISABLE_ENV):
        logger.info("ast-grep prefilter disabled via %s", PREFILTER_DISABLE_ENV)
        return AstGrepBackend(runner=runner, workspace_root=workspace_root)

    cfg = config if config is not None else RoutingMatrix.ast_grep_global()
    if not cfg.get("use_call_graph_prefilter"):
        return AstGrepBackend(runner=runner, workspace_root=workspace_root)

    db_value = cfg.get("call_graph_db", "cache/bsl_call_graph.db")
    db_path = Path(db_value)
    if not db_path.is_absolute() and project_root is not None:
        db_path = project_root / db_path

    if not db_path.exists():
        logger.warning(
            "ast-grep prefilter enabled but call graph DB missing: %s; "
            "falling back to no-prefilter",
            db_path,
        )
        return AstGrepBackend(runner=runner, workspace_root=workspace_root)

    prefilter = _open_prefilter(db_path)
    return AstGrepBackend(runner=runner, workspace_root=workspace_root, prefilter=prefilter)


def _open_prefilter(db_path: Path) -> CallGraphPreFilter:
    # Local import avoids requiring sqlite-bound modules at import time.
    from src.bsl.call_graph.store import CallGraphStore

    return CallGraphPreFilter(CallGraphStore(str(db_path)))
