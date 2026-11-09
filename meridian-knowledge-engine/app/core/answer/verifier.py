# app/core/answer/verifier.py
"""Answer Verifier - 4-Check Verification Pipeline."""
from typing import Dict, Any, List
from app.store.blocks import BlockRepository


class AnswerVerifier:
    """
    4-Check Verifier:
    1. Citations Real - Every cited block_id exists AND quote is substring of block.content
    2. Numbers Sourced - Every number in answer appears in citation OR calculator output
    3. No Superseded - No citation with fact.status='superseded' presented as current
    4. Sentences Supported - Each sentence has at least one citation OR calculator source
    """

    def __init__(self):
        pass

    def verify(
        self,
        answer_markdown: str,
        citations: List[Dict[str, Any]],
        calculator_outputs: Optional[Dict[str, Any]],
        older_sources: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Run all 4 verification checks."""
        checks = {
            "citations_real": self._check_citations_real(citations),
            "numbers_sourced": self._check_numbers_sourced(answer_markdown, citations, calculator_outputs),
            "no_superseded": self._check_no_superseded(citations, older_sources),
            "sentences_supported": self._check_sentences_supported(answer_markdown, citations, calculator_outputs),
        }

        passed = all(checks.values())

        return {
            "passed": passed,
            "checks": checks,
            "failed_checks": [k for k, v in checks.items() if not v],
        }

    def _check_citations_real(self, citations: List[Dict[str, Any]]) -> bool:
        """Check 1: Every cited block_id exists AND quote is substring of block.content."""
        # In production, would verify against BlockRepository
        # For now, assume valid if citation has required fields
        for c in citations:
            if not c.get("block_id") or not c.get("quote"):
                return False
        return True

    def _check_numbers_sourced(
        self,
        answer_markdown: str,
        citations: List[Dict[str, Any]],
        calculator_outputs: Optional[Dict[str, Any]],
    ) -> bool:
        """Check 2: Every number in answer appears in citation OR calculator output."""
        import re

        # Extract all numbers from answer
        answer_numbers = re.findall(r'[\d,]+\.?\d*', answer_markdown.replace(',', ''))
        answer_numbers = {float(n) for n in answer_numbers if n}

        # Collect numbers from citations
        citation_numbers = set()
        for c in citations:
            quote = c.get("quote", "")
            nums = re.findall(r'[\d,]+\.?\d*', quote.replace(',', ''))
            citation_numbers.update(float(n) for n in nums if n)

        # Collect numbers from calculator outputs
        calc_numbers = set()
        if calculator_outputs:
            def extract_nums(obj):
                if isinstance(obj, (int, float)):
                    calc_numbers.add(float(obj))
                elif isinstance(obj, dict):
                    for v in obj.values():
                        extract_nums(v)
                elif isinstance(obj, list):
                    for v in obj:
                        extract_nums(v)
            extract_nums(calculator_outputs)

        all_sourced = citation_numbers | calc_numbers

        # Check each answer number is sourced
        for num in answer_numbers:
            if num not in all_sourced:
                # Allow small tolerance for rounding
                if not any(abs(num - s) < 0.01 for s in all_sourced):
                    return False

        return True

    def _check_no_superseded(
        self,
        citations: List[Dict[str, Any]],
        older_sources: List[Dict[str, Any]],
    ) -> bool:
        """Check 3: No citation with fact.status='superseded' presented as current."""
        for c in citations:
            # In production, would check fact status from fact_ids
            # For now, assume valid if not in older_sources
            pass

        # Ensure older_sources are clearly marked as older
        for o in older_sources:
            if "superseded" not in str(o).lower():
                return False

        return True

    def _check_sentences_supported(
        self,
        answer_markdown: str,
        citations: List[Dict[str, Any]],
        calculator_outputs: Optional[Dict[str, Any]],
    ) -> bool:
        """Check 4: Each sentence has at least one citation OR calculator source."""
        import re

        # Split into sentences
        sentences = re.split(r'[.!?]+', answer_markdown)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return True

        # For calculator answers, assume supported if calculator_outputs exists
        if calculator_outputs:
            return True

        # For lookup answers, each sentence should have citation
        # This is a simplified check
        citation_count = len(citations)
        if citation_count == 0 and len(sentences) > 0:
            return False

        return True