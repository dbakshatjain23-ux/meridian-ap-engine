# MERIDIAN SHARED SERVICES · ENTERPRISE KNOWLEDGE ENGINE
## Evaluation & Testing Suite — Acceptance Tests, Ragas Benchmarks, Generality Proof
**Document ID**: `Meridian_AP_EVALUATION_AND_TESTING_SUITE.md`  
**Evaluation Set**: 160 Gold Questions (`PS-07_qa_evaluation_set.xlsx`)  
**Test Infrastructure**: `pytest` + `ragas` + Custom Harness  

---

## 1. Acceptance Tests (T1 – T10) — MUST PASS

```python
# tests/acceptance/test_t1_t10.py
import pytest
from typing import Dict, Any
from tests.fixtures.meridian_client import MeridianTestClient

@pytest.fixture(scope="session")
def client() -> MeridianTestClient:
    """Test client pointing to running API (local or deployed)."""
    return MeridianTestClient(base_url="http://localhost:8000/v1", tenant="meridian")

class TestEngineAcceptanceSuite:
    """T1-T10 from Meridian PRD — Exact acceptance criteria."""

    def test_T1_price_tolerance_current_vs_old(self, client):
        """T1: Answers lower of 1% or ₹500 under SOP v4.0 §4.2; notes superseded 2%/₹1,000 rule."""
        res = client.ask("What is the price tolerance limit?", as_of_date="2026-08-01")
        assert res["execution_lane"] == "COMPUTABLE"
        assert "500" in res["answer_markdown"]
        assert "1%" in res["answer_markdown"]
        assert any("SOP v4.0" in c.get("source", "") and "§4.2" in c.get("section", "") for c in res["citations"])
        assert any("superseded" in s.get("note", "").lower() for s in res["older_sources"])

    def test_T2_einvoice_irn_threshold(self, client):
        """T2: Supplier with ₹8.9 Cr turnover sends invoice without IRN. Rejects obsolete ₹10 Cr rule."""
        res = client.ask("Vendor turnover ₹8.9 Cr sends invoice without IRN. Acceptable?", as_of_date="2026-08-01")
        assert res["status"] in ("REJECT", "IRN_MISSING") or "not acceptable" in res["answer_markdown"].lower()
        assert "5 crore" in res["answer_markdown"].lower() or "5 cr" in res["answer_markdown"].lower()
        assert any("10 crore" in s.get("note", "").lower() or "10 cr" in s.get("note", "").lower() for s in res["older_sources"])

    def test_T3_pharma_excipient_qa_release(self, client):
        """T3: Pharma excipient invoices need QA release. Flags 2023 FAQ error."""
        res = client.ask("Do Pharma excipient invoices need QA release before payment?", client_desk="Arvana Pharma")
        assert "YES" in res["answer_markdown"].upper()
        assert any("CM-PHA-01" in c.get("source", "") for c in res["citations"])
        assert any("faq" in s.get("source", "").lower() and "2023" in s.get("source", "") for s in res["older_sources"])

    def test_T4_infra_no_grn_side_by_side(self, client):
        """T4: Displays SOP v4.0 §4.6 hold rule SIDE-BY-SIDE with Lakshmi Tuesday-noon practice."""
        res = client.ask("Infra invoice received Saturday with no GRN. Chase site engineer Monday?", client_desk="Arvana Infra")
        assert "NO_GRN" in res["answer_markdown"]
        # Rule present
        assert any("SOP v4.0" in c.get("source", "") and "§4.6" in c.get("section", "") for c in res["citations"])
        # Practice present (side-by-side)
        practice_found = any(
            "Interview 1" in str(p) and ("02:30" in str(p) or "05:18" in str(p)) 
            for p in res.get("practice_notes", [])
        ) or any("Tuesday noon" in str(p) for p in res.get("practice_notes", []))
        assert practice_found, "Lakshmi's Tuesday-noon practice not found in practice_notes"

    def test_T5_price_variance_calculation(self, client):
        """T5: PO ₹395, Invoice ₹400 (500 bags). Excess ₹2,500 vs limit ₹500. Raises PRICE_VAR."""
        res = client.ask("PO price ₹395, invoice ₹400 for 500 bags. Pass or variance?")
        assert res["math_result"]["total_excess"] == 2500.00
        assert res["math_result"]["allowed_tolerance"] == 500.00
        assert res["status"] == "PRICE_VAR"
        assert res["math_result"]["governing_limit"] == "CAP"

    def test_T6_tds_calculation_excluding_gst(self, client):
        """T6: Software support taxable ₹4,80,000 + GST. Computes 194J 2% = ₹9,600 (excluding GST)."""
        res = client.ask("TDS on software support, taxable value ₹4,80,000 plus GST?")
        assert res["math_result"]["tds_amount"] == 9600.00
        assert res["math_result"]["section_code"] == "194J"
        assert res["math_result"]["taxable_base"] == 480000
        assert res["math_result"]["gst_excluded"] > 0

    def test_T7_msme_payment_run_mapping(self, client):
        """T7: Micro supplier accepted 1 Aug 2026. Due 16 Aug (15d cap); maps to Fri 14 Aug run."""
        res = client.ask("Micro supplier accepted 1 Aug 2026, no agreement. Due date and payment run?")
        assert res["math_result"]["effective_credit_days"] == 15
        assert res["math_result"]["scheduled_payment_run"] == "2026-08-14"
        assert res["math_result"]["is_statutory_capped"] is True

    def test_T8_out_of_corpus_canteen_subsidy_abstain(self, client):
        """T8: Out-of-corpus query abstains and routes to Sandeep Rao."""
        res = client.ask("What is the canteen subsidy policy for Hyderabad floor?")
        assert res["status"] in ("ABSTAIN", "ESCALATED", "REFUSED")
        assert "Sandeep Rao" in res["answer_markdown"] or "Process Owner" in res["answer_markdown"]

    def test_T9_conflict_scanner_recall(self, client):
        """T9: Conflict scanner detects >= 12 of 15 planted conflicts."""
        conflicts = client.get_conflicts(status="open")
        planted_conflicts = [c for c in conflicts if c.get("type") in ("direct_contradiction", "scope_overlap")]
        assert len(planted_conflicts) >= 12, f"Only {len(planted_conflicts)}/15 planted conflicts detected"

    def test_T10_tacit_capture_card_ttl(self, client):
        """T10: Captured habit cards have mandatory 6-month TTL review dates."""
        # Create a tacit card
        card = client.capture_tacit({
            "vendor_id": "V20000",
            "topic": "Test Habit",
            "habit_description": "Test habit for T10",
            "action_to_take": "Test action",
            "rule_predicate": "grn_status",
            "source_timestamp": "Test Interview [00:00]",
            "captured_by": "Test User",
            "approver_id": "user_sandeep",
            "review_by_date": "2027-05-10"
        })
        assert card["status"] == "approved"
        assert card["review_by_date"] == "2027-05-10"
        # Verify it appears in graph
        facts = client.get_facts(subject="grn_status", predicate="grn_status")
        tacit_facts = [f for f in facts if f.get("source_type") == "expert_interview"]
        assert len(tacit_facts) > 0
        assert tacit_facts[0]["authority_rank"] == 3
```

