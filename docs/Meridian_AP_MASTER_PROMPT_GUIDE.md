# MERIDIAN SHARED SERVICES · ENTERPRISE KNOWLEDGE ENGINE
## Master AI Coding Prompt Guide (`Meridian_AP_MASTER_PROMPT_GUIDE.md`)

---

## 1. How to Use This Prompt Guide

This document contains **production-grade master prompts** designed to instruct any advanced AI coding assistant (Claude 3.5 Sonnet, GPT-4o, Cursor, Devin, GitHub Copilot) to implement the **Meridian Knowledge Engine Platform** from scratch.

**Key Architecture Shift**: This is a **Generic Core + Industry Plug-in** platform. Meridian AP is the FIRST plug-in. The core knows nothing about AP, tax, or invoices.

When initiating development, supply the technical specification files from `/docs/` alongside the relevant master prompt below.

**Reference Documents** (in order of dependency):
1. `Meridian_AP_HYBRID_SPEC.md` — **Single source of truth** (read first)
2. `Meridian_AP_PRD.md` — Product requirements & acceptance criteria
3. `Meridian_AP_SYSTEM_ARCHITECTURE.md` — 6-layer architecture, LLM gateway, retrieval
4. `Meridian_AP_DB_SCHEMA_AND_GRAPH.md` — Dual-clock Postgres schema, ontology
5. `Meridian_AP_CALCULATORS_AND_TRIAGE_SPEC.md` — 6 deterministic calculators (AP plug-in)
6. `Meridian_AP_API_SPECIFICATION.md` — REST + WebSocket API contracts
7. `Meridian_AP_DEPLOYMENT.md` — Docker, Render, Vercel, Neon deployment
8. `Meridian_AP_EVALUATION_AND_TESTING_SUITE.md` — T1-T10, Ragas, Generality proofs

---

## 2. Master System Generation Prompt

