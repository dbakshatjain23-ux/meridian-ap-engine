# MERIDIAN SHARED SERVICES · ENTERPRISE KNOWLEDGE ENGINE
## Master Problem Breakdown, Hybrid Architecture & Platform Deployment Guide (v5.0)
**Document ID**: `Meridian_AP_Master_System_Design_and_Problem_Breakdown_v5.0.md`  
**Supersedes**: v4.2 (Zoho Catalyst Architecture)  
**Architecture**: **Generic Core + AP Plug-in** — Deployed on **Docker (Render + Vercel + Neon)**  

---

## 1. Executive Summary & Operational Context

Meridian Shared Services operates a 120-person Accounts Payable (AP) department in Hyderabad, managing invoice processing, tax compliance, and supplier disbursements for three distinct Arvana Group entities: **Arvana Retail**, **Arvana Pharma**, and **Arvana Infra Projects**.

Over a six-month operational evaluation period (April through September 2026), the floor processed **9,000 supplier invoices** totaling tens of crores in disbursements across three primary intake channels:
* **Portal Intake**: 5,378 invoices (59.8%)
* **E-mail Intake**: 3,418 invoices (38.0%)
* **Paper Scans**: 204 invoices (2.3%)

### The Operational Bottlenecks (Abhisshek Raaj / EY Problem Statement)

1. **Exception Surge**: **3,207 out of 9,000 invoices (35.6%)** raise operational exceptions, consuming **64% of total processor working minutes**.
2. **Communication Bottleneck**: Junior processors post **1,900 questions on MS Teams** over 6 months. The **median wait time for a first reply is 33 minutes** (spiking to **47 minutes for pings after 5:00 PM** and 96 minutes at the 90th percentile), accumulating **1,480 total hours of parked idle time** (1,219 hours in computable and lookup lanes).
3. **Outdated Guidance & Rework**: **12.7% of Teams answers (241 replies)** match outdated or superseded rules, forcing **16.5% of askers to re-key or redo their work**.
4. **Single-Point-of-Failure Exit Risk**: Three senior experts answer **58% of all floor questions**. Senior Processor **Lakshmi Reddy (11 years tenure)** answers **33% of all questions alone (619 queries)**. Lakshmi exits the company on **14 November 2026**. If her pings fall to the general floor (where stale answers hit 20.7%), floor-wide stale answers will jump from **12.7% to ~18%**.
5. **Onboarding Latency**: New-joiner time-to-proficiency (TTP)—the time needed to sustain 4 consecutive weeks at $\ge 90\%$ accuracy—has stretched from **71 days to 87 days** ($n=11$ post-April 2026 cohort). New joiners suffer a **5.8% error rate** in their first 90 days and take **15.2 minutes per invoice** (vs 10.4 minutes for experienced staff).
6. **Quality Check (QC) Error Reconciliation**: Audits uncovered **339 processing errors (3.8% floor error rate)**:
   * **120 Superseded Rule Errors (35.4%)**: 82 price tolerance errors (applying old 2% / ₹1,000) + 38 e-invoice IRN errors (applying obsolete ₹10 Cr limit).
   * **101 TDS Section Errors (29.8%)**: Processors picking incorrect TDS sections (194C vs 194J) or calculating TDS on GST-inclusive amounts.
   * **10 Missed QA Releases (2.9%)**: Caused by the 2023 FAQ claiming excipients do not need QA release, contradicting Client Memo **CM-PHA-01**.

### The Core Problem (Abhisshek Raaj, EY)
> **"How do you collate all these information [email, Teams, video, PDF], these changes, put that back to the SOP and ensure that everyone is following the same document, same set of knowledge base for doing the processes?"**
>
> **"You need to capture it at the right moment. You need to ensure that it is updated and everyone has access to it."**
>
> **"Think of it: you have multiple sources of input: email, teams chat, video interaction, some PDF document... Now your work is to collate all that information and ensure that your process is up to date with all the knowledge."**

---

## 2. Hybrid Platform Architecture (v5.0)

