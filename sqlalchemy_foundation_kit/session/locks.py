"""PostgreSQL advisory locks (async)."""

import hashlib

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# PostgreSQL bigint (signed 64-bit) range constants
_INT64_OFFSET: int = 1 << 63  # 2^63 = 9223372036854775808
_INT64_MASK: int = (1 << 64) - 1  # 2^64 - 1 = 18446744073709551615


async def try_advisory_xact_lock(session: AsyncSession, key: str | int) -> bool:
    """Acquire a Postgres transaction-scoped advisory lock.

    Uses ``pg_try_advisory_xact_lock``: non-blocking, released automatically
    at transaction end. String keys are hashed to integers. The key is then
    truncated to signed 64-bit as Postgres expects.

    A string key produces the same lock in every process, on every host and in
    every release of the library, so two replicas of a service asking for
    ``"nightly-rollup"`` contend for one lock.

    Args:
        session: SQLAlchemy AsyncSession within an active transaction.
        key: Lock identifier (string or integer). Strings are hashed to integers.

    Returns:
        True if lock was acquired, False if already held by another session.

    Examples:
        >>> async with session_maker() as session:
        ...     async with session.begin():
        ...         if await try_advisory_xact_lock(session, "my_operation"):
        ...             # Perform protected operation
        ...             await session.execute(...)
        ...             await session.commit()
    """
    # Convert string keys to integers via hashing
    int_key = _hash_lock_key(key) if isinstance(key, str) else key

    result = await session.execute(
        text("SELECT pg_try_advisory_xact_lock(:k)"),
        {"k": _to_signed64(int_key)},
    )
    return bool(result.scalar())


def _hash_lock_key(key: str) -> int:
    """Hash a string lock key into the PostgreSQL bigint range, reproducibly.

    Python's built-in ``hash()`` is unusable here: string hashing is salted per
    interpreter, so the same key becomes a different lock in every process and two
    replicas of the same service lock nothing against each other. BLAKE2b is
    deterministic, so the key is stable across processes, hosts and restarts.

    Args:
        key: Lock identifier.

    Returns:
        A signed 64-bit integer suitable for ``pg_try_advisory_xact_lock``.

    Examples:
        >>> _hash_lock_key("nightly-rollup") == _hash_lock_key("nightly-rollup")
        True
    """
    digest = hashlib.blake2b(key.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=True)


def _to_signed64(key: int) -> int:
    """Wrap integer to PostgreSQL signed 64-bit bigint range.

    PostgreSQL advisory locks use bigint (signed 64-bit integers).
    This function wraps arbitrary Python ints into the range [-2^63, 2^63-1].

    Args:
        key: Integer of any size.

    Returns:
        Equivalent value in range [-9223372036854775808, 9223372036854775807].

    Examples:
        >>> _to_signed64(12345)
        12345
        >>> _to_signed64(2**64 + 100)
        100
        >>> _to_signed64(-1)
        -1
    """
    return ((key + _INT64_OFFSET) & _INT64_MASK) - _INT64_OFFSET


__all__ = [
    "try_advisory_xact_lock",
]
