# MERIDIAN SHARED SERVICES · ENTERPRISE KNOWLEDGE ENGINE
## Product Requirements Document (PRD) — Production Repo Specification
**Document ID**: `Meridian_AP_PRD.md`  
**Target Environment**: **Docker on Render (API + Worker), Vercel (Web), Neon (Postgres)**  
**LLM Layer**: **Anthropic Claude Only** (Haiku for triage/routing, Sonnet for extraction/answer/verification)  
**Embeddings**: **BGE-small-en-v1.5 (CPU) + BGE Reranker** — Local, no API cost  
**Search**: **Postgres Full-Text + pgvector (HNSW) + Reciprocal Rank Fusion**  

---

## 1. Executive Context & Operational Problem Statement

Meridian Shared Services operates a 120-person Accounts Payable (AP) department in Hyderabad, managing invoice processing, tax compliance, and supplier disbursements for three distinct Arvana Group entities: **Arvana Retail**, **Arvana Pharma**, and **Arvana Infra Projects**.

Over a six-month evaluation period (April – September 2026), the floor processed **9,000 supplier invoices** totaling tens of crores across three intake channels:
* **Portal Intake**: 5,378 invoices (59.8%)
* **E-mail Intake**: 3,418 invoices (38.0%)
* **Paper Scans**: 204 invoices (2.3%)

### 1.1 The Operational Bottlenecks
1. **Exception Surge**: **3,207 out of 9,000 invoices (35.6%)** raise operational or compliance exceptions, consuming **64% of total processor working minutes**.
2. **MS Teams Queue Latency**: Junior processors posted **1,900 questions on MS Teams**. The **median wait time for a reply is 33 minutes** (spiking to **47 minutes after 5:00 PM**), accumulating **1,480 total hours of parked idle time** (1,219 hours in computable/lookup lanes).
3. **Stale Guidance & Rework**: **12.7% of Teams replies (241 answers)** match outdated rules, forcing **16.5% of askers to re-key or redo work**.
4. **Single-Point-of-Failure Exit Risk**: Three senior experts answer **58% of all floor questions**. Senior Processor **Lakshmi Reddy (11 years tenure)** answers **33% of all questions alone (619 pings)**. Lakshmi exits on **14 November 2026**. If her pings fall to the general floor (where stale answers hit 20.7%), floor-wide stale answers will jump from **12.7% to ~18%**.
5. **Quality Check (QC) Errors**: Audits uncovered **339 errors (3.8% error rate)**: **120 errors (35.4%)** stem directly from superseded rules (82 price tolerance + 38 e-invoice IRN), **101 errors (29.8%)** from incorrect TDS section selection, and **10 errors (2.9%)** from a 2023 FAQ error regarding Pharma excipient QA releases.
6. **Onboarding Latency**: New-joiner Time-to-Proficiency (TTP) stretched from **71 days to 87 days** ($n=11$ cohort) with a **5.8% error rate** in their first 90 days.

---

## 2. Partitioning into 8 Isolated Problem Chunks

| Problem Chunk | Operational Floor Issue | Primary Data Metric | Mandatory System Constraint |
|---|---|---|---|
| **P1. Stale Search Traps** | Shared drive searches return superseded files (SOP v3.1, 2023 FAQ, 2022 Video) first. | 120 QC errors (82 price tolerance, 38 IRN limit). | System must **never present an outdated rule as current policy**. Dual-clock temporal graph enforces authority > recency. |
| **P2. Queue Idle Latency** | Junior processors wait on MS Teams for senior answers, parking invoices. | 1,900 pings; median wait 33m; 1,480 idle hours. | Deliver cited, version-accurate answers in **< 30 seconds** at point of invoice entry via ERP embed / Teams app / browser extension. |
| **P3. Key-Person Exit Risk** | Q&A concentrated on Lakshmi Reddy (33% alone, 619 pings). Exits 14 Nov. | 619 queries routed to one person. | Capture unwritten tacit know-how into structured, reviewable **Fact Cards** with mandatory **6-month TTL** before expiry. |
| **P4. Onboarding Deficit** | New joiners lack a reliable source of truth, causing high error rates and slow ramp-up. | TTP stretched to 87 days; 5.8% error rate in first 90 days. | Reduce TTP by $\ge 15$ days via instant cited induction guidance + guided learning path from corpus. |
| **P5. Document Fragmentation** | General SOP v4.0 overridden by client-specific memos stored in separate folders. | Client invoice rejections caused by applying general SOP to client accounts. | System must be **client-desk aware**. Client Memos (CM-INF-02, CM-PHA-01, CM-RET-03) strictly override general SOP via authority ranking. |
| **P6. Arithmetic Hallucinations** | 57.5% of evaluation queries require multi-step math calculations. | Manual math errors on price tolerances, TDS base values, and approval limits. | Math calculations for price tolerances (`min(1%, ₹500)`), TDS, and payment caps must be **100% deterministic** via Python calculators reading params from graph. |
| **P7. MSME Tax Exposure** | Processors confuse MSME terms with standard 60-day commercial terms. | 245 late MSME payments worth ₹3.4 crore. | Under Sec 43B(h) IT Act & Sec 16 MSMED Act, enforce 15/45-day caps and mandatory 3x RBI compound interest rules via calculator. |
| **P8. Fraud & DPDP Security** | Bank account change requests vulnerable to phishing; PII exposure. | 2 fraudulent bank change attempts in 2025; DPDP Act 2023 compliance. | Enforce SOP v4.0 §8.2 / DI-07 callback controls; **Pre-LLM PII Regex Scrubber** masks PAN/bank before any model call. |

