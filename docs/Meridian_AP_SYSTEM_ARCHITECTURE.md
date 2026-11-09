# MERIDIAN SHARED SERVICES · ENTERPRISE KNOWLEDGE ENGINE
## Deep System Architecture — Generic Core + AP Plug-in
**Document ID**: `Meridian_AP_SYSTEM_ARCHITECTURE.md`  
**Target Environment**: **Docker on Render (API + Worker), Vercel (Web), Neon (Postgres 16 + pgvector + pg_trgm + btree_gist)**  
**LLM Layer**: **Anthropic Claude Only** — Haiku (triage/routing) + Sonnet (extraction/answer/verify)  
**Embeddings**: **BGE-small-en-v1.5 (CPU) + BGE Reranker** — Local, no API cost  
**Background Jobs**: **Postgres Queue** (`SELECT FOR UPDATE SKIP LOCKED`) — No Redis/Celery  

---

## 1. High-Level 6-Layer System Architecture

The solution treats organizational knowledge management as a **Governed Dual-Clock Temporal Knowledge Engine** with a **Generic Core** and **Industry Plug-ins**. Meridian AP is the first plug-in.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                    ENTERPRISE KNOWLEDGE ENGINE SYSTEM ARCHITECTURE                      │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ LAYER 0: LIVE CAPTURE CONNECTORS (NEW)                                                 │
│   • Email (IMAP/Graph API) • Teams Bot (Live Msg + Webhook)                            │
│   • Meeting Bot (Teams/Zoom/Meet + faster-whisper + pyannote)                          │
│   • Drive/SharePoint Watcher (Graph API) • Upload API                                  │
│   • Live PII Redaction (Audio + Text) • Speaker Authority Weighting                    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ LAYER 1: UNIFIED INGESTION PIPELINE (Background Workers)                               │
│   • 5-Tier Parser → Unified Block List (styles, headings, tables, transcript turns)    │
│   • Structure Repair (AI assigns heading levels if flat)                               │
│   • File Type Detection (libmagic, not extension) • LibreOffice Headless for Legacy    │
│   • Entity/Topic Extraction (Learns Schema • Owner Reviews Once)                       │
│   • Fact Extraction + Dual Clocks (Valid Time + Transaction Time)                      │
│   • Source Authority Ranking (Type > Version > Status)                                 │
│   • 4-Case Conflict Resolution → Atomic Graph Write (Close Old + Open New)             │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ LAYER 2: DUAL-CLOCK TEMPORAL KNOWLEDGE GRAPH (Postgres Native)                         │
│   • Episodes (Raw Inputs) → Blocks (Structural Units) → Entities → Facts              │
│   • Facts: subject_entity + predicate + object_value + valid_from/to + recorded_at/retracted_at │
│   • Range Indexes (GiST) on Both Clocks • Vector Indexes (HNSW) on Embeddings         │
│   • Full-Text + Fuzzy Name (pg_trgm) • Tenant Isolation (tenant_id on Every Table)    │
│   • Repository Layer: All Graph R/W Through app/store/ — Storage Engine Swappable      │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ LAYER 3: 3-LANE EXECUTION & CONFLICT RESOLUTION ENGINE                                 │
│   • Lane 1 (Computable 54%): 6 Deterministic Python Calculators (Params from Graph)    │
│   • Lane 2 (Lookup 28%): Hybrid Retrieval (Keyword + Vector + Graph Walk → RRF → Rerank)│
│   • Lane 3 (Judgment 18%): classify_tds Pre-Triage; Side-by-Side Rules vs. Practices   │
│   • Router: Calculator / Lookup / Judgment / Refuse (Out-of-Scope)                     │
│   • Conflict Scanner: 4-Case Detection (Direct, Drift, Scope, Authority)               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ LAYER 4: VERIFIED ANSWER ENGINE & ESCALATION LOOP                                      │
│   • Answer Builder: Citations + Calculator Outputs + Older Sources Line + Expert Tips  │
│   • 4-Check Verifier: Citations Real • Numbers Sourced • No Superseded • Sentences OK  │
│   • Escalation Loop: Unanswered → Owner Review → Approves → Becomes Fact (Live)        │
│   • 7 Guardrails: Scope • Closed-Book • Retrieval Gate • Verifier • Deterministic      │
│     • Injection Resistance • Audit Trail                                               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ LAYER 5: DELIVERY & SOP SYNC (NEW)                                                     │
│   • Delivery: REST API + WS • Teams App • ERP Embed • Browser Extension • Webhooks    │
│   • SOP Sync: Change Detection → Redline → Push (SharePoint/Git) → Notify → Ack Track │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. LLM Gateway (Single Provider — Anthropic Claude)

