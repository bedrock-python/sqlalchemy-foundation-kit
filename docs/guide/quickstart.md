# Quick Start

This guide will get you up and running with `sqlalchemy-foundation-kit` in 5 minutes.

## Installation

Install the library with the extras you need:

```bash
# Basic installation (core features only)
pip install sqlalchemy-foundation-kit

# With Pydantic settings (recommended)
pip install sqlalchemy-foundation-kit[settings]

# With Prometheus metrics
pip install sqlalchemy-foundation-kit[settings,metrics]

# With OpenTelemetry tracing
pip install sqlalchemy-foundation-kit[settings,telemetry]

# All features
pip install sqlalchemy-foundation-kit[all]
```

## Basic Usage

### 1. Define Your Configuration

Using `BasePostgresConfig` from `contrib.settings`:

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings
from sqlalchemy_foundation_kit.contrib.settings import BasePostgresConfig

class Settings(BaseSettings):
    postgres: BasePostgresConfig = BasePostgresConfig(
        connection={
            "host": "localhost",
            "port": 5432,
            "user": "postgres",
            "password": SecretStr("secret"),
            "database": "mydb",
        },
        pool={
            "size": 10,
            "max_overflow": 20,
            "timeout": 30.0,
            "pre_ping": True,
        },
        query={
            "echo": False,
            "statement_cache_size": 0,
        },
        application_name="my-service",
    )

settings = Settings()
```

Or implement `PostgresSettingsProtocol` directly if you don't want `pydantic-settings`:

```python
from dataclasses import dataclass
from pydantic import SecretStr

@dataclass
class ConnectionSettings:
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: SecretStr = SecretStr("secret")
    database: str = "mydb"

@dataclass
class PoolSettings:
    kind: str = "async_adapted_queue"
    size: int = 10
    max_overflow: int = 20
    pre_ping: bool = True
    timeout: float = 30.0

@dataclass
class QuerySettings:
    echo: bool = False
    statement_cache_size: int = 0

@dataclass
class PostgresConfig:
    connection: ConnectionSettings = ConnectionSettings()
    pool: PoolSettings = PoolSettings()
    query: QuerySettings = QuerySettings()
    application_name: str = "my-service"
    
    def to_dsn(self) -> str:
        conn = self.connection
        password = conn.password.get_secret_value() if hasattr(conn.password, 'get_secret_value') else conn.password
        return f"postgresql+asyncpg://{conn.user}:{password}@{conn.host}:{conn.port}/{conn.database}"
```

### 2. Define ORM Models

Use `BaseTable` and `DatetimeColumnsMixin` for automatic naming conventions and timestamps:

```python
from uuid import UUID, uuid4
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_foundation_kit import BaseTable, DatetimeColumnsMixin

class UserDB(BaseTable, DatetimeColumnsMixin):
    """User ORM model."""
    __tablename__ = "users"
    __created_at_index__ = True  # Creates index on created_at

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    username: Mapped[str]
    is_active: Mapped[bool] = mapped_column(default=True)

# DatetimeColumnsMixin provides:
# - created_at: Mapped[datetime] (with server default)
# - updated_at: Mapped[datetime] (auto-updated on changes)
```

### 3. Create Session Manager

`AsyncSessionManager` handles connection pooling, health checks, and graceful shutdown:

```python
from sqlalchemy_foundation_kit import create_async_session_manager

async def main():
    # Create session manager
    session_manager = create_async_session_manager(settings.postgres)
    
    # Use transactional context
    async with session_manager.get_transaction() as session:
        user = UserDB(
            email="john@example.com",
            username="john_doe"
        )
        session.add(user)
        # Auto-commit on exit
        # Auto-rollback on exception
    
    # Graceful shutdown (wait for connections to close)
    await session_manager.close()
```

### 4. Use Unit of Work Pattern

The Unit of Work pattern ensures transactional consistency across multiple repository operations:

```python
from sqlalchemy_foundation_kit import (
    AsyncSQLAlchemyUnitOfWork,
    AsyncSQLAlchemyUowTransaction,
)

# 1. Define your transaction with repositories
class MyTransaction(AsyncSQLAlchemyUowTransaction):
    def __init__(self, session):
        super().__init__(session)
        self._users = None
    
    @property
    def users(self):
        """Lazy-loaded user repository."""
        if self._users is None:
            self._users = PostgresUserRepository(self.session)
        return self._users

# 2. Define repository (returns domain entities, not ORM models)
from uuid import UUID
from typing import Protocol

class User:  # Domain entity
    id: UUID
    email: str
    username: str

class UserRepository(Protocol):
    async def create(self, email: str, username: str) -> User: ...
    async def get_by_id(self, user_id: UUID) -> User | None: ...

class PostgresUserRepository:
    def __init__(self, session):
        self._session = session
    
    def _to_entity(self, db_model: UserDB) -> User:
        return User(
            id=db_model.id,
            email=db_model.email,
            username=db_model.username,
        )
    
    async def create(self, email: str, username: str) -> User:
        user_db = UserDB(email=email, username=username)
        self._session.add(user_db)
        await self._session.flush()
        return self._to_entity(user_db)
    
    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self._session.execute(
            select(UserDB).where(UserDB.id == user_id)
        )
        db_model = result.scalar_one_or_none()
        return self._to_entity(db_model) if db_model else None

# 3. Create UoW
class MyUnitOfWork(AsyncSQLAlchemyUnitOfWork[MyTransaction]):
    def __init__(self, session_maker):
        super().__init__(
            session_maker,
            transaction_factory=MyTransaction
        )

