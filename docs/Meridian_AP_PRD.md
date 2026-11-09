# MERIDIAN SHARED SERVICES · ENTERPRISE KNOWLEDGE ENGINE
## Product Requirements Document (PRD) — Production Repo Specification
**Document ID**: `Meridian_AP_PRD.md`  
**Target Environment**: Zoho Catalyst (Python 3.12 AppLogic + Node.js API Functions + Catalyst Data Store)  
**LLM Layer**: Dynamic Multi-LLM Adapter (OpenAI GPT-4o, Gemini 1.5/2.0, Nemotron 4 340B, Claude 3.5 Sonnet)

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
| **P1. Stale Search Traps** | Shared drive searches return superseded files (SOP v3.1, 2023 FAQ, 2022 Video) first. | 120 QC errors (82 price tolerance, 38 IRN limit). | System must **never present an outdated rule as current policy**. Enforce SOP v4.0 (eff. 1 April 2026). |
| **P2. Queue Idle Latency** | Junior processors wait on MS Teams for senior answers, parking invoices. | 1,900 pings; median wait 33m; 1,480 idle hours. | Deliver cited, version-accurate answers in **< 30 seconds** at point of invoice entry. |
| **P3. Key-Person Exit Risk** | Q&A concentrated on Lakshmi Reddy (33% alone, 619 pings). Exits 14 Nov. | 619 queries routed to one person. | Capture unwritten tacit know-how into structured, reviewable cards before exit. |
| **P4. Onboarding Deficit** | New joiners lack a reliable source of truth, causing high error rates and slow ramp-up. | TTP stretched to 87 days; 5.8% error rate in first 90 days. | Reduce TTP by $\ge 15$ days via instant cited induction guidance. |
| **P5. Document Fragmentation** | General SOP v4.0 overridden by client-specific memos stored in separate folders. | Client invoice rejections caused by applying general SOP to client accounts. | System must be **client-desk aware**. Client Memos (CM-INF-02, CM-PHA-01, CM-RET-03) strictly override general SOP. |
| **P6. Arithmetic Hallucinations** | 57.5% of evaluation queries require multi-step math calculations. | Manual math errors on price tolerances, TDS base values, and approval limits. | Math calculations for price tolerances (`min(1%, ₹500)`), TDS, and payment caps must be **100% deterministic**. |
| **P7. MSME Tax Exposure** | Processors confuse MSME terms with standard 60-day commercial terms. | 245 late MSME payments worth ₹3.4 crore. | Under Sec 43B(h) IT Act & Sec 16 MSMED Act, enforce 15/45-day caps and mandatory 3x RBI compound interest rules. |
| **P8. Fraud & DPDP Security** | Bank account change requests vulnerable to phishing; PII exposure. | 2 fraudulent bank change attempts in 2025; DPDP Act 2023 compliance. | Enforce SOP v4.0 §8.2 / DI-07 callback controls; scrub PAN/bank PII before LLM processing. |

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
│ • Run Python math │ • Verifies bank   │ • Approves/rejects      │   queries            │
│   calculators     │   callbacks       │   captured tacit cards  │ • Issues binding tax │
│ • Zero manual math│ • Escalates clashes│ • Sets 6-month TTLs     │   classification rules│
└───────────────────┴───────────────────┴─────────────────────────┴──────────────────────┘
```

---

## 4. Product Functional Specifications

### 4.1 Functional Requirement 1: 3-Lane Execution Engine
* **Lane 1 · Computable Lane (54% / 1,025 Pings)**: Handles price tolerances, e-invoice thresholds, approval hierarchies, MSME due dates, duplicate normalization, and month-end cut-offs using **5 Deterministic Python Calculators** querying a dated claim store.
* **Lane 2 · Lookup Lane (28% / 526 Pings)**: Delivers cited retrieval scoped strictly by client desk (`Arvana Infra / Pharma / Retail`) and invoice `as_of_date`.
* **Lane 3 · Judgment / Tacit Lane (18% / 349 Pings)**: Executes pre-calculation triage via `classify_tds`. Ambiguous contracts return **`TDS_SECTION_UNCLEAR`** to Tax Lead Imran Qureshi. Approved expert practice cards are displayed side-by-side with written rules.

### 4.2 Functional Requirement 2: Dynamic Multi-LLM Provider Layer
* Pluggable LLM abstraction supporting **OpenAI (GPT-4o)**, **Gemini (1.5 Pro / 2.0 Flash)**, **Nemotron (4 340B)**, and **Claude (3.5 Sonnet)**.
* Provider selection controlled via `LLM_PROVIDER` environment configuration without modifying prompt templates or tool JSON schemas.

### 4.3 Functional Requirement 3: Version-Aware Claim Store & Temporal Knowledge Graph
* Knowledge stored as individual **Claim Records** with `valid_from` and `valid_to` dates rather than raw text chunks.
* Incorporates **Zep / Graphiti Temporal Memory Architecture (`arXiv:2501.13956`)** for dynamic fact evolution.

### 4.4 Functional Requirement 4: Corpus-Wide Conflict Scanner & Redline Queue
* Uses **ConflictRAG (`arXiv:2605.17301`)** two-stage MLP detection + Entropy-TOPSIS scoring to detect cross-document contradictions (Target: $\ge 12$ of 15 planted conflicts).

### 4.5 Functional Requirement 5: Tacit Exit Capture Studio
* Captures senior expert habits before Lakshmi Reddy's 14 November exit into structured **Vendor Habit Cards** carrying a mandatory **6-month TTL review date**.

---

## 5. Non-Functional Requirements & Performance Targets

1. **Answer Latency**: $< 30$ seconds end-to-end ($< 2$ seconds for Lane 1 calculators).
2. **Security & Data Privacy**: Pre-LLM Regex scrubber masking PAN, bank accounts, and employee PII (complying with DPDP Act 2023).
3. **Availability & Resilience**: 99.9% uptime deployed on Zoho Catalyst infrastructure.
4. **Benchmark Targets**:
   * **Answer Accuracy**: $\ge 95\%$ (152/160 gold questions).
   * **Citation Accuracy**: $\ge 90\%$ (144/160 gold questions).
   * **Outdated Answers Offered**: $< 2\%$ overall (0 outdated rules returned as current).

---

## 6. Financial ROI & Target Business Metrics

* **Parked Waiting Hours Avoided**: 914 to 1,097 hours saved out of 1,219 computable/lookup wait hours.
* **Superseded-Rule QC Errors Avoided**: 90 to 108 errors prevented (out of 120 baseline errors).
* **Statutory Tax Exposure Mitigated**: 245 late MSME invoices worth ₹3.4 crore protected from 3x RBI compound interest disallowance under Section 16 of the MSMED Act.
* **Payback Period**: **4.9 Months** based on operational waste reduction.
