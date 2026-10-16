"""asyncpg connection class with uuid prepared-statement names."""

import uuid

import asyncpg


class AsyncCConnection(asyncpg.Connection):
    """asyncpg connection whose prepared statements are named with a uuid.

    Overrides only the private ``_get_unique_id``, so statement names are unique across
    every connection rather than counted per connection. The only failure that prevents
    is two clients colliding on a name on a shared server connection
    (https://github.com/sqlalchemy/sqlalchemy/issues/6467). That needs a transaction-mode
    PgBouncer that does not track prepared statements, where a named statement fails
    anyway with ``prepared statement ... does not exist``.

    It is not what makes the library work behind PgBouncer. With
    ``statement_cache_size=0`` (the default) asyncpg sends unnamed statements and asks for
    no name at all; with ``statement_cache_size > 0`` PgBouncer has to track prepared
    statements itself (1.21+ with ``max_prepared_statements > 0``, the default from 1.24),
    and then rewrites the names per server connection. Kept as the default connection
    class of :func:`create_async_session_manager` because it is harmless.
    """

    def _get_unique_id(self, prefix: str) -> str:
        """Generate unique ID for prepared statements.

        Args:
            prefix: Prefix for the unique ID.

        Returns:
            A unique string ID including the prefix and a UUID.
        """
        return f"__asyncpg_{prefix}_{uuid.uuid4()}__"


__all__ = [
    "AsyncCConnection",
]
