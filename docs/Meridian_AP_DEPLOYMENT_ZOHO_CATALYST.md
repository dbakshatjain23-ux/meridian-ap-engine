# MERIDIAN SHARED SERVICES · ENTERPRISE KNOWLEDGE ENGINE
## Zoho Catalyst Infrastructure & Deployment Architecture
**Document ID**: `Meridian_AP_DEPLOYMENT_ZOHO_CATALYST.md`  
**Target Environment**: Zoho Catalyst Serverless Infrastructure  

---

## 1. Zoho Catalyst Architecture Mapping

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   ZOHO CATALYST DEPLOYMENT ARCHITECTURE                                │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. APPLOGIC SERVERLESS FUNCTIONS (Python 3.12)                                        │
│    • 5 Deterministic Math Calculators (calculate_price_variance, classify_tds, etc.)  │
│    • Zep Temporal Knowledge Graph Traversal Engine (OpenSPG Ontology)                 │
│    • ConflictRAG 2-Stage MLP Classifier & Entropy-TOPSIS Scoring Engine                │
│    • Universal LLMAdapter (OpenAI / Gemini / Nemotron / Claude API switching)          │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 2. SERVERLESS NODE.JS FUNCTIONS & MIDDLEWARE                                          │
│    • MS Teams Bot Webhook Receiver & Handler                                           │
│    • REST API Router (/api/v1/query/ask, /api/v1/tacit/capture)                        │
│    • Pre-LLM Regex PII Scrubber (PAN, Bank Accounts, DPDP Act 2023 Masking)            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 3. CATALYST DATA STORE (Relational SQL DB)                                             │
│    • Tables: claims, passages, vendors, practices, invoices                            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 4. CATALYST CIRCUITS & CRON JOBS                                                       │
│    • Scheduled Conflict Scanner: Runs weekly cross-document graph diff (Test T9)      │
│    • Tacit TTL Expiry Cron: Sends automated pings to Sandeep Rao for 6-month TTL cards │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Environment Configuration (`catalyst.json` & `.env`)

```bash
# Environment Configuration Variables
CATALYST_ENV="production"
LLM_PROVIDER="GEMINI" # Options: OPENAI | GEMINI | NEMOTRON | CLAUDE

# LLM Provider API Key Placeholders
OPENAI_API_KEY="ENV_OPENAI_API_KEY"
GEMINI_API_KEY="ENV_GEMINI_API_KEY"
NEMOTRON_API_KEY="ENV_NEMOTRON_API_KEY"
CLAUDE_API_KEY="ENV_CLAUDE_API_KEY"

# Security & Vector DB Configuration
PII_REGEX_MASKING="true"
ZEP_API_URL="ENV_ZEP_API_URL"
ZEP_API_KEY="ENV_ZEP_API_KEY"
```

---

## 3. Deployment CLI Commands

```bash
# Initialize Zoho Catalyst Project
catalyst init

# Test Functions Locally
catalyst serve

# Deploy Entire Stack to Zoho Catalyst Cloud
catalyst deploy --only functions,datastore,circuits
```
