"""Unit tests for custom connection class."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from sqlalchemy_foundation_kit.session.connection import AsyncCConnection

# ============================================================================
# AsyncCConnection Tests
# ============================================================================


def test__async_c_connection__is_subclass_of_asyncpg_connection() -> None:
    # Arrange & Act
    import asyncpg

    # Assert
    assert issubclass(AsyncCConnection, asyncpg.Connection)


def test__async_c_connection__get_unique_id__format_correct() -> None:
    # Arrange
    connection = Mock(spec=AsyncCConnection)
    prefix = "test"

    # Act
    result = AsyncCConnection._get_unique_id(connection, prefix)

    # Assert
    assert isinstance(result, str)
    assert prefix in result
    assert "__asyncpg_" in result
    assert result.startswith("__asyncpg_")
    assert result.endswith("__")


def test__async_c_connection__get_unique_id__contains_uuid() -> None:
    # Arrange
    connection = Mock(spec=AsyncCConnection)
    prefix = "test"

    # Act
    result = AsyncCConnection._get_unique_id(connection, prefix)

    # Assert
    # UUID format: 8-4-4-4-12 hex digits separated by hyphens
    parts = result.split("_")
    # Should have __asyncpg, prefix, uuid parts
    assert len(parts) >= 3


def test__async_c_connection__get_unique_id__different_prefixes__different_results() -> None:
    # Arrange
    connection = Mock(spec=AsyncCConnection)

    # Act
    result1 = AsyncCConnection._get_unique_id(connection, "prefix1")
    result2 = AsyncCConnection._get_unique_id(connection, "prefix2")

    # Assert
    assert "prefix1" in result1
    assert "prefix2" in result2
    assert result1 != result2


def test__async_c_connection__get_unique_id__multiple_calls__unique_ids() -> None:
    # Arrange
    connection = Mock(spec=AsyncCConnection)
    prefix = "test"

    # Act
    result1 = AsyncCConnection._get_unique_id(connection, prefix)
    result2 = AsyncCConnection._get_unique_id(connection, prefix)
    result3 = AsyncCConnection._get_unique_id(connection, prefix)

    # Assert
    assert result1 != result2
    assert result2 != result3
    assert result1 != result3


@pytest.mark.parametrize(
    "prefix",
    [
        "",  # empty
        "very_long_prefix_with_many_characters",  # long
        "test-prefix.123",  # special characters
        "stmt",  # normal
    ],
)
def test__async_c_connection__get_unique_id__various_prefixes__work(prefix: str) -> None:
    # Arrange
    connection = Mock(spec=AsyncCConnection)

    # Act
    result = AsyncCConnection._get_unique_id(connection, prefix)

    # Assert
    assert isinstance(result, str)
    assert "__asyncpg_" in result
    if prefix:  # Only check prefix presence if non-empty
        assert prefix in result


@patch("sqlalchemy_foundation_kit.session.connection.uuid.uuid4")
def test__async_c_connection__get_unique_id__uses_uuid4(mock_uuid4: Mock) -> None:
    # Arrange
    mock_uuid4.return_value = "test-uuid-1234"
    connection = Mock(spec=AsyncCConnection)
    prefix = "test"

    # Act
    result = AsyncCConnection._get_unique_id(connection, prefix)

    # Assert
    mock_uuid4.assert_called_once()
    assert "test-uuid-1234" in result


def test__async_c_connection__get_unique_id__thread_safe_uniqueness() -> None:
    # Arrange
    connection = Mock(spec=AsyncCConnection)
    prefix = "concurrent"
    results = set()

    # Act
    for _ in range(100):
        result = AsyncCConnection._get_unique_id(connection, prefix)
        results.add(result)

    # Assert
    # All 100 IDs should be unique
    assert len(results) == 100


@pytest.mark.parametrize(
    "obj,expected_keyword",
    [
        (AsyncCConnection, "pgbouncer"),
        (AsyncCConnection._get_unique_id, "unique"),
    ],
)
def test__async_c_connection__docstrings__exist(obj: object, expected_keyword: str) -> None:
    # Arrange & Act
    docstring = obj.__doc__

    # Assert
    assert docstring is not None
    assert expected_keyword in docstring.lower()
