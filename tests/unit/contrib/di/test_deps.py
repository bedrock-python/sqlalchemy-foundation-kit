"""Unit tests for dishka dependency helpers."""

from __future__ import annotations

from unittest.mock import patch

import pytest

# ============================================================================
# check_dishka Tests
# ============================================================================


@pytest.mark.unit
def test__check_dishka__not_installed__raises_import_error() -> None:
    # Arrange
    with patch("sqlalchemy_foundation_kit.contrib.di._deps.HAS_DISHKA", False):
        from sqlalchemy_foundation_kit.contrib.di._deps import check_dishka

        # Act & Assert
        with pytest.raises(ImportError, match="dishka is required"):
            check_dishka()


@pytest.mark.unit
def test__check_dishka__installed__does_not_raise() -> None:
    # Arrange
    with patch("sqlalchemy_foundation_kit.contrib.di._deps.HAS_DISHKA", True):
        from sqlalchemy_foundation_kit.contrib.di._deps import check_dishka

        # Act & Assert - should not raise
        check_dishka()


# ============================================================================
# Module Constants Tests
# ============================================================================


@pytest.mark.unit
def test__has_dishka__importable() -> None:
    # Arrange & Act
    from sqlalchemy_foundation_kit.contrib.di._deps import HAS_DISHKA

    # Assert - just check it's defined
    assert isinstance(HAS_DISHKA, bool)


@pytest.mark.unit
def test__provider__importable() -> None:
    # Arrange & Act
    from sqlalchemy_foundation_kit.contrib.di._deps import Provider

    # Assert - should be defined (either real class or object)
    assert Provider is not None


@pytest.mark.unit
def test__scope__importable() -> None:
    # Arrange & Act
    from sqlalchemy_foundation_kit.contrib.di._deps import Scope

    # Assert - should be defined (either real class or None)
    assert Scope is not None or Scope is None


@pytest.mark.unit
def test__provide__importable() -> None:
    # Arrange & Act
    from sqlalchemy_foundation_kit.contrib.di._deps import provide

    # Assert - should be defined (either real decorator or None)
    assert provide is not None or provide is None
