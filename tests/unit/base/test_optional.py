"""Tests for base._optional module."""

from __future__ import annotations

import pytest

from sqlalchemy_foundation_kit.base._optional import require_optional


def test__require_optional__module_exists__returns_module() -> None:
    """Test require_optional with existing module."""
    module = require_optional("os", "core")
    assert module.__name__ == "os"


def test__require_optional__module_not_found__raises_import_error() -> None:
    """Test require_optional with non-existent module."""
    with pytest.raises(ImportError) as exc_info:
        require_optional("nonexistent_module_xyz", "extra-name")

    assert "nonexistent_module_xyz is required" in str(exc_info.value)
    assert "pip install 'sqlalchemy-foundation-kit[extra-name]'" in str(exc_info.value)


def test__require_optional__preserves_original_error() -> None:
    """Test require_optional preserves original ImportError."""
    with pytest.raises(ImportError) as exc_info:
        require_optional("this_module_does_not_exist_123", "test")

    assert exc_info.value.__cause__ is not None
    assert isinstance(exc_info.value.__cause__, ImportError)