**No Multi-Provider Abstraction**. One gateway, two models, clear tiering:

```python
# app/gateways/llm.py
class LLMGateway:
    """Single gateway for all Anthropic Claude calls."""
    
    def __init__(self):
        self.haiku = Anthropic(model="claude-3-5-haiku-20241022")   # Cheap, fast
        self.sonnet = Anthropic(model="claude-3-5-sonnet-20241022") # Strong reasoning
        self.pii_redactor = PIIRedactor()
        self.call_log = CallLogger()
        self.cache = LRUCache(maxsize=10000)
    
    def route(self, task_type: str) -> Anthropic:
        """Route to appropriate model tier."""
        haiku_tasks = {"triage", "routing", "structure_repair", "schema_learning", 
                       "classification", "simple_extraction"}
        return self.haiku if task_type in haiku_tasks else self.sonnet
    
    async def complete(self, task_type: str, prompt: str, system: str = None, 
                       temperature: float = 0.0, **kwargs) -> str:
        # 1. Redact PII from prompt
        clean_prompt = self.pii_redactor.redact(prompt)
        # 2. Check cache
        cache_key = self._cache_key(task_type, clean_prompt, system, temperature)
        if cached := self.cache.get(cache_key):
            return cached
        # 3. Call model
        model = self.route(task_type)
        response = await model.complete(clean_prompt, system, temperature, **kwargs)
        # 4. Log & cache
        self.call_log.log(task_type, clean_prompt, response)
        self.cache.set(cache_key, response)
        return response
```

**Why This Works**:
- Haiku (~$0.25/M tokens) handles 70% of calls (triage, routing, structure)
- Sonnet (~$3/M tokens) handles 30% (extraction, answer, verification)
- Single provider = simpler prompts, no schema translation, no failover complexity
- Local embeddings (BGE-small) = $0 embedding cost

---

## 3. Rules vs. Practices Architecture (The Side-by-Side Principle)

The corpus contains two fundamentally distinct types of claims:

* **Rules** (Client Memos, SOP v4.0, Desk Instructions): Authoritative mandates with effective dates and owners. Compete hierarchically via `authority_rank` (1=Client Memo, 2=SOP v4.0/DI, 3=Tacit, 4=Superseded).
* **Practices** (Senior expert floor habits): What an experienced processor does *inside* a rule. Stored as Facts with `authority_rank=3`, `source_type=expert_interview`, `status=approved`, mandatory `review_by_date` (6-month TTL).

### Side-by-Side Execution Pattern (Acceptance Test T4)

On **Acceptance Test T4** (Infra invoice received Saturday with no GRN), the engine presents both claims side-by-side:

1. **Authoritative Rule (SOP v4.0 §4.6)**: Hold as `NO_GRN`. System sends automatic reminder after 2 working days, escalates after 5.
2. **Approved Expert Practice (Interview 1 [02:30] & [05:18])**: Infra sites batch GRNs Monday morning; wait until Tuesday noon before chasing.
3. **Control Guard**: Practice cards sit *beside* rules as annotations. They **never compete in or override** the rule control hierarchy. The processor sees both and decides.

