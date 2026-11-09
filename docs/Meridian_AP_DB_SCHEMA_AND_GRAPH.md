# MERIDIAN SHARED SERVICES · ENTERPRISE KNOWLEDGE ENGINE
## Database Schema & Dual-Clock Temporal Graph Specification
**Document ID**: `Meridian_AP_DB_SCHEMA_AND_GRAPH.md`  
**Target Environment**: **PostgreSQL 16 + pgvector + pg_trgm + btree_gist** (Single Database, No External Graph Store)  
**Architecture**: **Repository Layer** (`app/store/`) — All Graph R/W Through Here, Storage Engine Swappable  

---

## 1. Core Design Principles

1. **Dual Clocks on Every Fact** — Valid Time (world) + Transaction Time (system)
2. **Never Overwrite** — Close Old (`retracted_at = now()`) + Open New (Atomic Transaction)
3. **Tenant Isolation** — `tenant_id` on Every Table from Day 1
4. **Authority Ranking** — Source Type > Version > Status (Lower Rank = Higher Authority)
5. **Repository Pattern** — All DB Access Through `app/store/` — Swappable Storage Engine

---

## 2. Complete Postgres Schema

```sql
-- ============================================================
-- EXTENSIONS (Enable First)
-- ============================================================
CREATE EXTENSION IF NOT EXISTS vector;        -- pgvector for embeddings
CREATE EXTENSION IF NOT EXISTS pg_trgm;       -- Fuzzy text matching
CREATE EXTENSION IF NOT EXISTS btree_gist;    -- GiST range indexes
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";   -- UUID generation

-- ============================================================
-- TENANTS (Multi-Company from Day 1)
-- ============================================================
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,                -- URL-safe identifier
    settings JSONB DEFAULT '{}',              -- Tenant-specific config
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- EPISODES (Raw Inputs: Documents, Emails, Meetings, Chats, Uploads)
-- ============================================================
CREATE TABLE episodes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    source_type TEXT NOT NULL,                -- 'document' | 'email' | 'meeting' | 'chat' | 'upload'
    source_id TEXT NOT NULL,                  -- Message ID, Document ID, Meeting ID, File Path
    source_metadata JSONB NOT NULL DEFAULT '{}', -- {from, to, subject, timestamp, participants, file_name, etc.}
    raw_content TEXT,                         -- Original text (PII-scrubbed version)
    content_hash TEXT NOT NULL,               -- SHA256 for deduplication
    status TEXT DEFAULT 'pending',            -- 'pending' | 'processing' | 'completed' | 'failed'
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    processed_at TIMESTAMPTZ
);
CREATE INDEX idx_episodes_tenant ON episodes(tenant_id);
CREATE INDEX idx_episodes_source ON episodes(source_type, source_id);
CREATE INDEX idx_episodes_status ON episodes(status) WHERE status IN ('pending', 'processing');
CREATE UNIQUE INDEX idx_episodes_dedup ON episodes(tenant_id, content_hash);

-- ============================================================
-- BLOCKS (Parsed Structural Units: Sections, Table Rows, Transcript Turns, Slides)
-- ============================================================
CREATE TABLE blocks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    episode_id UUID NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    block_type TEXT NOT NULL,                 -- 'heading' | 'paragraph' | 'table_row' | 'transcript_turn' | 'slide'
    heading_path TEXT[],                      -- ['4', '2'] for §4.2
    heading_level INT,                        -- 1, 2, 3...
    content TEXT NOT NULL,                    -- Block text content
    metadata JSONB DEFAULT '{}',              -- {speaker, timestamp, row_data, slide_num, etc.}
    char_start INT,                           -- Position in episode for citation highlighting
    char_end INT,
    embedding VECTOR(384),                    -- BGE-small-en-v1.5 embedding (384 dims)
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_blocks_tenant ON blocks(tenant_id);
CREATE INDEX idx_blocks_episode ON blocks(episode_id);
CREATE INDEX idx_blocks_embedding ON blocks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
CREATE INDEX idx_blocks_fts ON blocks USING gin (to_tsvector('english', content));
CREATE INDEX idx_blocks_heading ON blocks(tenant_id, heading_path);

-- ============================================================
-- ENTITIES (Domain Objects: Client, Vendor, Policy, Invoice, Regulation, Person)
-- ============================================================
CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    entity_type TEXT NOT NULL,                -- 'client' | 'vendor' | 'policy' | 'invoice' | 'regulation' | 'person'
    name TEXT NOT NULL,
    canonical_name TEXT,                      -- Normalized for matching (lowercase, no punctuation)
    metadata JSONB DEFAULT '{}',              -- Flexible attributes
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX idx_entities_tenant_type_canonical 
    ON entities(tenant_id, entity_type, canonical_name);
CREATE INDEX idx_entities_tenant ON entities(tenant_id);

-- ============================================================
-- FACTS (Core Knowledge: Dual-Clock Temporal Edges)
-- ============================================================
CREATE TABLE facts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    subject_entity_id UUID NOT NULL REFERENCES entities(id),  -- e.g., Vendor V20000
    predicate TEXT NOT NULL,                                          -- e.g., 'price_tolerance', 'tds_section', 'msme_category'
    object_value JSONB NOT NULL,                                      -- Structured: {"pct": 0.01, "cap": 500} or "194J"
    object_type TEXT NOT NULL,                                        -- 'json' | 'string' | 'number' | 'date' | 'boolean'
    
    -- VALID TIME (When true in the world)
    valid_from DATE NOT NULL,
    valid_to DATE,                                                    -- NULL = currently true
    
    -- TRANSACTION TIME (When system learned/retracted)
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    retracted_at TIMESTAMPTZ,                                         -- NULL = currently believed
    
    -- SOURCE & AUTHORITY
    source_episode_id UUID REFERENCES episodes(id),
    source_block_ids UUID[] NOT NULL DEFAULT '{}',                    -- Supporting block IDs
    source_type TEXT NOT NULL,                                        -- 'client_memo' | 'sop' | 'desk_instruction' | 'faq' | 'expert_interview' | 'meeting' | 'email' | 'chat'
    source_version TEXT,                                              -- 'v4.0', 'v3.1', '2023-10-09'
    source_status TEXT NOT NULL,                                      -- 'current' | 'superseded' | 'draft' | 'unreviewed'
    authority_rank INT NOT NULL,                                      -- Lower = Higher Authority (1=Client Memo, 2=SOP v4.0/DI, 3=Tacit, 4=Superseded)
    
    -- CONFIDENCE & GOVERNANCE
    confidence FLOAT DEFAULT 1.0,                                     -- Extraction confidence (0.0-1.0)
    status TEXT DEFAULT 'active',                                     -- 'active' | 'superseded' | 'retracted' | 'conflict' | 'pending_review'
    approved_by UUID,                                                 -- Owner who approved (references users table)
    approved_at TIMESTAMPTZ,
    review_by_date DATE,                                              -- For tacit cards (6-month TTL)
    
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_facts_tenant ON facts(tenant_id);
CREATE INDEX idx_facts_subject_predicate ON facts(subject_entity_id, predicate);
CREATE INDEX idx_facts_valid_time ON facts(valid_from, valid_to);
CREATE INDEX idx_facts_txn_time ON facts(recorded_at, retracted_at);
CREATE INDEX idx_facts_authority ON facts(authority_rank);
CREATE INDEX idx_facts_status ON facts(status) WHERE status IN ('active', 'conflict', 'pending_review');
-- GiST Range Index for Valid Time Queries (e.g., "what was rule on 2026-03-01?")
CREATE INDEX idx_facts_valid_range ON facts USING gist (
    tenant_id, 
    daterange(valid_from, COALESCE(valid_to, 'infinity'::DATE), '[]')
);
-- GiST Range Index for Transaction Time Queries (e.g., "what did engine know on 2026-11-10?")
CREATE INDEX idx_facts_txn_range ON facts USING gist (
    tenant_id,
    tsrange(recorded_at, COALESCE(retracted_at, 'infinity'::TIMESTAMPTZ), '[]')
);

-- ============================================================
-- CONFLICTS (Detected Contradictions for Owner Review)
-- ============================================================
CREATE TABLE conflicts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    fact_id_1 UUID NOT NULL REFERENCES facts(id),
    fact_id_2 UUID NOT NULL REFERENCES facts(id),
    conflict_type TEXT NOT NULL,                                      -- 'direct_contradiction' | 'parameter_drift' | 'scope_overlap' | 'authority_clash'
    severity TEXT NOT NULL,                                           -- 'critical' | 'high' | 'medium' | 'low'
    status TEXT DEFAULT 'open',                                       -- 'open' | 'resolved' | 'dismissed'
    resolution_notes TEXT,
    resolved_by UUID,                                                 -- Owner who resolved
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_conflicts_tenant ON conflicts(tenant_id);
CREATE INDEX idx_conflicts_status ON conflicts(status) WHERE status = 'open';

-- ============================================================
-- JOBS (Background Worker Queue — Postgres SKIP LOCKED)
-- ============================================================
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    job_type TEXT NOT NULL,                                           -- 'ingest' | 'extract' | 'conflict_scan' | 'sop_sync' | 'notification' | 'replay'
    payload JSONB NOT NULL,                                           -- Job-specific parameters
    status TEXT DEFAULT 'queued',                                     -- 'queued' | 'running' | 'completed' | 'failed' | 'retrying'
    attempts INT DEFAULT 0,
    max_attempts INT DEFAULT 3,
    error_message TEXT,
    scheduled_for TIMESTAMPTZ DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_jobs_tenant_status_scheduled 
    ON jobs(tenant_id, status, scheduled_for) 
    WHERE status IN ('queued', 'retrying');

-- ============================================================
-- ANSWER LOGS (Audit Trail for Every Query)
-- ============================================================
CREATE TABLE answer_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    query_text TEXT NOT NULL,
    client_desk TEXT,
    as_of_date DATE,
    route TEXT NOT NULL,                                              -- 'computable' | 'lookup' | 'judgment' | 'escalated' | 'refused'
    answer_markdown TEXT,
    citations JSONB,                                                  -- [{block_id, quote, fact_ids}]
    calculator_outputs JSONB,
    verifier_result JSONB,                                            -- {passed: bool, checks: {...}}
    escalated BOOLEAN DEFAULT false,
    escalation_reason TEXT,
    response_time_ms INT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_answer_logs_tenant ON answer_logs(tenant_id);
CREATE INDEX idx_answer_logs_created ON answer_logs(created_at);

-- ============================================================
-- USERS (For Approval Tracking)
-- ============================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    email TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT NOT NULL,                                               -- 'processor' | 'senior' | 'owner' | 'tax_lead' | 'admin'
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE UNIQUE INDEX idx_users_tenant_email ON users(tenant_id, email);
```

