# app/core/auth/rbac.py
"""Enterprise RBAC System - Role-Based Access Control with ABAC extensions."""
from enum import Enum
from typing import Set, Dict, List, Optional, Any
from dataclasses import dataclass, field
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class Permission(str, Enum):
    """Granular permissions for the system."""
    # Episode permissions
    EPISODE_CREATE = "episode:create"
    EPISODE_READ = "episode:read"
    EPISODE_UPDATE = "episode:update"
    EPISODE_DELETE = "episode:delete"
    EPISODE_LIST = "episode:list"
    EPISODE_REPROCESS = "episode:reprocess"
    
    # Query permissions
    QUERY_EXECUTE = "query:execute"
    QUERY_HISTORY = "query:history"
    QUERY_EXPORT = "query:export"
    
    # Document permissions
    DOCUMENT_UPLOAD = "document:upload"
    DOCUMENT_DOWNLOAD = "document:download"
    DOCUMENT_DELETE = "document:delete"
    
    # Calculator permissions
    CALCULATOR_EXECUTE = "calculator:execute"
    CALCULATOR_CONFIGURE = "calculator:configure"
    
    # Admin permissions
    TENANT_MANAGE = "tenant:manage"
    USER_MANAGE = "user:manage"
    ROLE_MANAGE = "role:manage"
    SETTINGS_MANAGE = "settings:manage"
    AUDIT_VIEW = "audit:view"
    SYSTEM_HEALTH = "system:health"
    
    # Webhook permissions
    WEBHOOK_REGISTER = "webhook:register"
    WEBHOOK_MANAGE = "webhook:manage"
    
    # Worker permissions
    WORKER_VIEW = "worker:view"
    WORKER_MANAGE = "worker:manage"
    QUEUE_MANAGE = "queue:manage"
    
    # API Key permissions
    API_KEY_CREATE = "api_key:create"
    API_KEY_REVOKE = "api_key:revoke"
    API_KEY_VIEW = "api_key:view"
    
    # Integration permissions
    INTEGRATION_CONFIGURE = "integration:configure"
    INTEGRATION_TEST = "integration:test"


class Role(str, Enum):
    """Predefined roles with permission sets."""
    # System roles
    SUPER_ADMIN = "super_admin"
    TENANT_ADMIN = "tenant_admin"
    
    # Operational roles
    AP_MANAGER = "ap_manager"
    AP_ANALYST = "ap_analyst"
    AP_CLERK = "ap_clerk"
    AP_AUDITOR = "ap_auditor"
    
    # Technical roles
    DEVELOPER = "developer"
    INTEGRATION_ENGINEER = "integration_engineer"
    DATA_ENGINEER = "data_engineer"
    
    # Read-only roles
    VIEWER = "viewer"
    REPORT_VIEWER = "report_viewer"
    
    # API roles
    API_CLIENT = "api_client"
    WEBHOOK_RECEIVER = "webhook_receiver"


