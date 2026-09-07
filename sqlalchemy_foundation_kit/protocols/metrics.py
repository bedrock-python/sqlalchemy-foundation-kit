"""Metrics protocols for database monitoring.

Protocols are split by capability (ISP). Implementations may satisfy
the narrow protocols selectively (e.g., only record errors), and
``PostgresMetricsProtocol`` aggregates them for convenience.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class PoolStatsRecorder(Protocol):
    """Capability protocol for recording pool statistics."""

    def record_pool_stats(
        self,
        pool_size: int,
        pool_checked_out: int,
        pool_overflow: int,
    ) -> None:
        """Record database connection pool statistics.

        Args:
            pool_size: Current total number of connections in the pool.
            pool_checked_out: Number of connections currently in use.
            pool_overflow: Number of connections over the configured pool_size.
        """
        ...


class CheckoutRecorder(Protocol):
    """Capability protocol for recording how long a connection was held."""

    def record_checkout(self, duration: float) -> None:
        """Record a completed database connection checkout.

        Args:
            duration: Time between the connection leaving the pool and coming back to it,
                in seconds — how long the caller *held* it, which is the query time seen
                from the pool. The time a caller spent *waiting* for it is
                :class:`CheckoutWaitRecorder`.
        """
        ...


@runtime_checkable
class CheckoutWaitRecorder(Protocol):
    """Capability protocol for recording the wait for a connection from the pool.

    Deliberately not part of :class:`PostgresMetricsProtocol`: a metrics object written
    against the three older capabilities stays valid and simply publishes no wait series.
    The session manager tests for this protocol with ``isinstance`` and instruments the
    pool class only when it is satisfied, which is what ``runtime_checkable`` is for here.
    """

    def record_checkout_wait(self, duration: float, timed_out: bool = False) -> None:
        """Record the time a caller spent acquiring a connection from the pool.

        Args:
            duration: Seconds spent inside ``pool.connect()`` — the queue wait, and the
                pre-ping round trip and connect handshake when the pool had to grow.
            timed_out: True if the wait ended in ``sqlalchemy.exc.TimeoutError`` rather
                than in a connection. This is the pool checkout timeout; it is raised
                before any DBAPI call and so never reaches the engine's ``handle_error``.
        """
        ...


class ErrorRecorder(Protocol):
    """Capability protocol for recording database errors."""

    def record_error(self, error_type: str, is_timeout: bool = False) -> None:
        """Record a database connection or execution error.

        Args:
            error_type: The type of error that occurred (e.g., "OperationalError").
            is_timeout: True if this error was specifically a connection checkout timeout.
        """
        ...


class PostgresMetricsProtocol(PoolStatsRecorder, CheckoutRecorder, ErrorRecorder, Protocol):
    """Composite protocol covering all PostgreSQL metrics capabilities.

    Aggregates the narrow capability protocols for convenience. Implementations
    that only need a subset can implement the individual protocols directly.

    :class:`CheckoutWaitRecorder` is intentionally left out so that implementations
    written before it keep satisfying this protocol; add ``record_checkout_wait`` to get
    the checkout wait histogram and the pool timeout counter as well.

    Examples:
        >>> class MyMetrics:
        ...     def record_pool_stats(self, pool_size: int, pool_checked_out: int, pool_overflow: int) -> None: ...
        ...     def record_checkout(self, duration: float) -> None: ...
        ...     def record_checkout_wait(self, duration: float, timed_out: bool = False) -> None: ...
        ...     def record_error(self, error_type: str, is_timeout: bool = False) -> None: ...
        >>> metrics: PostgresMetricsProtocol = MyMetrics()
    """


__all__ = [
    "CheckoutRecorder",
    "CheckoutWaitRecorder",
    "ErrorRecorder",
    "PoolStatsRecorder",
    "PostgresMetricsProtocol",
]
