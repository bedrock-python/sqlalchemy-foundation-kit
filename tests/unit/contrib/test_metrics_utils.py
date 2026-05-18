"""Unit tests for _metrics_utils module."""

from __future__ import annotations

import pytest

from sqlalchemy_foundation_kit.contrib._metrics_utils import _infra_metrics_prefix

# ============================================================================
# _infra_metrics_prefix Tests
# ============================================================================


@pytest.mark.unit
def test___infra_metrics_prefix__none__returns_none() -> None:
    # Arrange
    default_prefix = None

    # Act
    result = _infra_metrics_prefix(default_prefix)

    # Assert
    assert result is None


@pytest.mark.unit
def test___infra_metrics_prefix__valid_prefix__returns_prefix() -> None:
    # Arrange
    default_prefix = "my_service"

    # Act
    result = _infra_metrics_prefix(default_prefix)

    # Assert
    assert result == "my_service"


@pytest.mark.unit
def test___infra_metrics_prefix__empty_string__returns_none() -> None:
    # Arrange
    default_prefix = ""

    # Act
    result = _infra_metrics_prefix(default_prefix)

    # Assert
    assert result is None


@pytest.mark.unit
def test___infra_metrics_prefix__whitespace_only__returns_none() -> None:
    # Arrange
    default_prefix = "   "

    # Act
    result = _infra_metrics_prefix(default_prefix)

    # Assert
    assert result is None


@pytest.mark.unit
def test___infra_metrics_prefix__whitespace_with_text__returns_stripped() -> None:
    # Arrange
    default_prefix = "  my_service  "

    # Act
    result = _infra_metrics_prefix(default_prefix)

    # Assert
    assert result == "my_service"


@pytest.mark.unit
def test___infra_metrics_prefix__tabs_only__returns_none() -> None:
    # Arrange
    default_prefix = "\t\t"

    # Act
    result = _infra_metrics_prefix(default_prefix)

    # Assert
    assert result is None


@pytest.mark.unit
def test___infra_metrics_prefix__newlines_only__returns_none() -> None:
    # Arrange
    default_prefix = "\n\n"

    # Act
    result = _infra_metrics_prefix(default_prefix)

    # Assert
    assert result is None
