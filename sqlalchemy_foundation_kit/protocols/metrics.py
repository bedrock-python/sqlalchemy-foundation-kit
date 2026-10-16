"""Metrics protocols for database monitoring.

Protocols are split by capability (ISP). Implementations may satisfy
the narrow protocols selectively (e.g., only record errors), and
``PostgresMetricsProtocol`` aggregates them for convenience.
"""

from __future__ import annotations

from collections.abc import Callable
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

        Called from the pool's ``checkout`` and ``checkin`` events, so each call describes
        the pool as that event saw it -- and ``checkin`` fires before the connection is
        back, so the last call of a burst still counts it as checked out. A recorder that
        also implements :class:`PoolStatsFunctionRecorder` reads the pool when it is
        collected instead, and this method is then not called.

        Args:
            pool_size: The configured ``pool_size`` of a queue pool, 0 for any other pool.
            pool_checked_out: Number of connections currently in use.
            pool_overflow: Number of open connections over ``pool_size``, within
                ``max_overflow``; never negative.
        """
        ...


@runtime_checkable
class PoolStatsFunctionRecorder(Protocol):
    """Capability protocol for reading pool statistics when the metrics are collected.

    A gauge sampled from pool events goes stale: the ``checkin`` event fires before the
    connection is returned, and nothing fires once the pool is idle, so an idle pool keeps
    reporting the last burst. A recorder that implements this protocol is handed
    functions that read the pool on demand -- ``prometheus_client``'s
    ``Gauge.set_function`` -- and :class:`PoolStatsRecorder` is then not used for it.

    Not part of :class:`PostgresMetricsProtocol`, so implementations written without it
    stay valid; the session manager tests for it with ``isinstance``.
    """

    def set_pool_stats_functions(
        self,
        pool_size: Callable[[], float],
        pool_checked_out: Callable[[], float],
        pool_overflow: Callable[[], float],
    ) -> None:
        """Read the pool statistics from these functions whenever they are collected.

        Each function reads the engine's current pool, so the pool that ``dispose()``
        creates is the one reported. Values mean the same as in
        :meth:`PoolStatsRecorder.record_pool_stats`.

        Args:
            pool_size: Returns the configured ``pool_size``.
            pool_checked_out: Returns the number of connections currently in use.
            pool_overflow: Returns the number of open connections over ``pool_size``.
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
            timed_out: True if the wait ended in a timeout rather than in a connection:
                the pool checkout timeout (``sqlalchemy.exc.TimeoutError``) or the
                driver's connect timeout (a builtin ``TimeoutError`` while the pool opens
                a connection). Neither reaches the engine's ``handle_error``.
        """
        ...


@runtime_checkable
class ErrorRecorder(Protocol):
    """Capability protocol for recording database errors.

    Called for every error the engine's ``handle_error`` sees -- errors on an established
    connection, a statement timeout among them -- and, from the instrumented pool, for a
    connection the pool could not open. ``runtime_checkable`` so the instrumented pool can
    tell whether its recorder takes errors too.
    """

    def record_error(self, error_type: str, is_timeout: bool = False) -> None:
        """Record a database connection or execution error.

        Args:
            error_type: The type of error that occurred (e.g., "OperationalError").
            is_timeout: Kept for compatibility; the library no longer sets it. Timeouts
                acquiring a connection are reported through
                :meth:`CheckoutWaitRecorder.record_checkout_wait`.
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
    "PoolStatsFunctionRecorder",
    "PoolStatsRecorder",
    "PostgresMetricsProtocol",
]
