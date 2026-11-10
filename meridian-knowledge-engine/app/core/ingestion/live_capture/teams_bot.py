# app/core/ingestion/live_capture/teams_bot.py
"""Teams Bot Connector - Real-time Teams message ingestion via Bot Framework."""
import asyncio
import httpx
import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime, timedelta
from uuid import UUID
from dataclasses import dataclass
from enum import Enum
import json

from app.config import get_settings
from app.core.ingestion.live_capture.pii_redactor import LivePIIRedactor

settings = get_settings()
logger = logging.getLogger(__name__)


class TeamsEventType(str, Enum):
    MESSAGE = "message"
    REACTION = "reaction"
    TYPING = "typing"
    MEMBERS_ADDED = "membersAdded"
    MEMBERS_REMOVED = "membersRemoved"


@dataclass
class TeamsMessage:
    """Normalized Teams message."""
    message_id: str
    conversation_id: str
    from_user: Dict[str, Any]  # {id, name, aad_object_id}
    conversation_type: str  # "personal", "groupChat", "channel"
    team_id: Optional[str]
    channel_id: Optional[str]
    body_text: str
    body_html: Optional[str]
    timestamp: datetime
    reply_to_id: Optional[str]
    attachments: List[Dict[str, Any]]
    reactions: List[Dict[str, Any]]  # [{"type": "like", "count": 5, "users": [...]}]
    mentions: List[Dict[str, Any]]  # [{"id": "user-id", "name": "name"}]
    web_url: Optional[str]


