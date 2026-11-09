# MERIDIAN SHARED SERVICES · ENTERPRISE KNOWLEDGE ENGINE
## Ragas Benchmark & Acceptance Testing Suite (T1–T10)
**Document ID**: `Meridian_AP_EVALUATION_AND_TESTING_SUITE.md`  
**Evaluation Set**: 160 Gold Questions (`PS - 07_qa_evaluation_set.xlsx`)  

---

## 1. Acceptance Tests (T1 – T10) Implementation Runner

```python
import pytest
from typing import Dict, Any

# Interface Call to Engine
def query_engine(query: str, client_desk: str = "ALL", as_of_date: str = "2026-08-01") -> Dict[str, Any]:
    # Runs 3-Lane pipeline
    pass

class TestEngineAcceptanceSuite:

    def test_T1_price_tolerance_current_vs_old(self):
        """T1: Answers lower of 1% or ₹500 under SOP v4.0 §4.2; notes superseded 2%/₹1,000 rule."""
        res = query_engine("What is the price tolerance limit?", as_of_date="2026-08-01")
        assert "500" in res["answer_markdown"]
        assert "1%" in res["answer_markdown"]
        assert "SOP v4.0 §4.2" in str(res["citations"])
        assert "superseded" in res["older_rule_note"].lower()

    def test_T2_einvoice_irn_threshold(self):
        """T2: Supplier with ₹8.9 Cr turnover sends invoice without IRN. Rejects obsolete ₹10 Cr rule."""
        res = query_engine("Vendor turnover ₹8.9 Cr sends invoice without IRN. Acceptable?", as_of_date="2026-08-01")
        assert res["status"] == "REJECT" or "not acceptable" in res["answer_markdown"].lower()
        assert "5 crore" in res["answer_markdown"].lower()

    def test_T3_pharma_excipient_qa_release(self):
        """T3: Pharma excipient invoices need QA release. Flags 2023 FAQ error."""
        res = query_engine("Do Pharma excipient invoices need QA release before payment?", client_desk="Arvana Pharma")
        assert "YES" in res["answer_markdown"].upper()
        assert "CM-PHA-01" in str(res["citations"])

    def test_T4_infra_no_grn_side_by_side(self):
        """T4: Displays SOP v4.0 §4.6 hold rule SIDE-BY-SIDE with Lakshmi Tuesday-noon practice."""
        res = query_engine("Infra invoice received Saturday with no GRN. Chase site engineer Monday?", client_desk="Arvana Infra")
        assert "NO_GRN" in res["answer_markdown"]
        assert "Interview 1 [02:30]" in str(res["practice_notes"]) or "Tuesday noon" in str(res["practice_notes"])

    def test_T5_price_variance_calculation(self):
        """T5: PO ₹395, Invoice ₹400 (500 bags). Excess ₹2,500 vs limit ₹500. Raises PRICE_VAR."""
        res = query_engine("PO price ₹395, invoice ₹400 for 500 bags. Pass or variance?")
        assert res["math_result"]["total_excess"] == 2500.00
        assert res["math_result"]["allowed_tolerance"] == 500.00
        assert res["status"] == "PRICE_VAR"

    def test_T6_tds_calculation_excluding_gst(self):
        """T6: Software support taxable ₹4,80,000 + GST. Computes 194J 2% = ₹9,600 (excluding GST)."""
        res = query_engine("TDS on software support, taxable value ₹4,80,000 plus GST?")
        assert res["math_result"]["tds_amount"] == 9600.00
        assert res["math_result"]["section_code"] == "194J"

    def test_T7_msme_payment_run_mapping(self):
        """T7: Micro supplier accepted 1 Aug 2026. Due 16 Aug (15d cap); maps to Fri 14 Aug run."""
        res = query_engine("Micro supplier accepted 1 Aug 2026, no agreement. Due date and payment run?")
        assert res["math_result"]["effective_credit_days"] == 15
        assert res["math_result"]["scheduled_payment_run"] == "2026-08-14"

    def test_T8_out_of_corpus_canteen_subsidy_abstain(self):
        """T8: Out-of-corpus query abstains and routes to Sandeep Rao."""
        res = query_engine("What is the canteen subsidy policy for Hyderabad floor?")
        assert res["status"] == "ABSTAIN"
        assert "Sandeep Rao" in res["answer_markdown"]

    def test_T9_conflict_scanner_recall(self):
        """T9: Conflict scanner detects >= 12 of 15 planted conflicts."""
        pass

    def test_T10_tacit_capture_card_ttl(self):
        """T10: Captured habit cards have mandatory 6-month TTL review dates."""
        pass
```

---

## 2. Ragas Continuous Benchmark Metrics & Target KPIs

| Ragas Metric | Target Score | Verification Purpose |
|---|:---:|---|
| **Faithfulness** | $\ge 0.95$ | Verifies zero hallucinated claims; every fact traces to source passage. |
| **Answer Relevance** | $\ge 0.95$ | Ensures direct, crisp answers tailored to processor exception context. |
| **Context Precision** | $\ge 0.90$ | Validates that graph subgraphs return exact claims without text noise. |
| **Harmfulness / Safety** | $0.00$ | Confirms 100% PII regex masking (PAN, bank accounts) under DPDP Act. |
