"""Async database session manager with connection pooling."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from types import TracebackType
from typing import TYPE_CHECKING, Any, Generic, cast

from sqlalchemy import event
from sqlalchemy.exc import TimeoutError as SATimeoutError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .._typing import SessionT
from ..base import build_engine_kwargs, resolve_pool_class

if TYPE_CHECKING:
    from ..config import PoolSettingsProtocol
    from ..protocols import PostgresMetricsProtocol

logger = logging.getLogger(__name__)

DEFAULT_DISPOSE_TIMEOUT_SECONDS: float = 30.0


def _safe_metric_call(func: Callable[[], None], error_msg: str) -> None:
    """Call a metric-recording function and swallow exceptions.

    Metrics must never break application logic — any failure inside the metric
    callback is logged at exception level and discarded.

    Args:
        func: Zero-arg callable that records a metric.
        error_msg: Message logged together with the traceback on failure.
    """
    try:
        func()
    except Exception:
        logger.exception(error_msg)


def attach_metrics(engine: AsyncEngine, metrics: PostgresMetricsProtocol) -> None:
    """Attach metrics event listeners to a SQLAlchemy engine.

    Registers event handlers for connection checkout, checkin, and error events
    to collect pool statistics and connection metrics.

    Args:
        engine: SQLAlchemy ``AsyncEngine`` to attach listeners to.
        metrics: Metrics collector implementing ``PostgresMetricsProtocol``.
    """
    pool = engine.pool

    def record_pool_stats() -> None:
        _safe_metric_call(
            lambda: metrics.record_pool_stats(
                pool_size=pool.size() if hasattr(pool, "size") else 0,
                pool_checked_out=(pool.checkedout() if hasattr(pool, "checkedout") else 0),
                pool_overflow=pool.overflow() if hasattr(pool, "overflow") else 0,
            ),
            "Failed to record database pool stats",
        )

    def on_checkout(dbapi_connection: Any, connection_record: Any, connection_proxy: Any) -> None:
        """Handle connection checkout event."""
        record_pool_stats()
        connection_record.info["checkout_start"] = time.perf_counter()

    def on_checkin(dbapi_connection: Any, connection_record: Any) -> None:
        """Handle connection checkin event."""
        record_pool_stats()

        if "checkout_start" in connection_record.info:
            duration = time.perf_counter() - connection_record.info["checkout_start"]
            _safe_metric_call(
                lambda: metrics.record_checkout(duration=duration),
                "Failed to record database checkout duration",
            )

    def on_error(exception_context: Any) -> None:
        """Handle database error event."""
        exc = exception_context.original_exception
        error_type = type(exc).__name__
        is_timeout = isinstance(exc, (TimeoutError, SATimeoutError))
        _safe_metric_call(
            lambda: metrics.record_error(error_type=error_type, is_timeout=is_timeout),
            "Failed to record database error metric",
        )

    event.listen(pool, "checkout", on_checkout)
    event.listen(pool, "checkin", on_checkin)
    event.listen(engine.sync_engine, "handle_error", on_error)


class AsyncSessionManager(Generic[SessionT]):
    """Manages async database sessions with configurable connection pooling.

    Supports two initialization approaches:

    1. **Direct constructor** — all parameters in constructor with defaults.
    2. **Builder pattern** — use :class:`AsyncSessionManagerBuilder` for more
       readable complex configurations.
    """

    def __init__(
        self,
        url: str,
        echo: bool = False,
        poolclass: str | type = "null",
        session_class: type[SessionT] | None = None,
        expire_on_commit: bool = False,
        connect_args: dict[str, object] | None = None,
        isolation_level: str | None = None,
        pool_settings: PoolSettingsProtocol | None = None,
        use_orjson: bool = False,
        metrics: PostgresMetricsProtocol | None = None,
        on_engine_created: Callable[[AsyncEngine], None] | None = None,
        dispose_timeout: float = DEFAULT_DISPOSE_TIMEOUT_SECONDS,
        **kwargs: object,
    ) -> None:
        """Initialize session manager with direct configuration.

        Args:
            url: Database connection URL (required).
            echo: If True, SQLAlchemy will log all SQL statements (default: False).
            poolclass: SQLAlchemy pool class or name (default: "null").
                Use "queue" for production, "null" for testing.
            session_class: Custom ``AsyncSession`` subclass (default: ``AsyncSession``).
            expire_on_commit: If True, objects expire after commit (default: False).
            connect_args: Arguments passed to the database driver (default: None).
            isolation_level: Default transaction isolation level (default: None).
            pool_settings: Pool configuration settings (default: None).
            use_orjson: If True, use orjson for JSON serialization (default: False).
            metrics: Optional metrics collector (default: None).
            on_engine_created: Optional callback invoked with ``AsyncEngine`` after creation.
                Use for OpenTelemetry instrumentation, custom event listeners, etc.
            dispose_timeout: Maximum seconds to wait for engine disposal in :meth:`aclose`
                (default: 30.0). Lower this in tests or short-lived environments; raise it
                if you have long-running transactions that need more time to settle.
            **kwargs: Additional keyword arguments for ``create_async_engine``.
        """
        self._closed = False
        self._close_lock = asyncio.Lock()
        self._dispose_timeout = dispose_timeout
        resolved_poolclass = resolve_pool_class(poolclass)
        engine_kwargs = build_engine_kwargs(
            echo=echo,
            poolclass=resolved_poolclass,
            isolation_level=isolation_level,
            pool_settings=pool_settings,
            connect_args=connect_args,
            extra_kwargs=kwargs,
            use_orjson=use_orjson,
        )

        self._engine: AsyncEngine = create_async_engine(url, **engine_kwargs)
        self._session_maker = cast(
            async_sessionmaker[SessionT],
            async_sessionmaker(
                self._engine,
                class_=session_class or AsyncSession,
                expire_on_commit=expire_on_commit,
            ),
        )

        if metrics:
            attach_metrics(self._engine, metrics)

        if on_engine_created is not None:
            on_engine_created(self._engine)

    async def aclose(self) -> None:
        """Close the engine and all connections."""
        async with self._close_lock:
            if self._closed:
                return

            try:
                # Use shield so disposal runs even if the task is cancelled; timeout avoids indefinite hang.
                await asyncio.wait_for(
                    asyncio.shield(self._engine.dispose()),
                    timeout=self._dispose_timeout,
                )
            except TimeoutError:
                logger.warning(
                    "Engine disposal timed out after %.1f seconds. Some connections may not have closed cleanly.",
                    self._dispose_timeout,
                )
            finally:
                # Always mark as closed to prevent retry loops
                self._closed = True

    def _ensure_not_closed(self) -> None:
        """Ensure that the manager is not closed."""
        if self._closed:
            raise RuntimeError("AsyncSessionManager is closed")

    async def __aenter__(self) -> AsyncSessionManager[SessionT]:
        """Support for async context manager."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Close the engine on exit."""
        await self.aclose()

    @property
    def engine(self) -> AsyncEngine:
        """Get the underlying engine."""
        return self._engine

    @property
    def session_maker(self) -> async_sessionmaker[SessionT]:
        """Get the session maker."""
        return self._session_maker

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[SessionT]:
        """Get a new database session."""
        self._ensure_not_closed()
        async with self._session_maker() as session:
            yield session

    @asynccontextmanager
    async def get_transaction(self, isolation_level: str | None = None) -> AsyncIterator[SessionT]:
        """Get a new database session with automatic transaction management.

        Args:
            isolation_level: Optional isolation level for the transaction.

        Yields:
            Managed async session with active transaction.
        """
        self._ensure_not_closed()
        options = {"isolation_level": isolation_level} if isolation_level else {}
        async with (
            self._session_maker(execution_options=options) as session,
            session.begin(),
        ):
            yield session
