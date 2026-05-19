"""Base PostgreSQL configuration using pydantic-settings."""

from __future__ import annotations

from typing import Literal
from urllib.parse import quote_plus

from ...base.engine import PoolClassStr

try:
    from pydantic import BaseModel, Field, SecretStr, model_validator
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError as _e:
    raise ImportError(
        "pydantic and pydantic-settings are required for this functionality. "
        "Install with: pip install 'sqlalchemy-foundation-kit[settings]'"
    ) from _e

PostgresIsolationLevel = Literal["READ UNCOMMITTED", "READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"]
PostgresJit = Literal["off", "on"]


class ConnectionSettings(BaseModel):
    """PostgreSQL connection configuration.

    Groups all connection-related parameters: host, port, credentials, and database name.

    Examples:
        >>> connection = ConnectionSettings(
        ...     host="localhost",
        ...     port=5432,
        ...     user="postgres",
        ...     password=SecretStr("secret"),
        ...     database="mydb",
        ... )
    """

    host: str = Field(default="localhost", description="PostgreSQL host")
    port: int = Field(default=5432, ge=1, le=65535, description="PostgreSQL port")
    user: str = Field(default="postgres", description="PostgreSQL user")
    password: SecretStr = Field(description="PostgreSQL password")
    database: str = Field(description="Database name")


class PoolSettings(BaseModel):
    """PostgreSQL connection pool configuration.

    Groups all connection pool-related parameters for SQLAlchemy engine.

    Examples:
        >>> pool = PoolSettings(size=10, max_overflow=20)
    """

    kind: PoolClassStr = Field(
        default="async_adapted_queue",
        description="PostgreSQL pool implementation kind",
    )
    size: int = Field(default=10, ge=1, description="Connection pool size")
    max_overflow: int = Field(default=20, ge=0, description="Additional connections when pool is exhausted")
    pre_ping: bool = Field(default=True, description="Check connection health before use (pre-ping)")
    recycle: int = Field(default=3600, ge=-1, description="Recycle connections after N seconds")
    timeout: float = Field(
        default=30.0,
        ge=0,
        description="Seconds to wait before giving up on getting connection",
    )

    @model_validator(mode="after")
    def _validate_pool_settings(self) -> PoolSettings:
        """Validate pool configuration constraints."""
        if self.kind == "static" and self.max_overflow > 0:
            raise ValueError(f"max_overflow must be 0 for static pool, got {self.max_overflow}")
        return self


class QuerySettings(BaseModel):
    """PostgreSQL query and performance configuration.

    Groups query execution, caching, and transaction isolation settings.

    Examples:
        >>> query = QuerySettings(echo=False, isolation_level="READ COMMITTED")
    """

    echo: bool = Field(default=False, description="Echo SQL queries")
    statement_cache_size: int = Field(default=0, ge=0, description="Statement cache size")
    prepared_statement_cache_size: int = Field(default=0, ge=0, description="Prepared statement cache size")
    isolation_level: PostgresIsolationLevel | None = Field(default=None, description="Transaction isolation level")


class BasePostgresConfig(BaseSettings):
    """Base PostgreSQL configuration.

    Organized configuration for PostgreSQL database connections with grouped settings.

    Attributes:
        connection: Connection parameters (host, port, credentials, database).
        pool: Connection pool configuration (size, overflow, timeouts).
        query: Query execution settings (echo, caching, isolation level).
        application_name: Application name for connection identification.
        db_schema: Optional PostgreSQL schema name.
        use_orjson_serialization: Use orjson for JSON serialization (requires orjson).
        jit: JIT compilation setting (off/on) for PgBouncer compatibility.
        metrics_enabled: Enable connection pool metrics collection.

    Examples:
        >>> config = BasePostgresConfig(
        ...     connection=ConnectionSettings(
        ...         host="localhost",
        ...         user="postgres",
        ...         password=SecretStr("secret"),
        ...         database="mydb",
        ...     ),
        ...     application_name="my-service",
        ... )
        >>> dsn = config.to_dsn()
        >>> host = config.connection.host
        >>> pool_size = config.pool.size
    """

    # Grouped configuration
    connection: ConnectionSettings = Field(description="PostgreSQL connection settings")
    pool: PoolSettings = Field(default_factory=PoolSettings, description="Connection pool settings")
    query: QuerySettings = Field(default_factory=QuerySettings, description="Query execution settings")

    # Top-level settings
    application_name: str = Field(description="Application name for PostgreSQL")
    db_schema: str | None = Field(default=None, description="PostgreSQL schema name")
    use_orjson_serialization: bool = Field(
        default=True,
        description="Use orjson for JSON serialization (requires orjson installed)",
    )
    jit: PostgresJit | None = Field(default="off", description="JIT setting (off/on)")
    metrics_enabled: bool = Field(default=False, description="Enable PostgreSQL metrics")

    def __repr__(self) -> str:
        """Return representation with masked password."""
        return f"{self.__class__.__name__}(dsn={self.to_dsn(mask_password=True)!r})"

    def to_dsn(self, driver: str | None = "asyncpg", mask_password: bool = False) -> str:
        """Build PostgreSQL DSN for async connections.

        This library is async-only, so DSN always includes asyncpg driver by default.

        Args:
            driver: Driver name (default: 'asyncpg' for async connections).
                Pass None to omit driver suffix.
            mask_password: If True, the password will be masked (default: False).

        Returns:
            PostgreSQL connection string (e.g., 'postgresql+asyncpg://user:pass@host:5432/db').

        Examples:
            >>> config.to_dsn()
            'postgresql+asyncpg://user:secret@localhost:5432/mydb'
            >>> config.to_dsn(mask_password=True)
            'postgresql+asyncpg://user:**********@localhost:5432/mydb'
        """
        user = quote_plus(self.connection.user)
        password = "**********" if mask_password else quote_plus(self.connection.password.get_secret_value())
        scheme = f"postgresql+{driver}" if driver else "postgresql"
        return f"{scheme}://{user}:{password}@{self.connection.host}:{self.connection.port}/{self.connection.database}"


class BasePostgresMigrationsConfig(BaseSettings):
    """Base configuration for PostgreSQL database migrations."""

    model_config = SettingsConfigDict(
        extra="ignore",
        env_nested_delimiter="__",
        case_sensitive=False,
    )

    postgres: BasePostgresConfig


__all__ = [
    "BasePostgresConfig",
    "BasePostgresMigrationsConfig",
    "ConnectionSettings",
    "PoolSettings",
    "QuerySettings",
]
