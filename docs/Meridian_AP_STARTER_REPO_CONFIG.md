# MERIDIAN SHARED SERVICES · ENTERPRISE KNOWLEDGE ENGINE
## Production Starter Repository Configuration
**Document ID**: `Meridian_AP_STARTER_REPO_CONFIG.md`  
**Replaces**: `Meridian_AP_STARTER_REPO_CONFIG.md` (Zoho Catalyst version)  
**Target Stack**: **Docker on Render + Vercel + Neon**  

---

## 1. Complete Directory Tree

```
meridian-knowledge-engine/
├── .github/
│   └── workflows/
│       ├── ci.yml                    # Lint, typecheck, unit/integration tests
│       ├── deploy-api.yml            # Render API service deploy
│       ├── deploy-worker.yml         # Render Worker service deploy
│       ├── deploy-web.yml            # Vercel web deploy
│       └── eval.yml                  # Nightly Ragas + Meridian eval
├── docker/
│   ├── api.Dockerfile                # FastAPI + Uvicorn (multi-stage)
│   ├── worker.Dockerfile             # Worker + ML models (multi-stage)
│   ├── web.Dockerfile                # Next.js (for local Docker)
│   └── docker-compose.yml            # Local dev stack
├── docs/                             # All 13 specification documents
│   ├── Meridian_AP_HYBRID_SPEC.md           # SINGLE SOURCE OF TRUTH
│   ├── Meridian_AP_PRD.md
│   ├── Meridian_AP_SYSTEM_ARCHITECTURE.md
│   ├── Meridian_AP_DB_SCHEMA_AND_GRAPH.md
│   ├── Meridian_AP_CALCULATORS_AND_TRIAGE_SPEC.md
│   ├── Meridian_AP_API_SPECIFICATION.md
│   ├── Meridian_AP_DEPLOYMENT.md
│   ├── Meridian_AP_EVALUATION_AND_TESTING_SUITE.md
│   ├── Meridian_AP_MASTER_PROMPT_GUIDE.md
│   ├── Meridian_AP_STARTER_REPO_CONFIG.md   # THIS FILE
│   ├── Meridian_AP_Master_System_Design_and_Problem_Breakdown_v4.2.md
│   └── Data/                         # Source corpus (4 Word docs, eval Excel)
├── app/                              # FastAPI Application (Python 3.11)
│   ├── __init__.py
│   ├── main.py                       # App factory, lifespan, middleware
│   ├── config.py                     # Pydantic Settings (all env vars)
│   ├── database.py                   # Async engine, session, Base
│   ├── models/                       # SQLAlchemy Models (10 tables)
│   │   ├── __init__.py
│   │   ├── tenant.py
│   │   ├── episode.py
│   │   ├── block.py
│   │   ├── entity.py
│   │   ├── fact.py
│   │   ├── conflict.py
│   │   ├── job.py
│   │   ├── answer_log.py
│   │   └── user.py
│   ├── schemas/                      # Pydantic Schemas (API contracts)
│   │   ├── __init__.py
│   │   ├── query.py
│   │   ├── episode.py
│   │   ├── fact.py
│   │   ├── conflict.py
│   │   ├── tacit.py
│   │   ├── delivery.py
│   │   └── sop_sync.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                   # Dependencies (tenant, auth, DB)
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── query.py              # POST /query/ask, GET /query/ask/stream
│   │       ├── tacit.py              # POST /tacit/capture, GET /tacit/list
│   │       ├── episodes.py           # POST /episodes/upload, webhook endpoints
│   │       ├── facts.py              # GET /facts, /facts/{id}/history
│   │       ├── conflicts.py          # GET /conflicts, POST /conflicts/{id}/resolve
│   │       ├── sop_sync.py           # GET/POST /sop/sync/*
│   │       ├── delivery.py           # POST /delivery/erp/embed, /delivery/teams/message
│   │       ├── admin.py              # Schema switch, eval triggers
│   │       └── health.py             # /health, /health/ready
│   ├── core/
│   │   ├── __init__.py
│   │   ├── ingestion/
│   │   │   ├── __init__.py
│   │   │   ├── parser.py             # 5-tier parser → BlockList
│   │   │   ├── structure_repair.py   # AI heading assignment
│   │   │   ├── extractor.py          # Entity/Topic/Fact extraction
│   │   │   ├── authority.py          # Source ranking config
│   │   │   ├── conflict.py           # 4-case detection
│   │   │   └── graph_writer.py       # Atomic close+open
│   │   ├── retrieval/
│   │   │   ├── __init__.py
│   │   │   ├── hybrid.py             # Keyword + Vector + Graph Walk
│   │   │   ├── reranker.py           # BGE reranker
│   │   │   └── filters.py            # Time, client, scope
│   │   ├── answer/
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # Calculator / Lookup / Judge / Refuse
│   │   │   ├── builder.py            # Citations, calcs, older, tips
│   │   │   ├── verifier.py           # 4 checks
│   │   │   └── escalation.py         # Owner review loop
│   │   ├── calculators/              # MERIDIAN AP PLUG-IN
│   │   │   ├── __init__.py
│   │   │   ├── base.py               # BaseCalculator, CalculatorContext
│   │   │   ├── price_variance.py
│   │   │   ├── tds_triage.py         # classify_tds + calculate_tds
│   │   │   ├── msme_due_date.py
│   │   │   ├── e_invoice.py
│   │   │   └── supplier_normalizer.py
│   │   ├── ontology/                 # Meridian AP entities/predicates
│   │   │   ├── __init__.py
│   │   │   ├── entities.py
│   │   │   ├── predicates.py
│   │   │   └── authority.py
│   │   └── live_capture/             # PHASE 5 — Live Connectors
│   │       ├── __init__.py
│   │       ├── email_connector.py
│   │       ├── teams_bot.py
│   │       ├── meeting_bot.py
│   │       ├── transcriber.py
│   │       ├── diarization.py
│   │       ├── pii_redactor.py
│   │       └── drive_watcher.py
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── main.py                   # Job processor (SKIP LOCKED)
│   │   ├── registry.py               # Job handler registry
│   │   ├── ingestion_worker.py       # Processes ingest jobs
│   │   ├── conflict_scanner.py       # Daily corpus scan
│   │   ├── sop_sync_worker.py        # SOP sync jobs
│   │   └── notification_worker.py    # Change alerts
│   ├── store/                        # Repository Layer (ALL DB access)
│   │   ├── __init__.py
│   │   ├── base.py                   # BaseRepository
│   │   ├── episodes.py
│   │   ├── blocks.py
│   │   ├── entities.py
│   │   ├── facts.py
│   │   ├── conflicts.py
│   │   ├── jobs.py
│   │   ├── answers.py
│   │   └── users.py
│   ├── gateways/
│   │   ├── __init__.py
│   │   ├── llm.py                    # Anthropic Claude (Haiku/Sonnet)
│   │   ├── embeddings.py             # BGE-small + Reranker (local)
│   │   └── pii.py                    # Regex scrubber
│   └── middleware/
│       ├── __init__.py
│       ├── auth.py                   # JWT + Tenant middleware
│       ├── pii.py                    # Request/Response PII scrubbing
│       ├── rate_limit.py             # Redis-based rate limiting
│       └── logging.py                # Structured JSON logging
├── web/                              # Next.js 14 Frontend (Vercel)
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── next.config.js
│   ├── public/
│   │   └── fonts/                    # Hanken Grotesk, Inter, JetBrains Mono
│   ├── src/
│   │   ├── app/                      # App Router (Next.js 14)
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx              # Landing / Processor UI
│   │   │   ├── owner/                # Process Owner Dashboard
│   │   │   │   ├── page.tsx
│   │   │   │   ├── redline/          # Conflict Redline Queue
│   │   │   │   ├── tacit/            # Tacit Approval Studio
│   │   │   │   └── sop-sync/         # SOP Sync Review
│   │   │   ├── api/                  # API routes (proxy to FastAPI)
│   │   │   └── globals.css
│   │   ├── components/
│   │   │   ├── ui/                   # Base components (Button, Card, Input)
│   │   │   ├── AnswerCard.tsx        # Citations, calcs, older, tips
│   │   │   ├── EscalationCard.tsx    # Not-covered + escalate button
│   │   │   ├── TacitCaptureStudio.tsx
│   │   │   ├── RedlineDashboard.tsx
│   │   │   ├── LiveSourcePanel.tsx   # Connector status
│   │   │   ├── SOPSyncPanel.tsx      # Change review
│   │   │   ├── ERPEmbedWidget.tsx    # For iframe embed
│   │   │   └── ChatInterface.tsx     # Teams-style chat
│   │   ├── lib/
│   │   │   ├── api.ts                # Typed API client (fetch + WS)
│   │   │   ├── auth.ts               # JWT handling
│   │   │   ├── utils.ts
│   │   │   └── constants.ts
│   │   └── hooks/
│   │       ├── useQuery.ts
│   │       ├── useWebSocket.ts
│   │       └── useAuth.ts
│   └── .env.example
├── tests/                            # Comprehensive Test Suite
│   ├── __init__.py
│   ├── conftest.py                   # Pytest fixtures (client, DB, auth)
│   ├── pytest.ini
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_calculators.py       # 6 calculators + TDS triage
│   │   ├── test_parser.py            # 5 tiers → blocks
│   │   ├── test_extraction.py        # Entity/Fact extraction
│   │   ├── test_conflict.py          # 4 cases
│   │   ├── test_retrieval.py         # Hybrid + RRF + Rerank
│   │   ├── test_verifier.py          # 4 checks
│   │   └── test_live_capture.py      # Phase 5 mocks
│   ├── acceptance/
│   │   ├── __init__.py
│   │   ├── test_t1_t10.py            # T1-T10 exact cases
│   │   ├── test_meridian_eval.py     # 160 gold questions
│   │   ├── test_conflict_scan.py     # ≥12/15 planted
│   │   ├── test_tacit_lifecycle.py   # 5-state + TTL
│   │   └── test_generality.py        # Second company, format ablation
│   ├── integration/
│   │   ├── __init__.py
│   │   ├── test_ingestion_pipeline.py
│   │   ├── test_answer_pipeline.py
│   │   ├── test_escalation_loop.py
│   │   └── test_delivery.py
│   ├── eval/
│   │   ├── __init__.py
│   │   ├── test_ragas_eval.py
│   │   └── test_meridian_metrics.py
│   ├── fixtures/
│   │   ├── __init__.py
│   │   ├── meridian_client.py        # Test client helper
│   │   ├── meridian_corpus/          # 4 Word docs
│   │   ├── meridian_eval.xlsx        # 160 questions
│   │   ├── planted_conflicts.json    # 15 known conflicts
│   │   ├── second_company/           # Different domain corpus
│   │   └── format_ablation/          # Same SOP in 5 formats
│   └── helpers/
│       ├── __init__.py
│       └── similarity.py
├── scripts/                          # Operational Scripts
│   ├── __init__.py
│   ├── seed_meridian.py              # Load Meridian AP ontology
│   ├── load_meridian_corpus.py       # Ingest 4 docs for testing
│   ├── run_eval.py                   # Full eval suite runner
│   ├── generate_redline.py           # SOP sync helper
│   ├── replay_temporal.py            # Temporal replay test
│   └── ablation_study.py             # Layer contribution analysis
├── alembic/                          # Database Migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 001_initial_schema.py
│       ├── 002_indexes.py
│       ├── 003_meridian_seed.py
│       └── 004_rls_policies.py
├── requirements.txt                  # Core Python deps
├── requirements-ml.txt               # ML deps (worker only)
├── requirements-dev.txt              # Dev tools (ruff, mypy, pytest, pre-commit)
├── pyproject.toml                    # Tool config (ruff, mypy, pytest, coverage)
├── .env.example                      # All env vars (see DEPLOYMENT.md)
├── .gitignore
├── .dockerignore
├── README.md                         # Quick start, architecture overview
├── CLAUDE.md                         # Context for Claude Code
└── LICENSE
```

