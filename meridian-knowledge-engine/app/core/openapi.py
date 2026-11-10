# app/core/openapi.py
"""OpenAPI Documentation - Enterprise API documentation."""
from typing import Dict, Any, List, Optional
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import HTMLResponse

from app.config import get_settings
from app.core.auth.rbac import Permission, Role

settings = get_settings()


def custom_openapi(app: FastAPI) -> Dict[str, Any]:
    """Generate custom OpenAPI schema with enterprise extensions."""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="Meridian AP Knowledge Engine API",
        version="1.0.0",
        description="""
# Meridian Accounts Payable Knowledge Engine

Enterprise-grade hybrid RAG system for 120-person AP department.

## Features
- **Deterministic Calculators**: 6 AP-specific calculators (Price Variance, TDS, MSME, E-Invoice, Pharma QA, Infra NO_GRN)
- **Hybrid RAG Pipeline**: 5-Tier Parser → Structure Repair → Entity/Topic/Fact Extraction → Authority Ranking → Conflict Detection → Graph Writer
- **3-Lane Router**: Computable / Retrieval / Refused
- **4-Check Verifier**: Numbers Sourced / Logic Valid / Calculations Match / No Hallucination
- **Live Capture**: Email (IMAP/Graph), Teams Bot, Meeting Bot (Teams/Zoom/Meet), Drive Watcher (OneDrive/SharePoint)
- **Real-time PII Redaction**: 13 Indian patterns (PAN, Aadhaar, GSTIN, IFSC, etc.)
- **Speaker Diarization**: pyannote.audio for meeting transcripts

## Authentication
- **JWT Bearer Tokens**: Short-lived access tokens (15min) + refresh tokens (7 days)
- **API Keys**: Long-lived keys for service-to-service communication
- **Webhook Signatures**: HMAC verification for Microsoft Graph, Teams, etc.

## Authorization
Role-Based Access Control (RBAC) with 12 predefined roles:
- **Super Admin**: Full system access
- **Tenant Admin**: Full tenant access
- **AP Manager**: AP operations + team management
- **AP Analyst**: Read + query + export
- **AP Clerk**: Document upload + basic queries
- **AP Auditor**: Read-only + audit logs
- **Developer**: API + webhook + integration access
- **Integration Engineer**: Webhook + API key management
- **Data Engineer**: Bulk operations + export
- **Viewer**: Read-only access
- **Report Viewer**: Read + export
- **API Client**: Programmatic access

## Rate Limiting
| Tier | Requests/Minute |
|------|----------------|
| Anonymous | 60 |
| Authenticated | 300 |
| Premium (Admin) | 1,000 |
| API Key | 5,000 |
| Webhook | 10,000 |

Endpoint-specific limits apply for sensitive operations.

## Error Handling
All errors follow RFC 7807 Problem Details format:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "field": "email",
    "context": {...}
  },
  "request_id": "abc123",
  "timestamp": "2026-01-15T10:30:00Z",
  "path": "/api/v1/episodes"
}
```

## Webhooks
Supported providers:
- **Microsoft Graph**: Email, Drive, Teams
- **Teams Bot Framework**: Messages, reactions
- **Zoom/Meet**: Meeting events (via webhook)
- **Custom**: HMAC-SHA256 signed payloads

## Compliance
- **India DPDP Act 2023**: Data localization, consent management, right to erasure
- **GDPR**: Data portability, right to access, DPO contact
- **SOC 2 Type II**: Audit logging, access controls, encryption
- **ISO 27001**: Information security management

## Support
- **Enterprise**: 24/7 SLA, dedicated support
- **Professional**: Business hours, ticket-based
- **Community**: GitHub issues, documentation
        """,
        routes=app.routes,
        tags=[
            {"name": "Authentication", "description": "Login, token management, API keys"},
            {"name": "Episodes", "description": "Document ingestion and management"},
            {"name": "Queries", "description": "Natural language querying with hybrid RAG"},
            {"name": "Calculators", "description": "Deterministic AP calculators"},
            {"name": "Webhooks", "description": "Live capture webhooks"},
            {"name": "Workers", "description": "Background job monitoring"},
            {"name": "Admin", "description": "Tenant and user management"},
            {"name": "Health", "description": "System health and metrics"},
        ],
    )
    
    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT access token (15min expiry)",
        },
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "API key for service-to-service auth",
        },
        "WebhookSignature": {
            "type": "apiKey",
            "in": "header",
            "name": "X-Webhook-Signature",
            "description": "HMAC signature for webhook verification",
        },
    }
    
    # Add global security requirement
    openapi_schema["security"] = [
        {"BearerAuth": []},
        {"ApiKeyAuth": []},
    ]
    
    # Add permission metadata to operations
    for path, methods in openapi_schema["paths"].items():
        for method, operation in methods.items():
            # Add x-permissions extension
            required_perms = _get_required_permissions(path, method)
            if required_perms:
                operation["x-permissions"] = [p.value for p in required_perms]
            
            # Add x-roles extension
            required_roles = _get_required_roles(path, method)
            if required_roles:
                operation["x-roles"] = [r.value for r in required_roles]
            
            # Add rate limit info
            rate_limit = _get_rate_limit_info(path)
            if rate_limit:
                operation["x-rate-limit"] = rate_limit
    
    # Add custom extensions
    openapi_schema["x-enterprise"] = {
        "version": "1.0.0",
        "support_tiers": ["community", "professional", "enterprise"],
        "compliance": ["DPDP-2023", "GDPR", "SOC2-Type-II", "ISO-27001"],
        "data_residency": ["IN-MUM", "IN-DEL", "US-EAST", "EU-WEST"],
        "sla": {
            "enterprise": "99.99%",
            "professional": "99.9%",
            "community": "best-effort",
        },
    }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


