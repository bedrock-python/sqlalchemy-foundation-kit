"""Integration tests for the Unit of Work against a real PostgreSQL."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from sqlalchemy_foundation_kit.session.manager import AsyncSessionManager
from sqlalchemy_foundation_kit.uow.enums import IsolationLevel
from sqlalchemy_foundation_kit.uow.sqlalchemy import AsyncSQLAlchemyUnitOfWork, AsyncSQLAlchemyUowTransaction
from tests.integration.conftest import SEARCH_PATH_SCHEMA, PostgresContainer, asyncpg_url
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


# ============================================================================
# search_path Tests (issue #23 scenario)
# ============================================================================


@pytest.fixture
def schema_uow(
    schema_session_manager: AsyncSessionManager[AsyncSession],
) -> AsyncSQLAlchemyUnitOfWork[AsyncSQLAlchemyUowTransaction]:
    return AsyncSQLAlchemyUnitOfWork(
        schema_session_manager.session_maker, transaction_factory=AsyncSQLAlchemyUowTransaction
    )


async def _search_path(session: AsyncSession) -> str:
    return (await session.execute(text("SHOW search_path"))).scalar_one()  # type: ignore[no-any-return]


@pytest.mark.integration
@pytest.mark.asyncio
async def test__transaction__search_path__applied_to_the_transaction(
    schema_uow: AsyncSQLAlchemyUnitOfWork[AsyncSQLAlchemyUowTransaction],
) -> None:
    # Act
    async with schema_uow.transaction() as tx:
        actual = await _search_path(tx.session)

    # Assert
    assert actual == SEARCH_PATH_SCHEMA


@pytest.mark.integration
@pytest.mark.asyncio
async def test__query__search_path__applied_to_the_transaction(
    schema_uow: AsyncSQLAlchemyUnitOfWork[AsyncSQLAlchemyUowTransaction],
) -> None:
    # Act
    async with schema_uow.query() as qx:
        actual = await _search_path(qx.session)

    # Assert
    assert actual == SEARCH_PATH_SCHEMA


@pytest.mark.integration
@pytest.mark.asyncio
async def test__transaction__search_path_and_isolation_level__both_applied(
    schema_uow: AsyncSQLAlchemyUnitOfWork[AsyncSQLAlchemyUowTransaction],
) -> None:
    # Act
    async with schema_uow.transaction(isolation_level=IsolationLevel.SERIALIZABLE) as tx:
        search_path = await _search_path(tx.session)
        isolation = await _transaction_isolation(tx.session)

    # Assert
    assert search_path == SEARCH_PATH_SCHEMA
    assert isolation == "serializable"


@pytest.mark.integration
@pytest.mark.asyncio
async def test__transaction__search_path__held_inside_and_after_a_savepoint(
    schema_uow: AsyncSQLAlchemyUnitOfWork[AsyncSQLAlchemyUowTransaction],
) -> None:
    # Act
    async with schema_uow.transaction() as tx:
        async with tx.savepoint():
            inside = await _search_path(tx.session)
        after = await _search_path(tx.session)

    # Assert
    assert inside == SEARCH_PATH_SCHEMA
    assert after == SEARCH_PATH_SCHEMA


@pytest.mark.integration
@pytest.mark.asyncio
async def test__managed_session__search_path__reapplied_after_the_caller_commits(
    schema_uow: AsyncSQLAlchemyUnitOfWork[AsyncSQLAlchemyUowTransaction],
) -> None:
    # Act: the commit ends the transaction the schema was set on; the next statement
    # autobegins a new one, which has to see the schema again
    async with schema_uow.managed_session() as (_tx, session):
        before = await _search_path(session)
        await session.execute(text("INSERT INTO schema_probe (v) VALUES (1)"))
        await session.commit()
        after = await _search_path(session)
        count = (await session.execute(text("SELECT count(*) FROM schema_probe"))).scalar_one()
        await session.rollback()

    # Assert
    assert before == SEARCH_PATH_SCHEMA
    assert after == SEARCH_PATH_SCHEMA
    assert count == 1


# ============================================================================
# Failed Flush Logging Tests (issue #57 scenario)
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("flush_before_commit", [True, False])
async def test__transaction__failed_flush__row_values_reach_the_caller_and_no_log(
    async_session_factory: async_sessionmaker[AsyncSession],
    caplog: pytest.LogCaptureFixture,
    flush_before_commit: bool,
) -> None:
    # Arrange: the reporter's duplicate email, on the default flush_before_commit=True path too
    uow = AsyncSQLAlchemyUnitOfWork(async_session_factory, transaction_factory=AsyncSQLAlchemyUowTransaction)
    email = "jane.doe@example.org"
    async with uow.transaction() as tx:
        tx.session.add(TestUser(name="Jane", email=email, age=30))

    # Act
    with caplog.at_level(logging.DEBUG, logger="sqlalchemy_foundation_kit"):
        with pytest.raises(IntegrityError) as raised:
            async with uow.transaction(flush_before_commit=flush_before_commit) as tx:
                tx.session.add(TestUser(name="Jane again", email=email, age=31))

    # Assert: the caller has everything needed to debug it...
    assert raised.value.orig is not None
    assert getattr(raised.value.orig, "sqlstate", None) == "23505"
    assert getattr(raised.value.orig.__cause__, "constraint_name", None) == "test_users_email_key"
    assert email in str(raised.value)
    # ...and the library wrote none of it to the logs, at any level
    assert [r for r in caplog.records if r.name.startswith("sqlalchemy_foundation_kit")] == []


# ============================================================================
# Read-Only query() Tests (issue #56 scenario)
# ============================================================================

READ_ONLY_SQL_TRANSACTION = "25006"


@dataclass
class _OneConnection:
    kind: str = "async_adapted_queue"
    size: int = 1
    max_overflow: int = 0
    pre_ping: bool = False
    recycle: int = -1
    timeout: float = 5.0


def _sqlstate(error: DBAPIError) -> str | None:
    return getattr(error.orig, "sqlstate", None)


@pytest.mark.integration
@pytest.mark.asyncio
async def test__query__insert_and_commit__rejected_and_nothing_persisted(
    uow: AsyncSQLAlchemyUnitOfWork[AsyncSQLAlchemyUowTransaction],
    async_session: AsyncSession,
) -> None:
    # Arrange: the reporter's write through query(), committed explicitly
    email = "written-inside-query@example.com"

    # Act
    with pytest.raises(DBAPIError) as raised:
        async with uow.query() as qx:
            qx.session.add(TestUser(name="Query", email=email, age=30))
            await qx.session.commit()

    # Assert
    assert _sqlstate(raised.value) == READ_ONLY_SQL_TRANSACTION
    result = await async_session.execute(select(TestUser).where(TestUser.email == email))
    assert result.scalar_one_or_none() is None


@pytest.mark.integration
@pytest.mark.asyncio
async def test__query__reads__run_in_a_read_only_transaction(
    uow: AsyncSQLAlchemyUnitOfWork[AsyncSQLAlchemyUowTransaction],
) -> None:
    # Act
    async with uow.query() as qx:
        read_only = (await qx.session.execute(text("SHOW transaction_read_only"))).scalar_one()
        users = (await qx.session.execute(select(func.count()).select_from(TestUser))).scalar_one()

    # Assert
    assert read_only == "on"
    assert users == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test__query__isolation_level__read_only_as_well(
    uow: AsyncSQLAlchemyUnitOfWork[AsyncSQLAlchemyUowTransaction],
) -> None:
    # Act: the isolation level checks the connection out first, so the block marks the
    # transaction itself
    async with uow.query(isolation_level=IsolationLevel.SERIALIZABLE) as qx:
        isolation = await _transaction_isolation(qx.session)
        read_only = (await qx.session.execute(text("SHOW transaction_read_only"))).scalar_one()

    # Assert
    assert (isolation, read_only) == ("serializable", "on")


class _StatementFirstUnitOfWork(AsyncSQLAlchemyUnitOfWork[AsyncSQLAlchemyUowTransaction]):
    """The ``open_session`` override from its docstring: a statement before the block runs."""

    @asynccontextmanager
    async def open_session(self, isolation_level: IsolationLevel | str | None = None) -> AsyncIterator[AsyncSession]:
        async with super().open_session(isolation_level) as session:
            await session.execute(text("SELECT set_config('app.tenant_id', '7', true)"))
            yield session


@pytest.mark.integration
@pytest.mark.asyncio
async def test__query__open_session_override_ran_a_statement__still_read_only(
    async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Arrange
    uow = _StatementFirstUnitOfWork(async_session_factory, transaction_factory=AsyncSQLAlchemyUowTransaction)

    # Act
    with pytest.raises(DBAPIError) as raised:
        async with uow.query() as qx:
            tenant = (await qx.session.execute(text("SELECT current_setting('app.tenant_id')"))).scalar_one()
            assert tenant == "7"
            await qx.session.execute(text("INSERT INTO test_users (name, email, age) VALUES ('x', 'x@x', 1)"))

    # Assert
    assert _sqlstate(raised.value) == READ_ONLY_SQL_TRANSACTION


@pytest.mark.integration
@pytest.mark.asyncio
async def test__query__connection_back_in_the_pool__next_transaction_can_write(
    postgres_container: PostgresContainer,
) -> None:
    # Arrange: one connection, so the transaction after query() gets the very same one
    manager: AsyncSessionManager[AsyncSession] = AsyncSessionManager(
        asyncpg_url(postgres_container),
        poolclass="async_adapted_queue",
        pool_settings=_OneConnection(),
    )
    uow = AsyncSQLAlchemyUnitOfWork(manager.session_maker, transaction_factory=AsyncSQLAlchemyUowTransaction)

    # Act
    async with manager:
        async with uow.query() as qx:
            reader_pid = (await qx.session.execute(text("SELECT pg_backend_pid()"))).scalar_one()
        async with uow.transaction() as tx:
            writer_pid = (await tx.session.execute(text("SELECT pg_backend_pid()"))).scalar_one()
            read_only = (await tx.session.execute(text("SHOW transaction_read_only"))).scalar_one()
            tx.session.add(TestUser(name="After", email="after-query@example.com", age=40))

    # Assert
    assert writer_pid == reader_pid
    assert read_only == "off"


@pytest.mark.integration
@pytest.mark.asyncio
async def test__query__advisory_lock__held_until_the_block_exits(
    uow: AsyncSQLAlchemyUnitOfWork[AsyncSQLAlchemyUowTransaction],
    async_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    # Act
    async with uow.query() as qx:
        mine = (await qx.session.execute(text("SELECT pg_try_advisory_xact_lock(56)"))).scalar_one()
        async with async_session_factory() as other:
            theirs_meanwhile = (await other.execute(text("SELECT pg_try_advisory_xact_lock(56)"))).scalar_one()
    async with async_session_factory() as other:
        theirs_after = (await other.execute(text("SELECT pg_try_advisory_xact_lock(56)"))).scalar_one()

    # Assert
    assert (mine, theirs_meanwhile, theirs_after) == (True, False, True)
