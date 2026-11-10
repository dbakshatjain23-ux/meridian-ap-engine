# app/core/ingestion/live_capture/__init__.py
"""Live Capture Connectors - Email, Teams, Meetings, Drive/SharePoint."""
from app.core.ingestion.live_capture.email_connector import EmailConnector, EmailSourceType
from app.core.ingestion.live_capture.teams_bot import TeamsBot
from app.core.ingestion.live_capture.meeting_bot import MeetingBot, MeetingConfig, MeetingPlatform, MeetingStatus
from app.core.ingestion.live_capture.transcriber import Transcriber
from app.core.ingestion.live_capture.diarization import Diarizer
from app.core.ingestion.live_capture.pii_redactor import LivePIIRedactor
from app.core.ingestion.live_capture.drive_watcher import DriveWatcher, WatchConfig, DrivePlatform, ChangeType

__all__ = [
    "EmailConnector",
    "EmailSourceType",
    "TeamsBot",
    "MeetingBot",
    "MeetingConfig",
    "MeetingPlatform",
    "MeetingStatus",
    "Transcriber",
    "Diarizer",
    "LivePIIRedactor",
    "DriveWatcher",
    "WatchConfig",
    "DrivePlatform",
    "ChangeType",
]