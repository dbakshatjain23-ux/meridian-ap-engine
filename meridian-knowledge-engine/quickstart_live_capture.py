#!/usr/bin/env python
"""
Quickstart script for Meridian Live Capture System.

This script demonstrates:
1. Setting up email connector (IMAP)
2. Setting up Teams bot webhook
3. Starting meeting bot
4. Processing a document through the ingestion pipeline
5. Querying the knowledge engine

Run with: python quickstart_live_capture.py
"""
import asyncio
import os
import sys
from uuid import UUID

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set required environment variables
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only-min-64-characters-long-enough-for-validation")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")


async def demo_pii_redaction():
    """Demo PII redaction for Indian context."""
    print("\n" + "=" * 60)
    print("DEMO: PII Redaction (Indian Patterns)")
    print("=" * 60)
    
    from app.core.ingestion.live_capture import LivePIIRedactor
    
    redactor = LivePIIRedactor()
    
    # Test various Indian PII patterns
    test_cases = [
        ("PAN Card", "User's PAN is ABCDE1234F for verification"),
        ("Aadhaar", "Aadhaar number: 1234 5678 9012"),
        ("Email", "Contact john.doe@company.com for details"),
        ("Phone", "Call +91-9876543210 or 09876543210"),
        ("IFSC", "Bank IFSC: SBIN0001234"),
        ("GSTIN", "GSTIN: 27ABCDE1234F1Z5"),
        ("Credit Card", "Card number: 1234 5678 9012 3456"),
        ("Passport", "Passport: A1234567"),
        ("Driving License", "DL: MH1234567890123"),
        ("Voter ID", "Voter ID: ABC1234567"),
    ]
    
    for name, text in test_cases:
        redacted = redactor.redact(text)
        matches = redactor.find_pii(text)
        print(f"\n{name}:")
        print(f"  Original: {text}")
        print(f"  Redacted: {redacted}")
        print(f"  Found: {len(matches)} PII items")
        for m in matches:
            print(f"    - {m['type']}: {m['value']} -> {m['replacement']}")


async def demo_transcriber():
    """Demo transcriber (mock-based)."""
    print("\n" + "=" * 60)
    print("DEMO: Transcriber Configuration")
    print("=" * 60)
    
    from app.core.ingestion.live_capture import Transcriber
    
    transcriber = Transcriber(
        model_size="base",
        device="cpu",
        compute_type="int8",
        language="en",
        vad_filter=True,
    )
    
    print(f"Model: {transcriber.model_size}")
    print(f"Device: {transcriber.device}")
    print(f"Compute Type: {transcriber.compute_type}")
    print(f"Language: {transcriber.language}")
    print(f"VAD Filter: {transcriber.vad_filter}")
    print(f"Supported Languages: {len(transcriber.get_supported_languages())} languages")
    
    # Show what would happen with real audio
    print("\nNote: Actual transcription requires faster-whisper and audio files.")
    print("Install with: pip install faster-whisper")