---

## 2. Key Configuration Files

### 2.1 `pyproject.toml`

```toml
[project]
name = "meridian-knowledge-engine"
version = "0.1.0"
description = "Generic Dual-Clock Temporal Knowledge Engine + AP Plug-in"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = [
    "ruff==0.5.0",
    "mypy==1.10.0",
    "pytest==8.2.0",
    "pytest-asyncio==0.23.0",
    "pytest-cov==5.0.0",
    "httpx==0.27.0",
    "pre-commit==3.7.0",
]

[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "T20"]
ignore = ["E501", "B008"]
fixable = ["ALL"]
[tool.ruff.format]
quote-style = "double"
indent-style = "space"

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true
show_error_codes = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short --strict-markers"
markers = [
    "unit: Unit tests",
    "acceptance: T1-T10 acceptance tests",
    "eval: Ragas + Meridian metrics",
    "generality: Generality proofs",
    "integration: Integration tests",
    "live_capture: Live connector tests",
    "slow: Slow tests (>10s)",
]

[tool.coverage.run]
source = ["app"]
omit = ["tests/*", "alembic/*", "scripts/*"]

[tool.coverage.report]
exclude_lines = ["pragma: no cover", "def __repr__", "raise NotImplementedError"]
```

---

### 2.2 `requirements.txt` (Core)

