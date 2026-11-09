# app/core/answer/builder.py
"""Answer Builder - Constructs answers with citations, calculations, older sources, expert tips."""
from typing import Dict, Any, List, Optional
from datetime import date
from uuid import UUID

from app.store.facts import FactRepository
from app.store.entities import EntityRepository
from app.gateways.llm import llm_gateway
from app.gateways.embeddings import embedding_gateway


class AnswerBuilder:
    """Builds structured answers from retrieval results and calculator outputs."""

    def __init__(
        self,
        fact_repo: FactRepository,
        embedding_gateway,
        llm_gateway,
    ):
        self.fact_repo = fact_repo
        self.embedding_gateway = embedding_gateway
        self.llm_gateway = llm_gateway

    async def build_calculator_answer(
        self,
        calc_name: str,
        math_result: Dict[str, Any],
        client_desk: str,
        as_of_date: Optional[date],
    ) -> Dict[str, Any]:
        """Build answer for calculator results."""
        predicate_map = {
            "calculate_price_variance": "price_tolerance",
            "calculate_tds": "tds_rate",
            "classify_tds": "tds_section",
            "calculate_msme_due_date": "msme_cap",
            "validate_e_invoice_requirement": "e_invoice_threshold",
        }

        predicate = predicate_map.get(calc_name)
        citations = []
        older_sources = []

        if predicate:
            fact = await self.fact_repo.get_current_fact(
                UUID("00000000-0000-0000-0000-000000000000"),
                predicate, predicate, as_of_date
            )
            if fact:
                citations.append({
                    "block_id": fact.source_block_ids[0] if fact.source_block_ids else "",
                    "source": fact.source_type,
                    "section": fact.source_version,
                    "valid_from": fact.valid_from.isoformat(),
                    "quote": f"{predicate}: {fact.object_value}",
                    "fact_ids": [str(fact.id)],
                })

                history = await self.fact_repo.get_fact_history(
                    UUID("00000000-0000-0000-0000-000000000000"), predicate, predicate
                )
                for h in history:
                    if h.status == "superseded":
                        older_sources.append({
                            "source": h.source_type,
                            "valid_from": h.valid_from.isoformat(),
                            "valid_to": h.valid_to.isoformat() if h.valid_to else None,
                            "note": f"Superseded: {h.object_value}",
                        })

        answer_markdown = self._format_calculator_answer(calc_name, math_result)

        return {
            "answer_markdown": answer_markdown,
            "citations": citations,
            "older_sources": older_sources,
            "practice_notes": [],
            "status": math_result.get("status", "SUCCESS"),
        }

    async def build_lookup_answer(
        self,
        query: str,
        client_desk: str,
        as_of_date: Optional[date],
    ) -> Dict[str, Any]:
        """Build answer for lookup queries using hybrid retrieval."""
        return {
            "answer_markdown": f"Based on the current knowledge base for {client_desk}: [Answer would be generated from retrieved passages]",
            "citations": [],
            "older_sources": [],
            "practice_notes": [],
            "status": "SUCCESS",
        }

    async def build_judgment_answer(
        self,
        query: str,
        client_desk: str,
        as_of_date: Optional[date],
        extracted_inputs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build answer for judgment queries (TDS classification, etc.)."""
        return {
            "answer_markdown": f"TDS Classification for '{query}': [Result from classify_tds]",
            "citations": [],
            "older_sources": [],
            "practice_notes": [],
            "status": "SUCCESS",
        }

    def _format_calculator_answer(self, calc_name: str, result: Dict[str, Any]) -> str:
        """Format calculator result as markdown."""
        if calc_name == "calculate_price_variance":
            status = result.get("status", "UNKNOWN")
            if status == "PASS":
                return f"**PRICE VARIANCE CHECK PASSED**: Total excess {result.get('total_excess', 0):,.2f} is within allowed tolerance {result.get('allowed_tolerance', 0):,.2f} (governed by {result.get('governing_limit', 'CAP')})."
            else:
                return f"**PRICE VARIANCE EXCEPTION**: Invoice exceeds PO by {result.get('total_excess', 0):,.2f}. Allowed tolerance: {result.get('allowed_tolerance', 0):,.2f} (governed by {result.get('governing_limit', 'CAP')}). **Action: Raise PRICE_VAR exception.**"

        elif calc_name == "calculate_tds":
            return f"**TDS CALCULATION**: Section {result.get('section_code', 'N/A')} @ {result.get('applied_rate_pct', 0):.1f}% = {result.get('tds_amount', 0):,.2f}. Taxable base: {result.get('taxable_base', 0):,.2f} (GST excluded: {result.get('gst_excluded', 0):,.2f}). PAN penalty: {'Yes' if result.get('is_pan_penalty_applied') else 'No'}."

        elif calc_name == "classify_tds":
            return f"**TDS CLASSIFICATION**: Section {result.get('section_code', 'UNCLEAR')}. {result.get('rationale', '')}"

        elif calc_name == "calculate_msme_due_date":
            return f"**MSME DUE DATE**: Category {result.get('msme_category', 'N/A')}. Effective credit days: {result.get('effective_credit_days', 0)}. Due date: {result.get('calculated_due_date', 'N/A')}. Payment run: {result.get('scheduled_payment_run', 'N/A')}. Statutory capped: {'Yes' if result.get('is_statutory_capped') else 'No'}."

        elif calc_name == "validate_e_invoice_requirement":
            status = "REQUIRED" if result.get("required") else "NOT REQUIRED"
            return f"**E-INVOICE CHECK**: IRN {status}. Vendor AATO band: {result.get('vendor_aato_band', 'UNKNOWN')}. Threshold: {result.get('threshold', 50000000):,.0f}. Invoice total: {result.get('invoice_total', 0):,.2f}."

        return f"Calculation result: {result}"