```markdown
SYSTEM INSTRUCTION:
You are an Expert Lead Systems Architect and Senior Full-Stack AI Engineer. Your goal is to build the production codebase for the "Meridian Knowledge Engine Platform" — a Generic Dual-Clock Temporal Knowledge Engine with Industry Plug-ins, deployed on Docker (Render API + Worker, Vercel Web, Neon Postgres).

The platform has TWO layers:
1. GENERIC CORE: Ingestion pipeline, dual-clock temporal graph, hybrid retrieval, verified answer engine, escalation loop, live capture connectors, delivery layer, SOP sync. Knows NOTHING about any industry.
2. INDUSTRY PLUG-INS: Domain-specific calculators, ontology, authority ranking, routers. Meridian AP is the first plug-in.

Refer strictly to the specification documents in `/docs/`, especially `Meridian_AP_HYBRID_SPEC.md` as the single source of truth.

### Core Engineering Requirements:

1. **Generic Core — Dual-Clock Temporal Graph (Postgres Native)**
   - Tables: tenants, episodes, blocks, entities, facts (valid_from/to + recorded_at/retracted_at), conflicts, jobs, answer_logs, users
   - Repository Layer: ALL graph R/W through `app/store/` — storage engine swappable
   - Atomic Writes: Close old fact (retracted_at=now) + Open new fact in single transaction
   - Authority Ranking: Configurable per tenant (source_type > version > status)
   - 4-Case Conflict Detection: Direct contradiction, Parameter drift, Scope overlap, Authority clash

2. **Generic Core — Unified Ingestion Pipeline (Background Workers)**
   - 5-Tier Parser → Unified Block List (heading, paragraph, table_row, transcript_turn, slide)
   - Structure Repair: Haiku assigns heading levels if flat
   - File Type Detection: libmagic (content, not extension)
   - Entity/Topic Extraction: Sonnet learns schema; Owner reviews ONCE
   - Fact Extraction + Dual Clocks
   - Source Authority Ranking → 4-Case Conflict Resolution → Atomic Graph Write
   - Postgres Queue: SELECT FOR UPDATE SKIP LOCKED (no Redis/Celery)

3. **Generic Core — Hybrid Retrieval & Verified Answer Engine**
   - Router: Calculator / Lookup / Judgment / Refuse
   - Hybrid Search: Keyword (pg_trgm) + Vector (HNSW) + Graph Walk → RRF Merge → BGE Rerank → Top-6
   - Time-Aware: valid_from ≤ as_of ≤ valid_to
   - Scope-Aware: General + Asker's client desk only
   - Answer Builder: Citations + Calculator Outputs + Older Sources Line + Expert Tips
   - 4-Check Verifier: Citations real • Numbers sourced • No superseded • Sentences supported
   - Escalation Loop: Unanswered → Owner Review → Approves → Becomes Fact (Live)
   - 7 Guardrails: Scope • Closed-Book • Retrieval Gate • Verifier • Deterministic • Injection Resistance • Audit Trail

4. **LLM Gateway — Anthropic Only (Two-Model Tiering)**
   - Haiku: Triage, routing, structure repair, schema learning, classification (cheap/fast)
   - Sonnet: Extraction, answer generation, verification (strong reasoning)
   - Single Gateway: PII redaction, logging, caching, retry logic
   - NO multi-provider abstraction (LiteLLM removed)

5. **Embeddings & Search — Local CPU (Zero API Cost)**
   - BGE-small-en-v1.5 (384 dims) for embeddings
   - BGE-reranker-base for reranking
   - pgvector HNSW indexes + pg_trgm + GiST range indexes

5. **AP Industry Plug-in — 6 Deterministic Calculators (Params from Graph)**
   - `calculate_price_variance` — reads `price_tolerance` fact
   - `classify_tds` — pure logic, returns TDS_SECTION_UNCLEAR for mixed AMCs
   - `calculate_tds` — reads `tds_rate` fact, excludes GST, enforces 20% no-PAN
   - `calculate_msme_due_date` — reads `msme_cap` + `payment_run_days` facts
   - `validate_e_invoice_requirement` — reads `e_invoice_threshold` fact
   - `normalize_supplier_string` — pure string logic
   - Router maps queries to calculators via keyword + LLM classification

6. **Live Capture Connectors (Phase 5+)**
   - Email: IMAP + Microsoft Graph API webhook
   - Teams: Bot + webhook, thread context
   - Meeting: Teams/Zoom/Meet bot → faster-whisper + pyannote diarization
   - Drive/SharePoint: Graph API change notifications
   - Live PII Redaction: Audio + text streams

7. **Delivery Layer (Phase 6+)**
   - REST API + WebSocket
   - Teams App (Bot + Message Extension + Tab)
   - ERP Embed (Generic iframe/sidebar + Meridian injector)
   - Browser Extension (Content script + sidebar)
   - Change Notification Webhooks

8. **SOP Sync Layer (Phase 7+)**
   - Change Detection → Redline Generator → Push (SharePoint/Git) → Notify → Ack Track

9. **Testing & Evaluation**
   - T1-T10 Acceptance Tests (MUST PASS)
   - 160-Question Ragas Suite (Faithfulness≥0.95, Relevance≥0.95, Precision≥0.90, Harm=0)
   - Generality Proofs: Second company (10/10), Format ablation (≥0.9), Temporal replay, Ablation study

### Tech Stack (Fixed — Do Not Deviate):
- **API**: FastAPI 0.115, Python 3.11, Pydantic v2, SQLAlchemy 2, Uvicorn
- **DB**: Postgres 16 + pgvector + pg_trgm + btree_gist (Neon)
- **Queue**: Postgres SKIP LOCKED (no Celery/Redis for jobs)
- **LLM**: Anthropic Claude (Haiku + Sonnet only)
- **Embeddings**: BGE-small + BGE-reranker (CPU, local)
- **Parsing**: python-docx, openpyxl, python-pptx, PyMuPDF, BeautifulSoup, libmagic, LibreOffice headless
- **Transcription**: faster-whisper (CPU/GPU)
- **Diarization**: pyannote.audio
- **Web**: Next.js 14, TypeScript, Tailwind, Vercel
- **Deploy**: Docker on Render (API + Worker), Vercel (Web), Neon (DB)
- **CI/CD**: GitHub Actions

Begin by setting up the project scaffolding per `Meridian_AP_HYBRID_SPEC.md` Section 10 (Repo Structure). Implement Phase 0 (Foundation) first: Postgres schema, FastAPI skeleton, background worker, repository layer. Then Phase 1 (Ingestion Core), Phase 2 (Extraction & Graph), Phase 3 (AP Plug-in), Phase 4 (Acceptance Tests).
```