---

## 2. Ragas Continuous Benchmark Metrics

| Ragas Metric | Target Score | Verification Purpose |
|---|---:|---|
| **Faithfulness** | $\ge 0.95$ | Every claim in answer traces to retrieved passage — zero hallucination. |
| **Answer Relevance** | $\ge 0.95$ | Direct, crisp answers tailored to processor exception context. |
| **Context Precision** | $\ge 0.90$ | Graph subgraphs return exact claims without text noise. |
| **Harmfulness / Safety** | $0.00$ | 100% PII regex masking (PAN, bank accounts) under DPDP Act. |

### 2.1 Ragas Evaluation Runner

```python
# tests/eval/test_ragas_eval.py
import pytest
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, harmfulness
from datasets import Dataset
from tests.fixtures.meridian_client import MeridianTestClient

@pytest.fixture(scope="session")
def eval_dataset() -> Dataset:
    """Load 160 gold questions from Excel."""
    import pandas as pd
    df = pd.read_excel("tests/fixtures/meridian_eval.xlsx", sheet_name="gold_questions")
    return Dataset.from_pandas(df)

def test_ragas_benchmarks(eval_dataset, client: MeridianTestClient):
    """Run full Ragas evaluation on 160 questions."""
    
    # Generate answers
    results = []
    for row in eval_dataset:
        res = client.ask(
            query=row["question"],
            client_desk=row.get("client_desk", "ALL"),
            as_of_date=row.get("as_of_date", "2026-08-01")
        )
        results.append({
            "question": row["question"],
            "answer": res["answer_markdown"],
            "contexts": [c["quote"] for c in res["citations"]],
            "ground_truth": row["expected_answer"]
        })
    
    # Evaluate
    dataset = Dataset.from_list(results)
    scores = evaluate(dataset, metrics=[faithfulness, answer_relevancy, context_precision, harmfulness])
    
    # Assert targets
    assert scores["faithfulness"] >= 0.95, f"Faithfulness: {scores['faithfulness']:.3f} < 0.95"
    assert scores["answer_relevancy"] >= 0.95, f"Answer Relevance: {scores['answer_relevancy']:.3f} < 0.95"
    assert scores["context_precision"] >= 0.90, f"Context Precision: {scores['context_precision']:.3f} < 0.90"
    assert scores["harmfulness"] == 0.00, f"Harmfulness: {scores['harmfulness']:.3f} > 0.00"
    
    # Log for tracking
    print(f"RAGAS SCORES: Faithfulness={scores['faithfulness']:.3f}, "
          f"Relevance={scores['answer_relevancy']:.3f}, "
          f"Precision={scores['context_precision']:.3f}, "
          f"Harmfulness={scores['harmfulness']:.3f}")
```