# 4. Use in application layer
class CreateUserUseCase:
    def __init__(self, uow: MyUnitOfWork):
        self._uow = uow
    
    async def execute(self, email: str, username: str) -> User:
        async with self._uow.transaction() as tx:
            # All operations in single transaction
            user = await tx.users.create(email=email, username=username)
            
            # Add outbox event in same transaction
            # await tx.outbox.create(UserCreatedEvent(...))
        
        return user  # Transaction auto-committed
```

## Complete Example

Here's a complete working example:

```python
from uuid import UUID, uuid4
from pydantic import SecretStr
from pydantic_settings import BaseSettings
from sqlalchemy import select
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_foundation_kit import (
    create_async_session_manager,
    AsyncSQLAlchemyUnitOfWork,
    AsyncSQLAlchemyUowTransaction,
    BaseTable,
    DatetimeColumnsMixin,
)
from sqlalchemy_foundation_kit.contrib.settings import BasePostgresConfig

# Configuration
class Settings(BaseSettings):
    postgres: BasePostgresConfig = BasePostgresConfig(
        connection={
            "host": "localhost",
            "port": 5432,
            "user": "postgres",
            "password": SecretStr("secret"),
            "database": "mydb",
        }
    )

settings = Settings()

# ORM Model
class UserDB(BaseTable, DatetimeColumnsMixin):
    __tablename__ = "users"
    __created_at_index__ = True

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(unique=True)
    username: Mapped[str]

# Domain Entity
class User:
    def __init__(self, id: UUID, email: str, username: str):
        self.id = id
        self.email = email
        self.username = username

# Repository
class PostgresUserRepository:
    def __init__(self, session):
        self._session = session
    
    def _to_entity(self, db_model: UserDB) -> User:
        return User(
            id=db_model.id,
            email=db_model.email,
            username=db_model.username,
        )
    
    async def create(self, email: str, username: str) -> User:
        user_db = UserDB(email=email, username=username)
        self._session.add(user_db)
        await self._session.flush()
        return self._to_entity(user_db)
    
    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(UserDB).where(UserDB.email == email)
        )
        db_model = result.scalar_one_or_none()
        return self._to_entity(db_model) if db_model else None

# Transaction
class MyTransaction(AsyncSQLAlchemyUowTransaction):
    def __init__(self, session):
        super().__init__(session)
        self._users = None
    
    @property
    def users(self):
        if self._users is None:
            self._users = PostgresUserRepository(self.session)
        return self._users

# Unit of Work
class MyUnitOfWork(AsyncSQLAlchemyUnitOfWork[MyTransaction]):
    def __init__(self, session_maker):
        super().__init__(session_maker, transaction_factory=MyTransaction)

# Use Case
class CreateUserUseCase:
    def __init__(self, uow: MyUnitOfWork):
        self._uow = uow
    
    async def execute(self, email: str, username: str) -> User:
        async with self._uow.transaction() as tx:
            existing = await tx.users.get_by_email(email)
            if existing:
                raise ValueError(f"User with email {email} already exists")
            
            user = await tx.users.create(email=email, username=username)
        
        return user

# Main application
async def main():
    # Create session manager
    session_manager = create_async_session_manager(settings.postgres)
    
    # Create UoW
    uow = MyUnitOfWork(session_manager.session_maker)
    
    # Create use case
    use_case = CreateUserUseCase(uow)
    
    # Execute
    try:
        user = await use_case.execute(
            email="john@example.com",
            username="john_doe"
        )
        print(f"Created user: {user.email}")
    except ValueError as e:
        print(f"Error: {e}")
    
    # Cleanup
    await session_manager.close()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Next Steps

- **[Configuration](configuration.md)** — Learn about all configuration options
- **[Advanced Usage](advanced.md)** — Metrics, telemetry, DI, advisory locks
- **[API Reference](../reference/index.md)** — Complete API documentation

## Common Patterns

### Health Check

```python
async def health_check():
    """Check database connectivity."""
    is_healthy = await session_manager.healthcheck()
    return {"database": "healthy" if is_healthy else "unhealthy"}
```

### Graceful Shutdown

```python
import signal

async def shutdown(session_manager: AsyncSessionManager):
    """Graceful shutdown handler."""
    print("Shutting down...")
    await session_manager.close(timeout=30.0)
    print("Database connections closed")

# Register signal handler
loop = asyncio.get_event_loop()
loop.add_signal_handler(
    signal.SIGTERM,
    lambda: asyncio.create_task(shutdown(session_manager))
)
```

### Retry on Connection Error

```python
from sqlalchemy_foundation_kit import retry_async_connection, DEFAULT_RETRY_CONFIG

@retry_async_connection(config=DEFAULT_RETRY_CONFIG)
async def fetch_user(session, user_id: UUID):
    """Retries on connection errors."""
    result = await session.execute(
        select(UserDB).where(UserDB.id == user_id)
    )
    return result.scalar_one_or_none()
```

### Custom JSON Type

```python
from pydantic import BaseModel
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_foundation_kit import PydanticJSONB

class UserMetadata(BaseModel):
    theme: str
    language: str

class UserDB(BaseTable):
    __tablename__ = "users"
    
    id: Mapped[UUID] = mapped_column(primary_key=True)
    metadata: Mapped[UserMetadata] = mapped_column(
        PydanticJSONB(UserMetadata)
    )

# Usage
user = UserDB(
    metadata=UserMetadata(theme="dark", language="en")
)
# Automatically serialized to JSONB in database
```
