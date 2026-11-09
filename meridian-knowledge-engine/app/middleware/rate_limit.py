# app/middleware/rate_limit.py
"""Rate Limiting Middleware - Redis-based."""
import time
from typing import Optional
from fastapi import Request, HTTPException, Response
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis
from app.config import get_settings

settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-based rate limiting."""

    def __init__(self, app, redis_url: str = None):
        super().__init__(app)
        self.redis_url = redis_url or settings.REDIS_URL
        self._redis: Optional[redis.Redis] = None

    async def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._redis

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip for health checks
        if request.url.path in ["/health", "/health/ready"]:
            return await call_next(request)

        # Get client identifier (IP + Tenant)
        tenant = request.headers.get("X-Tenant-Slug", settings.DEFAULT_TENANT_SLUG)
        client_ip = request.client.host if request.client else "unknown"
        key = f"ratelimit:{tenant}:{client_ip}"

        r = await self._get_redis()

        # Sliding window rate limit (requests per minute)
        now = time.time()
        window_start = now - 60

        pipe = r.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, 60)
        results = await pipe.execute()

        current_count = results[1]

        # Determine limit based on tier (could be from user/tenant settings)
        limit = 300  # Default: 300 req/min

        if current_count > limit:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now + 60)),
                }
            )

        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - current_count))
        response.headers["X-RateLimit-Reset"] = str(int(now + 60))

        return response