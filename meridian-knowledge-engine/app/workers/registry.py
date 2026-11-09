# app/workers/registry.py
"""Job Handler Registry."""
from app.workers.main import JobHandler, IngestHandler, ConflictScanHandler, SopSyncHandler


def get_all_handlers():
    """Get all registered job handlers."""
    return [
        IngestHandler(),
        ConflictScanHandler(),
        SopSyncHandler(),
    ]


def register_handlers(processor):
    """Register all handlers with processor."""
    for handler in get_all_handlers():
        processor.register_handler(handler)