def _get_required_permissions(path: str, method: str) -> List[Permission]:
    """Map endpoints to required permissions."""
    from app.core.auth.rbac import Permission
    
    perm_map = {
        # Auth
        ("POST", "/api/v1/auth/login"): [],
        ("POST", "/api/v1/auth/refresh"): [],
        ("POST", "/api/v1/auth/logout"): [],
        
        # Episodes
        ("POST", "/api/v1/episodes/upload"): [Permission.DOCUMENT_UPLOAD],
        ("GET", "/api/v1/episodes/"): [Permission.EPISODE_LIST],
        ("GET", "/api/v1/episodes/{id}"): [Permission.EPISODE_READ],
        ("GET", "/api/v1/episodes/{id}/status"): [Permission.EPISODE_READ],
        ("POST", "/api/v1/episodes/{id}/reprocess"): [Permission.EPISODE_REPROCESS],
        ("DELETE", "/api/v1/episodes/{id}"): [Permission.EPISODE_DELETE],
        
        # Queries
        ("POST", "/api/v1/query"): [Permission.QUERY_EXECUTE],
        ("GET", "/api/v1/query/history"): [Permission.QUERY_HISTORY],
        ("POST", "/api/v1/query/export"): [Permission.QUERY_EXPORT],
        
        # Calculators
        ("POST", "/api/v1/calculators/execute"): [Permission.CALCULATOR_EXECUTE],
        ("GET", "/api/v1/calculators/"): [Permission.CALCULATOR_EXECUTE],
        
        # Webhooks
        ("POST", "/api/v1/episodes/email/webhook"): [Permission.WEBHOOK_REGISTER],
        ("POST", "/api/v1/episodes/teams/webhook"): [Permission.WEBHOOK_REGISTER],
        ("POST", "/api/v1/episodes/meeting/start"): [Permission.WEBHOOK_REGISTER],
        
        # Workers
        ("GET", "/api/v1/workers/health"): [Permission.WORKER_VIEW],
        ("GET", "/api/v1/workers/queue/stats"): [Permission.QUEUE_MANAGE],
        ("POST", "/api/v1/workers/queue/retry-failed"): [Permission.QUEUE_MANAGE],
        ("DELETE", "/api/v1/workers/queue/clear-failed"): [Permission.QUEUE_MANAGE],
        
        # Admin
        ("GET", "/api/v1/admin/users"): [Permission.USER_MANAGE],
        ("POST", "/api/v1/admin/users"): [Permission.USER_MANAGE],
        ("PATCH", "/api/v1/admin/users/{id}"): [Permission.USER_MANAGE],
        ("DELETE", "/api/v1/admin/users/{id}"): [Permission.USER_MANAGE],
        ("GET", "/api/v1/admin/roles"): [Permission.ROLE_MANAGE],
        ("POST", "/api/v1/admin/roles"): [Permission.ROLE_MANAGE],
        ("GET", "/api/v1/admin/settings"): [Permission.SETTINGS_MANAGE],
        ("PATCH", "/api/v1/admin/settings"): [Permission.SETTINGS_MANAGE],
        ("GET", "/api/v1/admin/audit"): [Permission.AUDIT_VIEW],
        
        # API Keys
        ("POST", "/api/v1/api-keys"): [Permission.API_KEY_CREATE],
        ("GET", "/api/v1/api-keys"): [Permission.API_KEY_VIEW],
        ("DELETE", "/api/v1/api-keys/{key_id}"): [Permission.API_KEY_REVOKE],
    }
    
    return perm_map.get((method.upper(), path), [])


