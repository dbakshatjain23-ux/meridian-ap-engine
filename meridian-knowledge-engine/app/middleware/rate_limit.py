# app/middleware/rate_limit.py
"""Rate Limiting Middleware - Multi-tenant, multi-tier rate limiting."""
import time
import hashlib
from typing import Optional, Dict, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import get_settings
from app.core.exceptions import RateLimitedException, ErrorCode
from app.middleware.auth import get_optional_user_context

settings = get_settings()


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests: int
    window_seconds: int
    block_duration_seconds: int = 300  # 5 minutes default block


# Default rate limit tiers
DEFAULT_LIMITS = {
    "anonymous": RateLimitConfig(requests=60, window_seconds=60),      # 60/min
    "authenticated": RateLimitConfig(requests=300, window_seconds=60),  # 300/min
    "premium": RateLimitConfig(requests=1000, window_seconds=60),       # 1000/min
    "api_key": RateLimitConfig(requests=5000, window_seconds=60),       # 5000/min
    "webhook": RateLimitConfig(requests=10000, window_seconds=60),      # 10000/min
}

# Per-endpoint overrides
ENDPOINT_LIMITS = {
    "/api/v1/auth/login": RateLimitConfig(requests=10, window_seconds=300),      # 10/5min
    "/api/v1/auth/register": RateLimitConfig(requests=5, window_seconds=300),    # 5/5min
    "/api/v1/episodes/upload": RateLimitConfig(requests=50, window_seconds=60),  # 50/min
    "/api/v1/query": RateLimitConfig(requests=100, window_seconds=60),           # 100/min
    "/api/v1/webhooks/": RateLimitConfig(requests=1000, window_seconds=60),      # 1000/min
}


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting."""
    tokens: float
    last_refill: float
    blocked_until: float = 0
    request_count: int = 0


class InMemoryRateLimiter:
    """In-memory rate limiter (use Redis in production)."""
    
    def __init__(self):
        self.buckets: Dict[str, RateLimitBucket] = defaultdict(
            lambda: RateLimitBucket(tokens=0, last_refill=time.time())
        )
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()
    
    def _get_client_key(self, request: Request, user_context: Optional[object]) -> str:
        """Generate rate limit key from request and user context."""
        # Priority: user_id > api_key > ip
        if user_context and hasattr(user_context, 'user_id'):
            return f"user:{user_context.user_id}"
        
        # Check for API key
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"apikey:{hashlib.sha256(api_key.encode()).hexdigest()[:16]}"
        
        # Fall back to IP
        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        return f"ip:{client_ip}"
    
    def _get_tier(self, user_context: Optional[object]) -> str:
        """Determine rate limit tier."""
        if not user_context:
            return "anonymous"
        
        # Check for API key auth
        if hasattr(user_context, 'attributes') and user_context.attributes.get('api_key_id'):
            return "api_key"
        
        # Check for premium role
        if hasattr(user_context, 'roles'):
            from app.core.auth.rbac import Role
            if Role.TENANT_ADMIN in user_context.roles or Role.SUPER_ADMIN in user_context.roles:
                return "premium"
        
        return "authenticated"
    
    def _get_limit_config(self, tier: str, path: str) -> RateLimitConfig:
        """Get rate limit config for tier and path."""
        # Check endpoint-specific limits first
        for endpoint_prefix, config in ENDPOINT_LIMITS.items():
            if path.startswith(endpoint_prefix):
                return config
        
        # Fall back to tier defaults
        return DEFAULT_LIMITS.get(tier, DEFAULT_LIMITS["anonymous"])
    
    def _refill_bucket(self, bucket: RateLimitBucket, config: RateLimitConfig) -> None:
        """Refill token bucket based on elapsed time."""
        now = time.time()
        elapsed = now - bucket.last_refill
        
        if elapsed >= config.window_seconds:
            # Full refill
            bucket.tokens = config.requests
            bucket.last_refill = now
            bucket.request_count = 0
        else:
            # Proportional refill
            refill_rate = config.requests / config.window_seconds
            bucket.tokens = min(config.requests, bucket.tokens + elapsed * refill_rate)
    
    async def check_rate_limit(
        self,
        request: Request,
        user_context: Optional[object] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request should be rate limited.
        Returns: (allowed, rate_limit_info)
        """
        # Cleanup old buckets periodically
        if time.time() - self._last_cleanup > self._cleanup_interval:
            self._cleanup()
        
        client_key = self._get_client_key(request, user_context)
        tier = self._get_tier(user_context)
        config = self._get_limit_config(tier, request.url.path)
        
        bucket = self.buckets[client_key]
        
        # Check if blocked
        if bucket.blocked_until > time.time():
            retry_after = int(bucket.blocked_until - time.time()) + 1
            return False, {
                "allowed": False,
                "retry_after": retry_after,
                "limit": config.requests,
                "remaining": 0,
                "reset": int(bucket.blocked_until),
                "tier": tier,
            }
        
        # Refill bucket
        self._refill_bucket(bucket, config)
        
        # Check if tokens available
        if bucket.tokens >= 1:
            bucket.tokens -= 1
            bucket.request_count += 1
            
            return True, {
                "allowed": True,
                "limit": config.requests,
                "remaining": int(bucket.tokens),
                "reset": int(bucket.last_refill + config.window_seconds),
                "tier": tier,
            }
        
        # No tokens - rate limited
        retry_after = int((1 - bucket.tokens) * config.window_seconds / config.requests) + 1
        
        # Block if repeated violations
        if bucket.request_count > config.requests * 2:
            bucket.blocked_until = time.time() + config.block_duration_seconds
        
        return False, {
            "allowed": False,
            "retry_after": retry_after,
            "limit": config.requests,
            "remaining": 0,
            "reset": int(bucket.last_refill + config.window_seconds),
            "tier": tier,
        }
    
    def _cleanup(self) -> None:
        """Remove expired buckets."""
        now = time.time()
        expired_keys = [
            k for k, b in self.buckets.items()
            if b.last_refill < now - 3600 and b.blocked_until < now  # 1 hour old
        ]
        for k in expired_keys:
            del self.buckets[k]
        self._last_cleanup = time.time()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        return {
            "total_buckets": len(self.buckets),
            "blocked_buckets": sum(1 for b in self.buckets.values() if b.blocked_until > time.time()),
        }


