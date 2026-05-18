"""Metrics containers for dependency-injector."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ...protocols import PostgresMetricsProtocol
from .._metrics_utils import _infra_metrics_prefix
from ._base import BaseDIContainer
from ._deps import providers


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


try:
    from ...contrib.metrics import PostgresMetrics

    def _create_postgres_metrics(
        metrics_settings: PrometheusMetricsSettingsProtocol,
        default_prefix: str | None,
        postgres_settings: PostgresMetricsSettingsProtocol | None,
    ) -> PostgresMetricsProtocol | None:
        """Create Postgres metrics if enabled."""
        if postgres_settings is None or not postgres_settings.metrics_enabled:
            return None
        return PostgresMetrics(prefix=_infra_metrics_prefix(default_prefix))

    class PrometheusMetricsContainer(BaseDIContainer):
        """Container for Prometheus PostgreSQL metrics.

        Provides:
        - postgres_metrics: PostgreSQL metrics collector implementing PostgresMetricsProtocol.

        Configuration:
            - metrics_settings: General prometheus metrics settings (PrometheusMetricsSettingsProtocol).
            - default_prefix: Default prefix for infrastructure metrics (str | None).
            - postgres_settings: PostgreSQL settings with metrics_enabled flag (PostgresMetricsSettingsProtocol).
        """

        # Configuration
        metrics_settings = providers.Dependency()  # type: ignore[misc,var-annotated]
        default_prefix = providers.Dependency()  # type: ignore[misc,var-annotated]
        postgres_settings = providers.Dependency(default=None)  # type: ignore[misc,var-annotated]

        # Postgres metrics
        postgres_metrics = providers.Singleton(  # type: ignore[misc,var-annotated]
            _create_postgres_metrics,
            metrics_settings=metrics_settings,
            default_prefix=default_prefix,
            postgres_settings=postgres_settings,
        )

except ImportError:  # pragma: no cover
    PrometheusMetricsContainer = None  # type: ignore[misc,assignment]
    _create_postgres_metrics = None  # type: ignore[misc,assignment]


__all__ = [
    "PostgresMetricsSettingsProtocol",
    "PrometheusMetricsContainer",
    "PrometheusMetricsSettingsProtocol",
]
