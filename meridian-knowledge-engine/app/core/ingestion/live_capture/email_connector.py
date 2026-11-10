# app/core/ingestion/live_capture/email_connector.py
"""Email Connector - IMAP + Microsoft Graph API webhook for real-time email ingestion."""
import asyncio
import imaplib
import email
import email.message
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from uuid import UUID
import httpx
import logging
from dataclasses import dataclass
from enum import Enum

from app.config import get_settings

# Lazy import for parser to avoid libmagic dependency
_parser_module = None

def _get_parser():
    global _parser_module
    if _parser_module is None:
        from app.core.ingestion.parser import DocumentParser
        _parser_module = DocumentParser
    return _parser_module()

settings = get_settings()
logger = logging.getLogger(__name__)


class EmailSourceType(str, Enum):
    IMAP = "imap"
    GRAPH_WEBHOOK = "graph_webhook"


@dataclass
class EmailMessage:
    """Normalized email message."""
    message_id: str
    thread_id: Optional[str]
    from_email: str
    to_emails: List[str]
    cc_emails: List[str]
    subject: str
    body_text: str
    body_html: Optional[str]
    received_at: datetime
    attachments: List[Dict[str, Any]]
    headers: Dict[str, str]


class EmailConnector:
    """
    Real-time email ingestion via IMAP IDLE or Microsoft Graph webhook.
    
    Supports:
    - IMAP IDLE for real-time email notifications
    - Microsoft Graph webhook for Office 365 emails
    - Automatic attachment handling
    - Thread/conversation tracking
    - PII redaction before storage
    """
    
    def __init__(
        self,
        tenant_id: UUID,
        source_type: EmailSourceType = EmailSourceType.IMAP,
        imap_config: Optional[Dict[str, Any]] = None,
        graph_config: Optional[Dict[str, Any]] = None,
        pii_redactor: Optional["LivePIIRedactor"] = None,
    ):
        self.tenant_id = tenant_id
        self.source_type = source_type
        self.imap_config = imap_config or {}
        self.graph_config = graph_config or {}
        self.pii_redactor = pii_redactor
        self.parser = _get_parser()
        
        # Callbacks
        self.on_email: Optional[Callable[[EmailMessage], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None
        
        # State
        self._running = False
        self._imap_client: Optional[imaplib.IMAP4_SSL] = None
        self._http_client: Optional[httpx.AsyncClient] = None
        
    async def start(self) -> None:
        """Start the email connector."""
        self._running = True
        
        if self.source_type == EmailSourceType.IMAP:
            await self._start_imap()
        elif self.source_type == EmailSourceType.GRAPH_WEBHOOK:
            await self._start_graph_webhook()
        else:
            raise ValueError(f"Unknown source type: {self.source_type}")
    
    async def stop(self) -> None:
        """Stop the email connector."""
        self._running = False
        
        if self._imap_client:
            try:
                self._imap_client.idle_done()
                self._imap_client.logout()
            except Exception as e:
                logger.warning(f"Error closing IMAP: {e}")
            self._imap_client = None
        
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
    
    async def _start_imap(self) -> None:
        """Start IMAP IDLE connection."""
        host = self.imap_config.get("host", "imap.gmail.com")
        port = self.imap_config.get("port", 993)
        username = self.imap_config.get("username")
        password = self.imap_config.get("password")
        
        if not username or not password:
            raise ValueError("IMAP username and password required")
        
        # Connect
        self._imap_client = imaplib.IMAP4_SSL(host, port)
        self._imap_client.login(username, password)
        self._imap_client.select("INBOX")
        
        # Start IDLE loop
        asyncio.create_task(self._imap_idle_loop())
    
    async def _imap_idle_loop(self) -> None:
        """IMAP IDLE loop for real-time email notifications."""
        while self._running:
            try:
                # Use IMAP IDLE
                self._imap_client.idle()
                
                # Wait for response (timeout after 29 minutes per RFC)
                try:
                    responses = self._imap_client.idle_check(timeout=29 * 60)
                except Exception:
                    responses = None
                
                self._imap_client.idle_done()
                
                if responses:
                    for response in responses:
                        if response and b"EXISTS" in response:
                            # New email arrived
                            await self._fetch_new_emails()
                            
            except Exception as e:
                logger.error(f"IMAP IDLE error: {e}")
                await asyncio.sleep(30)  # Back off
                if self._running:
                    try:
                        self._imap_client = imaplib.IMAP4_SSL(
                            self.imap_config.get("host", "imap.gmail.com"),
                            self.imap_config.get("port", 993)
                        )
                        self._imap_client.login(
                            self.imap_config["username"],
                            self.imap_config["password"]
                        )
                        self._imap_client.select("INBOX")
                    except Exception as e:
                        logger.error(f"Failed to reconnect IMAP: {e}")
    
    async def _fetch_new_emails(self) -> None:
        """Fetch newly arrived emails."""
        try:
            # Search for unseen emails
            status, messages = self._imap_client.search(None, "UNSEEN")
            if status != "OK":
                return
            
            for msg_num in messages[0].split():
                try:
                    # Fetch full message
                    status, msg_data = self._imap_client.fetch(msg_num, "(RFC822)")
                    if status != "OK":
                        continue
                    
                    raw_email = msg_data[0][1]
                    email_msg = email.message_from_bytes(raw_email)
                    
                    # Parse to EmailMessage
                    email_message = self._parse_email(email_msg)
                    
                    # Redact PII
                    if self.pii_redactor:
                        email_message.body_text = self.pii_redactor.redact(email_message.body_text)
                        if email_message.body_html:
                            email_message.body_html = self.pii_redactor.redact(email_message.body_html)
                    
                    # Trigger callback
                    if self.on_email:
                        await self.on_email(email_message)
                        
                except Exception as e:
                    logger.error(f"Error fetching email {msg_num}: {e}")
                    if self.on_error:
                        self.on_error(e)
                        
        except Exception as e:
            logger.error(f"Error fetching new emails: {e}")
    
    def _parse_email(self, email_msg: email.message.Message) -> EmailMessage:
        """Parse email.message.Message to EmailMessage."""
        # Extract headers
        headers = dict(email_msg.items())
        
        # Extract addresses
        from_email = email.utils.parseaddr(email_msg.get("From", ""))[1]
        to_emails = [addr.strip() for addr in email_msg.get("To", "").split(",") if addr.strip()]
        cc_emails = [addr.strip() for addr in email_msg.get("Cc", "").split(",") if addr.strip()]
        
        # Extract subject
        subject = email.header.decode_header(email_msg.get("Subject", ""))
        subject = " ".join(
            part.decode(enc or "utf-8") if isinstance(part, bytes) else part
            for part, enc in subject
        )
        
        # Extract body
        body_text = ""
        body_html = None
        
        if email_msg.is_multipart():
            for part in email_msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))
                
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    body_text = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
                elif content_type == "text/html" and "attachment" not in content_disposition:
                    body_html = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", errors="ignore")
        else:
            content_type = email_msg.get_content_type()
            payload = email_msg.get_payload(decode=True)
            if isinstance(payload, bytes):
                payload = payload.decode(email_msg.get_content_charset() or "utf-8", errors="ignore")
            if content_type == "text/plain":
                body_text = payload
            elif content_type == "text/html":
                body_html = payload
        
        # Extract attachments
        attachments = []
        for part in email_msg.walk():
            if part.get_content_disposition() == "attachment":
                filename = part.get_filename()
                if filename:
                    filename = email.header.decode_header(filename)[0][0]
                    if isinstance(filename, bytes):
                        filename = filename.decode("utf-8", errors="ignore")
                    content = part.get_payload(decode=True)
                    attachments.append({
                        "filename": filename,
                        "content_type": part.get_content_type(),
                        "size": len(content) if content else 0,
                    })
        
        # Parse date
        date_str = email_msg.get("Date", "")
        received_at = datetime.now()
        if date_str:
            try:
                received_at = email.utils.parsedate_to_datetime(date_str)
            except Exception:
                pass
        
        return EmailMessage(
            message_id=email_msg.get("Message-ID", ""),
            thread_id=email_msg.get("In-Reply-To", "") or email_msg.get("References", ""),
            from_email=from_email,
            to_emails=to_emails,
            cc_emails=cc_emails,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            received_at=received_at,
            attachments=attachments,
            headers=headers,
        )
    
    async def _start_graph_webhook(self) -> None:
        """Start Microsoft Graph webhook listener."""
        # Validate config
        required = ["client_id", "client_secret", "tenant_id", "webhook_url"]
        for key in required:
            if key not in self.graph_config:
                raise ValueError(f"Graph config missing: {key}")
        
        self._http_client = httpx.AsyncClient(timeout=30.0)
        
        # Create subscription
        await self._create_graph_subscription()
        
        # Start webhook server (would need FastAPI/Uvicorn)
        logger.info("Graph webhook started")
    
    async def _create_graph_subscription(self) -> None:
        """Create Microsoft Graph subscription for mail notifications."""
        url = f"https://graph.microsoft.com/v1.0/subscriptions"
        
        # Get access token
        token = await self._get_graph_token()
        
        payload = {
            "changeType": "created",
            "notificationUrl": self.graph_config["webhook_url"],
            "resource": "me/messages",
            "expirationDateTime": (datetime.utcnow() + timedelta(hours=42)).isoformat() + "Z",
            "clientState": "meridian-secret",
        }
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code not in (200, 201):
                raise Exception(f"Failed to create subscription: {response.text}")
            
            data = response.json()
            logger.info(f"Created Graph subscription: {data.get('id')}")
    
    async def _get_graph_token(self) -> str:
        """Get Microsoft Graph access token."""
        # Implement OAuth2 client credentials flow
        # This is a simplified version
        token_url = f"https://login.microsoftonline.com/{self.graph_config['tenant_id']}/oauth2/v2.0/token"
        
        data = {
            "client_id": self.graph_config["client_id"],
            "client_secret": self.graph_config["client_secret"],
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, data=data)
            response.raise_for_status()
            return response.json()["access_token"]


# Factory function
async def create_email_connector(
    tenant_id: UUID,
    source_type: EmailSourceType,
    config: Dict[str, Any],
    pii_redactor: Optional["LivePIIRedactor"] = None,
) -> EmailConnector:
    """Factory to create email connector."""
    connector = EmailConnector(
        tenant_id=tenant_id,
        source_type=source_type,
        imap_config=config.get("imap"),
        graph_config=config.get("graph"),
        pii_redactor=pii_redactor,
    )
    await connector.start()
    return connector