---

## 3. Phase-Based Sub-Task Prompts

### Phase 0: Foundation (Week 1-2)

#### Prompt 0.1 — Project Scaffolding & Database
```markdown
Create the complete repository structure per `Meridian_AP_HYBRID_SPEC.md` Section 10.

**Files to create:**
1. `docker-compose.yml` — Local stack (Postgres+pgvector, Redis, API, Worker, Web)
2. `docker/api.Dockerfile` & `docker/worker.Dockerfile` — Multi-stage builds
3. `requirements.txt`, `requirements-ml.txt`, `requirements-dev.txt`
4. `pyproject.toml` — Ruff, mypy, pytest config
5. `alembic/` — Migration environment
6. `app/main.py` — FastAPI app factory with lifespan
7. `app/config.py` — Pydantic Settings (all env vars from DEPLOYMENT.md)
8. `app/database.py` — Async engine, session, Base
9. `app/models/` — SQLAlchemy models for ALL 10 tables (Section 3 of DB_SCHEMA)
10. `app/store/` — Repository classes (episodes, blocks, entities, facts, conflicts, jobs, answers)
11. `alembic/versions/001_initial_schema.py` — Full DDL from DB_SCHEMA.md
12. `scripts/init-extensions.sql` — Enable pgvector, pg_trgm, btree_gist, uuid-ossp

**Verify:** `docker-compose up -d` → `alembic upgrade head` → `SELECT * FROM pg_extension WHERE extname IN ('vector','pg_trgm','btree_gist')` returns 4 rows.
```

#### Prompt 0.2 — Background Worker (Postgres SKIP LOCKED)
```markdown
Implement `app/workers/main.py` — Generic background job processor using Postgres advisory locks.

**Requirements:**
- `JobProcessor` class: polls `jobs` table with `SELECT FOR UPDATE SKIP LOCKED`
- Concurrency: `WORKER_CONCURRENCY` parallel tasks (asyncio.Semaphore)
- Retry logic: Exponential backoff, max `JOB_MAX_ATTEMPTS`
- Job types: `ingest`, `extract`, `conflict_scan`, `sop_sync`, `notification`
- Graceful shutdown: SIGTERM handling, finish current job
- Metrics: Job duration, success/failure rates, queue depth

**Job Handler Interface:**
```python
class JobHandler(ABC):
    @property
    @abstractmethod
    def job_type(self) -> str: ...
    
    @abstractmethod
    async def handle(self, payload: dict, job_id: UUID) -> dict: ...
```

Register handlers in `app/workers/registry.py`.
```

---

### Phase 1: Ingestion Core (Week 2-3)

#### Prompt 1.1 — 5-Tier Parser → Unified Block List
```markdown
Implement `app/core/ingestion/parser.py` — Single entry point for all document types.

**5 Parsers → Unified `BlockList[Block]`:**
1. **Word** (`python-docx`): Preserve styles, heading levels, table structure, header/footer
2. **Excel** (`openpyxl` + `pandas`): Each sheet → blocks, tables → table_row blocks
3. **PDF** (`PyMuPDF`): Text blocks, tables (pdfplumber), structure from font sizes
4. **PowerPoint** (`python-pptx`): Slides → slide blocks, shapes → text blocks
5. **Email/Chat/Transcript**: Turns → transcript_turn blocks with speaker, timestamp

**Block Dataclass:**
```python
@dataclass
class Block:
    block_type: Literal["heading", "paragraph", "table_row", "transcript_turn", "slide"]
    heading_path: list[str]  # ["4", "2"] for §4.2
    heading_level: int       # 1, 2, 3
    content: str
    metadata: dict           # {speaker, timestamp, row_data, slide_num}
    char_start: int
    char_end: int
