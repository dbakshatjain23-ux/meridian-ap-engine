# MERIDIAN SHARED SERVICES · ENTERPRISE KNOWLEDGE ENGINE
## Master AI Coding Prompt Guide (`Meridian_AP_MASTER_PROMPT_GUIDE.md`)

---

## 1. How to Use This Prompt Guide

This document contains **production-grade master prompts** designed to instruct any advanced AI coding assistant (e.g. Claude 3.5 Sonnet, ChatGPT GPT-4o, Cursor AI, Devin, GitHub Copilot Workspace) to implement the **Meridian Accounts Payable Enterprise Knowledge Engine** from scratch.

When initiating development in an IDE or chat interface, supply the technical specification files from the `/docs/` folder alongside the relevant master prompt below.

---

## 2. Master System Generation Prompt (Pass to AI Chatbot / IDE)

```markdown
SYSTEM INSTRUCTION:
You are an Expert Lead Systems Architect and Senior Full-Stack AI Engineer. Your goal is to build the production codebase for the "Meridian Accounts Payable Enterprise Knowledge Engine" deployed on Zoho Catalyst (Python 3.12 AppLogic + Node.js 18 Middleware + React Frontend).

Refer strictly to the specification documents provided in `/docs/`:
- `Meridian_AP_PRD.md`
- `Meridian_AP_SYSTEM_ARCHITECTURE.md`
- `Meridian_AP_DB_SCHEMA_AND_GRAPH.md`
- `Meridian_AP_CALCULATORS_AND_TRIAGE_SPEC.md`
- `Meridian_AP_API_SPECIFICATION.md`
- `Meridian_AP_DEPLOYMENT_ZOHO_CATALYST.md`
- `Meridian_AP_EVALUATION_AND_TESTING_SUITE.md`
- `Meridian_AP_STARTER_REPO_CONFIG.md`

### Core Engineering Requirements:
1. **Multi-LLM Provider Adapter**: Implement `functions/python_applogic/adapter/llm_adapter.py` using LiteLLM to allow seamless runtime switching between OpenAI (`gpt-4o`), Gemini (`gemini-1.5-pro`), Nemotron (`nvidia/nemotron-4-340b-instruct`), and Claude (`claude-3-5-sonnet-20240620`).
2. **3-Lane Execution Engine**:
   - **Lane 1 (Computable 54%)**: Route price tolerance, e-invoice thresholds, approval limits, MSME payment runs, and string normalization queries directly to Python math calculators.
   - **Lane 2 (Lookup 28%)**: Execute scoped cited retrieval filtered by Client Desk (`Arvana Infra/Pharma/Retail`) and invoice `as_of_date`.
   - **Lane 3 (Judgment / Tacit 18%)**: Run `classify_tds` pre-calculation triage for AMC classification and present approved expert practice cards side-by-side with written SOP rules.
3. **5 Deterministic Python Calculators**: Implement clean, type-hinted code for `calculate_price_variance`, `classify_tds` / `calculate_tds`, `calculate_msme_due_date`, `validate_e_invoice_requirement`, and `normalize_supplier_string` in `functions/python_applogic/calculators/`.
4. **The 6 Mandatory Abstention Gates**: Enforce hard stop rules returning `TDS_SECTION_UNCLEAR` or refusing un-grounded queries to route them to human owners (Sandeep Rao for process / Imran Qureshi for tax).
5. **PII Regex Scrubber**: Implement Node.js middleware in `functions/node_middleware/middleware/pii_scrubber.js` to redact PAN numbers and bank account details under the DPDP Act 2023 before any data reaches external models.
6. **Pytest & Acceptance Test Suite**: Implement `tests/test_calculators.py` and `tests/test_acceptance_t1_t10.py` verifying acceptance test cases T1 through T10.

Begin by setting up the project scaffolding, helper modules, and calculator implementations following the exact schemas defined in the docs. Produce complete, production-ready code with no placeholder comments or omitted logic.
```

---

## 3. Sub-Task Generation Prompts

### Prompt A — Python Calculator Engine & TDS Triage
```markdown
Write the Python 3.12 implementation for `functions/python_applogic/calculators/`:
1. `price_variance.py`: `calculate_price_variance(po_line_val, po_unit_price, inv_unit_price, inv_qty, as_of_date, vendor_id)` computing excess line value vs `min(price_tol.pct * po_line_val, price_tol.cap)`.
2. `tds_triage.py`: `classify_tds(payment_description, vendor_category, contract_type)` returning 194C, 194J_2, 194J_10, 194I, 194Q, or `TDS_SECTION_UNCLEAR`. Also implement `calculate_tds(taxable_value_inr, section_code, pan_status, as_of_date)` excluding GST from the tax base and applying the higher 20% no-PAN rate.
3. `msme_due_date.py`: `calculate_msme_due_date(invoice_date, delivery_date, vendor_id, agreement_days)` applying 15/45-day caps only to Micro/Small suppliers and mapping to the preceding Tuesday/Friday run.
4. `e_invoice_check.py`: `validate_e_invoice_requirement(vendor_id, invoice_total_inr, as_of_date)` checking supplier AATO turnover against the ₹5 Crore threshold.
5. `supplier_normalizer.py`: `normalize_supplier_string(invoice_num_str)` stripping spaces, hyphens, slashes, leading zeros, and `/A` or `-REV` resubmission suffixes.
```

### Prompt B — Multi-LLM Provider Adapter & Prompts
```markdown
Implement `functions/python_applogic/adapter/llm_adapter.py` and `prompts.py`.
The `LLMAdapter` class must wrap `litellm.completion()` to support OpenAI, Gemini, Nemotron, and Claude based on `os.getenv("LLM_PROVIDER")`.
Include structured JSON schema extraction helpers and error-handling retries.
```

### Prompt C — Express API & DPDP PII Regex Scrubber
```markdown
Implement `functions/node_middleware/index.js` and `middleware/pii_scrubber.js`.
`pii_scrubber.js` must scan request bodies using regular expressions for Indian Permanent Account Numbers (PAN: `[A-Z]{5}[0-9]{4}[A-Z]{1}`) and bank account numbers, replacing matches with `[REDACTED_PAN]` and `[REDACTED_BANK_ACCOUNT]` before forwarding requests to the Python AppLogic function or external APIs.
```

### Prompt D — Acceptance Test Verification Suite (T1–T10)
```markdown
Implement `tests/test_acceptance_t1_t10.py` using `pytest`.
Write explicit test functions for each acceptance test T1 through T10 specified in `Meridian_AP_EVALUATION_AND_TESTING_SUITE.md`, validating the 3-lane routing, calculator outputs, side-by-side rule vs practice display, and abstention fallbacks.
```
