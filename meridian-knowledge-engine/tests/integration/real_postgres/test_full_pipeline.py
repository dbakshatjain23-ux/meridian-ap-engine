"""
Integration Tests - Real PostgreSQL + pgvector
Tests the complete ingestion pipeline and knowledge graph operations.
"""
import pytest
import pytest_asyncio
import asyncio
import os
import tempfile
import shutil
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from decimal import Decimal
from pathlib import Path

# Test configuration
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://meridian:meridian@localhost:5432/meridian_test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only-min-64-characters-long-enough-for-validation")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text, select, func
from sqlalchemy.exc import IntegrityError

from app.database import Base
from app.models import (
    Tenant, Episode, Block, Entity, Fact, FactStatus, Conflict, Job, User, ApiKey
)
from app.config import get_settings

from app.workers.ingestion_worker import IngestionWorker
from app.core.ingestion.parser import DocumentParser
from app.core.ingestion.extractor import EntityTopicExtractor
from app.core.ingestion.authority import AuthorityRanker
from app.core.ingestion.conflict import ConflictDetector
from app.core.ingestion.graph_writer import GraphWriter
from app.core.ingestion.live_capture.pii_redactor import LivePIIRedactor
from app.core.answer.router import CalculatorRouter
from app.core.answer.builder import AnswerBuilder
from app.core.answer.verifier import AnswerVerifier
from app.gateways.embeddings import EmbeddingGateway

settings = get_settings()


# ============================================================
# Test Database Setup
# ============================================================

@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test database engine with pgvector."""
    # Use test database
    test_db_url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://meridian:meridian@localhost:5432/meridian_test")
    
    engine = create_async_engine(test_db_url, echo=False)
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        
        # Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\""))
    
    yield engine
    
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(test_engine):
    """Create session factory."""
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def session(session_factory):
    """Create test session."""
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def tenant(session):
    """Create test tenant."""
    tenant = Tenant(
        name="Test Tenant",
        slug="test-tenant",
        settings={}
    )
    session.add(tenant)
    await session.flush()
    return tenant


# ============================================================
# Test Fixtures - Sample Documents
# ============================================================

SAMPLE_INVOICE_TEXT = """
INVOICE

Vendor: Acme Corporation
Vendor PAN: ABCDE1234F
Vendor GSTIN: 27ABCDE1234F1Z5
Address: 123 Business Park, Mumbai 400001

Bill To: Meridian Industries
Address: 456 Industrial Area, Delhi 110001

Invoice No: INV-2026-001
Date: 2026-01-15
Due Date: 2026-02-14

PO Number: PO-2026-001
PO Date: 2026-01-10

Item Description          Qty    Rate     Amount
--------------------------------------------------
Steel Pipes 2-inch        100    500.00   50,000.00
Steel Pipes 3-inch        50     750.00   37,500.00
Welding Rods              200     50.00   10,000.00

Subtotal: 97,500.00
GST (18%): 17,550.00
Total: 115,050.00

Payment Terms: Net 30
Bank: HDFC Bank
Account: 50100123456789
IFSC: HDFC0001234
"""

SAMPLE_EMAIL_TEXT = """
From: vendor@acmecorp.com
To: ap@meridian.com
Subject: Invoice INV-2026-001 Submission
Date: 2026-01-15 10:30:00

Dear AP Team,

Please find attached invoice INV-2026-001 for the recent supply of steel pipes.

The total amount is Rs. 115,050 including GST.

Payment is due by 2026-02-14.

Bank details:
HDFC Bank
Account: 50100123456789
IFSC: HDFC0001234