---

## 3. Meridian AP Ontology (Entities & Predicates)

### 3.1 Entity Types

| Entity Type | Canonical Name Examples | Key Metadata |
|---|---|---|
| `client` | `arvana_infra`, `arvana_pharma`, `arvana_retail` | `{industry: "infra|pharma|retail"}` |
| `vendor` | `v20000_balaji_logistics` | `{msme_category, aato_band, pan_available, qrmp_filer, habit_note}` |
| `policy` | `price_tolerance`, `tds_section`, `msme_due_date`, `e_invoice_threshold`, `approval_limit` | `{calculator: "price_variance|tds|msme|einvoice|approval"}` |
| `invoice` | `inv_2026_0042` | `{price_variance, tds_section, msme_due_date, grn_status, exception_code}` |
| `regulation` | `gst_act`, `income_tax_act`, `msmed_act` | `{section, rate, threshold}` |
| `person` | `lakshmi_reddy`, `imran_qureshi`, `sandeep_rao` | `{role, tenure, expertise_areas}` |

### 3.2 Key Predicates (Meridian AP)

| Predicate | Subject Type | Object Type | Example Value | Calculator |
|---|---|---|---|---|
| `price_tolerance` | policy | json | `{"pct": 0.01, "cap": 500}` | `calculate_price_variance` |
| `tds_section` | policy | string | `"194J"` | `classify_tds` |
| `tds_rate` | policy | json | `{"194C": 0.02, "194J": 0.02}` | `calculate_tds` |
| `msme_cap` | policy | json | `{"micro": 15, "small": 45}` | `calculate_msme_due_date` |
| `e_invoice_threshold` | policy | number | `50000000` (₹5 Cr) | `validate_e_invoice_requirement` |
| `approval_limit` | policy | json | `{"controller": 1000000, "cfo": 5000000}` | — |
| `msme_category` | vendor | string | `"MICRO"` | — |
| `aato_band` | vendor | string | `"ABOVE_5CR"` | — |
| `pan_available` | vendor | boolean | `true` | — |
| `qrmp_filer` | vendor | boolean | `false` | — |
| `habit_note` | vendor | string | `"Appends /A on resend"` | — |
| `grn_status` | invoice | string | `"PENDING" | "POSTED" | "MISSING"` | — |

