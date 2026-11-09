# app/core/calculators/base.py
"""Base Calculator Classes and Registry."""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from uuid import UUID

from app.store.facts import FactRepository


@dataclass
class CalculatorContext:
    """Context passed to every calculator - contains resolved graph parameters."""
    tenant_id: str
    client_desk: str
    as_of_date: str  # ISO format: "2026-08-01"
    vendor_id: Optional[str] = None
    invoice_id: Optional[str] = None


class BaseCalculator(ABC):
    """Base class for all deterministic calculators."""

    @abstractmethod
    def get_required_predicates(self) -> List[str]:
        """Predicates this calculator needs from the graph."""
        pass

    @abstractmethod
    async def calculate(self, ctx: CalculatorContext, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute calculation. Returns structured result with status."""
        pass

    async def _load_params(self, ctx: CalculatorContext, predicates: List[str]) -> Dict[str, Any]:
        """Load parameters from Fact Repository."""
        # In production, would use actual session
        # This is a placeholder showing the pattern
        params = {}
        for pred in predicates:
            # fact = await repo.get_current_fact(ctx.tenant_id, pred, pred, ctx.as_of_date)
            # if fact: params[pred] = fact.object_value
            pass
        return params


# Calculator Registry
CALCULATORS = {}