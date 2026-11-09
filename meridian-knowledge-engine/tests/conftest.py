"""Test configuration and fixtures."""
import pytest
import pytest_asyncio
from app.database import init_db, close_db


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    """Initialize database for tests."""
    await init_db()
    yield
    await close_db()