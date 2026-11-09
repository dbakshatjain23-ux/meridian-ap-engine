# Meridian Knowledge Engine

**Generic Dual-Clock Temporal Knowledge Engine + Industry Plug-ins**

A production-grade platform that ingests documents, emails, meetings, and chats into a governed temporal knowledge graph, answers questions with verified citations, and syncs changes back to SOPs.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    MERIDIAN KNOWLEDGE ENGINE                     │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 0: LIVE CAPTURE CONNECTORS                                │
│  Email • Teams • Meetings • Drive/SharePoint • Upload API        │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 1: UNIFIED INGESTION PIPELINE (Background Workers)        │
│  5-Tier Parser → Structure Repair → Entity/Topic Extraction     │
│  → Fact Extraction (Dual Clocks) → Authority Ranking            │
│  → 4-Case Conflict Detection → Atomic Graph Write               │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 2: DUAL-CLOCK TEMPORAL KNOWLEDGE GRAPH (Postgres Native) │
│  Episodes → Blocks → Entities → Facts (valid_from/to +          │
│  recorded_at/retracted_at) • Range Indexes (GiST) • Vector      │
│  Indexes (HNSW) • Full-Text + Fuzzy • Tenant Isolation          │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 3: 3-LANE EXECUTION ENGINE                                │
│  Lane 1: 6 Deterministic Calculators (params from graph)        │
│  Lane 2: Hybrid Retrieval (Keyword + Vector + Graph → RRF)      │
│  Lane 3: TDS Classification + Side-by-Side Practices            │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 4: VERIFIED ANSWER ENGINE + ESCALATION LOOP               │
│  4-Check Verifier • 7 Guardrails • Owner Review → Live Fact     │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 5: DELIVERY & SOP SYNC                                    │
│  REST API + WS • Teams App • ERP Embed • Browser Ext • Webhooks │
│  Change Detection → Redline → Push (SharePoint/Git) → Ack Track │
└─────────────────────────────────────────────────────────────────┘
```

## Key Innovations

1. **Dual-Clock Temporal Graph** - Valid Time (world) + Transaction Time (system) enables "what was rule on March 1?" AND "what would engine have said Nov 10?"
2. **Authority > Recency** - Stale FAQ never overrides current SOP; Client memo overrides general rule for that client only
3. **Any Format, No Setup** - 5 parser tiers → unified blocks; learns schema automatically (owner reviews once)
4. **Only Answers from KB, Escalates Rest** - 7 guardrails + 4-check verifier + live owner loop
5. **Generic Core + Industry Plug-ins** - Meridian AP is first plug-in; core knows nothing about AP/tax

## Tech Stack

| Layer | Technology |
|-------|------------|
| API | FastAPI 0.115, Python 3.11, Pydantic v2, SQLAlchemy 2 |
| Database | Postgres 16 + pgvector + pg_trgm + btree_gist (Neon) |
| Background Jobs | Postgres SKIP LOCKED Queue (no Celery/Redis) |
| LLM | Anthropic Claude (Haiku for triage, Sonnet for extraction/answer/verify) |
| Embeddings | BGE-small-en-v1.5 + BGE-reranker-base (CPU, local) |
| Parsing | python-docx, openpyxl, python-pptx, PyMuPDF, BeautifulSoup, libmagic, LibreOffice |
| Transcription | faster-whisper (CPU/GPU) |
| Diarization | pyannote.audio |
| Web | Next.js 14, TypeScript, Tailwind, Vercel |
| Deploy | Docker on Render (API + Worker), Vercel (Web), Neon (DB) |

## Quick Start

```bash
# 1. Clone and setup
git clone <repo> meridian-knowledge-engine
cd meridian-knowledge-engine
cp .env.example .env.local
# Edit .env.local with OPENAI_API_KEY

# 2. Start local stack
docker-compose up -d

# 3. Run migrations
docker-compose exec api alembic upgrade head

# 4. Seed Meridian AP ontology
docker-compose exec api python scripts/seed_meridian.py

# 5. Load test corpus
docker-compose exec api python scripts/load_meridian_corpus.py

# 6. Run acceptance tests
docker-compose exec api pytest tests/acceptance/test_t1_t10.py -v

# 7. Open UIs
# API Docs:     http://localhost:8000/docs
# Web App:      http://localhost:3000
# Health:       http://localhost:8000/health
```

## Project Structure

```
meridian-knowledge-engine/
├── .github/workflows/          # CI/CD (GitHub Actions)
├── docker/                     # Dockerfiles + docker-compose.yml
├── docs/                       # 13 specification documents
├── app/                        # FastAPI Application
│   ├── models/                 # SQLAlchemy Models (10 tables)
│   ├── schemas/                # Pydantic Schemas (API contracts)
│   ├── api/routes/             # REST + WebSocket Endpoints
│   ├── core/                   # Ingestion, Retrieval, Answer, Calculators
│   ├── store/                  # Repository Layer (ALL DB access)
│   ├── gateways/               # LLM, Embeddings, PII
│   └── workers/                # Background Job Processors
├── web/                        # Next.js 14 Frontend
├── tests/                      # Unit, Acceptance, Eval, Generality
├── scripts/                    # Seed, Load, Eval, Replay
├── alembic/                    # Database Migrations
└── requirements*.txt           # Core, ML, Dev Dependencies
```

## Evaluation Targets

| Metric | Target |
|--------|--------|
| T1-T10 Acceptance | 10/10 Pass |
| 160-Q Answer Accuracy | ≥95% (152/160) |
| Citation Accuracy | ≥90% (144/160) |
| Outdated Answers | <5% |
| Ragas Faithfulness | ≥0.95 |
| Ragas Answer Relevance | ≥0.95 |
| Ragas Context Precision | ≥0.90 |
| Ragas Harmfulness | 0.00 |
| Conflict Recall | ≥12/15 planted |
| Second Company Test | 10/10 questions |
| Format Ablation | ≥0.9 similarity |
| Temporal Replay | 100% correct |
| Ablation Gain | Full > Vector +15% |

## Documentation

See `docs/` for complete specifications:
- `Meridian_AP_HYBRID_SPEC.md` - **Single source of truth**
- `Meridian_AP_PRD.md` - Product requirements
- `Meridian_AP_SYSTEM_ARCHITECTURE.md` - 6-layer architecture
- `Meridian_AP_DB_SCHEMA_AND_GRAPH.md` - Dual-clock Postgres schema
- `Meridian_AP_CALCULATORS_AND_TRIAGE_SPEC.md` - 6 calculators
- `Meridian_AP_API_SPECIFICATION.md` - REST + WS contracts
- `Meridian_AP_DEPLOYMENT.md` - Docker/Render/Vercel/Neon deployment
- `Meridian_AP_EVALUATION_AND_TESTING_SUITE.md` - T1-T10, Ragas, Generality
- `Meridian_AP_MASTER_PROMPT_GUIDE.md` - Phase-based build prompts
- `Meridian_AP_STARTER_REPO_CONFIG.md` - Complete repo structure

## License

Proprietary - Meridian Shared Services