# scripts/load_meridian_corpus.py
"""Load Meridian AP corpus (4 Word docs) into the ingestion pipeline."""
import asyncio
import hashlib
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.config import get_settings
from app.models.tenant import Tenant
from app.models.episode import Episode
from app.models.job import Job
from app.core.ingestion import DocumentParser

settings = get_settings()

CORPUS_PATH = Path(__file__).parent.parent / "docs" / "Data"

CORPUS_FILES = [
    {
        "filename": "PS-07_AP_SOP_v4.0_2026.docx",
        "source_type": "document",
        "metadata": {
            "document_type": "sop",
            "version": "v4.0",
            "document_date": "2026-04-01",
            "status": "current",
            "client_desk": "ALL",
        },
    },
    {
        "filename": "PS-07_AP_SOP_v3.1_2023.docx",
        "source_type": "document",
        "metadata": {
            "document_type": "sop",
            "version": "v3.1",
            "document_date": "2023-07-01",
            "status": "superseded",
            "client_desk": "ALL",
        },
    },
    {
        "filename": "PS-07_training_and_expert_transcripts.docx",
        "source_type": "document",
        "metadata": {
            "document_type": "transcript",
            "version": "1.0",
            "document_date": "2026-01-01",
            "status": "current",
            "client_desk": "ALL",
        },
    },
    {
        "filename": "PS-07_desk_instructions_and_client_memos.docx",
        "source_type": "document",
        "metadata": {
            "document_type": "desk_instruction",
            "version": "1.0",
            "document_date": "2026-04-01",
            "status": "current",
            "client_desk": "ALL",
        },
    },
]


async def load_corpus():
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        # Get tenant
        stmt = select(Tenant).where(Tenant.slug == "meridian")
        result = await session.execute(stmt)
        tenant = result.scalar_one_or_none()

        if not tenant:
            print("Tenant 'meridian' not found. Run seed_meridian.py first.")
            return

        parser = DocumentParser()

        for file_info in CORPUS_FILES:
            filepath = CORPUS_PATH / file_info["filename"]
            if not filepath.exists():
                print(f"File not found: {filepath}")
                continue

            print(f"Loading: {file_info['filename']}")

            # Read file
            content = filepath.read_bytes()
            content_hash = hashlib.sha256(content).hexdigest()

            # Check if already ingested
            from app.models.episode import Episode
            stmt = select(Episode).where(
                Episode.tenant_id == tenant.id,
                Episode.content_hash == content_hash,
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                print(f"  Already ingested (episode: {existing.id})")
                continue

            # Create episode
            episode = Episode(
                id=uuid4(),
                tenant_id=tenant.id,
                source_type=file_info["source_type"],
                source_id=file_info["filename"],
                source_metadata=file_info["metadata"],
                raw_content=content.decode("utf-8", errors="ignore") if file_info["source_type"] != "pdf" else None,
                content_hash=content_hash,
                status="pending",
            )
            session.add(episode)
            await session.flush()

            # Queue ingestion job
            job = Job(
                tenant_id=tenant.id,
                job_type="ingest",
                payload={"episode_id": str(episode.id)},
                status="queued",
            )
            session.add(job)

            print(f"  Created episode {episode.id} and ingestion job")

        await session.commit()
        print("Corpus loading complete!")


async def main():
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        await load_corpus()

    await engine.dispose()
    print("Corpus loading complete!")


if __name__ == "__main__":
    asyncio.run(main())