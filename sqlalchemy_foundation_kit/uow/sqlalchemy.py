"""Unit of Work implementation (async SQLAlchemy)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Generic

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .._typing import T
from ..session.locks import try_advisory_xact_lock
from .enums import IsolationLevel
from .protocols import AsyncUnitOfWork, AsyncUowTransaction

logger = logging.getLogger(__name__)

# Cache valid isolation levels for performance (avoid recreating set on each call)
_VALID_ISOLATION_LEVELS: frozenset[str] = frozenset(item.value for item in IsolationLevel)


def normalize_isolation_level(
    isolation_level: IsolationLevel | str | None,
) -> str | None:
    """Normalize isolation_level to a valid PostgreSQL string or None.

    Accepts both enum members and strings. Strings may use either underscores
    or spaces (e.g., "READ_COMMITTED" or "READ COMMITTED") for convenience.

    Args:
        isolation_level: Enum member, string, or None.

    Returns:
        PostgreSQL-form string (with spaces) valid for execution_options, or None.

    Raises:
        ValueError: If isolation_level is not supported.

    Examples:
        >>> normalize_isolation_level(None)
        None
        >>> normalize_isolation_level(IsolationLevel.READ_COMMITTED)
        'READ COMMITTED'
        >>> normalize_isolation_level("READ_COMMITTED")
        'READ COMMITTED'
        >>> normalize_isolation_level("read committed")
        'READ COMMITTED'
    """
    # Explicit None check (PEP 8: explicit is better than implicit)
    if isolation_level is None:
        return None

    # Fast path for enum members
    if isinstance(isolation_level, IsolationLevel):
        return isolation_level.value

    # Normalize string input: uppercase and replace underscores with spaces
    normalized = str(isolation_level).upper().replace("_", " ")

    # Validate against cached valid levels
    if normalized not in _VALID_ISOLATION_LEVELS:
        supported = ", ".join(sorted(_VALID_ISOLATION_LEVELS))
        raise ValueError(f"Invalid isolation level: {isolation_level!r}. Supported values: {supported}")

    return normalized


async def apply_isolation_level(
    session: AsyncSession,
    isolation_level: IsolationLevel | str | None,
) -> None:
    """Apply isolation level to an async session's connection.

    The level has to reach the connection *before* the connection begins its
    transaction — PostgreSQL cannot change the isolation level of a transaction that
    is already running, and SQLAlchemy raises ``InvalidRequestError`` if you try. So
    the level is handed to the ``session.connection()`` call that checks the
    connection out, which applies it and only then begins.

    Call this on a session that has not yet talked to the database. It starts the
    session's transaction as a side effect, so a caller that wants to own the
    transaction should join the one already open rather than call ``session.begin()``.

    This is a DRY utility to eliminate duplication of isolation level application
    logic across ``transaction()``, ``managed_session()``, and ``query()`` methods.

    Args:
        session: SQLAlchemy AsyncSession to configure.
        isolation_level: Desired isolation level (enum, string, or None).

    Raises:
        ValueError: If isolation_level is not supported (raised by normalize_isolation_level).

    Examples:
        >>> async with session_maker() as session:
        ...     await apply_isolation_level(session, IsolationLevel.SERIALIZABLE)
        ...     result = await session.execute(select(User))
        ...     # Query runs with SERIALIZABLE isolation level

        Using string isolation level:
        >>> await apply_isolation_level(session, "READ COMMITTED")

        No-op when None:
        >>> await apply_isolation_level(session, None)  # Does nothing
    """
    normalized = normalize_isolation_level(isolation_level)
    if normalized is not None:
        await session.connection(execution_options={"isolation_level": normalized})


@asynccontextmanager
async def _owned_transaction(session: AsyncSession) -> AsyncIterator[None]:
    """Run a block inside a transaction, committing on success and rolling back on failure.

    ``session.begin()`` refuses to start a second transaction, and applying an isolation
    level has to check a connection out — which begins one. So the transaction is only
    started here when the session does not already have one, and the commit/rollback is
    driven explicitly instead of by the ``session.begin()`` context manager.
    """
    if not session.in_transaction():
        await session.begin()

    try:
        yield
    except BaseException:
        await session.rollback()
        raise

    try:
        await session.commit()
    except BaseException:
        await session.rollback()
        raise


class AsyncSQLAlchemyUowTransaction(AsyncUowTransaction):
    """Base async SQLAlchemy transaction-scoped repositories.

    This class provides access to the underlying SQLAlchemy session and is
    intended to be subclassed by services to expose specific repositories.

    Example:
        class IdentityTransaction(AsyncSQLAlchemyUowTransaction):
            @property
            def users(self) -> UserRepository:
                return PostgresUserRepository(self.session)
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def session(self) -> AsyncSession:
        """Get the underlying SQLAlchemy async session."""
        return self._session

    @asynccontextmanager
    async def savepoint(self) -> AsyncIterator[None]:
        """Open a savepoint whose failure does not poison the surrounding transaction.

        On PostgreSQL a single failed statement aborts the whole transaction: every
        later statement on the connection fails until rollback, including the ones
        that would record which step failed. A savepoint (``SAVEPOINT`` /
        ``ROLLBACK TO SAVEPOINT``) narrows that blast radius to this block.

        On exception the block's changes are rolled back, the exception propagates
        unchanged — the caller decides what a failed step means — and the surrounding
        transaction stays usable. On success the savepoint is released and its changes
        remain part of the surrounding transaction, committed or rolled back with it.
        Savepoints nest: a ``savepoint()`` inside another rolls back only the inner block.

        Intended for use inside :meth:`AsyncSQLAlchemyUnitOfWork.transaction` or
        :meth:`AsyncSQLAlchemyUnitOfWork.managed_session`.

        Example:
            async with uow.transaction() as tx:
                for event in await tx.outbox.list_pending():
                    try:
                        async with tx.savepoint():
                            await tx.outbox.process(event)
                    except Exception as exc:
                        await tx.outbox.mark_failed(event, reason=str(exc))
                # Commits processed events and failure records together
        """
        async with self._session.begin_nested():
            yield


