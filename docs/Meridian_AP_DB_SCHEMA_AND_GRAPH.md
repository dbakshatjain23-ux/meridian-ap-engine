# MERIDIAN SHARED SERVICES · ENTERPRISE KNOWLEDGE ENGINE
## Database Schema & Temporal Graph Ontology Specification
**Document ID**: `Meridian_AP_DB_SCHEMA_AND_GRAPH.md`  
**Target Environment**: Zoho Catalyst Data Store (SQL) + Zep / Graphiti Temporal Knowledge Graph  

---

## 1. Relational Database Schema (Zoho Catalyst Data Store)

```sql
-- 1. CLAIMS TABLE (Governed Knowledge Units)
CREATE TABLE claims (
    id VARCHAR(64) PRIMARY KEY,
    claim_id VARCHAR(64) NOT NULL,
    kind VARCHAR(32) NOT NULL, -- 'rule', 'parameter', 'practice'
    topic VARCHAR(64) NOT NULL, -- 'price_tolerance', 'tds_section', 'msme_due_date', etc.
    statement TEXT NOT NULL,
    params_json JSON, -- e.g. {"pct": 0.01, "cap": 500}
    scope_client VARCHAR(32) DEFAULT 'ALL', -- 'ALL', 'INFRA', 'PHARMA', 'RETAIL'
    valid_from DATE NOT NULL,
    valid_to DATE, -- NULL means currently open/valid
    authority_tier INT NOT NULL, -- 1: Client Memo, 2: SOP v4.0/DI, 3: Tacit, 4: Superseded v3.1
    status VARCHAR(32) NOT NULL, -- 'current', 'superseded', 'unreviewed', 'draft', 'approved'
    source_file VARCHAR(128) NOT NULL,
    source_section VARCHAR(64) NOT NULL,
    owner_role VARCHAR(64) NOT NULL,
    supersedes_claim_id VARCHAR(64),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. PASSAGES TABLE (Raw Source Citations)
CREATE TABLE passages (
    id VARCHAR(64) PRIMARY KEY,
    source_file VARCHAR(128) NOT NULL,
    section_or_timestamp VARCHAR(64) NOT NULL,
    raw_text TEXT NOT NULL,
    doc_version VARCHAR(32) NOT NULL,
    doc_date DATE NOT NULL,
    doc_status VARCHAR(32) NOT NULL
);

-- 3. VENDORS TABLE (Master Supplier Data)
CREATE TABLE vendors (
    vendor_id VARCHAR(32) PRIMARY KEY,
    vendor_name VARCHAR(128) NOT NULL,
    pan_number VARCHAR(16),
    is_pan_available BOOLEAN NOT NULL DEFAULT TRUE,
    aato_band VARCHAR(32) NOT NULL, -- 'ABOVE_5CR', 'BELOW_5CR'
    is_msme BOOLEAN NOT NULL DEFAULT FALSE,
    msme_category VARCHAR(32), -- 'MICRO', 'SMALL', 'MEDIUM', 'NONE'
    is_qrmp BOOLEAN NOT NULL DEFAULT FALSE,
    habit_note TEXT
);

-- 4. PRACTICES TABLE (Tacit Expert Cards)
CREATE TABLE practices (
    practice_id VARCHAR(64) PRIMARY KEY,
    vendor_id VARCHAR(32),
    topic VARCHAR(64) NOT NULL,
    habit_description TEXT NOT NULL,
    action_to_take TEXT NOT NULL,
    rule_claim_id VARCHAR(64) NOT NULL,
    source_timestamp VARCHAR(64) NOT NULL, -- e.g. 'Interview 1 [02:30]'
    captured_by VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL, -- 'draft', 'proposed', 'approved', 'expired', 'rejected'
    approver_name VARCHAR(64),
    review_by_date DATE NOT NULL, -- Mandatory 6-month TTL
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. INVOICES TABLE (Operational Log & Exceptions)
CREATE TABLE invoices (
    invoice_id VARCHAR(64) PRIMARY KEY,
    vendor_id VARCHAR(32) NOT NULL,
    client_entity VARCHAR(32) NOT NULL, -- 'Arvana Infra', 'Arvana Pharma', 'Arvana Retail'
    invoice_number VARCHAR(64) NOT NULL,
    normalized_invoice_num VARCHAR(64) NOT NULL,
    invoice_date DATE NOT NULL,
    received_date DATE NOT NULL,
    total_amount DECIMAL(12, 2) NOT NULL,
    taxable_amount DECIMAL(12, 2) NOT NULL,
    gst_amount DECIMAL(12, 2) NOT NULL,
    exception_code VARCHAR(64), -- 'PRICE_VAR', 'NO_GRN', 'TDS_SECTION_UNCLEAR', etc.
    handling_minutes DECIMAL(6, 2)
);
```

---

## 2. Zep / Graphiti Temporal Graph Schema (OpenSPG Ontology)

```cypher
// Graph Node Classes & Temporal Edges
(:Vendor {vendor_id: "V20000", name: "Balaji Logistics", aato_band: "ABOVE_5CR"})
  -[:APPLIES_TO_DESK]-> (:ClientDesk {name: "Arvana Pharma"})

(:Vendor {vendor_id: "V20000"})
  -[:GOVERNED_BY {valid_from: "2026-04-01", valid_to: null}]-> 
  (:RuleClaim {claim_id: "PRICE_TOL.v40", pct: 0.01, cap: 500})

(:RuleClaim {claim_id: "PRICE_TOL.v40"})
  -[:SUPERSEDES]-> 
  (:RuleClaim {claim_id: "PRICE_TOL.v31", valid_from: "2023-07-01", valid_to: "2026-03-31", pct: 0.02, cap: 1000})

(:Vendor {vendor_id: "V20000"})
  -[:HAS_PRACTICE {status: "approved", review_by: "2027-03-31"}]-> 
  (:PracticeCard {habit: "Appends /A or -REV on resend", source: "Interview 1 [02:30]"})
```
