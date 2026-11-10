"""Test configuration and fixtures."""
import os
import pytest
import pytest_asyncio

# Set required environment variables before any imports
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only-min-64-characters-long-enough-for-validation")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-testing")


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()