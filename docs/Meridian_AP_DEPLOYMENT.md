# MERIDIAN SHARED SERVICES · ENTERPRISE KNOWLEDGE ENGINE
## Deployment Architecture & Operations Guide
**Document ID**: `Meridian_AP_DEPLOYMENT.md`  
**Target Environment**: **Docker on Render (API + Worker), Vercel (Web), Neon (Postgres)**  
**Replaces**: `Meridian_AP_DEPLOYMENT_ZOHO_CATALYST.md` (Zoho Catalyst deprecated)  

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           PRODUCTION DEPLOYMENT ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│  │   Vercel     │    │    Render    │    │    Render    │    │    Neon      │     │
│  │   (Web)      │◄───│   (API)      │◄───│  (Worker)    │◄───│  (Postgres)  │     │
│  │              │    │              │    │              │    │              │     │
│  │ Next.js 14   │    │ FastAPI      │    │ Background   │    │ Postgres 16  │     │
│  │ TypeScript   │    │ Python 3.11  │    │ Workers      │    │ + pgvector   │     │
│  │ Tailwind     │    │ + Uvicorn    │    │ (SKIP LOCKED)│    │ + pg_trgm    │     │
│  └──────────────┘    └──────┬───────┘    └──────┬───────┘    │ + btree_gist │     │
│                             │                   │             └──────────────┘     │
│                             ▼                   ▼                                  │
│                    ┌─────────────────────────────────────┐                         │
│                    │         Shared Services             │                         │
│                    │  • Redis (caching, rate limits)     │                         │
│                    │  • S3/R2 (file storage, uploads)    │                         │
│                    │  • Anthropic API (Claude)           │                         │
│                    │  • Microsoft Graph API (connectors) │                         │
│                    └─────────────────────────────────────┘                         │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Infrastructure Components

| Component | Provider | Specification | Purpose |
|---|---|---|---|
| **API Server** | Render | Docker, 2+ instances, Auto-scale | FastAPI + Uvicorn, WebSocket support |
| **Background Workers** | Render | Docker, 4+ instances, Horizontal | Ingestion, Conflict Scan, SOP Sync, Notifications |
| **Web App** | Vercel | Next.js 14, Edge Functions | Processor UI, Owner Dashboard, Tacit Studio |
| **Database** | Neon | Postgres 16, pgvector, pg_trgm, btree_gist | Temporal Graph, Vectors, Full-Text, Jobs |
| **Cache/Rate Limit** | Redis (Upstash) | Serverless Redis | LLM Cache, Rate Limiting, Session |
| **File Storage** | Cloudflare R2 | S3-compatible | Episode files, Generated Redlines |
| **LLM** | Anthropic | Claude Haiku + Sonnet | All AI Tasks (Tiered) |
| **Embeddings** | Local (CPU) | BGE-small-en-v1.5 | Vector Embeddings (No API Cost) |
| **Reranker** | Local (CPU) | BGE-reranker-base | Hybrid Search Reranking |
| **Transcription** | Local (GPU) | faster-whisper | Meeting Transcription |
| **Diarization** | Local (GPU) | pyannote.audio | Speaker Separation |

---

## 3. Environment Configuration

### 3.1 Required Environment Variables