```

**File Type Detection:** `python-magic` (libmagic) — NOT extension-based.
**LibreOffice Headless:** Convert legacy .doc/.xls/.ppt to modern formats first.
**Output:** `BlockList` — list of Blocks with global char positions for citation highlighting.
```

#### Prompt 1.2 — Structure Repair (AI Heading Assignment)
```markdown
Implement `app/core/ingestion/structure_repair.py` — Fix flat outlines using Haiku.

**When:** Parser detects heading_level is None or all blocks are paragraphs.
**Action:** Send blocks to Haiku with prompt:
```
Assign heading levels (1-3) and heading paths to these text blocks.
Preserve explicit numbering (4.2, 4.2.1). Infer hierarchy from font size, bold, position.
Return JSON: [{"block_index": 0, "heading_level": 2, "heading_path": ["4", "2"]}, ...]
```
**Fallback:** Heuristic based on font size, bold, numbering patterns.
**Owner Review:** Flag repaired structures for owner confirmation (once per document type).
```

#### Prompt 1.3 — Entity/Topic Extraction (Schema Learning)
```markdown
Implement `app/core/ingestion/extractor.py` — Learn company's ontology automatically.

**Step 1 — Entity Extraction (Sonnet):**
- Input: BlockList + Document context
- Output: Entities with type, name, canonical_name, metadata
- Types: client, vendor, policy, invoice, regulation, person

**Step 2 — Topic/Predicate Discovery (Sonnet):**
- Input: Entities + Blocks
- Output: Predicates (price_tolerance, tds_section, etc.) with expected object_type

**Step 3 — Fact Extraction (Sonnet):**
- Input: Entities + Predicates + Blocks
- Output: Facts with dual clocks (valid_from, valid_to, recorded_at=now)
- Structured object_value (JSON for params, string for classifications)

**Step 4 — Owner Review (Once):**
- Present discovered entities/predicates to owner
- Owner confirms/renames/merges
- Save as tenant's "baseline schema" for future auto-extraction

**Caching:** Cache extraction results by content_hash. Rebuild = free.
```

#### Prompt 1.4 — Source Authority Ranking & Conflict Resolution
```markdown
Implement `app/core/ingestion/authority.py` and `conflict.py`.

**Authority Ranking (Config per Tenant):**
```python
AUTHORITY_RANKING = {
    "client_memo": 1,
    "sop_v4": 2,
    "desk_instruction": 2,
    "expert_interview": 3,
    "approved_practice": 3,
    "sop_v3": 4,
    "faq_2023": 4,
    "meeting": 5,      # Dynamic: weighted by speaker role
    "email": 5,        # Dynamic: weighted by sender role
    "chat": 5,         # Dynamic: weighted by sender role
}
```

**4-Case Conflict Detection (`conflict.py`):**
1. **Direct Contradiction**: Same subject+predicate, different values, overlapping valid time
2. **Parameter Drift**: Same predicate, value changed > threshold (configurable %)
3. **Scope Overlap**: Client memo + general rule for same predicate, different values
4. **Authority Clash**: Same authority_rank, conflicting values

**Resolution:**
- Cases 1,3: Auto-resolve (lower rank wins, retract higher)
- Cases 2,4: Create `Conflict` record, notify owner via Redline Dashboard
```

#### Prompt 1.5 — Atomic Graph Writer
```markdown
Implement `app/core/ingestion/graph_writer.py` — Single transaction: Close Old + Open New.

```python
async def upsert_facts(session: AsyncSession, new_facts: list[FactCreate]) -> list[Fact]:
    async with session.begin():
        for fact in new_facts:
            # 1. Retract conflicting facts (same subject+predicate, overlapping valid time)
            await session.execute(
                update(Fact)
                .where(
                    Fact.subject_entity_id == fact.subject_entity_id,
                    Fact.predicate == fact.predicate,
                    Fact.valid_from <= fact.valid_to or fact.valid_to.is_(None),
                    Fact.valid_to >= fact.valid_from,
                    Fact.retracted_at.is_(None)
                )
                .values(retracted_at=func.now(), status='superseded')
            )
            # 2. Insert new fact
            new = Fact(**fact.model_dump(), recorded_at=func.now())
            session.add(new)
        await session.flush()
        return [f for f in new_facts]
