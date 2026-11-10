# app/core/ingestion/live_capture/transcriber.py
"""Transcriber - Real-time speech-to-text using faster-whisper."""
import asyncio
import logging
import tempfile
import os
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TranscriptSegment:
    """Single transcript segment with timing."""
    segment_id: str
    start_time: float  # seconds
    end_time: float
    text: str
    confidence: float
    language: Optional[str] = None


class Transcriber:
    """
    Real-time speech-to-text using faster-whisper.
    
    Features:
    - Streaming transcription
    - Multiple language support
    - Word-level timestamps
    - Confidence scores
    - Voice activity detection
    """
    
    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        language: Optional[str] = None,
        beam_size: int = 5,
        vad_filter: bool = True,
        vad_parameters: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize transcriber.
        
        Args:
            model_size: tiny, base, small, medium, large-v2, large-v3
            device: cpu, cuda, auto
            compute_type: int8, int8_float16, float16, float32
            language: ISO language code (None for auto-detect)
            beam_size: Beam size for decoding
            vad_filter: Use voice activity detection
            vad_parameters: VAD parameters dict
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.beam_size = beam_size
        self.vad_filter = vad_filter
        self.vad_parameters = vad_parameters or {
            "threshold": 0.5,
            "min_speech_duration_ms": 250,
            "max_speech_duration_s": 30,
            "min_silence_duration_ms": 100,
        }
        
        self._model = None
        self._model_loaded = False
    
    def _load_model(self) -> None:
        """Lazy load the faster-whisper model."""
        if self._model_loaded:
            return
        
        try:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            self._model_loaded = True
            logger.info(f"Loaded faster-whisper model: {self.model_size} on {self.device}")
        except ImportError:
            raise ImportError(
                "faster-whisper not installed. Install with: pip install faster-whisper"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load whisper model: {e}")
    
    def transcribe_file(
        self,
        audio_path: str,
        language: Optional[str] = None,
        task: str = "transcribe",
    ) -> List[TranscriptSegment]:
        """
        Transcribe an audio file.
        
        Args:
            audio_path: Path to audio file
            language: Language code (None for auto-detect)
            task: "transcribe" or "translate"
            
        Returns:
            List of transcript segments
        """
        self._load_model()
        
        segments, info = self._model.transcribe(
            audio_path,
            language=language or self.language,
            task=task,
            beam_size=self.beam_size,
            vad_filter=self.vad_filter,
            vad_parameters=self.vad_parameters,
            word_timestamps=True,
        )
        
        segments_list = []
        for segment in segments:
            segments_list.append(TranscriptSegment(
                segment_id=f"seg_{segment.start:.2f}",
                start_time=segment.start,
                end_time=segment.end,
                text=segment.text.strip(),
                confidence=segment.avg_logprob if hasattr(segment, 'avg_logprob') else 0.0,
                language=info.language if hasattr(info, 'language') else None,
            ))
        
        return segments_list
    
    async def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language: Optional[str] = None,
        chunk_duration: float = 30.0,
    ) -> AsyncGenerator[TranscriptSegment, None]:
        """
        Transcribe audio stream in real-time.
        
        Args:
            audio_stream: Async generator yielding audio chunks (bytes)
            language: Language code
            chunk_duration: Duration of each chunk in seconds
            
        Yields:
            Transcript segments as they're generated
        """
        self._load_model()
        
        # Buffer for accumulating audio
        audio_buffer = bytearray()
        sample_rate = 16000  # Whisper expects 16kHz
        bytes_per_second = sample_rate * 2  # 16-bit = 2 bytes
        chunk_bytes = int(chunk_duration * bytes_per_second)
        
        async for chunk in audio_stream:
            audio_buffer.extend(chunk)
            
            # Process when we have enough audio
            while len(audio_buffer) >= chunk_bytes:
                chunk_data = bytes(audio_buffer[:chunk_bytes])
                audio_buffer = audio_buffer[chunk_bytes:]
                
                # Write to temp file
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    # Write WAV header
                    import wave
                    with wave.open(tmp.name, 'wb') as wav:
                        wav.setnchannels(1)
                        wav.setsampwidth(2)
                        wav.setframerate(16000)
                        wav.writeframes(chunk_data)
                    
                    # Transcribe chunk
                    segments = self.transcribe_file(tmp.name)
                    
                    # Clean up
                    os.unlink(tmp.name)
                    
                    for segment in segments:
                        yield segment
    
    def transcribe_audio_data(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        language: Optional[str] = None,
    ) -> List[TranscriptSegment]:
        """
        Transcribe raw audio data.
        
        Args:
            audio_data: Raw PCM audio bytes (16-bit, mono)
            sample_rate: Sample rate in Hz
            language: Language code
            
        Returns:
            List of transcript segments
        """
        self._load_model()
        
        # Write to temp WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            import wave
            with wave.open(tmp.name, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)  # 16-bit
                wav.setframerate(sample_rate)
                wav.writeframes(audio_data)
            
            try:
                return self.transcribe_file(tmp.name)
            finally:
                os.unlink(tmp.name)
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes."""
        return [
            "en", "zh", "de", "es", "ru", "ko", "fr", "ja", "pt", "tr",
            "pl", "ca", "nl", "ar", "sv", "it", "id", "hi", "fi", "vi",
            "he", "uk", "el", "ms", "cs", "ro", "da", "hu", "ta", "no",
            "th", "ur", "hr", "bg", "lt", "la", "mi", "ml", "cy", "sk",
            "te", "fa", "lv", "bn", "sr", "az", "sl", "kn", "et", "mk",
            "br", "eu", "is", "hy", "ne", "mn", "bs", "kk", "sq", "sw",
            "gl", "mr", "pa", "si", "km", "sn", "yo", "so", "af", "oc",
            "ka", "be", "tg", "sd", "gu", "am", "mg", "lo", "ne", "ka",
        ]


# Streaming audio handler
class AudioStreamHandler:
    """Handles real-time audio stream processing."""
    
    def __init__(
        self,
        transcriber: Transcriber,
        chunk_duration: float = 5.0,
        overlap: float = 0.5,
    ):
        self.transcriber = transcriber
        self.chunk_duration = chunk_duration
        self.overlap = overlap
        self.buffer = bytearray()
        self.sample_rate = 16000
    
    async def process_chunk(self, audio_chunk: bytes) -> List[str]:
        """Process an audio chunk and return transcriptions."""
        # Add to buffer
        # When buffer reaches chunk_duration, transcribe
        # Return any new transcriptions
        pass
    
    async def flush(self) -> List[str]:
        """Flush remaining buffer."""
        pass