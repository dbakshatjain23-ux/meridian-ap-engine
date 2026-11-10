# app/middleware/auth.py
"""Authentication Middleware - FastAPI dependencies for auth."""
from typing import Optional, List, Set
from fastapi import Depends, HTTPException, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_session
from app.models.user import User
from app.models.api_key import ApiKey
from app.core.auth.jwt_handler import get_jwt_handler, TokenType, JWTHandler
from app.core.auth.rbac import (
    UserContext, Role, Permission, get_authorization_engine, AuthorizationEngine
)
from app.core.exceptions import UnauthorizedException, ForbiddenException

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_scheme = HTTPBearer(auto_error=False)  # For ApiKey auth


async def get_current_user_context(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
    session: AsyncSession = Depends(get_session),
) -> UserContext:
    """
    Extract and validate user context from request.
    Supports: Bearer JWT, Refresh tokens, API Keys, Webhook signatures.
    """
    # Try Bearer token first
    if credentials and credentials.credentials:
        token = credentials.credentials
        try:
            payload = jwt_handler.verify_token(token)
            
            # Convert roles back to Role enum
            roles = {Role(r) for r in payload.roles}
            
            return UserContext(
                user_id=payload.sub,
                tenant_id=payload.tenant_id,
                roles=roles,
                attributes={
                    "session_id": payload.session_id,
                    "token_jti": payload.jti,
                    "token_type": payload.token_type.value,
                } | (payload.metadata or {}),
            )
        except Exception as e:
            # Log but don't fail - try other auth methods
            request.state.auth_error = str(e)
    
    # Try X-API-Key header
    if x_api_key:
        api_key_result = jwt_handler.extract_api_key(f"ApiKey {x_api_key}")
        if api_key_result:
            key_id, secret = api_key_result
            
            # Look up API key in database
            result = await session.execute(
                select(ApiKey).where(
                    ApiKey.key_id == key_id,
                    ApiKey.is_active == True,
                )
            )
            api_key = result.scalar_one_or_none()
            
            if api_key and jwt_handler.verify_secret(secret, api_key.key_hash):
                # Check expiry
                if api_key.expires_at and api_key.expires_at < datetime.utcnow():
                    raise UnauthorizedException("API key has expired")
                
                # Update last used
                api_key.last_used_at = datetime.utcnow()
                await session.commit()
                
                roles = {Role(r) for r in api_key.roles}
                return UserContext(
                    user_id=str(api_key.user_id),
                    tenant_id=str(api_key.tenant_id),
                    roles=roles,
                    attributes={
                        "api_key_id": str(api_key.id),
                        "key_name": api_key.name,
                    },
                )
    
    # Try webhook signature (for webhook endpoints)
    # This would be handled by specific webhook dependencies
    
    raise UnauthorizedException("Authentication required")


async def get_optional_user_context(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
    session: AsyncSession = Depends(get_session),
) -> Optional[UserContext]:
    """Get user context if authenticated, otherwise None."""
    try:
        return await get_current_user_context(request, credentials, x_api_key, jwt_handler, session)
    except (UnauthorizedException, ForbiddenException):
        return None


def require_tenant(tenant_slug: str = "default") -> str:
    """Dependency to get tenant slug from context."""
    # In multi-tenant, extract from user context or header
    return tenant_slug


def require_auth(user_context: UserContext = Depends(get_current_user_context)) -> UserContext:
    """Require authenticated user."""
    return user_context


def require_permission(*permissions: Permission):
    """Dependency factory for permission checks."""
    async def permission_checker(
        user_context: UserContext = Depends(require_auth),
        auth_engine: AuthorizationEngine = Depends(get_authorization_engine),
    ) -> UserContext:
        for perm in permissions:
            auth_engine.authorize_or_raise(user_context, perm)
        return user_context
    return permission_checker


def require_any_permission(*permissions: Permission):
    """Dependency factory for any-of permission checks."""
    async def permission_checker(
        user_context: UserContext = Depends(require_auth),
    ) -> UserContext:
        if not user_context.has_any_permission(set(permissions)):
            raise ForbiddenException(
                f"Requires one of: {[p.value for p in permissions]}"
            )
        return user_context
    return permission_checker


def require_role(*roles: Role):
    """Dependency factory for role checks."""
    async def role_checker(
        user_context: UserContext = Depends(require_auth),
    ) -> UserContext:
        if not any(user_context.has_role(r) for r in roles):
            raise ForbiddenException(f"Requires one of roles: {[r.value for r in roles]}")
        return user_context
    return role_checker


# Common permission dependencies
require_episode_read = require_permission(Permission.EPISODE_READ)
require_episode_write = require_permission(Permission.EPISODE_CREATE, Permission.EPISODE_UPDATE)
require_episode_delete = require_permission(Permission.EPISODE_DELETE)
require_query = require_permission(Permission.QUERY_EXECUTE)
require_document_upload = require_permission(Permission.DOCUMENT_UPLOAD)
require_admin = require_role(Role.TENANT_ADMIN, Role.SUPER_ADMIN)
require_ap_manager = require_role(Role.AP_MANAGER, Role.TENANT_ADMIN, Role.SUPER_ADMIN)
require_developer = require_role(Role.DEVELOPER, Role.INTEGRATION_ENGINEER, Role.TENANT_ADMIN, Role.SUPER_ADMIN)


