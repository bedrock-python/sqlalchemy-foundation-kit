"""Unit tests for BaseDIContainer."""

from __future__ import annotations

from unittest.mock import patch

import pytest

# ============================================================================
# BaseDIContainer Subclass Creation Tests
# ============================================================================


@pytest.mark.unit
def test__base_di_container__subclass_without_dependency_injector__raises_error() -> None:
    # Arrange
    with patch("sqlalchemy_foundation_kit.contrib.dependency_injector._deps.HAS_DEPENDENCY_INJECTOR", False):
        from sqlalchemy_foundation_kit.contrib.dependency_injector._base import BaseDIContainer

        # Act & Assert
        with pytest.raises(ImportError, match="dependency-injector is required"):

            class TestContainer(BaseDIContainer):  # type: ignore[misc]
                pass
