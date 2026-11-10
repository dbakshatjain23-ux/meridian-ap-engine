# app/core/exceptions.py
"""Enterprise Exception Hierarchy - Structured error handling."""
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import traceback
import uuid
import logging

logger = logging.getLogger(__name__)


class ErrorCode(str):
    """Standardized error codes for API consumers."""
    # Authentication
    AUTH_REQUIRED = "AUTH_REQUIRED"
    AUTH_INVALID_TOKEN = "AUTH_INVALID_TOKEN"
    AUTH_EXPIRED_TOKEN = "AUTH_EXPIRED_TOKEN"
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_INSUFFICIENT_PERMISSIONS = "AUTH_INSUFFICIENT_PERMISSIONS"
    
    # Authorization
    FORBIDDEN = "FORBIDDEN"
    ROLE_REQUIRED = "ROLE_REQUIRED"
    TENANT_ISOLATION = "TENANT_ISOLATION"
    
    # Validation
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    
    # Resource
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    CONFLICT = "CONFLICT"
    GONE = "GONE"
    
    # Business Logic
    CALCULATION_ERROR = "CALCULATION_ERROR"
    INVALID_STATE = "INVALID_STATE"
    OPERATION_NOT_ALLOWED = "OPERATION_NOT_ALLOWED"
    
    # External
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    WEBHOOK_VERIFICATION_FAILED = "WEBHOOK_VERIFICATION_FAILED"
    INTEGRATION_ERROR = "INTEGRATION_ERROR"
    
    # System
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    
    # Compliance
    DATA_RETENTION_VIOLATION = "DATA_RETENTION_VIOLATION"
    PII_DETECTED = "PII_DETECTED"
    AUDIT_REQUIRED = "AUDIT_REQUIRED"


