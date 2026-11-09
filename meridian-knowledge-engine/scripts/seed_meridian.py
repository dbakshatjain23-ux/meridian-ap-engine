# scripts/seed_meridian.py
"""Seed Meridian AP ontology into the database."""
import asyncio
import uuid
from datetime import date, datetime
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.config import get_settings
from app.models.tenant import Tenant
from app.models.entity import Entity
from app.models.fact import Fact, FactStatus
from app.core.ontology import MERIDIAN_ENTITIES, MERIDIAN_PREDICATES, AUTHORITY_RANKING

settings = get_settings()


async def seed_tenant(session, tenant_slug: str = "meridian") -> Tenant:
    """Create or get Meridian tenant."""
    stmt = select(Tenant).where(Tenant.slug == tenant_slug)
    result = await session.execute(stmt)
    tenant = result.scalar_one_or_none()

    if not tenant:
        tenant = Tenant(
            id=uuid.uuid4(),
            name="Meridian Shared Services",
            slug=tenant_slug,
            settings={},
        )
        session.add(tenant)
        await session.flush()
        print(f"Created tenant: {tenant.name} ({tenant.slug})")
    else:
        print(f"Tenant already exists: {tenant.name}")

    return tenant


async def seed_entities(session, tenant_id: uuid.UUID) -> dict:
    """Seed all Meridian AP entities."""
    entity_map = {}

    # Clients
    for key, data in MERIDIAN_ENTITIES["clients"].items():
        entity = Entity(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            entity_type="client",
            name=data["name"],
            canonical_name=data["canonical_name"],
            metadata=data["metadata"],
        )
        session.add(entity)
        await session.flush()
        entity_map[key] = entity.id
        print(f"Created client entity: {data['name']}")

    # Vendors
    for key, data in MERIDIAN_ENTITIES["vendors"].items():
        entity = Entity(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            entity_type="vendor",
            name=data["name"],
            canonical_name=data["canonical_name"],
            metadata=data["metadata"],
        )
        session.add(entity)
        await session.flush()
        entity_map[key] = entity.id
        print(f"Created vendor entity: {data['name']}")

    # Policies
    for key, data in MERIDIAN_ENTITIES["policies"].items():
        entity = Entity(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            entity_type="policy",
            name=key.replace("_", " ").title(),
            canonical_name=key,
            metadata=data["metadata"],
        )
        session.add(entity)
        await session.flush()
        entity_map[key] = entity.id
        print(f"Created policy entity: {key}")

    # Regulations
    for key, data in MERIDIAN_ENTITIES["regulations"].items():
        entity = Entity(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            entity_type="regulation",
            name=key.replace("_", " ").title(),
            canonical_name=key,
            metadata=data["metadata"],
        )
        session.add(entity)
        await session.flush()
        entity_map[key] = entity.id
        print(f"Created regulation entity: {key}")

    # Persons
    for key, data in MERIDIAN_ENTITIES["persons"].items():
        entity = Entity(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            entity_type="person",
            name=data["name"],
            canonical_name=key,
            metadata=data["metadata"],
        )
        session.add(entity)
        await session.flush()
        entity_map[key] = entity.id
        print(f"Created person entity: {data['name']}")

    return entity_map


