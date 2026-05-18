"""PostgreSQL advisory locks (async)."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def try_advisory_xact_lock(session: AsyncSession, key: str | int) -> bool:
    """Acquire a Postgres transaction-scoped advisory lock.

    Uses ``pg_try_advisory_xact_lock``: non-blocking, released automatically
    at transaction end. String keys are hashed to integers. The key is then
    truncated to signed 64-bit as Postgres expects.
    """
    # Convert string keys to integers via hashing
    int_key = hash(key) if isinstance(key, str) else key

    result = await session.execute(
        text("SELECT pg_try_advisory_xact_lock(:k)"),
        {"k": _to_signed64(int_key)},
    )
    return bool(result.scalar())


def _to_signed64(key: int) -> int:
    """Truncate integer to signed 64-bit range as PostgreSQL expects."""
    return ((key + (1 << 63)) & ((1 << 64) - 1)) - (1 << 63)
