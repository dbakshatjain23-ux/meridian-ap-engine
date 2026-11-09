# app/core/calculators/price_variance.py
"""Price Variance Calculator - Reads price_tolerance from graph."""
from typing import Any, Dict
from app.core.calculators.base import BaseCalculator, CalculatorContext


class PriceVarianceCalculator(BaseCalculator):
    """Computes excess line value vs lower of (pct * po_line_val, cap)."""

    def get_required_predicates(self) -> list[str]:
        return ["price_tolerance"]  # Returns {"pct": 0.01, "cap": 500}

    async def calculate(self, ctx: CalculatorContext, inputs: Dict[str, Any]) -> Dict[str, Any]:
        # Load dynamic params from graph
        params = await self._load_params(ctx, self.get_required_predicates())
        price_tol = params.get("price_tolerance", {"pct": 0.01, "cap": 500.0})

        po_line_val = float(inputs.get("po_line_val", 0))
        po_unit_price = float(inputs.get("po_unit_price", 0))
        inv_unit_price = float(inputs.get("inv_unit_price", 0))
        inv_qty = float(inputs.get("inv_qty", 0))

        actual_line_val = inv_unit_price * inv_qty
        unit_excess = max(0.0, inv_unit_price - po_unit_price)
        total_excess = round(unit_excess * inv_qty, 2)

        pct_limit = price_tol.get("pct", 0.01) * po_line_val
        cap_limit = price_tol.get("cap", 500.0)
        allowed_tolerance = round(min(pct_limit, cap_limit), 2)

        is_pass = total_excess <= allowed_tolerance

        return {
            "status": "PASS" if is_pass else "PRICE_VAR",
            "po_line_value": po_line_val,
            "actual_line_value": actual_line_val,
            "total_excess": total_excess,
            "allowed_tolerance": allowed_tolerance,
            "governing_limit": "CAP" if cap_limit < pct_limit else "PERCENTAGE",
            "params_used": {"pct": price_tol.get("pct"), "cap": price_tol.get("cap")},
        }