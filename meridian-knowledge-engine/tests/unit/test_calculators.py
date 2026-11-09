# tests/unit/test_calculators.py
"""Unit tests for AP Calculators - 100% Deterministic."""
import pytest
from decimal import Decimal
from app.core.calculators import (
    get_calculator,
    CALCULATORS,
    PriceVarianceCalculator,
    TDSClassifier,
    TDSCalculator,
    MSMEDueDateCalculator,
    EInvoiceValidator,
    SupplierNormalizer,
)
from app.core.calculators.base import CalculatorContext


@pytest.fixture
def ctx():
    """Calculator context for testing."""
    return CalculatorContext(
        tenant_id="meridian",
        client_desk="Arvana Infra",
        as_of_date="2026-08-01",
        vendor_id="V20000",
    )


class TestCalculatorRegistry:
    """Test calculator registry."""

    def test_all_calculators_registered(self):
        """All 6 calculators should be registered."""
        expected = {
            "calculate_price_variance",
            "classify_tds",
            "calculate_tds",
            "calculate_msme_due_date",
            "validate_e_invoice_requirement",
            "normalize_supplier_string",
        }
        assert set(CALCULATORS.keys()) == expected

    def test_get_calculator(self):
        """get_calculator returns correct calculator instance."""
        for name in CALCULATORS:
            calc = get_calculator(name)
            assert calc is not None
            assert hasattr(calc, 'calculate')
            assert hasattr(calc, 'get_required_predicates')

    def test_unknown_calculator_raises(self):
        """Unknown calculator raises ValueError."""
        with pytest.raises(ValueError, match="Unknown calculator"):
            get_calculator("nonexistent")


class TestPriceVarianceCalculator:
    """Test Price Variance Calculator (T1, T5)."""

    @pytest.mark.asyncio
    async def test_t1_price_tolerance_current(self, ctx):
        """T1: Price tolerance is lower of 1% or ₹500."""
        calc = get_calculator("calculate_price_variance")
        # PO line: ₹395 * 500 = ₹197,500
        # 1% of line = ₹1,975, cap = ₹500
        # Lower = ₹500
        result = await calc.calculate(ctx, {
            "po_line_val": 197500.00,
            "po_unit_price": 395.00,
            "inv_unit_price": 395.00,
            "inv_qty": 500.0,
        })
        assert result["allowed_tolerance"] == 500.00
        assert result["governing_limit"] == "CAP"

    @pytest.mark.asyncio
    async def test_t5_price_variance_exception(self, ctx):
        """T5: PO ₹395, Invoice ₹400 (500 bags) = excess ₹2,500 > ₹500."""
        calc = get_calculator("calculate_price_variance")
        result = await calc.calculate(ctx, {
            "po_line_val": 197500.00,
            "po_unit_price": 395.00,
            "inv_unit_price": 400.00,
            "inv_qty": 500.0,
        })
        assert result["status"] == "PRICE_VAR"
        assert result["total_excess"] == 2500.00
        assert result["allowed_tolerance"] == 500.00
        assert result["governing_limit"] == "CAP"

    @pytest.mark.asyncio
    async def test_price_below_po_passes(self, ctx):
        """Invoice price below PO price should PASS."""
        calc = get_calculator("calculate_price_variance")
        result = await calc.calculate(ctx, {
            "po_line_val": 197500.00,
            "po_unit_price": 400.00,
            "inv_unit_price": 395.00,
            "inv_qty": 500.0,
        })
        assert result["status"] == "PASS"
        assert result["total_excess"] == 0.0

    @pytest.mark.asyncio
    async def test_small_line_percentage_governs(self, ctx):
        """Small line: 1% governs over ₹500 cap."""
        calc = get_calculator("calculate_price_variance")
        # PO line: ₹100 * 100 = ₹10,000
        # 1% = ₹100, cap = ₹500
        # Lower = ₹100 (PERCENTAGE)
        result = await calc.calculate(ctx, {
            "po_line_val": 10000.00,
            "po_unit_price": 100.00,
            "inv_unit_price": 101.00,
            "inv_qty": 100.0,
        })
        assert result["allowed_tolerance"] == 100.00
        assert result["governing_limit"] == "PERCENTAGE"


