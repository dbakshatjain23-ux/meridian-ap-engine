# app/core/ingestion/structure_repair.py
"""Structure Repair - AI assigns heading levels if flat."""
from typing import List, Optional
from app.core.ingestion.parser import Block
from app.gateways.llm import llm_gateway


class StructureRepair:
    """Fixes flat outlines using Haiku."""

    @staticmethod
    def needs_repair(blocks: List[Block]) -> bool:
        """Check if structure repair is needed."""
        has_headings = any(b.block_type == "heading" for b in blocks)
        has_levels = any(b.heading_level is not None for b in blocks)
        return not has_headings or not has_levels

    @staticmethod
    async def repair(blocks: List[Block]) -> List[Block]:
        """Send blocks to Haiku for heading level assignment."""
        if not StructureRepair.needs_repair(blocks):
            return blocks

        # Prepare input for LLM
        block_texts = []
        for i, b in enumerate(blocks):
            preview = b.content[:200] if len(b.content) > 200 else b.content
            block_texts.append(f"Block {i}: [{b.block_type}] {preview}")

        prompt = f"""Assign heading levels (1-3) and heading paths to these text blocks.
Preserve explicit numbering (4.2, 4.2.1). Infer hierarchy from font size, bold, position.
Return JSON: [{{"block_index": 0, "heading_level": 2, "heading_path": ["4", "2"]}}, ...]

Blocks:
{chr(10).join(block_texts)}"""

        try:
            response = await llm_gateway.complete_json(
                task_type="structure_repair",
                prompt=prompt,
                system="You are a document structure analyst. Output only valid JSON.",
            )

            # Apply repairs
            for repair in response:
                idx = repair.get("block_index")
                if 0 <= idx < len(blocks):
                    blocks[idx].heading_level = repair.get("heading_level")
                    blocks[idx].heading_path = repair.get("heading_path", [])
                    if repair.get("heading_level"):
                        blocks[idx].block_type = "heading"

        except Exception:
            # Fallback: heuristic based on font size, bold, numbering patterns
            StructureRepair._heuristic_repair(blocks)

        return blocks

    @staticmethod
    def _heuristic_repair(blocks: List[Block]) -> None:
        """Heuristic heading assignment when AI fails."""
        import re

        current_path = []
        for b in blocks:
            # Check for explicit numbering
            match = re.match(r"^(\d+(?:\.\d+)*)\s+", b.content)
            if match:
                nums = match.group(1).split(".")
                level = len(nums)
                b.heading_level = level
                b.heading_path = nums
                b.block_type = "heading"
                current_path = nums[:level]
            elif b.block_type == "heading" and b.heading_level:
                current_path = current_path[:b.heading_level - 1] + [str(len(current_path) + 1)]
                b.heading_path = current_path