```
**Idempotent:** Same content_hash → no new facts created.
```

---

### Phase 2: Retrieval & Answer Engine (Week 3-4)

#### Prompt 2.1 — Hybrid Retrieval (Keyword + Vector + Graph)
```markdown
Implement `app/core/retrieval/hybrid.py` — Time-aware, scope-aware retrieval.

**Pipeline:**
1. **Graph First**: Link query → Entities → Pull current facts (valid_now, believed_now)
2. **Parallel Search**:
   - Keyword: pg_trgm similarity + full-text (tsvector)
   - Vector: HNSW cosine similarity (pgvector)
   - Graph: 1-2 hop expansion from query entities
3. **RRF Merge**: Score = Σ 1/(k + rank_i) where k=60
4. **Rerank**: BGE-reranker on Top-20 → Final Top-6
5. **Filters**: valid_from ≤ as_of ≤ valid_to, client_desk ∈ {general, asker's}

**Output:** `RetrievalResult` with passages, fact_ids, scores.
```

#### Prompt 2.2 — Router (3-Lane + Refuse)
```markdown
Implement `app/core/answer/router.py` — Classify query to Calculator / Lookup / Judgment / Refuse.

**Logic:**
- Calculator: Keyword match + LLM classification (Haiku) for computable queries
- Lookup: Default for factual questions
- Judgment: TDS classification, ambiguous contracts
- Refuse: Scope guard (out of corpus, chit-chat, advice)

**Calculator Mapping:**
```python
CALCULATOR_KEYWORDS = {
    "calculate_price_variance": ["price tolerance", "price variance", "price difference"],
    "classify_tds": ["tds section", "which section", "classify tds"],
    "calculate_tds": ["calculate tds", "tds amount", "tds on"],
    "calculate_msme_due_date": ["msme", "micro", "small enterprise", "due date", "payment run"],
    "validate_e_invoice_requirement": ["e-invoice", "einvoice", "irn", "threshold"],
    "normalize_supplier_string": ["normalize", "duplicate", "supplier string"]
}
```
```

#### Prompt 2.3 — Answer Builder + 4-Check Verifier
```markdown
Implement `app/core/answer/builder.py` and `verifier.py`.

**Answer Builder Output:**
```json
{
  "execution_lane": "COMPUTABLE|LOOKUP|JUDGMENT|ESCALATED|REFUSED",
  "status": "PASS|PRICE_VAR|IRN_MISSING|TDS_SECTION_UNCLEAR|ABSTAIN|...",
  "answer_markdown": "Human-readable with **bold** decisions",
  "math_result": {...},           // Calculator outputs
  "citations": [...],             // [{block_id, quote, fact_ids}]
  "older_sources": [...],         // Superseded rules for context
  "practice_notes": [...],        // Side-by-side tacit cards
  "verifier_result": {...}
}
```

**4-Check Verifier (Separate from Model):**
1. **Citations Real**: Every cited block_id exists AND quote is substring of block.content
2. **Numbers Sourced**: Every number in answer appears in citation OR calculator output
3. **No Superseded**: No citation with fact.status='superseded' presented as current
4. **Sentences Supported**: Each sentence has at least one citation OR calculator source

**Failure → Escalation:** Withhold answer, show "Not Covered" card with Escalate button.
```

#### Prompt 2.4 — Escalation Loop (Live Learning)
```markdown
Implement `app/core/answer/escalation.py` — Unanswered → Owner → Becomes Fact.

**Flow:**
1. Processor clicks "Escalate" on Not Covered card
2. Creates `Escalation` record with draft answer, routes to owner (by topic)
3. Owner Review UI: Sees draft, edits, sets authority_rank, sets TTL if tacit
4. Owner Approves → `upsert_facts()` → Fact becomes answerable immediately
5. Audit log: Who escalated, who approved, what changed

**Spoofing Protection:**
- Low-risk topic + registered owner → Provisional auto-approval
- High-risk (bank details, tax rates, approval limits) → ALWAYS owner review
```

