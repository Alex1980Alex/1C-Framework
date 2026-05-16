"""Register local/zero-cost models in Langfuse Cloud (roadmap 260515 §6).

Roadmap §6 Risks row 1: "Custom models (Qwen3 local, embeddings) ->
cost_details.total = null". This script registers every non-cloud model
used by the framework with input/output price = $0, so Langfuse fills
cost_details.total = 0.0 instead of null. Without it the cost baseline
under-counts (NULL cost rows excluded from sum) and by-model section
hides local providers entirely.

Idempotent: lists existing models via client.api.models.list and skips
any model_name already registered. Safe to run on cron or repeatedly.

Usage:
    python scripts/setup_langfuse_local_pricing.py             # apply
    python scripts/setup_langfuse_local_pricing.py --dry-run   # plan only

Reuses singleton client from observability/langfuse_setup.py.

Roadmap: docs/roadmap/260515_ROADMAP_LANGFUSE_COST_BASELINE.md
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer

# Force UTF-8 on Windows console for any non-ASCII content.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pdf_framework.observability.langfuse_setup import _get_langfuse_client  # noqa: E402

logger = logging.getLogger(__name__)
app = typer.Typer(help="Register local/zero-cost models in Langfuse")


@dataclass(frozen=True)
class LocalModel:
    """Local or 3rd-party model that needs $0 pricing for Langfuse cost tracking.

    - `model_name`: canonical name shown in Langfuse Model Library.
    - `match_pattern`: regex (Langfuse-side) used to attribute a generation
      span to this model. Span field `model` is matched against this.
    - `unit`: usage unit. TOKENS for LLM/embedding/reranker, IMAGES for
      visual models.
    """

    model_name: str
    match_pattern: str
    unit: str  # "TOKENS" | "CHARACTERS" | "IMAGES" | "REQUESTS"


# Canonical roster of non-Anthropic-cloud models the framework emits.
# Maintained alongside src/shared/llm_rotation/service.py (providers) and
# config defaults (embedding/reranker). Source of truth: this file.
LOCAL_MODELS: tuple[LocalModel, ...] = (
    # ── Z.AI GLM family (paid via Z.AI proxy, treated as $0 in Langfuse
    # because cost tracking happens upstream in src/shared/llm_rotation)
    LocalModel("glm-5.1", r"(?i)^glm-5\.1$", "TOKENS"),
    LocalModel("glm-5", r"(?i)^glm-5$", "TOKENS"),
    LocalModel("glm-4.6", r"(?i)^glm-4\.6$", "TOKENS"),
    LocalModel("glm-4.5-air", r"(?i)^glm-4\.5-air$", "TOKENS"),
    LocalModel("glm-4-flash", r"(?i)^glm-4-flash$", "TOKENS"),
    LocalModel("glm-4-plus", r"(?i)^glm-4-plus$", "TOKENS"),
    # ── Ollama local LLMs
    LocalModel("qwen2.5-coder:7b", r"(?i)^qwen2\.5-coder:7b$", "TOKENS"),
    LocalModel("qwen2.5:7b", r"(?i)^qwen2\.5:7b$", "TOKENS"),
    LocalModel("llama3.1:8b", r"(?i)^llama3\.1:8b$", "TOKENS"),
    # ── Embeddings (Phase 8 production)
    LocalModel(
        "Qwen/Qwen3-Embedding-8B",
        r"(?i)^Qwen/Qwen3-Embedding-8B$",
        "TOKENS",
    ),
    # ── Embeddings (legacy, still emit until Phase 9 deprecation)
    LocalModel(
        "intfloat/multilingual-e5-large",
        r"(?i)^intfloat/multilingual-e5-large$",
        "TOKENS",
    ),
    LocalModel(
        "nomic-embed-text",
        r"(?i)^nomic-embed-text(:v1\.5)?$",
        "TOKENS",
    ),
    # ── Rerankers (local cross-encoders)
    LocalModel(
        "BAAI/bge-reranker-v2-m3",
        r"(?i)^BAAI/bge-reranker-v2-m3$",
        "TOKENS",
    ),
    LocalModel("ms-marco-MiniLM-L-6-v2", r"(?i)^ms-marco-MiniLM-L-6-v2$", "TOKENS"),
    # ── Visual (ColPali — page-level, billed in IMAGES)
    LocalModel("vidore/colpali-v1.3", r"(?i)^vidore/colpali-v1\.3$", "IMAGES"),
)


def _list_existing_names(client: Any) -> set[str]:
    """Page through models.list() and collect existing model_name set."""
    names: set[str] = set()
    page = 1
    while True:
        try:
            res = client.api.models.list(page=page, limit=100)
        except Exception:
            logger.exception("models.list page=%s failed", page)
            return names
        data = list(getattr(res, "data", []) or [])
        for m in data:
            n = getattr(m, "model_name", None)
            if n:
                names.add(str(n))
        meta = getattr(res, "meta", None)
        # Langfuse PaginatedModels meta: total_pages / page / etc.
        total_pages = getattr(meta, "total_pages", 1) if meta else 1
        if page >= total_pages or not data:
            return names
        page += 1


def _register(client: Any, m: LocalModel) -> bool:
    """Create a $0-priced model entry. Returns True on success."""
    try:
        client.api.models.create(
            model_name=m.model_name,
            match_pattern=m.match_pattern,
            unit=m.unit,
            input_price=0.0,
            output_price=0.0,
        )
        return True
    except Exception as e:
        logger.warning("models.create %s failed: %s", m.model_name, e)
        return False


@app.command()
def main(
    dry_run: bool = typer.Option(False, help="Plan only — do not POST to Langfuse"),
) -> None:
    """Register every LOCAL_MODELS entry missing from Langfuse with $0 pricing."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    client = _get_langfuse_client()
    if client is None:
        typer.secho(
            "Langfuse not enabled or creds missing. "
            "Check .env (OBSERVABILITY__LANGFUSE_*) or repo secrets.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)

    typer.secho("Fetching existing models from Langfuse...", fg=typer.colors.CYAN)
    existing = _list_existing_names(client)
    typer.secho(f"  found {len(existing)} existing model(s)", fg=typer.colors.CYAN)

    to_register = [m for m in LOCAL_MODELS if m.model_name not in existing]
    skipped = len(LOCAL_MODELS) - len(to_register)

    if not to_register:
        typer.secho(
            f"All {len(LOCAL_MODELS)} canonical local models already registered.",
            fg=typer.colors.GREEN,
        )
        return

    typer.secho(
        f"\nPlan: register {len(to_register)} model(s), skip {skipped} already present.",
        fg=typer.colors.YELLOW,
    )
    for m in to_register:
        typer.echo(f"  + {m.model_name}  (pattern={m.match_pattern}  unit={m.unit})")

    if dry_run:
        typer.secho("\n--dry-run: nothing posted.", fg=typer.colors.YELLOW)
        return

    typer.secho("\nRegistering...", fg=typer.colors.CYAN)
    ok = 0
    fail = 0
    for m in to_register:
        if _register(client, m):
            typer.secho(f"  OK  {m.model_name}", fg=typer.colors.GREEN)
            ok += 1
        else:
            typer.secho(f"  FAIL {m.model_name}", fg=typer.colors.RED)
            fail += 1

    typer.secho(
        f"\nDone: {ok} registered, {fail} failed, {skipped} already present.",
        fg=typer.colors.GREEN if fail == 0 else typer.colors.YELLOW,
    )
    if fail > 0:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
