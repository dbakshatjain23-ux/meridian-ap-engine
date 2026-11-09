# MERIDIAN SHARED SERVICES · ENTERPRISE KNOWLEDGE ENGINE
## OpenAPI 3.0 REST & WebSocket API Specification
**Document ID**: `Meridian_AP_API_SPECIFICATION.md`  
**Target Environment**: **FastAPI on Render (Docker)** — Single Public URL  
**Base URL**: `https://api.meridian-engine.com/v1`  
**Authentication**: Bearer Token (JWT) + Tenant Header (`X-Tenant-Slug`)  

---

## 1. Core Query Endpoints

### 1.1 `POST /query/ask` — Processor Query Endpoint
Executes the 3-Lane pipeline for processor questions and invoice exceptions.

**Request**:
```json
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
  },
  "stream": false
}
```

**Response (200 OK)**:
```json
{
  "execution_lane": "COMPUTABLE",
  "status": "PRICE_VAR",
  "answer_markdown": "**PRICE VARIANCE EXCEPTION**: Invoice unit price ₹400 exceeds PO price ₹395 by ₹2,500 total. The allowed tolerance is ₹500 (lower of 1% line value ₹1,975 and ₹500 cap under SOP v4.0 §4.2).",
  "math_result": {
    "total_excess": 2500.00,
    "allowed_tolerance": 500.00,
    "decision": "RAISE_EXCEPTION",
    "params_used": {"pct": 0.01, "cap": 500}
  },
  "citations": [
    {
      "block_id": "blk_abc123",
      "source": "SOP v4.0",
      "section": "§4.2",
      "valid_from": "2026-04-01",
      "quote": "The tolerance is the lower of 1% of the PO line value and ₹500."
    }
  ],
  "practice_notes": [],
  "older_sources": [
    {
      "source": "SOP v3.1 §3",
      "valid_from": "2023-07-01",
      "valid_to": "2026-03-31",
      "note": "Tolerance was 2% or ₹1,000. Superseded by SOP v4.0."
    }
  ],
  "verifier_result": {
    "passed": true,
    "checks": {
      "citations_real": true,
      "numbers_sourced": true,
      "no_superseded": true,
      "sentences_supported": true
    }
  },
  "response_time_ms": 1450
}
```

**Response — Escalated (200 OK)**:
```json
{
  "execution_lane": "LOOKUP",
  "status": "ESCALATED",
  "answer_markdown": "I don't have enough information to answer this confidently. This has been escalated to the Process Owner.",
  "escalation": {
    "reason": "RETRIEVAL_GATE_FAILED",
    "detail": "Best evidence score below threshold (0.42 < 0.65)",
    "escalated_to": "Sandeep Rao",
    "ticket_id": "esc_xyz789"
  },
  "citations": [],
  "verifier_result": {
    "passed": false,
    "checks": {
      "citations_real": true,
      "numbers_sourced": true,
      "no_superseded": true,
      "sentences_supported": false
    }
  }
}
```

**Response — Refused (200 OK)**:
```json
{
  "execution_lane": "REFUSED",
  "status": "OUT_OF_SCOPE",
  "answer_markdown": "This question is outside the scope of the knowledge base. Please contact Sandeep Rao (Process Excellence).",
  "refusal_reason": "SCOPE_GUARD: Query about canteen subsidy policy not covered in any document."
}
```

---

### 1.2 `GET /query/ask/stream` — Streaming Query (WebSocket)
For real-time answer generation with progressive citations.

**Connection**: `wss://api.meridian-engine.com/v1/query/ask/stream?token=<jwt>`

**Client → Server**:
```json
{
  "type": "query",
  "payload": { /* same as POST /query/ask */ }
}
```

**Server → Client** (Multiple Messages):
```json
{"type": "lane", "lane": "COMPUTABLE"}
{"type": "citation", "citation": {...}}
{"type": "math_result", "result": {...}}
{"type": "answer_chunk", "text": "**PRICE VARIANCE**..."}
{"type": "verifier", "result": {...}}
{"type": "complete", "answer_id": "ans_abc123"}
```

---

### 1.3 `POST /tacit/capture` — Tacit Knowledge Capture
Creates a new Expert Practice Fact with 6-month TTL.

**Request**:
```json
{
  "vendor_id": "V20000",
  "topic": "Infra GRN Batching",
  "habit_description": "Infra construction sites batch physical GRNs on Monday mornings.",
  "action_to_take": "Wait until Tuesday noon before chasing site engineer for NO_GRN hold.",
  "rule_predicate": "grn_status",
  "source_timestamp": "Interview 1 [02:30]",
  "captured_by": "Knowledge Team",
  "approver_id": "user_sandeep_rao",
  "review_by_date": "2027-03-31"
}
```