---

## 4. Authority Ranking (Meridian AP Configuration)

```python
# app/core/ontology/authority.py
AUTHORITY_RANKING = {
    # Rank 1: Highest Authority — Client-Specific Overrides
    "client_memo": 1,           # CM-INF-02, CM-PHA-01, CM-RET-03
    
    # Rank 2: Current General Rules
    "sop_v4": 2,                # SOP v4.0 (eff. 2026-04-01)
    "desk_instruction": 2,      # DI-03, DI-07 (eff. 2026-04-01)
    
    # Rank 3: Approved Tacit Knowledge
    "expert_interview": 3,      # Lakshmi, Imran interviews (approved, 6-month TTL)
    "approved_practice": 3,     # Captured habit cards (owner approved)
    
    # Rank 4: Superseded / Historical
    "sop_v3": 4,                # SOP v3.1 (expired 2026-03-31)
    "faq_2023": 4,              # Team FAQ (Oct 2023, known errors)
    "training_video_old": 4,    # Pre-2026 videos
    
    # Rank 5: Live Sources (Dynamic — Evaluated Per Source)
    "meeting": 5,               # Client meetings — authority by speaker role
    "email": 5,                 # Client emails — authority by sender role
    "chat": 5,                  # Teams messages — authority by sender role
}
```

