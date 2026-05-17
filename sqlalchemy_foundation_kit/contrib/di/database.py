"""Database providers for dishka."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...config import PostgresSettingsProtocol
from ...protocols import PostgresMetricsProtocol
from ...session import AsyncSessionManager, create_async_session_manager
from ...uow import AsyncSQLAlchemyUnitOfWork, AsyncSQLAlchemyUowTransaction, AsyncUnitOfWork
from ._deps import Provider, Scope, check_dishka, provide

logger = logging.getLogger(__name__)

DEFAULT_HEALTHCHECK_QUERY = "SELECT 1"
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0


async def retry_async_connection(
    connect_func: Callable[[], Awaitable[None]],
    service_name: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay: float = DEFAULT_RETRY_DELAY,
) -> None:
    """Retry an async connection callable with exponential backoff.

    Args:
        connect_func: Callable that attempts to establish/test the connection.
        service_name: Human-readable service name used in log messages.
        max_retries: Maximum number of attempts before giving up.
        retry_delay: Base delay in seconds; actual delay is ``retry_delay * 2 ** attempt``.

    Raises:
        Exception: Re-raises the last exception when all attempts fail.
    """
    for attempt in range(max_retries):
        try:
            await connect_func()
        except Exception:
            if attempt == max_retries - 1:
                logger.exception("%s connection failed after %d attempts", service_name, max_retries)
                raise
            logger.warning("%s connection attempt %d failed, retrying...", service_name, attempt + 1)
            await asyncio.sleep(retry_delay * (2**attempt))
        else:
            logger.info("%s connection successful", service_name)
            return


async def safe_async_cleanup(
    cleanup_func: Callable[[], Awaitable[None]],
    service_name: str,
    exception_type: type[BaseException] = Exception,
) -> None:
    """Run an async cleanup callable, logging instead of raising on failure."""
    try:
        await cleanup_func()
        logger.info("%s closed successfully", service_name)
    except exception_type as e:
        logger.warning("Error closing %s: %s", service_name, e)


class AsyncDatabaseProvider(Provider):
    """Provider for database dependencies.

    Provides:
    - AsyncSessionManager: Manages database connections and engine lifecycle.
    - async_sessionmaker[AsyncSession]: Factory for creating database sessions.

    Note: metrics (PostgresMetricsProtocol) must be provided by a separate
    provider (e.g., PrometheusPostgresMetricsProvider) or registered in the
    container. If you don't want metrics, simply don't register such provider.

    Customization:
        - Pass ``healthcheck_query=None`` to skip the startup connectivity check.
        - Override ``healthcheck_query``, ``max_retries``, ``retry_delay`` for
          custom startup behavior.
        - Subclass and override :meth:`build_session_manager` to fully customize
          how the manager is constructed (e.g., to pass ``extra_server_settings``,
          ``connection_class``, or ``on_engine_created``).

    Examples:
        >>> provider = AsyncDatabaseProvider(
        ...     healthcheck_query="SELECT version()",
        ...     max_retries=5,
        ...     retry_delay=2.0,
        ... )

        >>> # Skip healthcheck entirely (e.g., for tests):
        >>> provider = AsyncDatabaseProvider(healthcheck_query=None)
    """

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Check dependencies when subclassing."""
        super().__init_subclass__(**kwargs)
        check_dishka()

    scope = Scope.APP

    def __init__(
        self,
        healthcheck_query: str | None = DEFAULT_HEALTHCHECK_QUERY,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ) -> None:
        """Initialize provider.

        Args:
            healthcheck_query: SQL executed at startup to verify connectivity.
                Pass ``None`` to skip the healthcheck entirely.
            max_retries: How many times to retry the healthcheck before failing.
            retry_delay: Base delay between healthcheck retries (exponential backoff).
        """
        super().__init__()
        check_dishka()
        self._healthcheck_query = healthcheck_query
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    def build_session_manager(
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
            Configured AsyncSessionManager.
        """
        return create_async_session_manager(postgres_config, metrics=metrics)

    @provide
    async def get_session_manager(
        self,
        postgres_config: PostgresSettingsProtocol,
        metrics: PostgresMetricsProtocol | None = None,
    ) -> AsyncIterator[AsyncSessionManager[AsyncSession]]:
        """Provide database session manager."""
        manager = self.build_session_manager(postgres_config, metrics)

        if self._healthcheck_query is not None:
            query = self._healthcheck_query

            async def test_connection() -> None:
                async with manager.session_maker() as session:
                    await session.execute(text(query))

            await retry_async_connection(
                connect_func=test_connection,
                service_name="PostgreSQL",
                max_retries=self._max_retries,
                retry_delay=self._retry_delay,
            )

        try:
            yield manager
        finally:
            await safe_async_cleanup(
                cleanup_func=manager.aclose,
                service_name="database session manager",
                exception_type=SQLAlchemyError,
            )

    @provide
    def get_session_maker(self, session_manager: AsyncSessionManager[AsyncSession]) -> async_sessionmaker[AsyncSession]:
        """Provide session maker."""
        return session_manager.session_maker  # type: ignore[no-any-return]


class AsyncUnitOfWorkProvider(Provider):
    """Provider for Unit of Work.

    Provides:
    - AsyncUnitOfWork: Standardized interface for database transactions.

    Note: UoW is APP-scoped because it's stateless - it only holds a reference to
    session_maker (factory). Real database connections are created only when calling
    uow.transaction(), and are properly closed after the context manager exits.

    Customization:
        Override :meth:`build_uow` to use a custom transaction class
        (e.g., one that exposes domain repositories as lazy properties).
    """

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Check dependencies when subclassing."""
        super().__init_subclass__(**kwargs)
        check_dishka()

    scope = Scope.APP

    def build_uow(
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
        Each call to uow.transaction() creates a new database session/connection.
        """
        return self.build_uow(session_maker)


__all__ = [
    "AsyncDatabaseProvider",
    "AsyncUnitOfWorkProvider",
    "retry_async_connection",
    "safe_async_cleanup",
]
