"""Unit tests for database connection retry utilities."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from sqlalchemy_foundation_kit.session.retry import (
    DEFAULT_HEALTHCHECK_QUERY,
    DEFAULT_RETRY_CONFIG,
    RetryConfig,
    retry_async_connection,
)

# ============================================================================
# DEFAULT_HEALTHCHECK_QUERY Tests
# ============================================================================


def test__default_healthcheck_query__is_select_1() -> None:
    # Arrange & Act & Assert
    assert DEFAULT_HEALTHCHECK_QUERY == "SELECT 1"


# ============================================================================
# RetryConfig Tests
# ============================================================================


@pytest.mark.parametrize(
    "max_retries,retry_delay,max_backoff_delay",
    [
        (3, 1.0, 60.0),  # defaults
        (5, 2.0, 120.0),  # custom
        (0, 0.001, 10.0),  # edge case
    ],
)
def test__retry_config__values__stored_correctly(
    max_retries: int, retry_delay: float, max_backoff_delay: float
) -> None:
    # Arrange & Act
    config = RetryConfig(
        max_retries=max_retries,
        retry_delay=retry_delay,
        max_backoff_delay=max_backoff_delay,
    )

    # Assert
    assert config.max_retries == max_retries
    assert config.retry_delay == retry_delay
    assert config.max_backoff_delay == max_backoff_delay


def test__retry_config__is_frozen__immutable() -> None:
    # Arrange
    config = RetryConfig()

    # Act & Assert
    with pytest.raises(AttributeError):
        config.max_retries = 10  # type: ignore


# ============================================================================
# DEFAULT_RETRY_CONFIG Tests
# ============================================================================


def test__default_retry_config__is_retry_config_instance() -> None:
    # Arrange & Act & Assert
    assert isinstance(DEFAULT_RETRY_CONFIG, RetryConfig)


def test__default_retry_config__has_default_values() -> None:
    # Arrange & Act & Assert
    assert DEFAULT_RETRY_CONFIG.max_retries == 3
    assert DEFAULT_RETRY_CONFIG.retry_delay == 1.0
    assert DEFAULT_RETRY_CONFIG.max_backoff_delay == 60.0


# ============================================================================
# retry_async_connection - Success Tests
# ============================================================================


@pytest.mark.asyncio
async def test__retry_async_connection__success_on_first_attempt__logs_success() -> None:
    # Arrange
    connect_func = AsyncMock()

    # Act
    with patch("sqlalchemy_foundation_kit.session.retry.logger") as mock_logger:
        await retry_async_connection(connect_func, "test-service")

    # Assert
    connect_func.assert_called_once()
    mock_logger.info.assert_called_once_with("%s connection successful", "test-service")
    mock_logger.warning.assert_not_called()
    mock_logger.exception.assert_not_called()


@pytest.mark.asyncio
async def test__retry_async_connection__success_on_first_attempt__returns_none() -> None:
    # Arrange
    connect_func = AsyncMock()

    # Act
    result = await retry_async_connection(connect_func, "test-service")

    # Assert
    assert result is None


# ============================================================================
# retry_async_connection - Retry Tests
# ============================================================================


@pytest.mark.asyncio
async def test__retry_async_connection__fails_once_then_succeeds__retries_and_logs() -> None:
    # Arrange
    connect_func = AsyncMock(side_effect=[Exception("Connection failed"), None])

    # Act
    with patch("sqlalchemy_foundation_kit.session.retry.logger") as mock_logger:
        with patch("sqlalchemy_foundation_kit.session.retry.asyncio.sleep") as mock_sleep:
            await retry_async_connection(connect_func, "test-service")

    # Assert
    assert connect_func.call_count == 2
    mock_logger.warning.assert_called_once_with("%s connection attempt %d failed, retrying...", "test-service", 1)
    mock_logger.info.assert_called_once_with("%s connection successful", "test-service")
    mock_sleep.assert_called_once_with(1.0)  # retry_delay * 2^0


@pytest.mark.asyncio
async def test__retry_async_connection__fails_twice_then_succeeds__logs_two_warnings() -> None:
    # Arrange
    connect_func = AsyncMock(side_effect=[Exception("Failed 1"), Exception("Failed 2"), None])

    # Act
    with patch("sqlalchemy_foundation_kit.session.retry.logger") as mock_logger:
        with patch("sqlalchemy_foundation_kit.session.retry.asyncio.sleep"):
            await retry_async_connection(connect_func, "test-service")

    # Assert
    assert connect_func.call_count == 3
    assert mock_logger.warning.call_count == 2


@pytest.mark.asyncio
async def test__retry_async_connection__exponential_backoff__calculates_correctly() -> None:
    # Arrange
    connect_func = AsyncMock(side_effect=[Exception("Failed 1"), Exception("Failed 2"), None])
    config = RetryConfig(max_retries=3, retry_delay=2.0, max_backoff_delay=60.0)

    # Act
    with patch("sqlalchemy_foundation_kit.session.retry.asyncio.sleep") as mock_sleep:
        await retry_async_connection(connect_func, "test-service", config)

    # Assert
    assert mock_sleep.call_count == 2
    # First retry: 2.0 * 2^0 = 2.0
    mock_sleep.assert_any_call(2.0)
    # Second retry: 2.0 * 2^1 = 4.0
    mock_sleep.assert_any_call(4.0)


@pytest.mark.asyncio
async def test__retry_async_connection__max_backoff_delay__caps_delay() -> None:
    # Arrange
    connect_func = AsyncMock(
        side_effect=[
            Exception("1"),
            Exception("2"),
            Exception("3"),
            Exception("4"),
            None,
        ]
    )
    config = RetryConfig(max_retries=5, retry_delay=10.0, max_backoff_delay=30.0)

    # Act
    with patch("sqlalchemy_foundation_kit.session.retry.asyncio.sleep") as mock_sleep:
        await retry_async_connection(connect_func, "test-service", config)

    # Assert
    # Attempt 0: 10.0 * 2^0 = 10.0
    # Attempt 1: 10.0 * 2^1 = 20.0
    # Attempt 2: 10.0 * 2^2 = 40.0 -> capped to 30.0
    # Attempt 3: 10.0 * 2^3 = 80.0 -> capped to 30.0
    mock_sleep.assert_any_call(10.0)
    mock_sleep.assert_any_call(20.0)
    mock_sleep.assert_any_call(30.0)  # Capped


# ============================================================================
# retry_async_connection - Failure Tests
# ============================================================================


@pytest.mark.asyncio
async def test__retry_async_connection__all_attempts_fail__raises_exception() -> None:
    # Arrange
    connect_func = AsyncMock(side_effect=Exception("Connection failed"))
    config = RetryConfig(max_retries=3)

    # Act & Assert
    with pytest.raises(Exception, match="Connection failed"):
        with patch("sqlalchemy_foundation_kit.session.retry.logger"):
            with patch("sqlalchemy_foundation_kit.session.retry.asyncio.sleep"):
                await retry_async_connection(connect_func, "test-service", config)

    assert connect_func.call_count == 3


@pytest.mark.asyncio
async def test__retry_async_connection__all_attempts_fail__logs_exception() -> None:
    # Arrange
    connect_func = AsyncMock(side_effect=Exception("Connection failed"))
    config = RetryConfig(max_retries=2)

    # Act & Assert
    with pytest.raises(Exception), patch("sqlalchemy_foundation_kit.session.retry.logger") as mock_logger:
        with patch("sqlalchemy_foundation_kit.session.retry.asyncio.sleep"):
            await retry_async_connection(connect_func, "test-service", config)

    mock_logger.exception.assert_called_once_with("%s connection failed after %d attempts", "test-service", 2)


@pytest.mark.asyncio
async def test__retry_async_connection__zero_retries__raises_value_error() -> None:
    # Arrange
    connect_func = AsyncMock(side_effect=Exception("Failed"))
    config = RetryConfig(max_retries=0)

    # Act & Assert
    with pytest.raises(ValueError, match="max_retries must be >= 1, got 0"):
        await retry_async_connection(connect_func, "test-service", config)

    # Assert connect was never called due to validation
    connect_func.assert_not_called()


@pytest.mark.asyncio
async def test__retry_async_connection__one_retry__fails_on_second_attempt() -> None:
    # Arrange
    connect_func = AsyncMock(side_effect=Exception("Failed"))
    config = RetryConfig(max_retries=1)

    # Act & Assert
    with pytest.raises(Exception), patch("sqlalchemy_foundation_kit.session.retry.logger"):
        with patch("sqlalchemy_foundation_kit.session.retry.asyncio.sleep"):
            await retry_async_connection(connect_func, "test-service", config)

    connect_func.assert_called_once()


# ============================================================================
# retry_async_connection - Edge Cases
# ============================================================================


@pytest.mark.asyncio
async def test__retry_async_connection__different_exception_types__handles_all() -> None:
    # Arrange
    connect_func = AsyncMock(
        side_effect=[
            ConnectionError("Connection refused"),
            TimeoutError("Timeout"),
            None,
        ]
    )

    # Act
    with patch("sqlalchemy_foundation_kit.session.retry.logger"):
        with patch("sqlalchemy_foundation_kit.session.retry.asyncio.sleep"):
            await retry_async_connection(connect_func, "test-service")

    # Assert
    assert connect_func.call_count == 3


@pytest.mark.asyncio
async def test__retry_async_connection__custom_service_name__logs_with_name() -> None:
    # Arrange
    connect_func = AsyncMock()

    # Act
    with patch("sqlalchemy_foundation_kit.session.retry.logger") as mock_logger:
        await retry_async_connection(connect_func, "postgres-db")

    # Assert
    mock_logger.info.assert_called_once_with("%s connection successful", "postgres-db")


@pytest.mark.asyncio
async def test__retry_async_connection__very_small_retry_delay__uses_exact_value() -> None:
    # Arrange
    connect_func = AsyncMock(side_effect=[Exception("Failed"), None])
    config = RetryConfig(retry_delay=0.001)

    # Act
    with patch("sqlalchemy_foundation_kit.session.retry.asyncio.sleep") as mock_sleep:
        await retry_async_connection(connect_func, "test-service", config)

    # Assert
    mock_sleep.assert_called_once_with(0.001)


@pytest.mark.asyncio
async def test__retry_async_connection__large_max_retries__handles_correctly() -> None:
    # Arrange
    failures = [Exception(f"Failed {i}") for i in range(99)]
    connect_func = AsyncMock(side_effect=[*failures, None])
    config = RetryConfig(max_retries=100, retry_delay=0.001, max_backoff_delay=0.01)

    # Act
    with patch("sqlalchemy_foundation_kit.session.retry.logger"):
        with patch("sqlalchemy_foundation_kit.session.retry.asyncio.sleep"):
            await retry_async_connection(connect_func, "test-service", config)

    # Assert
    assert connect_func.call_count == 100


@pytest.mark.asyncio
async def test__retry_async_connection__async_exception__propagates() -> None:
    # Arrange
    async def failing_connect() -> None:
        await asyncio.sleep(0)
        raise ValueError("Async failure")

    # Act & Assert
    with pytest.raises(ValueError, match="Async failure"), patch("sqlalchemy_foundation_kit.session.retry.logger"):
        with patch("sqlalchemy_foundation_kit.session.retry.asyncio.sleep"):
            await retry_async_connection(failing_connect, "test-service")
