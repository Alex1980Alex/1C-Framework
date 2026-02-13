"""Page coverage verification for PDF loaders.

Phase 28: Validates that all pages in a PDF have been extracted,
diagnoses gaps, and suggests fixes.
"""

import logging
from pathlib import Path

import fitz

logger = logging.getLogger(__name__)


class PageCoverageVerifier:
    """Verify that all PDF pages are covered by extracted text."""

    @staticmethod
    def verify(
        page_offsets: list[tuple[int, int]],
        total_pages: int,
    ) -> dict:
        """Check all pages 1..N are present in page_offsets.

        Args:
            page_offsets: List of (char_offset, page_number) from loader.
            total_pages: Total number of pages in PDF.

        Returns:
            Coverage report dict.
        """
        if total_pages <= 0:
            return {
                "complete": True,
                "total_pages": 0,
                "covered_pages": 0,
                "missing_pages": [],
                "coverage_ratio": 1.0,
            }

        covered = {p for _, p in page_offsets}
        expected = set(range(1, total_pages + 1))
        missing = sorted(expected - covered)

        report = {
            "complete": len(missing) == 0,
            "total_pages": total_pages,
            "covered_pages": len(covered),
            "missing_pages": missing,
            "coverage_ratio": len(covered) / total_pages,
        }

        if missing:
            logger.warning(
                "[COVERAGE] Missing %d/%d pages: %s",
                len(missing), total_pages,
                missing[:20] if len(missing) > 20 else missing,
            )
        else:
            logger.info("[COVERAGE] All %d pages covered", total_pages)

        return report

    @staticmethod
    def diagnose_gaps(
        missing_pages: list[int],
        pdf_path: Path,
    ) -> list[dict]:
        """Diagnose why specific pages are missing.

        Checks each missing page for: blank, scanned (image-only),
        or has extractable text that was missed.
        """
        if not missing_pages:
            return []

        diagnostics: list[dict] = []
        doc = fitz.open(str(pdf_path))

        try:
            for page_num in missing_pages:
                if page_num < 1 or page_num > len(doc):
                    diagnostics.append({
                        "page": page_num,
                        "type": "out_of_range",
                        "text_chars": 0,
                        "image_count": 0,
                    })
                    continue

                page = doc[page_num - 1]
                text = str(page.get_text()).strip()
                images = page.get_images()

                if not text and not images:
                    page_type = "blank"
                elif not text and images:
                    page_type = "scanned"
                elif len(text) < 50:
                    page_type = "near_blank"
                else:
                    page_type = "has_text"

                diagnostics.append({
                    "page": page_num,
                    "type": page_type,
                    "text_chars": len(text),
                    "image_count": len(images),
                })
        finally:
            doc.close()

        # Log summary
        type_counts: dict[str, int] = {}
        for d in diagnostics:
            type_counts[d["type"]] = type_counts.get(d["type"], 0) + 1
        logger.info("[COVERAGE] Gap diagnostics: %s", type_counts)

        return diagnostics