**Response (201 Created)**:
```json
{
  "fact_id": "fact_abc123",
  "status": "approved",
  "authority_rank": 3,
  "review_by_date": "2027-03-31",
  "message": "Practice card created and approved. Will appear side-by-side with NO_GRN rule."
}
```

---

### 1.4 `GET /tacit/list` — List Tacit Cards (Owner View)
```json
{
  "vendor_id": "V20000",
  "status": "approved",
  "expiring_within_days": 90
}
```

---

## 2. Ingestion Endpoints (Live Capture)

### 2.1 `POST /episodes/upload` — Document/File Upload
Ingest any document (PDF, Word, Excel, PPT, Email, Text).

**Request** (multipart/form-data):
```
file: <binary>
source_type: "document" | "email" | "upload"
metadata: {"client_desk": "Arvana Infra", "tags": ["sop", "v4.0"]}
```

**Response (202 Accepted)**:
```json
{
  "episode_id": "ep_abc123",
  "job_id": "job_xyz789",
  "status": "queued",
  "message": "Ingestion started. Check job status for completion."
}
```

---

### 2.2 `GET /episodes/{episode_id}/status` — Ingestion Status
```json
{
  "episode_id": "ep_abc123",
  "status": "completed",
  "blocks_extracted": 47,
  "facts_created": 23,
  "conflicts_detected": 2,
  "processing_time_ms": 12500
}
```

---

### 2.3 `POST /episodes/email/webhook` — Email Webhook (Microsoft Graph / IMAP)
Real-time email ingestion.

**Headers**: `X-Webhook-Signature: <hmac>`

**Request**:
```json
{
  "message_id": "msg_abc123",
  "from": "client@arvana.com",
  "to": ["ap@meridian.com"],
  "subject": "URGENT: Change in invoice processing for Pharma",
  "body": "Effective immediately, all excipient invoices require QA release...",
  "received_at": "2026-11-10T10:30:00Z",
  "attachments": [{"name": "memo.pdf", "content_type": "application/pdf"}]
}
```

---

### 2.4 `POST /episodes/teams/webhook` — Teams Message Webhook
Real-time Teams chat ingestion.

**Request**:
```json
{
  "message_id": "msg_xyz789",
  "channel_id": "ch_ap_exceptions",
  "from": {"id": "usr_lakshmi", "name": "Lakshmi Reddy", "role": "senior_processor"},
  "body": "Remember: Infra sites batch GRNs Monday. Wait until Tuesday noon.",
  "timestamp": "2026-11-10T10:30:00Z",
  "thread_id": "thread_abc",
  "reactions": [{"emoji": "👍", "count": 5}]
}
```

---

### 2.5 `POST /episodes/meeting/start` — Meeting Bot Join
Trigger meeting bot to join a call.

**Request**:
```json
{
  "platform": "teams" | "zoom" | "meet",
  "meeting_url": "https://teams.microsoft.com/l/meetup-join/...",
  "tenant_id": "meridian",
  "record": true,
  "transcribe": true,
  "diarize": true
}
```

**Response (202 Accepted)**:
```json
{
  "meeting_id": "mtg_abc123",
  "bot_id": "bot_xyz789",
  "status": "joining",
  "websocket_url": "wss://api.meridian-engine.com/v1/episodes/meeting/mtg_abc123/stream"
}
```

---

### 2.6 `GET /episodes/meeting/{meeting_id}/stream` — Meeting Live Stream (WebSocket)
Real-time transcription + diarization stream.

**Messages**:
```json
{"type": "transcript", "speaker": "Client VP", "text": "Change the process to 2 steps", "timestamp": "00:05:23", "confidence": 0.94}
{"type": "pii_redacted", "original": "PAN: ABCDE1234F", "redacted": "[REDACTED_PAN]"}
{"type": "candidate_fact", "subject": "policy:invoice_processing", "predicate": "steps", "value": "2", "authority_weight": 0.9}
```

---

### 2.7 `POST /episodes/drive/webhook` — Drive/SharePoint Change Webhook
Real-time document change notifications.

**Request**:
```json
{
  "change_type": "created" | "updated" | "deleted",
  "file_id": "file_abc123",
  "file_name": "SOP_v4.1.docx",
  "drive_id": "drive_meridian",
  "modified_by": "user_sandeep",
  "modified_at": "2026-11-10T10:30:00Z"
}
```

---

## 3. Graph Management Endpoints

