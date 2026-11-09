# MERIDIAN SHARED SERVICES · ENTERPRISE KNOWLEDGE ENGINE
## OpenAPI 3.0 REST & WebSocket API Specification
**Document ID**: `Meridian_AP_API_SPECIFICATION.md`  
**Target Environment**: Zoho Catalyst Serverless Node.js / Python Functions  

---

## 1. Core API Endpoints

### 1.1 `POST /api/v1/query/ask` — Processor Query Endpoint
Executes the 3-Lane pipeline for processor questions and invoice exceptions.

```json
// REQUEST BODY
{
  "query_text": "PO price is ₹395, invoice is ₹400 for 500 bags. Can I pass this line?",
  "client_desk": "Arvana Infra",
  "vendor_id": "V20000",
  "invoice_date": "2026-08-01",
  "as_of_date": "2026-08-05",
  "invoice_context": {
    "po_line_val": 197500.00,
    "po_unit_price": 395.00,
    "inv_unit_price": 400.00,
    "inv_qty": 500.0
  }
}

// RESPONSE BODY (200 OK)
{
  "execution_lane": "COMPUTABLE",
  "status": "PRICE_VAR",
  "answer_markdown": "**PRICE VARIANCE EXCEPTION**: Invoice unit price ₹400 exceeds PO price ₹395 by ₹2,500 total. The allowed tolerance is ₹500 (lower of 1% line value ₹1,975 and ₹500 cap under SOP v4.0 §4.2).",
  "math_result": {
    "total_excess": 2500.00,
    "allowed_tolerance": 500.00,
    "decision": "RAISE_EXCEPTION"
  },
  "citations": [
    {"source": "SOP v4.0", "section": "§4.2", "valid_from": "2026-04-01"}
  ],
  "practice_notes": [],
  "older_rule_note": "Note: Under superseded SOP v3.1 §3, tolerance was 2% or ₹1,000. That rule expired on 31 March 2026."
}
```

### 1.2 `POST /api/v1/tacit/capture` — Tacit Exit Capture Studio
Creates a new Vendor Habit Card with a 6-month TTL expiry date.

```json
// REQUEST BODY
{
  "vendor_id": "V20000",
  "topic": "Infra GRN Batching",
  "habit_description": "Infra construction sites batch physical GRNs on Monday mornings.",
  "action_to_take": "Wait until Tuesday noon before chasing site engineer for NO_GRN hold.",
  "rule_claim_id": "NO_GRN_HOLD.v40",
  "source_timestamp": "Interview 1 [02:30]",
  "captured_by": "Knowledge Team",
  "approver_name": "Sandeep Rao",
  "review_by_date": "2027-03-31"
}
```

### 1.3 `POST /api/v1/admin/provider-switch` — Multi-LLM Dynamic Switcher
Dynamically switches the underlying LLM provider.

```json
// REQUEST BODY
{
  "provider": "GEMINI", // Options: 'OPENAI', 'GEMINI', 'NEMOTRON', 'CLAUDE'
  "model_name": "gemini-1.5-pro"
}
```