---

## 3. Core User Personas & System Interactions

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 USER PERSONA WORKFLOWS                                 │
├───────────────────┬───────────────────┬─────────────────────────┬──────────────────────┤
│ AP PROCESSOR      │ AP SENIOR REVIEWER│ PROCESS OWNER (SANDEEP) │ TAX LEAD (IMRAN Q.)  │
│ (Junior Staff)    │ (Approver)        │ (Governance Lead)       │ (Tax Desk Lead)      │
├───────────────────┼───────────────────┼─────────────────────────┼──────────────────────┤
│ • Receives cited  │ • Reviews flagged │ • Receives Redline Queue│ • Receives routed    │
│   answers < 30s   │   exceptions      │   of corpus conflicts   │   TDS_SECTION_UNCLEAR│
│ • Run Python math │ • Verifies bank   │ • Approves/rejects      │ • Issues binding tax │
│   calculators     │   callbacks       │   captured tacit cards  │   classification rules│
│ • Zero manual math│ • Escalates clashes│ • Sets 6-month TTLs     │ • Reviews tax changes│
│ • In ERP/Teams/   │ • Approves SOP    │ • Triggers SOP sync     │                       │
│   Browser Ext     │   sync changes    │   to SharePoint         │                       │
└───────────────────┴───────────────────┴─────────────────────────┴──────────────────────┘
```

---

## 4. Product Functional Specifications

### 4.1 Functional Requirement 1: 3-Lane Execution Engine
* **Lane 1 · Computable Lane (54% / 1,025 Pings)**: Handles price tolerances, e-invoice thresholds, approval hierarchies, MSME due dates, duplicate normalization, and month-end cut-offs using **6 Deterministic Python Calculators** (`calculate_price_variance`, `classify_tds`, `calculate_tds`, `calculate_msme_due_date`, `validate_e_invoice_requirement`, `normalize_supplier_string`) reading parameters **dynamically from the temporal graph** (NOT hardcoded).
* **Lane 2 · Lookup Lane (28% / 526 Pings)**: Delivers cited retrieval scoped strictly by client desk (`Arvana Infra / Pharma / Retail`) and invoice `as_of_date`. Hybrid search: Keyword + Vector + Graph Walk → RRF Merge → Rerank → Top-6 passages.
* **Lane 3 · Judgment / Tacit Lane (18% / 349 Pings)**: Executes pre-calculation triage via `classify_tds`. Ambiguous contracts return **`TDS_SECTION_UNCLEAR`** to Tax Lead Imran Qureshi. Approved expert practice cards (Fact status=approved, authority_rank=3) displayed **side-by-side** with written rules.

### 4.2 Functional Requirement 2: Single-Provider LLM Gateway (Anthropic Claude)
* **Two-Model Tiering**: `claude-3-5-haiku` for triage, routing, structure repair, schema learning (cheap, fast). `claude-3-5-sonnet` for extraction, answer generation, verification (strong reasoning).
* **One Gateway**: All model calls routed through `LLMGateway` class — hides PII, logs calls, caches results for reproducibility.
* **No Multi-Provider Abstraction**: Removes complexity; Claude + local embeddings covers all needs.

### 4.3 Functional Requirement 3: Dual-Clock Temporal Knowledge Graph (Postgres Native)
* Knowledge stored as **Facts** with **two clocks**:
  - **Valid Time**: `valid_from` / `valid_to` — When the fact was true in the world
  - **Transaction Time**: `recorded_at` / `retracted_at` — When the system learned/retracted it
* Enables: "What was the rule on March 1?" (valid time) AND "What would the engine have told someone on Nov 10?" (transaction time)
* **Never Overwrites**: New fact closes old fact (`retracted_at = now()`) and opens new fact atomically in single transaction.
* **Authority Ranking**: Source type > version > status (Client Memo=1, SOP v4.0=2, DI=3, Tacit=4, Superseded=5). Lower rank wins.

### 4.4 Functional Requirement 4: Corpus-Wide Conflict Scanner & Redline Queue
* **4-Case Conflict Detection** (not MLP):
  1. **Direct Contradiction** — Same subject/predicate, different values, overlapping valid time
  2. **Parameter Drift** — Same predicate, value changed beyond threshold
  3. **Scope Overlap** — Client memo vs general rule for same predicate
  4. **Authority Clash** — Two sources same rank, conflicting values
* **Entropy-TOPSIS** retained for credibility scoring when needed.
* Target: Detect **≥12 of 15** planted conflicts in Meridian corpus.

### 4.5 Functional Requirement 5: Tacit Knowledge Capture Lifecycle (5-State)
* **States**: `draft` → `proposed` → `approved` → `expired` / `rejected`
* Every approved habit card carries **mandatory 6-month TTL** (`review_by_date`)
* Must be **signed off by Process Owner** (Sandeep Rao) before becoming answerable
* Captured facts enter graph with `authority_rank=3`, `status=approved`, `source_type=expert_interview`

### 4.6 Functional Requirement 6: Live Source Ingestion (NEW — Abhisshek's Problem)
* **Email Connector**: IMAP + Microsoft Graph API, real-time webhook ingestion
* **Teams Bot**: Live message ingestion, thread context preservation, webhook receiver
* **Meeting Bot**: Joins Teams/Zoom/Meet, records, transcribes (faster-whisper), diarizes (pyannote)
* **Drive/SharePoint Watcher**: Graph API notifications for document changes
* **Live PII Redaction**: Audio + text streams scrubbed BEFORE graph ingestion

### 4.7 Functional Requirement 7: In-Workflow Delivery Layer (NEW — Abhisshek's Problem)
* **REST API + WebSocket**: Primary programmatic interface
* **Teams App**: Bot + Message Extension + Tab for in-chat answers
* **ERP Embed**: Generic iframe/sidebar injector + Meridian-specific integration
* **Browser Extension**: Content script + sidebar, works on any web app
* **Change Notification Webhooks**: Graph changes → subscribers (email, Teams, in-app)

### 4.8 Functional Requirement 8: SOP Sync Layer (NEW — Abhisshek's Problem)
* **Change Detection**: Fact closed/new → triggers sync job
* **Redline Generator**: DocX diff with highlighted changes
* **Push Targets**: SharePoint/Drive (Graph API), Git (GitHub/GitLab API)
* **Stakeholder Notification**: Email, Teams, in-app with acknowledgement tracking
* **Audit Trail**: Who saw what, when, acknowledged — compliance ready

---

## 5. Non-Functional Requirements & Performance Targets

1. **Answer Latency**: $< 30$ seconds end-to-end ($< 2$ seconds for Lane 1 calculators).
2. **Security & Data Privacy**: Pre-LLM Regex scrubber masking PAN, bank accounts, employee PII (DPDP Act 2023). Live audio/video redaction.
3. **Availability & Resilience**: 99.9% uptime on Render (managed Docker) + Neon (managed Postgres).
4. **Benchmark Targets**:
   * **Answer Accuracy**: $\ge 95\%$ (152/160 gold questions).
   * **Citation Accuracy**: $\ge 90\%$ (144/160 gold questions).
   * **Outdated Answers Offered**: $< 5\%$ overall (0 outdated rules returned as current).
   * **Known Conflicts Found**: $\ge 12/15$ planted conflicts.
   * **Unsupported → Escalated**: 100% when supporting passages removed.
5. **Generality Proof** (Arnav's Platform Requirement):
   * Second unrelated company docs, no code changes → 10/10 questions answered with citations
   * Same SOP in other formats (PDF, MD, HTML, XLSX, email) → Facts match ≥0.9 similarity
   * Temporal replay (ingest in date order) → Every as-of question returns correct value

---

## 6. Financial ROI & Target Business Metrics

* **Parked Waiting Hours Avoided**: 914 to 1,097 hours saved out of 1,219 computable/lookup wait hours.
* **Superseded-Rule QC Errors Avoided**: 90 to 108 errors prevented (out of 120 baseline errors).
* **Statutory Tax Exposure Mitigated**: 245 late MSME invoices worth ₹3.4 crore protected from 3x RBI compound interest disallowance under Section 16 of the MSMED Act.
* **Payback Period**: **4.9 Months** based on operational waste reduction.
* **Platform Value**: Same core serves unlimited tenants; Meridian AP is first industry plug-in.