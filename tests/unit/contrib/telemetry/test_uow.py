"""Unit tests for TracedAsyncUnitOfWork."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

import pytest

# ============================================================================
# TracedAsyncUnitOfWork Initialization Tests
# ============================================================================


@pytest.mark.unit
def test__traced_async_unit_of_work__init_without_otel__tracer_is_none() -> None:
    # Arrange
    mock_session_maker = MagicMock()
    mock_transaction_factory = MagicMock()

    with patch("sqlalchemy_foundation_kit.contrib.telemetry.uow.HAS_OTEL", False):
        from sqlalchemy_foundation_kit.contrib.telemetry.uow import TracedAsyncUnitOfWork

        # Act
        uow = TracedAsyncUnitOfWork(
            session_maker=mock_session_maker,
            transaction_factory=mock_transaction_factory,
            service_name="test-service",
        )

        # Assert
        assert uow._tracer is None


@pytest.mark.unit
def test__traced_async_unit_of_work__init_with_otel__tracer_is_set() -> None:
    # Arrange
    mock_session_maker = MagicMock()
    mock_transaction_factory = MagicMock()
    mock_tracer = MagicMock()
    mock_trace = MagicMock()
    mock_trace.get_tracer.return_value = mock_tracer

    with patch("sqlalchemy_foundation_kit.contrib.telemetry.uow.HAS_OTEL", True):
        with patch("sqlalchemy_foundation_kit.contrib.telemetry.uow.trace", mock_trace):
            from sqlalchemy_foundation_kit.contrib.telemetry.uow import TracedAsyncUnitOfWork

            # Act
            uow = TracedAsyncUnitOfWork(
                session_maker=mock_session_maker,
                transaction_factory=mock_transaction_factory,
                service_name="test-service",
            )

            # Assert
            mock_trace.get_tracer.assert_called_once_with("test-service")
            assert uow._tracer == mock_tracer


@pytest.mark.unit
def test__traced_async_unit_of_work__default_service_name() -> None:
    # Arrange
    mock_session_maker = MagicMock()
    mock_transaction_factory = MagicMock()
    mock_trace = MagicMock()

    with patch("sqlalchemy_foundation_kit.contrib.telemetry.uow.HAS_OTEL", True):
        with patch("sqlalchemy_foundation_kit.contrib.telemetry.uow.trace", mock_trace):
            from sqlalchemy_foundation_kit.contrib.telemetry.uow import TracedAsyncUnitOfWork

            # Act
            uow = TracedAsyncUnitOfWork(
                session_maker=mock_session_maker,
                transaction_factory=mock_transaction_factory,
            )

            # Assert
            mock_trace.get_tracer.assert_called_once_with("sqlalchemy-foundation-kit")


# ============================================================================
# TracedAsyncUnitOfWork _traced Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test__traced_async_unit_of_work___traced_without_otel__delegates_to_context_manager() -> None:
    # Arrange
    mock_session_maker = MagicMock()
    mock_transaction_factory = MagicMock()
    mock_transaction = MagicMock()

    @asynccontextmanager
    async def mock_context_manager():
        yield mock_transaction

    with patch("sqlalchemy_foundation_kit.contrib.telemetry.uow.HAS_OTEL", False):
        from sqlalchemy_foundation_kit.contrib.telemetry.uow import TracedAsyncUnitOfWork

        uow = TracedAsyncUnitOfWork(
            session_maker=mock_session_maker,
            transaction_factory=mock_transaction_factory,
        )

        # Act
        async with uow._traced("test_operation", mock_context_manager()) as tx:
            result = tx

        # Assert
        assert result == mock_transaction


@pytest.mark.unit
@pytest.mark.asyncio
async def test__traced_async_unit_of_work___traced_with_otel__creates_span() -> None:
    # Arrange
    mock_session_maker = MagicMock()
    mock_transaction_factory = MagicMock()
    mock_transaction = MagicMock()
    mock_span = MagicMock()
    mock_tracer = MagicMock()
    mock_tracer.start_span.return_value = mock_span
    mock_trace = MagicMock()

    @asynccontextmanager
    async def mock_context_manager():
        yield mock_transaction

    with patch("sqlalchemy_foundation_kit.contrib.telemetry.uow.HAS_OTEL", True):
        with patch("sqlalchemy_foundation_kit.contrib.telemetry.uow.trace", mock_trace):
            from sqlalchemy_foundation_kit.contrib.telemetry.uow import TracedAsyncUnitOfWork

            uow = TracedAsyncUnitOfWork(
                session_maker=mock_session_maker,
                transaction_factory=mock_transaction_factory,
            )
            uow._tracer = mock_tracer

            # Act
            async with uow._traced("test_operation", mock_context_manager()) as tx:
                result = tx

            # Assert
            mock_tracer.start_span.assert_called_once_with("uow.test_operation")
            mock_span.set_attribute.assert_called()
            mock_span.set_status.assert_called_once()
            mock_span.end.assert_called_once()
            assert result == mock_transaction


@pytest.mark.unit
@pytest.mark.asyncio
async def test__traced_async_unit_of_work___traced_with_attributes__sets_attributes() -> None:
    # Arrange
    mock_session_maker = MagicMock()
    mock_transaction_factory = MagicMock()
    mock_transaction = MagicMock()
    mock_span = MagicMock()
    mock_tracer = MagicMock()
    mock_tracer.start_span.return_value = mock_span
    mock_trace = MagicMock()

    @asynccontextmanager
    async def mock_context_manager():
        yield mock_transaction

    with patch("sqlalchemy_foundation_kit.contrib.telemetry.uow.HAS_OTEL", True):
        with patch("sqlalchemy_foundation_kit.contrib.telemetry.uow.trace", mock_trace):
            from sqlalchemy_foundation_kit.contrib.telemetry.uow import TracedAsyncUnitOfWork

            uow = TracedAsyncUnitOfWork(
                session_maker=mock_session_maker,
                transaction_factory=mock_transaction_factory,
            )
            uow._tracer = mock_tracer

            # Act
            async with uow._traced(
                "test_operation",
                mock_context_manager(),
                attributes={"key1": "value1", "key2": True},
            ) as tx:
                result = tx

            # Assert
            # Should set db.operation + custom attributes
            assert mock_span.set_attribute.call_count >= 3


@pytest.mark.unit
@pytest.mark.asyncio
async def test__traced_async_unit_of_work___traced_with_exception__records_exception() -> None:
    # Arrange
    mock_session_maker = MagicMock()
    mock_transaction_factory = MagicMock()
    mock_span = MagicMock()
    mock_tracer = MagicMock()
    mock_tracer.start_span.return_value = mock_span
    mock_trace = MagicMock()

    test_exception = ValueError("test error")

    @asynccontextmanager
    async def mock_context_manager():
        if False:
            yield
        raise test_exception

    with patch("sqlalchemy_foundation_kit.contrib.telemetry.uow.HAS_OTEL", True):
        with patch("sqlalchemy_foundation_kit.contrib.telemetry.uow.trace", mock_trace):
            from sqlalchemy_foundation_kit.contrib.telemetry.uow import TracedAsyncUnitOfWork

            uow = TracedAsyncUnitOfWork(
                session_maker=mock_session_maker,
                transaction_factory=mock_transaction_factory,
            )
            uow._tracer = mock_tracer

            # Act & Assert
            with pytest.raises(ValueError, match="test error"):
                async with uow._traced("test_operation", mock_context_manager()):
                    pass

            # Assert
            mock_span.record_exception.assert_called_once()
            mock_span.end.assert_called_once()


# ============================================================================
# TracedAsyncUnitOfWork Parameters Tests
# ============================================================================


@pytest.mark.unit
def test__traced_async_unit_of_work__flush_before_commit_param__passed_to_parent() -> None:
    # Arrange
    mock_session_maker = MagicMock()
    mock_transaction_factory = MagicMock()

    with patch("sqlalchemy_foundation_kit.contrib.telemetry.uow.HAS_OTEL", False):
        from sqlalchemy_foundation_kit.contrib.telemetry.uow import TracedAsyncUnitOfWork

        # Act
        uow = TracedAsyncUnitOfWork(
            session_maker=mock_session_maker,
            transaction_factory=mock_transaction_factory,
            flush_before_commit=False,
        )

        # Assert
        assert uow._flush_before_commit is False


# ============================================================================
# TracedAsyncUnitOfWork transaction() Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test__traced_async_unit_of_work__transaction_with_isolation_level__sets_attribute() -> None:
    """Test that transaction() with isolation_level sets the attribute in span."""
    # Arrange
    from unittest.mock import AsyncMock

    mock_session_maker = MagicMock()
    mock_transaction_factory = MagicMock()
    mock_transaction = MagicMock()
    mock_session = AsyncMock()
    mock_session.begin = MagicMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()
    mock_session.close = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()

    mock_session_maker.return_value = mock_session
    mock_transaction_factory.return_value = mock_transaction

    mock_span = MagicMock()
    mock_tracer = MagicMock()
    mock_tracer.start_span.return_value = mock_span
    mock_trace = MagicMock()

    with patch("sqlalchemy_foundation_kit.contrib.telemetry.uow.HAS_OTEL", True):
        with patch("sqlalchemy_foundation_kit.contrib.telemetry.uow.trace", mock_trace):
            from sqlalchemy_foundation_kit.contrib.telemetry.uow import TracedAsyncUnitOfWork

            uow = TracedAsyncUnitOfWork(
                session_maker=mock_session_maker,
                transaction_factory=mock_transaction_factory,
            )
            uow._tracer = mock_tracer

            # Act
            async with uow.transaction(isolation_level="SERIALIZABLE") as tx:
                pass

            # Assert
            # Check that isolation_level attribute was set
            attribute_calls = list(mock_span.set_attribute.call_args_list)
            isolation_call_found = any(
                "isolation" in str(call) or "SERIALIZABLE" in str(call) for call in attribute_calls
            )
            assert isolation_call_found or any("db.isolation_level" in str(call) for call in attribute_calls)


# ============================================================================
# TracedAsyncUnitOfWork managed_session() Tests
# ============================================================================


# ============================================================================
# TracedAsyncUnitOfWork query() Tests
# ============================================================================


@pytest.mark.unit
@pytest.mark.asyncio
async def test__traced_async_unit_of_work__query_with_isolation_level__sets_attribute() -> None:
    """Test that query() with isolation_level sets the attribute in span."""
    # Arrange
    from unittest.mock import AsyncMock

    mock_session_maker = MagicMock()
    mock_transaction_factory = MagicMock()
    mock_transaction = MagicMock()
    mock_session = AsyncMock()
    mock_session.begin = MagicMock()
    mock_session.close = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock()

    mock_session_maker.return_value = mock_session
    mock_transaction_factory.return_value = mock_transaction

    mock_span = MagicMock()
    mock_tracer = MagicMock()
    mock_tracer.start_span.return_value = mock_span
    mock_trace = MagicMock()

    with patch("sqlalchemy_foundation_kit.contrib.telemetry.uow.HAS_OTEL", True):
        with patch("sqlalchemy_foundation_kit.contrib.telemetry.uow.trace", mock_trace):
            from sqlalchemy_foundation_kit.contrib.telemetry.uow import TracedAsyncUnitOfWork

            uow = TracedAsyncUnitOfWork(
                session_maker=mock_session_maker,
                transaction_factory=mock_transaction_factory,
            )
            uow._tracer = mock_tracer

            # Act
            async with uow.query(isolation_level="SERIALIZABLE") as qx:
                pass

            # Assert
            attribute_calls = list(mock_span.set_attribute.call_args_list)
            isolation_call_found = any(
                "isolation" in str(call) or "SERIALIZABLE" in str(call) for call in attribute_calls
            )
            assert isolation_call_found or any("db.isolation_level" in str(call) for call in attribute_calls)
