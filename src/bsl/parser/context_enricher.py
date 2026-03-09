"""
BSL Context Enricher — Phase 63

Adds module context (object type, subsystem, dependencies) to BSLChunks.
Applied after chunking, before embedding. Based on Anthropic's Contextual Retrieval.

Context prefix improves retrieval by 15-20% by situating each chunk
within its 1C Enterprise project structure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.bsl.call_graph.store import CallGraphStore
    from src.bsl.knowledge_graph.metadata_extractor import MetadataExtractor

from .bsl_chunker import BSLChunk


class BSLContextEnricher:
    """Enrich BSL chunks with project context for better retrieval."""

    def __init__(
        self,
        metadata_extractor: MetadataExtractor | None = None,
        call_graph: CallGraphStore | None = None,
    ) -> None:
        self._extractor = metadata_extractor
        self._call_graph = call_graph
        self._object_cache: dict[str, tuple[str, str]] = {}

    def enrich(self, chunks: list[BSLChunk]) -> list[BSLChunk]:
        """Enrich chunks with contextual prefix and metadata."""
        for chunk in chunks:
            self._enrich_chunk(chunk)
        return chunks

    def _enrich_chunk(self, chunk: BSLChunk) -> None:
        """Add context prefix to chunk content and enrich metadata."""
        module_path = chunk.metadata.get("module_path", "")
        if not module_path:
            return

        context_lines: list[str] = []
        obj_type, obj_name = self._resolve_object(module_path)

        if obj_type and obj_name:
            chunk.metadata["object_type"] = obj_type
            chunk.metadata["object_name"] = obj_name
            context_lines.append(f"// Object: {obj_type}.{obj_name}")

            if self._extractor:
                obj_info = self._extractor.get_object_by_name(obj_name)
                if obj_info and obj_info.has_forms:
                    chunk.metadata["forms"] = obj_info.form_names
                    context_lines.append(
                        f"// Forms: {', '.join(obj_info.form_names[:5])}"
                    )

        if (
            self._call_graph
            and chunk.metadata.get("chunk_type") == "symbol"
        ):
            symbol_name = chunk.metadata.get("name", "")
            if symbol_name:
                self._add_call_context(chunk, symbol_name, module_path, context_lines)

        if context_lines:
            prefix = "\n".join(context_lines)
            chunk.content = f"{prefix}\n{chunk.content}"

    def _resolve_object(self, module_path: str) -> tuple[str, str]:
        """Extract object_type and object_name from module path."""
        if module_path in self._object_cache:
            return self._object_cache[module_path]

        result = ("", "")

        if self._extractor:
            norm = module_path.replace("\\", "/")
            for obj in self._extractor.extract_objects():
                if obj.path and norm.find(obj.path.replace("\\", "/")) != -1:
                    result = (obj.object_type, obj.name)
                    break

        if result == ("", ""):
            result = self._parse_path(module_path)

        self._object_cache[module_path] = result
        return result

    @staticmethod
    def _parse_path(file_path: str) -> tuple[str, str]:
        """Extract object type and name from file path conventions."""
        parts = file_path.replace("\\", "/").split("/")
        type_map = {
            "catalogs": "Catalog",
            "documents": "Document",
            "informationregisters": "InformationRegister",
            "accumulationregisters": "AccumulationRegister",
            "dataprocessors": "DataProcessor",
            "commonmodules": "CommonModule",
            "reports": "Report",
            "enums": "Enum",
            "constants": "Constant",
            "commonforms": "CommonForm",
            "exchangeplans": "ExchangePlan",
            "справочники": "Catalog",
            "документы": "Document",
            "регистрысведений": "InformationRegister",
            "регистрынакопления": "AccumulationRegister",
            "обработки": "DataProcessor",
            "общиемодули": "CommonModule",
            "отчеты": "Report",
            "перечисления": "Enum",
            "константы": "Constant",
            "общиеформы": "CommonForm",
            "планыобмена": "ExchangePlan",
        }
        for i, part in enumerate(parts):
            key = part.lower()
            if key in type_map and i + 1 < len(parts):
                return type_map[key], parts[i + 1]
        return "", ""

    def _add_call_context(
        self,
        chunk: BSLChunk,
        symbol_name: str,
        module_path: str,
        context_lines: list[str],
    ) -> None:
        """Add caller/callee summary to context."""
        store = self._call_graph
        if store is None:
            return

        callers = store.callers_of(symbol_name)
        if callers:
            caller_names = list({c["name"] for c in callers[:5]})
            chunk.metadata["caller_count"] = len(callers)
            suffix = f" (+{len(callers) - len(caller_names)} more)" if len(callers) > 5 else ""
            context_lines.append(f"// Called by: {', '.join(caller_names)}{suffix}")

        sid = f"{module_path}::{symbol_name}"
        callees = store.callees_of(sid)
        cross_module = [c for c in callees if c.get("callee_module")]
        if cross_module:
            dep_names = list({c["callee_module"] for c in cross_module[:5]})
            chunk.metadata["cross_module_deps"] = dep_names
            context_lines.append(f"// Dependencies: {', '.join(dep_names)}")
