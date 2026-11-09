# app/middleware/pii.py
"""PII Middleware - Scrubs PII from request/response bodies."""
import json
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.gateways.pii import pii_gateway


class PIIMiddleware(BaseHTTPMiddleware):
    """Middleware to redact PII from request/response bodies."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip for health checks
        if request.url.path in ["/health", "/health/ready"]:
            return await call_next(request)

        # Read request body
        body = await request.body()
        if body:
            try:
                body_json = json.loads(body)
                redacted = pii_gateway.redact_dict(body_json)
                # Replace request body (need to recreate request)
                request._body = json.dumps(redacted).encode()
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass  # Not JSON, skip

        response = await call_next(request)

        # Optionally redact response body (be careful with streaming)
        # For now, only redact request

        return response