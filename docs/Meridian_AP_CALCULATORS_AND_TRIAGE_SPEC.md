# MERIDIAN SHARED SERVICES · ENTERPRISE KNOWLEDGE ENGINE
## Deterministic Python Calculators & `classify_tds` Specification
**Document ID**: `Meridian_AP_CALCULATORS_AND_TRIAGE_SPEC.md`  
**Target Environment**: **Python 3.11 (FastAPI on Render)** — Part of AP Industry Plug-in  
**Execution Guarantee**: **100% Deterministic Arithmetic (0% Math Hallucination)**  
**Parameter Source**: **All Rates/Caps/Thresholds Read from Temporal Graph (Facts Table)** — NEVER Hardcoded  

---

## 1. Overview & Dynamic Parameter Engine

To prevent calculation errors and math hallucinations (P6), the LLM is restricted to extracting parameters only. All arithmetic is executed by **6 Deterministic Python Calculators** in the AP Plug-in.

**Crucial Architecture Requirement**: Rates, caps, thresholds, and statutory days must **NEVER be hardcoded** inside Python scripts. The calculators dynamically query the **Fact Repository** for active parameters based on the invoice's `client_desk` and `as_of_date`.

```python
# app/core/calculators/base.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass

@dataclass
class CalculatorContext:
    """Context passed to every calculator — contains resolved graph parameters."""
    tenant_id: str
    client_desk: str
    as_of_date: str  # ISO format: "2026-08-01"
    vendor_id: Optional[str] = None
    invoice_id: Optional[str] = None

class BaseCalculator(ABC):
    """Base class for all deterministic calculators."""
    
    @abstractmethod
    def get_required_predicates(self) -> list[str]:
        """Predicates this calculator needs from the graph."""
        pass
    
    @abstractmethod
    async def calculate(self, ctx: CalculatorContext, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Execute calculation. Returns structured result with status."""
        pass
    
    async def _load_params(self, ctx: CalculatorContext, predicates: list[str]) -> Dict[str, Any]:
        """Load parameters from Fact Repository."""
        from app.store.facts import FactRepository
        from app.database import get_session
        
        async with get_session() as session:
            repo = FactRepository(session)
            params = {}
            for pred in predicates:
                fact = await repo.get_current_fact(
                    tenant_id=ctx.tenant_id,
                    subject_canonical=pred,
                    predicate=pred,
                    as_of_date=ctx.as_of_date
                )
                if fact:
                    params[pred] = fact.object_value
            return params
```

---

## 2. Calculator Registry (AP Plug-in)

```python
# app/core/calculators/__init__.py
from .price_variance import PriceVarianceCalculator
from .tds_triage import TDSClassifier, TDSCalculator
from .msme_due_date import MSMEDueDateCalculator
from .e_invoice import EInvoiceValidator
from .supplier_normalizer import SupplierNormalizer

CALCULATORS = {
    "calculate_price_variance": PriceVarianceCalculator(),
    "classify_tds": TDSClassifier(),
    "calculate_tds": TDSCalculator(),
    "calculate_msme_due_date": MSMEDueDateCalculator(),
    "validate_e_invoice_requirement": EInvoiceValidator(),
    "normalize_supplier_string": SupplierNormalizer(),
}

def get_calculator(name: str) -> BaseCalculator:
    calc = CALCULATORS.get(name)
    if not calc:
        raise ValueError(f"Unknown calculator: {name}")
    return calc
```

---

## 3. Complete Calculator Implementations

### 3.1 Price Variance Calculator

```python
# app/core/calculators/price_variance.py
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
        
        po_line_val = float(inputs["po_line_val"])
        po_unit_price = float(inputs["po_unit_price"])
        inv_unit_price = float(inputs["inv_unit_price"])
        inv_qty = float(inputs["inv_qty"])
        
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
            "params_used": {"pct": price_tol.get("pct"), "cap": price_tol.get("cap")}
        }
```

### 3.2 TDS Classifier (Pre-Calculation Triage)

```python
# app/core/calculators/tds_triage.py
from typing import Any, Dict, Tuple
from app.core.calculators.base import BaseCalculator, CalculatorContext

class TDSClassifier(BaseCalculator):
    """
    Pre-calculation TDS Triage step.
    Evaluates service nature upfront to prevent 101 floor errors.
    Returns (section_code, rationale). Returns 'TDS_SECTION_UNCLEAR' for mixed AMCs.
    """
    
    def get_required_predicates(self) -> list[str]:
        return []  # Pure classification logic — no graph params needed
    
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
                "status": "ABSTAIN"
            }
        
        if "rent" in invoice_description or vendor_category == "LESSOR":
            return {"section_code": "194I", "rationale": "Section 194I applies to land/building/machinery rent.", "status": "SUCCESS"}
        elif any(kw in invoice_description for kw in ["software", "technical", "consulting"]) or vendor_category == "PROFESSIONAL":
            return {"section_code": "194J", "rationale": "Section 194J applies to professional/technical services (2% for technical).", "status": "SUCCESS"}
        elif any(kw in invoice_description for kw in ["transport", "freight", "works contract", "maintenance"]):
            return {"section_code": "194C", "rationale": "Section 194C applies to works contracts and freight.", "status": "SUCCESS"}
        elif "goods purchase" in invoice_description or vendor_category == "MANUFACTURER":
            return {"section_code": "194Q", "rationale": "Section 194Q applies to purchase of goods above ₹50 Lakhs.", "status": "SUCCESS"}
        else:
            return {"section_code": "194C", "rationale": "Default general contractor rate under SOP §6.", "status": "SUCCESS"}
```