# Role-Permission mapping
ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.SUPER_ADMIN: set(Permission),  # All permissions
    
    Role.TENANT_ADMIN: {
        Permission.EPISODE_CREATE, Permission.EPISODE_READ, Permission.EPISODE_UPDATE,
        Permission.EPISODE_DELETE, Permission.EPISODE_LIST, Permission.EPISODE_REPROCESS,
        Permission.QUERY_EXECUTE, Permission.QUERY_HISTORY, Permission.QUERY_EXPORT,
        Permission.DOCUMENT_UPLOAD, Permission.DOCUMENT_DOWNLOAD, Permission.DOCUMENT_DELETE,
        Permission.CALCULATOR_EXECUTE, Permission.CALCULATOR_CONFIGURE,
        Permission.USER_MANAGE, Permission.ROLE_MANAGE, Permission.SETTINGS_MANAGE,
        Permission.AUDIT_VIEW, Permission.SYSTEM_HEALTH,
        Permission.WEBHOOK_REGISTER, Permission.WEBHOOK_MANAGE,
        Permission.WORKER_VIEW, Permission.WORKER_MANAGE, Permission.QUEUE_MANAGE,
        Permission.API_KEY_CREATE, Permission.API_KEY_REVOKE, Permission.API_KEY_VIEW,
        Permission.INTEGRATION_CONFIGURE, Permission.INTEGRATION_TEST,
    },
    
    Role.AP_MANAGER: {
        Permission.EPISODE_CREATE, Permission.EPISODE_READ, Permission.EPISODE_UPDATE,
        Permission.EPISODE_LIST, Permission.EPISODE_REPROCESS,
        Permission.QUERY_EXECUTE, Permission.QUERY_HISTORY, Permission.QUERY_EXPORT,
        Permission.DOCUMENT_UPLOAD, Permission.DOCUMENT_DOWNLOAD,
        Permission.CALCULATOR_EXECUTE, Permission.CALCULATOR_CONFIGURE,
        Permission.AUDIT_VIEW, Permission.WEBHOOK_REGISTER,
        Permission.WORKER_VIEW, Permission.QUEUE_MANAGE,
        Permission.INTEGRATION_TEST,
    },
    
    Role.AP_ANALYST: {
        Permission.EPISODE_READ, Permission.EPISODE_LIST,
        Permission.QUERY_EXECUTE, Permission.QUERY_HISTORY, Permission.QUERY_EXPORT,
        Permission.DOCUMENT_DOWNLOAD, Permission.CALCULATOR_EXECUTE,
        Permission.AUDIT_VIEW, Permission.WORKER_VIEW,
    },
    
    Role.AP_CLERK: {
        Permission.EPISODE_CREATE, Permission.EPISODE_READ, Permission.EPISODE_LIST,
        Permission.DOCUMENT_UPLOAD, Permission.CALCULATOR_EXECUTE,
    },
    
    Role.AP_AUDITOR: {
        Permission.EPISODE_READ, Permission.EPISODE_LIST,
        Permission.QUERY_EXECUTE, Permission.QUERY_HISTORY, Permission.QUERY_EXPORT,
        Permission.DOCUMENT_DOWNLOAD, Permission.AUDIT_VIEW,
    },
    
    Role.DEVELOPER: {
        Permission.EPISODE_READ, Permission.EPISODE_LIST,
        Permission.QUERY_EXECUTE, Permission.QUERY_HISTORY,
        Permission.DOCUMENT_DOWNLOAD, Permission.CALCULATOR_EXECUTE,
        Permission.WEBHOOK_REGISTER, Permission.WEBHOOK_MANAGE,
        Permission.API_KEY_CREATE, Permission.API_KEY_VIEW,
        Permission.INTEGRATION_CONFIGURE, Permission.INTEGRATION_TEST,
    },
    
    Role.INTEGRATION_ENGINEER: {
        Permission.EPISODE_READ, Permission.EPISODE_LIST,
        Permission.WEBHOOK_REGISTER, Permission.WEBHOOK_MANAGE,
        Permission.API_KEY_CREATE, Permission.API_KEY_VIEW,
        Permission.INTEGRATION_CONFIGURE, Permission.INTEGRATION_TEST,
        Permission.WORKER_VIEW, Permission.QUEUE_MANAGE,
    },
    
    Role.DATA_ENGINEER: {
        Permission.EPISODE_READ, Permission.EPISODE_LIST, Permission.EPISODE_REPROCESS,
        Permission.QUERY_EXECUTE, Permission.QUERY_HISTORY, Permission.QUERY_EXPORT,
        Permission.DOCUMENT_DOWNLOAD, Permission.WORKER_VIEW, Permission.QUEUE_MANAGE,
    },
    
    Role.VIEWER: {
        Permission.EPISODE_READ, Permission.EPISODE_LIST,
        Permission.QUERY_EXECUTE, Permission.QUERY_HISTORY,
    },
    
    Role.REPORT_VIEWER: {
        Permission.EPISODE_READ, Permission.EPISODE_LIST,
        Permission.QUERY_EXECUTE, Permission.QUERY_HISTORY, Permission.QUERY_EXPORT,
    },
    
    Role.API_CLIENT: {
        Permission.EPISODE_CREATE, Permission.EPISODE_READ, Permission.EPISODE_LIST,
        Permission.QUERY_EXECUTE, Permission.DOCUMENT_UPLOAD, Permission.DOCUMENT_DOWNLOAD,
        Permission.CALCULATOR_EXECUTE,
    },
    
    Role.WEBHOOK_RECEIVER: {
        Permission.WEBHOOK_REGISTER,
    },
}


@dataclass
class UserContext:
    """User context for authorization decisions."""
    user_id: str
    tenant_id: str
    roles: Set[Role]
    permissions: Set[Permission] = field(default_factory=set)
    attributes: Dict[str, Any] = field(default_factory=dict)  # For ABAC
    
    def __post_init__(self):
        # Aggregate permissions from roles
        for role in self.roles:
            self.permissions.update(ROLE_PERMISSIONS.get(role, set()))
    
    def has_permission(self, permission: Permission) -> bool:
        """Check if user has a specific permission."""
        return permission in self.permissions
    
    def has_any_permission(self, permissions: Set[Permission]) -> bool:
        """Check if user has any of the given permissions."""
        return bool(self.permissions & permissions)
    
    def has_all_permissions(self, permissions: Set[Permission]) -> bool:
        """Check if user has all of the given permissions."""
        return permissions.issubset(self.permissions)
    
    def has_role(self, role: Role) -> bool:
        """Check if user has a specific role."""
        return role in self.roles