async def demo_diarization():
    """Demo diarization configuration."""
    print("\n" + "=" * 60)
    print("DEMO: Diarization Configuration")
    print("=" * 60)
    
    from app.core.ingestion.live_capture import Diarizer
    
    diarizer = Diarizer(
        model_name="pyannote/speaker-diarization-3.1",
        device="cpu",
        min_speakers=1,
        max_speakers=10,
    )
    
    print(f"Model: {diarizer.model_name}")
    print(f"Device: {diarizer.device}")
    print(f"Min Speakers: {diarizer.min_speakers}")
    print(f"Max Speakers: {diarizer.max_speakers}")
    
    # Demo transcript-diarization merge
    print("\nTranscript-Diarization Merge Demo:")
    from app.core.ingestion.live_capture.diarization import (
        merge_transcript_with_diarization, DiarizationResult, SpeakerSegment
    )
    
    transcript = [
        {"segment_id": "1", "start_time": 0.0, "end_time": 3.0, "text": "Good morning team"},
        {"segment_id": "2", "start_time": 3.0, "end_time": 6.0, "text": "Let's start the meeting"},
        {"segment_id": "3", "start_time": 6.0, "end_time": 9.0, "text": "Agenda item one"},
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
    
    for seg in merged:
        print(f"  [{seg['speaker_id']}] {seg['text']} (confidence: {seg['speaker_confidence']:.1%})")


async def demo_email_connector():
    """Demo email connector configuration."""
    print("\n" + "=" * 60)
    print("DEMO: Email Connector Configuration")
    print("=" * 60)
    
    from app.core.ingestion.live_capture import EmailConnector, EmailSourceType
    from uuid import UUID
    
    # IMAP configuration
    imap_config = {
        "host": "imap.gmail.com",
        "port": 993,
        "username": "your-email@gmail.com",
        "password": "your-app-password",
    }
    
    # Graph webhook configuration
    graph_config = {
        "client_id": "your-azure-client-id",
        "client_secret": "your-azure-client-secret",
        "tenant_id": "your-azure-tenant-id",
        "webhook_url": "https://your-domain.com/api/episodes/email/webhook",
    }
    
    print("IMAP Config:")
    print(f"  Host: {imap_config['host']}")
    print(f"  Port: {imap_config['port']}")
    print(f"  Username: {imap_config['username']}")
    
    print("\nGraph Webhook Config:")
    print(f"  Client ID: {graph_config['client_id']}")
    print(f"  Webhook URL: {graph_config['webhook_url']}")
    
    print("\nNote: Actual connection requires valid credentials.")
    print("For IMAP: Enable 'Less secure apps' or use App Password.")
    print("For Graph: Register app in Azure AD with Mail.Read permission.")


async def demo_teams_bot():
    """Demo Teams bot configuration."""
    print("\n" + "=" * 60)
    print("DEMO: Teams Bot Configuration")
    print("=" * 60)
    
    from app.core.ingestion.live_capture import TeamsBot
    
    config = {
        "app_id": "your-teams-app-id",
        "app_password": "your-teams-app-password",
        "webhook_url": "https://your-domain.com/api/episodes/teams/webhook",
    }
    
    print("Teams Bot Config:")
    print(f"  App ID: {config['app_id']}")
    print(f"  Webhook URL: {config['webhook_url']}")
    
    print("\nNote: Configure in Azure Bot Service:")
    print("  1. Create Bot resource in Azure")
    print("  2. Add Teams channel")
    print("  3. Set messaging endpoint to webhook URL")
    print("  4. Grant necessary permissions (Chat.Read, ChannelMessage.Read.All)")


async def demo_meeting_bot():
    """Demo meeting bot configuration."""
    print("\n" + "=" * 60)
    print("DEMO: Meeting Bot Configuration")
    print("=" * 60)
    
    from app.core.ingestion.live_capture import MeetingBot, MeetingConfig, MeetingPlatform
    from uuid import UUID
    
    config = MeetingConfig(
        platform=MeetingPlatform.TEAMS,
        meeting_url="https://teams.microsoft.com/l/meetup-join/...",
        meeting_id="meeting-123",
        platform_specific={
            "tenant_id": "your-tenant-id",
            "client_id": "your-client-id",
        },
        record=True,
        transcribe=True,
        diarize=True,
        pii_redact=True,
    )
    
    print("Meeting Config:")
    print(f"  Platform: {config.platform.value}")
    print(f"  Meeting URL: {config.meeting_url}")
    print(f"  Record: {config.record}")
    print(f"  Transcribe: {config.transcribe}")
    print(f"  Diarize: {config.diarize}")
    print(f"  PII Redact: {config.pii_redact}")
    
    print("\nSupported Platforms:")
    for p in MeetingPlatform:
        print(f"  - {p.value}")
    
    print("\nNote: Requires:")
    print("  - faster-whisper for transcription")
    print("  - pyannote.audio for diarization (needs HF token)")
    print("  - GPU recommended for real-time processing")


async def demo_drive_watcher():
    """Demo drive watcher configuration."""
    print("\n" + "=" * 60)
    print("DEMO: Drive Watcher Configuration")
    print("=" * 60)
    
    from app.core.ingestion.live_capture import DriveWatcher, WatchConfig, DrivePlatform
    
    # OneDrive/SharePoint config
    graph_config = WatchConfig(
        platform=DrivePlatform.SHAREPOINT,
        root_path="/sites/yoursite/Shared Documents",
        platform_specific={
            "client_id": "your-client-id",
            "client_secret": "your-client-secret",
            "tenant_id": "your-tenant-id",
            "site_id": "your-site-id",
            "drive_id": "your-drive-id",
            "webhook_url": "https://your-domain.com/api/episodes/drive/webhook",
        },
        file_types=[".pdf", ".docx", ".xlsx", ".pptx", ".txt"],
        recursive=True,
        debounce_seconds=2.0,
    )
    
    # Local file system config
    local_config = WatchConfig(
        platform=DrivePlatform.LOCAL,
        root_path="/data/watch",
        file_types=[".pdf", ".docx"],
        recursive=True,
    )
    
    print("SharePoint Config:")
    print(f"  Platform: {graph_config.platform.value}")
    print(f"  Root Path: {graph_config.root_path}")
    print(f"  File Types: {graph_config.file_types}")
    print(f"  Site ID: {graph_config.platform_specific['site_id']}")
    
    print("\nLocal Config:")
    print(f"  Platform: {local_config.platform.value}")
    print(f"  Root Path: {local_config.root_path}")
    print(f"  File Types: {local_config.file_types}")
    
    print("\nSupported Platforms:")
    for p in DrivePlatform:
        print(f"  - {p.value}")
    
    print("\nNote: Google Drive not yet implemented.")


async def demo_ingestion_worker():
    """Demo ingestion worker."""
    print("\n" + "=" * 60)
    print("DEMO: Ingestion Worker")
    print("=" * 60)
    
    from app.workers import IngestionWorker
    
    print("Worker Configuration:")
    print("  Job Types: ingest, email_ingest, teams_ingest, meeting_ingest")
    print("  Poll Interval: 5 seconds")
    print("  Queue: PostgreSQL SKIP LOCKED")
    
    print("\nProcessing Pipeline:")
    print("  1. Claim job from queue (atomic SKIP LOCKED)")
    print("  2. Load episode and raw content")
    print("  3. Redact PII from content")
    print("  4. Parse document (5-tier parser)")
    print("  5. Structure repair")
    print("  6. Extract entities, topics, facts")
    print("  7. Authority ranking")
    print("  8. Conflict detection (4-case)")
    print("  9. Write to knowledge graph")
    print("  10. Save blocks and facts")
    print("  11. Mark job complete")
    
    print("\nTo run:")
    print("  python -m app.workers.ingestion_worker")
    print("  Or via Docker: docker-compose up worker")


async def demo_api_endpoints():
    """Demo API endpoints for live capture."""
    print("\n" + "=" * 60)
    print("DEMO: Live Capture API Endpoints")
    print("=" * 60)
    
    endpoints = [
        ("POST", "/api/v1/episodes/email/webhook", "Email webhook (Graph/IMAP)"),
        ("POST", "/api/v1/episodes/teams/webhook", "Teams message webhook"),
        ("POST", "/api/v1/episodes/meeting/start", "Start meeting bot"),
        ("POST", "/api/v1/episodes/upload", "Upload document"),
        ("GET", "/api/v1/episodes/{id}/status", "Check ingestion status"),
        ("GET", "/api/v1/workers/health", "Worker health status"),
        ("GET", "/api/v1/workers/queue/stats", "Queue statistics"),
        ("POST", "/api/v1/workers/queue/retry-failed", "Retry failed jobs"),
        ("DELETE", "/api/v1/workers/queue/clear-failed", "Clear old failed jobs"),
    ]
    
    print(f"{'Method':<6} {'Endpoint':<45} {'Description'}")
    print("-" * 80)
    for method, endpoint, desc in endpoints:
        print(f"{method:<6} {endpoint:<45} {desc}")
    
    print("\nExample email webhook payload:")
    print("""  {
    "message_id": "<msg-123@domain.com>",
    "from": "sender@domain.com",
    "to": ["recipient@domain.com"],
    "subject": "Invoice INV-001",
    "body": "Please find attached invoice...",
    "received_at": "2026-08-01T10:00:00Z",
    "attachments": [{"filename": "invoice.pdf", "content_type": "application/pdf"}]
  }""")


async def main():
    print("=" * 60)
    print("MERIDIAN LIVE CAPTURE - QUICKSTART")
    print("=" * 60)
    print("\nThis demo shows the live capture system components.")
    print("All components use mock/safe configurations for demo purposes.")
    
    await demo_pii_redaction()
    await demo_transcriber()
    await demo_diarization()
    await demo_email_connector()
    await demo_teams_bot()
    await demo_meeting_bot()
    await demo_drive_watcher()
    await demo_ingestion_worker()
    await demo_api_endpoints()
    
    print("\n" + "=" * 60)
    print("QUICKSTART COMPLETE")
    print("=" * 60)
    print("\nNext Steps:")
    print("1. Configure real credentials in environment variables")
    print("2. Install optional ML dependencies:")
    print("   pip install faster-whisper pyannote.audio")
    print("3. Set up PostgreSQL and Redis:")
    print("   docker-compose up -d postgres redis")
    print("4. Run database migrations:")
    print("   alembic upgrade head")
    print("5. Start API server:")
    print("   uvicorn app.main:app --reload")
    print("6. Start workers:")
    print("   python -m app.workers.ingestion_worker")
    print("7. Test webhooks with ngrok or similar tunneling")


if __name__ == "__main__":
    asyncio.run(main())