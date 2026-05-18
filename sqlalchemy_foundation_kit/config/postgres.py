"""PostgreSQL configuration."""

from __future__ import annotations

from typing import Protocol


class PasswordLike(Protocol):
    """Protocol for secret string types (e.g., ``pydantic.SecretStr``).

    Allows ``ConnectionSettingsProtocol.password`` to accept either a plain ``str``
    or a SecretStr-like object without forcing pydantic as a dependency in the core layer.
    """

    def get_secret_value(self) -> str:
        """Return the underlying secret value as a plain string."""
        ...


class ConnectionSettingsProtocol(Protocol):
    """Protocol for PostgreSQL connection settings.

    Defines connection parameters required for establishing database connections.

    Attributes:
        host: PostgreSQL server hostname or IP address.
        port: PostgreSQL server port number.
        user: Database username for authentication.
        password: Database password — either a plain ``str`` or a SecretStr-like object
            implementing ``get_secret_value()``.
        database: Target database name.
    """

    host: str
    port: int
    user: str
    password: PasswordLike | str
    database: str


class PoolSettingsProtocol(Protocol):
    """Protocol for PostgreSQL connection pool settings.

    Defines pool configuration for SQLAlchemy engine connection management.

    Attributes:
        kind: Connection pool implementation (queue, static, etc.).
        size: Number of connections to maintain in pool.
        max_overflow: Additional connections allowed when pool exhausted.
        pre_ping: Test connection health before checkout.
        recycle: Recycle connections after N seconds.
        timeout: Timeout for acquiring connection from pool.

    Examples:
        >>> pool: PoolSettingsProtocol = ...
        >>> if pool.size > 100:
        ...     logger.warning("Large pool size detected")
    """

    kind: str | type
    size: int | None
    max_overflow: int | None
    pre_ping: bool
    recycle: int | None
    timeout: float | None


class QuerySettingsProtocol(Protocol):
    """Protocol for PostgreSQL query execution settings.

    Defines query behavior, caching, and transaction isolation configuration.

    Attributes:
        echo: Enable SQL statement logging.
        statement_cache_size: Prepared statement cache size.
        prepared_statement_cache_size: Server-side prepared statement cache size.
        isolation_level: Transaction isolation level.

    Examples:
        >>> query: QuerySettingsProtocol = ...
        >>> if query.echo:
        ...     logger.info("SQL echo enabled")
    """

    echo: bool
    statement_cache_size: int | None
    prepared_statement_cache_size: int | None
    isolation_level: str | None


class PostgresSettingsProtocol(Protocol):
    """Protocol for PostgreSQL configuration.

    Organized protocol with grouped settings for connection, pool, and query configuration.

    Attributes:
        connection: Connection parameters (host, port, user, database).
        pool: Connection pool settings.
        query: Query execution and transaction settings.
        application_name: Application identifier for connections.
        db_schema: Optional PostgreSQL schema name.
        use_orjson_serialization: Enable orjson for JSON operations.
        jit: JIT compilation setting (PgBouncer compatibility).

    Examples:
        Implementing the protocol:
            >>> class MyConfig:
            ...     connection: ConnectionSettingsProtocol
            ...     pool: PoolSettingsProtocol
            ...     query: QuerySettingsProtocol
            ...     application_name: str = "my-app"
            ...     db_schema: str | None = None
            ...     use_orjson_serialization: bool = True
            ...     jit: str | None = "off"
            ...
            ...     def to_dsn(self) -> str:
            ...         return f"postgresql://{self.connection.user}@{self.connection.host}..."

        Using the protocol:
            >>> def create_engine(config: PostgresSettingsProtocol):
            ...     dsn = config.to_dsn()
            ...     pool_size = config.pool.pool_size
            ...     echo = config.query.echo
    """

    connection: ConnectionSettingsProtocol
    pool: PoolSettingsProtocol
    query: QuerySettingsProtocol
    application_name: str
    db_schema: str | None
    use_orjson_serialization: bool
    jit: str | None

    def to_dsn(self) -> str:
        """Convert config to DSN string.

        Returns PostgreSQL connection string in format:
        postgresql+asyncpg://user:password@host:port/database

        Examples:
            >>> config.to_dsn()
            'postgresql+asyncpg://user:***@localhost:5432/mydb'
        """
        ...
