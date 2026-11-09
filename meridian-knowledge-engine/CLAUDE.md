# CLAUDE.md - Context for Claude Code

## Project Overview

**Meridian Knowledge Engine** - Generic Dual-Clock Temporal Knowledge Engine with Industry Plug-ins.

**Meridian AP** = First industry plug-in (Accounts Payable for Meridian Shared Services).

## Architecture Summary

**Generic Core** (knows nothing about AP/tax):
- Dual-clock temporal graph (Postgres native, no Zep/Graphiti)
- 5-tier ingestion parser → unified blocks
- Hybrid retrieval (keyword + vector + graph walk → RRF → rerank)
- 4-check verifier + 7 guardrails + escalation loop
- Live capture connectors (Email, Teams, Meetings, Drive)
- Delivery layer (REST, Teams App, ERP Embed, Browser Ext)
- SOP Sync (redline → SharePoint/Git → ack tracking)

**AP Plug-in** (Meridian-specific):
- 6 deterministic calculators reading params from graph
- TDS classification + calculation
- Meridian ontology (clients, vendors, policies, regulations)
- Side-by-side rules vs practices (T4)
- 6-month TTL tacit capture lifecycle

## Key Files to Reference

| File | Purpose |
|------|---------|
| `docs/Meridian_AP_HYBRID_SPEC.md` | **Single source of truth** - read first |
| `docs/Meridian_AP_PRD.md` | Product requirements, 8 problem chunks, acceptance criteria |
| `docs/Meridian_AP_SYSTEM_ARCHITECTURE.md` | 6-layer architecture, LLM gateway, retrieval |
| `docs/Meridian_AP_DB_SCHEMA_AND_GRAPH.md` | Dual-clock Postgres schema, ontology |
| `docs/Meridian_AP_CALCULATORS_AND_TRIAGE_SPEC.md` | 6 calculators with exact implementations |
| `docs/Meridian_AP_API_SPECIFICATION.md` | REST + WS contracts |
| `docs/Meridian_AP_DEPLOYMENT.md` | Docker/Render/Vercel/Neon deployment |
| `docs/Meridian_AP_EVALUATION_AND_TESTING_SUITE.md` | T1-T10, Ragas, Generality proofs |

## Critical Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Graph Storage | Postgres native (dual-clock) | Single DB, GiST ranges, tenant isolation, no external dependency |
| Deployment | Render + Vercel + Neon | Managed, scalable, standard Python, no vendor lock-in |
| LLM Provider | Anthropic Only (Haiku/Sonnet) | Two-model tiering, simpler, cheaper, no failover complexity |
| Embeddings | BGE-small + Reranker (CPU) | Local, free, no API cost, fast enough |
| Background Jobs | Postgres SKIP LOCKED | No Redis/Celery, transactional, horizontal workers |
| Temporal Model | Dual-clock (Valid + Transaction + Retracted) | Answers "what was rule?" AND "what would engine say?" |
| Conflict Resolution | 4-Case Deterministic + TOPSIS | Auditable, owner-controllable, replaces MLP |
| Schema Learning | Auto + Owner Review + Baseline Mode | Generality proof, safety net |
| Parsing | 5-Tier → Unified Block List | Any format, no setup, structure from real signals |
| Answer Verification | Separate 4-Check Verifier | Model-agnostic, catches hallucinations |
| Escalation | Live Loop: Unanswered → Owner → Becomes Fact | Continuous learning, no stale answers |

## Current Phase: Phase 0 (Foundation)

**Goal**: Postgres schema, FastAPI skeleton, background worker, repository layer.

