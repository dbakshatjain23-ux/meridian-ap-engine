# MERIDIAN AP KNOWLEDGE ENGINE — HYBRID UNIFIED SPECIFICATION
**Version:** 1.0 (Consolidated from 3 Sources + Gap Analysis)  
**Date:** November 10, 2026  
**Status:** FINAL — Ready for Implementation

---

## 1. SOURCE DOCUMENT MAP

| Source Document | Type | What We Take | What We Discard/Override |
|---|---|---|---|
| **PS-07 Brief** (EY Problem Statement) | Business Problem | Operational context, 9K invoices, 6 bottlenecks, 160 Q eval set, success metrics, guardrails | — |
| **Meeting Transcription** (Abhisshek Raaj, EY) | **True Problem Statement** | **General platform scope**, live sources (email, Teams, video, PDF), continuous capture, SOP sync, in-workflow delivery, ROI tiers, generality test | Specific Meridian-only implementation |
| **Arnav's "How Our Knowledge Engine Works"** | Platform Architecture | **Generic core + plug-in model**, dual-clock graph, 12-step pipeline, 7 guardrails, verifier, Postgres stack, background workers, any-format parsing, authority > recency, escalation loop | — |
| **Meridian_AP_PRD.md** | Case Study Requirements | 8 problem chunks (P1-P8), personas, functional reqs FR1-FR5, NFR targets (95% accuracy, <30s), ROI numbers | Zoho Catalyst deployment → **Override: Render/Vercel/Neon** |
| **Meridian_AP_SYSTEM_ARCHITECTURE.md** | Technical Architecture | 5-layer architecture, Multi-LLM adapter, Rules vs Practices, ConflictRAG details, Side-by-Side principle | Zep/Graphiti → **Override: Postgres native**, Catalyst → **Override: Render** |
| **Meridian_AP_DB_SCHEMA_AND_GRAPH.md** | Data Model | Claim Record schema, Practices table, Vendors, Invoices, OpenSPG ontology | Zep-specific → **Override: Dual-clock Postgres tables** |
| **Meridian_AP_CALCULATORS_AND_TRIAGE_SPEC.md** | Business Logic | **5 Calculators + classify_tds** (exact implementations), dynamic param loading from claim store | — |
| **Meridian_AP_API_SPECIFICATION.md** | API Contract | `/query/ask`, `/tacit/capture`, `/admin/provider-switch` schemas, response formats | — |
| **Meridian_AP_DEPLOYMENT_ZOHO_CATALYST.md** | Deployment (OLD) | Circuit names, cron schedules | **FULLY OVERRIDDEN** by Arnav's stack |
| **Meridian_AP_EVALUATION_AND_TESTING_SUITE.md** | Acceptance Tests | **T1-T10 exact test cases**, Ragas metrics (Faithfulness ≥0.95, etc.), 160 gold questions | — |
| **Meridian_AP_MASTER_PROMPT_GUIDE.md** | Build Instructions | Sub-task prompts A-D (calculators, LLM adapter, API, tests) | Catalyst-specific paths → **Override** |
| **Meridian_AP_STARTER_REPO_CONFIG.md** | Repo Structure (OLD) | Directory tree, file inventory | **FULLY OVERRIDDEN** by Arnav's stack |

---

