# app/middleware/logging.py
"""Structured JSON Logging Middleware."""
import json
import time
import uuid
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import get_settings

settings = get_settings()


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured request/response logging."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
        start_time = time.time()

        # Add request ID to request state
        request.state.request_id = request_id

        # Log request
        log_data = {
            "timestamp": time.time(),
            "level": "INFO",
            "logger": "http.request",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query": str(request.query_params),
            "client_ip": request.client.host if request.client else None,
            "tenant": request.headers.get("X-Tenant-Slug"),
            "user_agent": request.headers.get("User-Agent"),
        }

        # Don't log request body (may contain PII)
        print(json.dumps(log_data))

        try:
            response = await call_next(request)
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_log = {
                "timestamp": time.time(),
                "level": "ERROR",
                "logger": "http.error",
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "error": str(e),
                "duration_ms": duration_ms,
            }
            print(json.dumps(error_log))
            raise

        duration_ms = int((time.time() - start_time) * 1000)

        # Log response
        response_log = {
            "timestamp": time.time(),
            "level": "INFO",
            "logger": "http.response",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        }
        print(json.dumps(response_log))

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response