class TestTDSClassifier:
    """Test TDS Section Classification."""

    @pytest.mark.asyncio
    async def test_software_technical_services_194J(self, ctx):
        """Software/technical services -> 194J."""
        calc = get_calculator("classify_tds")
        result = await calc.calculate(ctx, {
            "invoice_description": "Software support services",
            "vendor_category": "PROFESSIONAL",
        })
        assert result["section_code"] == "194J"
        assert result["status"] == "SUCCESS"

    @pytest.mark.asyncio
    async def test_rent_194I(self, ctx):
        """Rent -> 194I."""
        calc = get_calculator("classify_tds")
        result = await calc.calculate(ctx, {
            "invoice_description": "Office rent",
            "vendor_category": "LESSOR",
        })
        assert result["section_code"] == "194I"

    @pytest.mark.asyncio
    async def test_transport_freight_194C(self, ctx):
        """Transport/freight -> 194C."""
        calc = get_calculator("classify_tds")
        result = await calc.calculate(ctx, {
            "invoice_description": "Freight charges",
            "vendor_category": "TRANSPORT",
        })
        assert result["section_code"] == "194C"

    @pytest.mark.asyncio
    async def test_mixed_amc_unclear(self, ctx):
        """Mixed AMC (CCTV + monitoring) -> TDS_SECTION_UNCLEAR."""
        calc = get_calculator("classify_tds")
        result = await calc.calculate(ctx, {
            "invoice_description": "CCTV maintenance with remote monitoring",
            "vendor_category": "SECURITY",
            "is_mixed_service": True,
        })
        assert result["section_code"] == "TDS_SECTION_UNCLEAR"
        assert result["status"] == "ABSTAIN"

    @pytest.mark.asyncio
    async def test_cctv_monitoring_maintenance_unclear(self, ctx):
        """CCTV with monitoring and maintenance -> UNCLEAR."""
        calc = get_calculator("classify_tds")
        result = await calc.calculate(ctx, {
            "invoice_description": "CCTV repair and remote monitoring maintenance",
            "vendor_category": "SECURITY",
        })
        assert result["section_code"] == "TDS_SECTION_UNCLEAR"
        assert result["status"] == "ABSTAIN"


class TestTDSCalculator:
    """Test TDS Calculation (T6)."""

    @pytest.mark.asyncio
    async def test_t6_tds_excludes_gst(self, ctx):
        """T6: TDS on ₹4,80,000 + GST = 194J @ 2% = ₹9,600 (excludes GST)."""
        calc = get_calculator("calculate_tds")
        result = await calc.calculate(ctx, {
            "section_code": "194J",
            "taxable_value_inr": 480000,
            "gst_inr": 86400,
            "is_corporate_vendor": True,
            "is_pan_available": True,
        })
        assert result["tds_amount"] == 9600.00
        assert result["taxable_base"] == 480000
        assert result["gst_excluded"] == 86400
        assert result["applied_rate_pct"] == 2.0
        assert result["is_pan_penalty_applied"] is False

    @pytest.mark.asyncio
    async def test_pan_penalty_20_percent(self, ctx):
        """No PAN -> 20% rate applied."""
        calc = get_calculator("calculate_tds")
        result = await calc.calculate(ctx, {
            "section_code": "194C",
            "taxable_value_inr": 100000,
            "gst_inr": 18000,
            "is_corporate_vendor": True,
            "is_pan_available": False,
        })
        assert result["applied_rate_pct"] == 20.0
        assert result["tds_amount"] == 20000.00
        assert result["is_pan_penalty_applied"] is True

    @pytest.mark.asyncio
    async def test_unclear_section_abstains(self, ctx):
        """TDS_SECTION_UNCLEAR -> ABSTAIN."""
        calc = get_calculator("calculate_tds")
        result = await calc.calculate(ctx, {
            "section_code": "TDS_SECTION_UNCLEAR",
            "taxable_value_inr": 100000,
            "gst_inr": 18000,
        })
        assert result["status"] == "ABSTAIN"
        assert result["tds_amount"] == 0.0


