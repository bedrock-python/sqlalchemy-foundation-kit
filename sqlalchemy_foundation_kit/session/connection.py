"""Custom connection class for pgbouncer compatibility (async)."""

import uuid

import asyncpg


class AsyncCConnection(asyncpg.Connection):
    """Custom async connection class for pgbouncer magic.

    This subclass overrides only the private method _get_unique_id so that
    prepared statement identifiers are unique per connection. That is required
    when using pgbouncer in transaction mode, where the same server connection
    may be reused for different logical connections.

    See: https://github.com/sqlalchemy/sqlalchemy/issues/6467
    """

    def _get_unique_id(self, prefix: str) -> str:
        """Generate unique ID for prepared statements.

        Args:
            prefix: Prefix for the unique ID.

        Returns:
            A unique string ID including the prefix and a UUID.
        """
        return f"__asyncpg_{prefix}_{uuid.uuid4()}__"