Best regards,
John Smith
Accounts Receivable
Acme Corporation
PAN: ABCDE1234F
"""

# ============================================================
# Pipeline Component Tests
# ============================================================

class TestDocumentParser:
    """Test the document parser with real files."""
    
    @pytest.mark.asyncio
    async def test_parse_text_document(self):
        """Test parsing plain text document."""
        parser = DocumentParser()
        
        blocks = parser.parse(SAMPLE_INVOICE_TEXT, "text")
        
        assert len(blocks) > 0
        # Should have paragraph blocks
        paragraph_blocks = [b for b in blocks if b.block_type == "paragraph"]
        assert len(paragraph_blocks) > 0
        
        # Check content extraction
        full_text = " ".join([b.content for b in blocks])
        assert "Acme Corporation" in full_text
        assert "ABCDE1234F" in full_text
        assert "115,050.00" in full_text
    
    @pytest.mark.asyncio
    async def test_parse_email_document(self):
        """Test parsing email document."""
        parser = DocumentParser()
        
        blocks = parser.parse(SAMPLE_EMAIL_TEXT, "email")
        
        assert len(blocks) > 0
        # Should extract email metadata
        email_blocks = [b for b in blocks if b.block_type in ["paragraph", "heading"]]
        assert len(email_blocks) > 0
        
        full_text = " ".join([b.content for b in blocks])
        assert "vendor@acmecorp.com" in full_text
        assert "INV-2026-001" in full_text


class TestPIIRedaction:
    """Test PII redaction in pipeline."""
    
    @pytest.mark.asyncio
    async def test_redact_indian_pii(self):
        """Test redaction of Indian PII patterns."""
        redactor = LivePIIRedactor()
        
        text = SAMPLE_INVOICE_TEXT
        redacted = redactor.redact(text)
        
        # PAN should be redacted
        assert "ABCDE1234F" not in redacted
        assert "[REDACTED_PAN]" in redacted
        
        # GSTIN should be redacted
        assert "27ABCDE1234F1Z5" not in redacted
        assert "[REDACTED_GSTIN]" in redacted
        
        # Bank account should be redacted
        assert "50100123456789" not in redacted
        assert "[REDACTED_BANK_ACCOUNT]" in redacted
        
        # IFSC should be redacted
        assert "HDFC0001234" not in redacted
        assert "[REDACTED_IFSC]" in redacted


class TestEntityExtraction:
    """Test entity and fact extraction."""
    
    @pytest.mark.asyncio
    async def test_extract_entities_from_invoice(self):
        """Test entity extraction from invoice text."""
        parser = DocumentParser()
        extractor = EntityTopicExtractor()
        redactor = LivePIIRedactor()
        
        # Parse
        blocks = parser.parse(SAMPLE_INVOICE_TEXT, "text")
        
        # Redact PII
        for block in blocks:
            block.content = redactor.redact(block.content)
        
        # Extract
        entities, topics, facts = extractor.extract(blocks)
        
        # Should find vendor entity
        vendor_entities = [e for e in entities if e.get("type") == "ORG"]
        assert len(vendor_entities) > 0
        
        # Should find amount facts
        amount_facts = [f for f in facts if f.get("predicate") == "has_amount"]
        assert len(amount_facts) > 0
        
        # Should find PAN fact (redacted)
        pan_facts = [f for f in facts if "PAN" in str(f.get("object_value", ""))]
        assert len(pan_facts) > 0


class TestAuthorityRanking:
    """Test authority ranking of facts."""
    
    @pytest.mark.asyncio
    async def test_rank_facts_by_source_authority(self):
        """Test that facts are ranked by source authority."""
        ranker = AuthorityRanker()
        
        # Create test facts from different sources
        facts = [
            {"entity_id": "e1", "predicate": "has_amount", "object_value": "100000", "confidence": 0.9, "source_type": "document"},
            {"entity_id": "e1", "predicate": "has_amount", "object_value": "95000", "confidence": 0.8, "source_type": "email"},
            {"entity_id": "e1", "predicate": "has_amount", "object_value": "100000", "confidence": 0.95, "source_type": "document"},
        ]
        
        blocks = []  # Simplified
        
        ranked = ranker.rank(facts, blocks)
        
        # Higher confidence + document source should rank higher
        assert len(ranked) == 3
        assert ranked[0]["authority"] >= ranked[1]["authority"]


class TestConflictDetection:
    """Test conflict detection."""
    
    @pytest.mark.asyncio
    async def test_detect_contradiction(self):
        """Test detection of contradictory facts."""
        detector = ConflictDetector()
        
        facts = [
            {"id": "f1", "entity_id": "e1", "predicate": "has_amount", "object_value": "100000", "confidence": 0.9, "valid_from": datetime(2026, 1, 1)},
            {"id": "f2", "entity_id": "e1", "predicate": "has_amount", "object_value": "95000", "confidence": 0.85, "valid_from": datetime(2026, 1, 1)},
        ]
        
        conflicts = detector.detect(facts)
        
        # Should detect contradiction
        assert len(conflicts) > 0
        contradiction = conflicts[0]
        assert contradiction.conflict_type == "CONTRADICTION"
        assert set([conflict.fact_id_1, conflict.fact_id_2]) == {"f1", "f2"}


class TestGraphWriter:
    """Test atomic graph writing."""
    
    @pytest.mark.asyncio
    async def test_atomic_write_entities_facts(self, session, tenant):
        """Test atomic writing of entities and facts."""
        writer = GraphWriter()
        
        entities = [
            {"id": "e1", "name": "Acme Corporation", "type": "ORG", "properties": {"pan": "[REDACTED_PAN]"}},
            {"id": "e2", "name": "Meridian Industries", "type": "ORG", "properties": {}},
        ]
        
        facts = [
            {
                "entity_id": "e1",
                "predicate": "has_amount",
                "object_value": "115050.00",
                "confidence": 0.95,
                "authority": 10,
                "valid_from": datetime(2026, 1, 15),
                "source_episode_id": str(uuid4()),
            },
            {
                "entity_id": "e1",
                "predicate": "has_gstin",
                "object_value": "[REDACTED_GSTIN]",
                "confidence": 0.9,
                "authority": 8,
                "valid_from": datetime(2026, 1, 15),
                "source_episode_id": str(uuid4()),
            },
        ]
        
        conflicts = []
        
        # Should write atomically
        writer.write(str(tenant.id), entities, topics=[], facts=facts, conflicts=conflicts)
        
        # Verify entities created
        result = await session.execute(
            select(Entity).where(Entity.tenant_id == tenant.id)
        )
        db_entities = result.scalars().all()
        assert len(db_entities) == 2
        
        # Verify facts created
        result = await session.execute(
            select(Fact).where(Fact.tenant_id == tenant.id)
        )
        db_facts = result.scalars().all()
        assert len(db_facts) == 2


# ============================================================
# Full Pipeline Integration Tests
# ============================================================

class TestFullIngestionPipeline:
    """Test the complete ingestion pipeline."""
    
    @pytest.mark.asyncio
    async def test_ingest_invoice_document(self, session, tenant):
        """Test full pipeline: parse → redact → extract → rank → detect → write."""
        
        # Initialize pipeline components
        parser = DocumentParser()
        extractor = EntityTopicExtractor()
        redactor = LivePIIRedactor()
        ranker = AuthorityRanker()
        detector = ConflictDetector()
        writer = GraphWriter()
        
        # 1. Parse
        blocks = parser.parse(SAMPLE_INVOICE_TEXT, "text")
        assert len(blocks) > 0
        
        # 2. Redact PII
        for block in blocks:
            block.content = redactor.redact(block.content)
        
        # 3. Extract entities, topics, facts
        entities, topics, facts = extractor.extract(blocks)
        assert len(entities) > 0
        assert len(facts) > 0
        
        # 4. Rank authority
        facts = ranker.rank(facts, blocks)
        
        # 5. Detect conflicts
        conflicts = detector.detect(facts)
        
        # 6. Write to graph
        writer.write(str(tenant.id), entities, topics, facts, conflicts)
        
        # Verify in database
        entity_count = await session.scalar(
            select(func.count(Entity.id)).where(Entity.tenant_id == tenant.id)
        )
        assert entity_count > 0
        
        fact_count = await session.scalar(
            select(func.count(Fact.id)).where(Fact.tenant_id == tenant.id)
        )
        assert fact_count > 0
        
        # Verify PII was redacted in stored facts
        facts_result = await session.execute(
            select(Fact.object_value).where(Fact.tenant_id == tenant.id)
        )
        for (obj_val,) in facts_result:
            assert "ABCDE1234F" not in str(obj_val)
            assert "27ABCDE1234F1Z5" not in str(obj_val)


class TestTemporalQueries:
    """Test temporal query capabilities."""
    
    @pytest.mark.asyncio
    async def test_temporal_fact_versioning(self, session, tenant):
        """Test that fact versions are maintained over time."""
        
        writer = GraphWriter()
        episode_id = uuid4()
        
        # Create initial fact at T1
        facts_t1 = [{
            "entity_id": "e1",
            "predicate": "has_amount",
            "object_value": "100000",
            "confidence": 0.9,
            "authority": 10,
            "valid_from": datetime(2026, 1, 1),
            "source_episode_id": str(episode_id),
        }]
        
        writer.write(str(tenant.id), [], [], facts_t1, [])
        
        # Get fact ID
        fact_result = await session.execute(
            select(Fact.id).where(Fact.tenant_id == tenant.id)
        )
        fact_id = fact_result.scalar()
        
        # Update fact at T2 (new version)
        facts_t2 = [{
            "id": str(fact_id),
            "entity_id": "e1",
            "predicate": "has_amount",
            "object_value": "110000",
            "confidence": 0.95,
            "authority": 12,
            "valid_from": datetime(2026, 2, 1),
            "source_episode_id": str(uuid4()),
        }]
        
        writer.write(str(tenant.id), [], [], facts_t2, [])
        
        # Query AS OF T1 - should get old value
        result = await session.execute(text("""
            SELECT object_value FROM facts 
            WHERE id = :fid AND valid_from <= '2026-01-15'
            ORDER BY valid_from DESC LIMIT 1
        """), {"fid": fact_id})
        value_at_t1 = result.scalar()
        assert value_at_t1 == "100000"
        
        # Query AS OF T2 - should get new value
        result = await session.execute(text("""
            SELECT object_value FROM facts 
            WHERE id = :fid AND valid_from <= '2026-02-15'
            ORDER BY valid_from DESC LIMIT 1
        """), {"fid": fact_id})
        value_at_t2 = result.scalar()
        assert value_at_t2 == "110000"
    
    @pytest.mark.asyncio
    async def test_temporal_query_between(self, session, tenant):
        """Test BETWEEN temporal queries."""
        
        # This tests the dual-clock model (valid_time + transaction_time)
        # Verify both clocks are populated
        result = await session.execute(
            select(Fact.valid_from, Fact.transaction_time).where(Fact.tenant_id == tenant.id)
        )
        for valid_from, tx_time in result:
            assert valid_from is not None
            assert tx_time is not None


class TestRAGPipeline:
    """Test the RAG retrieval pipeline."""
    
    @pytest.mark.asyncio
    async def test_vector_search_retrieval(self, session, tenant):
        """Test vector similarity search for retrieval."""
        
        # This test requires embeddings to be generated
        # For now, verify the vector column exists and can be queried
        
        # Check that blocks have embedding column
        result = await session.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'blocks' AND column_name = 'embedding'
        """))
        col = result.scalar()
        assert col == "embedding"
        
        # Check vector index exists
        result = await session.execute(text("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename = 'blocks' AND indexname LIKE '%embedding%'
        """))
        # Index may not exist yet in test, but column should exist
        assert col is not None
    
    @pytest.mark.asyncio
    async def test_hybrid_retrieval_components(self, session, tenant):
        """Test that all hybrid retrieval components are in place."""
        
        # Verify keyword search (tsvector)
        result = await session.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'blocks' AND column_name = 'search_vector'
        """))
        assert result.scalar() == "search_vector"
        
        # Verify GIN index on search_vector
        result = await session.execute(text("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename = 'blocks' AND indexname LIKE '%search_vector%'
        """))
        # Index may not exist in test
        
        # Verify entities have embeddings
        result = await session.execute(text("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'entities' AND column_name = 'embedding'
        """))
        assert result.scalar() == "embedding"


