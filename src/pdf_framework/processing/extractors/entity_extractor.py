"""LLM-based entity and relation extractor.

Uses an LLM to extract structured entities and relations from text chunks.
"""

import json
import logging
import re
import uuid

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from src.pdf_framework.config import AgentSettings
from src.pdf_framework.schemas.documents import DocumentChunk
from src.pdf_framework.schemas.entities import Entity, ExtractionResult, Relation
from src.shared.llm_rotation.adapter import cheap_llm_call, is_cheap_llm_enabled

logger = logging.getLogger(__name__)


def _repair_truncated_json(text: str) -> dict | None:
    """Try to repair truncated JSON from LLM output.

    When max_tokens is hit, the JSON gets cut mid-object.
    Strategy: find the last complete object in entities/relations arrays,
    then close all open brackets.
    """
    # Find the last complete object boundary: "}," or "}\n" before truncation
    # Remove everything after the last complete object
    last_complete = -1
    for m in re.finditer(r'\}\s*,', text):
        last_complete = m.end()

    if last_complete == -1:
        return None

    # Take text up to last complete object, close arrays and root object
    truncated = text[:last_complete - 1]  # remove trailing comma

    # Count open brackets to figure out what to close
    open_brackets = truncated.count('[') - truncated.count(']')
    open_braces = truncated.count('{') - truncated.count('}')

    truncated += ']' * open_brackets + '}' * open_braces

    try:
        return json.loads(truncated)
    except json.JSONDecodeError:
        return None


_EXTRACTION_PROMPT = """Extract named entities and relations from the text below.

Return a JSON object with:
- "entities": list of objects with fields: "name", "entity_type" (one of: PERSON, ORG, LOCATION, DATE, CONCEPT, DOCUMENT), "properties" (optional dict)
- "relations": list of objects with fields: "source" (entity name), "target" (entity name), "relation_type" (e.g. WORKS_AT, LOCATED_IN, MENTIONS, RELATED_TO, AUTHORED_BY, PART_OF)

Return ONLY valid JSON, no other text.

Text:
{text}"""


