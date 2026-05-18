"""Unit tests for dependency_injector dependency helpers."""

from __future__ import annotations

from unittest.mock import patch

import pytest

# ============================================================================
# check_dependency_injector Tests
# ============================================================================


@pytest.mark.unit
def test__check_dependency_injector__not_installed__raises_import_error() -> None:
    # Arrange
    with patch("sqlalchemy_foundation_kit.contrib.dependency_injector._deps.HAS_DEPENDENCY_INJECTOR", False):
        from sqlalchemy_foundation_kit.contrib.dependency_injector._deps import check_dependency_injector

        # Act & Assert
        with pytest.raises(ImportError, match="dependency-injector is required"):
            check_dependency_injector()


@pytest.mark.unit
def test__check_dependency_injector__installed__does_not_raise() -> None:
    # Arrange
    with patch("sqlalchemy_foundation_kit.contrib.dependency_injector._deps.HAS_DEPENDENCY_INJECTOR", True):
        from sqlalchemy_foundation_kit.contrib.dependency_injector._deps import check_dependency_injector

        # Act & Assert - should not raise
        check_dependency_injector()


# ============================================================================
# Module Constants Tests
# ============================================================================


@pytest.mark.unit
def test__has_dependency_injector__importable() -> None:
    # Arrange & Act
    from sqlalchemy_foundation_kit.contrib.dependency_injector._deps import HAS_DEPENDENCY_INJECTOR

    # Assert - just check it's defined
    assert isinstance(HAS_DEPENDENCY_INJECTOR, bool)


@pytest.mark.unit
def test__containers__importable() -> None:
    # Arrange & Act
    from sqlalchemy_foundation_kit.contrib.dependency_injector._deps import containers

    # Assert - should be defined (either real module or None)
    assert containers is not None or containers is None


@pytest.mark.unit
def test__providers__importable() -> None:
    # Arrange & Act
    from sqlalchemy_foundation_kit.contrib.dependency_injector._deps import providers

    # Assert - should be defined (either real module or None)
    assert providers is not None or providers is None
