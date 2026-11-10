# app/workers/ingestion_worker.py
"""Background Worker - Processes ingestion jobs from the queue."""
import asyncio
import logging
import signal
import sys
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import get_settings
from app.store.jobs import JobRepository
from app.store.episodes import EpisodeRepository
from app.store.facts import FactRepository
from app.models.job import Job
from app.models.episode import Episode
from app.models.block import Block
from app.models.fact import Fact, FactStatus
from app.core.ingestion.live_capture import LivePIIRedactor
from app.core.ingestion.live_capture.transcriber import Transcriber
from app.core.ingestion.live_capture.diarization import Diarizer, merge_transcript_with_diarization

settings = get_settings()
logger = logging.getLogger(__name__)

# Lazy imports for heavy components
_parser = None
_structure_repair = None
_extractor = None
_authority_ranker = None
_conflict_detector = None
_graph_writer = None

def _get_parser():
    global _parser
    if _parser is None:
        from app.core.ingestion.parser import DocumentParser
        _parser = DocumentParser()
    return _parser

def _get_structure_repair():
    global _structure_repair
    if _structure_repair is None:
        from app.core.ingestion.structure_repair import StructureRepair
        _structure_repair = StructureRepair()
    return _structure_repair

def _get_extractor():
    global _extractor
    if _extractor is None:
        from app.core.ingestion.extractor import EntityTopicExtractor
        _extractor = EntityTopicExtractor()
    return _extractor

def _get_authority_ranker():
    global _authority_ranker
    if _authority_ranker is None:
        from app.core.ingestion.authority import AuthorityRanker
        _authority_ranker = AuthorityRanker()
    return _authority_ranker

def _get_conflict_detector():
    global _conflict_detector
    if _conflict_detector is None:
        from app.core.ingestion.conflict import ConflictDetector
        _conflict_detector = ConflictDetector()
    return _conflict_detector

def _get_graph_writer():
    global _graph_writer
    if _graph_writer is None:
        from app.core.ingestion.graph_writer import GraphWriter
        _graph_writer = GraphWriter()
    return _graph_writer


