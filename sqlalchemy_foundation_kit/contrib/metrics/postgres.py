"""Postgres metrics using prometheus-client."""

from __future__ import annotations

import re

try:
    from prometheus_client import Counter, Gauge, Histogram

    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

# Default buckets for connection checkout duration (seconds)
CONNECTION_CHECKOUT_BUCKETS: tuple[float, ...] = (
    0.001,
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
)


def _check_prometheus() -> None:
    """Check if prometheus-client is installed."""
    if not HAS_PROMETHEUS:
        raise ImportError(
            "prometheus-client is required for PostgresMetrics. "
            "Install it with: pip install 'sqlalchemy-foundation-kit[metrics]'"
        )


class PostgresMetrics:
    """Postgres connection pool metrics.

    Metrics:
        - postgres_db_pool_size: Current database connection pool size.
        - postgres_db_pool_checked_out: Number of connections currently checked out.
        - postgres_db_pool_overflow: Number of connections over pool_size (within max_overflow).
        - postgres_db_connection_checkout_duration_seconds: Time to acquire connection from pool.
        - postgres_db_connection_timeouts_total: Number of connection checkout timeouts.
        - postgres_db_connection_errors_total: Number of connection errors.

    Labels:
        - error_type: Type of connection error (for errors_total).
    """

    def __init__(self, prefix: str | None = None) -> None:
        """Initialize postgres metrics.

        Args:
            prefix: Metric name prefix.

        Raises:
            ImportError: If prometheus-client is not installed.
        """
        _check_prometheus()

        self.pool_size = Gauge(
            _make_metric_name("postgres_db_pool_size", prefix),
            "Current database connection pool size",
        )
        self.pool_checked_out = Gauge(
            _make_metric_name("postgres_db_pool_checked_out", prefix),
            "Number of database connections currently checked out",
        )
        self.pool_overflow = Gauge(
            _make_metric_name("postgres_db_pool_overflow", prefix),
            "Number of connections over pool_size (within max_overflow)",
        )
        self.connection_checkout_duration = Histogram(
            _make_metric_name("postgres_db_connection_checkout_duration_seconds", prefix),
            "Time to acquire connection from pool",
            buckets=list(CONNECTION_CHECKOUT_BUCKETS),
        )
        self.connection_timeouts_total = Counter(
            _make_metric_name("postgres_db_connection_timeouts_total", prefix),
            "Number of connection checkout timeouts",
        )
        self.connection_errors_total = Counter(
            _make_metric_name("postgres_db_connection_errors_total", prefix),
            "Number of connection errors",
            ["error_type"],
        )

    def record_pool_stats(
        self,
        pool_size: int,
        pool_checked_out: int,
        pool_overflow: int,
    ) -> None:
        """Record database connection pool statistics."""
        self.pool_size.set(float(pool_size))
        self.pool_checked_out.set(float(pool_checked_out))
        self.pool_overflow.set(float(pool_overflow))

    def record_checkout(
        self,
        duration: float,
    ) -> None:
        """Record a database connection checkout from the pool."""
        self.connection_checkout_duration.observe(duration)

    def record_error(
        self,
        error_type: str,
        is_timeout: bool = False,
    ) -> None:
        """Record a database connection or execution error."""
        self.connection_errors_total.labels(error_type=error_type).inc()
        if is_timeout:
            self.connection_timeouts_total.inc()


_PREFIX_PATTERN: re.Pattern[str] = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _make_metric_name(name: str, prefix: str | None = None) -> str:
    """Make metric name with optional prefix.

    Prefix must follow Prometheus naming conventions (^[a-zA-Z_][a-zA-Z0-9_]*$).

    Args:
        name: Base metric name.
        prefix: Optional prefix for the metric.

    Returns:
        The combined metric name.

    Raises:
        ValueError: If the prefix is invalid.
    """
    if prefix:
        if not _PREFIX_PATTERN.match(prefix):
            raise ValueError(
                f"Invalid metric prefix: '{prefix}'. "
                "Prefixes must start with a letter or underscore and contain only letters, numbers, or underscores."
            )
        return f"{prefix}_{name}"
    return name


__all__ = ["PostgresMetrics"]
