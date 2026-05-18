"""Unit tests for Unit of Work SQLAlchemy implementation."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy_foundation_kit.uow.enums import IsolationLevel
from sqlalchemy_foundation_kit.uow.sqlalchemy import (
    AsyncSQLAlchemyUnitOfWork,
    AsyncSQLAlchemyUowTransaction,
    PostgresAdvisoryLockMixin,
    apply_isolation_level,
    normalize_isolation_level,
)

# ============================================================================
# normalize_isolation_level Tests
# ============================================================================


def test__normalize_isolation_level__none__returns_none() -> None:
    # Arrange & Act
    result = normalize_isolation_level(None)

    # Assert
    assert result is None


def test__normalize_isolation_level__read_committed_enum__returns_string() -> None:
    # Arrange & Act
    result = normalize_isolation_level(IsolationLevel.READ_COMMITTED)

    # Assert
    assert result == "READ COMMITTED"


def test__normalize_isolation_level__repeatable_read_enum__returns_string() -> None:
    # Arrange & Act
    result = normalize_isolation_level(IsolationLevel.REPEATABLE_READ)

    # Assert
    assert result == "REPEATABLE READ"


def test__normalize_isolation_level__serializable_enum__returns_string() -> None:
    # Arrange & Act
    result = normalize_isolation_level(IsolationLevel.SERIALIZABLE)

    # Assert
    assert result == "SERIALIZABLE"


def test__normalize_isolation_level__read_uncommitted_enum__returns_string() -> None:
    # Arrange & Act
    result = normalize_isolation_level(IsolationLevel.READ_UNCOMMITTED)

    # Assert
    assert result == "READ UNCOMMITTED"


def test__normalize_isolation_level__string_with_underscores__converts() -> None:
    # Arrange & Act
    result = normalize_isolation_level("READ_COMMITTED")

    # Assert
    assert result == "READ COMMITTED"


def test__normalize_isolation_level__lowercase_string__converts() -> None:
    # Arrange & Act
    result = normalize_isolation_level("read committed")

    # Assert
    assert result == "READ COMMITTED"


def test__normalize_isolation_level__mixed_case__converts() -> None:
    # Arrange & Act
    result = normalize_isolation_level("repeatable_READ")

    # Assert
    assert result == "REPEATABLE READ"


def test__normalize_isolation_level__string_with_spaces__converts() -> None:
    # Arrange & Act
    result = normalize_isolation_level("REPEATABLE READ")

    # Assert
    assert result == "REPEATABLE READ"


def test__normalize_isolation_level__invalid_level__raises_error() -> None:
    # Arrange & Act & Assert
    with pytest.raises(ValueError) as exc_info:
        normalize_isolation_level("INVALID_LEVEL")

    assert "Invalid isolation level" in str(exc_info.value)
    assert "Supported values:" in str(exc_info.value)


def test__normalize_isolation_level__empty_string__raises_error() -> None:
    # Arrange & Act & Assert
    with pytest.raises(ValueError):
        normalize_isolation_level("")


@pytest.mark.parametrize(
    "input_value,expected_output",
    [
        ("read_committed", "READ COMMITTED"),
        ("REPEATABLE_READ", "REPEATABLE READ"),
        ("serializable", "SERIALIZABLE"),
        ("READ UNCOMMITTED", "READ UNCOMMITTED"),
    ],
)
def test__normalize_isolation_level__various_formats__converts(input_value: str, expected_output: str) -> None:
    # Arrange & Act
    result = normalize_isolation_level(input_value)

    # Assert
    assert result == expected_output


# ============================================================================
# apply_isolation_level Tests
# ============================================================================


@pytest.mark.asyncio
async def test__apply_isolation_level__none__does_nothing() -> None:
    # Arrange
    mock_session = AsyncMock(spec=AsyncSession)

    # Act
    await apply_isolation_level(mock_session, None)

    # Assert
    mock_session.connection.assert_not_called()


@pytest.mark.asyncio
async def test__apply_isolation_level__read_committed__applies() -> None:
    # Arrange
    mock_connection = AsyncMock()
    mock_connection.run_sync = AsyncMock()
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.connection = AsyncMock(return_value=mock_connection)

    # Act
    await apply_isolation_level(mock_session, IsolationLevel.READ_COMMITTED)

    # Assert
    mock_session.connection.assert_called_once()
    mock_connection.run_sync.assert_called_once()


@pytest.mark.asyncio
async def test__apply_isolation_level__serializable__applies() -> None:
    # Arrange
    mock_connection = AsyncMock()
    mock_connection.run_sync = AsyncMock()
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.connection = AsyncMock(return_value=mock_connection)

    # Act
    await apply_isolation_level(mock_session, "SERIALIZABLE")

    # Assert
    mock_session.connection.assert_called_once()


@pytest.mark.asyncio
async def test__apply_isolation_level__invalid_level__raises_error() -> None:
    # Arrange
    mock_session = AsyncMock(spec=AsyncSession)

    # Act & Assert
    with pytest.raises(ValueError):
        await apply_isolation_level(mock_session, "INVALID")


# ============================================================================
# AsyncSQLAlchemyUowTransaction Tests
# ============================================================================


def test__uow_transaction__init__stores_session() -> None:
    # Arrange
    mock_session = Mock(spec=AsyncSession)

    # Act
    transaction = AsyncSQLAlchemyUowTransaction(mock_session)

    # Assert
    assert transaction._session is mock_session


def test__uow_transaction__session_property__returns_session() -> None:
    # Arrange
    mock_session = Mock(spec=AsyncSession)
    transaction = AsyncSQLAlchemyUowTransaction(mock_session)

    # Act
    session = transaction.session

    # Assert
    assert session is mock_session


# ============================================================================
# PostgresAdvisoryLockMixin Tests
# ============================================================================


@pytest.mark.asyncio
async def test__advisory_lock_mixin__lock_acquired__returns_true() -> None:
    # Arrange
    class TestTransaction(AsyncSQLAlchemyUowTransaction, PostgresAdvisoryLockMixin):
        pass

    mock_session = AsyncMock(spec=AsyncSession)
    transaction = TestTransaction(mock_session)

    with patch("sqlalchemy_foundation_kit.uow.sqlalchemy.try_advisory_xact_lock") as mock_lock:
        mock_lock.return_value = True

        # Act
        result = await transaction.try_advisory_lock(12345)

        # Assert
        assert result is True
        mock_lock.assert_called_once_with(mock_session, 12345)


@pytest.mark.asyncio
async def test__advisory_lock_mixin__lock_not_acquired__returns_false() -> None:
    # Arrange
    class TestTransaction(AsyncSQLAlchemyUowTransaction, PostgresAdvisoryLockMixin):
        pass

    mock_session = AsyncMock(spec=AsyncSession)
    transaction = TestTransaction(mock_session)

    with patch("sqlalchemy_foundation_kit.uow.sqlalchemy.try_advisory_xact_lock") as mock_lock:
        mock_lock.return_value = False

        # Act
        result = await transaction.try_advisory_lock(99999)

        # Assert
        assert result is False


# ============================================================================
# AsyncSQLAlchemyUnitOfWork Init Tests
# ============================================================================


def test__uow__init__stores_session_maker() -> None:
    # Arrange
    mock_session_maker = Mock()
    mock_factory = Mock()

    # Act
    uow = AsyncSQLAlchemyUnitOfWork(mock_session_maker, mock_factory)

    # Assert
    assert uow._session_maker is mock_session_maker
    assert uow._transaction_factory is mock_factory


def test__uow__init__default_flush_before_commit__is_true() -> None:
    # Arrange
    mock_session_maker = Mock()
    mock_factory = Mock()

    # Act
    uow = AsyncSQLAlchemyUnitOfWork(mock_session_maker, mock_factory)

    # Assert
    assert uow._flush_before_commit is True


def test__uow__init__custom_flush_before_commit__stores_value() -> None:
    # Arrange
    mock_session_maker = Mock()
    mock_factory = Mock()

    # Act
    uow = AsyncSQLAlchemyUnitOfWork(mock_session_maker, mock_factory, flush_before_commit=False)

    # Assert
    assert uow._flush_before_commit is False


# ============================================================================
# open_session Tests
# ============================================================================


@pytest.mark.asyncio
async def test__open_session__creates_session__no_isolation() -> None:
    # Arrange
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    mock_session_maker = Mock(return_value=mock_session)
    mock_factory = Mock()

    uow = AsyncSQLAlchemyUnitOfWork(mock_session_maker, mock_factory)

    # Act
    async with uow.open_session() as session:
        # Assert
        assert session is mock_session

    mock_session_maker.assert_called_once()


@pytest.mark.asyncio
async def test__open_session__with_isolation_level__applies() -> None:
    # Arrange
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    mock_session_maker = Mock(return_value=mock_session)
    mock_factory = Mock()

    uow = AsyncSQLAlchemyUnitOfWork(mock_session_maker, mock_factory)

    with patch("sqlalchemy_foundation_kit.uow.sqlalchemy.apply_isolation_level") as mock_apply:
        # Act
        async with uow.open_session(isolation_level=IsolationLevel.SERIALIZABLE):
            # Assert
            mock_apply.assert_called_once()


# ============================================================================
# transaction Tests
# ============================================================================


@pytest.mark.asyncio
async def test__transaction__commits_on_success() -> None:
    # Arrange
    mock_begin_context = AsyncMock()
    mock_begin_context.__aenter__ = AsyncMock(return_value=None)
    mock_begin_context.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin = Mock(return_value=mock_begin_context)
    mock_session.flush = AsyncMock()

    mock_transaction = Mock()
    mock_session_maker = Mock(return_value=mock_session)
    mock_factory = Mock(return_value=mock_transaction)

    uow = AsyncSQLAlchemyUnitOfWork(mock_session_maker, mock_factory)

    # Act
    async with uow.transaction() as tx:
        assert tx is mock_transaction

    # Assert
    mock_session.flush.assert_called_once()


@pytest.mark.asyncio
async def test__transaction__flushes_before_commit__when_enabled() -> None:
    # Arrange
    mock_begin_context = AsyncMock()
    mock_begin_context.__aenter__ = AsyncMock(return_value=None)
    mock_begin_context.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin = Mock(return_value=mock_begin_context)
    mock_session.flush = AsyncMock()

    mock_transaction = Mock()
    mock_session_maker = Mock(return_value=mock_session)
    mock_factory = Mock(return_value=mock_transaction)

    uow = AsyncSQLAlchemyUnitOfWork(mock_session_maker, mock_factory, flush_before_commit=True)

    # Act
    async with uow.transaction():
        pass

    # Assert
    mock_session.flush.assert_called_once()


@pytest.mark.asyncio
async def test__transaction__skips_flush__when_disabled() -> None:
    # Arrange
    mock_begin_context = AsyncMock()
    mock_begin_context.__aenter__ = AsyncMock(return_value=None)
    mock_begin_context.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin = Mock(return_value=mock_begin_context)
    mock_session.flush = AsyncMock()

    mock_transaction = Mock()
    mock_session_maker = Mock(return_value=mock_session)
    mock_factory = Mock(return_value=mock_transaction)

    uow = AsyncSQLAlchemyUnitOfWork(mock_session_maker, mock_factory, flush_before_commit=False)

    # Act
    async with uow.transaction():
        pass

    # Assert
    mock_session.flush.assert_not_called()


@pytest.mark.asyncio
async def test__transaction__flush_override__overrides_default() -> None:
    # Arrange
    mock_begin_context = AsyncMock()
    mock_begin_context.__aenter__ = AsyncMock(return_value=None)
    mock_begin_context.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin = Mock(return_value=mock_begin_context)
    mock_session.flush = AsyncMock()

    mock_transaction = Mock()
    mock_session_maker = Mock(return_value=mock_session)
    mock_factory = Mock(return_value=mock_transaction)

    uow = AsyncSQLAlchemyUnitOfWork(mock_session_maker, mock_factory, flush_before_commit=True)

    # Act
    async with uow.transaction(flush_before_commit=False):
        pass

    # Assert
    mock_session.flush.assert_not_called()


@pytest.mark.asyncio
async def test__transaction__flush_error__logs_warning_and_raises() -> None:
    # Arrange
    mock_begin_context = AsyncMock()
    mock_begin_context.__aenter__ = AsyncMock(return_value=None)
    mock_begin_context.__aexit__ = AsyncMock(return_value=None)

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin = Mock(return_value=mock_begin_context)
    mock_session.flush = AsyncMock(side_effect=SQLAlchemyError("Flush error"))

    mock_transaction = Mock()
    mock_session_maker = Mock(return_value=mock_session)
    mock_factory = Mock(return_value=mock_transaction)

    uow = AsyncSQLAlchemyUnitOfWork(mock_session_maker, mock_factory)

    # Act & Assert
    with patch("sqlalchemy_foundation_kit.uow.sqlalchemy.logger") as mock_logger:
        with pytest.raises(SQLAlchemyError):
            async with uow.transaction():
                pass

        mock_logger.warning.assert_called_once()


# ============================================================================
# managed_session Tests
# ============================================================================


@pytest.mark.asyncio
async def test__managed_session__yields_transaction_and_session() -> None:
    # Arrange
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_transaction = Mock()
    mock_session_maker = Mock(return_value=mock_session)
    mock_factory = Mock(return_value=mock_transaction)

    uow = AsyncSQLAlchemyUnitOfWork(mock_session_maker, mock_factory)

    # Act
    async with uow.managed_session() as (tx, session):
        # Assert
        assert tx is mock_transaction
        assert session is mock_session

    mock_session.begin.assert_called_once()


@pytest.mark.asyncio
async def test__managed_session__requires_manual_commit() -> None:
    # Arrange
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_transaction = Mock()
    mock_session_maker = Mock(return_value=mock_session)
    mock_factory = Mock(return_value=mock_transaction)

    uow = AsyncSQLAlchemyUnitOfWork(mock_session_maker, mock_factory)

    # Act
    async with uow.managed_session() as (tx, session):
        await session.commit()

    # Assert
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test__managed_session__exception__rolls_back() -> None:
    # Arrange
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    mock_session.begin = AsyncMock()
    mock_session.rollback = AsyncMock()

    mock_transaction = Mock()
    mock_session_maker = Mock(return_value=mock_session)
    mock_factory = Mock(return_value=mock_transaction)

    uow = AsyncSQLAlchemyUnitOfWork(mock_session_maker, mock_factory)

    # Act & Assert
    with pytest.raises(ValueError):
        async with uow.managed_session():
            raise ValueError("Test error")

    mock_session.rollback.assert_called_once()


# ============================================================================
# query Tests
# ============================================================================


@pytest.mark.asyncio
async def test__query__yields_transaction__no_transaction_management() -> None:
    # Arrange
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    mock_transaction = Mock()
    mock_session_maker = Mock(return_value=mock_session)
    mock_factory = Mock(return_value=mock_transaction)

    uow = AsyncSQLAlchemyUnitOfWork(mock_session_maker, mock_factory)

    # Act
    async with uow.query() as qx:
        # Assert
        assert qx is mock_transaction


@pytest.mark.asyncio
async def test__query__with_isolation_level__applies() -> None:
    # Arrange
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    mock_transaction = Mock()
    mock_session_maker = Mock(return_value=mock_session)
    mock_factory = Mock(return_value=mock_transaction)

    uow = AsyncSQLAlchemyUnitOfWork(mock_session_maker, mock_factory)

    with patch("sqlalchemy_foundation_kit.uow.sqlalchemy.apply_isolation_level") as mock_apply:
        # Act
        async with uow.query(isolation_level=IsolationLevel.READ_COMMITTED):
            pass

        # Assert
        mock_apply.assert_called_once()
