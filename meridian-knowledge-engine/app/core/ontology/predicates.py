# app/core/ontology/predicates.py
"""Meridian AP Predicate Definitions."""
from typing import Dict, Any

MERIDIAN_PREDICATES: Dict[str, Dict[str, Any]] = {
    "price_tolerance": {
        "subject_type": "policy",
        "object_type": "json",
        "calculator": "calculate_price_variance",
        "example_value": {"pct": 0.01, "cap": 500},
    },
    "tds_section": {
        "subject_type": "policy",
        "object_type": "string",
        "calculator": "classify_tds",
        "example_value": "194J",
    },
    "tds_rate": {
        "subject_type": "policy",
        "object_type": "json",
        "calculator": "calculate_tds",
        "example_value": {"194C": 0.02, "194J": 0.02, "194I": 0.10, "194Q": 0.001},
    },
    "msme_cap": {
        "subject_type": "policy",
        "object_type": "json",
        "calculator": "calculate_msme_due_date",
        "example_value": {"micro": 15, "small": 45},
    },
    "e_invoice_threshold": {
        "subject_type": "policy",
        "object_type": "number",
        "calculator": "validate_e_invoice_requirement",
        "example_value": 50000000,
    },
    "approval_limit": {
        "subject_type": "policy",
        "object_type": "json",
        "example_value": {"controller": 1000000, "cfo": 5000000},
    },
    "msme_category": {
        "subject_type": "vendor",
        "object_type": "string",
        "example_value": "MICRO",
    },
    "aato_band": {
        "subject_type": "vendor",
        "object_type": "string",
        "example_value": "ABOVE_5CR",
    },
    "pan_available": {
        "subject_type": "vendor",
        "object_type": "boolean",
        "example_value": True,
    },
    "qrmp_filer": {
        "subject_type": "vendor",
        "object_type": "boolean",
        "example_value": False,
    },
    "habit_note": {
        "subject_type": "vendor",
        "object_type": "string",
        "example_value": "Appends /A on resend",
    },
    "grn_status": {
        "subject_type": "invoice",
        "object_type": "string",
        "example_value": "PENDING",
    },
}