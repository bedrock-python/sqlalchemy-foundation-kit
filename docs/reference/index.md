# API Reference

Complete API documentation auto-generated from source code.

## Core Module

The main `sqlalchemy_foundation_kit` module exports all core functionality.

::: sqlalchemy_foundation_kit
    options:
      heading_level: 3
      show_root_heading: true
      show_root_toc_entry: true
      show_source: true
      members:
        - Base
        - BaseTable
        - DatetimeColumnsMixin
        - PydanticJSONB
        - UnConstrainedEnum
        - GenericJSONDict
        - AsyncSessionManager
        - AsyncSessionManagerBuilder
        - AsyncCConnection
        - create_async_session_manager
        - AsyncUnitOfWork
        - AsyncSQLAlchemyUnitOfWork
        - AsyncUowTransaction
        - AsyncSQLAlchemyUowTransaction
        - IsolationLevel
        - PostgresAdvisoryLockMixin
        - SupportsAdvisoryLock
        - try_advisory_xact_lock
        - retry_async_connection
        - RetryConfig
        - PostgresSettingsProtocol
        - ConnectionSettingsProtocol
        - PoolSettingsProtocol
        - QuerySettingsProtocol
        - PostgresMetricsProtocol
        - build_engine_kwargs
        - resolve_pool_class
        - register_pool_class
        - load_orm_metadata
        - configure_orjson_serialization
        - DB_NAMING_CONVENTION

---

## Base ORM Models

Base classes and mixins for SQLAlchemy models.

::: sqlalchemy_foundation_kit.base.models
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - Base
        - BaseTable
        - DatetimeColumnsMixin
        - DB_NAMING_CONVENTION

### Example Usage

```python
from uuid import UUID, uuid4
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_foundation_kit import BaseTable, DatetimeColumnsMixin

class UserDB(BaseTable, DatetimeColumnsMixin):
    """User ORM model with automatic timestamps."""
    __tablename__ = "users"
    __created_at_index__ = True  # Creates index on created_at

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(unique=True)
    username: Mapped[str]

# Provides:
# - created_at: Mapped[datetime] (server default)
# - updated_at: Mapped[datetime] (auto-updated)
# - __repr__: String representation
```

---

## Custom Types

Custom SQLAlchemy types for PostgreSQL.

::: sqlalchemy_foundation_kit.base.types
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - PydanticJSONB
        - GenericJSONDict

### Example Usage

```python
from pydantic import BaseModel
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_foundation_kit import PydanticJSONB, BaseTable

class UserPreferences(BaseModel):
    theme: str
    language: str

class UserDB(BaseTable):
    __tablename__ = "users"
    
    id: Mapped[UUID] = mapped_column(primary_key=True)
    preferences: Mapped[UserPreferences] = mapped_column(
        PydanticJSONB(UserPreferences)
    )

# Automatically validated on read/write
user = UserDB(
    preferences=UserPreferences(theme="dark", language="en")
)
```

---

## Session Management

Async session manager with connection pooling and health checks.

::: sqlalchemy_foundation_kit.session.manager
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - AsyncSessionManager
        - attach_metrics

::: sqlalchemy_foundation_kit.session.builder
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - AsyncSessionManagerBuilder
        - create_async_session_manager

::: sqlalchemy_foundation_kit.session.connection
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - AsyncCConnection

::: sqlalchemy_foundation_kit.session.retry
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - retry_async_connection
        - RetryConfig
        - DEFAULT_RETRY_CONFIG

::: sqlalchemy_foundation_kit.session.locks
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - try_advisory_xact_lock

### Example Usage

```python
from sqlalchemy_foundation_kit import create_async_session_manager

# Create session manager
session_manager = create_async_session_manager(
    settings.postgres,
    metrics=metrics,
)

# Transactional context
async with session_manager.get_transaction() as session:
    user = UserDB(email="user@example.com")
    session.add(user)
    # Auto-commit on exit, auto-rollback on exception

# Health check
is_healthy = await session_manager.healthcheck()

# Graceful shutdown
await session_manager.close(timeout=30.0)
```

---

## Unit of Work

Unit of Work pattern for transactional consistency.

::: sqlalchemy_foundation_kit.uow.protocols
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - AsyncUnitOfWork
        - AsyncUowTransaction
        - SupportsAdvisoryLock

::: sqlalchemy_foundation_kit.uow.sqlalchemy
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - AsyncSQLAlchemyUnitOfWork
        - AsyncSQLAlchemyUowTransaction
        - PostgresAdvisoryLockMixin
        - normalize_isolation_level
        - apply_isolation_level

::: sqlalchemy_foundation_kit.uow.enums
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - IsolationLevel

### Example Usage

