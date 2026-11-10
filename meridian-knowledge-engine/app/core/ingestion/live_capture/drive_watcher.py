# app/core/ingestion/live_capture/drive_watcher.py
"""Drive/SharePoint Watcher - File system and cloud storage change notifications."""
import asyncio
import httpx
import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from uuid import UUID
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class DrivePlatform(str, Enum):
    ONEDRIVE = "onedrive"
    SHAREPOINT = "sharepoint"
    GOOGLE_DRIVE = "google_drive"
    LOCAL = "local"


class ChangeType(str, Enum):
    CREATED = "created"
    UPDATED = "updated"
    DELETED = "deleted"
    MOVED = "moved"


@dataclass
class FileChange:
    """File change event."""
    change_id: str
    change_type: ChangeType
    file_id: str
    file_name: str
    file_path: str
    parent_folder_id: Optional[str]
    modified_by: Optional[str]
    modified_at: datetime
    size: Optional[int]
    mime_type: Optional[str]
    web_url: Optional[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WatchConfig:
    """Configuration for a drive watcher."""
    platform: DrivePlatform
    root_path: str  # Root folder to watch
    platform_specific: Dict[str, Any] = field(default_factory=dict)
    file_types: List[str] = field(default_factory=list)  # e.g., [".docx", ".pdf"]
    recursive: bool = True
    include_deleted: bool = True
    debounce_seconds: float = 1.0


class DriveWatcher:
    """
    Drive/SharePoint Watcher - File system and cloud storage change notifications.

    Features:
    - Real-time file change notifications
    - Microsoft Graph API integration (OneDrive/SharePoint)
    - Google Drive API integration
    - Local file system watching
    - Debounced change events
    - File type filtering
    - Recursive folder watching
    """

    def __init__(
        self,
        tenant_id: str,
        config: WatchConfig,
        on_change: Optional[Callable[[FileChange], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ):
        self.tenant_id = tenant_id
        self.config = config
        self.on_change = on_change
        self.on_error = on_error

        # State
        self._running = False
        self._debounce_tasks: Dict[str, asyncio.Task] = {}
        self._last_events: Dict[str, datetime] = {}

        # HTTP client
        self._http_client: Optional[httpx.AsyncClient] = None

        # Platform-specific
        self._graph_token: Optional[str] = None
        self._graph_token_expires: Optional[datetime] = None

    async def start(self) -> None:
        """Start the drive watcher."""
        self._running = True

        if self.config.platform == DrivePlatform.ONEDRIVE or self.config.platform == DrivePlatform.SHAREPOINT:
            await self._start_graph_watcher()
        elif self.config.platform == DrivePlatform.GOOGLE_DRIVE:
            await self._start_google_drive_watcher()
        elif self.config.platform == DrivePlatform.LOCAL:
            await self._start_local_watcher()
        else:
            raise ValueError(f"Unsupported platform: {self.config.platform}")

        logger.info(f"Drive watcher started for {self.config.platform.value}")

    async def stop(self) -> None:
        """Stop the drive watcher."""
        self._running = False

        # Cancel debounce tasks
        for task in self._debounce_tasks.values():
            task.cancel()

        # Close HTTP client
        if self._http_client:
            await self._http_client.aclose()

        logger.info("Drive watcher stopped")

    async def _start_graph_watcher(self) -> None:
        """Start Microsoft Graph watcher (OneDrive/SharePoint)."""
        # Validate config
        required = ["client_id", "client_secret", "tenant_id", "webhook_url"]
        for key in required:
            if key not in self.config.platform_specific:
                raise ValueError(f"Graph config missing: {key}")

        self._http_client = httpx.AsyncClient(timeout=30.0)

        # Create subscriptions for change notifications
        await self._create_graph_subscription()

        logger.info("Graph watcher started")

    async def _create_graph_subscription(self) -> None:
        """Create Microsoft Graph subscription for change notifications."""
        # Get token
        token = await self._get_graph_token()

        url = "https://graph.microsoft.com/v1.0/subscriptions"

        # Build resource path based on platform
        if self.config.platform == DrivePlatform.ONEDRIVE:
            resource = "me/drive/root"
        else:  # SHAREPOINT
            site_id = self.config.platform_specific.get("site_id")
            drive_id = self.config.platform_specific.get("drive_id")
            resource = f"sites/{site_id}/drives/{drive_id}/root"

        payload = {
            "changeType": "created,updated,deleted",
            "notificationUrl": self.config.platform_specific["webhook_url"],
            "resource": resource,
            "expirationDateTime": (datetime.utcnow() + timedelta(hours=42)).isoformat() + "Z",
            "clientState": "meridian-watcher",
            "latestSupportedTlsVersion": "v1_2",
        }

        headers = {
            "Authorization": f"Bearer {await self._get_graph_token()}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://graph.microsoft.com/v1.0/subscriptions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            logger.info("Created Graph subscription")

    async def _get_graph_token(self) -> str:
        """Get Microsoft Graph access token."""
        if self._graph_token and self._graph_token_expires and datetime.utcnow() < self._graph_token_expires:
            return self._graph_token

        config = self.config.platform_specific
        url = f"https://login.microsoftonline.com/{config['tenant_id']}/oauth2/v2.0/token"

        data = {
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://login.microsoftonline.com/{config['tenant_id']}/oauth2/v2.0/token",
                data=data,
            )
            response.raise_for_status()
            data = response.json()

            self._graph_token = data["access_token"]
            expires_in = data.get("expires_in", 3600)
            self._graph_token_expires = datetime.utcnow() + timedelta(seconds=expires_in - 300)

            return self._graph_token

    async def handle_webhook(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming webhook from Microsoft Graph.

        Returns:
            Response dict for Graph webhook
        """
        # Validate client state
        client_state = request_body.get("clientState")
        if client_state != "meridian-watcher":
            return {"status": "invalid_client_state"}

        # Process each change
        for notification in request_body.get("value", []):
            await self._process_graph_notification(notification)

        return {"status": "ok"}

    async def _process_graph_notification(self, notification: Dict[str, Any]) -> None:
        """Process a single Graph change notification."""
        # Decode the change
        change = FileChange(
            change_id=notification.get("id", ""),
            change_type=ChangeType(notification.get("changeType", "updated")),
            file_id=notification.get("resourceData", {}).get("id", ""),
            file_name=notification.get("resourceData", {}).get("name", ""),
            file_path=notification.get("resourceData", {}).get("parentReference", {}).get("path", ""),
            parent_folder_id=notification.get("resourceData", {}).get("parentReference", {}).get("id"),
            modified_by=notification.get("resourceData", {}).get("lastModifiedBy", {}).get("user", {}).get("displayName"),
            modified_at=datetime.fromisoformat(notification.get("resourceData", {}).get("lastModifiedDateTime", "").replace("Z", "+00:00")) if notification.get("resourceData", {}).get("lastModifiedDateTime") else datetime.utcnow(),
            size=notification.get("resourceData", {}).get("size"),
            mime_type=notification.get("resourceData", {}).get("file", {}).get("mimeType"),
            web_url=notification.get("resourceData", {}).get("webUrl"),
        )

        # Apply debouncing
        await self._debounce_and_emit(change)

    async def _debounce_and_emit(self, change: FileChange) -> None:
        """Debounce rapid changes to the same file."""
        key = f"{change.file_id}:{change.change_type.value}"

        # Cancel existing debounce task
        if key in self._debounce_tasks:
            self._debounce_tasks[key].cancel()

        # Schedule new debounced emit
        async def emit_after_debounce():
            await asyncio.sleep(self.config.debounce_seconds)
            if self.on_change:
                await self.on_change(change)
            self._debounce_tasks.pop(change.file_id + ":" + change.change_type.value, None)

        self._debounce_tasks[key] = asyncio.create_task(emit_after_debounce())

    async def _start_google_drive_watcher(self) -> None:
        """Start Google Drive watcher."""
        # Google Drive API v3 with push notifications
        logger.info("Google Drive watcher not yet implemented")
        raise NotImplementedError("Google Drive watcher not yet implemented")

    async def _start_local_watcher(self) -> None:
        """Start local file system watcher using watchdog."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            raise ImportError("watchdog not installed. Install with: pip install watchdog")

        class ChangeHandler(FileSystemEventHandler):
            def __init__(self, watcher: 'DriveWatcher'):
                self.watcher = watcher

            def on_created(self, event):
                if not event.is_directory:
                    asyncio.create_task(self.watcher._handle_local_change(event, ChangeType.CREATED))

            def on_modified(self, event):
                if not event.is_directory:
                    asyncio.create_task(self.watcher._handle_local_change(event, ChangeType.UPDATED))

            def on_deleted(self, event):
                if not event.is_directory:
                    asyncio.create_task(self.watcher._handle_local_change(event, ChangeType.DELETED))

            def on_moved(self, event):
                if not event.is_directory:
                    asyncio.create_task(self.watcher._handle_local_change(event, ChangeType.MOVED))

        handler = ChangeHandler(self)
        self._observer = Observer()
        self._observer.schedule(handler, self.config.root_path, recursive=self.config.recursive)
        self._observer.start()

        logger.info(f"Local file watcher started on {self.config.root_path}")

    async def _handle_local_change(self, event, change_type: ChangeType) -> None:
        """Handle local file system change."""
        import os

        file_path = event.src_path
        if not os.path.exists(file_path) and change_type != ChangeType.DELETED:
            return

        # Check file type filter
        if self.config.file_types:
            ext = os.path.splitext(event.src_path)[1].lower()
            if ext not in self.config.file_types:
                return

        change = FileChange(
            change_id=f"{event.src_path}:{change_type.value}",
            change_type=change_type,
            file_id=event.src_path,
            file_name=os.path.basename(event.src_path),
            file_path=event.src_path,
            parent_folder_id=os.path.dirname(event.src_path),
            modified_at=datetime.utcnow(),
            size=os.path.getsize(event.src_path) if os.path.exists(event.src_path) else None,
        )

        await self._debounce_and_emit(change)


# Factory
async def create_drive_watcher(
    tenant_id: str,
    config: WatchConfig,
    on_change: Optional[Callable[[FileChange], None]] = None,
    on_error: Optional[Callable[[Exception], None]] = None,
) -> DriveWatcher:
    """Factory to create drive watcher."""
    watcher = DriveWatcher(
        tenant_id=tenant_id,
        config=config,
        on_change=on_change,
        on_error=on_error,
    )
    await watcher.start()
    return watcher