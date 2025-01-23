import asyncio
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from {{cookiecutter.package_name}}.core.config import get_settings
from {{cookiecutter.package_name}}.db import async_session, init_db
from {{cookiecutter.package_name}}.main import app

settings = get_settings()


# Use an in-memory database for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    
    await engine.dispose()

@pytest.fixture(scope="function")
async def test_session(test_engine):
    """Create a test database session."""
    # Drop all tables before creating
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    
    async_session_maker = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session_maker() as session:
        yield session

@pytest.fixture
async def client():
    """Create a test client."""
    async def override_get_db():
        """Override the database dependency."""
        try:
            async with async_session() as session:
                yield session
        except Exception as e:
            print(f"Database error: {e}")
            raise
    
    app.dependency_overrides = {}
    
    async with AsyncClient(
        base_url="http://test", 
        transport=ASGITransport(app=app)
    ) as ac:
        yield ac

@pytest.fixture
def sync_client():
    """Create a synchronous test client."""
    return TestClient(app)
