# app/core/audit.py
"""Audit Logging - Comprehensive audit trail for compliance."""
import json
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from contextvars import ContextVar
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.config import get_settings
from app.database import Base
from sqlalchemy import Column, String, DateTime, Text, JSON, Index, BigInteger
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

settings = get_settings()

logger = logging.getLogger(__name__)

# Context variable for request correlation
request_context: ContextVar[Dict[str, Any]] = ContextVar("request_context", default={})


class AuditEventType(str, Enum):
    """Types of auditable events."""
    # Authentication
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    TOKEN_REFRESH = "token_refresh"
    PASSWORD_CHANGED = "password_changed"
    PASSWORD_RESET = "password_reset"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"
    
    # Authorization
    PERMISSION_GRANTED = "permission_granted"
    PERMISSION_REVOKED = "permission_revoked"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REMOVED = "role_removed"
    
    # User Management
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_IMPERSONATED = "user_impersonated"
    
    # API Keys
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    API_KEY_USED = "api_key_used"
    
    # Episodes/Documents
    EPISODE_CREATED = "episode_created"
    EPISODE_UPDATED = "episode_updated"
    EPISODE_DELETED = "episode_deleted"
    EPISODE_REPROCESSED = "episode_reprocessed"
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_DOWNLOADED = "document_downloaded"
    
    # Queries
    QUERY_EXECUTED = "query_executed"
    QUERY_EXPORTED = "query_exported"
    
    # Calculators
    CALCULATOR_EXECUTED = "calculator_executed"
    
    # Webhooks
    WEBHOOK_REGISTERED = "webhook_registered"
    WEBHOOK_DELIVERED = "webhook_delivered"
    WEBHOOK_FAILED = "webhook_failed"
    WEBHOOK_VERIFICATION_FAILED = "webhook_verification_failed"
    
    # Integrations
    INTEGRATION_CONFIGURED = "integration_configured"
    INTEGRATION_SYNC = "integration_sync"
    INTEGRATION_FAILED = "integration_failed"
    
    # System
    SETTINGS_CHANGED = "settings_changed"
    FEATURE_FLAG_CHANGED = "feature_flag_changed"
    MAINTENANCE_MODE = "maintenance_mode"
    
    # Data Access
    DATA_EXPORTED = "data_exported"
    DATA_IMPORTED = "data_imported"
    PII_ACCESSED = "pii_accessed"
    PII_REDACTED = "pii_redacted"
    
    # Compliance
    DATA_RETENTION_APPLIED = "data_retention_applied"
    GDPR_REQUEST = "gdpr_request"
    DPDP_REQUEST = "dpdp_request"
    AUDIT_LOG_ACCESSED = "audit_log_accessed"


class AuditSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Structured audit event."""
    event_type: AuditEventType
    severity: AuditSeverity = AuditSeverity.MEDIUM
    
    # Actor
    actor_id: Optional[str] = None
    actor_type: str = "user"  # user, system, api_key, webhook
    actor_roles: List[str] = field(default_factory=list)
    
    # Tenant
    tenant_id: Optional[str] = None
    
    # Resource
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    resource_owner_id: Optional[str] = None
    
    # Request context
    request_id: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    api_key_id: Optional[str] = None
    
    # Event details
    action: str = ""
    outcome: str = "success"  # success, failure, partial
    error_message: Optional[str] = None
    
    # Changes
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    changed_fields: List[str] = field(default_factory=list)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Timestamps
    timestamp: datetime = field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = None
    
    # Correlation
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        # Convert enums to strings
        data["event_type"] = self.event_type.value
        data["severity"] = self.severity.value
        data["timestamp"] = self.timestamp.isoformat() + "Z"
        if self.processed_at:
            data["processed_at"] = self.processed_at.isoformat() + "Z"
        return data


class AuditLogger:
    """Enterprise audit logger with multiple outputs."""
    
    def __init__(self):
        self._handlers: List[callable] = []
        self._buffer: List[AuditEvent] = []
        self._buffer_size = 100
        self._flush_interval = 5  # seconds
        self._last_flush = datetime.utcnow()
    
    def add_handler(self, handler: callable):
        """Add custom audit handler."""
        self._handlers.append(handler)
    
    def log(self, event: AuditEvent):
        """Log an audit event."""
        # Enrich with request context
        context = request_context.get()
        if context:
            if not event.request_id:
                event.request_id = context.get("request_id")
            if not event.session_id:
                event.session_id = context.get("session_id")
            if not event.ip_address:
                event.ip_address = context.get("ip_address")
            if not event.user_agent:
                event.user_agent = context.get("user_agent")
            if not event.correlation_id:
                event.correlation_id = context.get("correlation_id")
        
        # Add to buffer
        self._buffer.append(event)
        
        # Flush if buffer full or interval exceeded
        if len(self._buffer) >= self._buffer_size:
            self.flush()
        elif (datetime.utcnow() - self._last_flush).seconds >= self._flush_interval:
            self.flush()
    
    def flush(self):
        """Flush buffer to handlers."""
        if not self._buffer:
            return
        
        events = self._buffer.copy()
        self._buffer.clear()
        self._last_flush = datetime.utcnow()
        
        # Process with all handlers
        for handler in self._handlers:
            try:
                handler(events)
            except Exception as e:
                logger.error(f"Audit handler error: {e}")
    
    def log_event(
        self,
        event_type: AuditEventType,
        actor_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: str = "",
        outcome: str = "success",
        severity: AuditSeverity = AuditSeverity.MEDIUM,
        **kwargs
    ):
        """Convenience method to log an event."""
        event = AuditEvent(
            event_type=event_type,
            severity=severity,
            actor_id=actor_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            outcome=outcome,
            **kwargs
        )
        self.log(event)


# Database model for audit logs
class AuditLog(Base):
    """Audit log database model."""
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_tenant_time", "tenant_id", "timestamp"),
        Index("ix_audit_logs_actor_time", "actor_id", "timestamp"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
        Index("ix_audit_logs_event_type", "event_type"),
        Index("ix_audit_logs_correlation", "correlation_id"),
        {"schema": "public"},
    )
    
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(100), nullable=False, index=True)
    severity = Column(String(20), nullable=False)
    
    # Actor
    actor_id = Column(PG_UUID(as_uuid=True), index=True)
    actor_type = Column(String(50))
    actor_roles = Column(JSON)
    
    # Tenant
    tenant_id = Column(PG_UUID(as_uuid=True), index=True)
    
    # Resource
    resource_type = Column(String(100))
    resource_id = Column(PG_UUID(as_uuid=True))
    resource_owner_id = Column(PG_UUID(as_uuid=True))
    
    # Request context
    request_id = Column(String(100))
    session_id = Column(String(100))
    ip_address = Column(String(45))
    user_agent = Column(Text)
    api_key_id = Column(PG_UUID(as_uuid=True))
    
    # Event details
    action = Column(String(200))
    outcome = Column(String(20))
    error_message = Column(Text)
    
    # Changes
    old_values = Column(JSON)
    new_values = Column(JSON)
    changed_fields = Column(JSON)
    
    # Metadata
    metadata = Column(JSON)
    
    # Timestamps
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    processed_at = Column(DateTime(timezone=True))
    
    # Correlation
    correlation_id = Column(String(100), index=True)
    causation_id = Column(String(100))
    
    def __repr__(self):
        return f"<AuditLog({self.event_type}:{self.action}@{self.timestamp})>"


class DatabaseAuditHandler:
    """Database audit log handler."""
    
    def __init__(self, session_factory):
        self.session_factory = session_factory
    
    async def handle(self, events: List[AuditEvent]):
        """Store events in database."""
        async with self.session_factory() as session:
            for event in events:
                audit_log = AuditLog(
                    event_type=event.event_type.value,
                    severity=event.severity.value,
                    actor_id=event.actor_id,
                    actor_type=event.actor_type,
                    actor_roles=event.actor_roles,
                    tenant_id=event.tenant_id,
                    resource_type=event.resource_type,
                    resource_id=event.resource_id,
                    resource_owner_id=event.resource_owner_id,
                    request_id=event.request_id,
                    session_id=event.session_id,
                    ip_address=event.ip_address,
                    user_agent=event.user_agent,
                    api_key_id=event.api_key_id,
                    action=event.action,
                    outcome=event.outcome,
                    error_message=event.error_message,
                    old_values=event.old_values,
                    new_values=event.new_values,
                    changed_fields=event.changed_fields,
                    metadata=event.metadata,
                    timestamp=event.timestamp,
                    processed_at=event.processed_at,
                    correlation_id=event.correlation_id,
                    causation_id=event.causation_id,
                )
                session.add(audit_log)
            
            await session.commit()


class SIEMAuditHandler:
    """SIEM/Log aggregation handler (Splunk, Datadog, etc.)."""
    
    def __init__(self, endpoint: str, api_key: str):
        self.endpoint = endpoint
        self.api_key = api_key
        self._session = None
    
    async def handle(self, events: List[AuditEvent]):
        """Send events to SIEM."""
        import aiohttp
        
        payload = [e.to_dict() for e in events]
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.endpoint,
                json={"events": payload},
                headers={"Authorization": f"Bearer {self.api_key}"},
            ) as resp:
                if resp.status >= 400:
                    logger.error(f"SIEM ingestion failed: {resp.status}")


# Global audit logger
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
        # Add default console handler for development
        from app.config import get_settings
        settings = get_settings()
        if settings.APP_ENV == "development":
            _audit_logger.add_handler(lambda events: logger.info(f"AUDIT: {[e.event_type.value for e in events]}"))
    return _audit_logger


def set_request_context(**kwargs):
    """Set request context for audit enrichment."""
    current = request_context.get()
    current.update(kwargs)
    request_context.set(current)


def clear_request_context():
    """Clear request context."""
    request_context.set({})


# Convenience functions for common audit events
async def audit_login(
    user_id: str,
    tenant_id: str,
    success: bool,
    ip_address: str,
    user_agent: str,
    error: Optional[str] = None,
):
    """Audit login attempt."""
    logger = get_audit_logger()
    logger.log_event(
        event_type=AuditEventType.LOGIN_SUCCESS if success else AuditEventType.LOGIN_FAILED,
        actor_id=user_id,
        tenant_id=tenant_id,
        actor_type="user",
        action="login",
        outcome="success" if success else "failure",
        severity=AuditSeverity.HIGH if not success else AuditSeverity.MEDIUM,
        ip_address=ip_address,
        user_agent=user_agent,
        error_message=error,
    )


async def audit_permission_change(
    actor_id: str,
    tenant_id: str,
    target_user_id: str,
    permission: str,
    granted: bool,
    roles: List[str],
):
    """Audit permission change."""
    logger = get_audit_logger()
    logger.log_event(
        event_type=AuditEventType.PERMISSION_GRANTED if granted else AuditEventType.PERMISSION_REVOKED,
        actor_id=actor_id,
        tenant_id=tenant_id,
        resource_type="user_permission",
        resource_id=target_user_id,
        action=f"permission_{'grant' if granted else 'revoke'}",
        outcome="success",
        severity=AuditSeverity.HIGH,
        new_values={"permission": permission, "granted": granted},
        actor_roles=roles,
    )


async def audit_data_access(
    actor_id: str,
    tenant_id: str,
    resource_type: str,
    resource_id: str,
    action: str,
    pii_accessed: bool = False,
    fields_accessed: Optional[List[str]] = None,
):
    """Audit data access."""
    logger = get_audit_logger()
    logger.log_event(
        event_type=AuditEventType.PII_ACCESSED if pii_accessed else AuditEventType.QUERY_EXECUTED,
        actor_id=actor_id,
        tenant_id=tenant_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        outcome="success",
        severity=AuditSeverity.HIGH if pii_accessed else AuditSeverity.LOW,
        metadata={"fields_accessed": fields_accessed or []},
    )


async def audit_webhook(
    tenant_id: str,
    webhook_id: str,
    provider: str,
    event: str,
    success: bool,
    error: Optional[str] = None,
):
    """Audit webhook delivery."""
    logger = get_audit_logger()
    logger.log_event(
        event_type=AuditEventType.WEBHOOK_DELIVERED if success else AuditEventType.WEBHOOK_FAILED,
        tenant_id=tenant_id,
        resource_type="webhook",
        resource_id=webhook_id,
        action=f"webhook_{event}",
        outcome="success" if success else "failure",
        severity=AuditSeverity.MEDIUM if success else AuditSeverity.HIGH,
        metadata={"provider": provider},
        error_message=error,
    )


async def audit_calculator(
    actor_id: str,
    tenant_id: str,
    calculator: str,
    inputs: Dict[str, Any],
    result: Dict[str, Any],
    success: bool,
    error: Optional[str] = None,
):
    """Audit calculator execution."""
    logger = get_audit_logger()
    logger.log_event(
        event_type=AuditEventType.CALCULATOR_EXECUTED,
        actor_id=actor_id,
        tenant_id=tenant_id,
        resource_type="calculator",
        resource_id=calculator,
        action=f"execute_{calculator}",
        outcome="success" if success else "failure",
        severity=AuditSeverity.MEDIUM,
        old_values=inputs,
        new_values=result,
        error_message=error,
    )