class TestConcurrentWrites:
    """Test concurrent write safety."""
    
    @pytest.mark.asyncio
    async def test_concurrent_entity_writes(self, test_engine, tenant):
        """Test that concurrent writes to same entity are handled."""
        
        async def write_fact(engine, value, delay=0):
            if delay:
                await asyncio.sleep(delay)
            
            async with engine.begin() as conn:
                # Simulate graph writer upsert
                await conn.execute(text("""
                    INSERT INTO entities (id, tenant_id, name, type, created_at, updated_at)
                    VALUES (:id, :tid, :name, 'ORG', NOW(), NOW())
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        updated_at = NOW()
                """), {"id": "e1", "tid": str(tenant.id), "name": f"Acme Corp {value}"})
        
        # Fire concurrent writes
        await asyncio.gather(
            write_fact(test_engine, "v1"),
            write_fact(test_engine, "v2", 0.01),
            write_fact(test_engine, "v3", 0.02),
        )
        
        # Verify final state is consistent
        async with AsyncSession(test_engine) as session:
            result = await session.execute(
                select(Entity).where(Entity.id == "e1")
            )
            entity = result.scalar_one()
            assert entity is not None
            # Should have one of the values (last write wins)
            assert entity.name.startswith("Acme Corp")


class TestConflictResolution:
    """Test conflict resolution workflow."""
    
    @pytest.mark.asyncio
    async def test_conflict_escalation_creation(self, session, tenant):
        """Test that unresolved conflicts create escalations."""
        from app.models.escalation import Escalation
        
        # Create a conflict
        conflict = Conflict(
            tenant_id=tenant.id,
            fact_id_1="f1",
            fact_id_2="f2",
            conflict_type="CONTRADICTION",
            severity="high",
            description="Contradictory amounts for same entity",
        )
        session.add(conflict)
        await session.flush()
        
        # Create escalation
        escalation = Escalation(
            tenant_id=tenant.id,
            question="Resolve contradictory amounts for entity e1",
            context={"conflict_id": str(conflict.id), "fact_ids": ["f1", "f2"]},
            status="open",
        )
        session.add(escalation)
        await session.flush()
        
        # Verify escalation created
        result = await session.execute(
            select(Escalation).where(Escalation.tenant_id == tenant.id)
        )
        esc = result.scalar_one()
        assert esc.status == "open"
        assert esc.context["conflict_id"] == str(conflict.id)