class PostgresAdvisoryLockMixin:
    """Mixin providing PostgreSQL advisory lock support for UoW transactions.

    Requires the class to have a `session` property returning AsyncSession.

    Example:
        class IdentityTransaction(AsyncSQLAlchemyUowTransaction, PostgresAdvisoryLockMixin):
            @property
            def users(self) -> UserRepository:
                return PostgresUserRepository(self.session)

        # Now has access to try_advisory_lock method
        async with uow.transaction() as tx:
            if await tx.try_advisory_lock(12345):
                # Protected operation
                ...
    """

    session: AsyncSession  # Type annotation for protocol compliance

    async def try_advisory_lock(self, key: str | int) -> bool:
        """Acquire a Postgres transaction-scoped advisory lock.

        Delegates to :func:`try_advisory_xact_lock` for actual locking logic.

        Args:
            key: Lock key. An integer is used as-is; a string is hashed to one
                reproducibly, so the same string is the same lock in every process.

        Returns:
            True if lock was acquired, False if already held by another session.
        """
        return await try_advisory_xact_lock(self.session, key)


class AsyncSQLAlchemyUnitOfWork(AsyncUnitOfWork[T], Generic[T]):
    """Base async SQLAlchemy Unit of Work.

    Provides transactional context for repository operations using SQLAlchemy AsyncSession.

    Methods:
        transaction(): For write operations with automatic commit/rollback.
        query(): For read-only operations without transaction management.
    """

    def __init__(
        self,
        session_maker: async_sessionmaker[AsyncSession],
        transaction_factory: Callable[[AsyncSession], T],
        *,
        flush_before_commit: bool = True,
    ) -> None:
        """Initialize the unit of work.

        Args:
            session_maker: Async session factory.
            transaction_factory: Callable producing the transaction object exposed to callers.
            flush_before_commit: Default ``flush_before_commit`` policy applied when
                :meth:`transaction` is called without an explicit override.
                Set to ``False`` here once if your service prefers SQLAlchemy's default
                "flush on commit" semantics instead of an early flush.
        """
        self._session_maker = session_maker
        self._transaction_factory = transaction_factory
        self._flush_before_commit = flush_before_commit

    @asynccontextmanager
    async def open_session(
        self,
        isolation_level: IsolationLevel | str | None = None,
    ) -> AsyncIterator[AsyncSession]:
        """Open a session with optional isolation level applied.

        This is the extension point for subclasses that need custom session setup
        (e.g., RLS context, session-level GUCs, custom statement timeouts).
        Override to wrap or augment session creation while preserving isolation handling.

        Used internally by :meth:`transaction` and :meth:`query`.

        Args:
            isolation_level: Optional transaction isolation level.

        Yields:
            Configured AsyncSession instance.

        Raises:
            ValueError: If isolation_level is not supported.

        Examples:
            Subclass that sets a session-level GUC for every transaction:

                class TenantUnitOfWork(AsyncSQLAlchemyUnitOfWork):
                    def __init__(self, session_maker, tx_factory, tenant_id):
                        super().__init__(session_maker, tx_factory)
                        self._tenant_id = tenant_id

                    @asynccontextmanager
                    async def open_session(self, isolation_level=None):
                        async with super().open_session(isolation_level) as session:
                            await session.execute(
                                text("SET app.tenant_id = :tid"),
                                {"tid": self._tenant_id},
                            )
                            yield session
        """
        async with self._session_maker() as session:
            # Apply isolation level if specified (DRY: using utility function)
            await apply_isolation_level(session, isolation_level)
            yield session

    @asynccontextmanager
    async def transaction(
        self,
        isolation_level: IsolationLevel | str | None = None,
        flush_before_commit: bool | None = None,
    ) -> AsyncIterator[T]:
        """Create a new transaction context with automatic commit/rollback.

        The Unit of Work automatically commits the transaction on successful exit
        and rolls back on exception. This ensures atomic operations.

        Args:
            isolation_level: Optional transaction isolation level.
                Can be an IsolationLevel enum member or a string value.
                Supported values: "READ_COMMITTED", "REPEATABLE_READ", "SERIALIZABLE", "READ_UNCOMMITTED".
            flush_before_commit: If True, flush the session before commit to surface
                constraint violations while still inside the transaction. If ``None`` (default),
                falls back to the value passed to the constructor (``True`` unless overridden).

        Raises:
            ValueError: If isolation_level is not supported.

        Examples:
            Write operation with automatic commit:
                async with uow.transaction() as tx:
                    await tx.users.create(...)
                    # Auto-commit on exit, rollback on exception
        """
        if flush_before_commit is None:
            flush_before_commit = self._flush_before_commit

        async with self.open_session(isolation_level) as session, _owned_transaction(session):
            uow = self._transaction_factory(session)
            yield uow
            if flush_before_commit:
                # Flush changes before commit to catch constraint violations early
                # while still inside the transaction context.
                try:
                    await session.flush()
                except SQLAlchemyError as e:
                    logger.warning("Database flush failed", extra={"error": str(e)})
                    raise

    @asynccontextmanager
    async def managed_session(
        self,
        isolation_level: IsolationLevel | str | None = None,
    ) -> AsyncIterator[tuple[T, AsyncSession]]:
        """Create a session with manual transaction control.

        Unlike transaction(), this does NOT auto-commit. The caller must
        explicitly call session.commit() or session.rollback(). This is useful
        for complex transactional logic where commit decision depends on multiple
        conditions or external factors.

        A transaction is started automatically, but you have full control over
        when to commit or rollback. If you exit without calling either, SQLAlchemy
        will automatically rollback on session close.

        Args:
            isolation_level: Optional transaction isolation level.
                Can be an IsolationLevel enum member or a string value.
                Supported values: "READ_COMMITTED", "REPEATABLE_READ", "SERIALIZABLE", "READ_UNCOMMITTED".

        Yields:
            Tuple of (transaction object, session) for manual control.

        Raises:
            ValueError: If isolation_level is not supported.

        Examples:
            Manual transaction control:
                async with uow.managed_session() as (tx, session):
                    await tx.users.create(...)

                    # Manually decide when to commit
                    if should_commit:
                        await session.commit()
                    else:
                        await session.rollback()

            Conditional commit based on external service:
                async with uow.managed_session() as (tx, session):
                    user = await tx.users.create(...)

                    # Call external service
                    result = await external_api.validate(user)

                    if result.success:
                        await session.commit()
                    else:
                        await session.rollback()

            Multiple operations with intermediate decision:
                async with uow.managed_session() as (tx, session):
                    user = await tx.users.create(...)

                    # First checkpoint
                    await session.flush()

                    # More operations
                    await tx.profiles.create(user_id=user.id)

                    # Final decision
                    await session.commit()

        Note:
            Prefer :meth:`transaction` for the vast majority of use cases — it commits
            automatically and enforces the UoW pattern. This method is an advanced escape
            hatch for scenarios where the commit/rollback decision depends on conditions
            that can only be evaluated after data is written (e.g., external service
            validation). ``session.commit()`` calls belong exclusively at the use-case
            boundary via this method, never inside repository implementations.

        Warning:
            You MUST explicitly call session.commit() or session.rollback().
            Exiting the context without calling either will result in automatic
            rollback when the session closes.
        """
        async with self.open_session(isolation_level) as session:
            # Start transaction WITHOUT context manager - no auto-commit.
            # An isolation level, if one was asked for, has already begun it.
            if not session.in_transaction():
                await session.begin()
            try:
                uow = self._transaction_factory(session)
                yield uow, session
            except (Exception, asyncio.CancelledError):
                # Auto-rollback on exception OR cancellation
                await session.rollback()
                raise
            # User must call session.commit() or session.rollback() explicitly

    @asynccontextmanager
    async def query(
        self,
        isolation_level: IsolationLevel | str | None = None,
    ) -> AsyncIterator[T]:
        """Create a read-only query context without transaction management.

        This method is designed for read-only operations and does not start a transaction
        or perform any commit/rollback. It's semantically clearer than managed_session()
        for read operations.

        Args:
            isolation_level: Optional transaction isolation level.
                Can be an IsolationLevel enum member or a string value.
                Supported values: "READ_COMMITTED", "REPEATABLE_READ", "SERIALIZABLE", "READ_UNCOMMITTED".

        Raises:
            ValueError: If isolation_level is not supported.

        Examples:
            Read-only query:
                async with uow.query() as qx:
                    users = await qx.users.list_all()
                    user = await qx.users.get_by_id(user_id)
                # No commit/rollback - just closes session

        Note:
            While this method is intended for read-only operations, SQLAlchemy does not enforce
            this at the session level. It's up to the caller to ensure only read operations are performed.
        """
        async with self.open_session(isolation_level) as session:
            # No transaction begin/commit - just yield the session
            uow = self._transaction_factory(session)
            yield uow