```txt
# ============================================================
# CORE FRAMEWORK
# ============================================================
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy[asyncio]==2.0.32
asyncpg==0.29.0
pydantic[email]==2.8.2
pydantic-settings==2.3.4
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.9
httpx==0.27.0
tenacity==8.3.0

# ============================================================
# DATABASE & SEARCH
# ============================================================
pgvector==0.2.5
psycopg[pool]==3.1.18

# ============================================================
# AI / LLM (OpenAI - GPT-4o-mini + GPT-4o)
# ============================================================
openai==1.30.0

# ============================================================
# EMBEDDINGS & RERANKING (Local CPU)
# ============================================================
sentence-transformers==3.0.1
torch==2.4.0 --index-url https://download.pytorch.org/whl/cpu
transformers==4.42.0
accelerate==0.32.0

# ============================================================
# DOCUMENT PARSING
# ============================================================
python-docx==1.1.2
openpyxl==3.1.2
pandas==2.2.0
python-pptx==1.0.2
pymupdf==1.23.26
beautifulsoup4==4.12.2
python-magic==0.4.27

# ============================================================
# BACKGROUND JOBS (Postgres Queue)
# ============================================================
redis==5.0.3

# ============================================================
# MONITORING & OBSERVABILITY
# ============================================================
sentry-sdk==1.45.0
opentelemetry-api==1.25.0
opentelemetry-sdk==1.25.0
opentelemetry-exporter-otlp==1.25.0
prometheus-client==0.19.0

# ============================================================
# UTILITIES
# ============================================================
python-dateutil==2.9.0
pytz==2024.1
```