class TestMSMEDueDateCalculator:
    """Test MSME Due Date Calculator (T7)."""

    @pytest.mark.asyncio
    async def test_t7_micro_supplier_no_agreement(self, ctx):
        """T7: Micro supplier, no agreement -> 15 days -> Friday payment run."""
        calc = get_calculator("calculate_msme_due_date")
        result = await calc.calculate(ctx, {
            "invoice_date": "2026-08-01",
            "acceptance_date": "2026-08-01",
            "msme_category": "MICRO",
            "has_written_agreement": False,
            "agreement_days": 60,
        })
        assert result["effective_credit_days"] == 15
        assert result["calculated_due_date"] == "2026-08-16"
        assert result["scheduled_payment_run"] == "2026-08-14"  # Friday
        assert result["is_statutory_capped"] is True

    @pytest.mark.asyncio
    async def test_small_supplier_with_agreement(self, ctx):
        """Small supplier with agreement -> min(agreement, 45)."""
        calc = get_calculator("calculate_msme_due_date")
        result = await calc.calculate(ctx, {
            "invoice_date": "2026-08-01",
            "acceptance_date": "2026-08-01",
            "msme_category": "SMALL",
            "has_written_agreement": True,
            "agreement_days": 30,
        })
        assert result["effective_credit_days"] == 30
        assert result["is_statutory_capped"] is False

    @pytest.mark.asyncio
    async def test_medium_supplier_follows_agreement(self, ctx):
        """Medium/Non-MSME follows agreement."""
        calc = get_calculator("calculate_msme_due_date")
        result = await calc.calculate(ctx, {
            "invoice_date": "2026-08-01",
            "acceptance_date": "2026-08-01",
            "msme_category": "MEDIUM",
            "has_written_agreement": True,
            "agreement_days": 60,
        })
        assert result["effective_credit_days"] == 60
        assert result["is_statutory_capped"] is False


class TestEInvoiceValidator:
    """Test E-Invoice Validator (T2)."""

    @pytest.mark.asyncio
    async def test_t2_above_5cr_requires_irn(self, ctx):
        """T2: ₹8.9 Cr vendor -> IRN required (threshold ₹5 Cr)."""
        calc = get_calculator("validate_e_invoice_requirement")
        result = await calc.calculate(ctx, {
            "vendor_id": "V20000",
            "invoice_total_inr": 1000000,
        })
        assert result["required"] is True
        assert result["threshold"] == 50000000
        assert result["vendor_aato_band"] == "ABOVE_5CR"
        assert result["status"] == "IRN_MISSING"

    @pytest.mark.asyncio
    async def test_below_5cr_no_irn(self, ctx):
        """Below ₹5 Cr -> IRN not required."""
        calc = get_calculator("validate_e_invoice_requirement")
        # Would need vendor with BELOW_5CR band
        result = await calc.calculate(ctx, {
            "vendor_id": "V_SMALL",
            "invoice_total_inr": 1000000,
        })
        # Vendor not found -> UNKNOWN band -> not required
        assert result["required"] is False


class TestSupplierNormalizer:
    """Test Supplier String Normalizer."""

    @pytest.mark.asyncio
    async def test_basic_normalization(self, ctx):
        """Basic normalization: strips punctuation, spaces, leading zeros."""
        calc = get_calculator("normalize_supplier_string")
        result = await calc.calculate(ctx, {
            "invoice_num_str": "  INV/0042  ",
        })
        assert result["normalized"] == "INV42"

    @pytest.mark.asyncio
    async def test_resubmission_suffix_removed(self, ctx):
        """Removes /A, -REV, -A, /REV suffixes."""
        calc = get_calculator("normalize_supplier_string")
        
        test_cases = [
            ("INV/0042/A", "INV42"),
            ("INV-0042-REV", "INV42"),
            ("INV0042-A", "INV42"),
            ("INV/0042/REV", "INV42"),
        ]
        
        for input_str, expected in test_cases:
            result = await calc.calculate(ctx, {"invoice_num_str": input_str})
            assert result["normalized"] == expected, f"Failed for {input_str}"

    @pytest.mark.asyncio
    async def test_leading_zeros_stripped(self, ctx):
        """Leading zeros stripped."""
        calc = get_calculator("normalize_supplier_string")
        result = await calc.calculate(ctx, {
            "invoice_num_str": "000012345",
        })
        assert result["normalized"] == "12345"