async def seed_facts(session, tenant_id: uuid.UUID, entity_map: dict):
    """Seed initial facts for Meridian AP."""
    now = datetime.utcnow()

    # SOP v4.0 facts (current, authority=2)
    sop_v4_facts = [
        {
            "subject_entity_id": entity_map["price_tolerance"],
            "predicate": "price_tolerance",
            "object_value": {"pct": 0.01, "cap": 500},
            "object_type": "json",
            "valid_from": date(2026, 4, 1),
            "valid_to": None,
            "source_type": "sop_v4",
            "source_version": "v4.0",
            "source_status": "current",
            "authority_rank": AUTHORITY_RANKING["sop_v4"],
            "confidence": 1.0,
            "status": FactStatus.ACTIVE,
        },
        {
            "subject_entity_id": entity_map["tds_rate"],
            "predicate": "tds_rate",
            "object_value": {"194C": 0.02, "194J": 0.02, "194I": 0.10, "194Q": 0.001},
            "object_type": "json",
            "valid_from": date(2026, 4, 1),
            "valid_to": None,
            "source_type": "sop_v4",
            "source_version": "v4.0",
            "source_status": "current",
            "authority_rank": AUTHORITY_RANKING["sop_v4"],
            "confidence": 1.0,
            "status": FactStatus.ACTIVE,
        },
        {
            "subject_entity_id": entity_map["msme_cap"],
            "predicate": "msme_cap",
            "object_value": {"micro": 15, "small": 45},
            "object_type": "json",
            "valid_from": date(2026, 4, 1),
            "valid_to": None,
            "source_type": "sop_v4",
            "source_version": "v4.0",
            "source_status": "current",
            "authority_rank": AUTHORITY_RANKING["sop_v4"],
            "confidence": 1.0,
            "status": FactStatus.ACTIVE,
        },
        {
            "subject_entity_id": entity_map["e_invoice_threshold"],
            "predicate": "e_invoice_threshold",
            "object_value": 50000000,
            "object_type": "number",
            "valid_from": date(2026, 4, 1),
            "valid_to": None,
            "source_type": "sop_v4",
            "source_version": "v4.0",
            "source_status": "current",
            "authority_rank": AUTHORITY_RANKING["sop_v4"],
            "confidence": 1.0,
            "status": FactStatus.ACTIVE,
        },
        {
            "subject_entity_id": entity_map["approval_limit"],
            "predicate": "approval_limit",
            "object_value": {"controller": 1000000, "cfo": 5000000},
            "object_type": "json",
            "valid_from": date(2026, 4, 1),
            "valid_to": None,
            "source_type": "sop_v4",
            "source_version": "v4.0",
            "source_status": "current",
            "authority_rank": AUTHORITY_RANKING["sop_v4"],
            "confidence": 1.0,
            "status": FactStatus.ACTIVE,
        },
    ]

    # SOP v3.1 facts (superseded, authority=4)
    sop_v3_facts = [
        {
            "subject_entity_id": entity_map["price_tolerance"],
            "predicate": "price_tolerance",
            "object_value": {"pct": 0.02, "cap": 1000},
            "object_type": "json",
            "valid_from": date(2023, 7, 1),
            "valid_to": date(2026, 3, 31),
            "source_type": "sop_v3",
            "source_version": "v3.1",
            "source_status": "superseded",
            "authority_rank": AUTHORITY_RANKING["sop_v3"],
            "confidence": 1.0,
            "status": FactStatus.SUPERSEDED,
            "retracted_at": datetime(2026, 4, 1),
        },
    ]

    # FAQ 2023 facts (superseded, authority=4)
    faq_facts = [
        {
            "subject_entity_id": entity_map["price_tolerance"],
            "predicate": "price_tolerance",
            "object_value": {"pct": 0.02, "cap": 1000},
            "object_type": "json",
            "valid_from": date(2023, 10, 9),
            "valid_to": None,
            "source_type": "faq_2023",
            "source_version": "2023-10-09",
            "source_status": "superseded",
            "authority_rank": AUTHORITY_RANKING["faq_2023"],
            "confidence": 0.8,
            "status": FactStatus.SUPERSEDED,
            "retracted_at": datetime(2026, 4, 1),
        },
        {
            "subject_entity_id": entity_map["e_invoice_threshold"],
            "predicate": "e_invoice_threshold",
            "object_value": 100000000,  # 10 Cr (wrong)
            "object_type": "number",
            "valid_from": date(2023, 10, 9),
            "valid_to": None,
            "source_type": "faq_2023",
            "source_version": "2023-10-09",
            "source_status": "superseded",
            "authority_rank": AUTHORITY_RANKING["faq_2023"],
            "confidence": 0.8,
            "status": FactStatus.SUPERSEDED,
            "retracted_at": datetime(2026, 4, 1),
        },
    ]

    # Client Memos (authority=1)
    memo_facts = [
        {
            "subject_entity_id": entity_map["msme_cap"],
            "predicate": "msme_cap",
            "object_value": {"micro": 15, "small": 45},
            "object_type": "json",
            "valid_from": date(2026, 4, 1),
            "valid_to": None,
            "source_type": "client_memo",
            "source_version": "CM-INF-02",
            "source_status": "current",
            "authority_rank": AUTHORITY_RANKING["client_memo"],
            "confidence": 1.0,
            "status": FactStatus.ACTIVE,
        },
        {
            "subject_entity_id": entity_map["grn_status"],
            "predicate": "grn_status",
            "object_value": "QA_RELEASE_REQUIRED",
            "object_type": "string",
            "valid_from": date(2026, 1, 2),
            "valid_to": None,
            "source_type": "client_memo",
            "source_version": "CM-PHA-01",
            "source_status": "current",
            "authority_rank": AUTHORITY_RANKING["client_memo"],
            "confidence": 1.0,
            "status": FactStatus.ACTIVE,
        },
    ]

    # Desk Instructions (authority=2)
    di_facts = [
        {
            "subject_entity_id": entity_map["price_tolerance"],
            "predicate": "price_tolerance",
            "object_value": {"pct": 0.01, "cap": 500},
            "object_type": "json",
            "valid_from": date(2026, 4, 1),
            "valid_to": None,
            "source_type": "desk_instruction",
            "source_version": "DI-03",
            "source_status": "current",
            "authority_rank": AUTHORITY_RANKING["desk_instruction"],
            "confidence": 1.0,
            "status": FactStatus.ACTIVE,
        },
        {
            "subject_entity_id": entity_map["vendor_master"],
            "predicate": "bank_change_callback_required",
            "object_value": True,
            "object_type": "boolean",
            "valid_from": date(2026, 4, 1),
            "valid_to": None,
            "source_type": "desk_instruction",
            "source_version": "DI-07",
            "source_status": "current",
            "authority_rank": AUTHORITY_RANKING["desk_instruction"],
            "confidence": 1.0,
            "status": FactStatus.ACTIVE,
        },
    ]

    # Expert Interviews / Tacit (authority=3)
    tacit_facts = [
        {
            "subject_entity_id": entity_map["grn_status"],
            "predicate": "grn_status",
            "object_value": {
                "topic": "Infra GRN Batching",
                "habit_description": "Infra construction sites batch physical GRNs on Monday mornings.",
                "action_to_take": "Wait until Tuesday noon before chasing site engineer for NO_GRN hold.",
            },
            "object_type": "json",
            "valid_from": date(2026, 11, 1),
            "valid_to": None,
            "source_type": "expert_interview",
            "source_version": "Interview 1 [02:30] & [05:18]",
            "source_status": "approved",
            "authority_rank": AUTHORITY_RANKING["expert_interview"],
            "confidence": 0.9,
            "status": FactStatus.ACTIVE,
            "review_by_date": date(2027, 3, 31),
            "approved_by": entity_map["sandeep_rao"],
            "approved_at": datetime.utcnow(),
        },
    ]

    all_facts = sop_v4_facts + sop_v3_facts + faq_facts + memo_facts + di_facts + tacit_facts

    for fact_data in all_facts:
        fact = Fact(
            tenant_id=tenant_id,
            recorded_at=datetime.utcnow(),
            **fact_data,
        )
        session.add(fact)

    await session.commit()
    print(f"Seeded {len(all_facts)} facts")


async def main():
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        async with session.begin():
            tenant = await seed_tenant(session)
            entity_map = await seed_entities(session, tenant.id)
            await seed_facts(session, tenant.id, entity_map)

    await engine.dispose()
    print("Seeding complete!")


if __name__ == "__main__":
    asyncio.run(main())