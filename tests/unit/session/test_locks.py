"""Unit tests for PostgreSQL advisory locks."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest

from sqlalchemy_foundation_kit.session.locks import _to_signed64, try_advisory_xact_lock

# ============================================================================
# _to_signed64 Tests
# ============================================================================


def test__to_signed64__positive_number__returns_same() -> None:
    # Arrange & Act
    result = _to_signed64(12345)

    # Assert
    assert result == 12345


def test__to_signed64__zero__returns_zero() -> None:
    # Arrange & Act
    result = _to_signed64(0)

    # Assert
    assert result == 0


def test__to_signed64__negative_number__returns_same() -> None:
    # Arrange & Act
    result = _to_signed64(-12345)

    # Assert
    assert result == -12345


def test__to_signed64__max_positive_int64__returns_max() -> None:
    # Arrange
    max_int64 = 2**63 - 1

    # Act
    result = _to_signed64(max_int64)

    # Assert
    assert result == max_int64


def test__to_signed64__min_negative_int64__returns_min() -> None:
    # Arrange
    min_int64 = -(2**63)

    # Act
    result = _to_signed64(min_int64)

    # Assert
    assert result == min_int64


def test__to_signed64__exceeds_max_int64__wraps_to_negative() -> None:
    # Arrange
    overflow = 2**63

    # Act
    result = _to_signed64(overflow)

    # Assert
    assert result == -(2**63)


def test__to_signed64__exceeds_min_int64__wraps_to_positive() -> None:
    # Arrange
    underflow = -(2**63) - 1

    # Act
    result = _to_signed64(underflow)

    # Assert
    assert result == 2**63 - 1


def test__to_signed64__large_positive__truncates() -> None:
    # Arrange
    large_number = 2**64 + 42

    # Act
    result = _to_signed64(large_number)

    # Assert
    assert result == 42


def test__to_signed64__large_negative__truncates() -> None:
    # Arrange
    large_negative = -(2**64) - 42

    # Act
    result = _to_signed64(large_negative)

    # Assert
    assert result == -42


@pytest.mark.parametrize(
    "input_value,expected_output",
    [
        (1, 1),
        (-1, -1),
        (100, 100),
        (-100, -100),
        (2**32, 2**32),
        (-(2**32), -(2**32)),
    ],
)
def test__to_signed64__various_values__converts(input_value: int, expected_output: int) -> None:
    # Arrange & Act
    result = _to_signed64(input_value)

    # Assert
    assert result == expected_output


def test__to_signed64__boundary_plus_one__wraps() -> None:
    # Arrange
    boundary_plus_one = 2**63 + 1

    # Act
    result = _to_signed64(boundary_plus_one)

    # Assert
    assert result == -(2**63) + 1


def test__to_signed64__boundary_minus_one__within_range() -> None:
    # Arrange
    boundary_minus_one = 2**63 - 2

    # Act
    result = _to_signed64(boundary_minus_one)

    # Assert
    assert result == 2**63 - 2


def test__to_signed64__very_large__handles_correctly() -> None:
    # Arrange
    very_large = 10**20

    # Act
    result = _to_signed64(very_large)

    # Assert
    assert -(2**63) <= result <= (2**63 - 1)


def test__to_signed64__idempotent() -> None:
    # Arrange
    value = 12345

    # Act
    result1 = _to_signed64(value)
    result2 = _to_signed64(value)

    # Assert
    assert result1 == result2


# ============================================================================
# try_advisory_xact_lock Tests
# ============================================================================


@pytest.mark.asyncio
async def test__try_advisory_xact_lock__lock_acquired__returns_true() -> None:
    # Arrange
    mock_result = Mock()
    mock_result.scalar.return_value = True

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Act
    result = await try_advisory_xact_lock(mock_session, 12345)

    # Assert
    assert result is True
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test__try_advisory_xact_lock__lock_not_acquired__returns_false() -> None:
    # Arrange
    mock_result = Mock()
    mock_result.scalar.return_value = False

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Act
    result = await try_advisory_xact_lock(mock_session, 99999)

    # Assert
    assert result is False


@pytest.mark.asyncio
async def test__try_advisory_xact_lock__calls_correct_sql() -> None:
    # Arrange
    mock_result = Mock()
    mock_result.scalar.return_value = True

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Act
    await try_advisory_xact_lock(mock_session, 42)

    # Assert
    call_args = mock_session.execute.call_args
    sql_statement = call_args[0][0]
    params = call_args[0][1]

    assert "pg_try_advisory_xact_lock" in str(sql_statement)
    assert params["k"] == 42


@pytest.mark.asyncio
async def test__try_advisory_xact_lock__large_key__truncates() -> None:
    # Arrange
    mock_result = Mock()
    mock_result.scalar.return_value = True

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    large_key = 2**63 + 1000

    # Act
    await try_advisory_xact_lock(mock_session, large_key)

    # Assert
    call_args = mock_session.execute.call_args
    params = call_args[0][1]

    expected_truncated = _to_signed64(large_key)
    assert params["k"] == expected_truncated


@pytest.mark.asyncio
async def test__try_advisory_xact_lock__negative_key__converts() -> None:
    # Arrange
    mock_result = Mock()
    mock_result.scalar.return_value = True

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Act
    await try_advisory_xact_lock(mock_session, -12345)

    # Assert
    call_args = mock_session.execute.call_args
    params = call_args[0][1]

    assert params["k"] == -12345


@pytest.mark.asyncio
async def test__try_advisory_xact_lock__zero_key__works() -> None:
    # Arrange
    mock_result = Mock()
    mock_result.scalar.return_value = True

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Act
    result = await try_advisory_xact_lock(mock_session, 0)

    # Assert
    assert result is True
    call_args = mock_session.execute.call_args
    params = call_args[0][1]
    assert params["k"] == 0


@pytest.mark.asyncio
async def test__try_advisory_xact_lock__scalar_returns_none__returns_false() -> None:
    # Arrange
    mock_result = Mock()
    mock_result.scalar.return_value = None

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Act
    result = await try_advisory_xact_lock(mock_session, 123)

    # Assert
    assert result is False


@pytest.mark.asyncio
async def test__try_advisory_xact_lock__scalar_returns_truthy__returns_true() -> None:
    # Arrange
    mock_result = Mock()
    mock_result.scalar.return_value = 1

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Act
    result = await try_advisory_xact_lock(mock_session, 456)

    # Assert
    assert result is True


@pytest.mark.asyncio
async def test__try_advisory_xact_lock__multiple_calls__independent() -> None:
    # Arrange
    mock_result1 = Mock()
    mock_result1.scalar.return_value = True

    mock_result2 = Mock()
    mock_result2.scalar.return_value = False

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=[mock_result1, mock_result2])

    # Act
    result1 = await try_advisory_xact_lock(mock_session, 111)
    result2 = await try_advisory_xact_lock(mock_session, 222)

    # Assert
    assert result1 is True
    assert result2 is False
    assert mock_session.execute.call_count == 2


@pytest.mark.parametrize(
    "key",
    [1, 1000, 999999, 2**32, 2**63 - 1, -(2**63), -1, -1000],
)
@pytest.mark.asyncio
async def test__try_advisory_xact_lock__range_of_keys__all_work(key: int) -> None:
    # Arrange
    mock_result = Mock()
    mock_result.scalar.return_value = True

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    # Act
    result = await try_advisory_xact_lock(mock_session, key)

    # Assert
    assert result is True
    call_args = mock_session.execute.call_args
    params = call_args[0][1]
    assert -(2**63) <= params["k"] <= (2**63 - 1)
