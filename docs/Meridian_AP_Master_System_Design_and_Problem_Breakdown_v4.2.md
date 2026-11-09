# MERIDIAN SHARED SERVICES · ENTERPRISE KNOWLEDGE ENGINE
## Master Problem Breakdown, Deep Claim-Based System Architecture & Enterprise Production Deployment Guide (v4.2 Production Architecture)

---

## 1. Executive Summary & Operational Context
Meridian Shared Services operates a 120-person Accounts Payable (AP) department in Hyderabad, managing invoice processing, tax compliance, and supplier disbursements for three distinct Arvana Group entities: **Arvana Retail**, **Arvana Pharma**, and **Arvana Infra Projects**.

Over a six-month operational evaluation period (April through September 2026), the floor processed **9,000 supplier invoices** totaling tens of crores in disbursements across three primary intake channels:
* **Portal Intake**: 5,378 invoices (59.8%)
* **E-mail Intake**: 3,418 invoices (38.0%)
* **Paper Scans**: 204 invoices (2.3%)

### The Operational Bottlenecks
* **Exception Surge**: **3,207 out of 9,000 invoices (35.6%)** raise operational exceptions, consuming **64% of total processor working minutes**.
* **Communication Bottleneck**: Junior processors post **1,900 questions on MS Teams** over 6 months. The **median wait time for a first reply is 33 minutes** (spiking to **47 minutes for pings after 5:00 PM** and 96 minutes at the 90th percentile), accumulating **1,480 total hours of parked idle time** (1,219 hours in computable and lookup lanes).
* **Outdated Guidance & Rework**: **12.7% of Teams answers (241 replies)** match outdated or superseded rules, forcing **16.5% of askers to re-key or redo their work**.
* **Single-Point-of-Failure Exit Risk**: Three senior experts answer **58% of all floor questions**. Senior Processor **Lakshmi Reddy (11 years tenure)** answers **33% of all questions alone (619 queries)**. Lakshmi exits the company on **14 November 2026**. If her pings fall to the general floor (where stale answers hit 20.7%), floor-wide stale answers will jump from **12.7% to ~18%**.
* **Onboarding Latency**: New-joiner time-to-proficiency (TTP)—the time needed to sustain 4 consecutive weeks at $\ge 90\%$ accuracy—has stretched from **71 days to 87 days** ($n=11$ post-April 2026 cohort). New joiners suffer a **5.8% error rate** in their first 90 days and take **15.2 minutes per invoice** (vs 10.4 minutes for experienced staff).
* **Quality Check (QC) Error Reconciliation**: Audits uncovered **339 processing errors (3.8% floor error rate)**:
  * **120 Superseded Rule Errors (35.4%)**: 82 price tolerance errors (applying old 2% / ₹1,000) + 38 e-invoice IRN errors (applying obsolete ₹10 Cr limit).
  * **101 TDS Section Errors (29.8%)**: Processors picking incorrect TDS sections (194C vs 194J) or calculating TDS on GST-inclusive amounts.
  * **10 Missed QA Releases (2.9%)**: Caused by the 2023 FAQ claiming excipients do not need QA release, contradicting Client Memo **CM-PHA-01**.

---

## 2. Enterprise Production Architecture & The 6 Critical Fixes

To transition from a prototype to a **production-grade enterprise solution deployed on Zoho Catalyst**, the v4.2 architecture resolves 6 critical enterprise execution bottlenecks:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   v4.2 ENTERPRISE PRODUCTION ENGINE ARCHITECTURE                       │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. ASYNCHRONOUS CATALYST CIRCUITS & TASK QUEUES                                        │
│    • Decouples synchronous HTTP gateway from long-running graph diffs & batch evals.  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 2. ZINGG ACTIVE-LEARNING ENTITY RESOLUTION & HUMAN-IN-THE-LOOP AUDIT QUEUE             │
│    • Fuzzy blocking model handles GSTIN state mismatches & parent-subsidiary aliases.  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 3. 2-WAY ERP BAPI / ODATA CONNECTOR                                                    │
│    • Pre-fills draft fields in SAP/Oracle ERP for single-click "Accept & Post".        │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 4. LAZYGRAPHRAG & INCREMENTAL GRAPH EXTRACTION                                         │
│    • Cuts bulk document indexing costs by 90%+ while maintaining GraphRAG recall.      │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 5. AUTOMATED TACIT HEALTH & FEEDBACK LOOP                                              │
│    • Auto-extends high-confidence expert cards; prioritizes flagged cards for review.  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 6. PYDANTIC MULTI-LLM SCHEMA VALIDATION & AUTOMATED FAILOVER LOOP                      │
│    • Guarantees 100% valid JSON payload delivery across OpenAI, Gemini, Nemotron, Claude.│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### The 6 Enterprise Fixes Breakdown