---

## 3. Additional Meridian-Specific Metrics

| Metric | Target | Measurement |
|---|---:|---|
| **Answer Accuracy** | $\ge 95\%$ (152/160) | Exact match on decision + numbers vs gold |
| **Citation Accuracy** | $\ge 90\%$ (144/160) | Every cited passage actually supports the claim |
| **Outdated Answers** | $< 5\%$ | No superseded rule returned as current |
| **Escalation Rate (Supported)** | $0\%$ | When passages removed, 100% escalate |
| **Conflict Recall** | $\ge 12/15$ | Planted conflicts detected |

```python
# tests/eval/test_meridian_metrics.py
def test_meridian_metrics(eval_dataset, client):
    """Meridian-specific metrics beyond Ragas."""
    correct = 0
    citation_ok = 0
    outdated = 0
    escalated_when_empty = 0
    
    for row in eval_dataset:
        res = client.ask(row["question"], client_desk=row.get("client_desk"), as_of_date=row.get("as_of_date"))
        
        # Answer accuracy
        if _answers_match(res, row["expected_answer"]):
            correct += 1
        
        # Citation accuracy
        if _citations_valid(res):
            citation_ok += 1
        
        # Outdated check
        if _has_outdated_citation(res):
            outdated += 1
        
        # Escalation when no support
        if row.get("remove_passages") and res["status"] in ("ESCALATED", "ABSTAIN"):
            escalated_when_empty += 1
    
    total = len(eval_dataset)
    assert correct / total >= 0.95, f"Answer Accuracy: {correct}/{total} = {correct/total:.2%}"
    assert citation_ok / total >= 0.90, f"Citation Accuracy: {citation_ok}/{total} = {citation_ok/total:.2%}"
    assert outdated / total < 0.05, f"Outdated Rate: {outdated}/{total} = {outdated/total:.2%}"
    # Escalation tested in T8 + dedicated test
```

---

## 4. Generality Proof Tests (Arnav's Platform Requirement)

**These prove the engine is a GENERIC PLATFORM, not Meridian-specific.**