---

### 2.3 `requirements-ml.txt` (Worker Only — ML Models)

```txt
# ============================================================
# TRANSCRIPTION & DIARIZATION (GPU Recommended)
# ============================================================
faster-whisper==1.0.3
pyannote.audio==3.1.1
huggingface-hub==0.23.0

# ============================================================
# AUDIO PROCESSING
# ============================================================
librosa==0.10.2
soundfile==0.12.1
```

---

### 2.4 `.env.example`

```bash
# ============================================================
# CORE APPLICATION
# ============================================================
APP_ENV=development
APP_HOST=0.0.0.0
APP_PORT=8000
WORKERS=4
LOG_LEVEL=debug

# ============================================================
# DATABASE (Neon Postgres for prod, local for dev)
# ============================================================
DATABASE_URL=postgresql://meridian:meridian@localhost:5432/meridian
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=5

# ============================================================
# TENANCY
# ============================================================
DEFAULT_TENANT_SLUG=meridian

# ============================================================
# AUTHENTICATION
# ============================================================
JWT_SECRET_KEY=dev-secret-change-in-production-min-64-chars
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=60
JWT_REFRESH_EXPIRY_DAYS=7

# ============================================================
# LLM PROVIDER (OpenAI - GPT-4o-mini + GPT-4o)
# ============================================================
OPENAI_API_KEY=sk-...
OPENAI_MODEL_FAST=gpt-4o-mini      # Cheap, fast: triage, routing, structure repair, schema learning
OPENAI_MODEL_STRONG=gpt-4o         # Strong reasoning: extraction, answer, verification
LLM_CACHE_TTL_SECONDS=3600
LLM_MAX_RETRIES=3

# ============================================================
# EMBEDDINGS & SEARCH (Local CPU)
# ============================================================
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIM=384
EMBEDDING_BATCH_SIZE=32
RERANKER_MODEL=BAAI/bge-reranker-base
RERANKER_TOP_K=20
RRF_K=60

# ============================================================
# BACKGROUND WORKER (Postgres Queue)
# ============================================================
WORKER_CONCURRENCY=4
JOB_POLL_INTERVAL_MS=1000
JOB_MAX_ATTEMPTS=3
JOB_RETRY_BASE_DELAY_SECONDS=30

# ============================================================
# LIVE CAPTURE CONNECTORS (Phase 5+)
# ============================================================
# Microsoft Graph (Email, Teams, Drive, SharePoint)
MICROSOFT_GRAPH_CLIENT_ID=
MICROSOFT_GRAPH_CLIENT_SECRET=
MICROSOFT_GRAPH_TENANT_ID=
MICROSOFT_GRAPH_REDIRECT_URI=http://localhost:8000/auth/microsoft/callback

# Teams Bot
TEAMS_BOT_APP_ID=
TEAMS_BOT_APP_PASSWORD=
TEAMS_BOT_WEBHOOK_SECRET=

# Zoom (Meeting Bot)
ZOOM_ACCOUNT_ID=
ZOOM_CLIENT_ID=
ZOOM_CLIENT_SECRET=

# ============================================================
# FILE STORAGE (Cloudflare R2 for prod, local for dev)
# ============================================================
R2_ENDPOINT=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=meridian-episodes
R2_PUBLIC_URL=

# ============================================================
# REDIS (Upstash for prod, local for dev)
# ============================================================
REDIS_URL=redis://localhost:6379

# ============================================================
# PII REDACTION
# ============================================================
PII_REDACTION_ENABLED=true
PII_PAN_REGEX='[A-Z]{5}[0-9]{4}[A-Z]{1}'
PII_BANK_REGEX='[0-9]{9,18}'
PII_AADHAAR_REGEX='[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}'

# ============================================================
# SOP SYNC (Phase 7+)
# ============================================================
SHAREPOINT_SITE_URL=
GITHUB_TOKEN=
GITHUB_REPO=
GITLAB_TOKEN=
GITLAB_PROJECT=

# ============================================================
# FEATURE FLAGS
# ============================================================
ENABLE_LIVE_CONNECTORS=false
ENABLE_SOP_SYNC=false
ENABLE_MEETING_BOT=false
ENABLE_ERP_EMBED=false
ENABLE_TEAMS_APP=false
ENABLE_BROWSER_EXTENSION=false
SCHEMA_MODE=learned

# ============================================================
# MONITORING
# ============================================================
SENTRY_DSN=
OTEL_EXPORTER_OTLP_ENDPOINT=
```