### 3.1 `GET /facts` — Query Facts
```bash
GET /facts?subject=price_tolerance&predicate=price_tolerance&as_of=2026-08-01&client_desk=Arvana Infra
```

**Response**:
```json
{
  "facts": [
    {
      "fact_id": "fact_abc123",
      "subject": "price_tolerance",
      "predicate": "price_tolerance",
      "value": {"pct": 0.01, "cap": 500},
      "valid_from": "2026-04-01",
      "valid_to": null,
      "recorded_at": "2026-04-01T00:00:00Z",
      "retracted_at": null,
      "authority_rank": 2,
      "source_type": "sop_v4",
      "source_version": "v4.0",
      "status": "active"
    }
  ],
  "superseded": [
    {
      "fact_id": "fact_old456",
      "value": {"pct": 0.02, "cap": 1000},
      "valid_from": "2023-07-01",
      "valid_to": "2026-03-31",
      "retracted_at": "2026-04-01T00:00:00Z",
      "authority_rank": 4,
      "source_type": "sop_v3",
      "status": "superseded"
    }
  ]
}
```

---

### 3.2 `GET /facts/{fact_id}/history` — Temporal History (Both Clocks)
```json
{
  "fact_id": "fact_abc123",
  "valid_time_history": [
    {"valid_from": "2023-07-01", "valid_to": "2026-03-31", "value": {"pct": 0.02, "cap": 1000}},
    {"valid_from": "2026-04-01", "valid_to": null, "value": {"pct": 0.01, "cap": 500}}
  ],
  "transaction_time_history": [
    {"recorded_at": "2023-07-01", "retracted_at": "2026-04-01", "value": {"pct": 0.02, "cap": 1000}},
    {"recorded_at": "2026-04-01", "retracted_at": null, "value": {"pct": 0.01, "cap": 500}}
  ]
}
```

---

### 3.3 `GET /conflicts` — List Conflicts (Owner Dashboard)
```json
{
  "status": "open",
  "severity": "critical",
  "limit": 50
}
```

**Response**:
```json
{
  "conflicts": [
    {
      "conflict_id": "conf_abc123",
      "type": "direct_contradiction",
      "severity": "critical",
      "fact_1": {"fact_id": "fact_a", "value": {"pct": 0.01, "cap": 500}, "source": "SOP v4.0"},
      "fact_2": {"fact_id": "fact_b", "value": {"pct": 0.02, "cap": 1000}, "source": "FAQ 2023"},
      "detected_at": "2026-11-10T00:00:00Z",
      "status": "open"
    }
  ]
}
```

---

### 3.4 `POST /conflicts/{conflict_id}/resolve` — Resolve Conflict
```json
{
  "resolution": "fact_a_wins",
  "resolution_notes": "SOP v4.0 authority_rank=2 > FAQ authority_rank=4. FAQ marked superseded.",
  "resolved_by": "user_sandeep"
}
```

---

## 4. SOP Sync Endpoints

### 4.1 `GET /sop/sync/pending` — Pending Sync Changes
```json
{
  "pending_changes": [
    {
      "fact_id": "fact_new789",
      "action": "update",
      "predicate": "price_tolerance",
      "old_value": {"pct": 0.01, "cap": 500},
      "new_value": {"pct": 0.015, "cap": 750},
      "source": "meeting_mtg_abc123",
      "detected_at": "2026-11-10T10:30:00Z"
    }
  ]
}
```

---

### 4.2 `POST /sop/sync/generate-redline` — Generate Redline Document
```json
{
  "target_document": "SOP_v4.0.docx",
  "changes": ["fact_new789"],
  "output_format": "docx" | "pdf" | "html"
}
```

**Response**: Binary document download with tracked changes.

---

### 4.3 `POST /sop/sync/push` — Push to SharePoint/Git
```json
{
  "target": "sharepoint" | "github" | "gitlab",
  "document_id": "SOP_v4.0.docx",
  "redline_id": "redline_abc123",
  "commit_message": "Update price tolerance per client meeting 2026-11-10",
  "notify": ["user_sandeep", "user_imran"]
}
```

---

### 4.4 `GET /sop/sync/acknowledgements` — Track Acknowledgements
```json
{
  "sync_id": "sync_abc123",
  "acknowledged": [
    {"user_id": "user_sandeep", "acknowledged_at": "2026-11-10T11:00:00Z"},
    {"user_id": "user_imran", "acknowledged_at": "2026-11-10T11:15:00Z"}
  ],
  "pending": [
    {"user_id": "user_lakshmi", "deadline": "2026-11-12T10:00:00Z", "reminders_sent": 1}
  ]
}
```

---

