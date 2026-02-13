"""Claude Vision Image Describer (Phase 15.2).

Generates detailed text descriptions of images using Claude Vision API.
Descriptions are used for semantic search alongside text chunks.

Author: Claude Code
Version: 1.0.0 - Phase 15.2: Multimodal Image Understanding
"""

import base64
import hashlib
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from anthropic import Anthropic

from src.pdf_framework.schemas.images import (
    ImageChunk,
    ImageDescriptionRequest,
    ImageDescriptionResponse,
)

logger = logging.getLogger(__name__)


# Default prompts for different document types
DEFAULT_PROMPTS = {
    "default": "Describe this image in detail. What does it show? What information does it convey?",
    "screenshot": "Describe this user interface screenshot. What elements are visible? What actions can be performed?",
    "diagram": "Describe this diagram or flowchart. What process or relationship does it illustrate?",
    "table": "Describe this table structure. What data does it contain?",
    "chart": "Describe this chart or graph. What trends or patterns does it show?",
}


class ImageDescriber:
    """Generates descriptions of images using Claude Vision API."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-sonnet-4-5-20250929",
        max_tokens: int = 1024,
        cache_dir: Path | None = None,
        cache_enabled: bool = True,
    ):
        """Initialize the image describer.

        Args:
            api_key: Anthropic API key (empty = use env ANTHROPIC_API_KEY)
            model: Claude model to use for descriptions
            max_tokens: Maximum tokens in description
            cache_dir: Directory for caching descriptions (default: data/cache/image_descriptions)
            cache_enabled: Enable description caching
        """
        self._client = Anthropic(api_key=api_key or None)
        self._model = model
        self._max_tokens = max_tokens
        self._cache_enabled = cache_enabled
        self._cache_dir = cache_dir or Path.cwd() / "data" / "cache" / "image_descriptions"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def describe(
        self,
        request: ImageDescriptionRequest,
        prompt_template: str | None = None,
        detect_type: bool = True,
    ) -> ImageDescriptionResponse:
        """Generate a description for an image.

        Args:
            request: Image description request with image bytes and context
            prompt_template: Custom prompt (uses default if None)
            detect_type: Auto-detect image type for specialized prompt

        Returns:
            ImageDescriptionResponse with description and metadata
        """
        t0 = time.time()

        # Check cache first
        if self._cache_enabled:
            cached = self._get_cached_description(request.image_bytes)
            if cached:
                logger.debug(f"[VISION] Cache hit for image ({len(request.image_bytes)} bytes)")
                ts = cached.get("timestamp")
                return ImageDescriptionResponse(
                    description=cached["description"],
                    model_used=cached["model_used"],
                    timestamp=ts if isinstance(ts, datetime) else None,
                    processing_time_ms=0.0,
                    success=True,
                )

        # Select prompt based on context or auto-detection
        prompt = prompt_template or self._select_prompt(request, detect_type)

        # Add context to prompt if available
        if request.context:
            prompt += f"\n\nContext from document:\n{request.context[:500]}"

        # Build API request
        image_media_type = f"image/{request.image_format}"
        image_data = base64.standard_b64encode(request.image_bytes).decode("utf-8")

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": image_media_type,
                                    "data": image_data,
                                },
                            }
                        ],
                    }
                ],
            )

            description = response.content[0].text
            elapsed_ms = (time.time() - t0) * 1000

            logger.info(
                f"[VISION] Described image ({len(request.image_bytes)} bytes) "
                f"in {elapsed_ms:.0f}ms using {self._model}"
            )

            result = ImageDescriptionResponse(
                description=description,
                model_used=self._model,
                processing_time_ms=elapsed_ms,
                success=True,
            )

            # Cache the result
            if self._cache_enabled:
                self._cache_description(request.image_bytes, result)

            return result

        except Exception as e:
            elapsed_ms = (time.time() - t0) * 1000
            logger.error(f"[VISION] Failed to describe image: {e}")

            return ImageDescriptionResponse(
                description="[Image description failed]",
                model_used=self._model,
                processing_time_ms=elapsed_ms,
                success=False,
                error_message=str(e),
            )

    def describe_batch(
        self,
        requests: list[ImageDescriptionRequest],
        parallel: bool = True,
    ) -> list[ImageDescriptionResponse]:
        """Describe multiple images (optionally in parallel).

        Args:
            requests: List of image description requests
            parallel: Process in parallel (faster but more API calls)

        Returns:
            List of image description responses
        """
        if not parallel:
            return [self.describe(req) for req in requests]

        # Parallel processing
        import asyncio

        async def describe_all():
            loop = asyncio.get_event_loop()
            tasks = [
                loop.run_in_executor(None, self.describe, req)
                for req in requests
            ]
            return await asyncio.gather(*tasks)

        return asyncio.run(describe_all())

    def _select_prompt(
        self,
        request: ImageDescriptionRequest,
        detect_type: bool,
    ) -> str:
        """Select appropriate prompt based on image context.

        Args:
            request: Image description request
            detect_type: Whether to auto-detect image type

        Returns:
            Prompt string for Claude Vision
        """
        # Use custom prompt if provided
        if request.prompt:
            return request.prompt

        # Auto-detect from context
        if detect_type and request.context:
            context_lower = request.context.lower()

            if "скриншот" in context_lower or "интерфейс" in context_lower or "screenshot" in context_lower:
                return DEFAULT_PROMPTS["screenshot"]
            if "диаграмм" in context_lower or "схем" in context_lower or "диаграмма" in context_lower:
                return DEFAULT_PROMPTS["diagram"]
            if "таблиц" in context_lower or "table" in context_lower:
                return DEFAULT_PROMPTS["table"]
            if "график" in context_lower or "chart" in context_lower or "диаграмм" in context_lower:
                return DEFAULT_PROMPTS["chart"]

        return DEFAULT_PROMPTS["default"]

    def _get_cache_key(self, image_bytes: bytes) -> str:
        """Generate cache key from image bytes (SHA-256 hash)."""
        return hashlib.sha256(image_bytes).hexdigest()

    def _get_cached_description(self, image_bytes: bytes) -> dict[str, Any] | None:
        """Get cached description if available."""
        if not self._cache_enabled:
            return None

        cache_key = self._get_cache_key(image_bytes)
        cache_file = self._cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            return None

        try:
            import json
            from datetime import datetime

            data = json.loads(cache_file.read_text(encoding="utf-8"))
            # Parse timestamp
            if "timestamp" in data:
                data["timestamp"] = datetime.fromisoformat(data["timestamp"])
            return data
        except Exception as e:
            logger.warning(f"[VISION] Failed to load cache: {e}")
            return None

    def _cache_description(self, image_bytes: bytes, response: ImageDescriptionResponse):
        """Cache a description for future use."""
        if not self._cache_enabled:
            return

        cache_key = self._get_cache_key(image_bytes)
        cache_file = self._cache_dir / f"{cache_key}.json"

        try:
            import json

            data = {
                "description": response.description,
                "model_used": response.model_used,
                "timestamp": response.timestamp.isoformat(),
                "processing_time_ms": response.processing_time_ms,
            }

            cache_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.debug(f"[VISION] Cached description: {cache_file.name}")
        except Exception as e:
            logger.warning(f"[VISION] Failed to cache description: {e}")

    def clear_cache(self):
        """Clear all cached descriptions."""
        if not self._cache_dir.exists():
            return

        count = 0
        for file in self._cache_dir.glob("*.json"):
            file.unlink()
            count += 1

        logger.info(f"[VISION] Cleared {count} cached descriptions")


# Convenience function for simple usage
def describe_image(
    image_bytes: bytes,
    image_format: str = "png",
    page_number: int = 0,
    context: str = "",
    api_key: str = "",
    model: str = "claude-sonnet-4-5-20250929",
) -> str:
    """Simple function to describe an image.

    Args:
        image_bytes: Image data as bytes
        image_format: Image format (png, jpeg, etc.)
        page_number: Page number where image is located
        context: Surrounding text for better description
        api_key: Anthropic API key (empty = use env)
        model: Claude model to use

    Returns:
        Image description text
    """
    describer = ImageDescriber(api_key=api_key, model=model)
    request = ImageDescriptionRequest(
        image_bytes=image_bytes,
        image_format=image_format,
        page_number=page_number,
        context=context,
    )
    response = describer.describe(request)

    if not response.success:
        return f"[Error: {response.error_message}]"

    return response.description
