"""Shared helpers for metrics providers."""

from __future__ import annotations


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


__all__ = ["_infra_metrics_prefix"]
