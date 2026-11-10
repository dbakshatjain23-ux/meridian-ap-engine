# tests/integration/test_answer_pipeline.py
"""Integration tests for the complete answer pipeline."""
import pytest
import pytest_asyncio
from datetime import date
from uuid import UUID
from decimal import Decimal

from app.core.answer.router import CalculatorRouter
from app.core.answer.builder import AnswerBuilder
from app.core.answer.verifier import AnswerVerifier
from app.core.calculators import get_calculator
from app.core.calculators.base import CalculatorContext


class TestAnswerPipeline:
    """Integration tests for the complete answer pipeline."""

    @pytest.fixture
    def ctx(self):
        return CalculatorContext(
            tenant_id="meridian",
            client_desk="Arvana Infra",
            as_of_date="2026-08-01",
            vendor_id="V20000",
        )

    @pytest.mark.asyncio
    async def test_price_variance_pipeline(self, ctx):
        """Test complete price variance pipeline: route -> calculate -> build -> verify."""
        router = CalculatorRouter()

        # Route
        route_type, inputs = router.route(
            "PO price 395, invoice 400 for 500 bags. Pass or variance?",
            "Arvana Infra",
            "2026-08-01"
        )
        assert route_type == "computable"
        assert inputs["calculator"] == "calculate_price_variance"

        # Calculate
        calc = get_calculator("calculate_price_variance")
        result = await calc.calculate(ctx, inputs)

        # Verify calculation
        assert result["status"] == "PRICE_VAR"
        assert result["total_excess"] == 2500.0
        assert result["allowed_tolerance"] == 500.0

        # Build answer
        from app.store.facts import FactRepository
        from app.gateways.llm import llm_gateway
        from app.gateways.embeddings import embedding_gateway
        from app.database import get_session
        from app.store.facts import FactRepository

        # Note: Full integration would need a real session
        # For now, test the formatting
        from app.core.answer.builder import AnswerBuilder
        builder = AnswerBuilder(None, None, None)
        answer = builder._format_calculator_answer("calculate_price_variance", {
            "status": "PRICE_VAR",
            "total_excess": 2500.0,
            "allowed_tolerance": 500.0,
            "governing_limit": "CAP"
        })
        assert "PRICE VARIANCE EXCEPTION" in answer
        assert "2,500.00" in answer
        assert "500.00" in answer

    @pytest.mark.asyncio
    async def test_tds_pipeline(self, ctx):
        """Test TDS classification and calculation pipeline."""
        router = CalculatorRouter()

        # Test classification
        route_type, inputs = router.route(
            "TDS on software support, taxable value 480000 plus GST?",
            "ALL",
            "2026-08-01"
        )
        assert route_type == "computable"
        assert inputs["calculator"] == "classify_tds"

        calc = get_calculator("classify_tds")
        result = await calc.calculate(ctx, inputs)
        assert result["section_code"] == "194J"

        # Test calculation
        calc2 = get_calculator("calculate_tds")
        result2 = await calc2.calculate(ctx, {
            "section_code": "194J",
            "taxable_value_inr": 480000,
            "gst_inr": 86400,
            "is_corporate_vendor": True,
            "is_pan_available": True,
        })
        assert result2["tds_amount"] == 9600.0
        assert result2["section_code"] == "194J"

    @pytest.mark.asyncio
    async def test_msme_pipeline(self, ctx):
        """Test MSME due date pipeline."""
        router = CalculatorRouter()

        route_type, inputs = router.route(
            "Micro supplier accepted 1 Aug 2026, no agreement. Due date?",
            "ALL",
            "2026-08-01"
        )
        assert route_type == "computable"

        calc = get_calculator("calculate_msme_due_date")
        result = await calc.calculate(ctx, {
            "invoice_date": "2026-08-01",
            "acceptance_date": "2026-08-01",
            "msme_category": "MICRO",
            "has_written_agreement": False,
            "agreement_days": 60,
        })
        assert result["effective_credit_days"] == 15
        assert result["scheduled_payment_run"] == "2026-08-14"

    @pytest.mark.asyncio
    async def test_verifier(self):
        """Test the 4-check verifier."""
        verifier = AnswerVerifier()

        # Test passed verification
        result = verifier.verify(
            answer_markdown="**PRICE VARIANCE CHECK PASSED**: Total excess 100.00 within allowed tolerance 500.00.",
            citations=[{"block_id": "1", "quote": "price tolerance: 500", "fact_ids": ["1"]}],
            calculator_outputs={"allowed_tolerance": 500, "total_excess": 100},
            older_sources=[]
        )
        assert result["passed"] is True
        assert all(result["checks"].values())

        # Test failed verification - number not sourced
        result = verifier.verify(
            answer_markdown="Total excess is 999999.",
            citations=[{"block_id": "1", "quote": "price tolerance: 500"}],
            calculator_outputs={"allowed_tolerance": 500},
            older_sources=[]
        )
        assert result["passed"] is False
        assert result["checks"]["numbers_sourced"] is False

    @pytest.mark.asyncio
    async def test_router_refusal(self):
        """Test router refuses out-of-scope queries."""
        router = CalculatorRouter()
        route_type, inputs = router.route(
            "What is the canteen subsidy policy?",
            "ALL",
            "2026-08-01"
        )
        assert route_type == "refused"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])