### 4.1 Second Company Test (No Code Changes)

```python
# tests/generality/test_second_company.py
import pytest
from tests.fixtures.meridian_client import MeridianTestClient

@pytest.fixture(scope="session")
def second_company_client() -> MeridianTestClient:
    """Client for second company tenant (e.g., 'acme-corp')."""
    return MeridianTestClient(base_url="http://localhost:8000/v1", tenant="acme-corp")

def test_second_company_no_code_changes(second_company_client):
    """Load second company's docs, answer 10 questions — NO CODE CHANGES."""
    # 1. Ingest second company corpus (different domain: HR, Legal, etc.)
    second_company_client.upload_corpus("tests/fixtures/second_company/")
    
    # 2. Wait for ingestion
    second_company_client.wait_for_ingestion()
    
    # 3. Answer 10 gold questions
    gold = second_company_client.load_gold("tests/fixtures/second_company/gold_questions.json")
    correct = 0
    for q in gold:
        res = second_company_client.ask(q["question"], as_of_date=q.get("as_of_date"))
        if _answers_match(res, q["expected_answer"]):
            correct += 1
    
    assert correct >= 10, f"Second company: {correct}/10 questions answered correctly"
```

### 4.2 Format Ablation Test

```python
# tests/generality/test_format_ablation.py
def test_same_sop_different_formats(client):
    """Same SOP content in PDF, MD, HTML, XLSX, Email → Facts match ≥0.9 similarity."""
    from difflib import SequenceMatcher
    
    base_facts = client.ingest_and_extract("tests/fixtures/format_ablation/SOP_v4.0.docx")
    
    for fmt in ["pdf", "md", "html", "xlsx", "eml"]:
        test_facts = client.ingest_and_extract(f"tests/fixtures/format_ablation/SOP_v4.0.{fmt}")
        similarity = _fact_set_similarity(base_facts, test_facts)
        assert similarity >= 0.9, f"Format {fmt}: similarity {similarity:.2f} < 0.9"
```

### 4.3 Temporal Replay Test

```python
# tests/generality/test_temporal_replay.py
def test_temporal_replay(client):
    """Ingest documents in date order → Every as-of question returns correct value."""
    # Ingest in chronological order: SOP v3.1 → FAQ 2023 → SOP v4.0 → CMs → Interviews
    client.ingest_chronological("tests/fixtures/meridian_chronological/")
    
    # Query at different as_of dates
    test_cases = [
        {"as_of": "2023-10-01", "predicate": "price_tolerance", "expected": {"pct": 0.02, "cap": 1000}},
        {"as_of": "2024-06-01", "predicate": "price_tolerance", "expected": {"pct": 0.02, "cap": 1000}},
        {"as_of": "2026-04-01", "predicate": "price_tolerance", "expected": {"pct": 0.01, "cap": 500}},
        {"as_of": "2026-08-01", "predicate": "e_invoice_threshold", "expected": 50000000},
    ]
    
    for tc in test_cases:
        fact = client.get_fact("price_tolerance", "price_tolerance", as_of_date=tc["as_of"])
        assert fact["object_value"] == tc["expected"], f"As-of {tc['as_of']}: got {fact['object_value']}, expected {tc['expected']}"
```

### 4.4 Ablation Study (Layer Contribution)

```python
# tests/generality/test_ablation.py
def test_ablation_study(client):
    """Compare: Vector Only vs +Graph vs Full System — Gain visible per layer."""
    from tests.fixtures.ablation_client import AblationTestClient
    
    # Same 50 questions, 3 configurations
    questions = client.load_ablation_questions()
    
    configs = {
        "vector_only": AblationTestClient(mode="vector_only"),
        "vector_plus_graph": AblationTestClient(mode="vector_plus_graph"),
        "full_system": AblationTestClient(mode="full")
    }
    
    results = {}
    for name, c in configs.items():
        correct = sum(1 for q in questions if _answers_match(c.ask(q), q["expected"]))
        results[name] = correct / len(questions)
    
    # Each layer should add value
    assert results["full_system"] >= results["vector_plus_graph"] >= results["vector_only"]
    assert results["full_system"] - results["vector_only"] >= 0.15  # 15% gain from full system
    
    print(f"ABLATION: Vector={results['vector_only']:.1%}, +Graph={results['vector_plus_graph']:.1%}, Full={results['full_system']:.1%}")
```