```json
{
  "query": "Infra invoice Saturday no GRN. Chase Monday?",
  "client_desk": "Arvana Infra",
  "as_of_date": "2026-08-05",
  "answer": {
    "rule": {
      "claim": "Hold as NO_GRN. System reminds after 2 working days, escalates after 5.",
      "source": "SOP v4.0 §4.6",
      "authority_rank": 2,
      "valid_from": "2026-04-01"
    },
    "practice": {
      "claim": "Infra sites batch GRNs Monday morning. Wait until Tuesday noon before chasing.",
      "source": "Expert Interview 1 [02:30] & [05:18]",
      "authority_rank": 3,
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

## 4. Conflict Detection & Resolution (4 Cases, Not MLP)

Replaces ConflictRAG 2-Stage MLP with deterministic, auditable logic:

### 4-Case Conflict Detection

| Case | Trigger | Example |
|---|---|---|
| **1. Direct Contradiction** | Same subject + predicate, different values, overlapping `valid_from/to` | SOP v4.0: price_tol.cap=500 vs FAQ: price_tol.cap=1000 (both claim current) |
| **2. Parameter Drift** | Same predicate, value changed beyond threshold (configurable %) | price_tol.pct changed from 0.02 → 0.01 without version bump |
| **3. Scope Overlap** | Client memo + general rule for same predicate, different values | CM-INF-02: qty_tol=5% vs SOP v4.0 §4.3: qty_tol=0% |
| **4. Authority Clash** | Two sources same `authority_rank`, conflicting values | Two client memos for same desk, different values |

### Resolution Protocol

1. **Auto-Resolve** (Cases 1 & 3): Lower `authority_rank` wins. Higher rank fact gets `retracted_at = now()`, `status=superseded`. New fact written with `recorded_at = now()`.
2. **Flag for Owner** (Cases 2 & 4): Create `Conflict` record, notify Process Owner via Redline Dashboard. Owner resolves → system applies resolution.
3. **Audit Trail**: Every conflict, resolution, and owner decision logged in `conflicts` table.

### Entropy-TOPSIS (Retained for Credibility Scoring)

When auto-resolution isn't clear (e.g., same rank, same validity), credibility scored across:
- Authority ($w_1 = 0.312$) — Source type rank
- Recency ($w_2 = 0.245$) — `valid_from` date
- Relevance ($w_3 = 0.210$) — Predicate match strength
- Specificity ($w_4 = 0.133$) — Scope narrowness (client-specific > general)
- Consistency ($w_5 = 0.100$) — Cross-reference agreement

---

## 5. Ingestion Pipeline Details (12 Steps, 2 Stages)

### Stage 1: Build the Graph (Background Workers)

| Step | Operation | Key Tech |
|---|---|---|
| 1 | **Detect File Type** | `libmagic` (content-based, not extension) |
| 2 | **Parse → Unified Block List** | 5 Parsers → `BlockList[Block]` (heading, paragraph, table_row, transcript_turn, slide) |
| 3 | **Structure Repair** | Haiku assigns heading levels if flat outline |
| 4 | **Entity/Topic Extraction** | Sonnet learns company schema; Owner reviews once |
| 5 | **Fact Extraction + Dual Clocks** | Sonnet extracts `{subject, predicate, object, valid_from, valid_to}` |
| 6 | **Source Authority Ranking** | Config per tenant: type > version > status → `authority_rank` |
| 7 | **4-Case Conflict Check** | Compare new facts vs existing (same subject+predicate) |
| 8 | **Atomic Graph Write** | `BEGIN; UPDATE facts SET retracted_at=now() WHERE...; INSERT facts...; COMMIT;` |

### Stage 2: Answer Questions (Fast Path)

| Step | Operation | Key Tech |
|---|---|---|
| 9 | **Route** | Router: Calculator / Lookup / Judgment / Refuse |
| 10 | **Hybrid Retrieval** | Keyword (pg_trgm) + Vector (HNSW) + Graph Walk → RRF Merge → BGE Rerank → Top-6 |
| 11 | **Build Answer** | Citations + Calculator Outputs + Older Sources Line + Expert Tips |
| 12 | **4-Check Verifier** | Pass → Show; Fail → Escalate to Owner |

---

## 6. Retrieval Architecture (Hybrid, Time-Aware, Scope-Aware)

```
Query + Client Desk + As-Of Date
        │
        ▼
