"""Unit tests for PostgresMetrics import handling."""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.mark.unit
def test__postgres_metrics__init_without_prometheus__raises_import_error() -> None:
    """Test that PostgresMetrics raises ImportError when prometheus-client is not installed."""
    # Patch HAS_PROMETHEUS to False before importing
    with patch.dict("sys.modules", {"prometheus_client": None}):
        with patch("sqlalchemy_foundation_kit.contrib.metrics.postgres.HAS_PROMETHEUS", False):
            from sqlalchemy_foundation_kit.contrib.metrics.postgres import PostgresMetrics

            # Act & Assert
            with pytest.raises(ImportError, match="prometheus-client is required"):
                PostgresMetrics()


@pytest.mark.unit
def test__check_prometheus__not_installed__raises_import_error() -> None:
    """Test that _check_prometheus raises ImportError when prometheus-client is not installed."""
    # Patch HAS_PROMETHEUS to False
    with patch("sqlalchemy_foundation_kit.contrib.metrics.postgres.HAS_PROMETHEUS", False):
        from sqlalchemy_foundation_kit.contrib.metrics.postgres import _check_prometheus

        # Act & Assert
        with pytest.raises(ImportError, match="prometheus-client is required"):
            _check_prometheus()
