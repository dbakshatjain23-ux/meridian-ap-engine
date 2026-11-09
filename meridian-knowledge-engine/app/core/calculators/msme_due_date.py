# app/core/calculators/msme_due_date.py
"""MSME Due Date Calculator - Reads msme_cap and payment_run_days from graph."""
from datetime import datetime, timedelta
from typing import Any, Dict
from app.core.calculators.base import BaseCalculator, CalculatorContext


class MSMEDueDateCalculator(BaseCalculator):
    """
    Enforces 15/45-day statutory caps under Sec 16 MSMED Act & Sec 43B(h) IT Act.
    MEDIUM enterprises follow standard commercial credit terms.
    Reads caps from graph.
    """

    def get_required_predicates(self) -> list[str]:
        return ["msme_cap", "payment_run_days"]  # {"micro": 15, "small": 45}, [1, 4] (Tue/Fri)

    async def calculate(self, ctx: CalculatorContext, inputs: Dict[str, Any]) -> Dict[str, Any]:
        invoice_date = datetime.strptime(inputs["invoice_date"], "%Y-%m-%d")
        acceptance_date = datetime.strptime(inputs["acceptance_date"], "%Y-%m-%d")
        msme_category = inputs.get("msme_category", "NONE").upper()
        has_written_agreement = inputs.get("has_written_agreement", True)
        agreement_days = inputs.get("agreement_days", 60)

        # Load params from graph
        params = await self._load_params(ctx, self.get_required_predicates())
        msme_caps = params.get("msme_cap", {"micro": 15, "small": 45})
        payment_run_days = params.get("payment_run_days", [1, 4])  # Tuesday=1, Friday=4

        base_date = max(invoice_date, acceptance_date)

        if msme_category in ["MICRO", "SMALL"]:
            statutory_cap = msme_caps.get(msme_category.lower(), 45 if has_written_agreement else 15)
            effective_credit_days = min(agreement_days, statutory_cap)
            is_statutory_capped = agreement_days > effective_credit_days
        else:
            # Medium or non-MSME suppliers follow agreement
            effective_credit_days = agreement_days
            is_statutory_capped = False

        due_date = base_date + timedelta(days=effective_credit_days)

        # Map due date to preceding payment run day (Tuesday/Friday)
        payment_run_date = due_date
        while payment_run_date.weekday() not in payment_run_days:
            payment_run_date -= timedelta(days=1)

        return {
            "msme_category": msme_category,
            "effective_credit_days": effective_credit_days,
            "calculated_due_date": due_date.strftime("%Y-%m-%d"),
            "scheduled_payment_run": payment_run_date.strftime("%Y-%m-%d"),
            "is_statutory_capped": is_statutory_capped,
            "params_used": {"msme_caps": msme_caps, "payment_run_days": payment_run_days},
        }