class IngestionWorker:
    """
    Background worker that processes ingestion jobs from the queue.
    
    Handles:
    - Document ingestion (PDF, Word, Excel, PPTX, Text, Email)
    - Email webhook processing
    - Teams message processing
    - Meeting transcript processing
    """
    
    def __init__(
        self,
        worker_id: str,
        job_types: Optional[list[str]] = None,
        poll_interval: float = 5.0,
    ):
        self.worker_id = worker_id
        self.job_types = job_types or ["ingest", "email_ingest", "teams_ingest", "meeting_ingest"]
        self.poll_interval = poll_interval
        
        # Database
        self.engine = None
        self.session_factory = None
        
        # Components (lazy loaded)
        self._parser = None
        self._structure_repair = None
        self._extractor = None
        self._authority_ranker = None
        self._conflict_detector = None
        self._graph_writer = None
        self.pii_redactor = LivePIIRedactor()
        self.transcriber = Transcriber()
        self.diarizer = Diarizer()
        
        # State
        self._running = False
        self._tasks: list[asyncio.Task] = []
        
    @property
    def parser(self):
        if self._parser is None:
            self._parser = _get_parser()
        return self._parser
        
    @property
    def structure_repair(self):
        if self._structure_repair is None:
            self._structure_repair = _get_structure_repair()
        return self._structure_repair
        
    @property
    def extractor(self):
        if self._extractor is None:
            self._extractor = _get_extractor()
        return self._extractor
        
    @property
    def authority_ranker(self):
        if self._authority_ranker is None:
            self._authority_ranker = _get_authority_ranker()
        return self._authority_ranker
        
    @property
    def conflict_detector(self):
        if self._conflict_detector is None:
            self._conflict_detector = _get_conflict_detector()
        return self._conflict_detector
        
    @property
    def graph_writer(self):
        if self._graph_writer is None:
            self._graph_writer = _get_graph_writer()
        return self._graph_writer
        
    async def start(self) -> None:
        """Start the worker."""
        self.engine = create_async_engine(settings.DATABASE_URL, echo=False)
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        
        self._running = True
        logger.info(f"Worker {self.worker_id} started, polling for job types: {self.job_types}")
        
        # Start polling loop
        self._tasks.append(asyncio.create_task(self._poll_loop()))
        
        # Wait for tasks
        await asyncio.gather(*self._tasks, return_exceptions=True)
        
    async def stop(self) -> None:
        """Stop the worker gracefully."""
        logger.info(f"Worker {self.worker_id} stopping...")
        self._running = False
        
        for task in self._tasks:
            task.cancel()
            
        await asyncio.gather(*self._tasks, return_exceptions=True)
        
        if self.engine:
            await self.engine.dispose()
            
        logger.info(f"Worker {self.worker_id} stopped")
        
    async def _poll_loop(self) -> None:
        """Main polling loop - claims and processes jobs."""
        while self._running:
            try:
                async with self.session_factory() as session:
                    job_repo = JobRepository(session)
                    job = await job_repo.claim_next_job(self.worker_id, self.job_types)
                    
                    if job:
                        logger.info(f"Worker {self.worker_id} claimed job {job.id} ({job.job_type})")
                        await self._process_job(session, job)
                    else:
                        # No jobs available, wait before polling again
                        await asyncio.sleep(self.poll_interval)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {self.worker_id} poll loop error: {e}")
                await asyncio.sleep(self.poll_interval)
                
    async def _process_job(self, session: AsyncSession, job: Job) -> None:
        """Process a single job."""
        job_repo = JobRepository(session)
        
        try:
            if job.job_type == "ingest":
                await self._process_document_ingestion(session, job)
            elif job.job_type == "email_ingest":
                await self._process_email_ingestion(session, job)
            elif job.job_type == "teams_ingest":
                await self._process_teams_ingestion(session, job)
            elif job.job_type == "meeting_ingest":
                await self._process_meeting_ingestion(session, job)
            else:
                raise ValueError(f"Unknown job type: {job.job_type}")
                
            await job_repo.complete_job(job.id)
            logger.info(f"Job {job.id} completed successfully")
            
        except Exception as e:
            logger.error(f"Job {job.id} failed: {e}")
            await job_repo.fail_job(job.id, str(e))
            
    async def _process_document_ingestion(self, session: AsyncSession, job: Job) -> None:
        """Process a document ingestion job."""
        episode_id = UUID(job.payload["episode_id"])
        
        episode_repo = EpisodeRepository(session)
        episode = await episode_repo.get(episode_id)
        
        if not episode:
            raise ValueError(f"Episode {episode_id} not found")
            
        # Update episode status
        episode.status = "processing"
        await session.flush()
        
        # Get raw content
        raw_content = episode.raw_content
        if not raw_content and episode.source_type != "email":
            # For non-text files, we'd need to read from storage
            # For now, assume text content is available
            pass
            
        if raw_content:
            # Redact PII
            raw_content = self.pii_redactor.redact(raw_content)
            
        # Parse document
        blocks = self.parser.parse(raw_content or "", episode.source_type)
        
        # Structure repair
        blocks = self.structure_repair.repair(blocks)
        
        # Extract entities, topics, facts
        entities, topics, facts = self.extractor.extract(blocks)
        
        # Rank authority
        facts = self.authority_ranker.rank(facts, blocks)
        
        # Detect conflicts
        conflicts = self.conflict_detector.detect(facts)
        
        # Write to graph
        self.graph_writer.write(episode.tenant_id, entities, topics, facts, conflicts)
        
        # Save blocks
        for block in blocks:
            session.add(Block(
                episode_id=episode.id,
                tenant_id=episode.tenant_id,
                block_type=block.block_type.value if hasattr(block.block_type, 'value') else block.block_type,
                content=block.content,
                metadata=block.metadata or {},
                page=block.page,
                order=block.order,
            ))
            
        # Save facts
        for fact in facts:
            session.add(Fact(
                tenant_id=episode.tenant_id,
                source_episode_id=episode.id,
                entity_id=fact.get("entity_id"),
                predicate=fact.get("predicate"),
                object_value=fact.get("object_value"),
                confidence=fact.get("confidence", 0.0),
                authority=fact.get("authority", 0),
                status=FactStatus.PROPOSED,
            ))
            
        # Update episode
        episode.status = "completed"
        episode.processed_at = asyncio.get_event_loop().time()
        
        await session.flush()
        
    async def _process_email_ingestion(self, session: AsyncSession, job: Job) -> None:
        """Process an email ingestion job."""
        # Similar to document ingestion but with email-specific handling
        await self._process_document_ingestion(session, job)
        
    async def _process_teams_ingestion(self, session: AsyncSession, job: Job) -> None:
        """Process a Teams message ingestion job."""
        await self._process_document_ingestion(session, job)
        
    async def _process_meeting_ingestion(self, session: AsyncSession, job: Job) -> None:
        """Process a meeting transcript ingestion job."""
        episode_id = UUID(job.payload["episode_id"])
        recording_path = job.payload.get("recording_path")
        
        if not recording_path:
            raise ValueError("No recording path provided for meeting ingestion")
            
        episode_repo = EpisodeRepository(session)
        episode = await episode_repo.get(episode_id)
        
        if not episode:
            raise ValueError(f"Episode {episode_id} not found")
            
        episode.status = "processing"
        await session.flush()
        
        # Transcribe audio
        transcript_segments = self.transcriber.transcribe_file(recording_path)
        
        # Diarize
        diarization = self.diarizer.diarize_file(recording_path)
        
        # Merge transcript with diarization
        merged = merge_transcript_with_diarization(
            [{"segment_id": s.segment_id, "start_time": s.start_time, "end_time": s.end_time, "text": s.text} for s in transcript_segments],
            diarization
        )
        
        # Convert to text
        full_text = "\n".join([f"[{m['speaker_id']}] {m['text']}" for m in merged])
        
        # Redact PII
        full_text = self.pii_redactor.redact_audio_transcript(full_text)
        
        # Save transcript as raw content
        episode.raw_content = full_text
        
        # Process as document
        await self._process_document_ingestion(session, job)
        
        # Save transcript segments as blocks
        for segment in merged:
            session.add(Block(
                episode_id=episode.id,
                tenant_id=episode.tenant_id,
                block_type="transcript",
                content=segment["text"],
                metadata={
                    "speaker_id": segment.get("speaker_id"),
                    "start_time": segment.get("start_time"),
                    "end_time": segment.get("end_time"),
                    "confidence": segment.get("confidence"),
                },
                order=0,
            ))


async def run_worker(
    worker_id: str = "worker-1",
    job_types: Optional[list[str]] = None,
    poll_interval: float = 5.0,
) -> None:
    """Run the ingestion worker."""
    worker = IngestionWorker(
        worker_id=worker_id,
        job_types=job_types,
        poll_interval=poll_interval,
    )
    
    # Handle shutdown signals
    loop = asyncio.get_running_loop()
    
    def signal_handler():
        logger.info("Shutdown signal received")
        asyncio.create_task(worker.stop())
        
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass
            
    try:
        await worker.start()
    finally:
        await worker.stop()


if __name__ == "__main__":
    import os
    
    worker_id = os.getenv("WORKER_ID", "worker-1")
    job_types = os.getenv("JOB_TYPES", "ingest,email_ingest,teams_ingest,meeting_ingest").split(",")
    poll_interval = float(os.getenv("POLL_INTERVAL", "5.0"))
    
    asyncio.run(run_worker(worker_id, job_types, poll_interval))