---

## 3. Initialization Steps

### 3.1 Local Development Setup

```bash
# 1. Clone & enter
git clone <repo> meridian-knowledge-engine
cd meridian-knowledge-engine

# 2. Copy env template
cp .env.example .env.local
# Edit .env.local with your keys (OPENAI_API_KEY required)

# 3. Start local stack
docker-compose up -d

# 4. Verify services
docker-compose ps
# Should show: postgres, redis, api, worker, web (all healthy)

# 5. Run migrations
docker-compose exec api alembic upgrade head

# 6. Seed Meridian AP ontology
docker-compose exec api python scripts/seed_meridian.py

# 7. Load test corpus (4 Word docs)
docker-compose exec api python scripts/load_meridian_corpus.py

# 8. Run acceptance tests
docker-compose exec api pytest tests/acceptance/test_t1_t10.py -v

# 9. Open UIs
# API Docs:     http://localhost:8000/docs
# Web App:      http://localhost:3000
# Health:       http://localhost:8000/health
```

### 3.2 Production Deployment

```bash
# 1. Push to main branch → GitHub Actions deploys automatically
#    - API → Render (docker/api.Dockerfile)
#    - Worker → Render (docker/worker.Dockerfile)
#    - Web → Vercel (web/)

# 2. Or manual Render deploy:
render deploy --service meridian-api
render deploy --service meridian-worker

# 3. Verify production
curl https://api.meridian-engine.com/health
curl https://api.meridian-engine.com/health/ready
```

