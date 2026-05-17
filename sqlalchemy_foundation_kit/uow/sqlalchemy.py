"""Unit of Work implementation (async SQLAlchemy)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..session.locks import try_advisory_xact_lock
from .enums import IsolationLevel
from .protocols import AsyncUnitOfWork, AsyncUowTransaction

logger = logging.getLogger(__name__)


def normalize_isolation_level(isolation_level: IsolationLevel | str | None) -> str | None:
    """Normalize isolation_level to a valid PostgreSQL string or None.

    Accepts both enum members and strings. Strings may use either underscores
    or spaces (e.g., "READ_COMMITTED" or "READ COMMITTED") for convenience.

    Args:
        isolation_level: Enum member, string, or None.

    Returns:
        PostgreSQL-form string (with spaces) valid for execution_options, or None.

    Raises:
        ValueError: If isolation_level is not supported.
    """
    if not isolation_level:
        return None
    if isinstance(isolation_level, IsolationLevel):
        return isolation_level.value
    level_str = str(isolation_level).upper().replace("_", " ")
    valid_levels = {item.value for item in IsolationLevel}
    if level_str not in valid_levels:
        raise ValueError(
            f"Unsupported isolation level: {isolation_level}. Supported values: {', '.join(sorted(valid_levels))}"
        )
    return level_str


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

    async def try_advisory_lock(self, key: int) -> bool:
        """Acquire a Postgres transaction-scoped advisory lock.

        Delegates to :func:`try_advisory_xact_lock` for actual locking logic.

        Args:
            key: Integer lock key.

        Returns:
            True if lock was acquired, False if already held by another session.
        """
        return await try_advisory_xact_lock(self.session, key)


class AsyncSQLAlchemyUnitOfWork[T: AsyncUowTransaction](AsyncUnitOfWork[T]):
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
        isolation_level = normalize_isolation_level(isolation_level)
        options = {"isolation_level": isolation_level} if isolation_level else {}

        async with self._session_maker() as session:
            if options:
                conn = await session.connection()
                await conn.run_sync(lambda c: c.execution_options(**options))
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

        async with self.open_session(isolation_level) as session, session.begin():
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

        Note:
            The session.begin() is called automatically, but you must handle
            commit/rollback manually. If you exit the context without calling
            either, SQLAlchemy will automatically rollback.
        """
        async with self.open_session(isolation_level) as session:
            async with session.begin():
                uow = self._transaction_factory(session)
                yield uow, session
                # No auto-commit - user must call session.commit() or session.rollback()

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