**Resolution Rule**: Lower `authority_rank` wins. When ranks equal → Entropy-TOPSIS credibility scoring.

---

## 5. Dual-Clock Query Patterns

### 5.1 Valid Time Query — "What was the rule on [DATE]?"
```sql
-- Price tolerance for Arvana Infra on 2026-03-01 (should return v3.1: 2%/₹1000)
SELECT f.object_value
FROM facts f
JOIN entities e ON f.subject_entity_id = e.id
WHERE e.tenant_id = $1
  AND e.canonical_name = 'price_tolerance'
  AND f.predicate = 'price_tolerance'
  AND f.valid_from <= '2026-03-01'
  AND (f.valid_to IS NULL OR f.valid_to >= '2026-03-01')
  AND f.retracted_at IS NULL
ORDER BY f.authority_rank ASC, f.valid_from DESC
LIMIT 1;
```

### 5.2 Transaction Time Query — "What would engine have said on [DATE]?"
```sql
-- What the engine knew on 2026-03-01 (should return v3.1 because v4.0 not yet ingested)
SELECT f.object_value
FROM facts f
JOIN entities e ON f.subject_entity_id = e.id
WHERE e.tenant_id = $1
  AND e.canonical_name = 'price_tolerance'
  AND f.predicate = 'price_tolerance'
  AND f.recorded_at <= '2026-03-01'
  AND (f.retracted_at IS NULL OR f.retracted_at > '2026-03-01')
ORDER BY f.authority_rank ASC, f.recorded_at DESC
LIMIT 1;
```

### 5.3 Current State Query — "What is the rule NOW?"
```sql
-- Current active fact (valid_now AND believed_now)
SELECT f.object_value
FROM facts f
JOIN entities e ON f.subject_entity_id = e.id
WHERE e.tenant_id = $1
  AND e.canonical_name = 'price_tolerance'
  AND f.predicate = 'price_tolerance'
  AND f.valid_from <= CURRENT_DATE
  AND (f.valid_to IS NULL OR f.valid_to >= CURRENT_DATE)
  AND f.retracted_at IS NULL
ORDER BY f.authority_rank ASC, f.valid_from DESC
LIMIT 1;
```

---

## 6. Repository Layer Interface (app/store/facts.py)

```python
# app/store/facts.py
class FactRepository:
    """All fact reads/writes go through here. Storage engine swappable."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def upsert_fact(self, fact: FactCreate) -> Fact:
        """Atomic: Close Old + Open New in Single Transaction."""
        async with self.session.begin():
            # 1. Retract conflicting facts (same subject+predicate, overlapping valid time)
            await self.session.execute(
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
            new_fact = Fact(**fact.model_dump(), recorded_at=func.now())
            self.session.add(new_fact)
            await self.session.flush()
            return new_fact
    
    async def get_current_fact(self, tenant_id: UUID, subject_canonical: str, 
                               predicate: str, as_of_date: date = None) -> Fact | None:
        """Get highest-authority active fact at as_of_date (default: today)."""
        as_of = as_of_date or date.today()
        stmt = (
            select(Fact)
            .join(Entity)
            .where(
                Entity.tenant_id == tenant_id,
                Entity.canonical_name == subject_canonical,
                Fact.predicate == predicate,
                Fact.valid_from <= as_of,
                (Fact.valid_to.is_(None)) | (Fact.valid_to >= as_of),
                Fact.retracted_at.is_(None)
            )
            .order_by(Fact.authority_rank.asc(), Fact.valid_from.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)
    
    async def get_fact_history(self, tenant_id: UUID, subject_canonical: str, 
                               predicate: str) -> list[Fact]:
        """Full temporal history for audit/replay."""
        stmt = (
            select(Fact)
            .join(Entity)
            .where(
                Entity.tenant_id == tenant_id,
                Entity.canonical_name == subject_canonical,
                Fact.predicate == predicate
            )
            .order_by(Fact.valid_from.asc(), Fact.recorded_at.asc())
        )
        return (await self.session.scalars(stmt)).all()
```

---

## 7. Migration from Old Schema (Claims → Facts)

| Old Table | New Mapping |
|---|---|
| `claims` | → `facts` (subject=policy entity, predicate=topic, object_value=params_json) |
| `passages` | → `blocks` (episode_id links to source episode) |
| `vendors` | → `entities` (entity_type='vendor') + `facts` (predicates: msme_category, aato_band, etc.) |
| `practices` | → `facts` (source_type='expert_interview', authority_rank=3, review_by_date=TTL) |
| `invoices` | → `entities` (entity_type='invoice') + `facts` (operational predicates) |

**No Data Loss**: All old fields mapped. New dual-clock fields default appropriately.