## 2. UNIFIED ARCHITECTURE (Hybrid)

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                        LIVE CAPTURE LAYER (NEW — FROM ABHISHEK)                     │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐  │
│  │   Email     │  │   Teams     │  │  Meeting    │  │ Drive/      │  │  Upload   │  │
│  │ Connector   │  │    Bot      │  │    Bot      │  │ SharePoint  │  │    API    │  │
│  │ (IMAP/      │  │ (Live msg,  │  │ (Teams/     │  │  Watcher    │  │ (Ad-hoc   │  │
│  │  Graph API) │  │  webhook)   │  │  Zoom/Meet) │  │ (Graph API) │  │  PDFs)    │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬─────┘  │
│         │                │                │                │                │         │
│         └────────────────┴────────┬────────┴────────────────┴────────────────┘         │
│                                  ▼                                                         │
│                    ┌─────────────────────────┐                                           │
│                    │  LIVE PII REDACTION     │  (Audio + Text streams)                   │
│                    │  SPEAKER DIARIZATION    │  (Role + Tenure → Authority Weight)       │
│                    │  THREAD CONTEXT LINKING │  (Conversation → Candidate Claims)        │
│                    └───────────┬─────────────┘                                           │
└──────────────────────────────────│────────────────────────────────────────────────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│              UNIFIED INGESTION PIPELINE (ARNAV'S 12 STEPS — BACKGROUND WORKERS)     │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  STAGE 1: BUILD THE GRAPH                                                             │
│  ┌─────────┐ ┌─────────┐ ┌──────────────┐ ┌────────────┐ ┌────────────┐ ┌────────┐  │
│  │ Detect  │ │ Parse → │ │ Structure    │ │ Entity/    │ │ Fact       │ │ Source │  │
│  │ File    │ │ Unified │ │ Repair (AI   │ │ Topic      │ │ Extraction │ │ Auth   │  │
│  │ Type    │ │ Block   │ │ heading      │ │ Learning   │ │ + Dual     │ │ Ranking│  │
│  │(content)│ │ List    │ │ levels)      │ │ (owner     │ │ Clocks     │ │(type>  │  │
│  └────┬────┘ └────┬────┘ └──────┬───────┘ │ review once)│ │(valid/     │ │version>│  │
│       │         │         │         │         │         │ │ recorded/  │ │status) │  │
│       │         │         │         │         │         │ │ retracted) │ └────┬───┘  │
│       │         │         │         │         │         └──────┬───────┘        │
│       │         │         │         │                │        │                │
│       ▼         ▼         ▼         ▼                ▼        ▼                ▼
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │ CONFLICT RESOLUTION (4 CASES) → ATOMIC GRAPH WRITE (Close Old + Open New)   │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
│                                    │                                              │
│  STAGE 2: ANSWER QUESTIONS (FAST PATH)                                            │
│  ┌─────────┐ ┌─────────────────────┐ ┌─────────────┐ ┌─────────────────────────┐  │
│  │ Router  │ │ Hybrid Retrieval    │ │ Build       │ │ 4-Check Verifier        │  │
│  │(Calc/   │ │ (Keyword + Vector + │ │ Answer      │ │ (Citations real,        │  │
│  │ Lookup/ │ │  Graph Walk, RRF,   │ │ (Citations, │ │  Numbers sourced,       │  │
│  │ Judge)  │ │  Rerank, Top-6)     │ │  Calc, Old, │ │  No superseded,         │  │
│  └────┬────┘ └──────────┬──────────┘ │  Expert Tip)│ │  Sentence supported)    │  │
│       │                 │            └──────┬──────┘ └───────────┬────────────┘  │
│       │                 │                   │                    │                │
│       ▼                 ▼                   ▼                    ▼                ▼
│  ┌─────────────────────────────────────────────────────────────────────────────┐  │
│  │ SHOW ANSWER  OR  ESCALATE TO OWNER → OWNER APPROVES → BECOMES FACT (LIVE)   │  │
│  └─────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                    DELIVERY LAYER (NEW — FROM ABHISHEK'S "30 SEC AT POINT OF WORK") │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │  REST API   │ │  Teams App  │ │  ERP Embed  │ │ Browser Ext │ │ Webhooks    │   │
│  │  + WS       │ │  (In-chat)  │ │ (iframe/    │ │ (Any web    │ │ (Change     │   │
│  │             │ │             │ │  sidebar)   │ │  app)       │ │  notify)    │   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                   SOP SYNC LAYER (NEW — FROM ABHISHEK'S "PUT BACK TO SOP")          │
├─────────────────────────────────────────────────────────────────────────────────────┤
│  Graph Change Detection → Redline Generator → Push to SharePoint/Drive/Git         │
│  → Stakeholder Notification → Acknowledgement Tracking → Audit Trail               │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. CORE DATA MODEL (Dual-Clock Postgres Schema)

```sql
-- TENANTS (Multi-company from Day 1)
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- EPISODES (Raw inputs: documents, emails, meetings, chats)
CREATE TABLE episodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    source_type TEXT NOT NULL,           -- 'document' | 'email' | 'meeting' | 'chat' | 'upload'
    source_id TEXT NOT NULL,             -- Message ID, Document ID, Meeting ID
    source_metadata JSONB NOT NULL,      -- {from, to, subject, timestamp, participants, etc.}
    raw_content TEXT,                    -- Original text (PII-scrubbed version stored separately)
    content_hash TEXT NOT NULL,          -- For deduplication
    status TEXT DEFAULT 'pending',       -- 'pending' | 'processing' | 'completed' | 'failed'
    created_at TIMESTAMPTZ DEFAULT now(),
    processed_at TIMESTAMPTZ
);
CREATE INDEX idx_episodes_tenant ON episodes(tenant_id);
CREATE INDEX idx_episodes_source ON episodes(source_type, source_id);

-- BLOCKS (Parsed structural units: sections, table rows, transcript turns, slides)
CREATE TABLE blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    episode_id UUID REFERENCES episodes(id),
    tenant_id UUID REFERENCES tenants(id),
    block_type TEXT NOT NULL,            -- 'heading' | 'paragraph' | 'table_row' | 'transcript_turn' | 'slide'
    heading_path TEXT[],                 -- ['4', '2'] for §4.2
    heading_level INT,                   -- 1, 2, 3...
    content TEXT NOT NULL,
    metadata JSONB,                      -- {speaker, timestamp, row_data, etc.}
    char_start INT, char_end INT,        -- Position in episode for citation highlighting
    embedding VECTOR(384),               -- BGE-small embedding
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_blocks_tenant ON blocks(tenant_id);
CREATE INDEX idx_blocks_embedding ON blocks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_blocks_fts ON blocks USING gin (to_tsvector('english', content));

-- ENTITIES (Domain objects: Client, Vendor, Policy, Invoice, Regulation, Person)
CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    entity_type TEXT NOT NULL,           -- 'client' | 'vendor' | 'policy' | 'invoice' | 'regulation' | 'person'
    name TEXT NOT NULL,
    canonical_name TEXT,                 -- Normalized for matching
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX idx_entities_tenant_type_name ON entities(tenant_id, entity_type, canonical_name);

-- FACTS (The core knowledge: dual-clock temporal edges)
CREATE TABLE facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    subject_entity_id UUID REFERENCES entities(id),      -- e.g., Vendor V20000
    predicate TEXT NOT NULL,                              -- e.g., 'price_tolerance', 'tds_section', 'msme_category'
    object_value JSONB NOT NULL,                          -- Structured: {"pct": 0.01, "cap": 500} or "194J"
    object_type TEXT NOT NULL,                            -- 'json' | 'string' | 'number' | 'date' | 'boolean'
    
    -- VALID TIME (When true in the world)
    valid_from DATE NOT NULL,
    valid_to DATE,                                        -- NULL = currently true
    
    -- TRANSACTION TIME (When system learned/retracted)
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    retracted_at TIMESTAMPTZ,                             -- NULL = currently believed
    
    -- SOURCE & AUTHORITY
    source_episode_id UUID REFERENCES episodes(id),
    source_block_ids UUID[] NOT NULL,                     -- Supporting blocks
    source_type TEXT NOT NULL,                            -- 'client_memo' | 'sop' | 'desk_instruction' | 'faq' | 'expert_interview' | 'meeting' | 'email' | 'chat'
    source_version TEXT,                                  -- 'v4.0', 'v3.1', '2023-10-09'
    source_status TEXT NOT NULL,                          -- 'current' | 'superseded' | 'draft' | 'unreviewed'
    authority_rank INT NOT NULL,                          -- Lower = higher authority (1=Client Memo, 2=SOP v4.0, 3=DI, 4=Tacit, 5=Superseded)
    
    -- CONFIDENCE & GOVERNANCE
    confidence FLOAT DEFAULT 1.0,                         -- Extraction confidence
    status TEXT DEFAULT 'active',                         -- 'active' | 'superseded' | 'retracted' | 'conflict' | 'pending_review'
    approved_by UUID,                                     -- Owner who approved
    approved_at TIMESTAMPTZ,
    review_by_date DATE,                                  -- For tacit cards (6-month TTL)
    
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_facts_tenant ON facts(tenant_id);
CREATE INDEX idx_facts_subject_predicate ON facts(subject_entity_id, predicate);
CREATE INDEX idx_facts_valid_time ON facts(valid_from, valid_to);
CREATE INDEX idx_facts_txn_time ON facts(recorded_at, retracted_at);
CREATE INDEX idx_facts_authority ON facts(authority_rank);

-- CONFLICTS (Detected contradictions for owner review)
CREATE TABLE conflicts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    fact_id_1 UUID REFERENCES facts(id),
    fact_id_2 UUID REFERENCES facts(id),
    conflict_type TEXT NOT NULL,                          -- 'direct_contradiction' | 'parameter_drift' | 'scope_overlap' | 'authority_clash'
    severity TEXT NOT NULL,                               -- 'critical' | 'high' | 'medium' | 'low'
    status TEXT DEFAULT 'open',                           -- 'open' | 'resolved' | 'dismissed'
    resolution_notes TEXT,
    resolved_by UUID,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- JOBS (Background worker queue)
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    job_type TEXT NOT NULL,                               -- 'ingest' | 'extract' | 'conflict_scan' | 'sop_sync' | 'notification'
    payload JSONB NOT NULL,
    status TEXT DEFAULT 'queued',                         -- 'queued' | 'running' | 'completed' | 'failed' | 'retrying'
    attempts INT DEFAULT 0,
    max_attempts INT DEFAULT 3,
    error TEXT,
    scheduled_for TIMESTAMPTZ DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_jobs_tenant_status ON jobs(tenant_id, status, scheduled_for)
WHERE status IN ('queued', 'retrying');

-- ANSWER LOG (Audit trail for every query)
CREATE TABLE answer_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    query_text TEXT NOT NULL,
    client_desk TEXT,
    as_of_date DATE,
    route TEXT NOT NULL,                                  -- 'computable' | 'lookup' | 'judgment' | 'escalated' | 'refused'
    answer_markdown TEXT,
    citations JSONB,                                      -- [{block_id, quote, fact_ids}]
    calculator_outputs JSONB,
    verifier_result JSONB,                                -- {passed: bool, checks: {...}}
    escalated BOOLEAN DEFAULT false,
    escalation_reason TEXT,
    response_time_ms INT,
    created_at TIMESTAMPTZ DEFAULT now()
);
```

---

## 4. MERIDIAN AP PLUG-IN (First Industry Module)

### 4.1 Calculators (Read Params from Graph — NOT Hardcoded)

```python
# All calculators query facts table for current parameters
# Example: price_tolerance fact for client_desk + as_of_date
# Returns: {"pct": 0.01, "cap": 500}  (SOP v4.0) or {"pct": 0.02, "cap": 1000} (v3.1)

CALCULATORS = {
    "calculate_price_variance": {
        "params": ["price_tolerance.pct", "price_tolerance.cap"],
        "inputs": ["po_line_val", "po_unit_price", "inv_unit_price", "inv_qty", "client_desk", "as_of_date"],
        "output": {"status": "PASS|PRICE_VAR", "total_excess", "allowed_tolerance", "governing_limit"}
    },
    "classify_tds": {
        "params": [],  # Pure classification logic
        "inputs": ["payment_description", "vendor_category", "has_amc", "is_mixed_service"],
        "output": {"section_code": "194C|194J_2|194J_10|194I|194Q|TDS_SECTION_UNCLEAR", "rationale"}
    },
    "calculate_tds": {
        "params": ["tds_rates.194C", "tds_rates.194J_2", ...],  # From graph
        "inputs": ["taxable_value_inr", "gst_inr", "section_code", "is_corporate", "pan_available", "as_of_date"],
        "output": {"tds_amount", "applied_rate_pct", "taxable_base", "pan_penalty_applied"}
    },
    "calculate_msme_due_date": {
        "params": ["msme_caps.micro", "msme_caps.small", "payment_run_days"],  # From graph
        "inputs": ["invoice_date", "acceptance_date", "vendor_id", "agreement_days", "as_of_date"],
        "output": {"effective_credit_days", "due_date", "scheduled_payment_run", "statutory_capped"}
    },
    "validate_e_invoice_requirement": {
        "params": ["e_invoice_threshold"],  # ₹5 Cr from graph
        "inputs": ["vendor_id", "invoice_total_inr", "as_of_date"],
        "output": {"required": bool, "threshold", "vendor_aato_band"}
    },
    "normalize_supplier_string": {
        "params": [],  # Pure string logic
        "inputs": ["invoice_num_str"],
        "output": {"normalized"}
    }
}
```

### 4.2 Entities & Predicates (Meridian AP Ontology)

| Entity Type | Examples | Key Predicates |
|---|---|---|
| `client` | Arvana Infra, Arvana Pharma, Arvana Retail | — |
| `vendor` | V20000 Balaji Logistics | `msme_category`, `aato_band`, `pan_available`, `qrmp_filer`, `habit_note` |
| `policy` | Price Tolerance, TDS Section, MSME Due Date, E-Invoice, Approval Hierarchy | `price_tolerance`, `tds_section`, `tds_rate`, `msme_cap`, `e_invoice_threshold`, `approval_limit` |
| `invoice` | INV-2026-0042 | `price_variance`, `tds_section`, `msme_due_date`, `grn_status`, `exception_code` |
| `regulation` | GST Act, Income Tax Act, MSMED Act | `section`, `rate`, `threshold` |
| `person` | Lakshmi Reddy, Imran Qureshi, Sandeep Rao | `role`, `tenure`, `expertise_areas` |

### 4.3 Authority Ranking (Meridian AP Specific)

| Rank | Source Type | Examples |
|---|---|---|
| 1 | Client Memo | CM-INF-02, CM-PHA-01, CM-RET-03 |
| 2 | SOP v4.0 / Desk Instruction | SOP v4.0 §4.2, DI-03, DI-07 |
| 3 | Tacit Practice (Approved) | Lakshmi's GRN wait, Transporter /A suffix |
| 4 | Superseded | SOP v3.1, FAQ Oct 2023 |
| 5 | General Knowledge | Training videos (pre-2026) |

### 4.4 Side-by-Side Rules (Test T4)

```json
{
  "query": "Infra invoice received Saturday with no GRN. Chase site engineer Monday?",
  "client_desk": "Arvana Infra",
  "as_of_date": "2026-08-05",
  "answer": {
    "rule": {
      "claim": "Hold as NO_GRN. System reminds after 2 working days, escalates after 5.",
      "source": "SOP v4.0 §4.6",
      "authority": 2,
      "valid_from": "2026-04-01"
    },
    "practice": {
      "claim": "Infra sites batch GRNs Monday morning. Wait until Tuesday noon before chasing.",
      "source": "Expert Interview 1 [02:30] & [05:18]",
      "authority": 3,
      "status": "approved",
      "review_by": "2027-03-31",
      "approved_by": "Sandeep Rao"
    },
    "presentation": "SIDE_BY_SIDE",
    "note": "Practice sits beside rule as annotation. Does not override control hierarchy."
  }
}
```

---

## 5. ACCEPTANCE TESTS (From Meridian Specs — MUST PASS)

| Test | Scenario | Expected | Source |
|---|---|---|---|
| **T1** | Price tolerance query | "Lower of 1% or ₹500 (SOP v4.0 §4.2); notes superseded 2%/₹1,000" | PRD, Eval Set |
| **T2** | ₹8.9 Cr vendor without IRN | Rejects under ₹5 Cr threshold; rejects obsolete ₹10 Cr rule | PRD, Eval Set |
| **T3** | Pharma excipient QA release | Requires QA release per CM-PHA-01; flags 2023 FAQ error | PRD, Eval Set |
| **T4** | Saturday Infra no GRN | SOP v4.0 §4.6 hold rule SIDE-BY-SIDE with Lakshmi Tuesday-noon practice | PRD, Eval Set |
| **T5** | PO ₹395, Invoice ₹400 (500 bags) | Excess ₹2,500 vs limit ₹500 → PRICE_VAR | PRD, Eval Set |
| **T6** | TDS on software ₹4.8L + GST | 194J @ 2% = ₹9,600 (excludes GST) | PRD, Eval Set |
| **T7** | Micro supplier accepted 1 Aug | Due 16 Aug (15d cap) → Friday 14 Aug payment run | PRD, Eval Set |
| **T8** | Canteen subsidy (out of corpus) | ABSTAINS → routes to Sandeep Rao | PRD, Eval Set |
| **T9** | Corpus-wide conflict scan | Detects ≥12 of 15 planted conflicts | PRD, Eval Set |
| **T10** | Tacit capture card TTL | Creates habit cards with mandatory 6-month review date | PRD, Eval Set |

**Ragas Targets:** Faithfulness ≥0.95, Answer Relevance ≥0.95, Context Precision ≥0.90, Harmfulness = 0.00

---

## 6. GAP ANALYSIS — WHAT'S MISSING FROM ABHISHEK'S PROBLEM

### 6.1 LIVE SOURCE CONNECTORS (Critical — #1 Gap)

| Source | Abhisshek Quote | Current Status | Build Priority |
|---|---|---|---|
| **Email** | "You can get such changes on your email... few lines written on email" | ❌ No IMAP/Gmail/Graph connector | **P0** |
| **Teams Chat** | "Teams chat... multiple sources of input" | ❌ Only historical JSON export in docs | **P0** |
| **Meeting/Video Calls** | "Client will tell us and show us exactly how a process will run... over video call" | ❌ No meeting bot, no live transcription | **P0** |
| **SharePoint/Drive** | "Centralized folder, a SharePoint, wherein only managers can access it" | ❌ No watched folder / Graph API | **P1** |
| **Ad-hoc PDF Upload** | "Some PDF document that they'll send you" | ✅ Parser exists, needs upload API | **P1** |

**Missing Infrastructure:**
- Speaker diarization + authority weighting (Client VP > Internal Junior)
- Live PII redaction for audio streams
- Conversation thread context linking (email chains, Teams threads)
- Real-time claim candidate extraction from streams

### 6.2 CHANGE DETECTION & SOP SYNC (Critical — "Put Back to SOP")

| Requirement | Abhisshek Quote | Current Status | Build Priority |
|---|---|---|---|
| **Write-back to SOP** | "Collate all these information, these changes, put that back to the SOP" | ❌ Read-only graph | **P0** |
| **Version Control** | "SOP was updated, but nobody kept a track of the version control" | ⚠️ Graph has versions, no document versioning | **P1** |
| **Change Notifications** | "How everyone will get to know if they are referring to the latest one" | 📋 Listed as "After MVP" in Arnav | **P1** |
| **Acknowledgement Tracking** | "Ensure that everyone is following the same document" | ❌ No ack system | **P1** |

### 6.3 IN-WORKFLOW DELIVERY (Critical — "30 Seconds at Point of Work")

| Requirement | Abhisshek Quote | Current Status | Build Priority |
|---|---|---|---|
| **ERP Embed** | "I as an agent... should be able to just do my work... matter of five or ten seconds" | ❌ Only API endpoint | **P0** |
| **Teams App** | "Teams chat... how everyone will get to know" | ❌ No Teams app/bot for answers | **P0** |
| **Browser Extension** | Universal "any web app" delivery | ❌ Not designed | **P1** |
| **Contextual Injection** | "I will not read the entire 60 page... go to that specific chapter" | ✅ Retrieval works, no delivery | **P0** |

### 6.4 GOVERNANCE FOR LIVE SOURCES

| Gap | Why Critical |
|---|---|
| **Speaker Authority in Calls** | "Client explained on video call" — need to weight Client VP > Internal Junior |
| **Email Thread Understanding** | "Few lines written on email" buried in thread — need thread summarization |
| **Live PII Redaction** | Audio/video contains PAN, bank details — must redact BEFORE graph ingestion |
| **Source Provenance Chain** | "Lakshmi said in meeting" vs "SOP v4.0 §4.2" — different authority, different TTL |

### 6.5 GENERALITY PROOF (Arnav's "Second Company Test")

| Test | Target | Status |
|---|---|---|
| Second unrelated company docs, no code changes | 10/10 questions answered with citations | ❌ No test corpus |
| Same SOP in other formats (PDF, MD, HTML, XLSX, email) | Facts match at ≥0.9 similarity | ❌ No format ablation |
| Replay documents in date order | Every as-of question returns right value | ❌ No temporal replay harness |
| Ablation: Vector only vs +Graph vs Full | Gain from each layer visible | ❌ No ablation infra |

---

## 7. IMPLEMENTATION PHASES (Prioritized)

### Phase 0: Foundation (Week 1-2)
- [ ] Postgres + pgvector + pg_trgm + btree_gist setup
- [ ] Dual-clock schema (facts, episodes, blocks, entities, jobs)
- [ ] FastAPI skeleton + SQLAlchemy 2 + Pydantic v2
- [ ] Background worker (SELECT FOR UPDATE SKIP LOCKED)
- [ ] Tenant isolation middleware

### Phase 1: Ingestion Core (Week 2-3)
- [ ] 5 Parser Tiers → Unified Block List
  - Tier 1: Word (python-docx) — styles, headings, tables
  - Tier 2: Excel (openpyxl/pandas) — sheets, tables
  - Tier 3: PDF (PyMuPDF) — text, tables, structure
  - Tier 4: PowerPoint (python-pptx) — slides, shapes
  - Tier 5: Email/Chat/Transcript — turns, headers, timestamps
- [ ] Structure Repair (AI assigns heading levels if flat)
- [ ] File type detection from content (libmagic)
- [ ] LibreOffice headless for legacy Office files

### Phase 2: Extraction & Graph Build (Week 3-4)
- [ ] Entity/Topic Extraction (learns company schema, owner reviews once)
- [ ] Fact Extraction with Dual Clocks
- [ ] Source Authority Ranking (configurable per tenant)
- [ ] Conflict Resolution (4 cases: direct, parameter_drift, scope_overlap, authority_clash)
- [ ] Atomic Graph Write (Close Old + Open New in transaction)

### Phase 3: Meridian AP Plug-in (Week 4-5)
- [ ] 5 Calculators + classify_tds (read params from graph)
- [ ] Router (Calculator / Lookup / Judgment / Refuse)
- [ ] Hybrid Retrieval (Keyword + Vector + Graph Walk → RRF → Rerank → Top-6)
- [ ] Answer Builder (Citations, Calculator Outputs, Older Sources Line, Expert Tips)
- [ ] 4-Check Verifier (Citations real, Numbers sourced, No superseded, Sentences supported)
- [ ] Escalation Loop (Unanswered → Owner Review → Approves → Becomes Fact)

### Phase 4: Acceptance Tests (Week 5-6)
- [ ] Load Meridian corpus (4 Word docs + eval set)
- [ ] Run T1-T10 — **ALL MUST PASS**
- [ ] Run 160-question Ragas eval — **Hit targets**
- [ ] Conflict Scanner — Detect ≥12/15 planted conflicts
- [ ] Tacit Capture Flow — 5-state lifecycle, 6-month TTL

### Phase 5: LIVE CAPTURE LAYER (Week 6-8) — **ABHISHEK'S PROBLEM**
- [ ] Email Connector (IMAP + Graph API, webhook for real-time)
- [ ] Teams Bot (Live messages + webhook, thread context)
- [ ] Meeting Bot (Teams/Zoom/Meet join, record, transcribe)
- [ ] Whisper/faster-whisper for live transcription + timestamps
- [ ] Speaker Diarization (pyannote) + Authority Weighting
- [ ] Live PII Redaction (audio + text)
- [ ] Drive/SharePoint Watcher (Graph API, webhook notifications)

### Phase 6: DELIVERY LAYER (Week 7-8) — **ABHISHEK'S PROBLEM**
- [ ] REST API + WebSocket (existing)
- [ ] Teams App (Bot + Message Extension + Tab for in-chat answers)
- [ ] ERP Embed (Generic iframe/sidebar + Meridian-specific injector)
- [ ] Browser Extension (Content script + sidebar, any web app)
- [ ] Change Notification Webhooks (Graph changes → subscribers)

### Phase 7: SOP SYNC LAYER (Week 8-9) — **ABHISHEK'S PROBLEM**
- [ ] Graph Change Detection (Fact closed/new → trigger)
- [ ] Redline Generator (DocX diff, highlight changes)
- [ ] Push to SharePoint/Drive/Git (Graph API, GitHub/GitLab API)
- [ ] Stakeholder Notification (Email, Teams, in-app)
- [ ] Acknowledgement Tracking (Required/Optional, Deadline, Reminders)
- [ ] Audit Trail (Who saw what, when, acknowledged)

### Phase 8: GENERALITY VALIDATION (Week 9-10)
- [ ] Second Company Test Corpus (Different domain)
- [ ] Format Ablation (Same SOP → PDF/MD/HTML/XLSX/Email)
- [ ] Temporal Replay Harness (Ingest in date order, query as-of)
- [ ] Ablation Study Infra (Vector only / +Graph / Full)
- [ ] Load Test (20 concurrent users, 50-doc dump, <10s median)

---

## 8. TECH STACK (Final — From Arnav)

| Layer | Technology | Rationale |
|---|---|---|
| **API** | Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2 | Typed, fast, auto-docs |
| **Database** | Postgres 16 + pgvector + pg_trgm + btree_gist | Graph, vectors, fuzzy, time-range in one DB |
| **Background Jobs** | Postgres Queue (SELECT FOR UPDATE SKIP LOCKED) + Worker Process | No extra infra, horizontal scaling |
| **Search** | Postgres Full-text + Vector (RRF merge), BGE-small (CPU), BGE Reranker | No external search service |
| **AI Models** | Anthropic Claude (Haiku for triage/routing, Sonnet for extraction/answer/verify) | Cheap for simple, strong for hard |
| **Parsing** | python-docx, openpyxl, pandas, python-pptx, PyMuPDF, BeautifulSoup, libmagic, LibreOffice headless | One parser per family → unified blocks |
| **Transcription** | faster-whisper (CPU/GPU) | Local, fast, timestamps |
| **Diarization** | pyannote.audio | Speaker separation + authority |
| **Web App** | Next.js 14, TypeScript, Tailwind CSS, lucide-react | Modern, performant |
| **Fonts** | Hanken Grotesk, Inter, JetBrains Mono | Light rose answer-engine design |
| **Testing** | pytest, ruff, eslint, tsc, Playwright | Unit, acceptance, screenshot |
| **Deploy** | Docker on Render (API + Worker), Vercel (Web), Neon (Postgres) | One public URL, managed services |

---

## 9. CONFIGURATION (Environment Variables)

```env
# Multi-tenant
DEFAULT_TENANT_SLUG=meridian

# AI Models
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_HAIKU_MODEL=claude-3-5-haiku-20241022
CLAUDE_SONNET_MODEL=claude-3-5-sonnet-20241022

# Database
DATABASE_URL=postgresql://user:pass@host:5432/dbname
# Neon/Render managed Postgres

# Background Worker
WORKER_CONCURRENCY=4
JOB_POLL_INTERVAL_MS=1000

# Search
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
RERANKER_MODEL=BAAI/bge-reranker-base
EMBEDDING_DIM=384

# Live Connectors (Phase 5)
MICROSOFT_GRAPH_CLIENT_ID=...
MICROSOFT_GRAPH_CLIENT_SECRET=...
MICROSOFT_GRAPH_TENANT_ID=...
TEAMS_BOT_APP_ID=...
TEAMS_BOT_APP_PASSWORD=...
ZOOM_ACCOUNT_ID=...
ZOOM_CLIENT_ID=...
ZOOM_CLIENT_SECRET=...

# PII Redaction
PII_REDACTION_ENABLED=true
PII_PAN_REGEX='[A-Z]{5}[0-9]{4}[A-Z]{1}'
PII_BANK_REGEX='[0-9]{9,18}'

# SOP Sync (Phase 7)
SHAREPOINT_SITE_URL=...
GITHUB_TOKEN=... (for Git-backed SOPs)

# Feature Flags
SCHEMA_MODE=learned  # or 'baseline' for hand-written schema
ENABLE_LIVE_CONNECTORS=false
ENABLE_SOP_SYNC=false
```

---

## 10. REPO STRUCTURE (Final)

```
meridian-knowledge-engine/
├── .github/
│   └── workflows/
│       ├── ci.yml                    # Lint, typecheck, test
│       ├── deploy_api.yml            # Render deploy
│       ├── deploy_web.yml            # Vercel deploy
│       └── eval.yml                  # Nightly Ragas eval
├── docker/
│   ├── api.Dockerfile
│   ├── worker.Dockerfile
│   └── docker-compose.yml            # Local dev stack
├── docs/                             # All 12 source specs + this hybrid
│   ├── Meridian_AP_HYBRID_SPEC.md    # THIS FILE
│   └── ... (all other .md files)
├── app/                              # FastAPI Application
│   ├── __init__.py
│   ├── main.py                       # App factory, lifespan
│   ├── config.py                     # Pydantic Settings
│   ├── database.py                   # Engine, session, Base
│   ├── models/                       # SQLAlchemy Models (tables above)
│   ├── schemas/                      # Pydantic Schemas (API contracts)
│   ├── api/
│   │   ├── routes/
│   │   │   ├── query.py              # POST /query/ask
│   │   │   ├── tacit.py              # POST /tacit/capture
│   │   │   ├── episodes.py           # POST /episodes (upload)
│   │   │   ├── admin.py              # Schema switch, tenant mgmt
│   │   │   └── health.py
│   │   └── deps.py                   # Dependencies (tenant, auth)
│   ├── core/
│   │   ├── ingestion/
│   │   │   ├── parser.py             # 5-tier parser → BlockList
│   │   │   ├── structure_repair.py   # AI heading assignment
│   │   │   ├── extractor.py          # Entity/Topic/Fact extraction
│   │   │   ├── authority.py          # Source ranking
│   │   │   ├── conflict.py           # 4-case resolution
│   │   │   └── graph_writer.py       # Atomic close+open
│   │   ├── retrieval/
│   │   │   ├── hybrid.py             # Keyword + Vector + Graph Walk
│   │   │   ├── reranker.py           # BGE reranker
│   │   │   └── filters.py            # Time, client, scope
│   │   ├── answer/
│   │   │   ├── router.py             # Calculator / Lookup / Judge / Refuse
│   │   │   ├── builder.py            # Citations, calcs, older, tips
│   │   │   ├── verifier.py           # 4 checks
│   │   │   └── escalation.py         # Owner review loop
│   │   ├── calculators/              # MERIDIAN AP PLUG-IN
│   │   │   ├── __init__.py
│   │   │   ├── price_variance.py
│   │   │   ├── tds_triage.py
│   │   │   ├── msme_due_date.py
│   │   │   ├── e_invoice.py
│   │   │   └── supplier_normalizer.py
│   │   ├── ontology/                 # Meridian AP entities/predicates
│   │   │   ├── entities.py
│   │   │   ├── predicates.py
│   │   │   └── authority.py
│   │   └── live_capture/             # PHASE 5 - NEW
│   │       ├── email_connector.py
│   │       ├── teams_bot.py
│   │       ├── meeting_bot.py
│   │       ├── transcriber.py        # faster-whisper wrapper
│   │       ├── diarization.py        # pyannote wrapper
│   │       ├── pii_redactor.py       # Audio + text
│   │       └── drive_watcher.py
│   ├── workers/
│   │   ├── ingestion_worker.py       # Processes ingestion jobs
│   │   ├── conflict_scanner.py       # Daily corpus scan
│   │   ├── sop_sync_worker.py        # Phase 7
│   │   └── notification_worker.py    # Change alerts
│   ├── store/                        # Repository Layer (All DB access)
│   │   ├── __init__.py
│   │   ├── episodes.py
│   │   ├── blocks.py
│   │   ├── entities.py
│   │   ├── facts.py
│   │   ├── conflicts.py
│   │   ├── jobs.py
│   │   └── answers.py
│   └── gateways/
│       ├── llm.py                    # Anthropic Claude (Haiku/Sonnet)
│       ├── embeddings.py             # BGE-small + Reranker
│       └── pii.py                    # Regex scrubber
├── web/                              # Next.js 14 Frontend
│   ├── package.json
│   ├── src/
│   │   ├── app/                      # App Router
│   │   ├── components/
│   │   │   ├── AnswerCard.tsx        # Citations, calcs, older, tips
│   │   │   ├── EscalationCard.tsx    # Not-covered + escalate button
│   │   │   ├── TacitCaptureStudio.tsx
│   │   │   ├── RedlineDashboard.tsx  # Process owner view
│   │   │   ├── LiveSourcePanel.tsx   # Phase 5 - connector status
│   │   │   └── SOPSyncPanel.tsx      # Phase 7 - change review
│   │   └── lib/
│   │       ├── api.ts                # Typed API client
│   │       └── utils.ts
│   └── tailwind.config.ts
├── tests/
│   ├── unit/
│   │   ├── test_calculators.py       # 5 calculators + TDS triage
│   │   ├── test_parser.py            # 5 tiers → blocks
│   │   ├── test_extraction.py        # Entity/Fact extraction
│   │   ├── test_conflict.py          # 4 cases
│   │   ├── test_retrieval.py         # Hybrid + RRF + Rerank
│   │   ├── test_verifier.py          # 4 checks
│   │   └── test_live_capture.py      # Phase 5 mocks
│   ├── acceptance/
│   │   ├── test_t1_t10.py            # T1-T10 exact cases
│   │   ├── test_meridian_eval.py     # 160 gold questions
│   │   ├── test_conflict_scan.py     # ≥12/15 planted
│   │   ├── test_tacit_lifecycle.py   # 5-state + TTL
│   │   └── test_generality.py        # Second company, format ablation
│   ├── integration/
│   │   ├── test_ingestion_pipeline.py
│   │   ├── test_answer_pipeline.py
│   │   └── test_escalation_loop.py
│   └── fixtures/
│       ├── meridian_corpus/          # 4 Word docs
│       ├── meridian_eval.xlsx        # 160 questions
│       ├── planted_conflicts.json    # 15 known conflicts
│       └── second_company/           # Different domain corpus
├── scripts/
│   ├── load_meridian_corpus.py       # Ingest 4 docs for testing
│   ├── run_eval.py                   # Full eval suite
│   └── generate_redline.py           # SOP sync helper
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── README.md
└── CLAUDE.md                         # For Claude Code context
```

---

## 11. SUCCESS CRITERIA (Unified)

| Metric | Target | Source |
|---|---|---|
| **T1-T10 Acceptance** | 10/10 Pass | Meridian PRD |
| **160-Q Answer Accuracy** | ≥95% (152/160) | Meridian PRD |
| **Citation Accuracy** | ≥90% (144/160) | Meridian PRD |
| **Outdated Answers** | <5% | Meridian PRD + Arnav |
| **Known Conflicts Found** | ≥12/15 | Meridian PRD |
| **Unsupported → Escalated** | 100% when passages removed | Arnav |
| **Expert Escalation E2E** | Passes (Test T11) | Arnav |
| **Format Ablation** | Facts match ≥0.9 | Arnav |
| **Second Company** | 10/10 Questions answered | Arnav |
| **Temporal Replay** | Every as-of correct | Arnav |
| **Live Ingestion Latency** | <5 min email→answerable | Abhisshek (implied) |
| **In-Workflow Answer** | <30 sec at point of work | Abhisshek |
| **SOP Sync Latency** | <1 hour graph→document | Abhisshek (implied) |
| **ROI (Meridian)** | 4.9 Month Payback | Meridian PRD |

---

## 12. DECISION LOG (Key Architectural Choices)

| Decision | Choice | Rationale | Overrides |
|---|---|---|---|
| **Graph Storage** | Postgres native (dual-clock) | Single DB, range indexes, tenant isolation, no external dependency | Zep/Graphiti (Meridian specs) |
| **Deployment** | Render + Vercel + Neon | Managed, scalable, one public URL, Docker | Zoho Catalyst (Meridian specs) |
| **LLM Provider** | Anthropic Claude only (Haiku/Sonnet) | One gateway, cheap+strong tiering, no multi-provider complexity | OpenAI/Gemini/Nemotron (Meridian specs) |
| **Embeddings** | BGE-small (CPU) + BGE Reranker | Local, free, no API cost, fast enough | OpenAI embeddings (Meridian specs) |
| **Background Jobs** | Postgres SKIP LOCKED queue | No Redis/Celery, transactional, horizontal workers | Catalyst Circuits (Meridian specs) |
| **Temporal Model** | Dual-clock (Valid + Transaction + Retracted) | Answers "what was rule?" AND "what would engine say?" | Valid_from/to only (Meridian specs) |
| **Conflict Resolution** | Authority Rank (Source Type > Version > Status) | Deterministic, auditable, owner-controllable | MLP + TOPSIS (Meridian specs) |
| **Schema Learning** | Automatic + Owner Review + Baseline Mode | Generality proof, safety net | Fixed schema (Meridian specs) |
| **Parsing** | 5-Tier → Unified Block List | Any format, no setup, structure from real signals | AST-only (Meridian specs) |
| **Answer Verification** | Separate 4-Check Verifier (not model self-check) | Model-agnostic, catches hallucinations | None specified (Meridian specs) |
| **Escalation** | Live Loop: Unanswered → Owner → Becomes Fact | Continuous learning, no stale answers | Tacit Capture Studio only (Meridian specs) |

---

## 13. NEXT ACTIONS

1. **APPROVE THIS SPEC** — Team review, sign off
2. **INITIALIZE REPO** — Create structure above, `docker-compose.yml` for local Postgres
3. **PHASE 0 SPRINT** — Foundation (Week 1-2)
4. **WEEKLY CHECKPOINTS** — Against acceptance criteria

---

**This hybrid specification merges:**
- **Abhisshek's Problem** (Live capture, SOP sync, in-workflow delivery, generality)
- **Arnav's Platform** (Dual-clock graph, 12-step pipeline, 7 guardrails, verifier, Postgres stack)
- **Meridian's Requirements** (Exact calculators, T1-T10, 160 eval, conflict scenarios, tacit lifecycle)

**The gaps in Section 6 are the million-dollar differentiators.** Phases 5-7 build them.