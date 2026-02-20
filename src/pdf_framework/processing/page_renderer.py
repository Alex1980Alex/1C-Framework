"""PDF Page Renderer for Visual Retrieval (Phase 55).

Renders PDF pages as PIL Images for ColPali visual embeddings.
Supports multiple DPI settings and batch processing.

Author: Claude Code
Version: 1.0.0 - Phase 55: ColPali Visual Retrieval
"""

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
from PIL import Image

logger = logging.getLogger(__name__)


class RenderDPI(Enum):
    """Standard DPI presets for PDF rendering.

    Higher DPI = better quality but slower processing and larger images.
    """
    THUMBNAIL = 72   # Fast previews, ~600x800 px
    STANDARD = 150   # Standard quality, ~1200x1600 px
    HIGH = 200       # High quality, ~1600x2100 px
    ULTRA = 300      # Maximum quality, ~2400x3200 px


@dataclass
class RenderConfig:
    """Configuration for PDF page rendering.

    Attributes:
        dpi: Resolution (dots per inch) for rendering
        format: Output image format (png/jpeg)
        color_space: Color space (RGB/GRAYSCALE)
        anti_alias: Enable anti-aliasing
        rotate_for_orientation: Auto-rotate based on page orientation
        max_width: Maximum width (0 = no limit)
        max_height: Maximum height (0 = no limit)
    """
    dpi: int = 150
    format: str = "PNG"
    color_space: str = "RGB"
    anti_alias: int = 2
    rotate_for_orientation: bool = False
    max_width: int = 0
    max_height: int = 0

    @classmethod
    def from_preset(cls, preset: RenderDPI) -> "RenderConfig":
        """Create config from DPI preset.

        Args:
            preset: DPI preset enum

        Returns:
            RenderConfig instance
        """
        return cls(dpi=preset.value)

    def to_matrix(self) -> fitz.Matrix:
        """Convert DPI to PyMuPDF transformation matrix.

        Returns:
            fitz.Matrix for rendering
        """
        # DPI to zoom factor: 72 DPI = 1.0 zoom
        zoom = self.dpi / 72.0
        return fitz.Matrix(zoom, zoom)