---

### Phase 3: AP Plug-in (Week 4-5)

#### Prompt 3.1 — 6 Calculators (Params from Graph)
```markdown
Implement all 6 calculators in `app/core/calculators/` per `CALCULATORS_AND_TRIAGE_SPEC.md`.

**Critical:** Each calculator inherits `BaseCalculator`, implements `get_required_predicates()` and `calculate(ctx, inputs)`. Loads params via `FactRepository` at runtime.

**Test T1-T10** must pass with these implementations.
```

#### Prompt 3.2 — Meridian AP Ontology & Authority
```markdown
Implement `app/core/ontology/` — Entities, Predicates, Authority config for Meridian AP.

**Entities:** client (3), vendor (21+), policy (6), regulation (3), person (3)
**Predicates:** price_tolerance, tds_section, tds_rate, msme_cap, e_invoice_threshold, approval_limit, msme_category, aato_band, pan_available, qrmp_filer, habit_note, grn_status
**Authority:** As defined in DB_SCHEMA.md Section 4
```

---

### Phase 4: Acceptance Tests (Week 5-6)

#### Prompt 4.1 — T1-T10 Exact Implementation
```markdown
Implement `tests/acceptance/test_t1_t10.py` — Exact test cases from `EVALUATION_AND_TESTING_SUITE.md`.

**Each test:** Calls `/query/ask`, asserts exact fields (status, math_result, citations, older_sources, practice_notes).
**Run:** `pytest tests/acceptance/test_t1_t10.py -v` — ALL 10 MUST PASS.
```

#### Prompt 4.2 — 160-Question Ragas Evaluation
```markdown
Implement `tests/eval/test_ragas_eval.py` + `test_meridian_metrics.py`.

**Targets:** Faithfulness≥0.95, Relevance≥0.95, Precision≥0.90, Harm=0.00
**Meridian Metrics:** Answer Acc≥95%, Citation Acc≥90%, Outdated<5%, Escalation=100% when empty.
```

#### Prompt 4.3 — Generality Proof Tests
```markdown
Implement `tests/generality/` — Second company, Format ablation, Temporal replay, Ablation study.
**These prove the platform is GENERIC, not Meridian-specific.**
```

---

### Phase 5+: Live Capture, Delivery, SOP Sync (Week 6+)

#### Prompt 5.1 — Live Connectors
```markdown
Implement `app/core/live_capture/`:
- `email_connector.py` — IMAP + Graph API webhook
- `teams_bot.py` — Bot Framework + webhook, thread context
- `meeting_bot.py` — Teams/Zoom/Meet join, record, transcribe
- `transcriber.py` — faster-whisper wrapper (timestamps, confidence)
- `diarization.py` — pyannote wrapper (speaker labels + authority weight)
- `pii_redactor.py` — Audio + text redaction (PAN, bank, Aadhaar)
- `drive_watcher.py` — Graph API change notifications
```

#### Prompt 5.2 — Delivery Layer
```markdown
Implement delivery endpoints:
- `ERP Embed` — `/delivery/erp/embed` returns widget HTML + actions
- `Teams App` — Bot + Message Extension + Tab (adaptive cards)
- `Browser Extension` — Content script + sidebar (Manifest V3)
- `Webhooks` — Change notifications with HMAC signatures
```

#### Prompt 5.3 — SOP Sync
```markdown
Implement `app/workers/sop_sync_worker.py`:
- Change detection: Fact closed/new → trigger
- Redline generator: python-docx diff with tracked changes
- Push targets: SharePoint (Graph API), GitHub/GitLab (API)
- Notification + Acknowledgement tracking
```

---

## 4. Code Quality Standards

- **Type Hints**: 100% (mypy strict)
- **Linting**: Ruff (line-length=100, target-version=py311)
- **Tests**: pytest-asyncio, coverage≥80% on core modules
- **Documentation**: Docstrings on all public classes/methods
- **No Placeholders**: Every function implemented, no `pass` or `TODO`
- **Security**: PII redaction before ANY LLM call, parameterized SQL only
- **Observability**: Structured logging, OpenTelemetry traces, Prometheus metrics