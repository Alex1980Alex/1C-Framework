"""Image extraction and description using Claude Vision (Phase 10/15).

Extracts images from PDF and generates text descriptions via Claude Vision API.
Descriptions are indexed as searchable text chunks.

Author: Claude Code
Version: 2.0.0 - Phase 15: Full integration with indexing pipeline
"""

import asyncio
import base64
import hashlib
import logging
from pathlib import Path

from anthropic import Anthropic
from pydantic import BaseModel, Field

from src.pdf_framework.schemas.documents import DocumentChunk

logger = logging.getLogger(__name__)


class ImageDescription(BaseModel):
    """Image with text description from Claude Vision."""

    image_bytes: bytes = Field(description="Raw image data")
    description: str = Field(description="Text description from Claude Vision")
    page_number: int = Field(description="Page number where image was found")
    bbox: tuple[float, float, float, float] | None = Field(
        default=None,
        description="Bounding box on page"
    )
    image_format: str = Field(description="Image format (png, jpeg, etc.)")
    size: tuple[int, int] = Field(description="Image size (width, height) in pixels")
    description_model: str = Field(description="Claude model used for description")

    def to_markdown_chunk(self) -> str:
        """Convert to markdown chunk for embedding."""
        return f"[Изображение на странице {self.page_number}]\n{self.description}"

    def to_dict(self) -> dict:
        """Convert to dictionary (excluding binary data)."""
        return {
            "description": self.description,
            "page_number": self.page_number,
            "bbox": self.bbox,
            "image_format": self.image_format,
            "size": self.size,
            "description_model": self.description_model,
        }