---

## 4. Key Commands Reference

| Task | Command |
|---|---|
| **Start local** | `docker-compose up -d` |
| **Stop local** | `docker-compose down` |
| **View logs** | `docker-compose logs -f api` |
| **Run migrations** | `docker-compose exec api alembic upgrade head` |
| **Create migration** | `docker-compose exec api alembic revision --autogenerate -m "msg"` |
| **Run unit tests** | `docker-compose exec api pytest tests/unit -v` |
| **Run acceptance** | `docker-compose exec api pytest tests/acceptance -v` |
| **Run Ragas eval** | `docker-compose exec api pytest tests/eval/test_ragas_eval.py -v` |
| **Run generality** | `docker-compose exec api pytest tests/generality -v` |
| **Seed ontology** | `docker-compose exec api python scripts/seed_meridian.py` |
| **Load corpus** | `docker-compose exec api python scripts/load_meridian_corpus.py` |
| **Full eval** | `docker-compose exec api python scripts/run_eval.py --suite=all` |
| **Lint** | `docker-compose exec api ruff check app/` |
| **Type check** | `docker-compose exec api mypy app/` |
| **Format** | `docker-compose exec api ruff format app/` |

---

## 5. Verification Checklist (Post-Deploy)

- [ ] `/health` returns `{"status": "healthy", "database": "connected", "redis": "connected"}`
- [ ] `/health/ready` returns `{"status": "ready", "workers": 4, "queue_depth": 0}`
- [ ] `POST /query/ask` returns answer with citations in <30s
- [ ] T1-T10 acceptance tests: **10/10 PASS**
- [ ] 160-question eval: Answer Acc ≥95%, Citation Acc ≥90%, Outdated <5%
- [ ] Ragas: Faithfulness ≥0.95, Relevance ≥0.95, Precision ≥0.90, Harm = 0.00
- [ ] Conflict scan: ≥12/15 planted conflicts detected
- [ ] Tacit capture: Creates fact with 6-month TTL, authority_rank=3
- [ ] Live connectors (if enabled): Email/webhook → Episode → Facts
- [ ] ERP embed: Returns widget HTML with actions
- [ ] SOP sync (if enabled): Generates redline with tracked changes