**Files to Create/Verify**:
- [ ] `docker-compose.yml` with Postgres+pgvector, Redis, API, Worker, Web
- [ ] `docker/api.Dockerfile` & `docker/worker.Dockerfile`
- [ ] `requirements.txt`, `requirements-ml.txt`, `requirements-dev.txt`
- [ ] `pyproject.toml` (ruff, mypy, pytest config)
- [ ] `alembic/` migration environment
- [ ] `app/main.py` FastAPI app factory with lifespan
- [ ] `app/config.py` Pydantic Settings (all env vars)
- [ ] `app/database.py` Async engine, session, Base
- [ ] `app/models/` 10 SQLAlchemy models (tenant, episode, block, entity, fact, conflict, job, answer_log, user)
- [ ] `app/store/` Repository classes (facts, episodes, blocks, entities, conflicts, jobs, answers, users)
- [ ] `alembic/versions/001_initial_schema.py` Full DDL with GiST/HNSW indexes
- [ ] `scripts/init-extensions.sql` Enable pgvector, pg_trgm, btree_gist, uuid-ossp

## Testing Requirements

**T1-T10 Acceptance Tests** (MUST PASS):
- T1: Price tolerance = lower of 1% or ₹500 (SOP v4.0 §4.2)
- T2: ₹8.9 Cr vendor without IRN → rejects under ₹5 Cr threshold
- T3: Pharma excipient QA release → requires CM-PHA-01, flags FAQ error
- T4: Saturday Infra no GRN → SOP v4.0 §4.6 SIDE-BY-SIDE with Lakshmi Tuesday-noon practice
- T5: PO ₹395, Invoice ₹400 (500 bags) → excess ₹2,500 vs limit ₹500 → PRICE_VAR
- T6: TDS on software ₹4.8L + GST → 194J @ 2% = ₹9,600 (excludes GST)
- T7: Micro supplier accepted 1 Aug → due 16 Aug (15d cap) → Fri 14 Aug payment run
- T8: Canteen subsidy → ABSTAINS → routes to Sandeep Rao
- T9: Conflict scanner → detects ≥12/15 planted conflicts
- T10: Tacit capture → creates fact with 6-month TTL, authority_rank=3

**Ragas Targets**: Faithfulness≥0.95, Relevance≥0.95, Precision≥0.90, Harm=0.00

## Code Quality Standards

- **Type Hints**: 100% (mypy strict)
- **Linting**: Ruff (line-length=100, target-version=py311)
- **Tests**: pytest-asyncio, coverage≥80% on core modules
- **Documentation**: Docstrings on all public classes/methods
- **No Placeholders**: Every function implemented, no `pass` or `TODO`
- **Security**: PII redaction before ANY LLM call, parameterized SQL only
- **Observability**: Structured logging, OpenTelemetry traces, Prometheus metrics

## Commands

```bash
# Local development
docker-compose up -d
docker-compose exec api alembic upgrade head
docker-compose exec api python scripts/seed_meridian.py
docker-compose exec api python scripts/load_meridian_corpus.py
docker-compose exec api pytest tests/acceptance/test_t1_t10.py -v

# Linting
docker-compose exec api ruff check app/
docker-compose exec api ruff format app/

# Type checking
docker-compose exec api mypy app/
```

## Environment Variables (Required)

```bash
ANTHROPIC_API_KEY=sk-ant-...           # Required
DATABASE_URL=postgresql://...           # Neon or local
JWT_SECRET_KEY=...                      # 64+ chars
REDIS_URL=redis://localhost:6379        # Local Redis
```

## Notes for Development

1. **Never hardcode calculator params** - Always read from `facts` table via `FactRepository`
2. **Dual clocks on every fact** - `valid_from/to` (world time) + `recorded_at/retracted_at` (system time)
3. **Atomic graph writes** - Close old (`retracted_at=now()`) + Open new in single transaction
4. **Authority ranking** - Lower rank = higher authority (1=Client Memo, 2=SOP v4.0, 3=Tacit, 4=Superseded)
5. **4-case conflict detection** - Direct contradiction, Parameter drift, Scope overlap, Authority clash
6. **Live capture** - Email, Teams, Meeting bots → Episode → Blocks → Facts (Phase 5+)
7. **Delivery layer** - ERP Embed, Teams App, Browser Extension, Webhooks (Phase 6+)
8. **SOP Sync** - Change detection → Redline → Push (SharePoint/Git) → Notify → Ack Track (Phase 7+)