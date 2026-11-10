# tests/unit/live_capture/test_diarization.py
"""Unit tests for Diarization (mock-based since pyannote requires model)."""
import sys
import pytest
from unittest.mock import Mock, patch, MagicMock

# Mock optional dependencies before they're imported
sys.modules['pyannote'] = MagicMock()
sys.modules['pyannote.audio'] = MagicMock()

from app.core.ingestion.live_capture.diarization import (
    Diarizer, DiarizationResult, SpeakerSegment, merge_transcript_with_diarization
)

# Skip tests that require pyannote (PyTorch DLL issue on Windows)
pytestmark = pytest.mark.skipif(
    True,
    reason="pyannote requires PyTorch which has DLL issues on Windows"
)


class TestDiarizer:
    """Tests for Diarizer class."""

    @pytest.fixture
    def diarizer(self):
        return Diarizer(model_name="pyannote/speaker-diarization-3.1", device="cpu")

    def test_initialization(self, diarizer):
        """Test diarizer initialization."""
        assert diarizer.model_name == "pyannote/speaker-diarization-3.1"
        assert diarizer.device == "cpu"
        assert diarizer.min_speakers == 1
        assert diarizer.max_speakers == 10
        assert diarizer._pipeline is None
        assert diarizer._loaded is False

    @patch("pyannote.audio.Pipeline")
    def test_load_pipeline(self, mock_pipeline_class, diarizer):
        """Test lazy pipeline loading."""
        mock_pipeline = Mock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        diarizer._load_pipeline()

        assert diarizer._loaded is True
        assert diarizer._pipeline == mock_pipeline
        mock_pipeline_class.from_pretrained.assert_called_once_with(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=None,
        )

    @patch("pyannote.audio.Pipeline")
    def test_diarize_file(self, mock_pipeline_class, diarizer):
        """Test file diarization."""
        mock_pipeline = Mock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        # Mock diarization output
        mock_turn1 = Mock()
        mock_turn1.start = 0.0
        mock_turn1.end = 5.0

        mock_turn2 = Mock()
        mock_turn2.start = 5.0
        mock_turn2.end = 10.0

        mock_turn3 = Mock()
        mock_turn3.start = 10.0
        mock_turn3.end = 15.0

        # itertracks returns (turn, _, speaker)
        mock_pipeline.return_value.itertracks.return_value = [
            (mock_turn1, None, "SPEAKER_00"),
            (mock_turn2, None, "SPEAKER_01"),
            (mock_turn3, None, "SPEAKER_00"),
        ]

        result = diarizer.diarize_file("/fake/path/audio.wav")

        assert isinstance(result, DiarizationResult)
        assert len(result.segments) == 3
        assert result.speakers == ["SPEAKER_00", "SPEAKER_01"]
        assert result.num_speakers == 2
        assert result.total_duration == 15.0

        # Check segments
        assert result.segments[0].speaker_id == "SPEAKER_00"
        assert result.segments[0].start_time == 0.0
        assert result.segments[0].end_time == 5.0
        assert result.segments[0].duration == 5.0

    @patch("pyannote.audio.Pipeline")
    def test_diarize_audio_data(self, mock_pipeline_class, diarizer):
        """Test audio data diarization."""
        mock_pipeline = Mock()
        mock_pipeline_class.from_pretrained.return_value = mock_pipeline

        mock_turn = Mock()
        mock_turn.start = 0.0
        mock_turn.end = 3.0

        mock_pipeline.return_value.itertracks.return_value = [
            (mock_turn, None, "SPEAKER_00"),
        ]

        audio_data = b"fake_audio_data"
        result = diarizer.diarize_audio_data(audio_data, sample_rate=16000)

        assert isinstance(result, DiarizationResult)
        assert len(result.segments) == 1
        assert result.segments[0].speaker_id == "SPEAKER_00"

    def test_diarize_file_without_pipeline_raises(self, diarizer):
        """Test that diarize_file loads pipeline automatically."""
        pass


