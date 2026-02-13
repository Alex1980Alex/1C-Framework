"""Local embedding engine using sentence-transformers.

Runs models locally via asyncio.to_thread for async compatibility.
Supports E5 models (intfloat/multilingual-e5-*) with automatic prefix handling.

Phase 43: ONNX/OpenVINO backend support for ~7x CPU speedup.
Set EMBEDDING__BACKEND=onnx or EMBEDDING__BACKEND=openvino in .env.
Requires: pip install onnxruntime (ONNX) or pip install openvino (OpenVINO).
"""

import asyncio
import logging
import time

from sentence_transformers import SentenceTransformer

from src.pdf_framework.config import EmbeddingSettings
from src.pdf_framework.embeddings.engine import BaseEmbeddingEngine

logger = logging.getLogger(__name__)


class LocalEmbeddingEngine(BaseEmbeddingEngine):
    """Generate embeddings using a local sentence-transformers model."""

    def __init__(self, settings: EmbeddingSettings | None = None):
        self._settings = settings or EmbeddingSettings()
        self._model: SentenceTransformer | None = None
        # E5 models require "query: " / "passage: " prefixes
        self._is_e5 = "e5" in self._settings.model.lower()

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            import torch

            device = self._settings.device
            if device == "auto":
                if torch.cuda.is_available():
                    device = "cuda"
                elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                    device = "mps"
                else:
                    device = "cpu"

            backend = self._settings.backend  # "torch" | "onnx" | "openvino"

            t0 = time.time()
            logger.info(
                "[EMBEDDING] Загрузка модели '%s' (%d dims) на %s, backend=%s...",
                self._settings.model, self._settings.dimensions, device, backend,
            )

            # Phase 43: ONNX/OpenVINO acceleration
            model_kwargs: dict = {"device": device}
            if backend != "torch":
                model_kwargs["backend"] = backend
                # ONNX/OpenVINO run on CPU — override device
                if device != "cpu":
                    logger.info(
                        "[EMBEDDING] Backend %s использует CPU (device=%s игнорируется)",
                        backend, device,
                    )
                    model_kwargs["device"] = "cpu"

            self._model = SentenceTransformer(self._settings.model, **model_kwargs)
            logger.info(
                "[EMBEDDING] Модель загружена за %.2f сек (device=%s, backend=%s, CUDA=%s)",
                time.time() - t0, model_kwargs["device"], backend, torch.cuda.is_available(),
            )
        return self._model

    def _add_prefix(self, texts: list[str], prefix: str) -> list[str]:
        """Add prefix for E5 models if needed."""
        if not self._is_e5:
            return texts
        return [f"{prefix}{t}" for t in texts]

    def _embed_sync(self, texts: list[str], prefix: str) -> list[list[float]]:
        model = self._get_model()
        prefixed = self._add_prefix(texts, prefix)
        embeddings = model.encode(
            prefixed,
            batch_size=self._settings.batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return embeddings.tolist()

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text (uses 'query: ' prefix for E5)."""
        results = await asyncio.to_thread(self._embed_sync, [text], "query: ")
        return results[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts (uses 'passage: ' prefix for E5)."""
        if not texts:
            return []
        t0 = time.time()
        total_chars = sum(len(t) for t in texts)
        result = await asyncio.to_thread(self._embed_sync, texts, "passage: ")
        elapsed = time.time() - t0
        logger.info(
            "[EMBEDDING] %d текстов (%d символов) → %d эмбеддингов за %.2f сек (%.0f текстов/сек)",
            len(texts), total_chars, len(result), elapsed,
            len(texts) / elapsed if elapsed > 0 else 0,
        )
        return result

    def get_dimensions(self) -> int:
        return self._settings.dimensions

    def get_model_name(self) -> str:
        return self._settings.model
