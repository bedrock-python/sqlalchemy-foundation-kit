"""Unit of Work protocols."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Any, Generic, Protocol

from .._typing import T_co


class AsyncUowTransaction(Protocol):
    """Transaction-scoped repositories container.

    Intended to be extended by concrete transaction types that expose
    repository attributes for a specific bounded context.
    """


class SupportsAdvisoryLock(Protocol):
    """Capability protocol for transactions supporting advisory locks.

    Use this when your transaction needs PostgreSQL advisory lock support.
    Not all transactions require this capability (e.g., in-memory, read-only).
    """

    async def try_advisory_lock(self, key: int) -> bool:
        """Try to acquire a transaction-scoped advisory lock identified by ``key``.

        Returns ``True`` if the lock was acquired (and is held for the rest of the
        transaction), ``False`` if another transaction already holds it.
        """
        ...


class AsyncUnitOfWork(Protocol, Generic[T_co]):
    """Provides transactional context for repository operations.

    Provides three modes of operation:
        - ``transaction()``: For write operations with automatic commit/rollback.
        - ``managed_session()``: For write operations with **manual** commit/rollback control.
        - ``query()``: For read-only operations without transaction management.
    """

    def transaction(
        self,
        isolation_level: str | None = None,
        flush_before_commit: bool | None = None,
    ) -> AbstractAsyncContextManager[T_co]:
        """Create a new transaction context with automatic commit/rollback.

        Args:
            isolation_level: Optional transaction isolation level.
            flush_before_commit: If True, flush session before commit to surface
                constraint violations within transaction. If ``None``, the implementation
                applies its own default (typically configured at construction time).
        """

    def managed_session(
        self,
        isolation_level: str | None = None,
    ) -> AbstractAsyncContextManager[tuple[T_co, Any]]:
        """Create a session with manual transaction control.

        Unlike :meth:`transaction`, this does **NOT** auto-commit on success. The caller
        must explicitly call ``session.commit()`` or ``session.rollback()``. Useful for
        complex transactional logic where the commit decision depends on multiple
        conditions or external factors.

        The second element of the yielded tuple is the underlying session object
        (typed as ``Any`` in the protocol to avoid leaking SQLAlchemy types — concrete
        implementations like ``AsyncSQLAlchemyUnitOfWork`` yield ``AsyncSession``).

        On exception inside the context, the session is automatically rolled back.

        Args:
            isolation_level: Optional transaction isolation level.
        """

    def query(self, isolation_level: str | None = None) -> AbstractAsyncContextManager[T_co]:
        """Create a read-only query context without transaction management."""
