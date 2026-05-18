"""Unit tests for BaseDishkaProvider."""

from __future__ import annotations

from unittest.mock import patch

import pytest

# ============================================================================
# BaseDishkaProvider Subclass Creation Tests
# ============================================================================


@pytest.mark.unit
def test__base_dishka_provider__subclass_without_dishka__raises_error() -> None:
    # Arrange
    with patch("sqlalchemy_foundation_kit.contrib.di._deps.HAS_DISHKA", False):
        from sqlalchemy_foundation_kit.contrib.di._base import BaseDishkaProvider

        # Act & Assert
        with pytest.raises(ImportError, match="dishka is required"):

            class TestProvider(BaseDishkaProvider):
                pass


@pytest.mark.unit
def test__base_dishka_provider__init_without_dishka__raises_error() -> None:
    # Arrange
    mock_base_class = type(
        "MockProvider", (), {"__init__": lambda self: None, "__init_subclass__": lambda **kwargs: None}
    )

    with patch("sqlalchemy_foundation_kit.contrib.di._deps.HAS_DISHKA", True):
        with patch("sqlalchemy_foundation_kit.contrib.di._deps.Provider", mock_base_class):
            from sqlalchemy_foundation_kit.contrib.di._base import BaseDishkaProvider

            class TestProvider(BaseDishkaProvider):
                pass

            # Now patch it to False for instantiation
            with patch("sqlalchemy_foundation_kit.contrib.di._deps.HAS_DISHKA", False):
                with pytest.raises(ImportError, match="dishka is required"):
                    TestProvider()
