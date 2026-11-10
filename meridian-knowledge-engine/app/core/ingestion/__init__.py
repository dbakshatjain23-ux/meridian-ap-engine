# app/core/ingestion/__init__.py
"""Ingestion Pipeline - 5-Tier Parser, Structure Repair, Extractor, Authority, Conflict, Graph Writer."""

# Lazy imports to avoid libmagic dependency at module load time
_DocumentParser = None
_BlockList = None
_Block = None
_StructureRepair = None
_EntityTopicExtractor = None
_AuthorityRanker = None
_ConflictDetector = None
_GraphWriter = None


def __getattr__(name: str):
    global _DocumentParser, _BlockList, _Block, _StructureRepair
    global _EntityTopicExtractor, _AuthorityRanker, _ConflictDetector, _GraphWriter

    if name in ("DocumentParser", "BlockList", "Block"):
        if _DocumentParser is None:
            from app.core.ingestion.parser import DocumentParser, BlockList, Block
            _DocumentParser = DocumentParser
            _BlockList = BlockList
            _Block = Block
        return {"DocumentParser": _DocumentParser, "BlockList": _BlockList, "Block": _Block}[name]

    if name == "StructureRepair":
        if _StructureRepair is None:
            from app.core.ingestion.structure_repair import StructureRepair
            _StructureRepair = StructureRepair
        return _StructureRepair

    if name == "EntityTopicExtractor":
        if _EntityTopicExtractor is None:
            from app.core.ingestion.extractor import EntityTopicExtractor
            _EntityTopicExtractor = EntityTopicExtractor
        return _EntityTopicExtractor

    if name == "AuthorityRanker":
        if _AuthorityRanker is None:
            from app.core.ingestion.authority import AuthorityRanker
            _AuthorityRanker = AuthorityRanker
        return _AuthorityRanker

    if name == "ConflictDetector":
        if _ConflictDetector is None:
            from app.core.ingestion.conflict import ConflictDetector
            _ConflictDetector = ConflictDetector
        return _ConflictDetector

    if name == "GraphWriter":
        if _GraphWriter is None:
            from app.core.ingestion.graph_writer import GraphWriter
            _GraphWriter = GraphWriter
        return _GraphWriter

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "DocumentParser",
    "BlockList",
    "Block",
    "StructureRepair",
    "EntityTopicExtractor",
    "AuthorityRanker",
    "ConflictDetector",
    "GraphWriter",
]