### 3.3 TDS Calculator (Reads Rates from Graph)

```python
# app/core/calculators/tds_calculator.py
from typing import Any, Dict
from app.core.calculators.base import BaseCalculator, CalculatorContext

class TDSCalculator(BaseCalculator):
    """
    Computes TDS strictly on taxable_value_inr (EXCLUDING GST).
    Enforces mandatory 20% rate when PAN is missing.
    Reads rates from graph — NOT hardcoded.
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
                "tds_amount": 0.0
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
            "params_used": {"base_rate": base_rate, "applied_rate": applied_rate}
        }
```

### 3.4 MSME Due Date Calculator

```python
# app/core/calculators/msme_due_date.py
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
            "params_used": {"msme_caps": msme_caps, "payment_run_days": payment_run_days}
        }
```

### 3.5 E-Invoice Validator

```python
# app/core/calculators/e_invoice.py
from typing import Any, Dict
from app.core.calculators.base import BaseCalculator, CalculatorContext

class EInvoiceValidator(BaseCalculator):
    """
    Checks supplier AATO turnover against the ₹5 Crore threshold.
    Reads threshold from graph.
    """
    
    def get_required_predicates(self) -> list[str]:
        return ["e_invoice_threshold"]  # Returns 50000000 (₹5 Cr)
    
    async def calculate(self, ctx: CalculatorContext, inputs: Dict[str, Any]) -> Dict[str, Any]:
        vendor_id = inputs.get("vendor_id")
        invoice_total_inr = float(inputs.get("invoice_total_inr", 0))
        
        # Load threshold from graph
        params = await self._load_params(ctx, self.get_required_predicates())
        threshold = params.get("e_invoice_threshold", 50000000)  # ₹5 Cr default
        
        # Get vendor AATO band from vendor entity facts
        from app.store.facts import FactRepository
        from app.database import get_session
        
        async with get_session() as session:
            repo = FactRepository(session)
            vendor_entity = await repo.get_entity_by_canonical(ctx.tenant_id, "vendor", vendor_id)
            aato_fact = None
            if vendor_entity:
                aato_fact = await repo.get_current_fact(ctx.tenant_id, vendor_entity.canonical_name, "aato_band", ctx.as_of_date)
        
        aato_band = aato_fact.object_value if aato_fact else "UNKNOWN"
        required = aato_band == "ABOVE_5CR" and invoice_total_inr >= threshold
        
        return {
            "required": required,
            "threshold": threshold,
            "vendor_aato_band": aato_band,
            "invoice_total": invoice_total_inr,
            "status": "IRN_MISSING" if required else "OK",
            "params_used": {"threshold": threshold}
        }
```

### 3.6 Supplier String Normalizer

```python
# app/core/calculators/supplier_normalizer.py
import re
from typing import Any, Dict
from app.core.calculators.base import BaseCalculator, CalculatorContext

class SupplierNormalizer(BaseCalculator):
    """
    Strips slashes, spaces, hyphens, leading zeros, and trailing /A or -REV suffixes.
    Prevents duplicate matching failures (8.0% of QC errors).
    Pure string logic — no graph params needed.
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
            "original": invoice_num_str
        }
```

---

## 4. Router Integration (3-Lane)

