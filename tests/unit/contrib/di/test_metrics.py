"""Unit tests for dishka metrics providers."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest


def _unique_prefix() -> str:
    """Generate unique prefix to avoid prometheus registry conflicts."""
    return f"test_{uuid.uuid4().hex[:8]}"


@pytest.mark.unit
def test__prometheus_postgres_metrics_provider__get_metrics_postgres_none__returns_none() -> None:
    """Test that get_metrics returns None when postgres settings is None."""
    # Arrange
    mock_base_init = MagicMock()

    with patch("sqlalchemy_foundation_kit.contrib.di._deps.HAS_DISHKA", True):
        with patch("sqlalchemy_foundation_kit.contrib.di._deps.Provider.__init__", mock_base_init):
            from sqlalchemy_foundation_kit.contrib.di.metrics import PrometheusPostgresMetricsProvider

            provider = PrometheusPostgresMetricsProvider()
            mock_metrics_settings = MagicMock()
            default_prefix = "test"

            # Act
            result = provider.get_metrics(mock_metrics_settings, default_prefix, postgres=None)

            # Assert
            assert result is None


@pytest.mark.unit
def test__prometheus_postgres_metrics_provider__get_metrics_disabled__returns_none() -> None:
    """Test that get_metrics returns None when metrics_enabled is False."""
    # Arrange
    mock_base_init = MagicMock()

    with patch("sqlalchemy_foundation_kit.contrib.di._deps.HAS_DISHKA", True):
        with patch("sqlalchemy_foundation_kit.contrib.di._deps.Provider.__init__", mock_base_init):
            from sqlalchemy_foundation_kit.contrib.di.metrics import PrometheusPostgresMetricsProvider

            provider = PrometheusPostgresMetricsProvider()
            mock_metrics_settings = MagicMock()
            mock_postgres_settings = MagicMock()
            mock_postgres_settings.metrics_enabled = False
            default_prefix = "test"

            # Act
            result = provider.get_metrics(mock_metrics_settings, default_prefix, mock_postgres_settings)

            # Assert
            assert result is None


@pytest.mark.unit
def test__prometheus_postgres_metrics_provider__get_metrics_enabled__returns_metrics() -> None:
    """Test that get_metrics returns PostgresMetrics when metrics_enabled is True."""
    # Arrange
    mock_base_init = MagicMock()

    with patch("sqlalchemy_foundation_kit.contrib.di._deps.HAS_DISHKA", True):
        with patch("sqlalchemy_foundation_kit.contrib.di._deps.Provider.__init__", mock_base_init):
            from sqlalchemy_foundation_kit.contrib.di.metrics import PrometheusPostgresMetricsProvider

            provider = PrometheusPostgresMetricsProvider()
            mock_metrics_settings = MagicMock()
            mock_postgres_settings = MagicMock()
            mock_postgres_settings.metrics_enabled = True
            default_prefix = _unique_prefix()  # Use unique prefix to avoid registry conflicts

            # Act
            result = provider.get_metrics(mock_metrics_settings, default_prefix, mock_postgres_settings)

            # Assert
            assert result is not None
