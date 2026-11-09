# app/core/ingestion/conflict.py
"""4-Case Conflict Detection."""
from typing import List, Dict, Any, Optional
from uuid import UUID
from dataclasses import dataclass
from enum import Enum
from datetime import date

from app.models.fact import Fact
from app.core.ingestion.authority import AuthorityRanker


class ConflictType(str, Enum):
    DIRECT_CONTRADICTION = "direct_contradiction"
    PARAMETER_DRIFT = "parameter_drift"
    SCOPE_OVERLAP = "scope_overlap"
    AUTHORITY_CLASH = "authority_clash"


class ConflictSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Conflict:
    fact_id_1: UUID
    fact_id_2: UUID
    conflict_type: ConflictType
    severity: ConflictSeverity
    description: str


class ConflictDetector:
    """Detects 4 types of conflicts between new and existing facts."""

    def __init__(self, authority_ranker: Optional[AuthorityRanker] = None):
        self.authority_ranker = authority_ranker or AuthorityRanker()
        self.drift_threshold = 0.10  # 10% change triggers parameter drift

    def detect_conflicts(
        self,
        new_facts: List[Dict[str, Any]],
        existing_facts: List[Fact],
    ) -> List[Conflict]:
        """Detect all conflicts between new facts and existing facts."""
        conflicts = []

        for new_fact in new_facts:
            for existing in existing_facts:
                conflict = self._check_conflict(new_fact, existing)
                if conflict:
                    conflicts.append(conflict)

        return conflicts

    def _check_conflict(
        self,
        new_fact: Dict[str, Any],
        existing: Fact,
    ) -> Optional[Conflict]:
        """Check for conflict between new fact and existing fact."""
        # Same subject and predicate?
        if (new_fact.get("subject_entity_id") != existing.subject_entity_id or
            new_fact.get("predicate") != existing.predicate):
            return None

        # Check overlapping valid time
        if not self._valid_time_overlaps(new_fact, existing):
            return None

        # Both currently active?
        if existing.retracted_at is not None:
            return None

        # Case 1: Direct Contradiction - Different values
        if self._values_differ(new_fact.get("object_value"), existing.object_value):
            return Conflict(
                fact_id_1=existing.id,
                fact_id_2=UUID("00000000-0000-0000-0000-000000000000"),  # New fact ID TBD
                conflict_type=ConflictType.DIRECT_CONTRADICTION,
                severity=self._severity_for_direct_contradiction(new_fact, existing),
                description=f"Direct contradiction: {existing.object_value} vs {new_fact.get('object_value')}",
            )

        # Case 2: Parameter Drift - Same predicate, value changed beyond threshold
        if self._is_parameter_drift(new_fact.get("object_value"), existing.object_value):
            return Conflict(
                fact_id_1=existing.id,
                fact_id_2=UUID("00000000-0000-0000-0000-000000000000"),
                conflict_type=ConflictType.PARAMETER_DRIFT,
                severity=ConflictSeverity.HIGH,
                description=f"Parameter drift detected beyond {self.drift_threshold*100}% threshold",
            )

        # Case 3: Scope Overlap - Client memo + general rule
        if self._is_scope_overlap(new_fact, existing):
            return Conflict(
                fact_id_1=existing.id,
                fact_id_2=UUID("00000000-0000-0000-0000-000000000000"),
                conflict_type=ConflictType.SCOPE_OVERLAP,
                severity=ConflictSeverity.HIGH,
                description="Client-specific rule overlaps with general rule",
            )

        # Case 4: Authority Clash - Same rank, conflicting values
        if self._is_authority_clash(new_fact, existing):
            return Conflict(
                fact_id_1=existing.id,
                fact_id_2=UUID("00000000-0000-0000-0000-000000000000"),
                conflict_type=ConflictType.AUTHORITY_CLASH,
                severity=ConflictSeverity.CRITICAL,
                description="Same authority rank, conflicting values",
            )

        return None

    def _valid_time_overlaps(self, new_fact: Dict, existing: Fact) -> bool:
        """Check if valid time ranges overlap."""
        new_from = new_fact.get("valid_from")
        new_to = new_fact.get("valid_to")
        exist_from = existing.valid_from
        exist_to = existing.valid_to

        if not new_from or not exist_from:
            return True

        if new_to and exist_to:
            return new_from <= exist_to and new_to >= exist_from
        elif new_to:
            return new_from <= exist_to
        elif exist_to:
            return exist_from <= new_to
        return True

    def _values_differ(self, val1: Any, val2: Any) -> bool:
        """Check if two values are materially different."""
        if val1 is None or val2 is None:
            return val1 != val2

        if isinstance(val1, dict) and isinstance(val2, dict):
            # Compare dicts - check if any key differs
            all_keys = set(val1.keys()) | set(val2.keys())
            for k in all_keys:
                if val1.get(k) != val2.get(k):
                    return True
            return False

        return val1 != val2

    def _is_parameter_drift(self, val1: Any, val2: Any) -> bool:
        """Check if numeric parameter changed beyond threshold."""
        if not isinstance(val1, dict) or not isinstance(val2, dict):
            return False

        # Compare numeric fields
        for k in val1:
            if k in val2 and isinstance(val1[k], (int, float)) and isinstance(val2[k], (int, float)):
                v1, v2 = float(val1[k]), float(val2[k])
                if v1 != 0:
                    change = abs(v1 - v2) / abs(v1)
                    if change > self.drift_threshold:
                        return True
        return False

    def _is_scope_overlap(self, new_fact: Dict, existing: Fact) -> bool:
        """Check if client-specific and general rules overlap."""
        new_source = new_fact.get("source_type", "")
        exist_source = existing.source_type

        client_specific = new_source in ("client_memo",) or existing.source_type in ("client_memo",)
        general = new_source in ("sop_v4", "desk_instruction") or existing.source_type in ("sop_v4", "desk_instruction")

        return client_specific and general

    def _is_authority_clash(self, new_fact: Dict, existing: Fact) -> bool:
        """Check if same authority rank but conflicting values."""
        new_rank = self.authority_ranker.get_rank(
            new_fact.get("source_type", ""),
            new_fact.get("source_version", ""),
            new_fact.get("source_status", ""),
        )
        exist_rank = existing.authority_rank

        return new_rank == exist_rank and self._values_differ(
            new_fact.get("object_value"), existing.object_value
        )

    def _severity_for_direct_contradiction(self, new_fact: Dict, existing: Fact) -> str:
        """Determine severity for direct contradiction."""
        # Critical if both are high authority (rank <= 2)
        new_rank = self.authority_ranker.get_rank(
            new_fact.get("source_type", ""),
            new_fact.get("source_version", ""),
            new_fact.get("source_status", ""),
        )
        if new_rank <= 2 and existing.authority_rank <= 2:
            return "critical"
        return "high"