# app/workers/main.py
"""Background Worker - Postgres SKIP LOCKED Job Processor."""
import asyncio
import signal
import sys
from typing import Dict, Type, List, Optional
from uuid import UUID
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, update, func, text
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.job import Job
from app.models.episode import Episode
from app.models.block import Block
from app.models.fact import Fact, FactStatus
from app.core.ingestion import DocumentParser, StructureRepair, EntityTopicExtractor, AuthorityRanker, ConflictDetector, GraphWriter
from app.store.facts import FactRepository
from app.store.entities import EntityRepository
from app.store.blocks import BlockRepository
from app.store.episodes import EpisodeRepository

settings = get_settings()


@dataclass
class WorkerStats:
    completed: int = 0
    failed: int = 0
    started_at: datetime = field(default_factory=datetime.utcnow)


class JobHandler:
    """Base class for job handlers."""
    job_type: str = ""

    async def handle(self, payload: dict, job_id: UUID, session: AsyncSession) -> dict:
        raise NotImplementedError


class IngestHandler(JobHandler):
    job_type = "ingest"

    async def handle(self, payload: dict, job_id: UUID, session: AsyncSession) -> dict:
        episode_id = UUID(payload["episode_id"])

        # Get episode
        episode_repo = EpisodeRepository(session)
        episode = await episode_repo.get(episode_id)
        if not episode:
            raise ValueError(f"Episode {episode_id} not found")

        # Mark processing
        await episode_repo.mark_processing(episode_id)

        try:
            # Parse document
            parser = DocumentParser()
            # Would read episode raw_content or file from storage
            # For now, use raw_content
            content = episode.raw_content.encode() if episode.raw_content else b""
            if not content:
                raise ValueError("No content to parse")

            blocks = parser.parse(content, episode.source_metadata.get("filename", ""))

            # Structure repair
            blocks = await StructureRepair.repair(blocks)

            # Save blocks
            block_repo = BlockRepository(session)
            saved_blocks = await block_repo.bulk_create([
                Block(
                    episode_id=episode_id,
                    tenant_id=episode.tenant_id,
                    block_type=b.block_type,
                    heading_path=b.heading_path,
                    heading_level=b.heading_level,
                    content=b.content,
                    metadata=b.metadata,
                    char_start=b.char_start,
                    char_end=b.char_end,
                )
                for b in blocks
            ])

            # Extract entities, predicates, facts
            extractor = EntityTopicExtractor()
            extraction = await extractor.run_full_extraction(
                blocks=saved_blocks,
                episode_id=episode_id,
                tenant_id=str(episode.tenant_id),
                document_context=episode.source_metadata,
                valid_from=episode.source_metadata.get("document_date", datetime.utcnow().date().isoformat()),
                valid_to=episode.source_metadata.get("valid_to"),
            )

            # Rank authority
            authority_ranker = AuthorityRanker()

            # Detect conflicts
            conflict_detector = ConflictDetector(authority_ranker)
            # Get existing facts for conflict detection
            fact_repo = FactRepository(session)
            existing_facts = []
            for fact_data in extraction.facts:
                existing = await fact_repo.get_active_facts_for_subject(
                    UUID(episode.tenant_id),
                    UUID(fact_data["subject_entity"]),
                    datetime.utcnow().date()
                )
                existing_facts.extend(existing)

            conflicts = conflict_detector.detect_conflicts(extraction.facts, existing_facts)

            # Write to graph
            graph_writer = GraphWriter(session)
            created_facts = await graph_writer.upsert_facts(
                tenant_id=episode.tenant_id,
                new_facts=extraction.facts,
            )

            # Create conflict records
            if conflicts:
                from app.models.conflict import Conflict
                for c in conflicts:
                    conflict = Conflict(
                        tenant_id=episode.tenant_id,
                        fact_id_1=c.fact_id_1,
                        fact_id_2=c.fact_id_2,  # Would be new fact ID
                        conflict_type=c.conflict_type.value,
                        severity=c.severity.value,
                        status="open",
                    )
                    session.add(conflict)

            await session.commit()

            # Mark completed
            await episode_repo.mark_completed(episode_id, len(saved_blocks), len(created_facts))

            return {
                "blocks_extracted": len(saved_blocks),
                "facts_created": len(created_facts),
                "conflicts_detected": len(conflicts),
            }

        except Exception as e:
            await episode_repo.mark_failed(episode_id, str(e))
            raise


class ConflictScanHandler(JobHandler):
    job_type = "conflict_scan"

    async def handle(self, payload: dict, job_id: UUID, session: AsyncSession) -> dict:
        # Scan for new conflicts across all facts
        # This would run daily
        return {"scanned": True, "conflicts_found": 0}