# Global rate limiter instance
_rate_limiter: Optional[InMemoryRateLimiter] = None


def get_rate_limiter() -> InMemoryRateLimiter:
    """Get global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = InMemoryRateLimiter()
    return _rate_limiter


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting."""
    
    def __init__(self, app, rate_limiter: Optional[InMemoryRateLimiter] = None):
        super().__init__(app)
        self.rate_limiter = rate_limiter or get_rate_limiter()
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/healthz", "/ready", "/metrics"]:
            return await call_next(request)
        
        # Get user context (optional)
        user_context = None
        if hasattr(request.state, "user_context"):
            user_context = request.state.user_context
        
        # Check rate limit
        allowed, info = await self.rate_limiter.check_rate_limit(request, user_context)
        
        # Add rate limit headers
        headers = {
            "X-RateLimit-Limit": str(info["limit"]),
            "X-RateLimit-Remaining": str(info["remaining"]),
            "X-RateLimit-Reset": str(info["reset"]),
            "X-RateLimit-Tier": info["tier"],
        }
        
        if not info["allowed"]:
            # Rate limited
            headers["Retry-After"] = str(info["retry_after"])
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": ErrorCode.RATE_LIMITED,
                        "message": f"Rate limit exceeded. Retry after {info['retry_after']} seconds.",
                        "context": {
                            "retry_after": info["retry_after"],
                            "limit": info["limit"],
                            "tier": info["tier"],
                        },
                    },
                    "request_id": request.headers.get("X-Request-ID", "unknown"),
                },
                headers=headers,
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        for key, value in headers.items():
            response.headers[key] = value
        
        return response


# Dependency for manual rate limit checks
async def check_rate_limit(
    request: Request,
    user_context: Optional[object] = None,
    rate_limiter: InMemoryRateLimiter = Depends(get_rate_limiter),
) -> Dict[str, Any]:
    """Dependency to manually check rate limits."""
    allowed, info = await rate_limiter.check_rate_limit(request, user_context)
    if not allowed:
        raise RateLimitedException(info["retry_after"])
    return info