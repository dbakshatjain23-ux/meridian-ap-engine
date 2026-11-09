# app/main.py
"""FastAPI Application Factory."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import init_db, close_db
from app.middleware import (
    logging_middleware,
    pii_middleware,
    rate_limit_middleware,
    auth_middleware,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown."""
    # Startup
    await init_db()
    print("Database initialized")

    yield

    # Shutdown
    await close_db()
    print("Database connections closed")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Meridian Knowledge Engine",
        description="Generic Dual-Clock Temporal Knowledge Engine + Industry Plug-ins",
        version="0.1.0",
        docs_url="/docs" if settings.APP_ENV != "production" else None,
        redoc_url="/redoc" if settings.APP_ENV != "production" else None,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.APP_ENV == "development" else ["https://app.meridian-engine.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware (order matters - inner to outer)
    app.add_middleware(logging_middleware.LoggingMiddleware)
    app.add_middleware(pii_middleware.PIIMiddleware)
    # app.add_middleware(rate_limit_middleware.RateLimitMiddleware)  # Enable when Redis available

    # Include routers
    from app.api.routes import (
        query, tacit, episodes, facts, conflicts,
        sop_sync, delivery, admin, health
    )

    app.include_router(health.router, tags=["Health"])
    app.include_router(query.router, prefix="/v1", tags=["Query"])
    app.include_router(tacit.router, prefix="/v1", tags=["Tacit"])
    app.include_router(episodes.router, prefix="/v1", tags=["Episodes"])
    app.include_router(facts.router, prefix="/v1", tags=["Facts"])
    app.include_router(conflicts.router, prefix="/v1", tags=["Conflicts"])
    app.include_router(sop_sync.router, prefix="/v1", tags=["SOP Sync"])
    app.include_router(delivery.router, prefix="/v1", tags=["Delivery"])
    app.include_router(admin.router, prefix="/v1/admin", tags=["Admin"])

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        workers=settings.WORKERS if settings.APP_ENV == "production" else 1,
        reload=settings.APP_ENV == "development",
    )