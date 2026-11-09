# app/core/ontology/authority.py
"""Meridian AP Authority Ranking Configuration."""
from typing import Dict

AUTHORITY_RANKING: Dict[str, int] = {
    # Rank 1: Highest Authority - Client-Specific Overrides
    "client_memo": 1,           # CM-INF-02, CM-PHA-01, CM-RET-03

    # Rank 2: Current General Rules
    "sop_v4": 2,                # SOP v4.0 (eff. 2026-04-01)
    "desk_instruction": 2,      # DI-03, DI-07 (eff. 2026-04-01)

    # Rank 3: Approved Tacit Knowledge
    "expert_interview": 3,      # Lakshmi, Imran interviews (approved, 6-month TTL)
    "approved_practice": 3,     # Captured habit cards (owner approved)

    # Rank 4: Superseded / Historical
    "sop_v3": 4,                # SOP v3.1 (expired 2026-03-31)
    "faq_2023": 4,              # Team FAQ (Oct 2023, known errors)
    "training_video_old": 4,    # Pre-2026 videos

    # Rank 5: Live Sources (Dynamic - Evaluated Per Source)
    "meeting": 5,               # Client meetings - authority by speaker role
    "email": 5,                 # Client emails - authority by sender role
    "chat": 5,                  # Teams messages - authority by sender role
}

# Dynamic authority for live sources based on speaker/sender role
LIVE_SOURCE_AUTHORITY_WEIGHTS: Dict[str, float] = {
    "client_vp": 0.95,
    "client_director": 0.90,
    "client_manager": 0.80,
    "internal_senior": 0.70,
    "internal_junior": 0.40,
    "unknown": 0.30,
}

# Resolution: Lower authority_rank wins. When equal, use LIVE_SOURCE_AUTHORITY_WEIGHTS.