The solution is a **Generic Dual-Clock Temporal Knowledge Engine** with **Industry Plug-ins**. Meridian AP is the first plug-in.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                    MERIDIAN KNOWLEDGE ENGINE PLATFORM (v5.0)                           │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ LAYER 0: LIVE CAPTURE CONNECTORS (Solves: "Capture at the Right Moment")              │
│   • Email (IMAP/Graph API) • Teams Bot (Live Msg + Webhook)                            │
│   • Meeting Bot (Teams/Zoom/Meet + faster-whisper + pyannote)                          │
│   • Drive/SharePoint Watcher (Graph API) • Upload API                                  │
│   • Live PII Redaction (Audio + Text) • Speaker Authority Weighting                    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ LAYER 1: UNIFIED INGESTION PIPELINE (Background Workers — Postgres SKIP LOCKED)        │
│   • 5-Tier Parser → Unified Block List (styles, headings, tables, transcript turns)    │
│   • Structure Repair (AI assigns heading levels if flat)                               │
│   • File Type Detection (libmagic) • LibreOffice Headless for Legacy                   │
│   • Entity/Topic Extraction (Learns Schema • Owner Reviews Once)                       │
│   • Fact Extraction + Dual Clocks (Valid Time + Transaction Time)                      │
│   • Source Authority Ranking (Type > Version > Status)                                 │
│   • 4-Case Conflict Resolution → Atomic Graph Write (Close Old + Open New)             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ LAYER 2: DUAL-CLOCK TEMPORAL KNOWLEDGE GRAPH (Postgres Native — No Zep/Graphiti)      │
│   • Episodes → Blocks → Entities → Facts (valid_from/to + recorded_at/retracted_at)    │
│   • Range Indexes (GiST) on Both Clocks • Vector Indexes (HNSW) on Embeddings         │
│   • Full-Text + Fuzzy Name (pg_trgm) • Tenant Isolation (tenant_id on Every Table)    │
│   • Repository Layer: All Graph R/W Through app/store/ — Storage Engine Swappable      │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ LAYER 3: 3-LANE EXECUTION & CONFLICT RESOLUTION ENGINE                                 │
│   • Lane 1 (Computable 54%): 6 Deterministic Python Calculators (Params from Graph)    │
│   • Lane 2 (Lookup 28%): Hybrid Retrieval (Keyword + Vector + Graph Walk → RRF → Rerank)│
│   • Lane 3 (Judgment 18%): classify_tds Pre-Triage; Side-by-Side Rules vs. Practices   │
│   • Router: Calculator / Lookup / Judgment / Refuse                                    │
│   • Conflict Scanner: 4-Case Detection (Direct, Drift, Scope, Authority)               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ LAYER 4: VERIFIED ANSWER ENGINE & ESCALATION LOOP                                      │
│   • Answer Builder: Citations + Calculator Outputs + Older Sources Line + Expert Tips  │
│   • 4-Check Verifier: Citations Real • Numbers Sourced • No Superseded • Sentences OK  │
│   • Escalation Loop: Unanswered → Owner Review → Approves → Becomes Fact (Live)        │
│   • 7 Guardrails: Scope • Closed-Book • Retrieval Gate • Verifier • Deterministic      │
│     • Injection Resistance • Audit Trail                                               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ LAYER 5: DELIVERY & SOP SYNC (Solves: "30 Sec at Point of Work" + "Put Back to SOP")  │
│   • Delivery: REST API + WS • Teams App • ERP Embed • Browser Extension • Webhooks    │
│   • SOP Sync: Change Detection → Redline → Push (SharePoint/Git) → Notify → Ack Track │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. The 8 Platform Capabilities (Replacing v4.2's 6 Fixes)

| # | Capability | Solves | Implementation |
|---|---|---|---|
| **1** | **Live Multi-Source Ingestion** | "Capture at the right moment" — Email, Teams, Meetings, Drive | Layer 0: Connectors + Background Workers |
| **2** | **Dual-Clock Temporal Graph** | "Never present outdated rule" — Valid Time + Transaction Time | Layer 2: Postgres Native (GiST ranges) |
| **3** | **Authority > Recency** | "Stale FAQ never overrides current SOP" | Layer 1: Source Type > Version > Status ranking |
| **4** | **Deterministic Calculators** | "0% math hallucination" — Params from Graph | Layer 3 Lane 1: 6 AP Calculators reading Facts |
| **5** | **Verified Answers + Escalation** | "Only answer from KB, escalate rest" | Layer 4: 4-Check Verifier + Live Owner Loop |
| **6** | **In-Workflow Delivery** | "30 seconds at point of work" | Layer 5: ERP Embed, Teams App, Browser Ext |
| **7** | **SOP Sync (Write-Back)** | "Put changes back to SOP" | Layer 5: Redline → SharePoint/Git → Ack Track |
| **8** | **Generic Core + Plug-ins** | "Works for any company, not just Meridian" | Layer 2-4: Zero Meridian code in core |

---

## 4. Claim-Based Knowledge Units & 3-Lane Execution Engine

Knowledge is stored as **Facts** with **Dual Clocks**:

$$\text{Fact} = \langle \text{subject\_entity}, \text{predicate}, \text{object\_value}, \text{valid\_from}, \text{valid\_to}, \text{recorded\_at}, \text{retracted\_at}, \text{authority\_rank}, \text{source\_type}, \text{status} \rangle$$

### 3-Lane Routing Flow (Meridian AP Plug-in)

```
┌─────────────────────────┐   ┌─────────────────────────┐   ┌─────────────────────────┐
│ LANE 1: COMPUTABLE      │   │ LANE 2: LOOKUP          │   │ LANE 3: JUDGMENT/TACIT  │
│ (54% · 1,025 Pings)     │   │ (28% · 526 Pings)       │   │ (18% · 349 Pings)       │
├─────────────────────────┤   ├─────────────────────────┤   ├─────────────────────────┤
│ • Price Variance        │   │ • GSTR-2B Reconcile     │   │ • TDS Section Triage    │
│ • E-Invoice Thresholds  │   │ • Non-PO Categories     │   │ • Infra GRN Batching    │
│ • Approval Hierarchy    │   │ • Pharma QA Release     │   │ • RCM Tax Reviews       │
│ • MSME Payment Runs     │   │ • Bank Change Callbacks │   │ • Senior Floor Habits   │
│ • Duplicate Normalize   │   │ • General Policy Lookup │   │ • Ambiguous AMC         │
├─────────────────────────┤   ├─────────────────────────┤   ├─────────────────────────┤
│ MECHANISM:              │   │ MECHANISM:              │   │ MECHANISM:              │
│ 6 Python Calculators    │   │ Hybrid Retrieval        │   │ classify_tds Pre-Triage;│
│ Reading Params from     │   │ (Keyword + Vector +     │   │ Abstain on Mixed AMCs;  │
│ Temporal Graph Facts    │   │  Graph Walk → RRF →     │   │ Side-by-Side Practice   │
│ (NEVER Hardcoded)       │   │  Rerank → Top-6)        │   │ (Authority_Rank=3)      │
└─────────────────────────┘   └─────────────────────────┘   └─────────────────────────┘
```

### Side-by-Side Principle (Acceptance Test T4)
On **Saturday Infra invoice with no GRN**, engine presents:
1. **Rule (Authority=2)**: SOP v4.0 §4.6 — Hold as `NO_GRN`, remind 2 days, escalate 5 days
2. **Practice (Authority=3)**: Lakshmi Interview [02:30] & [05:18] — Sites batch GRNs Monday, wait until Tuesday noon
3. **Presentation**: SIDE_BY_SIDE — Practice annotates Rule, never overrides control hierarchy

---

## 5. Evaluation Benchmark & Acceptance Test Matrix (T1–T10)

| Test | Scenario | Expected Behaviour | Status Target |
|---|---|---|---|
| **T1** | Price tolerance query | Lower of 1% or ₹500 (SOP v4.0 §4.2); notes superseded 2%/₹1,000 | **PASS** |
| **T2** | ₹8.9 Cr vendor without IRN | Rejects under ₹5 Cr threshold; rejects obsolete ₹10 Cr rule | **PASS** |
| **T3** | Pharma excipient QA release | Requires QA release per CM-PHA-01; flags 2023 FAQ error | **PASS** |
| **T4** | Saturday Infra no GRN | SOP v4.0 §4.6 SIDE-BY-SIDE with Lakshmi Tuesday-noon practice | **PASS** |
| **T5** | PO ₹395, Invoice ₹400 (500 bags) | Excess ₹2,500 vs limit ₹500 → `PRICE_VAR` | **PASS** |
| **T6** | TDS on software ₹4.8L + GST | 194J @ 2% = ₹9,600 (excludes GST) | **PASS** |
| **T7** | Micro supplier accepted 1 Aug | Due 16 Aug (15d cap) → Friday 14 Aug payment run | **PASS** |
| **T8** | Canteen subsidy (out of corpus) | Abstains → routes to Sandeep Rao | **PASS** |
| **T9** | Corpus-wide conflict scan | Detects ≥12 of 15 planted conflicts (4-case detector) | **PASS** |
| **T10** | Tacit capture card TTL | Creates habit cards with mandatory 6-month review date | **PASS** |

### Platform-Level Benchmarks (Beyond Meridian)

| Benchmark | Target | Purpose |
|---|---|---|
| **Ragas Faithfulness** | ≥0.95 | Zero hallucination |
| **Ragas Answer Relevance** | ≥0.95 | Crisp, contextual answers |
| **Ragas Context Precision** | ≥0.90 | Exact claims, no text noise |
| **Ragas Harmfulness** | 0.00 | 100% PII masking (DPDP) |
| **Second Company Test** | 10/10 Qs | Generic core, no code changes |
| **Format Ablation** | ≥0.9 similarity | Any format → same facts |
| **Temporal Replay** | 100% correct | As-of queries at any date |
| **Ablation Gain** | Full > Vector+15% | Each layer adds measurable value |

---

## 6. Deployment Architecture (v5.0 — Replaces Zoho Catalyst)

```
meridian-knowledge-engine/
├── .github/workflows/              # CI/CD (GitHub Actions)
├── docker/                         # Multi-stage Dockerfiles
│   ├── api.Dockerfile              # FastAPI + Uvicorn
│   ├── worker.Dockerfile           # Background Workers + ML Models
│   └── docker-compose.yml          # Local Dev Stack
├── docs/                           # 13 Specification Documents
├── app/                            # FastAPI Application (Python 3.11)
│   ├── models/                     # SQLAlchemy (10 Tables)
│   ├── schemas/                    # Pydantic (API Contracts)
│   ├── api/routes/                 # REST + WebSocket Endpoints
│   ├── core/                       # Ingestion, Retrieval, Answer, Calculators
│   ├── store/                      # Repository Layer (All DB Access)
│   ├── gateways/                   # LLM, Embeddings, PII
│   └── workers/                    # Job Processors (SKIP LOCKED)
├── web/                            # Next.js 14 (Vercel)
│   ├── src/app/                    # App Router (Processor, Owner, Tacit)
│   └── src/components/             # AnswerCard, RedlineDashboard, etc.
├── tests/                          # Unit, Acceptance, Eval, Generality
├── scripts/                        # Seed, Load, Eval, Replay
├── alembic/                        # Postgres Migrations
└── requirements*.txt               # Core, ML, Dev Dependencies
```

### Target Infrastructure

| Component | Provider | Specification |
|---|---|---|
| **API Server** | Render | Docker, 2+ instances, Auto-scale, WebSocket |
| **Background Workers** | Render | Docker, 4+ instances, Horizontal, SKIP LOCKED Queue |
| **Web App** | Vercel | Next.js 14, Edge Functions, Global CDN |
| **Database** | Neon | Postgres 16 + pgvector + pg_trgm + btree_gist |
| **Cache/Rate Limit** | Upstash Redis | Serverless, LLM Cache, Rate Limiting |
| **File Storage** | Cloudflare R2 | S3-compatible, Episode Files, Redlines |
| **LLM** | Anthropic | Claude Haiku (triage) + Sonnet (extraction/answer/verify) |
| **Embeddings** | Local CPU | BGE-small-en-v1.5 + BGE-reranker-base (Zero API Cost) |
| **Transcription** | Local GPU | faster-whisper (Meeting Bot) |
| **Diarization** | Local GPU | pyannote.audio (Speaker Authority) |

---

## 7. ROI & Business Metrics (Meridian AP)

| Metric | Baseline | Target | Value |
|---|---|---|---|
| **Parked Waiting Hours** | 1,219 hrs (6 months) | 914–1,097 hrs saved | ₹2.1–2.5 Cr/yr |
| **Superseded-Rule QC Errors** | 120 errors | 90–108 prevented | ₹1.8–2.2 Cr/yr |
| **MSME Tax Exposure** | 245 late invoices (₹3.4 Cr) | 0 late payments | ₹3.4 Cr protected |
| **Onboarding TTP** | 87 days | ≤72 days (-15 days) | 11 FTE-months/yr |
| **Payback Period** | — | **4.9 Months** | Based on waste reduction |

### Platform Value (Beyond Meridian)
- **Marginal Cost per Tenant**: Near-zero (shared core, plug-in only)
- **Time to New Plug-in**: Weeks not months (ontology + calculators only)
- **Generality Proven**: Second company 10/10, Format ablation ≥0.9, Temporal replay 100%

---

## 8. Migration from v4.2 (Zoho Catalyst) → v5.0 (Platform)

| v4.2 Component | v5.0 Replacement | Rationale |
|---|---|---|
| Zoho Catalyst AppLogic | Render Docker (FastAPI) | Managed, scalable, standard Python |
| Zoho Catalyst Node.js | Removed (FastAPI handles all) | Single runtime, less complexity |
| Zep/Graphiti | Postgres Native (Dual-Clock) | Single DB, GiST ranges, tenant isolation |
| Multi-LLM (LiteLLM) | Anthropic Only (Haiku/Sonnet) | Two-model tiering, simpler, cheaper |
| ConflictRAG (MLP+TOPSIS) | 4-Case Deterministic + TOPSIS | Auditable, owner-controllable |
| Zingg Entity Resolution | Supplier Normalizer + Graph Facts | Deterministic, params from graph |
| Catalyst Circuits | Postgres SKIP LOCKED Queue | No vendor lock-in, transactional |
| Catalyst Data Store | Neon Postgres (pgvector) | Managed, scale, vector + graph + text |
| React/Vite | Next.js 14 (Vercel) | App Router, Edge, better DX |

---

## 9. Next Actions

1. **Approve v5.0 Spec** — Team sign-off on `HYBRID_SPEC.md` as single source of truth
2. **Initialize Repo** — Create structure per `STARTER_REPO_CONFIG.md`
3. **Phase 0 Sprint** — Foundation: Postgres schema, FastAPI skeleton, Worker, Repository Layer
4. **Phase 1 Sprint** — Ingestion Core: 5-Tier Parser, Structure Repair, Extractor, Authority, Conflict, Graph Writer
5. **Phase 2 Sprint** — Retrieval & Answer: Hybrid Search, Router, Builder, Verifier, Escalation
6. **Phase 3 Sprint** — AP Plug-in: 6 Calculators, Ontology, Router Integration
7. **Phase 4 Sprint** — Acceptance: T1-T10, 160-Q Ragas, Generality Proofs
8. **Phase 5+ Sprints** — Live Capture, Delivery, SOP Sync (Abhisshek's Million-Dollar Problem)

**The v4.2 architecture solved "Static Document RAG on Zoho Catalyst."  
The v5.0 platform solves "Live Knowledge Capture, Verified Answers, In-Workflow Delivery, SOP Sync — for Any Company."**