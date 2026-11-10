# app/core/auth/jwt_handler.py
"""JWT Token Handler - Enterprise-grade token management."""
import time
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.config import get_settings
from app.core.auth.rbac import Role, Permission, UserContext, ROLE_PERMISSIONS

settings = get_settings()

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenType(str, Enum):
    ACCESS = "access"
    REFRESH = "refresh"
    API_KEY = "api_key"
    WEBHOOK = "webhook"
    INVITATION = "invitation"
    PASSWORD_RESET = "password_reset"


@dataclass
class TokenPayload:
    """Decoded token payload."""
    sub: str  # user_id
    tenant_id: str
    roles: List[str]
    permissions: List[str]
    token_type: TokenType
    iat: int
    exp: int
    jti: str  # JWT ID for revocation
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = None


@dataclass
class TokenPair:
    """Access and refresh token pair."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900  # 15 minutes
    refresh_expires_in: int = 604800  # 7 days


class JWTHandler:
    """Enterprise JWT token handler with rotation and revocation."""
    
    def __init__(
        self,
        secret_key: Optional[str] = None,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 15,
        refresh_token_expire_days: int = 7,
        issuer: str = "meridian-ap",
        audience: str = "meridian-api",
    ):
        self.secret_key = secret_key or settings.JWT_SECRET_KEY
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
        self.issuer = issuer
        self.audience = audience
        
        # Token blacklist (in production, use Redis)
        self._revoked_tokens: set = set()
        self._revoked_refresh_tokens: set = set()
    
    def _generate_jti(self) -> str:
        """Generate unique JWT ID."""
        return secrets.token_urlsafe(16)
    
    def _get_permissions_for_roles(self, roles: List[Role]) -> List[str]:
        """Aggregate permissions from roles."""
        perms = set()
        for role in roles:
            perms.update(ROLE_PERMISSIONS.get(role, set()))
        return [p.value for p in perms]
    
    def create_access_token(
        self,
        user_id: str,
        tenant_id: str,
        roles: List[Role],
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create short-lived access token."""
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=self.access_token_expire_minutes)
        
        payload = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "roles": [r.value for r in roles],
            "permissions": self._get_permissions_for_roles(roles),
            "token_type": TokenType.ACCESS.value,
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "jti": self._generate_jti(),
            "iss": self.issuer,
            "aud": self.audience,
        }
        
        if session_id:
            payload["session_id"] = session_id
        if metadata:
            payload["metadata"] = metadata
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(
        self,
        user_id: str,
        tenant_id: str,
        roles: List[Role],
        session_id: Optional[str] = None,
    ) -> str:
        """Create long-lived refresh token."""
        now = datetime.now(timezone.utc)
        expire = now + timedelta(days=self.refresh_token_expire_days)
        
        payload = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "roles": [r.value for r in roles],
            "permissions": self._get_permissions_for_roles(roles),
            "token_type": TokenType.REFRESH.value,
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "jti": self._generate_jti(),
            "iss": self.issuer,
            "aud": self.audience,
        }
        
        if session_id:
            payload["session_id"] = session_id
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def create_token_pair(
        self,
        user_id: str,
        tenant_id: str,
        roles: List[Role],
        session_id: Optional[str] = None,
    ) -> TokenPair:
        """Create access + refresh token pair."""
        access = self.create_access_token(user_id, tenant_id, roles, session_id)
        refresh = self.create_refresh_token(user_id, tenant_id, roles, session_id)
        
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            expires_in=self.access_token_expire_minutes * 60,
            refresh_expires_in=self.refresh_token_expire_days * 86400,
        )
    
    def create_api_key(
        self,
        user_id: str,
        tenant_id: str,
        roles: List[Role],
        name: str,
        expires_days: Optional[int] = None,
        scopes: Optional[List[str]] = None,
    ) -> tuple[str, str]:
        """
        Create API key (prefix + secret).
        Returns: (api_key_id, full_api_key)
        """
        # Generate key components
        prefix = "mk_live_"  # Meridian Key Live
        key_id = secrets.token_urlsafe(8)
        secret = secrets.token_urlsafe(32)
        full_key = f"{prefix}{key_id}.{secret}"
        
        now = datetime.now(timezone.utc)
        if expires_days:
            expire = now + timedelta(days=expires_days)
        else:
            expire = now + timedelta(days=365)  # 1 year default
        
        payload = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "roles": [r.value for r in roles],
            "permissions": scopes or self._get_permissions_for_roles(roles),
            "token_type": TokenType.API_KEY.value,
            "key_name": name,
            "key_id": key_id,
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "jti": self._generate_jti(),
            "iss": self.issuer,
            "aud": self.audience,
        }
        
        # In production, store hashed secret in DB
        # Return the full key (only shown once)
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return key_id, full_key
    
    def verify_token(self, token: str, expected_type: Optional[TokenType] = None) -> TokenPayload:
        """Verify and decode token."""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                audience=self.audience,
                issuer=self.issuer,
            )
        except JWTError as e:
            from app.core.exceptions import UnauthorizedException
            raise UnauthorizedException(f"Invalid token: {str(e)}")
        
        # Check token type
        token_type = TokenType(payload.get("token_type", "access"))
        if expected_type and token_type != expected_type:
            from app.core.exceptions import UnauthorizedException
            raise UnauthorizedException(f"Expected {expected_type.value} token, got {token_type.value}")
        
        # Check revocation
        jti = payload.get("jti")
        if jti in self._revoked_tokens:
            from app.core.exceptions import UnauthorizedException
            raise UnauthorizedException("Token has been revoked")
        
        if token_type == TokenType.REFRESH and jti in self._revoked_refresh_tokens:
            from app.core.exceptions import UnauthorizedException
            raise UnauthorizedException("Refresh token has been revoked")
        
        return TokenPayload(
            sub=payload["sub"],
            tenant_id=payload["tenant_id"],
            roles=[Role(r) for r in payload.get("roles", [])],
            permissions=payload.get("permissions", []),
            token_type=token_type,
            iat=payload["iat"],
            exp=payload["exp"],
            jti=payload["jti"],
            session_id=payload.get("session_id"),
            metadata=payload.get("metadata"),
        )
    
    def refresh_access_token(self, refresh_token: str) -> TokenPair:
        """Rotate refresh token and create new access token."""
        payload = self.verify_token(refresh_token, TokenType.REFRESH)
        
        # Revoke old refresh token
        self.revoke_refresh_token(payload.jti)
        
        # Create new token pair
        roles = payload.roles
        return self.create_token_pair(
            user_id=payload.sub,
            tenant_id=payload.tenant_id,
            roles=roles,
            session_id=payload.session_id,
        )
    
    def revoke_token(self, jti: str):
        """Revoke access token (add to blacklist)."""
        self._revoked_tokens.add(jti)
    
    def revoke_refresh_token(self, jti: str):
        """Revoke refresh token."""
        self._revoked_refresh_tokens.add(jti)
    
    def revoke_all_user_tokens(self, user_id: str):
        """Revoke all tokens for a user (requires token store in production)."""
        # In production, query token store and revoke all user's tokens
        pass
    
    def hash_secret(self, secret: str) -> str:
        """Hash a secret for storage."""
        return pwd_context.hash(secret)
    
    def verify_secret(self, plain: str, hashed: str) -> bool:
        """Verify a secret against hash."""
        return pwd_context.verify(plain, hashed)
    
    def extract_token_from_header(self, authorization: Optional[str]) -> Optional[str]:
        """Extract Bearer token from Authorization header."""
        if not authorization:
            return None
        
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        
        return parts[1]
    
    def extract_api_key(self, authorization: Optional[str]) -> Optional[tuple[str, str]]:
        """Extract API key from Authorization header (ApiKey prefix)."""
        if not authorization:
            return None
        
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "apikey":
            return None
        
        # Format: mk_live_<key_id>.<secret>
        key = parts[1]
        if not key.startswith("mk_live_"):
            return None
        
        try:
            key_id_part, secret = key.split(".", 1)
            key_id = key_id_part[len("mk_live_"):]
            return key_id, secret
        except ValueError:
            return None


# Global JWT handler
_jwt_handler: Optional[JWTHandler] = None


def get_jwt_handler() -> JWTHandler:
    """Get global JWT handler."""
    global _jwt_handler
    if _jwt_handler is None:
        _jwt_handler = JWTHandler()
    return _jwt_handler