# app/core/ontology/__init__.py
"""Meridian AP Ontology - Entities, Predicates, Authority Configuration."""
from app.core.ontology.entities import MERIDIAN_ENTITIES
from app.core.ontology.predicates import MERIDIAN_PREDICATES
from app.core.ontology.authority import AUTHORITY_RANKING

__all__ = [
    "MERIDIAN_ENTITIES",
    "MERIDIAN_PREDICATES",
    "AUTHORITY_RANKING",
]