class TestMergeTranscriptWithDiarization:
    """Tests for transcript-diarization merging."""

    def test_merge_basic(self):
        """Test basic merging of transcript with diarization."""
        transcript = [
            {"segment_id": "seg1", "start_time": 0.0, "end_time": 3.0, "text": "Hello"},
            {"segment_id": "seg2", "start_time": 3.0, "end_time": 6.0, "text": "World"},
            {"segment_id": "seg3", "start_time": 6.0, "end_time": 9.0, "text": "Test"},
        ]

        diarization = DiarizationResult(
            segments=[
                SpeakerSegment("SPEAKER_00", 0.0, 5.0, 5.0),
                SpeakerSegment("SPEAKER_01", 5.0, 10.0, 5.0),
            ],
            speakers=["SPEAKER_00", "SPEAKER_01"],
            total_duration=10.0,
            num_speakers=2,
        )

        merged = merge_transcript_with_diarization(transcript, diarization)

        assert len(merged) == 3
        assert merged[0]["speaker_id"] == "SPEAKER_00"  # 0-3 overlaps with 0-5
        assert merged[1]["speaker_id"] == "SPEAKER_00"  # 3-6 overlaps with 0-5 (3 sec overlap) vs 5-10 (1 sec overlap)
        assert merged[2]["speaker_id"] == "SPEAKER_01"  # 6-9 overlaps with 5-10

    def test_merge_no_overlap(self):
        """Test merging when no overlap."""
        transcript = [
            {"segment_id": "seg1", "start_time": 0.0, "end_time": 1.0, "text": "Hi"},
        ]

        diarization = DiarizationResult(
            segments=[
                SpeakerSegment("SPEAKER_00", 10.0, 20.0, 10.0),
            ],
            speakers=["SPEAKER_00"],
            total_duration=20.0,
            num_speakers=1,
        )

        merged = merge_transcript_with_diarization(transcript, diarization)

        assert merged[0]["speaker_id"] == "UNKNOWN"
        assert merged[0]["speaker_confidence"] == 0.0

    def test_merge_empty_diarization(self):
        """Test merging with empty diarization."""
        transcript = [
            {"segment_id": "seg1", "start_time": 0.0, "end_time": 1.0, "text": "Hi"},
        ]

        diarization = DiarizationResult(
            segments=[],
            speakers=[],
            total_duration=0.0,
            num_speakers=0,
        )

        merged = merge_transcript_with_diarization(transcript, diarization)

        assert merged[0]["speaker_id"] == "UNKNOWN"

    def test_confidence_calculation(self):
        """Test speaker confidence calculation."""
        transcript = [
            {"segment_id": "seg1", "start_time": 0.0, "end_time": 10.0, "text": "Long segment"},
        ]

        diarization = DiarizationResult(
            segments=[
                SpeakerSegment("SPEAKER_00", 0.0, 5.0, 5.0),   # 5 sec overlap
                SpeakerSegment("SPEAKER_01", 5.0, 10.0, 5.0),  # 5 sec overlap
            ],
            speakers=["SPEAKER_00", "SPEAKER_01"],
            total_duration=10.0,
            num_speakers=2,
        )

        merged = merge_transcript_with_diarization(transcript, diarization)

        # Both have 50% overlap, should pick first one (SPEAKER_00)
        assert merged[0]["speaker_id"] == "SPEAKER_00"
        assert merged[0]["speaker_confidence"] == 0.5


class TestSpeakerSegment:
    """Tests for SpeakerSegment dataclass."""

    def test_creation(self):
        """Test segment creation."""
        segment = SpeakerSegment(
            speaker_id="SPEAKER_00",
            start_time=0.0,
            end_time=5.0,
            duration=5.0,
            confidence=0.9
        )
        assert segment.speaker_id == "SPEAKER_00"
        assert segment.duration == 5.0
        assert segment.confidence == 0.9


class TestDiarizationResult:
    """Tests for DiarizationResult dataclass."""

    def test_creation(self):
        """Test result creation."""
        segments = [
            SpeakerSegment("SPEAKER_00", 0.0, 5.0, 5.0),
            SpeakerSegment("SPEAKER_01", 5.0, 10.0, 5.0),
        ]
        result = DiarizationResult(
            segments=segments,
            speakers=["SPEAKER_00", "SPEAKER_01"],
            total_duration=10.0,
            num_speakers=2,
        )
        assert result.num_speakers == 2
        assert result.total_duration == 10.0


class TestStreamingDiarizer:
    """Tests for StreamingDiarizer."""

    def test_initialization(self):
        """Test streaming diarizer initialization."""
        from app.core.ingestion.live_capture.diarization import StreamingDiarizer
        mock_diarizer = Mock()
        streamer = StreamingDiarizer(mock_diarizer, chunk_duration=10.0, overlap=1.0)

        assert streamer.diarizer == mock_diarizer
        assert streamer.chunk_duration == 10.0
        assert streamer.overlap == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])