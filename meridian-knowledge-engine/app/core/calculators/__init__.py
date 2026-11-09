# app/core/calculators/__init__.py
"""AP Industry Plug-in - 6 Deterministic Calculators."""
from app.core.calculators.base import BaseCalculator, CalculatorContext, CALCULATORS
from app.core.calculators.price_variance import PriceVarianceCalculator
from app.core.calculators.tds_triage import TDSClassifier, TDSCalculator
from app.core.calculators.msme_due_date import MSMEDueDateCalculator
from app.core.calculators.e_invoice import EInvoiceValidator
from app.core.calculators.supplier_normalizer import SupplierNormalizer

__all__ = [
    "BaseCalculator",
    "CalculatorContext",
    "CALCULATORS",
    "PriceVarianceCalculator",
    "TDSClassifier",
    "TDSCalculator",
    "MSMEDueDateCalculator",
    "EInvoiceValidator",
    "SupplierNormalizer",
    "get_calculator",
]


def get_calculator(name: str) -> BaseCalculator:
    calc = CALCULATORS.get(name)
    if not calc:
        raise ValueError(f"Unknown calculator: {name}")
    return calc