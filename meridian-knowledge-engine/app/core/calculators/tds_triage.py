# app/core/calculators/tds_triage.py
"""TDS Classifier and Calculator - Reads tds_rate from graph."""
from typing import Any, Dict
from app.core.calculators.base import BaseCalculator, CalculatorContext


class TDSClassifier(BaseCalculator):
    """
    Pre-calculation TDS Triage step.
    Evaluates service nature upfront to prevent floor errors.
    Returns section_code. Returns 'TDS_SECTION_UNCLEAR' for mixed AMCs.
    """

    def get_required_predicates(self) -> list[str]:
        return []  # Pure classification logic

    async def calculate(self, ctx: CalculatorContext, inputs: Dict[str, Any]) -> Dict[str, Any]:
        invoice_description = inputs.get("invoice_description", "").lower()
        vendor_category = inputs.get("vendor_category", "").upper()
        has_amc = inputs.get("has_amc_contract", False)
        is_mixed = inputs.get("is_mixed_service", False)

        # Check mixed AMC trap (e.g. CCTV repair + remote monitoring)
        if is_mixed or ("cctv" in invoice_description and "monitoring" in invoice_description and "maintenance" in invoice_description):
            return {
                "section_code": "TDS_SECTION_UNCLEAR",
                "rationale": "Mixed AMC containing both technical monitoring (194J) and physical maintenance (194C). Route to Tax Desk Lead Imran Qureshi.",
                "status": "ABSTAIN",
            }

        if "rent" in invoice_description or vendor_category == "LESSOR":
            return {"section_code": "194I", "rationale": "Section 194I applies to land/building/machinery rent.", "status": "SUCCESS"}
        elif any(kw in invoice_description for kw in ["software", "technical", "consulting"]) or vendor_category == "PROFESSIONAL":
            return {"section_code": "194J", "rationale": "Section 194J applies to professional/technical services (2% for technical).", "status": "SUCCESS"}
        elif any(kw in invoice_description for kw in ["transport", "freight", "works contract", "maintenance"]):
            return {"section_code": "194C", "rationale": "Section 194C applies to works contracts and freight.", "status": "SUCCESS"}
        elif "goods purchase" in invoice_description or vendor_category == "MANUFACTURER":
            return {"section_code": "194Q", "rationale": "Section 194Q applies to purchase of goods above 50 Lakhs.", "status": "SUCCESS"}
        else:
            return {"section_code": "194C", "rationale": "Default general contractor rate under SOP 6.", "status": "SUCCESS"}


class TDSCalculator(BaseCalculator):
    """
    Computes TDS strictly on taxable_value_inr (EXCLUDING GST).
    Enforces mandatory 20% rate when PAN is missing.
    Reads rates from graph - NOT hardcoded.
    """

    def get_required_predicates(self) -> list[str]:
        return ["tds_rate"]  # Returns {"194C": 0.02, "194J": 0.02, "194I": 0.10, "194Q": 0.001}

    async def calculate(self, ctx: CalculatorContext, inputs: Dict[str, Any]) -> Dict[str, Any]:
        section_code = inputs.get("section_code")
        taxable_value_inr = float(inputs.get("taxable_value_inr", 0))
        gst_inr = float(inputs.get("gst_inr", 0))
        is_corporate = inputs.get("is_corporate_vendor", True)
        pan_available = inputs.get("is_pan_available", True)

        if section_code == "TDS_SECTION_UNCLEAR":
            return {
                "status": "ABSTAIN",
                "reason": "TDS Section is unclear. Routed to Tax Desk.",
                "tds_amount": 0.0,
            }

        # Load rates from graph
        params = await self._load_params(ctx, self.get_required_predicates())
        rate_table = params.get("tds_rate", {
            "194C": 0.02, "194J": 0.02, "194I": 0.10, "194Q": 0.001
        })

        base_rate = rate_table.get(section_code, 0.02)

        # Corporate vs Non-Corporate adjustment for 194C
        if section_code == "194C" and not is_corporate:
            base_rate = 0.01

        # Statutory No-PAN Rule: Higher of 20% and base rate
        applied_rate = max(0.20, base_rate) if not pan_available else base_rate

        # Compute TDS strictly on TAXABLE VALUE (excluding GST)
        tds_amount = round(taxable_value_inr * applied_rate, 2)

        return {
            "status": "SUCCESS",
            "section_code": section_code,
            "taxable_base": taxable_value_inr,
            "gst_excluded": gst_inr,
            "applied_rate_pct": applied_rate * 100,
            "is_pan_penalty_applied": not pan_available,
            "tds_amount": tds_amount,
            "params_used": {"base_rate": base_rate, "applied_rate": applied_rate},
        }