---

## 5. Live Capture Tests (Phase 5+)

```python
# tests/live_capture/test_connectors.py
import pytest
from unittest.mock import AsyncMock, patch

class TestLiveConnectors:
    """Test live source ingestion pipelines."""

    @pytest.mark.asyncio
    async def test_email_webhook_ingestion(self, client):
        """Email webhook → Episode → Blocks → Facts."""
        with patch("app.core.ingestion.extractor.extract_facts") as mock_extract:
            mock_extract.return_value = [
                {"subject": "policy:price_tolerance", "predicate": "price_tolerance", "value": {"pct": 0.015, "cap": 750}}
            ]
            
            # Simulate email webhook
            await client.post("/episodes/email/webhook", json={
                "message_id": "test_msg_001",
                "from": "client@arvana.com",
                "subject": "Price tolerance update",
                "body": "New price tolerance is 1.5% capped at ₹750.",
                "received_at": "2026-11-10T10:00:00Z"
            })
            
            # Verify fact created
            fact = client.get_fact("price_tolerance", "price_tolerance", as_of_date="2026-11-10")
            assert fact["object_value"] == {"pct": 0.015, "cap": 750}

    @pytest.mark.asyncio
    async def test_meeting_bot_transcription(self, client):
        """Meeting bot → Transcript → Diarized turns → Candidate facts."""
        with patch("app.core.live_capture.transcriber.transcribe") as mock_transcribe:
            mock_transcribe.return_value = [
                {"speaker": "Client VP", "text": "Change process to 2 steps", "start": 300, "end": 310}
            ]
            
            # Start meeting
            meeting = await client.post("/episodes/meeting/start", json={
                "platform": "teams",
                "meeting_url": "https://teams.microsoft.com/test",
                "record": True,
                "transcribe": True,
                "diarize": True
            })
            
            # Verify candidate fact generated
            candidate = client.get_candidate_facts(meeting["meeting_id"])
            assert len(candidate) > 0
            assert candidate[0]["authority_weight"] > 0.8  # Client VP = high authority
```

---

## 6. Delivery Layer Tests (Phase 6+)

```python
# tests/delivery/test_erp_embed.py
def test_erp_embed_context(client):
    """ERP embed returns contextual widget for current invoice."""
    res = client.post("/delivery/erp/embed", json={
        "invoice_id": "INV-2026-0042",
        "vendor_id": "V20000",
        "client_desk": "Arvana Infra",
        "exception_codes": ["PRICE_VAR"],
        "context": {"po_line_val": 197500, "po_unit_price": 395, "inv_unit_price": 400, "inv_qty": 500}
    })
    
    assert "widget_html" in res
    assert "PRICE_VAR" in res["widget_html"]
    assert "answer_id" in res
    assert len(res["actions"]) > 0
```

---

## 7. SOP Sync Tests (Phase 7+)

```python
# tests/sop_sync/test_sync.py
def test_sop_sync_generates_redline(client):
    """Graph change → Redline document with tracked changes."""
    # 1. Create a fact change
    client.upsert_fact({
        "subject": "price_tolerance",
        "predicate": "price_tolerance",
        "value": {"pct": 0.015, "cap": 750},
        "valid_from": "2026-11-15"
    })
    
    # 2. Generate redline
    redline = client.post("/sop/sync/generate-redline", json={
        "target_document": "SOP_v4.0.docx",
        "changes": ["price_tolerance_update"]
    })
    
    # 3. Verify redline contains change
    assert "1.5%" in redline.text
    assert "750" in redline.text
    assert "500" in redline.text  # Old value shown as deleted
```

---

## 8. Test Fixtures & Helpers

### 8.1 Test Client (`tests/fixtures/meridian_client.py`)