class LLMEntityExtractor:
    """Extract entities and relations from document chunks using an LLM."""

    def __init__(self, settings: AgentSettings | None = None, api_key: str = ""):
        self._settings = settings or AgentSettings()

        # Configure ChatAnthropic with optional base_url for proxies like Z.AI
        llm_kwargs = {
            "model": self._settings.model,
            "temperature": 0.0,
            "max_tokens": 4096,
            "api_key": api_key or None,
        }

        # Add base_url if configured (for Z.AI or other proxies)
        if self._settings.base_url:
            llm_kwargs["base_url"] = self._settings.base_url

        self._llm = ChatAnthropic(**llm_kwargs)

    async def extract(self, chunk: DocumentChunk) -> ExtractionResult:
        """Extract entities and relations from a single chunk (Ralph Wiggum)."""
        rw_feedback = ""
        for rw_attempt in range(1, 3):  # max 2 attempts
            try:
                return await self._extract_impl(chunk, rw_feedback)
            except json.JSONDecodeError as e:
                rw_feedback = (
                    f"Previous response was not valid JSON: {e}. "
                    "Return ONLY valid JSON with 'entities' and 'relations' arrays."
                )
                logger.warning(f"Entity extraction JSON error for chunk {chunk.id} (attempt {rw_attempt}): {e}")
            except Exception as e:
                logger.error("Entity extraction attempt %d failed for chunk %s: %s", rw_attempt, chunk.id, e)
                rw_feedback = f"Previous call failed: {e}."
        return ExtractionResult(chunk_id=chunk.id)

    async def _extract_impl(self, chunk: DocumentChunk, feedback: str = "") -> ExtractionResult:
        """Internal extraction logic."""
        # Cheap LLM path for entity extraction (skip if retrying with feedback)
        cheap_content: str | None = None
        if is_cheap_llm_enabled("entity_extractor") and not feedback:
            try:
                cheap_content = await cheap_llm_call(
                    prompt=_EXTRACTION_PROMPT.format(text=chunk.content),
                    system_prompt="You are an entity extraction system. Output only valid JSON.",
                    component="entity_extractor",
                )
            except Exception as e:
                logger.warning("[ENTITY] Cheap LLM failed for %s, falling back: %s", chunk.id[:12], e)

        if cheap_content and len(cheap_content.strip()) >= 10:
            content = cheap_content
        else:
            messages = [
                SystemMessage(content="You are an entity extraction system. Output only valid JSON."),
                HumanMessage(content=_EXTRACTION_PROMPT.format(text=chunk.content)),
            ]
            if feedback:
                messages.append(HumanMessage(content=f"\u26a0\ufe0f {feedback}"))

            response = await self._llm.ainvoke(messages)

            # Extract text content — handle both str and list[ContentBlock] formats
            if isinstance(response.content, str):
                content = response.content
            elif isinstance(response.content, list):
                parts: list[str] = []
                for block in response.content:
                    if isinstance(block, dict):
                        parts.append(block.get("text", ""))
                    elif hasattr(block, "text"):
                        parts.append(getattr(block, "text"))
                    else:
                        parts.append(str(block))
                content = "".join(parts)
            else:
                content = str(response.content)

        if not content.strip():
            logger.warning("Empty LLM response for chunk %s", chunk.id)
            return ExtractionResult(chunk_id=chunk.id)

        # Remove markdown code blocks if present (GLM models wrap JSON in ```json ... ```)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            # Try to repair truncated JSON (LLM hit max_tokens)
            data = _repair_truncated_json(content)
            if data:
                logger.info(
                    "Repaired truncated JSON for chunk %s (got %d entities)",
                    chunk.id, len(data.get("entities", [])),
                )
            else:
                logger.warning(
                    "Failed to parse entity extraction JSON for chunk %s: %s",
                    chunk.id, e,
                )
                return ExtractionResult(chunk_id=chunk.id)

        entities: list[Entity] = []
        entity_name_to_id: dict[str, str] = {}

        for raw_entity in data.get("entities", []):
            entity_id = uuid.uuid4().hex[:12]
            # Support both formats: "name" (Anthropic) and "text" (GLM)
            name = raw_entity.get("name") or raw_entity.get("text", "")
            if not name:
                continue
            entity_name_to_id[name] = entity_id
            # Support both formats: "entity_type" (Anthropic) and "type" (GLM)
            entity_type = raw_entity.get("entity_type") or raw_entity.get("type", "CONCEPT")
            entities.append(
                Entity(
                    id=entity_id,
                    name=name,
                    entity_type=entity_type,
                    properties=raw_entity.get("properties", {}),
                    source_document_id=chunk.document_id,
                    source_chunk_ids=[chunk.id],
                )
            )

        relations: list[Relation] = []
        for raw_rel in data.get("relations", []):
            # Support both formats for source/target entity names
            source_name = raw_rel.get("source") or raw_rel.get("from") or raw_rel.get("source_entity", "")
            target_name = raw_rel.get("target") or raw_rel.get("to") or raw_rel.get("target_entity", "")
            source_id = entity_name_to_id.get(source_name)
            target_id = entity_name_to_id.get(target_name)
            if source_id and target_id:
                # Support both formats: "relation_type" and "type"
                relation_type = raw_rel.get("relation_type") or raw_rel.get("type", "RELATED_TO")
                relations.append(
                    Relation(
                        id=uuid.uuid4().hex[:12],
                        source_entity_id=source_id,
                        target_entity_id=target_id,
                        relation_type=relation_type,
                        source_chunk_id=chunk.id,
                    )
                )

        logger.debug(
            "Chunk %s: extracted %d entities, %d relations",
            chunk.id, len(entities), len(relations),
        )
        return ExtractionResult(
            chunk_id=chunk.id,
            entities=entities,
            relations=relations,
        )

    async def extract_batch(self, chunks: list[DocumentChunk]) -> list[ExtractionResult]:
        """Extract entities from multiple chunks."""
        results: list[ExtractionResult] = []
        for chunk in chunks:
            result = await self.extract(chunk)
            results.append(result)
        return results