class SopSyncHandler(JobHandler):
    job_type = "sop_sync"

    async def handle(self, payload: dict, job_id: UUID, session: AsyncSession) -> dict:
        # Generate redline, push to SharePoint/Git
        return {"synced": True}


class JobProcessor:
    """Main job processor using Postgres SKIP LOCKED."""

    def __init__(self):
        self.engine = create_async_engine(settings.DATABASE_URL, pool_size=10, max_overflow=5)
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        self.handlers: Dict[str, JobHandler] = {}
        self.concurrency = settings.WORKER_CONCURRENCY
        self.semaphore = asyncio.Semaphore(self.concurrency)
        self.active_jobs: Dict[UUID, asyncio.Task] = {}
        self.stats = WorkerStats()
        self._running = False

    def register_handler(self, handler: JobHandler):
        self.handlers[handler.job_type] = handler

    async def claim_next_job(self, job_types: Optional[List[str]] = None) -> Optional[Job]:
        """Atomically claim next queued job using SELECT FOR UPDATE SKIP LOCKED."""
        async with self.session_factory() as session:
            stmt = text("""
                SELECT id, tenant_id, job_type, payload, status, attempts, max_attempts,
                       error_message, scheduled_for, started_at, completed_at, created_at
                FROM jobs
                WHERE status = 'queued'
                  AND scheduled_for <= NOW()
                  AND (:job_types IS NULL OR job_type = ANY(:job_types))
                ORDER BY scheduled_for
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            """)
            result = await session.execute(stmt, {"job_types": job_types})
            row = result.first()
            if not row:
                return None

            job_id = row.id
            # Update status to running
            await session.execute(
                update(Job)
                .where(Job.id == job_id)
                .values(status="running", started_at=func.now(), attempts=Job.attempts + 1)
            )
            await session.commit()

            # Reload job with session
            job = await session.get(Job, job_id)
            return job

    async def process_job(self, job: Job) -> None:
        """Process a single job."""
        async with self.semaphore:
            self.active_jobs[job.id] = asyncio.current_task()
            async with self.session_factory() as session:
                handler = self.handlers.get(job.job_type)
                if not handler:
                    await self._fail_job(session, job, f"No handler for job type: {job.job_type}")
                    return

                try:
                    result = await handler.handle(job.payload or {}, job.id, session)
                    await self._complete_job(session, job, result)
                    self.stats.completed += 1
                except Exception as e:
                    await self._fail_job(session, job, str(e))
                    self.stats.failed += 1
                finally:
                    self.active_jobs.pop(job.id, None)

    async def _complete_job(self, session: AsyncSession, job: Job, result: dict):
        await session.execute(
            update(Job)
            .where(Job.id == job.id)
            .values(status="completed", completed_at=func.now())
        )
        await session.commit()

    async def _fail_job(self, session: AsyncSession, job: Job, error: str):
        if job.attempts >= job.max_attempts:
            await session.execute(
                update(Job)
                .where(Job.id == job.id)
                .values(status="failed", error_message=error, completed_at=func.now())
            )
        else:
            await session.execute(
                update(Job)
                .where(Job.id == job.id)
                .values(status="retrying", error_message=error,
                        scheduled_for=func.now() + timedelta(seconds=30 * job.attempts))
            )
        await session.commit()

    async def get_queue_depth(self) -> int:
        async with self.session_factory() as session:
            stmt = select(func.count(Job.id)).where(Job.status.in_(["queued", "running", "retrying"]))
            return await session.scalar(stmt) or 0

    async def run(self, job_types: Optional[List[str]] = None):
        """Main worker loop."""
        self._running = True
        print(f"Worker started with concurrency={self.concurrency}")

        # Register default handlers
        self.register_handler(IngestHandler())
        self.register_handler(ConflictScanHandler())
        self.register_handler(SopSyncHandler())

        while self._running:
            try:
                job = await self.claim_next_job(job_types)
                if job:
                    asyncio.create_task(self.process_job(job))
                else:
                    await asyncio.sleep(settings.JOB_POLL_INTERVAL_MS / 1000)
            except Exception as e:
                print(f"Worker error: {e}")
                await asyncio.sleep(5)

    async def shutdown(self):
        print("Shutting down worker...")
        self._running = False
        # Wait for active jobs
        while self.active_jobs:
            await asyncio.sleep(0.5)
        await self.engine.dispose()
        print("Worker shutdown complete")


# Global worker instance
job_processor = JobProcessor()


async def main():
    """Entry point for worker process."""
    # Setup signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(job_processor.shutdown()))

    await job_processor.run()


if __name__ == "__main__":
    asyncio.run(main())