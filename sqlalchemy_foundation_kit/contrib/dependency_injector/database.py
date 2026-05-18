"""Database containers for dependency-injector."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...config import PostgresSettingsProtocol
from ...protocols import PostgresMetricsProtocol
from ...session import (
    DEFAULT_HEALTHCHECK_QUERY,
    DEFAULT_RETRY_CONFIG,
    AsyncSessionManager,
    RetryConfig,
    create_async_session_manager,
    retry_async_connection,
)
from ...uow import AsyncSQLAlchemyUnitOfWork, AsyncSQLAlchemyUowTransaction, AsyncUnitOfWork
from ._base import BaseDIContainer
from ._deps import providers

logger = logging.getLogger(__name__)


async def _create_session_manager_resource(
    postgres_config: PostgresSettingsProtocol,
    metrics: PostgresMetricsProtocol | None,
    healthcheck_query: str | None,
    retry_config: RetryConfig,
) -> AsyncIterator[AsyncSessionManager[AsyncSession]]:
    """Resource factory: build manager, run healthcheck, yield, then close."""
    manager = create_async_session_manager(postgres_config, metrics=metrics)

    if healthcheck_query is not None:
        query = healthcheck_query

        async def test_connection() -> None:
            async with manager.session_maker() as session:
                await session.execute(text(query))

        await retry_async_connection(
            connect_func=test_connection,
            service_name="PostgreSQL",
            config=retry_config,
        )

    try:
        yield manager
    finally:
        try:
            await manager.aclose()
            logger.info("Database session manager closed successfully")
        except SQLAlchemyError as e:
            logger.warning("Error closing database session manager: %s", e)


def _get_session_maker(
    session_manager: AsyncSessionManager[AsyncSession],
) -> async_sessionmaker[AsyncSession]:
    """Factory: extract session_maker from session_manager."""
    return session_manager.session_maker


def _create_uow(
    session_maker: async_sessionmaker[AsyncSession],
) -> AsyncUnitOfWork[AsyncSQLAlchemyUowTransaction]:
    """Factory: create Unit of Work from session_maker."""
    return AsyncSQLAlchemyUnitOfWork(session_maker, transaction_factory=AsyncSQLAlchemyUowTransaction)


class DatabaseContainer(BaseDIContainer):
    """Container for database dependencies.

    Provides:
        - ``session_manager``: Manages database connections and engine lifecycle.
        - ``session_maker``: Factory for creating database sessions.
        - ``uow``: Unit of Work for database transactions.

    Configuration:
        - ``postgres_config``: PostgreSQL configuration (``PostgresSettingsProtocol``).
        - ``metrics``: Optional metrics collector (``PostgresMetricsProtocol``).
        - ``healthcheck_query``: SQL executed at startup (default: ``"SELECT 1"``, ``None`` to skip).
        - ``retry_config``: Retry behavior for healthcheck (default: ``RetryConfig()``).
    """

    # Configuration
    postgres_config = providers.Dependency()  # type: ignore[misc,var-annotated]
    metrics = providers.Dependency(default=None)  # type: ignore[misc,var-annotated]

    # Healthcheck configuration
    healthcheck_query = providers.Object(DEFAULT_HEALTHCHECK_QUERY)  # type: ignore[misc,var-annotated]
    retry_config = providers.Object(DEFAULT_RETRY_CONFIG)  # type: ignore[misc,var-annotated]

    # Session manager (resource: handles lifecycle)
    session_manager = providers.Resource(  # type: ignore[misc,var-annotated]
        _create_session_manager_resource,
        postgres_config=postgres_config,
        metrics=metrics,
        healthcheck_query=healthcheck_query,
        retry_config=retry_config,
    )

    # Session maker
    session_maker = providers.Factory(  # type: ignore[misc,var-annotated]
        _get_session_maker,
        session_manager=session_manager,
    )

    # Unit of Work
    uow = providers.Singleton(  # type: ignore[misc,var-annotated]
        _create_uow,
        session_maker=session_maker,
    )


class AsyncDatabaseResourceProvider:
    """Helper class for managing database session manager lifecycle.

    Use this when you need manual control over session manager lifecycle —
    for example in tests or when not using dependency-injector containers.

    Examples:
        >>> provider = AsyncDatabaseResourceProvider(config, metrics)
        >>> manager = await provider.start()
        >>> # Use manager...
        >>> await provider.stop()
    """

    def __init__(
        self,
        postgres_config: PostgresSettingsProtocol,
        metrics: PostgresMetricsProtocol | None = None,
        healthcheck_query: str | None = DEFAULT_HEALTHCHECK_QUERY,
        retry_config: RetryConfig = DEFAULT_RETRY_CONFIG,
    ) -> None:
        """Initialize provider.

        Args:
            postgres_config: PostgreSQL configuration.
            metrics: Optional metrics collector.
            healthcheck_query: SQL executed at startup to verify connectivity.
                Pass ``None`` to skip the healthcheck entirely.
            retry_config: Retry behavior for healthcheck.
        """
        self._postgres_config = postgres_config
        self._metrics = metrics
        self._healthcheck_query = healthcheck_query
        self._retry_config = retry_config
        self._manager: AsyncSessionManager[AsyncSession] | None = None

    async def start(self) -> AsyncSessionManager[AsyncSession]:
        """Start session manager and perform healthcheck."""
        manager = create_async_session_manager(self._postgres_config, metrics=self._metrics)

        if self._healthcheck_query is not None:
            query = self._healthcheck_query

            async def test_connection() -> None:
                async with manager.session_maker() as session:
                    await session.execute(text(query))

            await retry_async_connection(
                connect_func=test_connection,
                service_name="PostgreSQL",
                config=self._retry_config,
            )

        self._manager = manager
        return manager

    async def stop(self) -> None:
        """Stop session manager and close connections."""
        if self._manager is not None:
            try:
                await self._manager.aclose()
                logger.info("Database session manager closed successfully")
            except SQLAlchemyError as e:
                logger.warning("Error closing database session manager: %s", e)
            finally:
                self._manager = None


__all__ = [
    "AsyncDatabaseResourceProvider",
    "DatabaseContainer",
    "RetryConfig",
    "retry_async_connection",
]