```bash
# ============================================================
# CORE APPLICATION
# ============================================================
APP_ENV=production
APP_HOST=0.0.0.0
APP_PORT=8000
WORKERS=4
LOG_LEVEL=info

# ============================================================
# DATABASE (Neon Postgres)
# ============================================================
DATABASE_URL=postgresql://user:pass@ep-xxx.us-east-1.aws.neon.tech/dbname?sslmode=require
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# ============================================================
# TENANCY
# ============================================================
DEFAULT_TENANT_SLUG=meridian

# ============================================================
# AUTHENTICATION
# ============================================================
JWT_SECRET_KEY=<64-char-random>
JWT_ALGORITHM=HS256
JWT_EXPIRY_MINUTES=60
JWT_REFRESH_EXPIRY_DAYS=7

# ============================================================
# LLM PROVIDER (Anthropic Only)
# ============================================================
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_HAIKU_MODEL=claude-3-5-haiku-20241022
CLAUDE_SONNET_MODEL=claude-3-5-sonnet-20241022
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
# LIVE CAPTURE CONNECTORS
# ============================================================
# Microsoft Graph (Email, Teams, Drive, SharePoint)
MICROSOFT_GRAPH_CLIENT_ID=xxx
MICROSOFT_GRAPH_CLIENT_SECRET=xxx
MICROSOFT_GRAPH_TENANT_ID=xxx
MICROSOFT_GRAPH_REDIRECT_URI=https://api.meridian-engine.com/auth/microsoft/callback

# Teams Bot
TEAMS_BOT_APP_ID=xxx
TEAMS_BOT_APP_PASSWORD=xxx
TEAMS_BOT_WEBHOOK_SECRET=xxx

# Zoom (Meeting Bot)
ZOOM_ACCOUNT_ID=xxx
ZOOM_CLIENT_ID=xxx
ZOOM_CLIENT_SECRET=xxx

# ============================================================
# FILE STORAGE (Cloudflare R2)
# ============================================================
R2_ENDPOINT=https://<account>.r2.cloudflarestorage.com
R2_ACCESS_KEY_ID=xxx
R2_SECRET_ACCESS_KEY=xxx
R2_BUCKET=meridian-episodes
R2_PUBLIC_URL=https://files.meridian-engine.com

# ============================================================
# REDIS (Upstash)
# ============================================================
REDIS_URL=rediss://default:xxx@xxx.upstash.io:6379

# ============================================================
# PII REDACTION
# ============================================================
PII_REDACTION_ENABLED=true
PII_PAN_REGEX='[A-Z]{5}[0-9]{4}[A-Z]{1}'
PII_BANK_REGEX='[0-9]{9,18}'
PII_AADHAAR_REGEX='[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}'

# ============================================================
# SOP SYNC
# ============================================================
SHAREPOINT_SITE_URL=https://meridian.sharepoint.com/sites/AP
GITHUB_TOKEN=ghp_xxx
GITHUB_REPO=meridian/sops
GITLAB_TOKEN=glpat_xxx
GITLAB_PROJECT=meridian/sops

# ============================================================
# FEATURE FLAGS
# ============================================================
ENABLE_LIVE_CONNECTORS=true
ENABLE_SOP_SYNC=true
ENABLE_MEETING_BOT=true
ENABLE_ERP_EMBED=true
ENABLE_TEAMS_APP=true
ENABLE_BROWSER_EXTENSION=true
SCHEMA_MODE=learned  # or 'baseline'

# ============================================================
# MONITORING
# ============================================================
SENTRY_DSN=https://xxx@sentry.io/xxx
OTEL_EXPORTER_OTLP_ENDPOINT=https://otel.xxx:4318
```

---

## 4. Docker Images

### 4.1 API Image (`docker/api.Dockerfile`)

```dockerfile
FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    libreoffice-headless \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY app/ ./app/
COPY alembic/ ./alembic/

# Non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 4.2 Worker Image (`docker/worker.Dockerfile`)

```dockerfile
FROM python:3.11-slim

# System dependencies (includes ML models for transcription/diarization)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    libreoffice-headless \
    poppler-utils \
    tesseract-ocr \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
WORKDIR /app
COPY requirements.txt .
COPY requirements-ml.txt .
RUN pip install --no-cache-dir -r requirements.txt -r requirements-ml.txt

# Download ML models at build time
RUN python -c "
from faster_whisper import WhisperModel
WhisperModel('base', device='cpu', download_root='/models')
from pyannote.audio import Pipeline
Pipeline.from_pretrained('pyannote/speaker-diarization', use_auth_token='${HF_TOKEN}', cache_dir='/models')
"

# Application code
COPY app/ ./app/
COPY alembic/ ./alembic/

# Non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

CMD ["python", "-m", "app.workers.main"]
```

### 4.3 Requirements Files

**`requirements.txt`**:
```txt
# Core
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

# Database & Search
pgvector==0.2.5
psycopg[pool]==3.1.18

# AI/ML
anthropic==0.39.0
sentence-transformers==3.0.1
torch==2.4.0 --index-url https://download.pytorch.org/whl/cpu
transformers==4.42.0
accelerate==0.32.0

# Document Parsing
python-docx==1.1.2
openpyxl==3.1.2
pandas==2.2.0
python-pptx==1.0.2
pymupdf==1.23.26
beautifulsoup4==4.12.2
python-magic==0.4.27

# Background Jobs
redis==5.0.3

# Monitoring
sentry-sdk==1.45.0
opentelemetry-api==1.25.0
opentelemetry-sdk==1.25.0
opentelemetry-exporter-otlp==1.25.0

# Testing
pytest==8.2.0
pytest-asyncio==0.23.0
pytest-cov==5.0.0
httpx==0.27.0
```

**`requirements-ml.txt`** (Worker only):
```txt
# Transcription & Diarization (GPU)
faster-whisper==1.0.3
pyannote.audio==3.1.1
huggingface-hub==0.23.0

# Audio processing
librosa==0.10.2
soundfile==0.12.1
```

---

## 5. Database Migrations (Alembic)

```bash
# Initialize (run once)
alembic init alembic

# Create migration
alembic revision --autogenerate -m "Initial dual-clock schema"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