## 5. Delivery & Notification Endpoints

### 5.1 `POST /delivery/erp/embed` — ERP Embed Context
Called by ERP iframe to get contextual answer for current invoice.

**Request**:
```json
{
  "invoice_id": "INV-2026-0042",
  "vendor_id": "V20000",
  "client_desk": "Arvana Infra",
  "exception_codes": ["PRICE_VAR", "NO_GRN"],
  "context": {"po_line_val": 197500, "inv_unit_price": 400, "po_unit_price": 395, "inv_qty": 500}
}
```

**Response**:
```json
{
  "widget_html": "<div class='meridian-widget'>...Answer Card...</div>",
  "answer_id": "ans_abc123",
  "actions": [
    {"label": "Accept & Post", "type": "erp_action", "payload": {"action": "post"}},
    {"label": "Raise Exception", "type": "erp_action", "payload": {"code": "PRICE_VAR"}}
  ]
}
```

---

### 5.2 `POST /delivery/teams/message` — Teams Bot Proactive Message
```json
{
  "user_id": "usr_junior_processor",
  "message": "Price variance detected on INV-2026-0042. Allowed: ₹500, Actual: ₹2,500. [View Details](https://app.meridian-engine.com/answer/ans_abc123)",
  "card_json": { /* Adaptive Card */ }
}
```

---

### 5.3 `POST /delivery/webhook/change` — Change Notification Webhook
Register webhooks for graph changes.

**Request** (Register):
```json
{
  "url": "https://client-system.com/webhook/meridian",
  "events": ["fact.created", "fact.superseded", "conflict.detected", "sop.sync"],
  "filter": {"client_desk": "Arvana Pharma"},
  "secret": "webhook_secret_xyz"
}
```

**Payload** (Delivered):
```json
{
  "event": "fact.superseded",
  "timestamp": "2026-11-10T10:30:00Z",
  "fact_id": "fact_old456",
  "new_fact_id": "fact_new789",
  "predicate": "price_tolerance",
  "change_summary": "Price tolerance cap changed from ₹500 to ₹750"
}
```

---

## 6. Admin & Evaluation Endpoints

### 6.1 `GET /admin/eval/run` — Run Evaluation Suite
```bash
GET /admin/eval/run?suite=acceptance_t1_t10
GET /admin/eval/run?suite=ragas_160
GET /admin/eval/run?suite=conflict_scan
GET /admin/eval/run?suite=generality_test
```

**Response**:
```json
{
  "run_id": "eval_abc123",
  "suite": "acceptance_t1_t10",
  "status": "running",
  "started_at": "2026-11-10T10:00:00Z"
}
```

---

### 6.2 `GET /admin/eval/{run_id}/results` — Evaluation Results
```json
{
  "run_id": "eval_abc123",
  "suite": "acceptance_t1_t10",
  "status": "completed",
  "results": {
    "T1": "PASS",
    "T2": "PASS",
    "T3": "PASS",
    "T4": "PASS",
    "T5": "PASS",
    "T6": "PASS",
    "T7": "PASS",
    "T8": "PASS",
    "T9": "PASS (13/15)",
    "T10": "PASS"
  },
  "metrics": {
    "answer_accuracy": 0.96,
    "citation_accuracy": 0.92,
    "outdated_rate": 0.02,
    "conflicts_found": 13
  }
}
```

---

### 6.3 `POST /admin/schema/mode` — Switch Schema Mode
```json
{
  "mode": "learned" | "baseline"
}
```

---

## 7. Error Responses

All endpoints return consistent error format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR" | "NOT_FOUND" | "UNAUTHORIZED" | "TENANT_MISMATCH" | "RATE_LIMITED" | "INTERNAL_ERROR",
    "message": "Human-readable description",
    "details": {},
    "request_id": "req_abc123"
  }
}
```

**HTTP Status Codes**:
- 200: Success
- 201: Created
- 202: Accepted (async job)
- 400: Validation Error
- 401: Unauthorized
- 403: Forbidden (tenant mismatch)
- 404: Not Found
- 422: Unprocessable Entity (business logic)
- 429: Rate Limited
- 500: Internal Error
- 503: Service Unavailable (worker queue full)

---

## 8. Rate Limits

| Tier | Requests/Minute | Burst |
|---|---|---|
| Free | 30 | 10 |
| Pro | 300 | 100 |
| Enterprise | 3000 | 1000 |

Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

---

## 9. Versioning

- **URL Versioning**: `/v1/`, `/v2/`
- **Breaking Changes**: New version
- **Non-Breaking**: Same version, additive fields
- **Deprecation**: 6-month notice via `Sunset` header