def _get_required_roles(path: str, method: str) -> List[Role]:
    """Map endpoints to required roles."""
    from app.core.auth.rbac import Role
    
    role_map = {
        ("DELETE", "/api/v1/episodes/{id}"): [Role.TENANT_ADMIN, Role.SUPER_ADMIN],
        ("GET", "/api/v1/admin/"): [Role.TENANT_ADMIN, Role.SUPER_ADMIN],
        ("POST", "/api/v1/admin/"): [Role.TENANT_ADMIN, Role.SUPER_ADMIN],
        ("PATCH", "/api/v1/admin/"): [Role.TENANT_ADMIN, Role.SUPER_ADMIN],
        ("POST", "/api/v1/workers/queue/retry-failed"): [Role.AP_MANAGER, Role.TENANT_ADMIN, Role.SUPER_ADMIN],
    }
    
    return role_map.get((method.upper(), path), [])


def _get_rate_limit_info(path: str) -> Optional[Dict[str, Any]]:
    """Get rate limit info for endpoint."""
    from app.middleware.rate_limit import ENDPOINT_LIMITS, DEFAULT_LIMITS
    
    # Check endpoint-specific
    for endpoint, config in ENDPOINT_LIMITS.items():
        if path.startswith(endpoint):
            return {
                "requests": config.requests,
                "window_seconds": config.window_seconds,
                "tier_specific": True,
            }
    
    # Return default info
    return {
        "requests": DEFAULT_LIMITS["authenticated"].requests,
        "window_seconds": DEFAULT_LIMITS["authenticated"].window_seconds,
        "tier_specific": False,
    }


def setup_docs(app: FastAPI):
    """Setup custom docs endpoints."""
    
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui():
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title="Meridian AP Knowledge Engine - API Docs",
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
            swagger_ui_parameters={
                "persistAuthorization": True,
                "displayRequestDuration": True,
                "filter": True,
                "showExtensions": True,
                "showCommonExtensions": True,
            },
        )
    
    @app.get("/redoc", include_in_schema=False)
    async def redoc_ui():
        return get_redoc_html(
            openapi_url="/openapi.json",
            title="Meridian AP Knowledge Engine - ReDoc",
            redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
        )
    
    @app.get("/openapi.json", include_in_schema=False)
    async def openapi_json():
        return custom_openapi(app)