```python
import httpx
from typing import Dict, Any, List, Optional

class MeridianTestClient:
    def __init__(self, base_url: str, tenant: str, token: str = None):
        self.base_url = base_url
        self.tenant = tenant
        self.headers = {
            "X-Tenant-Slug": tenant,
            "Authorization": f"Bearer {token}" if token else ""
        }
        self.client = httpx.AsyncClient(base_url=base_url, headers=self.headers, timeout=60.0)
    
    async def ask(self, query: str, client_desk: str = "ALL", as_of_date: str = None, **kwargs) -> Dict[str, Any]:
        payload = {"query_text": query, "client_desk": client_desk}
        if as_of_date:
            payload["as_of_date"] = as_of_date
        payload.update(kwargs)
        res = await self.client.post("/query/ask", json=payload)
        res.raise_for_status()
        return res.json()
    
    async def upload_corpus(self, path: str):
        # Upload all files in directory
        pass
    
    async def wait_for_ingestion(self):
        # Poll job status
        pass
    
    def get_fact(self, subject: str, predicate: str, as_of_date: str = None) -> Dict[str, Any]:
        params = {"subject": subject, "predicate": predicate}
        if as_of_date:
            params["as_of"] = as_of_date
        res = self.client.get("/facts", params=params)
        res.raise_for_status()
        return res.json()["facts"][0] if res.json()["facts"] else None
    
    # ... other helper methods
```

### 8.2 Similarity Helpers

```python
# tests/helpers/similarity.py
from difflib import SequenceMatcher

def _fact_set_similarity(facts1: List[Dict], facts2: List[Dict]) -> float:
    """Compare two fact sets by predicate+value similarity."""
    matched = 0
    for f1 in facts1:
        for f2 in facts2:
            if f1["predicate"] == f2["predicate"]:
                sim = SequenceMatcher(None, str(f1["value"]), str(f2["value"])).ratio()
                if sim > 0.9:
                    matched += 1
                    break
    return matched / max(len(facts1), 1)

def _answers_match(res: Dict, expected: str) -> bool:
    """Flexible answer matching for evaluation."""
    # Extract decision + numbers from both, compare
    pass

def _citations_valid(res: Dict) -> bool:
    """Verify every citation quote exists in retrieved passage."""
    pass

def _has_outdated_citation(res: Dict) -> bool:
    """Check if any citation references superseded source as current."""
    pass
```

---

## 9. Running the Full Suite

```bash
# Unit tests (fast)
pytest tests/unit -v

# Acceptance tests (T1-T10)
pytest tests/acceptance/test_t1_t10.py -v

# Meridian metrics (160 questions)
pytest tests/eval/test_meridian_metrics.py -v

# Ragas benchmarks
pytest tests/eval/test_ragas_eval.py -v

# Generality proofs
pytest tests/generality -v

# Live capture (with mocks)
pytest tests/live_capture -v

# Delivery & SOP sync
pytest tests/delivery tests/sop_sync -v

# Full CI suite (nightly)
pytest --cov=app --cov-report=html
```

---

## 10. Success Criteria Summary

| Test Category | Tests | Must Pass |
|---|---|---|
| **T1-T10 Acceptance** | 10 | 10/10 |
| **160-Q Answer Accuracy** | 160 | ≥152 (95%) |
| **Citation Accuracy** | 160 | ≥144 (90%) |
| **Outdated Rate** | 160 | <8 (5%) |
| **Ragas Faithfulness** | 160 | ≥0.95 |
| **Ragas Answer Relevance** | 160 | ≥0.95 |
| **Ragas Context Precision** | 160 | ≥0.90 |
| **Ragas Harmfulness** | 160 | 0.00 |
| **Conflict Recall** | 15 planted | ≥12 |
| **Second Company** | 10 Qs | 10/10 |
| **Format Ablation** | 5 formats | All ≥0.9 |
| **Temporal Replay** | 4 as-of dates | 4/4 |
| **Ablation Gain** | 3 configs | Full > Vector+15% |