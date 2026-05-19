"""Foundation layer for SQLAlchemy-based services with UoW, session management, and observability."""

from importlib.metadata import PackageNotFoundError, version

# Base ORM
from .base import (
    DB_NAMING_CONVENTION,
    Base,
    BaseTable,
    DatetimeColumnsMixin,
    GenericJSONDict,
    PoolClassStr,
    PoolRegistry,
    PydanticJSONB,
    UnConstrainedEnum,
    build_engine_kwargs,
    configure_orjson_serialization,
    load_orm_metadata,
    register_pool_class,
    resolve_pool_class,
)

# Config
from .config import (
    ConnectionSettingsProtocol,
    PoolSettingsProtocol,
    PostgresSettingsProtocol,
    QuerySettingsProtocol,
)

# Protocols
from .protocols import (
    CheckoutRecorder,
    ErrorRecorder,
    PoolStatsRecorder,
    PostgresMetricsProtocol,
)

# Session Management
from .session import (
    DEFAULT_HEALTHCHECK_QUERY,
    DEFAULT_RETRY_CONFIG,
    AsyncCConnection,
    AsyncSessionManager,
    AsyncSessionManagerBuilder,
    RetryConfig,
    create_async_session_manager,
    retry_async_connection,
    try_advisory_xact_lock,
)

# Unit of Work
from .uow import (
    AsyncSQLAlchemyUnitOfWork,
    AsyncSQLAlchemyUowTransaction,
    AsyncUnitOfWork,
    AsyncUowTransaction,
    IsolationLevel,
    PostgresAdvisoryLockMixin,
    SupportsAdvisoryLock,
)

try:
    __version__ = version("sqlalchemy-foundation-kit")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.1.0"

__all__ = [  # noqa: RUF022
    # Base ORM
    "DB_NAMING_CONVENTION",
    "Base",
    "BaseTable",
    "DatetimeColumnsMixin",
    "GenericJSONDict",
    "PoolClassStr",
    "PoolRegistry",
    "PydanticJSONB",
    "UnConstrainedEnum",
    "build_engine_kwargs",
    "configure_orjson_serialization",
    "load_orm_metadata",
    "register_pool_class",
    "resolve_pool_class",
    # Config
    "ConnectionSettingsProtocol",
    "PoolSettingsProtocol",
    "PostgresSettingsProtocol",
    "QuerySettingsProtocol",
    # Protocols
    "CheckoutRecorder",
    "ErrorRecorder",
    "PoolStatsRecorder",
    "PostgresMetricsProtocol",
    # Session Management
    "DEFAULT_HEALTHCHECK_QUERY",
    "DEFAULT_RETRY_CONFIG",
    "AsyncCConnection",
    "AsyncSessionManager",
    "AsyncSessionManagerBuilder",
    "RetryConfig",
    "create_async_session_manager",
    "retry_async_connection",
    "try_advisory_xact_lock",
    # Unit of Work
    "AsyncSQLAlchemyUnitOfWork",
    "AsyncSQLAlchemyUowTransaction",
    "AsyncUnitOfWork",
    "AsyncUowTransaction",
    "IsolationLevel",
    "PostgresAdvisoryLockMixin",
    "SupportsAdvisoryLock",
    # Version
    "__version__",
]

# Note: contrib modules are available via:
# - from sqlalchemy_foundation_kit.contrib.settings import BasePostgresConfig
# - from sqlalchemy_foundation_kit.contrib.metrics import PostgresMetrics
# - from sqlalchemy_foundation_kit.contrib.di import AsyncDatabaseProvider, AsyncUnitOfWorkProvider
