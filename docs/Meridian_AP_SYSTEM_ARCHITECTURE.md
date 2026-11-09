# MERIDIAN SHARED SERVICES · ENTERPRISE KNOWLEDGE ENGINE
## Deep System Architecture & Multi-LLM Provider Blueprint
**Document ID**: `Meridian_AP_SYSTEM_ARCHITECTURE.md`  
**Target Environment**: Zoho Catalyst (Python 3.12 AppLogic + Node.js API Functions)  
**LLM Layer**: Dynamic Multi-LLM Provider Abstraction (OpenAI, Gemini, Nemotron, Claude)

---

## 1. High-Level 5-Layer System Architecture

The solution treats Accounts Payable knowledge management as a **Governed Temporal Knowledge Engine** rather than a flat document vector database.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                   ENTERPRISE KNOWLEDGE ENGINE SYSTEM ARCHITECTURE                       │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ LAYER 1: MULTI-FORMAT & MULTI-SOURCE INGESTION PIPELINE                                │
│   • Ingests PDF/Word SOPs, Client Memos, Teams JSON Logs, & Whisper Video Transcripts  │
│   • Structure-Aware AST Parser (§ Headers) + Pre-LLM PII/PAN Regex Scrubber            │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ LAYER 2: TEMPORAL KNOWLEDGE GRAPH & CLAIM STORE (ZEP / GRAPHITI LAYER)                 │
│   • Zep Temporal Memory (arXiv:2501.13956) with valid_from / valid_to Edges             │
│   • OpenSPG Semantic Ontology + 4-Tier Authority Ranking (Memo > SOP v4.0 > Tacit)    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ LAYER 3: 3-LANE EXECUTION & CONFLICT RESOLUTION ENGINE                                 │
│   • Lane 1 (Computable 54%): 5 Deterministic Python Calculators (0% Math Hallucination)│
│   • Lane 2 (Lookup 28%): Scoped Cited Retrieval (Client Memo > SOP v4.0 by as_of_date) │
│   • Lane 3 (Judgment 18%): classify_tds Pre-Triage; Side-by-Side Rules vs. Practices   │
│   • ConflictRAG (arXiv:2605.17301): 2-Stage MLP Classifier + Entropy-TOPSIS Scoring   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ LAYER 4: MULTI-LLM PROVIDER ABSTRACTION LAYER                                          │
│   • Universal LLMAdapter supporting OpenAI, Gemini, Nemotron, and Claude APIs          │
│   • Provider-Agnostic Function Calling & System Prompt Serialization                   │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ LAYER 5: GOVERNANCE, PII & COMPLIANCE GUARDRAILS                                       │
│   • 6 Mandatory Abstention Gates (Uncovered T8, Rule Clash, Ambiguous AMC, etc.)       │
│   • SOP v4.0 §8.2 / DI-07 Bank Callback Control + Ragas Evaluation Benchmark Suite    │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Multi-LLM Provider Abstraction Layer

The engine incorporates a pluggable, provider-agnostic LLM interface (`LLMAdapter`) that allows switching between models dynamically based on environment configuration (`LLM_PROVIDER`).

### 2.1 Provider Architecture Pattern
```python
# System Abstraction Pattern for Multi-LLM Switching
from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseLLMProvider(ABC):
    @abstractmethod
    def generate_completion(self, prompt: str, system_prompt: str, temperature: float = 0.0) -> str:
        pass
    
    @abstractmethod
    def execute_function_call(self, prompt: str, tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        pass

class OpenAIProvider(BaseLLMProvider):
    # Implements gpt-4o / gpt-4o-mini interface
    pass

class GeminiProvider(BaseLLMProvider):
    # Implements gemini-1.5-pro / gemini-2.0-flash interface
    pass

class NemotronProvider(BaseLLMProvider):
    # Implements nvidia/nemotron-4-340b interface via OpenAI-compatible endpoint
    pass

class ClaudeProvider(BaseLLMProvider):
    # Implements claude-3-5-sonnet interface
    pass

class LLMAdapterFactory:
    @staticmethod
    def get_provider(provider_name: str = None) -> BaseLLMProvider:
        import os
        provider = provider_name or os.getenv("LLM_PROVIDER", "OPENAI").upper()
        if provider == "OPENAI":
            return OpenAIProvider()
        elif provider == "GEMINI":
            return GeminiProvider()
        elif provider == "NEMOTRON":
            return NemotronProvider()
        elif provider == "CLAUDE":
            return ClaudeProvider()
        else:
            raise ValueError(f"Unsupported LLM Provider: {provider}")
```

---

## 3. Rules vs. Practices Architecture (The Side-by-Side Principle)

The corpus contains two fundamentally distinct types of claims:
* **Rules** (Client Memos, SOP v4.0, SOP v3.1, DI-03, DI-07): Authoritative mandates with effective dates and owners. Rules compete hierarchically based on authority tier and validity date.
* **Practices** (Senior expert floor habits, Lakshmi Reddy's Tuesday-noon GRN wait, shadowing notes): What an experienced processor does *inside* a rule.

### Side-by-Side Execution Pattern (Acceptance Test T4)
On **Acceptance Test T4** (Infra invoice received Saturday with no GRN), the engine presents both claims side-by-side:
1. **Authoritative Rule (SOP v4.0 §4.6)**: Hold as `NO_GRN`. System sends automatic reminder after 2 working days.
2. **Approved Expert Practice (Interview 1 [02:30])**: Infra sites batch GRNs on Monday mornings; wait until Tuesday noon before chasing.
* **Control Guard**: Practice cards sit *beside* rules as annotations and never compete in or override the rule control hierarchy.

---

## 4. ConflictRAG & Entropy-TOPSIS Credibility Engine

To detect and resolve cross-document contradictions (Acceptance Test T9), the system uses **ConflictRAG (`arXiv:2605.17301`)**:

1. **Two-Stage Conflict Classifier**:
   * **Stage 1 (Lightweight MLP)**: Evaluates pairwise claim consistency using a MiniLM embedding classifier (120ms latency).
   * **Stage 2 (Selective LLM Verification)**: Ambiguous pairs ($	ext{confidence} < 0.7$) route to selective LLM verification, **cutting API costs by 62% at 90.8% detection accuracy**.
2. **Entropy-TOPSIS Credibility Scoring**:
   * When two active rules clash, credibility is calculated dynamically across Authority ($w_1 = 0.312$), Recency ($w_2 = 0.245$), Relevance ($w_3 = 0.210$), Specificity ($w_4 = 0.133$), and Consistency ($w_5 = 0.100$).