1. **Decoupled Asynchronous Catalyst Circuits**: Serverless functions enforce strict 15–30s execution timeouts. Heavy operations—such as multi-document graph diffing for **Acceptance Test T9** or batch 160-question evaluations—are offloaded to **Zoho Catalyst Concurrency Circuits** driven by asynchronous event triggers, returning instant job IDs to the UI.
2. **Active-Learning Entity Resolution**: Upgrades `normalize_supplier_string` with **Zingg active-learning blocking models**. Handles complex Indian GSTIN state mismatches (e.g., vendor `V20091` printing wrong-state GSTINs) and routes ambiguous matches ($	ext{similarity} \in [0.75, 0.90]$) to a **Human-in-the-Loop Audit Queue**.
3. **2-Way ERP BAPI / OData Webhooks**: Eliminates processor copy-paste friction by providing a **2-Way ERP Connector**. Verified TDS classifications, MSME payment due dates, and normalized invoice numbers are pushed directly into SAP/Oracle draft screens for a single-click **"Accept & Post"** action.
4. **LazyGraphRAG & Incremental Updates**: Avoids full graph extraction costs on every upload. Uses vector search for simple lookups, while triggering temporal graph node and edge updates (`valid_from`/`valid_to`) only for modified documents or specific entity neighborhoods.
5. **Automated Tacit Health & Feedback Loop**: Manages Lakshmi Reddy's 21 captured vendor habits post-exit without administrative overload. Cards with thumbs-up feedback and 0 linked QC errors auto-renew at their 6-month TTL expiry, while cards linked to recent floor exceptions are escalated for human re-approval.
6. **Pydantic Multi-LLM Fallback Loop**: Enforces strict Pydantic JSON schema validation at the gateway layer. If a provider (e.g., Gemini Flash) returns invalid function arguments, the system automatically fails over to Claude 3.5 Sonnet or GPT-4o before passing parameters to deterministic Python math calculators.

---

## 3. Claim-Based Knowledge Units & 3-Lane Execution Engine

Knowledge is stored as governed **Claim Records**:
$$	ext{Claim Record} = \langle 	ext{claim\_id}, 	ext{kind}, 	ext{topic}, 	ext{params}, 	ext{scope}, 	ext{valid\_from}, 	ext{valid\_to}, 	ext{authority}, 	ext{status}, 	ext{source} angle$$

### 3-Lane Routing Flow

```
┌─────────────────────────┐   ┌─────────────────────────┐   ┌─────────────────────────┐
│ LANE 1: COMPUTABLE      │   │ LANE 2: LOOKUP          │   │ LANE 3: JUDGMENT/TACIT  │
│ (54% · 1,025 Pings)     │   │ (28% · 526 Pings)       │   │ (18% · 349 Pings)       │
├─────────────────────────┤   ├─────────────────────────┤   ├─────────────────────────┤
│ • Price Variance        │   │ • GSTR-2B Reconcile     │   │ • TDS Section Triage    │
│ • E-Invoice Thresholds  │   │ • Non-PO Categories     │   │ • Infra GRN Batching    │
│ • Approval Hierarchy    │   │ • Pharma QA Release     │   │ • RCM Tax Reviews       │
│ • MSME Payment Runs     │   │ • Bank Change Callbacks │   │ • Senior Floor Habits   │
├─────────────────────────┤   ├─────────────────────────┤   ├─────────────────────────┤
│ MECHANISM:              │   │ MECHANISM:              │   │ MECHANISM:              │
│ 5 Python Math Tools     │   │ Scoped Cited Retrieval  │   │ classify_tds pre-triage;│
│ reading Dated Rule Store│   │ filtered by Client Desk │   │ Abstain on mixed AMCs;  │
│ + Vendor Master Metadata│   │ & Invoice as_of_date    │   │ Side-by-Side Practice   │
└─────────────────────────┘   └─────────────────────────┘   └─────────────────────────┘
```

---

## 4. Evaluation Benchmark & Acceptance Test Matrix (T1–T10)

| Acceptance Test | Scenario & Input Condition | Expected Engine Behaviour | Production Status |
| :--- | :--- | :--- | :--- |
| **T1** | Price tolerance query (Q001) | Answers lower of 1% or ₹500 (SOP v4.0 §4.2); notes superseded v3.1 2% rule | Verified (Retrieval) |
| **T2** | ₹8.9 Cr turnover vendor without IRN | Rejects under SOP v4.0 §5.4 (₹5 Cr threshold); rejects obsolete ₹10 Cr rule | PASSED IN CODE |
| **T3** | Pharma excipient QA release query | Requires QA release per CM-PHA-01; flags 2023 FAQ error | Verified (Retrieval) |
| **T4** | Saturday Infra invoice with no GRN | Displays SOP v4.0 §4.6 hold rule SIDE-BY-SIDE with Lakshmi Tuesday-noon practice | Verified (Side-by-Side) |
| **T5** | PO ₹395, Invoice ₹400 (500 bags) | Excess ₹2,500 vs limit ₹500; raises `PRICE_VAR` | PASSED IN CODE |
| **T6** | TDS on software support ₹4,80,000 + GST | Section 194J @ 2% = ₹9,600; excludes GST from TDS taxable base | PASSED IN CODE |
| **T7** | Micro supplier accepted 1 Aug 2026 | Due 16 Aug (15d cap); maps to Friday 14 Aug payment run | PASSED IN CODE |
| **T8** | Canteen subsidy out-of-corpus query | Abstains ("corpus silent"), routes to Sandeep Rao / Process Excellence | Verified (Abstention) |
| **T9** | Corpus-wide conflict scan | Detects $\ge 12$ of 15 planted conflicts via ConflictRAG 2-stage MLP classifier | Verified (Scanner) |
| **T10** | Unwritten vendor habit capture | Creates approved habit cards with mandatory 6-month TTL expiry date | Verified (Studio) |

---

## 5. Deployment Architecture on Zoho Catalyst

```
meridian-ap-knowledge-engine/
├── catalyst.json                        # Master Catalyst CLI config
├── functions/
│   ├── python_applogic/                 # Python 3.12 Serverless AppLogic (Calculators, Graph, LLM Adapter)
│   └── node_middleware/                 # Node.js 18+ API Gateway & DPDP PII Regex Scrubber
├── client/                              # React / Vite Front-End Web Application
└── tests/                               # Pytest Runner for Acceptance Tests T1–T10 & Ragas Evals
```
