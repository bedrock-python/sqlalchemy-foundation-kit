"""Shared fixtures for integration tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio

try:
    import docker
    from docker.errors import DockerException
except ImportError:
    docker = None  # type: ignore[assignment]
    DockerException = Exception  # type: ignore[assignment, misc]

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

try:
    from testcontainers.postgres import PostgresContainer

    HAS_TESTCONTAINERS = True
except ImportError:
    PostgresContainer = object  # type: ignore[assignment, misc]
    HAS_TESTCONTAINERS = False

from tests.integration.models import Base


def is_docker_available() -> bool:
    """Check if Docker is available."""
    if docker is None:
        return False
    try:
        client = docker.from_env()
        client.version()
        return True
    except (DockerException, Exception):
        return False


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    """Start PostgreSQL container once for entire test session."""
    if not HAS_TESTCONTAINERS:
        pytest.skip("testcontainers is not installed")

    if not is_docker_available():
        pytest.skip("Docker is not available")

    with PostgresContainer("postgres:17-alpine") as postgres:
        yield postgres


@pytest_asyncio.fixture(scope="session")
async def db_engine(postgres_container: PostgresContainer) -> AsyncGenerator[AsyncEngine, None]:
    """Create async database engine once for entire test session."""
    url = postgres_container.get_connection_url()
    if "://" in url:
        _scheme, rest = url.split("://", 1)
        url = f"postgresql+asyncpg://{rest}"

    engine = create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

    # Create tables once per session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(autouse=True, scope="function")
async def cleanup_db(db_engine: AsyncEngine) -> None:
    """Truncate all tables before each test."""
    async with db_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE'))


@pytest_asyncio.fixture
async def async_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create async database session for testing."""
    async_session_maker = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with async_session_maker() as session:
        yield session


@pytest_asyncio.fixture(scope="session")
async def async_session_factory(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create async session factory once for entire test session."""
    return async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
