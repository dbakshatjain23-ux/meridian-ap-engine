# app/core/ontology/entities.py
"""Meridian AP Entity Definitions."""
from typing import Dict, Any

MERIDIAN_ENTITIES: Dict[str, Dict[str, Any]] = {
    "clients": {
        "arvana_infra": {
            "name": "Arvana Infra Projects",
            "canonical_name": "arvana_infra",
            "metadata": {"industry": "infra"},
        },
        "arvana_pharma": {
            "name": "Arvana Pharma",
            "canonical_name": "arvana_pharma",
            "metadata": {"industry": "pharma"},
        },
        "arvana_retail": {
            "name": "Arvana Retail",
            "canonical_name": "arvana_retail",
            "metadata": {"industry": "retail"},
        },
    },
    "vendors": {
        "v20000_balaji_logistics": {
            "name": "Balaji Logistics",
            "canonical_name": "v20000_balaji_logistics",
            "metadata": {
                "msme_category": "NONE",
                "aato_band": "ABOVE_5CR",
                "pan_available": True,
                "qrmp_filer": False,
                "habit_note": "Appends /A on resend",
            },
        },
        # ... 20 more vendors from data pack
    },
    "policies": {
        "price_tolerance": {"metadata": {"calculator": "calculate_price_variance"}},
        "tds_section": {"metadata": {"calculator": "classify_tds"}},
        "tds_rate": {"metadata": {"calculator": "calculate_tds"}},
        "msme_cap": {"metadata": {"calculator": "calculate_msme_due_date"}},
        "e_invoice_threshold": {"metadata": {"calculator": "validate_e_invoice_requirement"}},
        "approval_limit": {"metadata": {}},
    },
    "regulations": {
        "gst_act": {"metadata": {}},
        "income_tax_act": {"metadata": {}},
        "msmed_act": {"metadata": {}},
    },
    "persons": {
        "lakshmi_reddy": {"metadata": {"role": "senior_processor", "tenure": "11_years"}},
        "imran_qureshi": {"metadata": {"role": "tax_desk_lead"}},
        "sandeep_rao": {"metadata": {"role": "process_owner"}},
    },
}