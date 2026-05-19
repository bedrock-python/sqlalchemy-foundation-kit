"""PostgreSQL advisory locks (async)."""

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
    int_key = hash(key) if isinstance(key, str) else key

    result = await session.execute(
        text("SELECT pg_try_advisory_xact_lock(:k)"),
        {"k": _to_signed64(int_key)},
    )
    return bool(result.scalar())


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
