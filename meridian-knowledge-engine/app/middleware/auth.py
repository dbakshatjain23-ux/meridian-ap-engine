# app/middleware/auth.py
"""Authentication middleware - JWT + Tenant resolution."""
from typing import Optional
from uuid import UUID
from fastapi import Request, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.database import get_session
from app.store.users import UserRepository
from app.models.user import User

settings = get_settings()
security = HTTPBearer(auto_error=False)


async def get_tenant(
    x_tenant_slug: Optional[str] = Header(None, alias="X-Tenant-Slug"),
) -> str:
    """Extract tenant slug from header."""
    return x_tenant_slug or settings.DEFAULT_TENANT_SLUG


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    tenant_slug: str = Depends(get_tenant),
    session: AsyncSession = Depends(get_session),
) -> Optional[User]:
    """Validate JWT and return current user."""
    if not credentials:
        return None

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id = payload.get("sub")
        token_tenant = payload.get("tenant")

        if not user_id or token_tenant != tenant_slug:
            return None

        user_repo = UserRepository(session)
        user = await user_repo.get(UUID(user_id))
        if not user or not user.is_active or user.tenant_id != UUID(tenant_slug):
            return None

        return user

    except JWTError:
        return None


def require_auth(user: User = Depends(get_current_user)) -> User:
    """Dependency that requires authentication."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_role(*roles: str):
    """Dependency that requires specific role(s)."""
    def check_role(user: User = Depends(require_auth)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail=f"Required role: {', '.join(roles)}")
        return user
    return check_role


# Alias for backward compatibility
auth_middleware = get_current_user