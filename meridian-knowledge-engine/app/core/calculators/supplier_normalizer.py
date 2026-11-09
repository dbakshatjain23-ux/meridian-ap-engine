# app/core/calculators/supplier_normalizer.py
"""Supplier String Normalizer - Pure string logic."""
import re
from typing import Any, Dict
from app.core.calculators.base import BaseCalculator, CalculatorContext


class SupplierNormalizer(BaseCalculator):
    """
    Strips slashes, spaces, hyphens, leading zeros, and trailing /A or -REV suffixes.
    Prevents duplicate matching failures.
    Pure string logic - no graph params needed.
    """

    def get_required_predicates(self) -> list[str]:
        return []

    async def calculate(self, ctx: CalculatorContext, inputs: Dict[str, Any]) -> Dict[str, Any]:
        invoice_num_str = inputs.get("invoice_num_str", "")

        s = invoice_num_str.upper().strip()
        # Remove trailing resubmission suffixes
        s = re.sub(r'(/A|-REV|-A|/REV)$', '', s)
        # Remove punctuation, spaces, leading zeros
        s = re.sub(r'[^A-Z0-9]', '', s)
        s = s.lstrip('0')

        return {
            "normalized": s,
            "original": invoice_num_str,
        }