**Migration Order**:
1. `001_initial_schema.py` — Core tables (tenants, episodes, blocks, entities, facts, conflicts, jobs, answer_logs, users)
2. `002_indexes.py` — GiST range indexes, HNSW vector indexes, GIN full-text
3. `003_meridian_seed.py` — Meridian AP ontology seed data (entities, predicates, authority ranking)
4. `004_rls_policies.py` — Row Level Security for tenant isolation

---

## 6. Render Deployment Configuration

### 6.1 `render.yaml`

```yaml
services:
  # API Service
  - type: web
    name: meridian-api
    env: docker
    dockerfilePath: docker/api.Dockerfile
    dockerContext: .
    plan: standard
    numInstances: 2
    autoScale:
      minInstances: 2
      maxInstances: 10
      cpuPercent: 70
    envVars:
      - key: DATABASE_URL
        fromDatabase: meridian-db
        property: connectionString
      - key: REDIS_URL
        fromService: meridian-redis
        property: connectionString
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: JWT_SECRET_KEY
        sync: false
      # ... all other env vars
    healthCheckPath: /health
    scaling:
      minInstances: 2
      maxInstances: 10

  # Background Worker
  - type: worker
    name: meridian-worker
    env: docker
    dockerfilePath: docker/worker.Dockerfile
    dockerContext: .
    plan: standard
    numInstances: 4
    autoScale:
      minInstances: 2
      maxInstances: 8
      cpuPercent: 60
    envVars:
      - key: DATABASE_URL
        fromDatabase: meridian-db
        property: connectionString
      - key: REDIS_URL
        fromService: meridian-redis
        property: connectionString
      # ... all other env vars

  # Redis (Upstash or Render Redis)
  - type: redis
    name: meridian-redis
    plan: starter
    maxmemoryPolicy: allkeys-lru

databases:
  - name: meridian-db
    databaseName: meridian
    user: meridian
    plan: standard
    ipAllowList: []
    # pgvector, pg_trgm, btree_gist enabled via init script
```

---

## 7. Vercel Deployment (Web App)

### 7.1 `vercel.json`

```json
{
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "devCommand": "npm run dev",
  "installCommand": "npm install",
  "regions": ["iad1"],
  "functions": {
    "src/app/api/**/*.ts": {
      "maxDuration": 30
    }
  },
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {"key": "X-Content-Type-Options", "value": "nosniff"},
        {"key": "X-Frame-Options", "value": "DENY"},
        {"key": "Referrer-Policy", "value": "strict-origin-when-cross-origin"}
      ]
    }
  ],
  "rewrites": [
    {"source"/api/:path*", "destination": "https://api.meridian-engine.com/v1/:path*"}
  ]
}
```

### 7.2 Web App Environment Variables

```bash
NEXT_PUBLIC_API_URL=https://api.meridian-engine.com/v1
NEXT_PUBLIC_WS_URL=wss://api.meridian-engine.com/v1
NEXT_PUBLIC_TENANT_SLUG=meridian
NEXT_PUBLIC_APP_NAME=Meridian Knowledge Engine
```

---

## 8. CI/CD Pipeline (GitHub Actions)

### 8.1 `.github/workflows/ci.yml`

```yaml
name: CI

on: [push, pull_request]

jobs:
  lint-typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install -r requirements-dev.txt
      - run: ruff check app/ tests/
      - run: mypy app/

  unit-tests:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env: {POSTGRES_PASSWORD: test, POSTGRES_DB: test}
        ports: [5432:5432]
        options: >-
          --health-cmd="pg_isready"
          --health-interval=10s
          --health-timeout=5s
          --health-retries=5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: alembic upgrade head
        env: {DATABASE_URL: postgresql://postgres:test@localhost:5432/test}
      - run: pytest tests/unit -v --cov=app --cov-report=xml

  integration-tests:
    runs-on: ubuntu-latest
    # Similar setup with testcontainers

  web-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: {node-version: '20', cache: 'npm'}
      - working-directory: ./web
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck
```

### 8.2 `.github/workflows/deploy.yml`

```yaml
name: Deploy

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  deploy-api:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: render/actions/deploy@v1
        with:
          service-id: ${{ secrets.RENDER_API_SERVICE_ID }}
          api-key: ${{ secrets.RENDER_API_KEY }}

  deploy-worker:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: render/actions/deploy@v1
        with:
          service-id: ${{ secrets.RENDER_WORKER_SERVICE_ID }}
          api-key: ${{ secrets.RENDER_API_KEY }}

  deploy-web:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          vercel-args: '--prod'
```

### 8.3 `.github/workflows/eval.yml` (Nightly)

