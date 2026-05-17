"""Unit of Work with OpenTelemetry tracing support."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from ...uow import AsyncSQLAlchemyUnitOfWork, AsyncUowTransaction, IsolationLevel

if TYPE_CHECKING:
    from opentelemetry.trace import Span, Tracer

logger = logging.getLogger(__name__)

try:
    from opentelemetry import trace
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
    ) -> None:
        """Initialize traced unit of work.

        Args:
            session_maker: SQLAlchemy async session maker.
            transaction_factory: Factory function to create transaction objects.
            service_name: Service name for OpenTelemetry tracer.
        """
        super().__init__(session_maker, transaction_factory)
        self._tracer: Tracer | None = trace.get_tracer(service_name) if HAS_OTEL else None

    @asynccontextmanager
    async def transaction(
        self,
        isolation_level: IsolationLevel | str | None = None,
        flush_before_commit: bool | None = None,
        auto_commit: bool = True,
    ) -> AsyncIterator[T]:
        """Create a new transaction context with tracing.

        Automatically creates a span named "uow.transaction" with attributes:
        - db.operation: "transaction"
        - db.isolation_level: The isolation level (if specified)
        - db.auto_commit: Whether auto-commit is enabled
        - db.outcome: "commit" or "rollback"

        Args:
            isolation_level: Optional transaction isolation level.
            flush_before_commit: If True, flush before commit.
            auto_commit: If True, automatically commit on exit.

        Yields:
            Transaction object with repositories.
        """
        if not self._tracer:
            # No tracing available, delegate to parent
            async with super().transaction(
                isolation_level=isolation_level,
                flush_before_commit=flush_before_commit,
                auto_commit=auto_commit,
            ) as tx:
                yield tx
            return

        span: Span = self._tracer.start_span("uow.transaction")
        span.set_attribute("db.operation", "transaction")
        if isolation_level:
            span.set_attribute("db.isolation_level", str(isolation_level))
        span.set_attribute("db.auto_commit", auto_commit)

        try:
            async with super().transaction(
                isolation_level=isolation_level,
                flush_before_commit=flush_before_commit,
                auto_commit=auto_commit,
            ) as tx:
                yield tx

            # Transaction succeeded
            span.set_attribute("db.outcome", "commit" if auto_commit else "manual")
            span.set_status(Status(StatusCode.OK))

        except Exception as e:
            # Transaction failed
            span.set_attribute("db.outcome", "rollback")
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise

        finally:
            span.end()

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
        if not self._tracer:
            # No tracing available, delegate to parent
            async with super().query(isolation_level=isolation_level) as qx:
                yield qx
            return

        span: Span = self._tracer.start_span("uow.query")
        span.set_attribute("db.operation", "query")
        if isolation_level:
            span.set_attribute("db.isolation_level", str(isolation_level))

        try:
            async with super().query(isolation_level=isolation_level) as qx:
                yield qx

            span.set_status(Status(StatusCode.OK))

        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise

        finally:
            span.end()


__all__ = ["TracedAsyncUnitOfWork"]
