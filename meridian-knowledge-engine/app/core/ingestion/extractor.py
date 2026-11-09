# app/core/ingestion/extractor.py
"""Entity/Topic/Fact Extraction - Learns company schema automatically."""
from typing import List, Dict, Any, Optional
from uuid import UUID
from dataclasses import dataclass

from app.core.ingestion.parser import Block
from app.gateways.llm import llm_gateway


@dataclass
class ExtractionResult:
    entities: List[Dict[str, Any]]
    predicates: List[Dict[str, Any]]
    facts: List[Dict[str, Any]]


class EntityTopicExtractor:
    """Learns company's ontology automatically (owner reviews once)."""

    def __init__(self):
        self.schema_cache: Dict[str, Dict] = {}

    async def extract_entities(
        self,
        blocks: List[Block],
        episode_id: UUID,
        tenant_id: str,
        document_context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Step 1: Entity Extraction."""
        # Prepare block content
        content = "\n\n".join(b.content for b in blocks[:50])  # Limit for token budget

        prompt = f"""Extract all entities from this document.
Document context: {document_context}

Content:
{content}

Return JSON array of entities:
[
  {{"entity_type": "client|vendor|policy|invoice|regulation|person",
    "name": "Exact name from text",
    "canonical_name": "normalized_lowercase_no_spaces",
    "metadata": {{}}}}
]"""

        try:
            response = await llm_gateway.complete_json(
                task_type="schema_learning",
                prompt=prompt,
                system="You are an entity extraction expert. Output only valid JSON array.",
            )
            return response if isinstance(response, list) else []
        except Exception:
            return []

    async def extract_predicates(
        self,
        entities: List[Dict[str, Any]],
        blocks: List[Block],
    ) -> List[Dict[str, Any]]:
        """Step 2: Topic/Predicate Discovery."""
        entity_list = ", ".join(f"{e['canonical_name']} ({e['entity_type']})" for e in entities)
        content = "\n\n".join(b.content for b in blocks[:30])

        prompt = f"""Given these entities: {entity_list}

Discover the predicates (attributes, relationships) for each entity from the document content.

Content:
{content}

Return JSON array:
[
  {{"subject_entity": "canonical_name",
    "predicate": "attribute_name",
    "expected_object_type": "json|string|number|date|boolean",
    "example_values": ["example1", "example2"]}}
]"""

        try:
            response = await llm_gateway.complete_json(
                task_type="schema_learning",
                prompt=prompt,
                system="You are a knowledge graph schema designer. Output only valid JSON array.",
            )
            return response if isinstance(response, list) else []
        except Exception:
            return []

    async def extract_facts(
        self,
        entities: List[Dict[str, Any]],
        predicates: List[Dict[str, Any]],
        blocks: List[Block],
        document_context: Dict[str, Any],
        valid_from: str,
        valid_to: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Step 3: Fact Extraction with Dual Clocks."""
        entity_list = ", ".join(f"{e['canonical_name']} ({e['entity_type']})" for e in entities)
        predicate_list = ", ".join(f"{p['subject_entity']}.{p['predicate']} ({p['expected_object_type']})" for p in predicates)
        content = "\n\n".join(b.content for b in blocks[:30])

        prompt = f"""Extract facts from this document.
Entities: {entity_list}
Predicates to populate: {predicate_list}
Document context: {document_context}
Valid from: {valid_from}
Valid to: {valid_to or 'present'}

Content:
{content}

Return JSON array of facts:
[
  {{"subject_entity": "canonical_name",
    "predicate": "predicate_name",
    "object_value": {{}} or "string" or 123,
    "object_type": "json|string|number|date|boolean",
    "source_block_indices": [0, 1, 2],
    "confidence": 0.95}}
]"""

        try:
            response = await llm_gateway.complete_json(
                task_type="schema_learning",
                prompt=prompt,
                system="You are a fact extraction expert. Output only valid JSON array.",
            )
            return response if isinstance(response, list) else []
        except Exception:
            return []

    async def run_full_extraction(
        self,
        blocks: List[Block],
        episode_id: UUID,
        tenant_id: str,
        document_context: Dict[str, Any],
        valid_from: str,
        valid_to: Optional[str],
    ) -> ExtractionResult:
        """Run complete extraction pipeline."""
        entities = await self.extract_entities(blocks, episode_id, tenant_id, document_context)
        predicates = await self.extract_predicates(entities, blocks)
        facts = await self.extract_facts(entities, predicates, blocks, document_context, valid_from, valid_to)

        return ExtractionResult(
            entities=entities,
            predicates=predicates,
            facts=facts,
        )