class PageRenderer:
    """Renders PDF pages as PIL Images for visual indexing.

    Workflow:
        1. Open PDF document
        2. Render specified pages at configured DPI
        3. Optionally resize to max dimensions
        4. Return PIL Images

    Example:
        >>> renderer = PageRenderer(dpi=150)
        >>> images = renderer.render_pages("document.pdf", pages=[0, 1, 2])
        >>> for page_num, img in enumerate(images):
        ...     img.save(f"page_{page_num}.png")
    """

    def __init__(
        self,
        config: RenderConfig | None = None,
        dpi: int | None = None,
        format: str | None = None,
    ):
        """Initialize page renderer.

        Args:
            config: Full render configuration (overrides other params)
            dpi: DPI for rendering (if config not provided)
            format: Image format PNG/JPEG (if config not provided)
        """
        if config is None:
            config = RenderConfig(
                dpi=dpi or 150,
                format=format or "PNG",
            )

        self._config = config
        self._matrix = config.to_matrix()

        logger.debug(
            f"[PAGE_RENDERER] Initialized: {config.dpi} DPI, "
            f"{config.format}, {config.color_space}"
        )

    def render_page(
        self,
        doc: fitz.Document,
        page_number: int,
    ) -> Image.Image:
        """Render a single PDF page as PIL Image.

        Args:
            doc: PyMuPDF Document object
            page_number: Zero-based page index

        Returns:
            PIL Image of the rendered page

        Raises:
            IndexError: If page_number is out of range
        """
        if page_number < 0 or page_number >= len(doc):
            raise IndexError(
                f"Page {page_number} out of range (0-{len(doc) - 1})"
            )

        page = doc[page_number]

        # Render page to pixmap
        pix = page.get_pixmap(
            matrix=self._matrix,
            alpha=False,
            clip=None,
        )

        # Convert to PIL Image
        img = Image.frombytes(
            "RGB",
            [pix.width, pix.height],
            pix.samples,
        )

        # Apply color space conversion if needed
        if self._config.color_space == "GRAYSCALE":
            img = img.convert("L")

        # Resize if max dimensions set
        if self._config.max_width > 0 and img.width > self._config.max_width:
            ratio = self._config.max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((self._config.max_width, new_height), Image.Resampling.LANCZOS)

        if self._config.max_height > 0 and img.height > self._config.max_height:
            ratio = self._config.max_height / img.height
            new_width = int(img.width * ratio)
            img = img.resize((new_width, self._config.max_height), Image.Resampling.LANCZOS)

        return img

    def render_pages(
        self,
        pdf_path: str | Path,
        pages: list[int] | None = None,
        first_page: int | None = None,
        last_page: int | None = None,
    ) -> list[tuple[int, Image.Image]]:
        """Render multiple PDF pages as PIL Images.

        Args:
            pdf_path: Path to PDF file
            pages: Specific page numbers to render (0-indexed)
            first_page: First page to render (inclusive)
            last_page: Last page to render (inclusive)

        Returns:
            List of (page_number, PIL_Image) tuples

        Example:
            >>> renderer = PageRenderer(dpi=150)
            >>> images = renderer.render_pages("doc.pdf", pages=[0, 5, 10])
            >>> for page_num, img in images:
            ...     print(f"Page {page_num}: {img.size}")
        """
        pdf_path = Path(pdf_path)
        logger.info(f"[PAGE_RENDERER] Rendering from {pdf_path.name}")

        doc = fitz.open(str(pdf_path))
        total_pages = len(doc)

        # Determine which pages to render
        if pages is not None:
            pages_to_render = [p for p in pages if 0 <= p < total_pages]
        elif first_page is not None or last_page is not None:
            start = first_page or 0
            end = last_page if last_page is not None else total_pages - 1
            pages_to_render = list(range(start, min(end + 1, total_pages)))
        else:
            pages_to_render = list(range(total_pages))

        if not pages_to_render:
            logger.warning(f"[PAGE_RENDERER] No valid pages to render")
            return []

        logger.debug(
            f"[PAGE_RENDERER] Rendering {len(pages_to_render)} pages "
            f"({pages_to_render[0]}-{pages_to_render[-1]})"
        )

        results = []

        for page_num in pages_to_render:
            try:
                img = self.render_page(doc, page_num)
                results.append((page_num, img))
            except Exception as e:
                logger.error(
                    f"[PAGE_RENDERER] Failed to render page {page_num}: {e}"
                )

        doc.close()

        logger.info(
            f"[PAGE_RENDERER] Rendered {len(results)}/{len(pages_to_render)} pages"
        )

        return results

    def render_all_pages(
        self,
        pdf_path: str | Path,
    ) -> list[tuple[int, Image.Image]]:
        """Render all pages in a PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of (page_number, PIL_Image) tuples for all pages
        """
        return self.render_pages(pdf_path)

    def get_page_count(self, pdf_path: str | Path) -> int:
        """Get number of pages in PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Number of pages
        """
        doc = fitz.open(str(Path(pdf_path)))
        count = len(doc)
        doc.close()
        return count

    def save_pages(
        self,
        pdf_path: str | Path,
        output_dir: str | Path,
        prefix: str = "page",
        pages: list[int] | None = None,
    ) -> list[Path]:
        """Render and save pages as image files.

        Args:
            pdf_path: Path to PDF file
            output_dir: Directory for saved images
            prefix: Filename prefix
            pages: Specific pages to render (None = all)

        Returns:
            List of saved file paths
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        rendered = self.render_pages(pdf_path, pages=pages)
        saved_paths = []

        for page_num, img in rendered:
            ext = self._format.lower()
            filename = f"{prefix}_{page_num:04d}.{ext}"
            filepath = output_dir / filename

            img.save(filepath, format=self._format)
            saved_paths.append(filepath)

        logger.info(
            f"[PAGE_RENDERER] Saved {len(saved_paths)} pages to {output_dir}"
        )

        return saved_paths


def create_page_renderer(
    dpi: int = 150,
    config: RenderConfig | None = None,
) -> PageRenderer:
    """Factory function to create page renderer.

    Args:
        dpi: DPI for rendering (if config not provided)
        config: Full render configuration

    Returns:
        Configured PageRenderer instance
    """
    if config is None:
        config = RenderConfig(dpi=dpi)

    return PageRenderer(config=config)


# Convenience function for quick rendering
def render_pdf_to_images(
    pdf_path: str | Path,
    dpi: int = 150,
    pages: list[int] | None = None,
) -> list[tuple[int, Image.Image]]:
    """Quick function to render PDF pages to images.

    Args:
        pdf_path: Path to PDF file
        dpi: Resolution (150 = standard quality)
        pages: Specific pages to render (None = all)

    Returns:
        List of (page_number, PIL_Image) tuples

    Example:
        >>> images = render_pdf_to_images("doc.pdf", dpi=150, pages=[0, 1, 2])
        >>> for page_num, img in images:
        ...     img.save(f"page_{page_num}.png")
    """
    renderer = PageRenderer(dpi=dpi)
    return renderer.render_pages(pdf_path, pages=pages)
