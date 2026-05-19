"""Database providers for dishka."""

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
from ...uow import (
    AsyncSQLAlchemyUnitOfWork,
    AsyncSQLAlchemyUowTransaction,
    AsyncUnitOfWork,
)
from ._base import BaseDishkaProvider
from ._deps import Scope, provide

logger = logging.getLogger(__name__)


class AsyncDatabaseProvider(BaseDishkaProvider):
    """Provider for database dependencies.

    Provides:
        - ``AsyncSessionManager``: Manages database connections and engine lifecycle.
        - ``async_sessionmaker[AsyncSession]``: Factory for creating database sessions.

    Note: ``PostgresMetricsProtocol`` must be provided by a separate provider
    (e.g., :class:`PrometheusPostgresMetricsProvider`) or registered in the container.
    If you don't want metrics, simply don't register such a provider.

    Customization:
        - Pass ``healthcheck_query=None`` to skip the startup connectivity check.
        - Pass a custom :class:`RetryConfig` to tune startup retry behaviour.
        - Subclass and override :meth:`create_session_manager` to fully customize
          how the manager is constructed (e.g., to pass ``extra_server_settings``,
          ``connection_class``, or ``on_engine_created``).
    """

    scope = Scope.APP

    def __init__(
        self,
        healthcheck_query: str | None = DEFAULT_HEALTHCHECK_QUERY,
        retry_config: RetryConfig = DEFAULT_RETRY_CONFIG,
    ) -> None:
        """Initialize provider.

        Args:
            healthcheck_query: SQL executed at startup to verify connectivity.
                Pass ``None`` to skip the healthcheck entirely.
            retry_config: Retry behavior for the startup healthcheck.
        """
        super().__init__()
        self._healthcheck_query = healthcheck_query
        self._retry_config = retry_config

    def create_session_manager(
        self,
        postgres_config: PostgresSettingsProtocol,
        metrics: PostgresMetricsProtocol | None,
    ) -> AsyncSessionManager[AsyncSession]:
        """Build an ``AsyncSessionManager`` for the given config.

        Override this hook to customize session manager construction — for example,
        to pass ``extra_server_settings``, a custom ``connection_class``, or an
        ``on_engine_created`` callback for OpenTelemetry instrumentation.

        Args:
            postgres_config: PostgreSQL configuration.
            metrics: Optional metrics collector.

        Returns:
            Configured ``AsyncSessionManager``.
        """
        return create_async_session_manager(postgres_config, metrics=metrics)

    @provide
    async def get_session_manager(
        self,
        postgres_config: PostgresSettingsProtocol,
        metrics: PostgresMetricsProtocol | None = None,
    ) -> AsyncIterator[AsyncSessionManager[AsyncSession]]:
        """Provide database session manager."""
        manager = self.create_session_manager(postgres_config, metrics)

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

        try:
            yield manager
        finally:
            try:
                await manager.aclose()
                logger.info("Database session manager closed successfully")
            except SQLAlchemyError as e:
                logger.warning("Error closing database session manager: %s", e)

    @provide
    def get_session_maker(self, session_manager: AsyncSessionManager[AsyncSession]) -> async_sessionmaker[AsyncSession]:
        """Provide session maker."""
        return session_manager.session_maker  # type: ignore[no-any-return]


class AsyncUnitOfWorkProvider(BaseDishkaProvider):
    """Provider for Unit of Work.

    Provides:
        - ``AsyncUnitOfWork``: Standardized interface for database transactions.

    Note: UoW is APP-scoped because it's stateless — it only holds a reference to
    ``session_maker`` (factory). Real database connections are created only when calling
    ``uow.transaction()``, and are properly closed after the context manager exits.

    Customization:
        Override :meth:`create_uow` to use a custom transaction class
        (e.g., one that exposes domain repositories as lazy properties).
    """

    scope = Scope.APP

    def create_uow(
        self,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> AsyncUnitOfWork[AsyncSQLAlchemyUowTransaction]:
        """Construct the UoW instance. Override to inject a custom transaction class."""
        return AsyncSQLAlchemyUnitOfWork(session_maker, transaction_factory=AsyncSQLAlchemyUowTransaction)

    @provide
    def get_uow(
        self,
        session_maker: async_sessionmaker[AsyncSession],
    ) -> AsyncUnitOfWork[AsyncSQLAlchemyUowTransaction]:
        """Provide Unit of Work.

        Returns a stateless UoW instance that can be safely reused.
        Each call to ``uow.transaction()`` creates a new database session/connection.
        """
        return self.create_uow(session_maker)


__all__ = [
    "AsyncDatabaseProvider",
    "AsyncUnitOfWorkProvider",
    "RetryConfig",
    "retry_async_connection",
]
