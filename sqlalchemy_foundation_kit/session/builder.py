"""Builder pattern for AsyncSessionManager configuration.

Provides a fluent interface for constructing AsyncSessionManager instances
with many optional parameters, following the Builder pattern to simplify
complex object creation and improve code readability.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from .manager import AsyncSessionManager

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncEngine

    from ..config import PoolSettingsProtocol
    from ..protocols import PostgresMetricsProtocol


class AsyncSessionManagerBuilder[SessionT: AsyncSession]:
    """Builder for AsyncSessionManager construction.

    Provides a fluent API for configuring AsyncSessionManager with many optional
    parameters. This pattern improves code readability and follows KISS principle
    by avoiding constructors with 10+ parameters.

    Examples:
        Basic usage:
            >>> manager = (
            ...     AsyncSessionManagerBuilder("postgresql+asyncpg://...")
            ...     .with_pool("queue")
            ...     .with_echo(True)
            ...     .build()
            ... )

        Advanced configuration:
            >>> manager = (
            ...     AsyncSessionManagerBuilder[CustomSession]("postgresql+asyncpg://...")
            ...     .with_session_class(CustomSession)
            ...     .with_pool("queue", pool_settings=settings.pool)
            ...     .with_metrics(metrics)
            ...     .with_callbacks(on_engine_created=instrument_engine)
            ...     .with_json_serialization(orjson=True)
            ...     .with_isolation_level("READ COMMITTED")
            ...     .build()
            ... )

        Reusable configuration:
            >>> builder = (
            ...     AsyncSessionManagerBuilder("postgresql+asyncpg://...")
            ...     .with_pool("queue")
            ...     .with_metrics(metrics)
            ... )
            >>> manager1 = builder.with_echo(True).build()
            >>> manager2 = builder.with_echo(False).build()
    """

    def __init__(self, url: str) -> None:
        """Initialize builder with database URL (required).

        Args:
            url: Database connection URL (required parameter).
        """
        self._url = url
        self._echo: bool = False
        self._poolclass: str | type = "null"
        self._session_class: type[SessionT] | None = None
        self._expire_on_commit: bool = False
        self._connect_args: dict[str, object] | None = None
        self._isolation_level: str | None = None
        self._pool_settings: PoolSettingsProtocol | None = None
        self._use_orjson: bool = False
        self._metrics: PostgresMetricsProtocol | None = None
        self._on_engine_created: Callable[[AsyncEngine], None] | None = None
        self._dispose_timeout: float | None = None
        self._extra_kwargs: dict[str, object] = {}

    def with_echo(self, echo: bool = True) -> AsyncSessionManagerBuilder[SessionT]:
        """Enable SQL statement logging.

        Args:
            echo: If True, SQLAlchemy logs all SQL statements.

        Returns:
            Self for method chaining.
        """
        self._echo = echo
        return self

    def with_pool(
        self,
        poolclass: str | type,
        pool_settings: PoolSettingsProtocol | None = None,
    ) -> AsyncSessionManagerBuilder[SessionT]:
        """Configure connection pool.

        Args:
            poolclass: Pool class name or type (e.g., "queue", "null").
            pool_settings: Optional pool configuration settings.

        Returns:
            Self for method chaining.
        """
        self._poolclass = poolclass
        self._pool_settings = pool_settings
        return self

    def with_session_class(
        self,
        session_class: type[SessionT],
    ) -> AsyncSessionManagerBuilder[SessionT]:
        """Use custom session class.

        Args:
            session_class: Custom AsyncSession subclass.

        Returns:
            Self for method chaining.
        """
        self._session_class = session_class
        return self

    def with_expire_on_commit(
        self,
        expire: bool = True,
    ) -> AsyncSessionManagerBuilder[SessionT]:
        """Configure object expiration behavior after commit.

        Args:
            expire: If True, all objects expire after commit.

        Returns:
            Self for method chaining.
        """
        self._expire_on_commit = expire
        return self

    def with_connect_args(
        self,
        **connect_args: object,
    ) -> AsyncSessionManagerBuilder[SessionT]:
        """Add database driver connection arguments.

        Args:
            **connect_args: Arguments passed to the database driver.

        Returns:
            Self for method chaining.

        Examples:
            >>> builder.with_connect_args(
            ...     server_settings={"application_name": "myapp"},
            ...     command_timeout=60,
            ... )
        """
        if self._connect_args is None:
            self._connect_args = {}
        self._connect_args.update(connect_args)
        return self

    def with_isolation_level(
        self,
        isolation_level: str,
    ) -> AsyncSessionManagerBuilder[SessionT]:
        """Set default transaction isolation level.

        Args:
            isolation_level: Default isolation level (e.g., "READ COMMITTED").

        Returns:
            Self for method chaining.
        """
        self._isolation_level = isolation_level
        return self

    def with_metrics(
        self,
        metrics: PostgresMetricsProtocol,
    ) -> AsyncSessionManagerBuilder[SessionT]:
        """Enable connection pool metrics collection.

        Args:
            metrics: Metrics collector implementing PostgresMetricsProtocol.

        Returns:
            Self for method chaining.
        """
        self._metrics = metrics
        return self

    def with_callbacks(
        self,
        on_engine_created: Callable[[AsyncEngine], None],
    ) -> AsyncSessionManagerBuilder[SessionT]:
        """Register engine creation callback.

        Useful for attaching instrumentation (OpenTelemetry), custom event
        listeners, or debug hooks right after engine creation.

        Args:
            on_engine_created: Callback invoked with AsyncEngine after creation.

        Returns:
            Self for method chaining.

        Examples:
            >>> from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
            >>> def instrument(engine):
            ...     SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
            >>> builder.with_callbacks(on_engine_created=instrument)
        """
        self._on_engine_created = on_engine_created
        return self

    def with_json_serialization(
        self,
        orjson: bool = True,
    ) -> AsyncSessionManagerBuilder[SessionT]:
        """Configure JSON serialization backend.

        Args:
            orjson: If True, use orjson for faster JSON serialization.

        Returns:
            Self for method chaining.

        Raises:
            ImportError: If orjson=True but orjson is not installed.
        """
        self._use_orjson = orjson
        return self

    def with_extra_kwargs(self, **kwargs: object) -> AsyncSessionManagerBuilder[SessionT]:
        """Add additional keyword arguments for create_async_engine.

        Args:
            **kwargs: Additional engine configuration.

        Returns:
            Self for method chaining.
        """
        self._extra_kwargs.update(kwargs)
        return self

    def with_dispose_timeout(self, timeout: float) -> AsyncSessionManagerBuilder[SessionT]:
        """Configure how long :meth:`AsyncSessionManager.aclose` waits for engine disposal.

        Args:
            timeout: Maximum seconds to wait for the engine to dispose.

        Returns:
            Self for method chaining.
        """
        self._dispose_timeout = timeout
        return self

    def build(self) -> AsyncSessionManager[SessionT]:
        """Build AsyncSessionManager instance with configured parameters.

        Returns:
            Configured AsyncSessionManager instance.

        Raises:
            ImportError: If use_orjson=True but orjson is not installed.

        Examples:
            >>> manager = builder.build()
            >>> async with manager.get_session() as session:
            ...     await session.execute(...)
        """
        kwargs: dict[str, object] = {
            "url": self._url,
            "echo": self._echo,
            "poolclass": self._poolclass,
            "session_class": self._session_class,
            "expire_on_commit": self._expire_on_commit,
            "connect_args": self._connect_args,
            "isolation_level": self._isolation_level,
            "pool_settings": self._pool_settings,
            "use_orjson": self._use_orjson,
            "metrics": self._metrics,
            "on_engine_created": self._on_engine_created,
        }
        if self._dispose_timeout is not None:
            kwargs["dispose_timeout"] = self._dispose_timeout
        return AsyncSessionManager(**kwargs, **self._extra_kwargs)  # type: ignore[arg-type]


__all__ = ["AsyncSessionManagerBuilder"]
