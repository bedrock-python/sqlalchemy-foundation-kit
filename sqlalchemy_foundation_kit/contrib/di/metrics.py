"""Metrics providers for dishka."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ...protocols import PostgresMetricsProtocol
from ._base import BaseDishkaProvider
from ._deps import Scope, provide


@runtime_checkable
class PrometheusMetricsSettingsProtocol(Protocol):
    """Protocol for general prometheus metrics settings."""

    @property
    def prefix(self) -> str | None:
        """Metric prefix."""
        ...

    @property
    def enabled(self) -> bool:
        """Whether metrics are enabled."""
        ...


@runtime_checkable
class PostgresMetricsSettingsProtocol(Protocol):
    """Protocol for Postgres settings that have metrics_enabled flag."""

    @property
    def metrics_enabled(self) -> bool:
        """Whether infrastructure metrics are enabled."""
        ...


class BaseMetricsProvider(BaseDishkaProvider):
    """Base provider for metrics with helper for optional infra name prefix."""

    scope = Scope.APP

    @staticmethod
    def _infra_metrics_prefix(default_prefix: str | None) -> str | None:
        """Resolve prefix from the app (``get_default_prefix`` → ``str | None``).

        ``None`` or whitespace-only string means no prefix for underlying metrics classes.
        This intentionally does **not** read ``PrometheusMetricsSettingsProtocol.prefix`` so
        service-level ``METRICS__PREFIX`` can target business metrics only.
        """
        if default_prefix is None:
            return None
        stripped = default_prefix.strip()
        return stripped if stripped else None


try:
    from ...contrib.metrics import PostgresMetrics

    class PrometheusPostgresMetricsProvider(BaseMetricsProvider):
        """Provider for Prometheus PostgreSQL metrics."""

        @provide
        def get_metrics(
            self,
            metrics: PrometheusMetricsSettingsProtocol,
            default_prefix: str | None,
            postgres: PostgresMetricsSettingsProtocol | None = None,
        ) -> PostgresMetricsProtocol | None:
            """Provide Postgres metrics implementing PostgresMetricsProtocol."""
            if postgres is None or not postgres.metrics_enabled:
                return None
            return PostgresMetrics(prefix=self._infra_metrics_prefix(default_prefix))

except ImportError:  # pragma: no cover
    PrometheusPostgresMetricsProvider = None  # type: ignore[misc,assignment]


__all__ = [
    "BaseMetricsProvider",
    "PostgresMetricsSettingsProtocol",
    "PrometheusMetricsSettingsProtocol",
    "PrometheusPostgresMetricsProvider",
]
