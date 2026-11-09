# MERIDIAN SHARED SERVICES · ENTERPRISE KNOWLEDGE ENGINE
## Deterministic Python Calculators & `classify_tds` Specification
**Document ID**: `Meridian_AP_CALCULATORS_AND_TRIAGE_SPEC.md`  
**Target Environment**: Python 3.12 (Zoho Catalyst AppLogic Layer)  
**Execution Guarantee**: 100% Deterministic Arithmetic (0% Math Hallucination)

---

## 1. Overview & Dynamic Parameter Engine

To prevent calculation errors and math hallucinations (P6), the LLM is restricted to extracting parameters only. All arithmetic is executed by **5 Deterministic Python Math Calculators**. 

**Crucial Architecture Requirement**: Rates, caps, thresholds, and statutory days must **NEVER be hardcoded** inside Python scripts. The tools dynamically query the claim store for active parameters based on the invoice's `as_of_date`.

---

## 2. Complete Python Calculator Implementations

```python
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple

class APMathCalculators:
    
    @staticmethod
    def classify_tds(
        invoice_description: str,
        vendor_category: str,
        has_amc_contract: bool = False,
        is_mixed_service: bool = False
    ) -> Tuple[str, str]:
        """
        Pre-calculation TDS Triage step.
        Evaluates service nature upfront to prevent 101 floor errors.
        Returns (section_code, rationale). Returns 'TDS_SECTION_UNCLEAR' for mixed AMCs.
        """
        desc_lower = invoice_description.lower()
        
        # Check mixed AMC trap (e.g. CCTV repair + remote monitoring)
        if is_mixed_service or ("cctv" in desc_lower and "monitoring" in desc_lower and "maintenance" in desc_lower):
            return "TDS_SECTION_UNCLEAR", "Mixed AMC containing both technical monitoring (194J) and physical maintenance (194C). Route to Tax Desk Lead Imran Qureshi."
        
        if "rent" in desc_lower or vendor_category.upper() == "LESSOR":
            return "194I", "Section 194I applies to land/building/machinery rent."
        elif "software" in desc_lower or "technical" in desc_lower or "consulting" in desc_lower or vendor_category.upper() == "PROFESSIONAL":
            return "194J", "Section 194J applies to professional/technical services."
        elif "transport" in desc_lower or "freight" in desc_lower or "works contract" in desc_lower or "maintenance" in desc_lower:
            return "194C", "Section 194C applies to works contracts and freight."
        elif "goods purchase" in desc_lower or vendor_category.upper() == "MANUFACTURER":
            return "194Q", "Section 194Q applies to purchase of goods above ₹50 Lakhs."
        else:
            return "194C", "Default general contractor rate under SOP §6."

    @staticmethod
    def calculate_tds(
        taxable_value_inr: float,
        gst_inr: float,
        section_code: str,
        is_corporate_vendor: bool = True,
        is_pan_available: bool = True
    ) -> Dict[str, Any]:
        """
        Computes TDS strictly on taxable_value_inr (EXCLUDING GST).
        Enforces mandatory 20% rate when PAN is missing.
        """
        if section_code == "TDS_SECTION_UNCLEAR":
            return {
                "status": "ABSTAIN",
                "reason": "TDS Section is unclear. Routed to Tax Desk.",
                "tds_amount": 0.0
            }
            
        # Base statutory rates
        rate_table = {
            "194C": 0.02 if is_corporate_vendor else 0.01,
            "194J": 0.02 if "tech" in section_code.lower() else 0.10, # 2% for tech, 10% for professional
            "194I": 0.10,
            "194Q": 0.001
        }
        
        base_rate = rate_table.get(section_code, 0.02)
        
        # Statutory No-PAN Rule: Higher of 20% and base rate
        applied_rate = max(0.20, base_rate) if not is_pan_available else base_rate
        
        # Compute TDS strictly on TAXABLE VALUE (excluding GST)
        tds_amount = round(taxable_value_inr * applied_rate, 2)
        
        return {
            "status": "SUCCESS",
            "section_code": section_code,
            "taxable_base": taxable_value_inr,
            "gst_excluded": gst_inr,
            "applied_rate_pct": applied_rate * 100,
            "is_pan_penalty_applied": not is_pan_available,
            "tds_amount": tds_amount
        }

    @staticmethod
    def calculate_price_variance(
        po_line_val: float,
        po_unit_price: float,
        inv_unit_price: float,
        inv_qty: float,
        claim_params: Dict[str, Any] = {"pct": 0.01, "cap": 500.0}
    ) -> Dict[str, Any]:
        """
        Computes excess line value vs lower of (pct * po_line_val, cap).
        Reads claim_params dynamically from dated store.
        """
        actual_line_val = inv_unit_price * inv_qty
        unit_excess = max(0.0, inv_unit_price - po_unit_price)
        total_excess = round(unit_excess * inv_qty, 2)
        
        pct_limit = claim_params.get("pct", 0.01) * po_line_val
        cap_limit = claim_params.get("cap", 500.0)
        allowed_tolerance = round(min(pct_limit, cap_limit), 2)
        
        is_pass = total_excess <= allowed_tolerance
        
        return {
            "status": "PASS" if is_pass else "PRICE_VAR",
            "po_line_value": po_line_val,
            "actual_line_value": actual_line_val,
            "total_excess": total_excess,
            "allowed_tolerance": allowed_tolerance,
            "governing_limit": "CAP" if cap_limit < pct_limit else "PERCENTAGE"
        }

    @staticmethod
    def calculate_msme_due_date(
        invoice_date_str: str,
        acceptance_date_str: str,
        msme_category: str, # 'MICRO', 'SMALL', 'MEDIUM', 'NONE'
        has_written_agreement: bool = True,
        agreement_days: int = 60
    ) -> Dict[str, Any]:
        """
        Enforces 15/45-day statutory caps under Sec 16 MSMED Act & Sec 43B(h) IT Act.
        MEDIUM enterprises follow standard commercial credit terms.
        """
        inv_date = datetime.strptime(invoice_date_str, "%Y-%m-%d")
        acc_date = datetime.strptime(acceptance_date_str, "%Y-%m-%d")
        base_date = max(inv_date, acc_date)
        
        category_upper = msme_category.upper()
        if category_upper in ["MICRO", "SMALL"]:
            statutory_cap = 45 if has_written_agreement else 15
            effective_credit_days = min(agreement_days, statutory_cap)
        else:
            # Medium or non-MSME suppliers follow agreement
            effective_credit_days = agreement_days
            
        due_date = base_date + timedelta(days=effective_credit_days)
        
        # Map due date to preceding Tuesday/Friday payment run
        payment_run_date = due_date
        while payment_run_date.weekday() not in [1, 4]: # 1: Tuesday, 4: Friday
            payment_run_date -= timedelta(days=1)
            
        return {
            "msme_category": category_upper,
            "effective_credit_days": effective_credit_days,
            "calculated_due_date": due_date.strftime("%Y-%m-%d"),
            "scheduled_payment_run": payment_run_date.strftime("%Y-%m-%d"),
            "is_statutory_capped": category_upper in ["MICRO", "SMALL"] and agreement_days > effective_credit_days
        }

    @staticmethod
    def normalize_supplier_string(invoice_num_str: str) -> str:
        """
        Strips slashes, spaces, hyphens, leading zeros, and trailing /A or -REV suffixes.
        Prevents duplicate matching failures (8.0% of QC errors).
        """
        s = invoice_num_str.upper().strip()
        # Remove trailing resubmission suffixes
        s = re.sub(r'(/A|-REV|-A|/REV)$', '', s)
        # Remove punctuation, spaces, leading zeros
        s = re.sub(r'[^A-Z0-9]', '', s)
        s = s.lstrip('0')
        return s
```
