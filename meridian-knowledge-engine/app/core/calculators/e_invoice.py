# app/core/calculators/e_invoice.py
"""E-Invoice Validator - Reads e_invoice_threshold from graph."""
from typing import Any, Dict
from app.core.calculators.base import BaseCalculator, CalculatorContext


class EInvoiceValidator(BaseCalculator):
    """
    Checks supplier AATO turnover against the 5 Crore threshold.
    Reads threshold from graph.
    """

    def get_required_predicates(self) -> list[str]:
        return ["e_invoice_threshold"]  # Returns 50000000 (5 Cr)

    async def calculate(self, ctx: CalculatorContext, inputs: Dict[str, Any]) -> Dict[str, Any]:
        vendor_id = inputs.get("vendor_id")
        invoice_total_inr = float(inputs.get("invoice_total_inr", 0))

        # Load threshold from graph
        params = await self._load_params(ctx, self.get_required_predicates())
        threshold = params.get("e_invoice_threshold", 50000000)  # 5 Cr default

        # Get vendor AATO band from vendor entity facts
        from app.store.facts import FactRepository
        from app.store.entities import EntityRepository
        from app.database import get_session

        async with get_session() as session:
            entity_repo = EntityRepository(session)
            fact_repo = FactRepository(session)

            vendor_entity = await entity_repo.get_by_canonical(ctx.tenant_id, "vendor", vendor_id)
            aato_fact = None
            if vendor_entity:
                aato_fact = await fact_repo.get_current_fact(ctx.tenant_id, vendor_entity.canonical_name, "aato_band", ctx.as_of_date)

        aato_band = aato_fact.object_value if aato_fact else "UNKNOWN"
        required = aato_band == "ABOVE_5CR" and invoice_total_inr >= threshold

        return {
            "required": required,
            "threshold": threshold,
            "vendor_aato_band": aato_band,
            "invoice_total": invoice_total_inr,
            "status": "IRN_MISSING" if required else "OK",
            "params_used": {"threshold": threshold},
        }