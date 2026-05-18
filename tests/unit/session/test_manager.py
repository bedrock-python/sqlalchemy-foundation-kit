"""Unit tests for async database session manager."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.exc import TimeoutError as SATimeoutError
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy_foundation_kit.session.manager import (
    DEFAULT_DISPOSE_TIMEOUT_SECONDS,
    AsyncSessionManager,
    _safe_metric_call,
    attach_metrics,
)

# ============================================================================
# _safe_metric_call Tests
# ============================================================================


def test__safe_metric_call__success__executes_function() -> None:
    # Arrange
    mock_func = Mock()

    # Act
    _safe_metric_call(mock_func, "Test error message")

    # Assert
    mock_func.assert_called_once()


def test__safe_metric_call__exception__logs_and_swallows() -> None:
    # Arrange
    mock_func = Mock(side_effect=Exception("Metric error"))

    # Act
    with patch("sqlalchemy_foundation_kit.session.manager.logger") as mock_logger:
        _safe_metric_call(mock_func, "Failed to record metric")

    # Assert
    mock_func.assert_called_once()
    mock_logger.exception.assert_called_once_with("Failed to record metric")


def test__safe_metric_call__exception__does_not_propagate() -> None:
    # Arrange
    mock_func = Mock(side_effect=ValueError("Metric failed"))

    # Act & Assert (should not raise)
    _safe_metric_call(mock_func, "Test error")


# ============================================================================
# attach_metrics Tests
# ============================================================================


def test__attach_metrics__registers_checkout_listener() -> None:
    # Arrange
    mock_engine = Mock()
    mock_metrics = Mock()

    # Act
    with patch("sqlalchemy_foundation_kit.session.manager.event") as mock_event:
        attach_metrics(mock_engine, mock_metrics)

    # Assert
    checkout_calls = [c for c in mock_event.listen.call_args_list if c[0][1] == "checkout"]
    assert len(checkout_calls) == 1
    assert checkout_calls[0][0][0] == mock_engine.pool


def test__attach_metrics__registers_checkin_listener() -> None:
    # Arrange
    mock_engine = Mock()
    mock_metrics = Mock()

    # Act
    with patch("sqlalchemy_foundation_kit.session.manager.event") as mock_event:
        attach_metrics(mock_engine, mock_metrics)

    # Assert
    checkin_calls = [c for c in mock_event.listen.call_args_list if c[0][1] == "checkin"]
    assert len(checkin_calls) == 1
    assert checkin_calls[0][0][0] == mock_engine.pool


def test__attach_metrics__registers_error_listener() -> None:
    # Arrange
    mock_engine = Mock()
    mock_metrics = Mock()

    # Act
    with patch("sqlalchemy_foundation_kit.session.manager.event") as mock_event:
        attach_metrics(mock_engine, mock_metrics)

    # Assert
    error_calls = [c for c in mock_event.listen.call_args_list if c[0][1] == "handle_error"]
    assert len(error_calls) == 1
    assert error_calls[0][0][0] == mock_engine.sync_engine


def test__attach_metrics__checkout_records_pool_stats() -> None:
    # Arrange
    mock_pool = Mock()
    mock_pool.size.return_value = 10
    mock_pool.checkedout.return_value = 5
    mock_pool.overflow.return_value = 2

    mock_engine = Mock()
    mock_engine.pool = mock_pool

    mock_metrics = Mock()

    # Act
    with patch("sqlalchemy_foundation_kit.session.manager.event") as mock_event:
        attach_metrics(mock_engine, mock_metrics)

        # Get the checkout callback and call it
        checkout_callback = None
        for call_item in mock_event.listen.call_args_list:
            if call_item[0][1] == "checkout":
                checkout_callback = call_item[0][2]
                break

        # Simulate checkout event
        connection_record = Mock()
        connection_record.info = {}
        checkout_callback(None, connection_record, None)

    # Assert
    mock_metrics.record_pool_stats.assert_called_once()
    call_args = mock_metrics.record_pool_stats.call_args[1]
    assert call_args["pool_size"] == 10
    assert call_args["pool_checked_out"] == 5
    assert call_args["pool_overflow"] == 2


def test__attach_metrics__checkout_stores_start_time() -> None:
    # Arrange
    mock_engine = Mock()
    mock_engine.pool = Mock()
    mock_metrics = Mock()

    # Act
    with patch("sqlalchemy_foundation_kit.session.manager.event") as mock_event:
        attach_metrics(mock_engine, mock_metrics)

        # Get checkout callback
        checkout_callback = [c[0][2] for c in mock_event.listen.call_args_list if c[0][1] == "checkout"][0]

        connection_record = Mock()
        connection_record.info = {}
        checkout_callback(None, connection_record, None)

    # Assert
    assert "checkout_start" in connection_record.info


def test__attach_metrics__checkin_records_duration() -> None:
    # Arrange
    mock_engine = Mock()
    mock_engine.pool = Mock()
    mock_metrics = Mock()

    # Act
    with patch("sqlalchemy_foundation_kit.session.manager.event") as mock_event:
        with patch("sqlalchemy_foundation_kit.session.manager.time") as mock_time:
            mock_time.perf_counter.side_effect = [100.0, 105.5]

            attach_metrics(mock_engine, mock_metrics)

            # Get callbacks
            checkout_callback = [c[0][2] for c in mock_event.listen.call_args_list if c[0][1] == "checkout"][0]
            checkin_callback = [c[0][2] for c in mock_event.listen.call_args_list if c[0][1] == "checkin"][0]

            # Simulate checkout then checkin
            connection_record = Mock()
            connection_record.info = {}
            checkout_callback(None, connection_record, None)
            checkin_callback(None, connection_record)

    # Assert
    mock_metrics.record_checkout.assert_called_once()
    duration = mock_metrics.record_checkout.call_args[1]["duration"]
    assert duration == 5.5


def test__attach_metrics__checkin_without_checkout_start__no_duration_recorded() -> None:
    # Arrange
    mock_engine = Mock()
    mock_engine.pool = Mock()
    mock_metrics = Mock()

    # Act
    with patch("sqlalchemy_foundation_kit.session.manager.event") as mock_event:
        attach_metrics(mock_engine, mock_metrics)

        checkin_callback = [c[0][2] for c in mock_event.listen.call_args_list if c[0][1] == "checkin"][0]

        connection_record = Mock()
        connection_record.info = {}  # No checkout_start
        checkin_callback(None, connection_record)

    # Assert
    mock_metrics.record_checkout.assert_not_called()


def test__attach_metrics__error_records_error_type() -> None:
    # Arrange
    mock_engine = Mock()
    mock_metrics = Mock()

    # Act
    with patch("sqlalchemy_foundation_kit.session.manager.event") as mock_event:
        attach_metrics(mock_engine, mock_metrics)

        error_callback = [c[0][2] for c in mock_event.listen.call_args_list if c[0][1] == "handle_error"][0]

        exception_context = Mock()
        exception_context.original_exception = ValueError("Test error")
        error_callback(exception_context)

    # Assert
    mock_metrics.record_error.assert_called_once()
    call_args = mock_metrics.record_error.call_args[1]
    assert call_args["error_type"] == "ValueError"
    assert call_args["is_timeout"] is False


def test__attach_metrics__timeout_error__marks_as_timeout() -> None:
    # Arrange
    mock_engine = Mock()
    mock_metrics = Mock()

    # Act
    with patch("sqlalchemy_foundation_kit.session.manager.event") as mock_event:
        attach_metrics(mock_engine, mock_metrics)

        error_callback = [c[0][2] for c in mock_event.listen.call_args_list if c[0][1] == "handle_error"][0]

        exception_context = Mock()
        exception_context.original_exception = TimeoutError("Connection timeout")
        error_callback(exception_context)

    # Assert
    call_args = mock_metrics.record_error.call_args[1]
    assert call_args["is_timeout"] is True


def test__attach_metrics__sqlalchemy_timeout__marks_as_timeout() -> None:
    # Arrange
    mock_engine = Mock()
    mock_metrics = Mock()

    # Act
    with patch("sqlalchemy_foundation_kit.session.manager.event") as mock_event:
        attach_metrics(mock_engine, mock_metrics)

        error_callback = [c[0][2] for c in mock_event.listen.call_args_list if c[0][1] == "handle_error"][0]

        exception_context = Mock()
        exception_context.original_exception = SATimeoutError("Pool timeout")
        error_callback(exception_context)

    # Assert
    call_args = mock_metrics.record_error.call_args[1]
    assert call_args["is_timeout"] is True


def test__attach_metrics__pool_without_size__uses_zero() -> None:
    # Arrange
    mock_pool = Mock(spec=[])  # No size method
    mock_engine = Mock()
    mock_engine.pool = mock_pool
    mock_metrics = Mock()

    # Act
    with patch("sqlalchemy_foundation_kit.session.manager.event") as mock_event:
        attach_metrics(mock_engine, mock_metrics)

        checkout_callback = [c[0][2] for c in mock_event.listen.call_args_list if c[0][1] == "checkout"][0]

        connection_record = Mock()
        connection_record.info = {}
        checkout_callback(None, connection_record, None)

    # Assert
    call_args = mock_metrics.record_pool_stats.call_args[1]
    assert call_args["pool_size"] == 0
    assert call_args["pool_checked_out"] == 0
    assert call_args["pool_overflow"] == 0


# ============================================================================
# AsyncSessionManager - Initialization Tests
# ============================================================================


def test__async_session_manager__init__creates_engine() -> None:
    # Arrange & Act
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine") as mock_create:
        mock_create.return_value = Mock()
        manager = AsyncSessionManager("postgresql://localhost/test")

    # Assert
    mock_create.assert_called_once()
    assert manager._engine == mock_create.return_value


def test__async_session_manager__init__creates_session_maker() -> None:
    # Arrange & Act
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine"):
        with patch("sqlalchemy_foundation_kit.session.manager.async_sessionmaker") as mock_maker:
            manager = AsyncSessionManager("postgresql://localhost/test")

    # Assert
    mock_maker.assert_called_once()
    assert manager._session_maker == mock_maker.return_value


def test__async_session_manager__init__sets_default_values() -> None:
    # Arrange & Act
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine"):
        manager = AsyncSessionManager("postgresql://localhost/test")

    # Assert
    assert manager._closed is False
    assert manager._dispose_timeout == DEFAULT_DISPOSE_TIMEOUT_SECONDS


def test__async_session_manager__init__custom_dispose_timeout() -> None:
    # Arrange & Act
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine"):
        manager = AsyncSessionManager("postgresql://localhost/test", dispose_timeout=60.0)

    # Assert
    assert manager._dispose_timeout == 60.0


def test__async_session_manager__init__attaches_metrics() -> None:
    # Arrange
    mock_metrics = Mock()

    # Act
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine"):
        with patch("sqlalchemy_foundation_kit.session.manager.attach_metrics") as mock_attach:
            manager = AsyncSessionManager("postgresql://localhost/test", metrics=mock_metrics)

    # Assert
    mock_attach.assert_called_once_with(manager._engine, mock_metrics)


def test__async_session_manager__init__no_metrics__does_not_attach() -> None:
    # Arrange & Act
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine"):
        with patch("sqlalchemy_foundation_kit.session.manager.attach_metrics") as mock_attach:
            AsyncSessionManager("postgresql://localhost/test")

    # Assert
    mock_attach.assert_not_called()


def test__async_session_manager__init__calls_on_engine_created() -> None:
    # Arrange
    mock_callback = Mock()

    # Act
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine"):
        manager = AsyncSessionManager("postgresql://localhost/test", on_engine_created=mock_callback)

    # Assert
    mock_callback.assert_called_once_with(manager._engine)


def test__async_session_manager__init__no_callback__does_not_call() -> None:
    # Arrange & Act
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine"):
        AsyncSessionManager("postgresql://localhost/test")

    # Assert (no exception raised)


def test__async_session_manager__init__passes_url_to_engine() -> None:
    # Arrange & Act
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine") as mock_create:
        AsyncSessionManager("postgresql://user:pass@host:5432/db")

    # Assert
    assert mock_create.call_args[0][0] == "postgresql://user:pass@host:5432/db"


def test__async_session_manager__init__resolves_poolclass() -> None:
    # Arrange & Act
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine"):
        with patch("sqlalchemy_foundation_kit.session.manager.resolve_pool_class") as mock_resolve:
            AsyncSessionManager("postgresql://localhost/test", poolclass="queue")

    # Assert
    mock_resolve.assert_called_once_with("queue")


def test__async_session_manager__init__builds_engine_kwargs() -> None:
    # Arrange & Act
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine"):
        with patch("sqlalchemy_foundation_kit.session.manager.build_engine_kwargs") as mock_build:
            mock_build.return_value = {}
            AsyncSessionManager(
                "postgresql://localhost/test",
                echo=True,
                poolclass="queue",
                isolation_level="SERIALIZABLE",
            )

    # Assert
    mock_build.assert_called_once()


# ============================================================================
# AsyncSessionManager - aclose Tests
# ============================================================================


@pytest.mark.asyncio
async def test__async_session_manager__aclose__disposes_engine() -> None:
    # Arrange
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine") as mock_create:
        mock_engine = AsyncMock()
        mock_create.return_value = mock_engine

        manager = AsyncSessionManager("postgresql://localhost/test")

    # Act
    await manager.aclose()

    # Assert
    mock_engine.dispose.assert_called_once()


@pytest.mark.asyncio
async def test__async_session_manager__aclose__sets_closed_flag() -> None:
    # Arrange
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine") as mock_create:
        mock_engine = AsyncMock()
        mock_create.return_value = mock_engine

        manager = AsyncSessionManager("postgresql://localhost/test")

    # Act
    await manager.aclose()

    # Assert
    assert manager._closed is True


@pytest.mark.asyncio
async def test__async_session_manager__aclose__already_closed__returns_immediately() -> None:
    # Arrange
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine") as mock_create:
        mock_engine = AsyncMock()
        mock_create.return_value = mock_engine

        manager = AsyncSessionManager("postgresql://localhost/test")
        await manager.aclose()

        mock_engine.dispose.reset_mock()

    # Act
    await manager.aclose()

    # Assert
    mock_engine.dispose.assert_not_called()


@pytest.mark.asyncio
async def test__async_session_manager__aclose__uses_timeout() -> None:
    # Arrange
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine") as mock_create:
        mock_engine = AsyncMock()
        mock_create.return_value = mock_engine

        manager = AsyncSessionManager("postgresql://localhost/test", dispose_timeout=45.0)

    # Act
    with patch("sqlalchemy_foundation_kit.session.manager.asyncio.wait_for") as mock_wait_for:
        mock_wait_for.return_value = None
        await manager.aclose()

    # Assert
    mock_wait_for.assert_called_once()
    assert mock_wait_for.call_args[1]["timeout"] == 45.0


# ============================================================================
# AsyncSessionManager - _ensure_not_closed Tests
# ============================================================================


def test__async_session_manager__ensure_not_closed__not_closed__no_error() -> None:
    # Arrange
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine"):
        manager = AsyncSessionManager("postgresql://localhost/test")

    # Act & Assert (should not raise)
    manager._ensure_not_closed()


@pytest.mark.asyncio
async def test__async_session_manager__ensure_not_closed__closed__raises_error() -> None:
    # Arrange
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine") as mock_create:
        mock_engine = AsyncMock()
        mock_create.return_value = mock_engine

        manager = AsyncSessionManager("postgresql://localhost/test")
        await manager.aclose()

    # Act & Assert
    with pytest.raises(RuntimeError, match="AsyncSessionManager is closed"):
        manager._ensure_not_closed()


# ============================================================================
# AsyncSessionManager - Context Manager Tests
# ============================================================================


@pytest.mark.asyncio
async def test__async_session_manager__aenter__returns_self() -> None:
    # Arrange
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine"):
        manager = AsyncSessionManager("postgresql://localhost/test")

    # Act
    result = await manager.__aenter__()

    # Assert
    assert result is manager


@pytest.mark.asyncio
async def test__async_session_manager__aexit__calls_aclose() -> None:
    # Arrange
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine") as mock_create:
        mock_engine = AsyncMock()
        mock_create.return_value = mock_engine

        manager = AsyncSessionManager("postgresql://localhost/test")

    # Act
    await manager.__aexit__(None, None, None)

    # Assert
    assert manager._closed is True


@pytest.mark.asyncio
async def test__async_session_manager__context_manager__works() -> None:
    # Arrange
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine") as mock_create:
        mock_engine = AsyncMock()
        mock_create.return_value = mock_engine

        # Act
        async with AsyncSessionManager("postgresql://localhost/test") as manager:
            assert manager._closed is False

    # Assert
    assert manager._closed is True


# ============================================================================
# AsyncSessionManager - Properties Tests
# ============================================================================


def test__async_session_manager__engine_property__returns_engine() -> None:
    # Arrange
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine") as mock_create:
        mock_engine = Mock()
        mock_create.return_value = mock_engine

        manager = AsyncSessionManager("postgresql://localhost/test")

    # Act
    result = manager.engine

    # Assert
    assert result is mock_engine


def test__async_session_manager__session_maker_property__returns_maker() -> None:
    # Arrange
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine"):
        with patch("sqlalchemy_foundation_kit.session.manager.async_sessionmaker") as mock_maker_class:
            mock_maker = Mock()
            mock_maker_class.return_value = mock_maker

            manager = AsyncSessionManager("postgresql://localhost/test")

    # Act
    result = manager.session_maker

    # Assert
    assert result is mock_maker


# ============================================================================
# AsyncSessionManager - get_session Tests
# ============================================================================


@pytest.mark.asyncio
async def test__async_session_manager__get_session__yields_session() -> None:
    # Arrange
    mock_session = AsyncMock(spec=AsyncSession)

    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine"):
        with patch("sqlalchemy_foundation_kit.session.manager.async_sessionmaker") as mock_maker_class:
            mock_session_maker = AsyncMock()
            mock_session_maker.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_maker.__aexit__ = AsyncMock()
            mock_maker_class.return_value = Mock(return_value=mock_session_maker)

            manager = AsyncSessionManager("postgresql://localhost/test")

    # Act
    async with manager.get_session() as session:
        result_session = session

    # Assert
    assert result_session is mock_session


@pytest.mark.asyncio
async def test__async_session_manager__get_session__closed__raises_error() -> None:
    # Arrange
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine") as mock_create:
        mock_engine = AsyncMock()
        mock_create.return_value = mock_engine

        manager = AsyncSessionManager("postgresql://localhost/test")
        await manager.aclose()

    # Act & Assert
    with pytest.raises(RuntimeError, match="AsyncSessionManager is closed"):
        async with manager.get_session():
            pass


# ============================================================================
# AsyncSessionManager - get_transaction Tests
# ============================================================================


@pytest.mark.asyncio
async def test__async_session_manager__get_transaction__yields_session() -> None:
    # Arrange
    mock_session = AsyncMock(spec=AsyncSession)

    # Mock session.begin() to return an async context manager
    mock_begin_ctx = AsyncMock()
    mock_begin_ctx.__aenter__ = AsyncMock(return_value=None)
    mock_begin_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin = Mock(return_value=mock_begin_ctx)

    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine"):
        with patch("sqlalchemy_foundation_kit.session.manager.async_sessionmaker") as mock_maker_class:
            # Mock the session maker to return an async context manager
            mock_session_ctx = AsyncMock()
            mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_maker_obj = Mock()
            mock_maker_obj.return_value = mock_session_ctx
            mock_maker_class.return_value = mock_maker_obj

            manager = AsyncSessionManager("postgresql://localhost/test")

    # Act
    async with manager.get_transaction() as session:
        result_session = session

    # Assert
    assert result_session is mock_session
    mock_session.begin.assert_called_once()


@pytest.mark.asyncio
async def test__async_session_manager__get_transaction__with_isolation_level__passes_options() -> None:
    # Arrange
    mock_session = AsyncMock(spec=AsyncSession)

    # Mock session.begin()
    mock_begin_ctx = AsyncMock()
    mock_begin_ctx.__aenter__ = AsyncMock(return_value=None)
    mock_begin_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin = Mock(return_value=mock_begin_ctx)

    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine"):
        with patch("sqlalchemy_foundation_kit.session.manager.async_sessionmaker") as mock_maker_class:
            # Mock the session maker
            mock_session_ctx = AsyncMock()
            mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_maker_obj = Mock()
            mock_maker_obj.return_value = mock_session_ctx
            mock_maker_class.return_value = mock_maker_obj

            manager = AsyncSessionManager("postgresql://localhost/test")

    # Act
    async with manager.get_transaction(isolation_level="SERIALIZABLE"):
        pass

    # Assert
    mock_maker_obj.assert_called_with(execution_options={"isolation_level": "SERIALIZABLE"})


@pytest.mark.asyncio
async def test__async_session_manager__get_transaction__no_isolation_level__no_options() -> None:
    # Arrange
    mock_session = AsyncMock(spec=AsyncSession)

    # Mock session.begin()
    mock_begin_ctx = AsyncMock()
    mock_begin_ctx.__aenter__ = AsyncMock(return_value=None)
    mock_begin_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin = Mock(return_value=mock_begin_ctx)

    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine"):
        with patch("sqlalchemy_foundation_kit.session.manager.async_sessionmaker") as mock_maker_class:
            # Mock the session maker
            mock_session_ctx = AsyncMock()
            mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session_ctx.__aexit__ = AsyncMock(return_value=None)

            mock_maker_obj = Mock()
            mock_maker_obj.return_value = mock_session_ctx
            mock_maker_class.return_value = mock_maker_obj

            manager = AsyncSessionManager("postgresql://localhost/test")

    # Act
    async with manager.get_transaction():
        pass

    # Assert
    # Check that it was called with empty execution_options
    assert mock_maker_obj.call_count == 1
    call_kwargs = mock_maker_obj.call_args[1] if mock_maker_obj.call_args[1] else {}
    assert call_kwargs.get("execution_options") == {}


@pytest.mark.asyncio
async def test__async_session_manager__get_transaction__closed__raises_error() -> None:
    # Arrange
    with patch("sqlalchemy_foundation_kit.session.manager.create_async_engine") as mock_create:
        mock_engine = AsyncMock()
        mock_create.return_value = mock_engine

        manager = AsyncSessionManager("postgresql://localhost/test")
        await manager.aclose()

    # Act & Assert
    with pytest.raises(RuntimeError, match="AsyncSessionManager is closed"):
        async with manager.get_transaction():
            pass


# ============================================================================
# AsyncSessionManager - DEFAULT_DISPOSE_TIMEOUT_SECONDS Tests
# ============================================================================


def test__default_dispose_timeout_seconds__is_thirty() -> None:
    # Arrange & Act & Assert
    assert DEFAULT_DISPOSE_TIMEOUT_SECONDS == 30.0
