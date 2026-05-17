"""Metrics protocols for database monitoring.

Protocols are split by capability (ISP). Implementations may satisfy
the narrow protocols selectively (e.g., only record errors), and
``PostgresMetricsProtocol`` aggregates them for convenience.
"""

from __future__ import annotations

from typing import Protocol


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
    """Capability protocol for recording connection checkout duration."""

    def record_checkout(self, duration: float) -> None:
        """Record a database connection checkout from the pool.

        Args:
            duration: Time taken to acquire the connection from the pool, in seconds.
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

    Examples:
        >>> class MyMetrics:
        ...     def record_pool_stats(self, pool_size: int, pool_checked_out: int, pool_overflow: int) -> None: ...
        ...     def record_checkout(self, duration: float) -> None: ...
        ...     def record_error(self, error_type: str, is_timeout: bool = False) -> None: ...
        >>> metrics: PostgresMetricsProtocol = MyMetrics()
    """


__all__ = [
    "CheckoutRecorder",
    "ErrorRecorder",
    "PoolStatsRecorder",
    "PostgresMetricsProtocol",
]