```yaml
name: Nightly Evaluation

on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM UTC daily
  workflow_dispatch:

jobs:
  eval:
    runs-on: ubuntu-latest
    timeout-minutes: 120
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: python scripts/run_eval.py --suite=all --output=eval_results.json
      - uses: actions/upload-artifact@v4
        with:
          name: eval-results
          path: eval_results.json
      - name: Comment PR with Results
        if: github.event_name == 'pull_request'
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const results = JSON.parse(fs.readFileSync('eval_results.json'));
            const body = `## Evaluation Results\n\n| Metric | Value |\n|---|---|\n| Answer Accuracy | ${results.answer_accuracy} |\n| Citation Accuracy | ${results.citation_accuracy} |\n| Outdated Rate | ${results.outdated_rate} |\n| Conflicts Found | ${results.conflicts_found}/15 |`;
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body
            });
```

---

## 9. Local Development

### 9.1 `docker-compose.yml`

```yaml
version: '3.8'

services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: meridian
      POSTGRES_USER: meridian
      POSTGRES_PASSWORD: meridian
    ports: ["5432:5432"]
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init-extensions.sql:/docker-entrypoint-initdb.d/init-extensions.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U meridian"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes: [redis_data:/data]

  api:
    build:
      context: .
      dockerfile: docker/api.Dockerfile
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql://meridian:meridian@postgres:5432/meridian
      REDIS_URL: redis://redis:6379
      APP_ENV: development
      # ... other env vars from .env.local
    volumes:
      - ./app:/app/app
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  worker:
    build:
      context: .
      dockerfile: docker/worker.Dockerfile
    environment:
      DATABASE_URL: postgresql://meridian:meridian@postgres:5432/meridian
      REDIS_URL: redis://redis:6379
      APP_ENV: development
    volumes:
      - ./app:/app/app
    depends_on:
      postgres:
        condition: service_healthy
    command: python -m app.workers.main

  web:
    build:
      context: ./web
      dockerfile: Dockerfile
    ports: ["3000:3000"]
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000/v1
      NEXT_PUBLIC_WS_URL: ws://localhost:8000/v1
    volumes:
      - ./web/src:/app/src
      - ./web/package.json:/app/package.json
    command: npm run dev

volumes:
  postgres_data:
  redis_data:
```

### 9.2 `scripts/init-extensions.sql`

```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

### 9.3 Start Local Stack

```bash
# 1. Copy env template
cp .env.example .env.local

# 2. Start services
docker-compose up -d

# 3. Run migrations
docker-compose exec api alembic upgrade head

# 4. Seed Meridian AP ontology
docker-compose exec api python scripts/seed_meridian.py

# 5. Load test corpus
docker-compose exec api python scripts/load_meridian_corpus.py

# 6. Open UIs
# API Docs: http://localhost:8000/docs
# Web App: http://localhost:3000
# Flower (Celery monitor): http://localhost:5555 (if using Celery)
```

---

## 10. Monitoring & Observability

### 10.1 Health Checks

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness (API + DB connection) |
| `GET /health/ready` | Readiness (DB + Redis + Workers) |
| `GET /health/workers` | Worker queue depth, active jobs |

### 10.2 Key Metrics (Prometheus/OpenTelemetry)

| Metric | Type | Alert Threshold |
|---|---|---|
| `api_request_duration_seconds` | Histogram | p99 > 30s |
| `api_requests_total` | Counter | Rate drop > 50% |
| `worker_job_duration_seconds` | Histogram | p99 > 10min |
| `worker_queue_depth` | Gauge | > 1000 for 5min |
| `db_connections_active` | Gauge | > 80% pool |
| `llm_tokens_total` | Counter | Cost > budget |
| `embedding_cache_hit_rate` | Gauge | < 80% |
| `verifier_failure_rate` | Gauge | > 10% |

### 10.3 Logging

- **Format**: JSON (structured)
- **Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Fields**: `timestamp`, `level`, `logger`, `message`, `tenant_id`, `request_id`, `user_id`, `duration_ms`
- **PII**: Automatically redacted by middleware

---

## 11. Backup & Disaster Recovery

| Component | Backup Strategy | RPO | RTO |
|---|---|---|---|
| **Neon Postgres** | Point-in-time recovery (7 days) | < 1 min | < 15 min |
| **R2 Files** | Cross-region replication | 0 | < 5 min |
| **Redis** | AOF + RDB snapshots | < 1 sec | < 5 min |
| **Config/Secrets** | GitOps (encrypted in repo) | 0 | < 5 min |

---

## 12. Security Checklist

- [ ] All secrets in environment variables (never in code)
- [ ] JWT tokens short-lived (60 min) + refresh tokens
- [ ] Row Level Security on all tenant tables
- [ ] PII redaction before any LLM call
- [ ] Rate limiting on all public endpoints
- [ ] CORS restricted to known origins
- [ ] Security headers (CSP, HSTS, X-Frame-Options)
- [ ] Dependency scanning (Dependabot + Trivy)
- [ ] Container scanning (Trivy in CI)
- [ ] Penetration testing quarterly