class TeamsBot:
    """
    Teams Bot Connector - Real-time Teams message ingestion via Bot Framework.
    
    Features:
    - Real-time message ingestion via webhook
    - Channel and chat message support
    - Thread/reply support
    - Reaction tracking
    - Attachment handling
    - PII redaction
    - Thread context preservation
    """
    
    def __init__(
        self,
        tenant_id: str,
        app_id: str,
        app_password: str,
        webhook_url: str,
        pii_redactor: Optional["LivePIIRedactor"] = None,
    ):
        self.tenant_id = tenant_id
        self.app_id = app_id
        self.app_password = app_password
        self.webhook_url = webhook_url
        self.pii_redactor = pii_redactor
        
        # Bot Framework credentials
        self._token_cache: Optional[str] = None
        self._token_expires: Optional[datetime] = None
        
        # Callbacks
        self.on_message: Optional[Callable[[TeamsMessage], None]] = None
        self.on_reaction: Optional[Callable[[Dict[str, Any]], None]] = None
        self.on_error: Optional[Callable[[Exception], None]] = None
        
        # HTTP client
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def start(self) -> None:
        """Start the Teams bot."""
        self._http_client = httpx.AsyncClient(timeout=30.0)
        
        # Get initial token
        await self._get_token()
        
        # Register webhook
        await self._register_webhook()
        
        logger.info("Teams bot started")
    
    async def stop(self) -> None:
        """Stop the Teams bot."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
    
    async def _get_token(self) -> str:
        """Get Bot Framework access token."""
        if self._token_cache and self._token_expires and datetime.utcnow() < self._token_expires:
            return self._token_cache
        
        url = "https://login.microsoftonline.com/botframework.com/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.app_id,
            "client_secret": self.app_password,
            "scope": "https://api.botframework.com/.default",
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data)
            response.raise_for_status()
            data = response.json()
            
            self._token_cache = data["access_token"]
            expires_in = data.get("expires_in", 3600)
            self._token_expires = datetime.utcnow() + timedelta(seconds=expires_in - 300)  # 5 min buffer
            
            return self._token_cache
    
    async def _register_webhook(self) -> None:
        """Register webhook with Bot Framework."""
        # Bot Framework doesn't require explicit webhook registration
        # Webhook is configured in Azure Bot Service / Azure portal
        logger.info(f"Teams bot webhook configured at: {self.webhook_url}")
    
    async def handle_webhook(self, request_body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle incoming webhook from Bot Framework.
        
        Returns response for Bot Framework.
        """
        activity = request_body
        
        # Verify activity
        if activity.get("type") != "message":
            return {"status": "ok"}
        
        # Verify it's for our bot
        recipient = activity.get("recipient", {})
        if recipient.get("id") != self.app_id:
            return {"status": "ignored"}
        
        # Process message
        try:
            message = self._parse_message(activity)
            
            # Redact PII
            if self.pii_redactor:
                message.body_text = self.pii_redactor.redact(message.body_text)
                if message.body_html:
                    message.body_html = self.pii_redactor.redact(message.body_html)
            
            # Trigger callback
            if self.on_message:
                await self.on_message(message)
            
        except Exception as e:
            logger.error(f"Error processing Teams message: {e}")
            if self.on_error:
                self.on_error(e)
        
        return {"status": "ok"}
    
    def _parse_message(self, activity: Dict[str, Any]) -> 'TeamsMessage':
        """Parse Bot Framework activity to TeamsMessage."""
        from_property = activity.get("from", {})
        conversation = activity.get("conversation", {})
        channel_data = activity.get("channelData", {})
        
        # Extract user info
        from_user = {
            "id": from_property.get("id"),
            "name": from_property.get("name"),
            "aad_object_id": from_property.get("aadObjectId"),
            "role": from_property.get("role"),
        }
        
        # Extract conversation info
        conversation_type = conversation.get("conversationType", "personal")
        team_id = channel_data.get("team", {}).get("id") if channel_data.get("team") else None
        channel_id = channel_data.get("channel", {}).get("id") if channel_data.get("channel") else None
        
        # Extract body
        body_text = activity.get("text", "")
        body_html = None
        if activity.get("attachments"):
            for att in activity["attachments"]:
                if att.get("contentType") == "text/html":
                    body_html = att.get("content")
                    break
        
        # Extract attachments
        attachments = []
        for att in activity.get("attachments", []):
            attachments.append({
                "content_type": att.get("contentType"),
                "content_url": att.get("contentUrl"),
                "name": att.get("name"),
                "content": att.get("content"),
            })
        
        # Extract reactions
        reactions = []
        for reaction in activity.get("reactions", []):
            reactions.append({
                "type": reaction.get("type"),
                "created": reaction.get("created"),
            })
        
        # Extract mentions
        mentions = []
        for entity in activity.get("entities", []):
            if entity.get("type") == "mention":
                mentions.append({
                    "id": entity.get("mentioned", {}).get("id"),
                    "name": entity.get("mentioned", {}).get("name"),
                })
        
        return TeamsMessage(
            message_id=activity.get("id"),
            conversation_id=conversation.get("id"),
            from_user=from_user,
            conversation_type=conversation_type,
            team_id=team_id,
            channel_id=channel_id,
            body_text=body_text,
            body_html=body_html,
            timestamp=datetime.fromisoformat(activity.get("timestamp", datetime.utcnow().isoformat())),
            reply_to_id=activity.get("replyToId"),
            attachments=attachments,
            reactions=reactions,
            mentions=mentions,
            web_url=activity.get("serviceUrl", "") + "v3/conversations/" + conversation.get("id") + "/activities/" + activity.get("id"),
        )
    
    async def send_message(
        self,
        conversation_id: str,
        text: str,
        reply_to_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a message to a conversation."""
        token = await self._get_token()
        
        url = f"https://smba.trafficmanager.net/amer/v3/conversations/{conversation_id}/activities"
        if reply_to_id:
            url += f"/{reply_to_id}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "type": "message",
            "text": text,
            "from": {"id": self.app_id, "name": "Meridian Bot"},
        }
        
        if reply_to_id:
            payload["replyToId"] = reply_to_id
        
        headers = {
            "Authorization": f"Bearer {await self._get_token()}",
            "Content-Type": "application/json",
        }
        
        response = await self._http_client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        return response.json()
    
    async def send_adaptive_card(
        self,
        conversation_id: str,
        card: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Send an Adaptive Card to a conversation."""
        token = await self._get_token()
        
        url = f"https://smba.trafficmanager.net/amer/v3/conversations/{conversation_id}/activities"
        
        payload = {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": card,
            }],
        }
        
        headers = {
            "Authorization": f"Bearer {await self._get_token()}",
            "Content-Type": "application/json",
        }
        
        response = await self._http_client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        
        return response.json()


# Factory
async def create_teams_bot(
    tenant_id: str,
    config: Dict[str, Any],
    pii_redactor: Optional["LivePIIRedactor"] = None,
) -> TeamsBot:
    """Factory to create Teams bot."""
    bot = TeamsBot(
        tenant_id=tenant_id,
        app_id=config["app_id"],
        app_password=config["app_password"],
        webhook_url=config["webhook_url"],
        pii_redactor=pii_redactor,
    )
    await bot.start()
    return bot