┌─────────────────────────────────────┐
│  GRAPH FIRST: Entity Linking        │
│  Link query → Entities (Client,     │
│  Vendor, Policy) → Pull Current     │
│  Facts (valid_from ≤ as_of ≤ valid_ │
│  to, retracted_at IS NULL)          │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│  HYBRID SEARCH (Parallel)           │
│  • Keyword: pg_trgm + Full-Text     │
│  • Vector: HNSW (cosine)            │
│  • Graph: 1-2 Hop Expansion         │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│  RECIPROCAL RANK FUSION (RRF)       │
│  Merge 3 ranked lists → Unified     │
│  Score = Σ 1/(k + rank_i)           │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│  RERANK (BGE Reranker)              │
│  Re-score Top-20 → Final Top-6      │
└─────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────┐
│  TIME + SCOPE FILTER                │
│  • valid_from ≤ as_of ≤ valid_to    │
│  • Client Desk = General + Asker's  │
│  • Superseded fetched separately    │
└─────────────────────────────────────┘
```

**Key Properties**:
- **Time-Aware**: Question about March 1 gets March 1 rules (valid time filter)
- **Scope-Aware**: Arvana Pharma query never sees Arvana Infra memos
- **Graph-First**: Facts pulled directly (structured values), not re-guessed from prose
- **Passages Structured**: Chunks follow sections, table rows, transcript turns — each carries header (doc, version, date, status)

---

## 7. Verification & Guardrails (7 Layers)

| Layer | Check | Failure Action |
|---|---|---|
| **1. Scope Guard** | General knowledge, chit-chat, advice beyond docs | Refuse before answer |
| **2. Closed-Book Writing** | Model sees ONLY retrieved passages + current facts + calculator outputs | Reject sentence without passage_id |
| **3. Retrieval Gate** | Best evidence score < threshold | Abstain → Escalate |
| **4. Verifier (4 Checks)** | 1. Every citation real & contains quote<br>2. Every number in source or calculator<br>3. No superseded value presented as current<br>4. Each sentence supported by citation | Withhold draft; Show "Not Covered" card + Escalate button |
| **5. Deterministic Numbers** | All math from calculators/graph — never model arithmetic | Hard constraint |
| **6. Injection Resistance** | Email/upload/expert reply text treated as DATA, never instructions | Prompt isolation |
| **7. Audit Trail** | Every answer, citations, verifier result logged | "Report Wrong Answer" → Owner Review Item |

---

## 8. Escalation Loop (Live Learning)

```
Processor Query → Retrieval Weak / Verifier Fails
                      │
                      ▼
          ┌───────────────────────┐
          │  NOT COVERED CARD     │
          │  • "I don't know"     │
          │  • Escalate Button    │
          │  • Routes to Owner    │
          └───────────┬───────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │  OWNER REVIEW UI      │
          │  • Sees Draft Answer  │
          │  • Edits / Approves   │
          │  • Sets Authority     │
          │  • Sets TTL (if tacit)│
          └───────────┬───────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │  BECOMES FACT         │
          │  • Atomic Graph Write │
          │  • Answerable Next Q  │
          │  • Audit Logged       │
          └───────────────────────┘
```

**Spoofing Protection**: Only registered owner of low-risk topic → provisional auto-approval. High-risk (bank details, tax rates) → always owner review.

---

## 9. Scaling & Pressure Handling

| Pressure | Mitigation |
|---|---|
| Many Documents Arriving | Background workers on Postgres queue. Horizontal workers. Failed jobs retry. Killed worker → same final graph (idempotent). |
| Cost of AI Extraction | Triage drops noise before extraction. New version re-extracts only changed passages (diff). Every result cached by input hash — rebuilds free. |
| Graph Growing Large | New fact compared only with related facts (same subject+predicate, or nearest neighbors), never whole graph. |
| Slow Queries | GiST range indexes on both clocks. HNSW vector indexes. Full-text + pg_trgm indexes. |
| Many Customers | `tenant_id` on every table from Day 1. Partitioning by tenant = later change, not rewrite. |
| Changing Database Later | All graph R/W through `app/store/` repository layer. Storage engine swappable. |
| Many Users Asking | Reads use consistent snapshot (Postgres MVCC). Reader mid-update sees old OR new state, never mix. |