class ImageExtractor:
    """
    Extracts images from PDF and generates descriptions using Claude Vision.

    Features:
    - Image extraction via PyMuPDF
    - Size filtering (skip decorative icons)
    - Claude Vision description generation (non-blocking)
    - Description caching
    - Conversion to DocumentChunk for indexing
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "claude-sonnet-4-5-20250929",
        min_size: int = 100,  # pixels — skip small icons
        max_size: int = 4096,  # pixels (limit for Vision API)
        cache_enabled: bool = True,
        base_url: str = "",  # Z.AI or other proxy endpoint
    ):
        self._api_key = api_key
        self._model = model
        self._min_size = min_size
        self._max_size = max_size
        self._cache_enabled = cache_enabled

        if api_key:
            kwargs = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self._client = Anthropic(**kwargs)
        else:
            self._client = None
        self._description_cache: dict[str, str] = {}

        self._pymupdf_available = self._check_pymupdf()

        if not self._pymupdf_available:
            logger.warning("[IMAGE] PyMuPDF not available — image extraction disabled")

    @staticmethod
    def _check_pymupdf() -> bool:
        try:
            import fitz  # PyMuPDF
            return True
        except ImportError:
            return False

    def has_vision_support(self) -> bool:
        return bool(self._api_key) and self._client is not None

    async def extract_all(
        self,
        pdf_path: str | Path,
    ) -> list[ImageDescription]:
        """Extract and describe all images from PDF."""
        if not self._pymupdf_available:
            return []

        import time

        import fitz  # PyMuPDF

        t0 = time.time()
        descriptions = []
        skipped_small = 0

        with fitz.open(str(pdf_path)) as doc:
            total_pages = len(doc)
            logger.info(
                "[IMAGE] Начало извлечения изображений из '%s' (%d страниц, модель=%s)",
                Path(pdf_path).name, total_pages, self._model,
            )

            for page_num, page in enumerate(doc, start=1):
                raw_images = page.get_images()
                page_images = await self._extract_from_page(page, page_num)
                skipped_small += len(raw_images) - len(page_images)
                descriptions.extend(page_images)

                # Log progress: every page with images
                if page_images:
                    elapsed = time.time() - t0
                    logger.info(
                        "[IMAGE] Стр. %d/%d: %d изображений описано "
                        "(всего %d, пропущено мелких %d, %.1f сек)",
                        page_num, total_pages, len(page_images),
                        len(descriptions), skipped_small, elapsed,
                    )

        elapsed = time.time() - t0
        logger.info(
            "[IMAGE] Готово: %d изображений из '%s' за %.1f сек "
            "(пропущено мелких: %d, %.1f изобр/сек)",
            len(descriptions), Path(pdf_path).name, elapsed,
            skipped_small,
            len(descriptions) / elapsed if elapsed > 0 else 0,
        )

        return descriptions

    async def _extract_from_page(
        self,
        page,
        page_number: int,
    ) -> list[ImageDescription]:
        """Extract images from a single PyMuPDF page."""
        import io
        from PIL import Image

        descriptions = []
        image_list = page.get_images()

        for img_index, img in enumerate(image_list):
            try:
                xref = img[0]
                base_image = page.parent.extract_image(xref)

                if not base_image:
                    continue

                image_bytes = base_image["image"]
                image_format = base_image.get("ext", "png")

                pil_image = Image.open(io.BytesIO(image_bytes))
                width, height = pil_image.size

                # Filter small images (icons, decorative elements)
                if width < self._min_size or height < self._min_size:
                    continue

                # Resize if too large for Vision API
                if width > self._max_size or height > self._max_size:
                    pil_image.thumbnail((self._max_size, self._max_size))
                    output = io.BytesIO()
                    save_format = "PNG" if image_format.lower() == "png" else "JPEG"
                    pil_image.save(output, format=save_format)
                    image_bytes = output.getvalue()
                    width, height = pil_image.size

                # Generate description via Claude Vision (non-blocking)
                logger.debug(
                    "[IMAGE] Описание изображения %d на стр. %d (%dx%d, %s, %d KB)...",
                    img_index + 1, page_number, width, height,
                    image_format, len(image_bytes) // 1024,
                )
                description = await self.describe_image(image_bytes)

                descriptions.append(ImageDescription(
                    image_bytes=image_bytes,
                    description=description,
                    page_number=page_number,
                    bbox=None,
                    image_format=image_format,
                    size=(width, height),
                    description_model=self._model,
                ))

            except Exception as e:
                logger.warning(f"[IMAGE] Error extracting image {img_index} on page {page_number}: {e}")

        return descriptions

    # Patterns indicating a model refusal or hallucination
    _REFUSAL_PATTERNS = [
        "не могу просмотреть",
        "не могу обработать",
        "cannot transcribe",
        "cannot read",
        "I cannot",
        "I am unable",
        "не удалась",
        "нет доступа к внешним",
        "нет возможности анализировать",
    ]

    @staticmethod
    def _is_garbage(text: str) -> bool:
        """Detect hallucinated/garbage output (non-Cyrillic noise)."""
        if len(text) < 50:
            return True
        # Count non-ASCII, non-Cyrillic characters (CJK, random symbols)
        exotic = sum(1 for ch in text[:500] if ord(ch) > 0x3000)
        if exotic > 10:
            return True
        # Mostly English in a Russian-language task — suspicious
        latin_chars = sum(1 for ch in text[:500] if 'a' <= ch.lower() <= 'z')
        cyrillic_chars = sum(1 for ch in text[:500] if '\u0400' <= ch <= '\u04ff')
        if latin_chars > cyrillic_chars * 3 and len(text) > 200:
            return True
        return False

    def _is_refusal(self, text: str) -> bool:
        """Check if model refused to process the image."""
        lower = text.lower()
        return any(p in lower for p in self._REFUSAL_PATTERNS)

    async def describe_image(self, image_bytes: bytes, max_retries: int = 3) -> str:
        """Generate text description via Claude Vision with Ralph Wiggum-style retry.

        Uses self-correcting feedback loop: if a response fails validation,
        the rejection reason is passed to the next attempt so the model can
        correct itself (instead of blind retry).
        """
        if not self.has_vision_support():
            return "[Описание изображения недоступно — нет API ключа]"

        # Check cache
        cache_key = hashlib.md5(image_bytes).hexdigest()
        if self._cache_enabled and cache_key in self._description_cache:
            return self._description_cache[cache_key]

        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        media_type = self._guess_media_type(image_bytes)

        last_description = ""
        feedback = ""  # Ralph Wiggum: pass rejection reason to next attempt

        for attempt in range(1, max_retries + 1):
            try:
                description = await asyncio.to_thread(
                    self._call_vision_api, image_base64, media_type, feedback
                )
                last_description = description

                # Validate: refusal?
                if self._is_refusal(description):
                    feedback = (
                        "Твой предыдущий ответ был отклонён: ты отказался анализировать "
                        "изображение. Изображение реальное и содержит данные. "
                        "Попробуй ещё раз — опиши ВСЁ, что видишь."
                    )
                    logger.warning(
                        f"[IMAGE] Attempt {attempt}/{max_retries}: refusal → retry with feedback"
                    )
                    continue

                # Validate: garbage/hallucination?
                if self._is_garbage(description):
                    feedback = (
                        "Твой предыдущий ответ был отклонён: он содержал мусорный текст, "
                        "символы других языков или бессмысленный контент. "
                        "Отвечай ТОЛЬКО на русском языке. Опиши изображение по существу."
                    )
                    logger.warning(
                        f"[IMAGE] Attempt {attempt}/{max_retries}: garbage → retry with feedback"
                    )
                    continue

                # Valid description — convergence reached
                if self._cache_enabled:
                    self._description_cache[cache_key] = description
                return description

            except Exception as e:
                logger.error(f"[IMAGE] Vision API error (attempt {attempt}): {e}")
                feedback = f"Предыдущий вызов API завершился ошибкой: {e}. Попробуй ещё раз."
                last_description = f"[Ошибка описания изображения: {e}]"

        # All retries exhausted — return best available or error
        logger.warning(
            f"[IMAGE] All {max_retries} attempts failed (Ralph Wiggum loop exhausted)"
        )
        if self._cache_enabled and last_description:
            self._description_cache[cache_key] = last_description
        return last_description or "[Ошибка описания изображения]"

    # System prompt forces structured output format (stronger than user instructions)
    _SYSTEM_PROMPT = (
        "Ты — OCR-транскриптор для технической документации 1С:Предприятие. "
        "Твоя задача — извлечь ВЕСЬ текст и данные с изображения в структурированном виде.\n\n"
        "ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА ФОРМАТИРОВАНИЯ:\n"
        "- Таблицы ВСЕГДА оформляй как markdown-таблицы с разделителями | и ---\n"
        "- Каждую строку таблицы — на отдельной строке\n"
        "- НЕ описывай таблицу словами «в таблице видны колонки...» — ТРАНСКРИБИРУЙ её\n"
        "- Текст на изображении — копируй дословно, не пересказывай\n"
        "- Отвечай ТОЛЬКО на русском языке"
    )

    # Few-shot example of expected markdown table format
    _TABLE_EXAMPLE = (
        "Пример правильного формата таблицы:\n"
        "| Имя реквизита | Тип | Проверка заполнения |\n"
        "| --- | --- | --- |\n"
        "| Контрагент | СправочникСсылка.Контрагенты | Выдавать ошибку |\n"
        "| Склад | СправочникСсылка.Склады | Не проверять |\n\n"
    )

    def _call_vision_api(
        self, image_base64: str, media_type: str, feedback: str = ""
    ) -> str:
        """Synchronous Vision API call (runs in thread).

        Args:
            feedback: Ralph Wiggum correction — reason why previous attempt
                      was rejected. Appended to prompt so model can self-correct.
        """
        prompt_text = (
            "Подробно опиши это изображение из технической документации 1С:Предприятие.\n\n"
            "Правила:\n"
            "1. ВЕСЬ текст на изображении — транскрибируй дословно (названия полей, кнопок, "
            "заголовков, значения параметров, подписи, метки).\n"
            "2. Таблицы — ОБЯЗАТЕЛЬНО воспроизведи как markdown-таблицу с | и ---. "
            "НЕ описывай таблицу словами — транскрибируй все строки и столбцы.\n"
            f"{self._TABLE_EXAMPLE}"
            "3. Диаграммы/схемы — опиши все элементы, связи, направления стрелок.\n"
            "4. Скриншоты интерфейса — опиши иерархию меню, названия вкладок, "
            "состояние чекбоксов/переключателей, выбранные значения.\n"
            "5. Настройки/свойства — перечисли ВСЕ видимые параметры с их значениями.\n\n"
            "Будь максимально подробным — не сокращай информацию."
        )

        # Ralph Wiggum: append correction feedback from previous failed attempt
        if feedback:
            prompt_text += f"\n\n⚠️ КОРРЕКЦИЯ: {feedback}"

        message = {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_base64,
                    },
                },
                {
                    "type": "text",
                    "text": prompt_text,
                },
            ],
        }

        response = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=self._SYSTEM_PROMPT,
            messages=[message],
        )

        # Handle response.content being list[ContentBlock]
        content = response.content[0]
        return getattr(content, "text", str(content)).strip()

    def _guess_media_type(self, image_bytes: bytes) -> str:
        if image_bytes.startswith(b"\x89PNG"):
            return "image/png"
        elif image_bytes.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        elif image_bytes.startswith(b"GIF87a") or image_bytes.startswith(b"GIF89a"):
            return "image/gif"
        elif image_bytes.startswith(b"WEBP", 0, 4):
            return "image/webp"
        return "image/png"

    def to_document_chunks(
        self,
        descriptions: list[ImageDescription],
        document_id: str,
        source_path: str = "",
    ) -> list[DocumentChunk]:
        """Convert image descriptions to DocumentChunk objects for indexing.

        Each image description becomes a searchable text chunk with
        metadata marking it as an image chunk.
        """
        chunks = []

        for idx, img_desc in enumerate(descriptions):
            chunk_id = f"{document_id}_img_{img_desc.page_number}_{idx}"
            chunks.append(DocumentChunk(
                id=chunk_id,
                content=img_desc.to_markdown_chunk(),
                document_id=document_id,
                page_number=img_desc.page_number,
                section="",  # Phase 29: empty → will be inherited from nearest text chunk
                chunk_index=9000 + idx,  # High index so images sort after text
                metadata={
                    "chunk_type": "image",
                    "element_type": "image",
                    "source": source_path,
                    "document_id": document_id,
                    "image_format": img_desc.image_format,
                    "image_size": f"{img_desc.size[0]}x{img_desc.size[1]}",
                    "description_model": img_desc.description_model,
                    "page_number": str(img_desc.page_number),
                },
            ))

        return chunks

    def clear_cache(self) -> None:
        self._description_cache.clear()
