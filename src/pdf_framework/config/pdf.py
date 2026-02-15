"""PDF processing and loader configuration."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class PDFSettings(BaseSettings):
    """PDF processing configuration."""

    loader: Literal["pymupdf", "pdfplumber", "unstructured", "docling", "pymupdf4llm", "smart", "hybrid"] = "pymupdf"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    splitter: Literal["recursive", "semantic", "by_heading", "by_page", "parent_child", "structure_aware"] = "recursive"
    extract_tables: bool = True
    extract_images: bool = True

    # Phase 2.2: Semantic chunking
    semantic_threshold: float = 0.75
    min_chunk_size: int = 200
    max_chunk_size: int = 1500


class DoclingSettings(BaseSettings):
    """Phase 15.1: Docling PDF parsing configuration.

    IBM Docling for advanced document understanding:
    - Layout detection (DocLayNet model)
    - Table structure recognition (TableFormer, 97.9% accuracy)
    - OCR for scanned documents (EasyOCR/Tesseract)
    """

    model_config = SettingsConfigDict(env_prefix="DOCLING__")

    # OCR
    ocr_enabled: bool = True
    ocr_engine: Literal["easyocr", "tesseract", "rapidocr"] = "rapidocr"
    ocr_languages: list[str] = ["ru", "en"]
    force_full_page_ocr: bool = False

    # Tables
    table_structure_enabled: bool = True
    table_mode: Literal["fast", "accurate"] = "accurate"

    # Images
    extract_images: bool = True
    generate_picture_images: bool = True

    # Performance
    document_timeout: float = 1800.0  # seconds (30 min -- large PDFs need more time)
    layout_batch_size: int = 16
    ocr_batch_size: int = 16
    table_batch_size: int = 4

    # ONNX (lightweight alternative to PyTorch)
    use_onnx: bool = False


class SmartRouterSettings(BaseSettings):
    """Phase 15.1: Smart Loader Router configuration.

    Auto-selects best loader based on PDF characteristics:
    - Native simple PDF -> PyMuPDF4LLM (fast, <0.1 sec/page)
    - Native complex PDF -> Docling (full pipeline)
    - Scanned PDF -> Docling with OCR
    """

    model_config = SettingsConfigDict(env_prefix="SMART_ROUTER__")

    # Thresholds for PDF classification
    min_text_chars_per_page: int = 100  # Less = scanned PDF
    complex_layout_threshold: float = 0.3  # Ratio of pages with >1 column
    table_heavy_threshold: float = 0.3  # Ratio of pages with tables

    # Loader selection
    fast_loader: Literal["pymupdf", "pymupdf4llm"] = "pymupdf4llm"
    full_loader: Literal["docling", "unstructured"] = "docling"


class HybridLoaderSettings(BaseSettings):
    """Phase 28: Resilient Hybrid Loader configuration.

    4-level cascade for 100% page coverage:
    - Level 1: PyMuPDF4LLM text extraction (page_chunks=True)
    - Level 2: PyMuPDF find_tables() for fast table extraction
    - Level 3: Docling TableFormer for complex tables
    - Level 4: Claude Vision OCR for scanned pages
    """

    model_config = SettingsConfigDict(env_prefix="HYBRID_LOADER__")

    enable_fitz_tables: bool = True
    enable_docling_tables: bool = True
    enable_vision_ocr: bool = True  # Level 4: auto-OCR scanned pages via Vision
    verify_coverage: bool = True
    coverage_threshold: float = 0.95
    table_dedup_enabled: bool = True
    table_dedup_threshold: float = 0.6
    docling_max_retries: int = 2
    docling_table_mode: Literal["fast", "accurate"] = "accurate"

    # Level 4: Vision OCR settings
    vision_model: str = "claude-sonnet-4-5-20250929"
    vision_max_retries: int = 2
    vision_dpi: int = 200  # Render resolution for scanned pages
    vision_min_text_chars: int = 50  # Pages with less text -> treated as scanned
