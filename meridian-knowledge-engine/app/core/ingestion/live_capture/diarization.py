# app/core/ingestion/live_capture/diarization.py
"""Diarization - Speaker identification using pyannote.audio."""
import asyncio
import logging
import tempfile
import os
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class SpeakerSegment:
    """Speaker diarization segment."""
    speaker_id: str  # e.g., "SPEAKER_00"
    start_time: float
    end_time: float
    duration: float
    confidence: float = 1.0


@dataclass
class DiarizationResult:
    """Complete diarization result."""
    segments: List[SpeakerSegment]
    speakers: List[str]  # Unique speaker IDs
    total_duration: float
    num_speakers: int


class Diarizer:
    """
    Speaker diarization using pyannote.audio.
    
    Features:
    - Speaker segmentation
    - Speaker clustering
    - Real-time capable (with overlap handling)
    - Speaker embedding extraction
    - Integration with transcription
    """
    
    def __init__(
        self,
        model_name: str = "pyannote/speaker-diarization-3.1",
        device: str = "cpu",
        hf_token: Optional[str] = None,
        min_speakers: int = 1,
        max_speakers: int = 10,
    ):
        """
        Initialize diarizer.
        
        Args:
            model_name: pyannote model name
            device: cpu or cuda
            hf_token: HuggingFace token (required for pyannote models)
            min_speakers: Minimum number of speakers
            max_speakers: Maximum number of speakers
        """
        self.model_name = model_name
        self.device = device
        self.hf_token = hf_token
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers
        
        self._pipeline = None
        self._loaded = False
    
    def _load_pipeline(self) -> None:
        """Lazy load the pyannote pipeline."""
        if self._loaded:
            return
        
        try:
            from pyannote.audio import Pipeline
            import torch
            
            self._pipeline = Pipeline.from_pretrained(
                self.model_name,
                use_auth_token=self.hf_token,
            )
            
            if self.device == "cuda" and torch.cuda.is_available():
                self._pipeline.to(torch.device("cuda"))
            
            self._loaded = True
            logger.info(f"Loaded diarization pipeline: {self.model_name}")
            
        except ImportError:
            raise ImportError(
                "pyannote.audio not installed. Install with: pip install pyannote.audio"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load diarization pipeline: {e}")
    
    def diarize_file(
        self,
        audio_path: str,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None,
    ) -> 'DiarizationResult':
        """
        Diarize an audio file.
        
        Args:
            audio_path: Path to audio file
            min_speakers: Override minimum speakers
            max_speakers: Override maximum speakers
            
        Returns:
            DiarizationResult with speaker segments
        """
        self._load_pipeline()
        
        # Run diarization
        diarization = self._pipeline(
            audio_path,
            min_speakers=min_speakers or self.min_speakers,
            max_speakers=max_speakers or self.max_speakers,
        )
        
        # Parse results
        segments = []
        speakers = set()
        
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            segment = SpeakerSegment(
                speaker_id=speaker,
                start_time=turn.start,
                end_time=turn.end,
                duration=turn.end - turn.start,
            )
            segments.append(segment)
            speakers.add(speaker)
        
        return DiarizationResult(
            segments=segments,
            speakers=sorted(list(speakers)),
            total_duration=max(s.end_time for s in segments) if segments else 0,
            num_speakers=len(speakers),
        )
    
    def diarize_audio_data(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
    ) -> 'DiarizationResult':
        """Diarize raw audio data."""
        # Write to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            import wave
            with wave.open(tmp.name, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(audio_data)
        
        try:
            return self.diarize_file(tmp.name)
        finally:
            os.unlink(tmp.name)


def merge_transcript_with_diarization(
    transcript_segments: List[Dict[str, Any]],
    diarization: 'DiarizationResult',
) -> List[Dict[str, Any]]:
    """
    Merge transcript segments with speaker diarization.
    
    Args:
        transcript_segments: List of transcript segments with start/end/time
        diarization: DiarizationResult with speaker segments
        
    Returns:
        Transcript segments with speaker_id added
    """
    # Sort both by time
    transcript = sorted(transcript_segments, key=lambda x: x.get("start_time", 0))
    diar_segments = sorted(diarization.segments, key=lambda x: x.start_time)
    
    merged = []
    diar_idx = 0
    
    for t_seg in transcript:
        t_start = t_seg.get("start_time", 0)
        t_end = t_seg.get("end_time", t_start)
        
        # Find overlapping speaker segment
        speaker = "UNKNOWN"
        max_overlap = 0
        
        for d_seg in diar_segments:
            overlap_start = max(t_start, d_seg.start_time)
            overlap_end = min(t_end, d_seg.end_time)
            overlap = max(0, overlap_end - overlap_start)
            
            if overlap > max_overlap:
                max_overlap = overlap
                speaker = d_seg.speaker_id
        
        merged.append({
            **t_seg,
            "speaker_id": speaker,
            "speaker_confidence": max_overlap / (t_end - t_start) if t_end > t_start else 0,
        })
    
    return merged


# Real-time diarization handler
class StreamingDiarizer:
    """Handles real-time diarization for streaming audio."""

    def __init__(
        self,
        diarizer: Diarizer,
        chunk_duration: float = 10.0,
        overlap: float = 1.0,
    ):
        self.diarizer = diarizer
        self.chunk_duration = chunk_duration
        self.overlap = overlap
        self.buffer = bytearray()
        self.sample_rate = 16000
        self.bytes_per_second = 16000 * 2  # 16-bit
        self.chunk_bytes = int(chunk_duration * self.bytes_per_second)
        self.overlap_bytes = int(overlap * self.bytes_per_second)

        self.buffer = bytearray()
        self.processed_duration = 0.0

    async def add_audio(self, audio_chunk: bytes) -> List[DiarizationResult]:
        """Add audio chunk and return any new diarization results."""
        self.buffer.extend(audio_chunk)
        results = []

        while len(self.buffer) >= self.chunk_bytes:
            # Extract chunk
            chunk_data = bytes(self.buffer[:self.chunk_bytes])
            self.buffer = self.buffer[self.chunk_bytes - self.overlap_bytes:]

            # Process chunk
            try:
                result = self.diarizer.diarize_audio_data(chunk_data)
                results.append(result)
            except Exception as e:
                logger.error(f"Diarization error: {e}")

        return results

    def flush(self) -> List[DiarizationResult]:
        """Process remaining buffer."""
        results = []
        if self.buffer:
            try:
                result = self.diarizer.diarize_audio_data(bytes(self.buffer))
                results.append(result)
            except Exception as e:
                logger.error(f"Final diarization error: {e}")
        return results