class ErrorDetail(BaseModel):
    """Structured error detail."""
    code: str
    message: str
    field: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Standardized error response format."""
    error: ErrorDetail
    request_id: str
    timestamp: str
    path: Optional[str] = None


class MeridianException(HTTPException):
    """Base exception with structured error response."""
    
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        field: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        self.code = code
        self.message = message
        self.field = field
        self.context = context or {}
        self.request_id = str(uuid.uuid4())[:8]
        
        detail = ErrorDetail(
            code=code,
            message=message,
            field=field,
            context=self.context,
        )
        
        super().__init__(status_code=status_code, detail=detail.model_dump())
    
    def to_response(self, request: Optional[Request] = None) -> JSONResponse:
        """Convert to JSON response."""
        error_response = ErrorResponse(
            error=ErrorDetail(
                code=self.code,
                message=self.message,
                field=self.field,
                context=self.context,
            ),
            request_id=self.request_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            path=request.url.path if request else None,
        )
        return JSONResponse(
            status_code=self.status_code,
            content=error_response.model_dump(),
            headers=self.headers,
        )


# Specific exception classes
class UnauthorizedException(MeridianException):
    def __init__(self, message: str = "Authentication required", **kwargs):
        super().__init__(
            code=ErrorCode.AUTH_REQUIRED,
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            **kwargs,
        )


class InvalidTokenException(MeridianException):
    def __init__(self, message: str = "Invalid or expired token", **kwargs):
        super().__init__(
            code=ErrorCode.AUTH_INVALID_TOKEN,
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            **kwargs,
        )


class ForbiddenException(MeridianException):
    def __init__(self, message: str = "Insufficient permissions", **kwargs):
        super().__init__(
            code=ErrorCode.FORBIDDEN,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            **kwargs,
        )


class ValidationException(MeridianException):
    def __init__(
        self,
        message: str = "Validation failed",
        errors: Optional[List[Dict[str, Any]]] = None,
        **kwargs,
    ):
        context = kwargs.get("context", {})
        if errors:
            context["validation_errors"] = errors
        super().__init__(
            code=ErrorCode.VALIDATION_ERROR,
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            context=context,
            **kwargs,
        )


class NotFoundException(MeridianException):
    def __init__(self, resource: str, identifier: str, **kwargs):
        super().__init__(
            code=ErrorCode.NOT_FOUND,
            message=f"{resource} not found: {identifier}",
            status_code=status.HTTP_404_NOT_FOUND,
            context={"resource": resource, "identifier": identifier},
            **kwargs,
        )


class ConflictException(MeridianException):
    def __init__(self, message: str, resource: str = "", **kwargs):
        super().__init__(
            code=ErrorCode.CONFLICT,
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            context={"resource": resource},
            **kwargs,
        )


class AlreadyExistsException(MeridianException):
    def __init__(self, resource: str, identifier: str, **kwargs):
        super().__init__(
            code=ErrorCode.ALREADY_EXISTS,
            message=f"{resource} already exists: {identifier}",
            status_code=status.HTTP_409_CONFLICT,
            context={"resource": resource, "identifier": identifier},
            **kwargs,
        )


class RateLimitedException(MeridianException):
    def __init__(self, retry_after: int, **kwargs):
        super().__init__(
            code=ErrorCode.RATE_LIMITED,
            message=f"Rate limit exceeded. Retry after {retry_after} seconds.",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
            context={"retry_after": retry_after},
            **kwargs,
        )


class InternalServerException(MeridianException):
    def __init__(self, message: str = "Internal server error", **kwargs):
        super().__init__(
            code=ErrorCode.INTERNAL_ERROR,
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            **kwargs,
        )


class ServiceUnavailableException(MeridianException):
    def __init__(self, service: str, **kwargs):
        super().__init__(
            code=ErrorCode.SERVICE_UNAVAILABLE,
            message=f"Service temporarily unavailable: {service}",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            context={"service": service},
            **kwargs,
        )


class CalculationException(MeridianException):
    def __init__(self, message: str, calculator: str = "", **kwargs):
        super().__init__(
            code=ErrorCode.CALCULATION_ERROR,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            context={"calculator": calculator},
            **kwargs,
        )


class PiiDetectedException(MeridianException):
    def __init__(self, pii_types: List[str], **kwargs):
        super().__init__(
            code=ErrorCode.PII_DETECTED,
            message="PII detected in input",
            status_code=status.HTTP_400_BAD_REQUEST,
            context={"pii_types": pii_types},
            **kwargs,
        )


class WebhookVerificationException(MeridianException):
    def __init__(self, provider: str, **kwargs):
        super().__init__(
            code=ErrorCode.WEBHOOK_VERIFICATION_FAILED,
            message=f"Webhook verification failed for {provider}",
            status_code=status.HTTP_401_UNAUTHORIZED,
            context={"provider": provider},
            **kwargs,
        )


# Exception handlers
async def meridian_exception_handler(request: Request, exc: MeridianException) -> JSONResponse:
    """Global handler for Meridian exceptions."""
    logger.warning(
        f"Request {exc.request_id}: {exc.code} - {exc.message}",
        extra={
            "request_id": exc.request_id,
            "code": exc.code,
            "path": request.url.path,
            "method": request.method,
            "context": exc.context,
        },
    )
    return exc.to_response(request)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handler for standard HTTP exceptions."""
    # Map standard HTTP exceptions to our format
    code_map = {
        400: ErrorCode.VALIDATION_ERROR,
        401: ErrorCode.AUTH_INVALID_TOKEN,
        403: ErrorCode.FORBIDDEN,
        404: ErrorCode.NOT_FOUND,
        409: ErrorCode.CONFLICT,
        422: ErrorCode.VALIDATION_ERROR,
        429: ErrorCode.RATE_LIMITED,
        500: ErrorCode.INTERNAL_ERROR,
        503: ErrorCode.SERVICE_UNAVAILABLE,
    }
    
    meridian_exc = MeridianException(
        code=code_map.get(exc.status_code, ErrorCode.INTERNAL_ERROR),
        message=exc.detail if isinstance(exc.detail, str) else "Request failed",
        status_code=exc.status_code,
        headers=exc.headers,
    )
    
    return meridian_exc.to_response(request)


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler for Pydantic validation errors."""
    from pydantic import ValidationError
    
    if isinstance(exc, ValidationError):
        errors = []
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            })
        
        meridian_exc = ValidationException(
            message="Request validation failed",
            errors=errors,
        )
        return meridian_exc.to_response(request)
    
    # Fallback
    return await internal_exception_handler(request, exc)


async def internal_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler for unhandled exceptions."""
    request_id = str(uuid.uuid4())[:8]
    
    logger.error(
        f"Unhandled exception {request_id}: {type(exc).__name__}: {exc}",
        exc_info=True,
        extra={
            "request_id": request_id,
            "path": request.url.path,
            "method": request.method,
        },
    )
    
    # Don't expose internal details in production
    from app.config import get_settings
    settings = get_settings()
    
    if settings.APP_ENV == "production":
        message = "An unexpected error occurred"
    else:
        message = f"{type(exc).__name__}: {str(exc)}"
    
    meridian_exc = InternalServerException(
        message=message,
        context={"request_id": request_id} if settings.APP_ENV != "production" else {},
    )
    
    return meridian_exc.to_response(request)


# Import at bottom to avoid circular imports
from datetime import datetime
import secrets