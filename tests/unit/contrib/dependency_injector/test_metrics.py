"""Unit tests for dependency-injector metrics providers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.mark.unit
def test___create_postgres_metrics__postgres_settings_none__returns_none() -> None:
    """Test that _create_postgres_metrics returns None when postgres_settings is None."""
    # Arrange
    from sqlalchemy_foundation_kit.contrib.dependency_injector.metrics import _create_postgres_metrics

    mock_metrics_settings = MagicMock()
    default_prefix = "test"

    # Act
    result = _create_postgres_metrics(mock_metrics_settings, default_prefix, postgres_settings=None)

    # Assert
    assert result is None


@pytest.mark.unit
def test___create_postgres_metrics__metrics_disabled__returns_none() -> None:
    """Test that _create_postgres_metrics returns None when metrics_enabled is False."""
    # Arrange
    from sqlalchemy_foundation_kit.contrib.dependency_injector.metrics import _create_postgres_metrics

    mock_metrics_settings = MagicMock()
    mock_postgres_settings = MagicMock()
    mock_postgres_settings.metrics_enabled = False
    default_prefix = "test"

    # Act
    result = _create_postgres_metrics(mock_metrics_settings, default_prefix, mock_postgres_settings)

    # Assert
    assert result is None


@pytest.mark.unit
def test___create_postgres_metrics__metrics_enabled__returns_metrics() -> None:
    """Test that _create_postgres_metrics returns PostgresMetrics when metrics_enabled is True."""
    # Arrange
    from sqlalchemy_foundation_kit.contrib.dependency_injector.metrics import _create_postgres_metrics

    mock_metrics_settings = MagicMock()
    mock_postgres_settings = MagicMock()
    mock_postgres_settings.metrics_enabled = True
    default_prefix = "test"

    # Act
    result = _create_postgres_metrics(mock_metrics_settings, default_prefix, mock_postgres_settings)

    # Assert
    assert result is not None
