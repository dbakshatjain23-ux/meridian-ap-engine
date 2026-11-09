# app/core/ingestion/authority.py
"""Source Authority Ranking Configuration."""
from typing import Dict
from app.config import get_settings

settings = get_settings()

# Default authority ranking (can be overridden per tenant)
DEFAULT_AUTHORITY_RANKING: Dict[str, int] = {
    # Rank 1: Highest Authority - Client-Specific Overrides
    "client_memo": 1,

    # Rank 2: Current General Rules
    "sop_v4": 2,
    "desk_instruction": 2,

    # Rank 3: Approved Tacit Knowledge
    "expert_interview": 3,
    "approved_practice": 3,

    # Rank 4: Superseded / Historical
    "sop_v3": 4,
    "faq_2023": 4,
    "training_video_old": 4,

    # Rank 5: Live Sources (Dynamic - Evaluated Per Source)
    "meeting": 5,
    "email": 5,
    "chat": 5,
}


class AuthorityRanker:
    """Computes authority rank for sources."""

    def __init__(self, tenant_ranking: Optional[Dict[str, int]] = None):
        self.ranking = tenant_ranking or DEFAULT_AUTHORITY_RANKING

    def get_rank(self, source_type: str, source_version: str = "", source_status: str = "") -> int:
        """Get authority rank for a source."""
        # Check specific source type
        if source_type in self.ranking:
            return self.ranking[source_type]

        # Fallback based on version/status
        if source_status == "superseded":
            return 4
        if source_status == "current" and source_version and "v4" in source_version:
            return 2
        if source_status == "current" and source_version and "v3" in source_version:
            return 4

        return 5  # Default low authority

    def compare(self, source1: Dict, source2: Dict) -> int:
        """Compare two sources. Returns -1 if source1 wins, 1 if source2 wins, 0 if tie."""
        rank1 = self.get_rank(source1.get("type", ""), source1.get("version", ""), source1.get("status", ""))
        rank2 = self.get_rank(source2.get("type", ""), source2.get("version", ""), source2.get("status", ""))

        if rank1 < rank2:
            return -1
        elif rank1 > rank2:
            return 1
        return 0