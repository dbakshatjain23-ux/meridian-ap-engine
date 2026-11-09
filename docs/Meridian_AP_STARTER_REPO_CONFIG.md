# MERIDIAN SHARED SERVICES · ENTERPRISE KNOWLEDGE ENGINE
## Production Starter Repository Setup & Configuration Guide (`Meridian_AP_STARTER_REPO_CONFIG.md`)

---

## 1. Directory Tree & File Inventory

```text
meridian-ap-knowledge-engine/
├── .github/
│   └── workflows/
│       ├── deploy_catalyst.yml          # CI/CD deployment pipeline to Zoho Catalyst
│       └── run_eval_suite.yml           # Automated Pytest + Ragas evaluation runner
├── catalyst.json                        # Master Zoho Catalyst CLI project configuration
├── .env.example                         # Multi-LLM API keys (OpenAI / Gemini / Nemotron / Claude)
├── docs/                                # System Design & Technical Specifications
│   ├── Meridian_AP_PRD.md
│   ├── Meridian_AP_SYSTEM_ARCHITECTURE.md
│   ├── Meridian_AP_DB_SCHEMA_AND_GRAPH.md
│   ├── Meridian_AP_CALCULATORS_AND_TRIAGE_SPEC.md
│   ├── Meridian_AP_API_SPECIFICATION.md
│   ├── Meridian_AP_DEPLOYMENT_ZOHO_CATALYST.md
│   └── Meridian_AP_EVALUATION_AND_TESTING_SUITE.md
├── functions/
│   ├── python_applogic/                 # Catalyst Python 3.12 Serverless AppLogic
│   │   ├── main.py                      # AppLogic handler & execution router
│   │   ├── requirements.txt             # Python dependencies
│   │   ├── adapter/
│   │   │   ├── llm_adapter.py           # Multi-LLM Provider Switcher Class
│   │   │   └── prompts.py               # Versioned prompt templates & JSON schemas
│   │   ├── calculators/
│   │   │   ├── __init__.py
│   │   │   ├── price_variance.py        # calculate_price_variance logic
│   │   │   ├── tds_triage.py            # classify_tds & calculate_tds logic
│   │   │   ├── msme_due_date.py         # calculate_msme_due_date logic
│   │   │   ├── e_invoice_check.py       # validate_e_invoice_requirement logic
│   │   │   └── supplier_normalizer.py   # normalize_supplier_string (Zingg algorithm)
│   │   ├── graph/
│   │   │   ├── temporal_graph.py        # Zep / Graphiti Temporal Memory interface
│   │   │   └── claim_store.py           # Catalyst Data Store claim query & filter layer
│   │   └── governance/
│   │       ├── conflict_scanner.py      # ConflictRAG 2-Stage MLP Classifier & TOPSIS
│   │       └── abstention_rules.py      # The 6 mandatory stop & escalation gates
│   │
│   └── node_middleware/                 # Catalyst Node.js 18+ Webhook & API Gateway
│       ├── index.js                     # Express API entrypoint & route handler
│       ├── package.json                 # Node.js dependencies
│       ├── middleware/
│       │   ├── pii_scrubber.js          # DPDP Act 2023 pre-LLM Regex Scrubber (PAN/Bank)
│       │   └── auth_guard.js            # Catalyst Auth & Role-Based Access Control
│       └── routes/
│           ├── query_routes.js          # Processor Assistant REST endpoints
│           ├── tacit_routes.js          # Tacit Knowledge Capture Studio endpoints
│           └── teams_webhook.js         # MS Teams Bot integration endpoint
├── circuits/                            # Catalyst Scheduled Jobs & Event Triggers
│   ├── conflict_scan_circuit/           # Daily cross-document redline scan trigger
│   └── tacit_expiry_circuit/            # 6-month TTL tacit card review notifier
├── client/                              # Front-End Web Application (React / Vite)
│   ├── package.json
│   ├── src/
│   │   ├── components/
│   │   │   ├── ProcessorWidget.jsx      # In-workflow ERP exception assistant
│   │   │   ├── RedlineDashboard.jsx     # Process Owner governance dashboard
│   │   │   └── TacitCaptureStudio.jsx   # Interactive expert exit interview UI
│   │   └── App.jsx
└── tests/                               # Comprehensive Test & Evaluation Suite
    ├── pytest.ini
    ├── test_calculators.py              # Unit tests for 5 Python math tools
    ├── test_acceptance_t1_t10.py        # Verification runner for T1–T10 acceptance cases
    └── test_ragas_eval.py              # Automated 160-question gold set evaluator
```

---

## 2. Configuration Files

### `catalyst.json`
```json
{
  "project_name": "meridian-ap-knowledge-engine",
  "functions": {
    "target": "functions",
    "ignore": [".git", "node_modules", "__pycache__"],
    "functions": [
      {
        "name": "python_applogic",
        "type": "AppLogic",
        "stack": "Python3.12",
        "entry": "main.py"
      },
      {
        "name": "node_middleware",
        "type": "BasicIO",
        "stack": "Nodejs18",
        "entry": "index.js"
      }
    ]
  },
  "client": {
    "source": "client/dist"
  },
  "cron": [
    {
      "name": "Daily_Corpus_Conflict_Scan",
      "cron_expression": "0 0 * * *",
      "target_function": "python_applogic"
    },
    {
      "name": "Tacit_Card_6Month_TTL_Review",
      "cron_expression": "0 6 * * *",
      "target_function": "python_applogic"
    }
  ]
}
```

### `.env.example`
```env
# Multi-LLM Provider Selection: openai | gemini | nemotron | claude
LLM_PROVIDER=gemini

# API Keys
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIzaSy...
NVIDIA_NEMOTRON_API_KEY=nvapi-...
ANTHROPIC_API_KEY=sk-ant-...

# Zep Temporal Memory Connection
ZEP_API_URL=http://localhost:8000
ZEP_API_KEY=zep_key_...

# Zoho Catalyst Credentials
CATALYST_PROJECT_ID=100029384
CATALYST_AUTH_TOKEN=cat_auth_...
```

### `functions/python_applogic/requirements.txt`
```text
openai>=1.30.0
google-generativeai>=0.5.0
anthropic>=0.25.0
litellm>=1.35.0
zep-python>=2.0.0
neo4j>=5.18.0
ragas>=0.1.7
numpy>=1.26.0
pandas>=2.2.0
rapidfuzz>=3.8.0
pytest>=8.0.0
scipy>=1.12.0
```

---

## 3. Initialization Steps

1. **Clone & Setup Directory**: Create the folder structure and place all 7 architecture `.md` files into `/docs/`.
2. **Initialize Zoho Catalyst CLI**:
   ```bash
   catalyst login
   catalyst init
   ```
3. **Install Dependencies**:
   ```bash
   cd functions/python_applogic && pip install -r requirements.txt
   cd ../node_middleware && npm install
   cd ../../client && npm install
   ```
4. **Run Unit Verification**:
   ```bash
   pytest tests/test_calculators.py
   ```
