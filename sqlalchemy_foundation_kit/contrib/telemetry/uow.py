"""Unit of Work with OpenTelemetry tracing support."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from ...base._optional import require_optional
from ...uow import AsyncSQLAlchemyUnitOfWork, AsyncUowTransaction, IsolationLevel

if TYPE_CHECKING:
    from opentelemetry.trace import Span, Tracer

logger = logging.getLogger(__name__)

try:
    trace = require_optional("opentelemetry.trace", "telemetry")
    from opentelemetry.trace import Status, StatusCode

    HAS_OTEL = True
except ImportError:
    HAS_OTEL = False
    trace = None  # type: ignore[assignment]


class TracedAsyncUnitOfWork[T: AsyncUowTransaction](AsyncSQLAlchemyUnitOfWork[T]):
    """Unit of Work with automatic OpenTelemetry tracing.

    Automatically creates spans for transaction() and query() operations,
    including transaction attributes (isolation level, duration, outcome).

    Example:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider

        trace.set_tracer_provider(TracerProvider())

        uow = TracedAsyncUnitOfWork(
            session_maker=session_maker,
            transaction_factory=MyTransaction,
            service_name="my-service",
        )

        async with uow.transaction() as tx:
            # This operation is automatically traced
            user = await tx.users.create(...)
    """

    def __init__(
        self,
        session_maker,
        transaction_factory,
        service_name: str = "sqlalchemy-foundation-kit",
        *,
        flush_before_commit: bool = True,
    ) -> None:
        """Initialize traced unit of work.

        Args:
            session_maker: SQLAlchemy async session maker.
            transaction_factory: Factory function to create transaction objects.
            service_name: Service name for OpenTelemetry tracer.
            flush_before_commit: Default ``flush_before_commit`` policy applied when
                :meth:`transaction` is called without an explicit override.
        """
        super().__init__(session_maker, transaction_factory, flush_before_commit=flush_before_commit)
        self._tracer: Tracer | None = trace.get_tracer(service_name) if HAS_OTEL else None

    @asynccontextmanager
    async def _traced(
        self,
        operation: str,
        context_manager,
        attributes: dict[str, str | bool] | None = None,
    ) -> AsyncIterator[T]:
        """Generic tracing wrapper for UoW operations.

        Args:
            operation: Operation name (e.g., "transaction", "query").
            context_manager: Async context manager to wrap with tracing.
            attributes: Optional span attributes to set.

        Yields:
            Transaction object from the wrapped context manager.
        """
        if not self._tracer:
            # No tracing available, delegate to wrapped context manager
            async with context_manager as result:
                yield result
            return

        span: Span = self._tracer.start_span(f"uow.{operation}")
        span.set_attribute("db.operation", operation)

        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)

        try:
            async with context_manager as result:
                yield result

            span.set_status(Status(StatusCode.OK))

        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise

        finally:
            span.end()

    @asynccontextmanager
    async def transaction(
        self,
        isolation_level: IsolationLevel | str | None = None,
        flush_before_commit: bool | None = None,
    ) -> AsyncIterator[T]:
        """Create a new transaction context with tracing.

        Automatically creates a span named "uow.transaction" with attributes:
        - db.operation: "transaction"
        - db.isolation_level: The isolation level (if specified)

        Args:
            isolation_level: Optional transaction isolation level.
            flush_before_commit: If True, flush before commit.

        Yields:
            Transaction object with repositories.
        """
        attributes = {}
        if isolation_level:
            attributes["db.isolation_level"] = str(isolation_level)

        async with self._traced(
            operation="transaction",
            context_manager=super().transaction(
                isolation_level=isolation_level,
                flush_before_commit=flush_before_commit,
            ),
            attributes=attributes,
        ) as tx:
            yield tx

    @asynccontextmanager
    async def query(
        self,
        isolation_level: IsolationLevel | str | None = None,
    ) -> AsyncIterator[T]:
        """Create a read-only query context with tracing.

        Automatically creates a span named "uow.query" with attributes:
        - db.operation: "query"
        - db.isolation_level: The isolation level (if specified)

        Args:
            isolation_level: Optional transaction isolation level.

        Yields:
            Query object with repositories.
        """
        attributes = {}
        if isolation_level:
            attributes["db.isolation_level"] = str(isolation_level)

        async with self._traced(
            operation="query",
            context_manager=super().query(isolation_level=isolation_level),
            attributes=attributes,
        ) as qx:
            yield qx


__all__ = ["TracedAsyncUnitOfWork"]
