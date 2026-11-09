# app/config.py
"""Application configuration using Pydantic Settings."""
from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ============================================================
    # CORE APPLICATION
    # ============================================================
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    WORKERS: int = 4
    LOG_LEVEL: str = "info"

    # ============================================================
    # DATABASE
    # ============================================================
    DATABASE_URL: str = Field(..., description="PostgreSQL connection string")
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # ============================================================
    # TENANCY
    # ============================================================
    DEFAULT_TENANT_SLUG: str = "meridian"

    # ============================================================
    # AUTHENTICATION
    # ============================================================
    JWT_SECRET_KEY: str = Field(..., min_length=64)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 60
    JWT_REFRESH_EXPIRY_DAYS: int = 7

    # ============================================================
    # LLM PROVIDER (OpenAI - GPT-4o-mini + GPT-4o)
    # ============================================================
    OPENAI_API_KEY: str = Field(..., description="OpenAI API key")
    OPENAI_MODEL_FAST: str = "gpt-4o-mini"      # Cheap, fast: triage, routing, structure repair, schema learning
    OPENAI_MODEL_STRONG: str = "gpt-4o"         # Strong reasoning: extraction, answer, verification
    LLM_CACHE_TTL_SECONDS: int = 3600
    LLM_MAX_RETRIES: int = 3

    # ============================================================
    # EMBEDDINGS & SEARCH (Local CPU)
    # ============================================================
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIM: int = 384
    EMBEDDING_BATCH_SIZE: int = 32
    RERANKER_MODEL: str = "BAAI/bge-reranker-base"
    RERANKER_TOP_K: int = 20
    RRF_K: int = 60

    # ============================================================
    # BACKGROUND WORKER (Postgres Queue)
    # ============================================================
    WORKER_CONCURRENCY: int = 4
    JOB_POLL_INTERVAL_MS: int = 1000
    JOB_MAX_ATTEMPTS: int = 3
    JOB_RETRY_BASE_DELAY_SECONDS: int = 30

    # ============================================================
    # LIVE CAPTURE CONNECTORS
    # ============================================================
    MICROSOFT_GRAPH_CLIENT_ID: Optional[str] = None
    MICROSOFT_GRAPH_CLIENT_SECRET: Optional[str] = None
    MICROSOFT_GRAPH_TENANT_ID: Optional[str] = None
    MICROSOFT_GRAPH_REDIRECT_URI: Optional[str] = None

    TEAMS_BOT_APP_ID: Optional[str] = None
    TEAMS_BOT_APP_PASSWORD: Optional[str] = None
    TEAMS_BOT_WEBHOOK_SECRET: Optional[str] = None

    ZOOM_ACCOUNT_ID: Optional[str] = None
    ZOOM_CLIENT_ID: Optional[str] = None
    ZOOM_CLIENT_SECRET: Optional[str] = None

    # ============================================================
    # FILE STORAGE (Cloudflare R2)
    # ============================================================
    R2_ENDPOINT: Optional[str] = None
    R2_ACCESS_KEY_ID: Optional[str] = None
    R2_SECRET_ACCESS_KEY: Optional[str] = None
    R2_BUCKET: str = "meridian-episodes"
    R2_PUBLIC_URL: Optional[str] = None

    # ============================================================
    # REDIS
    # ============================================================
    REDIS_URL: str = "redis://localhost:6379"

    # ============================================================
    # PII REDACTION
    # ============================================================
    PII_REDACTION_ENABLED: bool = True
    PII_PAN_REGEX: str = r"[A-Z]{5}[0-9]{4}[A-Z]{1}"
    PII_BANK_REGEX: str = r"[0-9]{9,18}"
    PII_AADHAAR_REGEX: str = r"[0-9]{4}\s?[0-9]{4}\s?[0-9]{4}"

    # ============================================================
    # SOP SYNC
    # ============================================================
    SHAREPOINT_SITE_URL: Optional[str] = None
    GITHUB_TOKEN: Optional[str] = None
    GITHUB_REPO: Optional[str] = None
    GITLAB_TOKEN: Optional[str] = None
    GITLAB_PROJECT: Optional[str] = None

    # ============================================================
    # FEATURE FLAGS
    # ============================================================
    ENABLE_LIVE_CONNECTORS: bool = False
    ENABLE_SOP_SYNC: bool = False
    ENABLE_MEETING_BOT: bool = False
    ENABLE_ERP_EMBED: bool = False
    ENABLE_TEAMS_APP: bool = False
    ENABLE_BROWSER_EXTENSION: bool = False
    SCHEMA_MODE: str = "learned"

    # ============================================================
    # MONITORING
    # ============================================================
    SENTRY_DSN: Optional[str] = None
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = None


@lru_cache
def get_settings() -> Settings:
    return Settings()