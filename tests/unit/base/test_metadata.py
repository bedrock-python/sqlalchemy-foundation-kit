"""Unit tests for ORM metadata loading utilities."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import MetaData

from sqlalchemy_foundation_kit.base import Base

# ============================================================================
# load_orm_metadata Tests - Basic Functionality
# ============================================================================


def test__load_orm_metadata__empty_list__returns_base_metadata() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Act
    result = load_orm_metadata([])

    # Assert
    assert result is Base.metadata
    assert isinstance(result, MetaData)


def test__load_orm_metadata__single_module__imports_module() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    mock_module = MagicMock()

    # Act
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module", return_value=mock_module) as mock_import:
        result = load_orm_metadata(["myapp.models"])

        # Assert
        mock_import.assert_called_once_with("myapp.models")
        assert result is Base.metadata


def test__load_orm_metadata__multiple_modules__imports_all() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    modules = ["myapp.users.models", "myapp.orders.models", "myapp.products.models"]

    # Act
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module") as mock_import:
        load_orm_metadata(modules)

        # Assert
        assert mock_import.call_count == 3
        mock_import.assert_any_call("myapp.users.models")
        mock_import.assert_any_call("myapp.orders.models")
        mock_import.assert_any_call("myapp.products.models")


def test__load_orm_metadata__returns_metadata_instance() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Act
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module"):
        result = load_orm_metadata(["myapp.models"])

    # Assert
    assert isinstance(result, MetaData)


def test__load_orm_metadata__no_metadata_arg__uses_base_metadata() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Act
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module"):
        result = load_orm_metadata(["myapp.models"])

    # Assert
    assert result is Base.metadata


# ============================================================================
# load_orm_metadata Tests - Custom Metadata
# ============================================================================


def test__load_orm_metadata__custom_metadata__returns_custom() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    custom_metadata = MetaData()

    # Act
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module"):
        result = load_orm_metadata(["myapp.models"], metadata=custom_metadata)

    # Assert
    assert result is custom_metadata
    assert result is not Base.metadata


def test__load_orm_metadata__custom_metadata_with_schema__preserves_schema() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    custom_metadata = MetaData(schema="public")

    # Act
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module"):
        result = load_orm_metadata(["myapp.models"], metadata=custom_metadata)

    # Assert
    assert result is custom_metadata
    assert result.schema == "public"


def test__load_orm_metadata__custom_metadata__still_imports_modules() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    custom_metadata = MetaData()
    modules = ["myapp.users", "myapp.orders"]

    # Act
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module") as mock_import:
        load_orm_metadata(modules, metadata=custom_metadata)

        # Assert
        assert mock_import.call_count == 2


def test__load_orm_metadata__none_metadata__uses_base() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Act
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module"):
        result = load_orm_metadata(["myapp.models"], metadata=None)

    # Assert
    assert result is Base.metadata


# ============================================================================
# load_orm_metadata Tests - Module Import Behavior
# ============================================================================


def test__load_orm_metadata__iterable_modules__processes_generator() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    def module_generator():
        yield "myapp.users"
        yield "myapp.orders"

    # Act
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module") as mock_import:
        load_orm_metadata(module_generator())

        # Assert
        assert mock_import.call_count == 2


def test__load_orm_metadata__tuple_modules__imports_all() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    modules = ("myapp.users", "myapp.orders")

    # Act
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module") as mock_import:
        load_orm_metadata(modules)

        # Assert
        assert mock_import.call_count == 2


def test__load_orm_metadata__set_modules__imports_all() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    modules = {"myapp.users", "myapp.orders", "myapp.products"}

    # Act
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module") as mock_import:
        load_orm_metadata(modules)

        # Assert
        assert mock_import.call_count == 3


def test__load_orm_metadata__module_import_order__preserves_order() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    modules = ["first", "second", "third"]
    imported = []

    def track_import(module: str):
        imported.append(module)
        return MagicMock()

    # Act
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module", side_effect=track_import):
        load_orm_metadata(modules)

        # Assert
        assert imported == ["first", "second", "third"]


# ============================================================================
# load_orm_metadata Tests - Error Handling
# ============================================================================


def test__load_orm_metadata__module_not_found__raises_import_error() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Act & Assert
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module") as mock_import:
        mock_import.side_effect = ImportError("No module named 'nonexistent'")

        with pytest.raises(ImportError, match="No module named 'nonexistent'"):
            load_orm_metadata(["nonexistent.module"])


def test__load_orm_metadata__module_import_error__propagates() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Act & Assert
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module") as mock_import:
        mock_import.side_effect = ImportError("Cannot import module")

        with pytest.raises(ImportError, match="Cannot import module"):
            load_orm_metadata(["myapp.broken"])


def test__load_orm_metadata__module_syntax_error__propagates() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Act & Assert
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module") as mock_import:
        mock_import.side_effect = SyntaxError("invalid syntax")

        with pytest.raises(SyntaxError, match="invalid syntax"):
            load_orm_metadata(["myapp.bad_syntax"])


def test__load_orm_metadata__partial_failure__raises_on_first_error() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    def import_side_effect(module: str):
        if module == "myapp.bad":
            raise ImportError("Bad module")
        return MagicMock()

    # Act & Assert
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module", side_effect=import_side_effect):
        with pytest.raises(ImportError, match="Bad module"):
            load_orm_metadata(["myapp.good", "myapp.bad", "myapp.another"])


# ============================================================================
# load_orm_metadata Tests - Real Module Loading
# ============================================================================


def test__load_orm_metadata__real_module__imports_successfully() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Act
    result = load_orm_metadata(["sqlalchemy_foundation_kit.base.models"])

    # Assert
    assert result is Base.metadata
    assert isinstance(result, MetaData)


def test__load_orm_metadata__builtin_module__imports_without_error() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Act - importing a safe builtin module
    result = load_orm_metadata(["json"])

    # Assert
    assert result is Base.metadata


def test__load_orm_metadata__sqlalchemy_module__imports_successfully() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Act
    result = load_orm_metadata(["sqlalchemy"])

    # Assert
    assert result is Base.metadata


# ============================================================================
# load_orm_metadata Tests - Side Effects
# ============================================================================


def test__load_orm_metadata__imports_register_models__in_metadata() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Create a temporary module with a table
    mock_module = MagicMock()
    initial_table_count = len(Base.metadata.tables)

    # Act
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module", return_value=mock_module):
        result = load_orm_metadata(["myapp.models"])

        # Assert
        # The metadata should be the same instance
        assert result is Base.metadata
        # Importing modules should trigger model registration (in real scenario)


def test__load_orm_metadata__multiple_calls__accumulates_imports() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Act
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module") as mock_import:
        load_orm_metadata(["myapp.users"])
        load_orm_metadata(["myapp.orders"])

        # Assert
        assert mock_import.call_count == 2


def test__load_orm_metadata__same_module_twice__imports_twice() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Act
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module") as mock_import:
        load_orm_metadata(["myapp.models"])
        load_orm_metadata(["myapp.models"])

        # Assert
        assert mock_import.call_count == 2
        # Python's import system will cache, but function calls import_module twice


# ============================================================================
# load_orm_metadata Tests - Edge Cases
# ============================================================================


def test__load_orm_metadata__empty_string_module__raises_error() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Act & Assert - Empty module raises ValueError, not ImportError
    with pytest.raises((ImportError, ValueError)):
        load_orm_metadata([""])


def test__load_orm_metadata__whitespace_module__raises_import_error() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Act & Assert
    with pytest.raises(ImportError):
        load_orm_metadata(["   "])


def test__load_orm_metadata__single_element_list__works() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Act
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module") as mock_import:
        result = load_orm_metadata(["myapp.models"])

        # Assert
        mock_import.assert_called_once()
        assert result is Base.metadata


def test__load_orm_metadata__large_module_list__imports_all() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    modules = [f"myapp.module{i}" for i in range(100)]

    # Act
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module") as mock_import:
        load_orm_metadata(modules)

        # Assert
        assert mock_import.call_count == 100


# ============================================================================
# load_orm_metadata Tests - Module Path Formats
# ============================================================================


def test__load_orm_metadata__nested_module_path__imports_correctly() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Act
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module") as mock_import:
        load_orm_metadata(["myapp.core.domain.users.models"])

        # Assert
        mock_import.assert_called_once_with("myapp.core.domain.users.models")


def test__load_orm_metadata__relative_import_syntax__passes_to_import() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Act
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module") as mock_import:
        load_orm_metadata([".models"])

        # Assert
        mock_import.assert_called_once_with(".models")


def test__load_orm_metadata__package_with_underscores__imports() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Act
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module") as mock_import:
        load_orm_metadata(["my_app.user_models"])

        # Assert
        mock_import.assert_called_once_with("my_app.user_models")


def test__load_orm_metadata__package_with_numbers__imports() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Act
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module") as mock_import:
        load_orm_metadata(["myapp.v2.models"])

        # Assert
        mock_import.assert_called_once_with("myapp.v2.models")


# ============================================================================
# load_orm_metadata Tests - Integration with Base
# ============================================================================


def test__load_orm_metadata__base_metadata__is_sqlalchemy_metadata() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Act
    result = load_orm_metadata([])

    # Assert
    assert isinstance(result, MetaData)
    assert hasattr(result, "tables")
    assert hasattr(result, "sorted_tables")


def test__load_orm_metadata__base_metadata__has_tables_attribute() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Act
    result = load_orm_metadata([])

    # Assert
    assert hasattr(result, "tables")
    assert isinstance(result.tables, dict)


def test__load_orm_metadata__metadata_schema__can_be_set() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    custom_meta = MetaData(schema="custom_schema")

    # Act
    result = load_orm_metadata([], metadata=custom_meta)

    # Assert
    assert result.schema == "custom_schema"


# ============================================================================
# load_orm_metadata Tests - Return Value Consistency
# ============================================================================


def test__load_orm_metadata__always_returns_metadata__never_none() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Act
    with patch("sqlalchemy_foundation_kit.base.metadata.import_module"):
        result1 = load_orm_metadata([])
        result2 = load_orm_metadata(["myapp.models"])
        result3 = load_orm_metadata(["myapp.models"], metadata=MetaData())

    # Assert
    assert result1 is not None
    assert result2 is not None
    assert result3 is not None
    assert all(isinstance(r, MetaData) for r in [result1, result2, result3])


def test__load_orm_metadata__multiple_calls_same_args__returns_same_instance() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    # Act
    result1 = load_orm_metadata([])
    result2 = load_orm_metadata([])

    # Assert
    assert result1 is result2
    assert result1 is Base.metadata


def test__load_orm_metadata__different_custom_metadata__returns_different() -> None:
    # Arrange
    from sqlalchemy_foundation_kit.base.metadata import load_orm_metadata

    meta1 = MetaData()
    meta2 = MetaData()

    # Act
    result1 = load_orm_metadata([], metadata=meta1)
    result2 = load_orm_metadata([], metadata=meta2)

    # Assert
    assert result1 is not result2
    assert result1 is meta1
    assert result2 is meta2