# Webhook authentication
async def verify_webhook_signature(
    request: Request,
    x_webhook_signature: Optional[str] = Header(None),
    x_webhook_timestamp: Optional[str] = Header(None),
    x_webhook_id: Optional[str] = Header(None),
) -> dict:
    """Verify webhook signature (to be implemented per provider)."""
    # This is a placeholder - implement per webhook provider
    # Microsoft Graph, Teams, etc. have different signature schemes
    return {
        "verified": True,
        "webhook_id": x_webhook_id,
        "timestamp": x_webhook_timestamp,
    }


# Session management
async def create_user_session(
    user: User,
    roles: List[Role],
    request: Request,
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
) -> dict:
    """Create new session tokens for user."""
    session_id = secrets.token_urlsafe(16)
    
    # Create token pair
    token_pair = jwt_handler.create_token_pair(
        user_id=str(user.id),
        tenant_id=str(user.tenant_id),
        roles=roles,
        session_id=session_id,
    )
    
    return {
        "access_token": token_pair.access_token,
        "refresh_token": token_pair.refresh_token,
        "token_type": "bearer",
        "expires_in": token_pair.expires_in,
        "refresh_expires_in": token_pair.refresh_expires_in,
        "session_id": session_id,
    }


async def refresh_session(
    refresh_token: str,
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
) -> dict:
    """Refresh access token using refresh token."""
    try:
        token_pair = jwt_handler.refresh_access_token(refresh_token)
        return {
            "access_token": token_pair.access_token,
            "refresh_token": token_pair.refresh_token,
            "token_type": "bearer",
            "expires_in": token_pair.expires_in,
            "refresh_expires_in": token_pair.refresh_expires_in,
        }
    except Exception as e:
        raise UnauthorizedException(f"Invalid refresh token: {str(e)}")


async def revoke_session(
    user_context: UserContext,
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
) -> dict:
    """Revoke current session."""
    jwt_handler.revoke_token(user_context.attributes.get("token_jti", ""))
    return {"message": "Session revoked"}


# API Key management
async def create_api_key(
    user_context: UserContext,
    name: str,
    expires_days: Optional[int] = None,
    scopes: Optional[List[str]] = None,
    jwt_handler: JWTHandler = Depends(get_jwt_handler),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Create new API key for user."""
    from app.models.api_key import ApiKey
    
    key_id, full_key = jwt_handler.create_api_key(
        user_id=user_context.user_id,
        tenant_id=user_context.tenant_id,
        roles=list(user_context.roles),
        name=name,
        expires_days=expires_days,
        scopes=scopes,
    )
    
    # Store in database (hash the secret)
    secret_hash = jwt_handler.hash_secret(full_key.split(".")[-1])
    
    api_key = ApiKey(
        tenant_id=user_context.tenant_id,
        user_id=user_context.user_id,
        key_id=key_id,
        key_hash=secret_hash,
        name=name,
        roles=[r.value for r in user_context.roles],
        scopes=scopes or [],
        expires_at=datetime.utcnow() + timedelta(days=expires_days) if expires_days else None,
    )
    
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    
    return {
        "id": str(api_key.id),
        "key_id": key_id,
        "name": name,
        "full_key": full_key,  # Only returned once!
        "expires_at": api_key.expires_at,
    }


async def list_api_keys(
    user_context: UserContext,
    session: AsyncSession = Depends(get_session),
) -> List[dict]:
    """List user's API keys (without secrets)."""
    from app.models.api_key import ApiKey
    
    result = await session.execute(
        select(ApiKey).where(
            ApiKey.user_id == user_context.user_id,
            ApiKey.tenant_id == user_context.tenant_id,
        ).order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()
    
    return [
        {
            "id": str(k.id),
            "key_id": k.key_id,
            "name": k.name,
            "roles": k.roles,
            "scopes": k.scopes,
            "is_active": k.is_active,
            "last_used_at": k.last_used_at,
            "expires_at": k.expires_at,
            "created_at": k.created_at,
        }
        for k in keys
    ]


async def revoke_api_key(
    key_id: str,
    user_context: UserContext,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Revoke an API key."""
    from app.models.api_key import ApiKey
    
    result = await session.execute(
        select(ApiKey).where(
            ApiKey.key_id == key_id,
            ApiKey.tenant_id == user_context.tenant_id,
        )
    )
    api_key = result.scalar_one_or_none()
    
    if not api_key:
        raise HTTPException(404, "API key not found")
    
    api_key.is_active = False
    await session.commit()
    
    return {"message": "API key revoked"}