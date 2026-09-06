"""Integration tests for the Unit of Work against a real PostgreSQL."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sqlalchemy_foundation_kit.uow.enums import IsolationLevel
from sqlalchemy_foundation_kit.uow.sqlalchemy import AsyncSQLAlchemyUnitOfWork, AsyncSQLAlchemyUowTransaction
from tests.integration.models import TestUser


class BatchTransaction(AsyncSQLAlchemyUowTransaction):
    """Transaction exposing just enough for the batch scenario, without leaking the session."""

    async def create_scratch_table(self) -> None:
        await self.session.execute(text("CREATE TEMP TABLE processed (item int) ON COMMIT DROP"))

    async def process(self, item: int) -> None:
        await self.session.execute(text("SELECT 100 / :i"), {"i": item})
        await self.session.execute(text("INSERT INTO processed VALUES (:i)"), {"i": item})

    async def count_processed(self) -> int:
        return (await self.session.execute(text("SELECT count(*) FROM processed"))).scalar_one()


@pytest.fixture
def batch_uow(async_session_factory: async_sessionmaker[AsyncSession]) -> AsyncSQLAlchemyUnitOfWork[BatchTransaction]:
    return AsyncSQLAlchemyUnitOfWork(async_session_factory, transaction_factory=BatchTransaction)


# ============================================================================
# Savepoint Tests (issue #5 scenario)
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test__savepoint__failed_item__does_not_poison_batch(
    batch_uow: AsyncSQLAlchemyUnitOfWork[BatchTransaction],
) -> None:
    # Arrange
    items = [1, 2, 0, 4]
    done: list[int] = []
    failed: list[int] = []

    # Act
    async with batch_uow.transaction() as tx:
        await tx.create_scratch_table()
        for item in items:
            try:
                async with tx.savepoint():
                    await tx.process(item)
                done.append(item)
            except DBAPIError:
                failed.append(item)
        rows_recorded = await tx.count_processed()

    # Assert
    assert done == [1, 2, 4]
    assert failed == [0]
    assert rows_recorded == 3


@pytest.mark.integration
@pytest.mark.asyncio
async def test__no_savepoint__failed_item__poisons_batch(
    batch_uow: AsyncSQLAlchemyUnitOfWork[BatchTransaction],
) -> None:
    # Arrange
    items = [1, 2, 0, 4]
    done: list[int] = []
    failed: list[int] = []

    # Act: the control case — without a savepoint the first failure aborts the transaction,
    # so item 4 fails as collateral damage and the read-back cannot run at all.
    with pytest.raises(DBAPIError):
        async with batch_uow.transaction() as tx:
            await tx.create_scratch_table()
            for item in items:
                try:
                    await tx.process(item)
                    done.append(item)
                except DBAPIError:
                    failed.append(item)
            await tx.count_processed()

    # Assert
    assert done == [1, 2]
    assert failed == [0, 4]


@pytest.mark.integration
@pytest.mark.asyncio
async def test__savepoint__integrity_error__outer_transaction_commits_valid_rows(
    async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Arrange
    uow = AsyncSQLAlchemyUnitOfWork(async_session_factory, transaction_factory=AsyncSQLAlchemyUowTransaction)
    users = [
        TestUser(name="First", email="first@example.com"),
        TestUser(name="Duplicate", email="first@example.com"),
        TestUser(name="Third", email="third@example.com"),
    ]
    failed: list[str] = []

    # Act
    async with uow.transaction() as tx:
        for user in users:
            try:
                async with tx.savepoint():
                    tx.session.add(user)
                    await tx.session.flush()
            except IntegrityError:
                failed.append(user.name)

    # Assert
    assert failed == ["Duplicate"]
    async with async_session_factory() as session:
        emails = (await session.execute(select(TestUser.email).order_by(TestUser.email))).scalars().all()
    assert list(emails) == ["first@example.com", "third@example.com"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test__savepoint__nested__inner_failure_keeps_outer_savepoint(
    async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Arrange
    uow = AsyncSQLAlchemyUnitOfWork(async_session_factory, transaction_factory=AsyncSQLAlchemyUowTransaction)

    # Act
    async with uow.transaction() as tx:
        async with tx.savepoint():
            tx.session.add(TestUser(name="Outer", email="outer@example.com"))
            await tx.session.flush()
            try:
                async with tx.savepoint():
                    tx.session.add(TestUser(name="Inner", email="inner@example.com"))
                    await tx.session.flush()
                    raise ValueError("Rollback inner only")
            except ValueError:
                pass

    # Assert
    async with async_session_factory() as session:
        count = (await session.execute(select(func.count()).select_from(TestUser))).scalar_one()
        emails = (await session.execute(select(TestUser.email))).scalars().all()
    assert count == 1
    assert list(emails) == ["outer@example.com"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test__savepoint__inside_managed_session__transaction_stays_usable(
    async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Arrange
    uow = AsyncSQLAlchemyUnitOfWork(async_session_factory, transaction_factory=AsyncSQLAlchemyUowTransaction)

    # Act
    async with uow.managed_session() as (tx, session):
        with pytest.raises(DBAPIError):
            async with tx.savepoint():
                await session.execute(text("SELECT 1 / 0"))
        session.add(TestUser(name="After failure", email="after@example.com"))
        await session.commit()

    # Assert
    async with async_session_factory() as session:
        emails = (await session.execute(select(TestUser.email))).scalars().all()
    assert list(emails) == ["after@example.com"]


# ============================================================================
# Isolation Level Tests
# ============================================================================


@pytest.fixture
def uow(
    async_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncSQLAlchemyUnitOfWork[AsyncSQLAlchemyUowTransaction]:
    return AsyncSQLAlchemyUnitOfWork(async_session_factory, transaction_factory=AsyncSQLAlchemyUowTransaction)


async def _transaction_isolation(session: AsyncSession) -> str:
    return (await session.execute(text("SHOW transaction_isolation"))).scalar_one()  # type: ignore[no-any-return]


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "isolation_level,expected",
    [
        (IsolationLevel.SERIALIZABLE, "serializable"),
        (IsolationLevel.REPEATABLE_READ, "repeatable read"),
        ("READ_COMMITTED", "read committed"),
    ],
)
async def test__transaction__isolation_level__applied_to_the_transaction(
    uow: AsyncSQLAlchemyUnitOfWork[AsyncSQLAlchemyUowTransaction],
    isolation_level: IsolationLevel | str,
    expected: str,
) -> None:
    # Act
    async with uow.transaction(isolation_level=isolation_level) as tx:
        actual = await _transaction_isolation(tx.session)

    # Assert
    assert actual == expected


@pytest.mark.integration
@pytest.mark.asyncio
async def test__managed_session__isolation_level__applied_to_the_transaction(
    uow: AsyncSQLAlchemyUnitOfWork[AsyncSQLAlchemyUowTransaction],
) -> None:
    # Act
    async with uow.managed_session(isolation_level=IsolationLevel.SERIALIZABLE) as (_tx, session):
        actual = await _transaction_isolation(session)
        await session.rollback()

    # Assert
    assert actual == "serializable"


@pytest.mark.integration
@pytest.mark.asyncio
async def test__query__isolation_level__applied_to_the_transaction(
    uow: AsyncSQLAlchemyUnitOfWork[AsyncSQLAlchemyUowTransaction],
) -> None:
    # Act
    async with uow.query(isolation_level=IsolationLevel.REPEATABLE_READ) as qx:
        actual = await _transaction_isolation(qx.session)

    # Assert
    assert actual == "repeatable read"


@pytest.mark.integration
@pytest.mark.asyncio
async def test__transaction__isolation_level__still_commits(
    uow: AsyncSQLAlchemyUnitOfWork[AsyncSQLAlchemyUowTransaction],
    async_session: AsyncSession,
) -> None:
    # Arrange
    email = "uow-isolation-commit@example.com"

    # Act
    async with uow.transaction(isolation_level=IsolationLevel.SERIALIZABLE) as tx:
        tx.session.add(TestUser(name="Serializable", email=email, age=33))

    # Assert
    result = await async_session.execute(select(TestUser).where(TestUser.email == email))
    assert result.scalar_one_or_none() is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test__transaction__isolation_level__rolls_back_on_exception(
    uow: AsyncSQLAlchemyUnitOfWork[AsyncSQLAlchemyUowTransaction],
    async_session: AsyncSession,
) -> None:
    # Arrange
    email = "uow-isolation-rollback@example.com"

    # Act
    with pytest.raises(ValueError):
        async with uow.transaction(isolation_level=IsolationLevel.SERIALIZABLE) as tx:
            tx.session.add(TestUser(name="Serializable", email=email, age=33))
            await tx.session.flush()
            raise ValueError("Intentional rollback")

    # Assert
    result = await async_session.execute(select(TestUser).where(TestUser.email == email))
    assert result.scalar_one_or_none() is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test__transaction__invalid_isolation_level__raises_value_error(
    uow: AsyncSQLAlchemyUnitOfWork[AsyncSQLAlchemyUowTransaction],
) -> None:
    # Act & Assert
    with pytest.raises(ValueError, match="Invalid isolation level"):
        async with uow.transaction(isolation_level="NOT A LEVEL"):
            pass