class AuthorizationEngine:
    """Central authorization engine with ABAC support."""
    
    def __init__(self):
        self.policies: List[callable] = []
    
    def register_policy(self, policy_func: callable):
        """Register a custom authorization policy."""
        self.policies.append(policy_func)
    
    def authorize(self, context: UserContext, permission: Permission, 
                  resource: Optional[Dict[str, Any]] = None) -> bool:
        """
        Authorize a user action.
        
        Args:
            context: User context
            permission: Required permission
            resource: Optional resource context for ABAC
            
        Returns:
            True if authorized, False otherwise
        """
        # Basic RBAC check
        if not context.has_permission(permission):
            logger.warning(f"User {context.user_id} denied {permission.value}: insufficient permissions")
            return False
        
        # ABAC policies
        for policy in self.policies:
            try:
                if not policy(context, permission, resource):
                    logger.warning(f"User {context.user_id} denied {permission.value}: policy denied")
                    return False
            except Exception as e:
                logger.error(f"Policy evaluation error: {e}")
                return False
        
        return True
    
    def authorize_or_raise(self, context: UserContext, permission: Permission,
                           resource: Optional[Dict[str, Any]] = None):
        """Authorize or raise ForbiddenException."""
        from app.core.exceptions import ForbiddenException
        if not self.authorize(context, permission, resource):
            raise ForbiddenException(
                f"Insufficient permissions: {permission.value} required"
            )


# Global authorization engine
_auth_engine: Optional[AuthorizationEngine] = None


def get_authorization_engine() -> AuthorizationEngine:
    """Get global authorization engine."""
    global _auth_engine
    if _auth_engine is None:
        _auth_engine = AuthorizationEngine()
    return _auth_engine


# Default ABAC policies
def tenant_isolation_policy(context: UserContext, permission: Permission, 
                           resource: Optional[Dict[str, Any]]) -> bool:
    """Enforce tenant isolation - users can only access their tenant's resources."""
    if resource and "tenant_id" in resource:
        return str(context.tenant_id) == str(resource["tenant_id"])
    return True


def ownership_policy(context: UserContext, permission: Permission,
                    resource: Optional[Dict[str, Any]]) -> bool:
    """Users can only modify resources they own (unless admin)."""
    if Role.TENANT_ADMIN in context.roles or Role.SUPER_ADMIN in context.roles:
        return True
    
    if resource and "owner_id" in resource:
        return str(context.user_id) == str(resource["owner_id"])
    return True


def sensitive_operation_policy(context: UserContext, permission: Permission,
                              resource: Optional[Dict[str, Any]]) -> bool:
    """Additional checks for sensitive operations."""
    sensitive_permissions = {
        Permission.EPISODE_DELETE, Permission.TENANT_MANAGE,
        Permission.USER_MANAGE, Permission.ROLE_MANAGE,
        Permission.API_KEY_REVOKE, Permission.SETTINGS_MANAGE,
    }
    
    if permission in sensitive_permissions:
        # Require explicit admin role for sensitive ops
        return Role.TENANT_ADMIN in context.roles or Role.SUPER_ADMIN in context.roles
    return True


# Register default policies
_default_engine = get_authorization_engine()
_default_engine.register_policy(tenant_isolation_policy)
_default_engine.register_policy(ownership_policy)
_default_engine.register_policy(sensitive_operation_policy)


def require_permission(permission: Permission):
    """Decorator for endpoint permission checks."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user context from request (to be implemented with FastAPI dependency)
            from app.middleware.auth import get_current_user_context
            # This will be injected by FastAPI
            context = kwargs.get("user_context") or get_current_user_context()
            
            engine = get_authorization_engine()
            engine.authorize_or_raise(context, permission)
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_any_permission(permissions: Set[Permission]):
    """Decorator requiring at least one of the given permissions."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from app.middleware.auth import get_current_user_context
            context = kwargs.get("user_context") or get_current_user_context()
            
            if not context.has_any_permission(permissions):
                from app.core.exceptions import ForbiddenException
                raise ForbiddenException(
                    f"Requires one of: {[p.value for p in permissions]}"
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_role(role: Role):
    """Decorator requiring a specific role."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            from app.middleware.auth import get_current_user_context
            context = kwargs.get("user_context") or get_current_user_context()
            
            if not context.has_role(role):
                from app.core.exceptions import ForbiddenException
                raise ForbiddenException(f"Requires role: {role.value}")
            return await func(*args, **kwargs)
        return wrapper
    return decorator