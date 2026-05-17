"""Unit of Work protocols."""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Protocol


class AsyncUowTransaction(Protocol):
    """Transaction-scoped repositories container.

    Intended to be extended by concrete transaction types that expose
    repository attributes for a specific bounded context.
    """


class SupportsAdvisoryLock(Protocol):
    """Capability protocol for transactions supporting advisory locks.

    Use this when your transaction needs PostgreSQL advisory lock support.
    Not all transactions require this capability (e.g., in-memory, read-only).

    Examples:
        >>> async def execute_with_lock(tx: SupportsAdvisoryLock, key: int) -> None:
        ...     if await tx.try_advisory_lock(key):
        ...         # Critical section protected by advisory lock
        ...         ...
    """

    async def try_advisory_lock(self, key: int) -> bool:
        """Try to acquire a transaction-scoped advisory lock identified by ``key``.

        Returns ``True`` if the lock was acquired (and is held for the rest of the
        transaction), ``False`` if another transaction already holds it.
        """
        ...


class AsyncUnitOfWork[T: AsyncUowTransaction](Protocol):
    """Provides transactional context for repository operations.

    Provides two modes of operation:
    - transaction(): For write operations with automatic commit/rollback
    - query(): For read-only operations without transaction management
    """

    def transaction(
        self,
        isolation_level: str | None = None,
        flush_before_commit: bool | None = None,
        auto_commit: bool = True,
    ) -> AbstractAsyncContextManager[T]:
        """Create a new transaction context.

        Args:
            isolation_level: Optional transaction isolation level.
            flush_before_commit: If True, flush session before commit to surface
                constraint violations within transaction. If ``None``, the implementation
                applies its own default (typically configured at construction time).
                Only applies when auto_commit=True.
            auto_commit: If True, automatically commit on success or rollback on exception.
                If False, caller must call session.commit() or session.rollback() manually.
        """

    def query(self, isolation_level: str | None = None) -> AbstractAsyncContextManager[T]:
        """Create a read-only query context."""