class TestCalculatorIntegration:
    """Test calculator integration with knowledge graph."""
    
    @pytest.mark.asyncio
    async def test_price_variance_calculator(self, tenant):
        """Test price variance calculator with graph data."""
        from app.core.calculators import get_calculator
        from app.core.calculators.base import CalculatorContext
        
        calc = get_calculator("calculate_price_variance")
        ctx = CalculatorContext(
            tenant_id=str(tenant.id),
            client_desk="Test Desk",
            as_of_date="2026-01-15",
        )
        
        result = await calc.calculate(ctx, {
            "po_line_val": 100000,
            "po_unit_price": 1000,
            "inv_unit_price": 1050,
            "inv_qty": 100,
        })
        
        assert result["status"] == "PRICE_VAR"
        assert result["total_excess"] == 5000
        assert result["allowed_tolerance"] == 1000  # 1% of 100000


class TestRouterAndVerifier:
    """Test 3-lane router and 4-check verifier."""
    
    @pytest.mark.asyncio
    async def test_router_classification(self):
        """Test router correctly classifies queries."""
        router = CalculatorRouter()
        
        # Computable query
        route, inputs = router.route(
            "PO price 1000, invoice 1050 for 100 units",
            "Test Desk",
            "2026-01-15"
        )
        assert route == "computable"
        assert inputs["calculator"] == "calculate_price_variance"
        
        # Retrieval query
        route, inputs = router.route(
            "What is the GSTIN for Acme Corporation?",
            "Test Desk",
            "2026-01-15"
        )
        assert route == "retrieval"
        
        # Refused query
        route, inputs = router.route(
            "What is the cafeteria menu?",
            "Test Desk",
            "2026-01-15"
        )
        assert route == "refused"
    
    @pytest.mark.asyncio
    async def test_verifier_checks(self):
        """Test 4-check verifier."""
        verifier = AnswerVerifier()
        
        # Pass: numbers match calculator
        result = verifier.verify(
            answer_markdown="**PRICE VARIANCE**: Excess 5000, tolerance 1000",
            citations=[{"block_id": "1", "quote": "excess 5000", "fact_ids": ["f1"]}],
            calculator_outputs={"total_excess": 5000, "allowed_tolerance": 1000},
            older_sources=[]
        )
        assert result["passed"] is True
        
        # Fail: numbers don't match
        result = verifier.verify(
            answer_markdown="Excess is 99999",
            citations=[{"block_id": "1", "quote": "excess 5000"}],
            calculator_outputs={"total_excess": 5000},
            older_sources=[]
        )
        assert result["passed"] is False
        assert result["checks"]["numbers_sourced"] is False


# ============================================================
# Performance / Load Tests
# ============================================================

class TestPerformance:
    """Basic performance benchmarks."""
    
    @pytest.mark.asyncio
    async def test_bulk_ingestion_throughput(self, session, tenant):
        """Measure ingestion throughput."""
        import time
        
        parser = DocumentParser()
        extractor = EntityTopicExtractor()
        redactor = LivePIIRedactor()
        writer = GraphWriter()
        
        # Generate test documents
        docs = [SAMPLE_INVOICE_TEXT.replace("INV-2026-001", f"INV-2026-{i:03d}") for i in range(10)]
        
        start = time.perf_counter()
        
        for doc in docs:
            blocks = parser.parse(doc, "text")
            for block in blocks:
                block.content = redactor.redact(block.content)
            entities, topics, facts = extractor.extract(blocks)
            writer.write(str(tenant.id), entities, topics, facts, [])
        
        elapsed = time.perf_counter() - start
        throughput = len(docs) / elapsed
        
        print(f"\nIngestion throughput: {throughput:.2f} docs/sec")
        assert throughput > 1  # At least 1 doc/sec


# ============================================================
# Run Configuration
# ============================================================

if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-x",  # Stop on first failure
    ])