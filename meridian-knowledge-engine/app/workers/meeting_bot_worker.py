# app/workers/meeting_bot_worker.py
"""Meeting Bot Worker - Processes meeting recordings for transcription and diarization."""
import asyncio
import logging
import signal
import os
from pathlib import Path
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import get_settings
from app.store.jobs import JobRepository
from app.store.episodes import EpisodeRepository
from app.models.job import Job
from app.models.episode import Episode
from app.models.block import Block
from app.core.ingestion.live_capture.transcriber import Transcriber
from app.core.ingestion.live_capture.diarization import Diarizer, merge_transcript_with_diarization
from app.core.ingestion.live_capture.pii_redactor import LivePIIRedactor

settings = get_settings()
logger = logging.getLogger(__name__)


class MeetingBotWorker:
    """
    Background worker that processes meeting recording jobs.
    
    Handles:
    - Audio transcription with faster-whisper
    - Speaker diarization with pyannote.audio
    - PII redaction
    - Transcript storage as blocks
    """
    
    def __init__(
        self,
        worker_id: str = "meeting-bot-1",
        poll_interval: float = 10.0,
        recordings_dir: str = "/app/recordings",
    ):
        self.worker_id = worker_id
        self.poll_interval = poll_interval
        self.recordings_dir = Path(recordings_dir)
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        
        # Database
        self.engine = None
        self.session_factory = None
        
        # Components
        self.transcriber = Transcriber(
            model_size=os.getenv("WHISPER_MODEL", "base"),
            device=os.getenv("WHISPER_DEVICE", "cuda"),
            compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "float16"),
        )
        self.diarizer = Diarizer(
            model_name=os.getenv("DIARIZATION_MODEL", "pyannote/speaker-diarization-3.1"),
            device=os.getenv("DIARIZATION_DEVICE", "cuda"),
            hf_token=os.getenv("HF_TOKEN"),
        )
        self.pii_redactor = LivePIIRedactor()
        
        # State
        self._running = False
        self._tasks: list[asyncio.Task] = []
        
    async def start(self) -> None:
        """Start the worker."""
        self.engine = create_async_engine(settings.DATABASE_URL, echo=False)
        self.session_factory = async_sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)
        
        self._running = True
        logger.info(f"Meeting Bot Worker {self.worker_id} started")
        
        # Start polling loop
        self._tasks.append(asyncio.create_task(self._poll_loop()))
        
        # Wait for tasks
        await asyncio.gather(*self._tasks, return_exceptions=True)
        
    async def stop(self) -> None:
        """Stop the worker gracefully."""
        logger.info(f"Meeting Bot Worker {self.worker_id} stopping...")
        self._running = False
        
        for task in self._tasks:
            task.cancel()
            
        await asyncio.gather(*self._tasks, return_exceptions=True)
        
        if self.engine:
            await self.engine.dispose()
            
        logger.info(f"Meeting Bot Worker {self.worker_id} stopped")
        
    async def _poll_loop(self) -> None:
        """Main polling loop - claims and processes meeting jobs."""
        while self._running:
            try:
                async with self.session_factory() as session:
                    job_repo = JobRepository(session)
                    job = await job_repo.claim_next_job(self.worker_id, ["meeting_ingest"])
                    
                    if job:
                        logger.info(f"Worker {self.worker_id} claimed meeting job {job.id}")
                        await self._process_meeting_job(session, job)
                    else:
                        await asyncio.sleep(self.poll_interval)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {self.worker_id} poll loop error: {e}")
                await asyncio.sleep(self.poll_interval)
                
    async def _process_meeting_job(self, session: AsyncSession, job: Job) -> None:
        """Process a meeting ingestion job."""
        job_repo = JobRepository(session)
        episode_repo = EpisodeRepository(session)
        
        try:
            episode_id = UUID(job.payload["episode_id"])
            recording_path = job.payload.get("recording_path")
            
            if not recording_path:
                raise ValueError("No recording path provided")
                
            episode = await episode_repo.get(episode_id)
            if not episode:
                raise ValueError(f"Episode {episode_id} not found")
                
            episode.status = "processing"
            await session.flush()
            
            logger.info(f"Processing meeting {episode_id}: {recording_path}")
            
            # Transcribe audio
            logger.info("Starting transcription...")
            transcript_segments = self.transcriber.transcribe_file(recording_path)
            logger.info(f"Transcription complete: {len(transcript_segments)} segments")
            
            # Diarize
            logger.info("Starting diarization...")
            diarization = self.diarizer.diarize_file(recording_path)
            logger.info(f"Diarization complete: {diarization.num_speakers} speakers")
            
            # Merge transcript with diarization
            transcript_dicts = [
                {
                    "segment_id": s.segment_id,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "text": s.text,
                }
                for s in transcript_segments
            ]
            merged = merge_transcript_with_diarization(transcript_dicts, diarization)
            
            # Convert to text with speaker labels
            full_text = "\n".join([f"[{m['speaker_id']}] {m['text']}" for m in merged])
            
            # Redact PII
            full_text = self.pii_redactor.redact_audio_transcript(full_text)
            
            # Save transcript as raw content
            episode.raw_content = full_text
            
            # Save transcript segments as blocks
            for i, segment in enumerate(merged):
                session.add(Block(
                    episode_id=episode.id,
                    tenant_id=episode.tenant_id,
                    block_type="transcript",
                    content=segment["text"],
                    metadata={
                        "speaker_id": segment.get("speaker_id"),
                        "speaker_confidence": segment.get("speaker_confidence", 0),
                        "start_time": segment.get("start_time"),
                        "end_time": segment.get("end_time"),
                        "confidence": segment.get("confidence", 0),
                    },
                    order=i,
                ))
            
            # Update episode
            episode.status = "completed"
            
            await session.flush()
            await job_repo.complete_job(job.id)
            
            logger.info(f"Meeting {episode_id} processing complete")
            
        except Exception as e:
            logger.error(f"Meeting job {job.id} failed: {e}")
            await job_repo.fail_job(job.id, str(e))
            raise


async def run_meeting_worker(
    worker_id: str = "meeting-bot-1",
    poll_interval: float = 10.0,
    recordings_dir: str = "/app/recordings",
) -> None:
    """Run the meeting bot worker."""
    worker = MeetingBotWorker(
        worker_id=worker_id,
        poll_interval=poll_interval,
        recordings_dir=recordings_dir,
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
            pass
            
    try:
        await worker.start()
    finally:
        await worker.stop()


if __name__ == "__main__":
    import os
    
    worker_id = os.getenv("WORKER_ID", "meeting-bot-1")
    poll_interval = float(os.getenv("POLL_INTERVAL", "10.0"))
    recordings_dir = os.getenv("RECORDINGS_DIR", "/app/recordings")
    
    asyncio.run(run_meeting_worker(worker_id, poll_interval, recordings_dir))