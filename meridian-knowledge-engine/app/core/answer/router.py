# app/core/answer/router.py
"""Query Router - Routes to Calculator / Lookup / Judgment / Refuse."""
from typing import Dict, Any, Tuple
from app.config import get_settings

settings = get_settings()


class CalculatorRouter:
    """Routes queries to appropriate calculator or lookup."""

    CALCULATOR_KEYWORDS = {
        "calculate_price_variance": [
            "price tolerance", "price variance", "price difference",
            "price variation", "excess price", "price exceed",
        ],
        "classify_tds": [
            "tds section", "which section", "classify tds",
            "section 194", "tds classification",
        ],
        "calculate_tds": [
            "calculate tds", "tds amount", "tds on",
            "tax deducted", "tds calculation",
        ],
        "calculate_msme_due_date": [
            "msme", "micro", "small enterprise", "due date",
            "payment run", "payment schedule", "msme payment",
        ],
        "validate_e_invoice_requirement": [
            "e-invoice", "einvoice", "irn", "threshold",
            "e invoice required", "irn required",
        ],
        "normalize_supplier_string": [
            "normalize", "duplicate", "supplier string",
            "invoice number format", "supplier normalization",
        ],
    }

    JUDGMENT_KEYWORDS = [
        "mixed amc", "ambiguous contract", "classify tds",
        "which tds", "tds unclear",
    ]

    REFUSE_KEYWORDS = [
        "canteen", "subsidy", "hr policy", "leave policy",
        "salary", "bonus", "promotion", "hiring",
    ]

    def route(self, query: str, client_desk: str, as_of_date: str) -> Tuple[str, Dict[str, Any]]:
        """Returns (route_type, extracted_inputs)."""
        query_lower = query.lower()

        # Check for refusal (out of scope)
        if any(kw in query_lower for kw in self.REFUSE_KEYWORDS):
            return "refused", {"query": query, "client_desk": client_desk, "as_of_date": as_of_date}

        # Check calculators
        for calc_name, keywords in self.CALCULATOR_KEYWORDS.items():
            if any(kw in query_lower for kw in keywords):
                return "computable", {
                    "calculator": calc_name,
                    "inputs": self._extract_inputs(query, calc_name),
                }

        # Check judgment
        if any(kw in query_lower for kw in self.JUDGMENT_KEYWORDS):
            return "judgment", {"query": query, "client_desk": client_desk, "as_of_date": as_of_date}

        # Default to lookup
        return "lookup", {"query": query, "client_desk": client_desk, "as_of_date": as_of_date}

    def _extract_inputs(self, query: str, calc_name: str) -> Dict[str, Any]:
        """Extract structured inputs from query for specific calculator."""
        import re

        # Extract numbers
        nums = re.findall(r'[\d,]+\.?\d*', query.replace(',', ''))
        nums = [float(n) for n in nums]

        if calc_name == "calculate_price_variance":
            return {
                "po_line_val": nums[0] if len(nums) > 0 else 0,
                "po_unit_price": nums[1] if len(nums) > 1 else 0,
                "inv_unit_price": nums[2] if len(nums) > 2 else 0,
                "inv_qty": nums[3] if len(nums) > 3 else 0,
            }
        elif calc_name in ("classify_tds", "calculate_tds"):
            return {
                "invoice_description": query,
            }
        elif calc_name == "calculate_msme_due_date":
            return {
                "invoice_date": "2026-08-01",  # Would extract from query
                "acceptance_date": "2026-08-01",
            }
        elif calc_name == "validate_e_invoice_requirement":
            return {
                "vendor_id": "V20000",  # Would extract
                "invoice_total_inr": nums[0] if nums else 0,
            }
        elif calc_name == "normalize_supplier_string":
            # Extract invoice number pattern
            inv_match = re.search(r'[A-Z0-9/_-]+', query.upper())
            return {
                "invoice_num_str": inv_match.group() if inv_match else "",
            }

        return {}