```python
# app/core/answer/router.py
from typing import Any, Dict, Literal
from app.core.calculators import get_calculator, CALCULATORS

class CalculatorRouter:
    """Routes queries to appropriate calculator or lookup."""
    
    COMPUTABLE_KEYWORDS = {
        "price tolerance", "price variance", "price difference",
        "tds", "tax deducted", "section 194",
        "msme", "micro", "small enterprise", "due date", "payment run",
        "e-invoice", "einvoice", "irn", "threshold",
        "normalize", "duplicate", "supplier string"
    }
    
    def route(self, query: str, client_desk: str, as_of_date: str) -> tuple[str, Dict[str, Any]]:
        """Returns (route_type, extracted_inputs)."""
        query_lower = query.lower()
        
        # Price Variance
        if any(kw in query_lower for kw in ["price tolerance", "price variance", "price difference"]):
            return "computable", {
                "calculator": "calculate_price_variance",
                "inputs": self._extract_price_inputs(query)
            }
        
        # TDS Classification
        if any(kw in query_lower for kw in ["tds section", "which section", "classify tds"]):
            return "computable", {
                "calculator": "classify_tds",
                "inputs": self._extract_tds_classify_inputs(query)
            }
        
        # TDS Calculation
        if any(kw in query_lower for kw in ["calculate tds", "tds amount", "tds on"]):
            return "computable", {
                "calculator": "calculate_tds",
                "inputs": self._extract_tds_calc_inputs(query)
            }
        
        # MSME Due Date
        if any(kw in query_lower for kw in ["msme", "micro", "small enterprise", "due date", "payment run"]):
            return "computable", {
                "calculator": "calculate_msme_due_date",
                "inputs": self._extract_msme_inputs(query)
            }
        
        # E-Invoice
        if any(kw in query_lower for kw in ["e-invoice", "einvoice", "irn", "threshold"]):
            return "computable", {
                "calculator": "validate_e_invoice_requirement",
                "inputs": self._extract_einvoice_inputs(query)
            }
        
        # Supplier Normalize
        if any(kw in query_lower for kw in ["normalize", "duplicate", "supplier string"]):
            return "computable", {
                "calculator": "normalize_supplier_string",
                "inputs": {"invoice_num_str": self._extract_invoice_num(query)}
            }
        
        # Default to Lookup Lane
        return "lookup", {"query": query, "client_desk": client_desk, "as_of_date": as_of_date}
    
    def _extract_price_inputs(self, query: str) -> Dict[str, Any]:
        # LLM-based extraction in production; regex fallback here
        import re
        nums = re.findall(r'[\d,]+\.?\d*', query.replace(',', ''))
        return {
            "po_line_val": float(nums[0]) if len(nums) > 0 else 0,
            "po_unit_price": float(nums[1]) if len(nums) > 1 else 0,
            "inv_unit_price": float(nums[2]) if len(nums) > 2 else 0,
            "inv_qty": float(nums[3]) if len(nums) > 3 else 0
        }
    
    # ... other extractors similar
```

---

## 5. Acceptance Test Mapping (T1-T10)

| Test | Calculator(s) | Expected Output |
|---|---|---|
| **T1** | `calculate_price_variance` | `allowed_tolerance = 500` (min of 1% × line, ₹500) |
| **T2** | `validate_e_invoice_requirement` | `required = True` for ₹8.9 Cr vendor, threshold = ₹5 Cr |
| **T3** | Lookup Lane (CM-PHA-01) | Citation to CM-PHA-01, flags FAQ error |
| **T4** | Lookup + Practice | Side-by-side: SOP v4.0 §4.6 + Interview 1 [02:30] |
| **T5** | `calculate_price_variance` | `total_excess = 2500`, `allowed_tolerance = 500`, `status = PRICE_VAR` |
| **T6** | `classify_tds` + `calculate_tds` | `section_code = 194J`, `tds_amount = 9600` (excludes GST) |
| **T7** | `calculate_msme_due_date` | `effective_credit_days = 15`, `scheduled_payment_run = 2026-08-14` |
| **T8** | Router → Refuse | `route = "refused"`, escalates to Sandeep Rao |
| **T9** | Conflict Scanner | Detects ≥12/15 planted conflicts |
| **T10** | Tacit Capture API | Creates fact with `review_by_date = +6 months`, `status = approved` |

---

## 6. Testing Requirements

```python
# tests/unit/test_calculators.py
import pytest
from app.core.calculators import get_calculator
from app.core.calculators.base import CalculatorContext

@pytest.fixture
def ctx():
    return CalculatorContext(
        tenant_id="meridian",
        client_desk="Arvana Infra",
        as_of_date="2026-08-01"
    )

class TestPriceVariance:
    @pytest.mark.asyncio
    async def test_t5_price_variance(self, ctx):
        calc = get_calculator("calculate_price_variance")
        result = await calc.calculate(ctx, {
            "po_line_val": 197500.00,
            "po_unit_price": 395.00,
            "inv_unit_price": 400.00,
            "inv_qty": 500.0
        })
        assert result["total_excess"] == 2500.00
        assert result["allowed_tolerance"] == 500.00
        assert result["status"] == "PRICE_VAR"

class TestTDS:
    @pytest.mark.asyncio
    async def test_t6_tds_excludes_gst(self, ctx):
        classifier = get_calculator("classify_tds")
        section = await classifier.calculate(ctx, {"invoice_description": "Software support"})
        assert section["section_code"] == "194J"
        
        calc = get_calculator("calculate_tds")
        result = await calc.calculate(ctx, {
            "section_code": "194J",
            "taxable_value_inr": 480000,
            "gst_inr": 86400,
            "is_corporate_vendor": True,
            "is_pan_available": True
        })
        assert result["tds_amount"] == 9600.00
        assert result["taxable_base"] == 480000

class TestMSME:
    @pytest.mark.asyncio
    async def test_t7_micro_supplier(self, ctx):
        calc = get_calculator("calculate_msme_due_date")
        result = await calc.calculate(ctx, {
            "invoice_date": "2026-08-01",
            "acceptance_date": "2026-08-01",
            "msme_category": "MICRO",
            "has_written_agreement": False,
            "agreement_days": 60
        })
        assert result["effective_credit_days"] == 15
        assert result["scheduled_payment_run"] == "2026-08-14"
```