```python
from sqlalchemy_foundation_kit import (
    AsyncSQLAlchemyUnitOfWork,
    AsyncSQLAlchemyUowTransaction,
    PostgresAdvisoryLockMixin,
)

# Define transaction with repositories
class MyTransaction(AsyncSQLAlchemyUowTransaction, PostgresAdvisoryLockMixin):
    def __init__(self, session):
        super().__init__(session)
        self._users = None
    
    @property
    def users(self):
        if self._users is None:
            self._users = PostgresUserRepository(self.session)
        return self._users

# Create UoW
class MyUnitOfWork(AsyncSQLAlchemyUnitOfWork[MyTransaction]):
    def __init__(self, session_maker):
        super().__init__(session_maker, transaction_factory=MyTransaction)

# Use in application
async with uow.transaction() as tx:
    # All operations in single transaction
    user = await tx.users.create(email="user@example.com")
    
    # Advisory lock
    if await tx.try_advisory_lock("process_payments"):
        await process_payments()
```

---

## Configuration Protocols

Type-safe configuration protocols.

::: sqlalchemy_foundation_kit.config.postgres
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - PostgresSettingsProtocol
        - ConnectionSettingsProtocol
        - PoolSettingsProtocol
        - QuerySettingsProtocol

### Example Usage

```python
from dataclasses import dataclass
from pydantic import SecretStr
from sqlalchemy_foundation_kit import PostgresSettingsProtocol

@dataclass
class MyPostgresConfig:
    connection: ConnectionSettingsProtocol
    pool: PoolSettingsProtocol
    query: QuerySettingsProtocol
    application_name: str = "my-service"
    
    def to_dsn(self) -> str:
        return f"postgresql+asyncpg://..."
```

---

## Metrics Protocols

Observability protocols for monitoring.

::: sqlalchemy_foundation_kit.protocols.metrics
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - PostgresMetricsProtocol
        - PoolStatsRecorder
        - CheckoutRecorder
        - ErrorRecorder

### Example Usage

```python
from sqlalchemy_foundation_kit.protocols import PostgresMetricsProtocol

class CustomMetrics:
    """Custom metrics implementation."""
    
    def record_pool_stats(
        self,
        pool_size: int,
        pool_checked_out: int,
        pool_overflow: int,
    ) -> None:
        # Record pool statistics
        pass
    
    def record_checkout(self, duration: float) -> None:
        # Record connection checkout duration
        pass
    
    def record_error(self, error_type: str, is_timeout: bool) -> None:
        # Record database errors
        pass
```

---

## Contrib Modules

Optional modules with extra functionality.

### contrib.settings

Pydantic-based configuration (requires `[settings]` extra).

::: sqlalchemy_foundation_kit.contrib.settings.postgres
    options:
      heading_level: 4
      show_root_heading: false
      members:
        - BasePostgresConfig
        - ConnectionSettings
        - PoolSettings
        - QuerySettings
        - BasePostgresMigrationsConfig

### contrib.metrics

Prometheus metrics (requires `[metrics]` extra).

::: sqlalchemy_foundation_kit.contrib.metrics.postgres
    options:
      heading_level: 4
      show_root_heading: false
      members:
        - PostgresMetrics

### contrib.di (Dishka)

Dishka dependency injection providers (requires `[dishka]` extra).

::: sqlalchemy_foundation_kit.contrib.di.database
    options:
      heading_level: 4
      show_root_heading: false
      members:
        - AsyncDatabaseProvider
        - AsyncUnitOfWorkProvider

::: sqlalchemy_foundation_kit.contrib.di.metrics
    options:
      heading_level: 4
      show_root_heading: false
      members:
        - PrometheusPostgresMetricsProvider

### contrib.dependency_injector

dependency-injector containers (requires `[dependency-injector]` extra).

::: sqlalchemy_foundation_kit.contrib.dependency_injector.database
    options:
      heading_level: 4
      show_root_heading: false
      members:
        - DatabaseContainer
        - AsyncDatabaseResourceProvider

::: sqlalchemy_foundation_kit.contrib.dependency_injector.metrics
    options:
      heading_level: 4
      show_root_heading: false
      members:
        - PrometheusMetricsContainer

### contrib.telemetry

OpenTelemetry instrumentation (requires `[telemetry]` extra).

::: sqlalchemy_foundation_kit.contrib.telemetry.instrumentations
    options:
      heading_level: 4
      show_root_heading: false
      members:
        - instrument_sqlalchemy
        - instrument_asyncpg

::: sqlalchemy_foundation_kit.contrib.telemetry.uow
    options:
      heading_level: 4
      show_root_heading: false
      members:
        - TracedAsyncUnitOfWork

---

## Engine Utilities

Low-level engine configuration utilities.

::: sqlalchemy_foundation_kit.base.engine
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - build_engine_kwargs
        - resolve_pool_class
        - register_pool_class
        - PoolRegistry
        - PoolClassStr

::: sqlalchemy_foundation_kit.base.metadata
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - load_orm_metadata

::: sqlalchemy_foundation_kit.base.serialization
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - configure_orjson_serialization

---

## Type Hints

Internal type hints used across the library.

::: sqlalchemy_foundation_kit._typing
    options:
      heading_level: 3
      show_root_heading: false
      members: true
